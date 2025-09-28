#include "eskf.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdio.h>

#define DEG_TO_RAD (M_PI / 180.0)
#define RAD_TO_DEG (180.0 / M_PI)
#define EARTH_RADIUS_M 6371000.0

// Simple coordinate transformation (without pyproj)
void lla_to_enu(const double* init_lla, const double* target_lla, vec3_t* enu) {
    double lat_ref = init_lla[0] * DEG_TO_RAD;
    double lon_ref = init_lla[1] * DEG_TO_RAD;
    double lat = target_lla[0] * DEG_TO_RAD;
    double lon = target_lla[1] * DEG_TO_RAD;

    double cos_lat_ref = cos(lat_ref);

    double dlon = lon - lon_ref;
    double dlat = lat - lat_ref;

    // Approximate ENU conversion
    enu->data[0] = EARTH_RADIUS_M * dlon * cos_lat_ref;  // East
    enu->data[1] = EARTH_RADIUS_M * dlat;                 // North
    enu->data[2] = target_lla[2] - init_lla[2];          // Up
}

void enu_to_lla(const double* init_lla, const vec3_t* enu, double* lla) {
    double lat_ref = init_lla[0] * DEG_TO_RAD;
    double lon_ref = init_lla[1] * DEG_TO_RAD;
    double cos_lat_ref = cos(lat_ref);

    double dlat = enu->data[1] / EARTH_RADIUS_M;
    double dlon = enu->data[0] / (EARTH_RADIUS_M * cos_lat_ref);

    lla[0] = (lat_ref + dlat) * RAD_TO_DEG;
    lla[1] = (lon_ref + dlon) * RAD_TO_DEG;
    lla[2] = init_lla[2] + enu->data[2];
}

// Helper functions
static void compute_gravity_from_acceleration(const eskf_t* eskf, vec3_t* gravity_direction) {
    vec3_t acc_sum;
    vec3_zero(&acc_sum);

    int count = eskf->imu_buffer_count < IMU_BUFFER_SIZE ?
                eskf->imu_buffer_count : IMU_BUFFER_SIZE;

    for (int i = 0; i < count; i++) {
        vec3_add(&acc_sum, &acc_sum, &eskf->imu_buffer[i].acc);
    }

    vec3_scale(gravity_direction, &acc_sum, 1.0f / (float)count);
    vec3_normalize(gravity_direction, gravity_direction);
}

static void compute_initial_rotation(const vec3_t* gravity_direction, mat3_t* rotation) {
    vec3_t z_axis = {{0, 0, 1}};

    // Check if gravity is already aligned with z-axis
    float dot = vec3_dot(gravity_direction, &z_axis);
    if (fabs(dot - 1.0f) < 1e-6f) {
        mat3_identity(rotation);
        return;
    }

    // Compute rotation to align gravity with z-axis
    vec3_t v;
    vec3_cross(&v, gravity_direction, &z_axis);

    float s = vec3_norm(&v);
    float c = dot;

    if (s > 1e-6f) {
        mat3_t vx;
        mat3_skew(&vx, &v);

        mat3_t vx2;
        mat3_multiply(&vx2, &vx, &vx);

        mat3_identity(rotation);
        mat3_add(rotation, rotation, &vx);

        mat3_t scaled_vx2;
        mat3_scale(&scaled_vx2, &vx2, (1.0f - c) / (s * s));
        mat3_add(rotation, rotation, &scaled_vx2);
    } else {
        mat3_identity(rotation);
    }
}

static float find_closest_rail_point(const eskf_t* eskf, double lat, double lon,
                                    double* best_lat, double* best_lon) {
    if (eskf->rail_node_count < 2) {
        *best_lat = lat;
        *best_lon = lon;
        return 1e6f;  // Large distance
    }

    float min_dist = 1e6f;
    *best_lat = lat;
    *best_lon = lon;

    for (int i = 0; i < eskf->rail_node_count - 1; i++) {
        float lat1 = eskf->rail_nodes[i].lat;
        float lon1 = eskf->rail_nodes[i].lon;
        float lat2 = eskf->rail_nodes[i + 1].lat;
        float lon2 = eskf->rail_nodes[i + 1].lon;

        float dx = lon2 - lon1;
        float dy = lat2 - lat1;

        if (fabs(dx) < 1e-10f && fabs(dy) < 1e-10f) {
            continue;
        }

        // Project point onto line segment
        float t = ((lon - lon1) * dx + (lat - lat1) * dy) / (dx * dx + dy * dy);
        t = fmaxf(0.0f, fminf(1.0f, t));

        float closest_lon = lon1 + t * dx;
        float closest_lat = lat1 + t * dy;

        // Approximate distance in meters
        float dist_lat = (lat - closest_lat) * 111000.0f;
        float dist_lon = (lon - closest_lon) * 111000.0f * cosf(lat * DEG_TO_RAD);
        float dist = sqrtf(dist_lat * dist_lat + dist_lon * dist_lon);

        if (dist < min_dist) {
            min_dist = dist;
            *best_lat = closest_lat;
            *best_lon = closest_lon;
        }
    }

    return min_dist;
}

// ESKF API implementation
eskf_t* eskf_create(void) {
    eskf_t* eskf = (eskf_t*)calloc(1, sizeof(eskf_t));
    if (!eskf) return NULL;

    // Default configuration
    eskf->config.acc_noise = 0.5f;
    eskf->config.gyro_noise = 0.01f;
    eskf->config.acc_bias_noise = 0.01f;
    eskf->config.gyro_bias_noise = 0.001f;
    eskf->config.gravity.data[0] = 0.0f;
    eskf->config.gravity.data[1] = 0.0f;
    eskf->config.gravity.data[2] = -9.81007f;
    vec3_zero(&eskf->config.I_p_Gps);

    eskf->tunnel_threshold = 5.0;
    eskf->heading_smoothing_factor = 0.5f;

    eskf_reset(eskf);
    return eskf;
}

void eskf_destroy(eskf_t* eskf) {
    if (eskf) {
        free(eskf);
    }
}

void eskf_reset(eskf_t* eskf) {
    eskf->initialized = 0;
    eskf->imu_buffer_count = 0;
    eskf->imu_buffer_index = 0;
    eskf->last_gps_time = 0;
    eskf->in_tunnel = 0;
    eskf->current_satellites = 0;  // Initialize satellite count

    // Reset state
    memset(&eskf->state, 0, sizeof(eskf_state_t));
    mat3_identity(&eskf->state.G_R_I);
    mat15_identity(&eskf->state.cov);
    mat15_scale(&eskf->state.cov, &eskf->state.cov, 0.01f);
}

void eskf_set_config(eskf_t* eskf, const eskf_config_t* config) {
    eskf->config = *config;
}

int eskf_load_rail_nodes(eskf_t* eskf, const rail_node_t* nodes, int count) {
    if (count > MAX_RAIL_NODES) {
        count = MAX_RAIL_NODES;
    }

    memcpy(eskf->rail_nodes, nodes, count * sizeof(rail_node_t));
    eskf->rail_node_count = count;
    return count;
}

// IMU prediction step
static void imu_predict(eskf_t* eskf, const imu_data_t* cur_imu) {
    float dt = (float)(cur_imu->timestamp - eskf->last_imu.timestamp);
    float dt2 = dt * dt;

    // Save last state
    eskf_state_t last_state = eskf->state;

    // Remove biases from measurements
    vec3_t acc_unbias, gyro_unbias;
    vec3_t acc_avg, gyro_avg;

    // Average of last and current IMU
    vec3_add(&acc_avg, &eskf->last_imu.acc, &cur_imu->acc);
    vec3_scale(&acc_avg, &acc_avg, 0.5f);
    vec3_add(&gyro_avg, &eskf->last_imu.gyro, &cur_imu->gyro);
    vec3_scale(&gyro_avg, &gyro_avg, 0.5f);

    vec3_subtract(&acc_unbias, &acc_avg, &last_state.acc_bias);
    vec3_subtract(&gyro_unbias, &gyro_avg, &last_state.gyro_bias);

    // Predict position
    vec3_t acc_global;
    mat3_multiply_vec3(&acc_global, &last_state.G_R_I, &acc_unbias);
    vec3_add(&acc_global, &acc_global, &eskf->config.gravity);

    vec3_t vel_delta, pos_delta;
    vec3_scale(&vel_delta, &last_state.G_v_I, dt);
    vec3_scale(&pos_delta, &acc_global, 0.5f * dt2);
    vec3_add(&eskf->state.G_p_I, &last_state.G_p_I, &vel_delta);
    vec3_add(&eskf->state.G_p_I, &eskf->state.G_p_I, &pos_delta);

    // Predict velocity
    vec3_scale(&vel_delta, &acc_global, dt);
    vec3_add(&eskf->state.G_v_I, &last_state.G_v_I, &vel_delta);

    // Predict rotation
    vec3_t delta_angle;
    vec3_scale(&delta_angle, &gyro_unbias, dt);
    float angle_norm = vec3_norm(&delta_angle);

    if (angle_norm > 1e-12f) {
        mat3_t delta_R;
        mat3_from_axis_angle(&delta_R, &delta_angle);
        mat3_multiply(&eskf->state.G_R_I, &last_state.G_R_I, &delta_R);
    }

    // Update covariance - simplified for now
    // Full implementation would compute Fx, Fi, Qi matrices
    // For now, just increase uncertainty
    mat15_scale(&eskf->state.cov, &last_state.cov, 1.0f + dt * 0.01f);

    eskf->state.timestamp = cur_imu->timestamp;
}

// GPS update step
static void gps_update(eskf_t* eskf, const gps_data_t* gps) {
    // Convert GPS to ENU
    vec3_t G_p_Gps;
    double gps_lla[3] = {gps->lat, gps->lon, gps->alt};
    lla_to_enu(eskf->init_lla, gps_lla, &G_p_Gps);

    // Compute residual
    vec3_t predicted_gps_pos;
    mat3_multiply_vec3(&predicted_gps_pos, &eskf->state.G_R_I, &eskf->config.I_p_Gps);
    vec3_add(&predicted_gps_pos, &eskf->state.G_p_I, &predicted_gps_pos);

    vec3_t residual;
    vec3_subtract(&residual, &G_p_Gps, &predicted_gps_pos);

    // Simple Kalman update (simplified version)
    // In full implementation, compute H matrix, K gain, etc.
    float K_gain = 0.5f;  // Simplified gain

    // Update position
    vec3_t pos_correction;
    vec3_scale(&pos_correction, &residual, K_gain);
    vec3_add(&eskf->state.G_p_I, &eskf->state.G_p_I, &pos_correction);

    // Update velocity (simplified)
    vec3_t vel_correction;
    vec3_scale(&vel_correction, &residual, K_gain * 0.1f);
    vec3_add(&eskf->state.G_v_I, &eskf->state.G_v_I, &vel_correction);

    // Update covariance (simplified)
    mat15_scale(&eskf->state.cov, &eskf->state.cov, 1.0f - K_gain);
}

int eskf_process_imu(eskf_t* eskf, const imu_data_t* imu) {
    // Check tunnel status
    double current_time = imu->timestamp;
    if (eskf->last_gps_time > 0) {
        double time_since_gps = current_time - eskf->last_gps_time;
        eskf->in_tunnel = (time_since_gps > eskf->tunnel_threshold) ? 1 : 0;
    } else {
        eskf->in_tunnel = 0;
    }

    if (!eskf->initialized) {
        // Add to buffer for initialization
        if (eskf->imu_buffer_count < IMU_BUFFER_SIZE) {
            eskf->imu_buffer[eskf->imu_buffer_count++] = *imu;
        } else {
            // Circular buffer
            eskf->imu_buffer[eskf->imu_buffer_index] = *imu;
            eskf->imu_buffer_index = (eskf->imu_buffer_index + 1) % IMU_BUFFER_SIZE;
        }
        eskf->last_imu = *imu;
        return 0;
    }

    // Predict with IMU
    if (eskf->state.timestamp > 0) {
        imu_predict(eskf, imu);
    }

    // Route projection if enabled and GPS quality is low (< 8 satellites)
    if (eskf->rail_node_count > 0 && eskf->initialized && eskf->current_satellites < 8) {
        // Convert position to LLA
        double current_lla[3];
        enu_to_lla(eskf->init_lla, &eskf->state.G_p_I, current_lla);
        eskf->state.lat = current_lla[0];
        eskf->state.lon = current_lla[1];
        eskf->state.alt = current_lla[2];

        // Snap to railway
        double snapped_lat, snapped_lon;
        float dist = find_closest_rail_point(eskf, eskf->state.lat,
                                            eskf->state.lon,
                                            &snapped_lat, &snapped_lon);

        if (dist < 20.0f) {  // Within 20 meters of track
            eskf->state.lat = snapped_lat;
            eskf->state.lon = snapped_lon;

            // Update ENU position
            double snapped_lla[3] = {snapped_lat, snapped_lon, eskf->state.alt};
            lla_to_enu(eskf->init_lla, snapped_lla, &eskf->state.G_p_I);

            // Adjust heading in tunnel (simplified)
            if (eskf->in_tunnel) {
                // Would implement heading alignment here
            }
        }
    }

    eskf->last_imu = *imu;
    return 1;
}

int eskf_process_gps(eskf_t* eskf, const gps_data_t* gps) {
    eskf->last_gps_time = gps->timestamp;
    eskf->in_tunnel = 0;
    eskf->current_satellites = gps->satellites;  // Update satellite count

    if (!eskf->initialized) {
        // Initialize with first GPS
        if (eskf->imu_buffer_count < 10) {
            return 0;  // Need more IMU data
        }

        // Set initial position
        eskf->init_lla[0] = gps->lat;
        eskf->init_lla[1] = gps->lon;
        eskf->init_lla[2] = gps->alt;

        vec3_zero(&eskf->state.G_p_I);
        vec3_zero(&eskf->state.G_v_I);

        // Initialize rotation from gravity
        vec3_t gravity_direction;
        compute_gravity_from_acceleration(eskf, &gravity_direction);
        compute_initial_rotation(&gravity_direction, &eskf->state.G_R_I);

        // Initialize biases
        vec3_zero(&eskf->state.acc_bias);

        // Compute gyro bias from buffer
        vec3_zero(&eskf->state.gyro_bias);
        int count = eskf->imu_buffer_count < IMU_BUFFER_SIZE ?
                   eskf->imu_buffer_count : IMU_BUFFER_SIZE;
        for (int i = 0; i < count; i++) {
            vec3_add(&eskf->state.gyro_bias, &eskf->state.gyro_bias,
                    &eskf->imu_buffer[i].gyro);
        }
        vec3_scale(&eskf->state.gyro_bias, &eskf->state.gyro_bias, 1.0f / (float)count);

        // Initialize covariance
        mat15_identity(&eskf->state.cov);
        for (int i = 0; i < 3; i++) eskf->state.cov.data[i][i] = 1.0f;
        for (int i = 3; i < 6; i++) eskf->state.cov.data[i][i] = 0.1f;
        for (int i = 6; i < 9; i++) eskf->state.cov.data[i][i] = 0.1f;
        for (int i = 9; i < 12; i++) eskf->state.cov.data[i][i] = 0.01f;
        for (int i = 12; i < 15; i++) eskf->state.cov.data[i][i] = 0.01f;

        eskf->state.timestamp = gps->timestamp;
        eskf->state.lat = gps->lat;
        eskf->state.lon = gps->lon;
        eskf->state.alt = gps->alt;

        eskf->initialized = 1;
        return 1;
    }

    // Update with GPS
    gps_update(eskf, gps);
    return 1;
}

void eskf_get_state(const eskf_t* eskf, eskf_state_t* state) {
    *state = eskf->state;
}