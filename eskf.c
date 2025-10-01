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

// Update euler angles from rotation matrix for debugging
static void update_euler_angles(eskf_state_t* state) {
    mat3_to_euler(&state->G_R_I, &state->roll, &state->pitch, &state->yaw);
}

// Verify gravity vector consistency (for debugging/validation)
// Returns the error magnitude between expected and transformed gravity
static float verify_gravity_alignment(const eskf_t* eskf, const vec3_t* acc_unbias) {
    // Transform measured acceleration to global frame
    vec3_t global_acc;
    mat3_multiply_vec3(&global_acc, &eskf->state.G_R_I, acc_unbias);

    // Expected: global_acc + gravity ≈ 0 (in static condition)
    vec3_t expected_zero;
    vec3_add(&expected_zero, &global_acc, &eskf->config.gravity);

    // Compute error magnitude
    float error = vec3_norm(&expected_zero);
    return error;
}

// Orthonormalize rotation matrix using Gram-Schmidt process
// This ensures the rotation matrix remains valid (orthogonal with unit columns)
// Prevents numerical drift from accumulating during repeated matrix operations
static void orthonormalize_rotation(mat3_t* R) {
    vec3_t x, y, z;

    // Extract columns
    x.data[0] = R->data[0][0];
    x.data[1] = R->data[1][0];
    x.data[2] = R->data[2][0];

    y.data[0] = R->data[0][1];
    y.data[1] = R->data[1][1];
    y.data[2] = R->data[2][1];

    z.data[0] = R->data[0][2];
    z.data[1] = R->data[1][2];
    z.data[2] = R->data[2][2];

    // Gram-Schmidt orthonormalization
    // Step 1: Normalize x
    vec3_normalize(&x, &x);

    // Step 2: Make y orthogonal to x, then normalize
    float dot_xy = vec3_dot(&x, &y);
    vec3_t x_proj;
    vec3_scale(&x_proj, &x, dot_xy);
    vec3_subtract(&y, &y, &x_proj);
    vec3_normalize(&y, &y);

    // Step 3: z = x × y (ensures right-handed coordinate system)
    vec3_cross(&z, &x, &y);

    // Write back orthonormalized columns
    R->data[0][0] = x.data[0];
    R->data[1][0] = x.data[1];
    R->data[2][0] = x.data[2];

    R->data[0][1] = y.data[0];
    R->data[1][1] = y.data[1];
    R->data[2][1] = y.data[2];

    R->data[0][2] = z.data[0];
    R->data[1][2] = z.data[1];
    R->data[2][2] = z.data[2];
}

// Correct rotation using gravity vector alignment
// This prevents gyroscope drift accumulation over time
static void correct_rotation_with_gravity(eskf_t* eskf, const vec3_t* acc_unbias, float gain) {
    // Compute normalized acceleration magnitude
    float acc_norm = vec3_norm(acc_unbias);

    // Only correct when acceleration is close to gravity (low dynamic motion)
    // This ensures we're measuring gravity, not dynamic acceleration
    float gravity_norm = vec3_norm(&eskf->config.gravity);
    float acc_diff = fabs(acc_norm - gravity_norm);

    // ===== NEW: Compute acceleration variance for motion detection =====
    // Use recent IMU buffer to detect dynamic motion
    float acc_variance = 0.0f;
    if (eskf->imu_buffer_count >= 10) {
        vec3_t acc_mean;
        vec3_zero(&acc_mean);

        // Compute mean
        int count = eskf->imu_buffer_count < 20 ? eskf->imu_buffer_count : 20;
        for (int i = 0; i < count; i++) {
            int idx = (eskf->imu_buffer_index - count + i + IMU_BUFFER_SIZE) % IMU_BUFFER_SIZE;
            vec3_add(&acc_mean, &acc_mean, &eskf->imu_buffer[idx].acc);
        }
        vec3_scale(&acc_mean, &acc_mean, 1.0f / (float)count);

        // Compute variance
        for (int i = 0; i < count; i++) {
            int idx = (eskf->imu_buffer_index - count + i + IMU_BUFFER_SIZE) % IMU_BUFFER_SIZE;
            vec3_t diff;
            vec3_subtract(&diff, &eskf->imu_buffer[idx].acc, &acc_mean);
            acc_variance += vec3_norm(&diff);
        }
        acc_variance /= (float)count;
    }

    // If acceleration differs too much from gravity, skip correction
    // (vehicle is accelerating/decelerating)
    // Also skip if high acceleration variance (dynamic motion)
    if (acc_diff > 2.0f || acc_variance > 0.5f) {
        return;
    }

    // ===== NEW: Dynamic gain adjustment based on velocity =====
    // Lower velocity = higher confidence in gravity measurement
    // Higher velocity = more dynamic motion, reduce correction
    float velocity = vec3_norm(&eskf->state.G_v_I);
    float velocity_factor = 1.0f;

    if (velocity < 1.0f) {
        // Nearly stationary: strong correction
        velocity_factor = 2.0f;
    } else if (velocity < 5.0f) {
        // Slow movement: moderate correction
        velocity_factor = 1.0f;
    } else if (velocity < 15.0f) {
        // Medium speed: reduced correction
        velocity_factor = 0.5f;
    } else {
        // High speed: minimal correction
        velocity_factor = 0.2f;
    }

    gain *= velocity_factor;

    // Measured gravity direction in IMU frame
    vec3_t measured_gravity;
    vec3_normalize(&measured_gravity, acc_unbias);

    // Expected gravity direction in IMU frame
    // Transform global gravity to IMU frame: I_gravity = G_R_I^T * G_gravity
    vec3_t expected_gravity;
    mat3_t G_R_I_T;
    mat3_transpose(&G_R_I_T, &eskf->state.G_R_I);
    mat3_multiply_vec3(&expected_gravity, &G_R_I_T, &eskf->config.gravity);
    vec3_normalize(&expected_gravity, &expected_gravity);

    // Compute rotation error (small angle approximation)
    // error = measured x expected
    vec3_t rotation_error;
    vec3_cross(&rotation_error, &measured_gravity, &expected_gravity);

    // Apply gain to control correction strength
    vec3_scale(&rotation_error, &rotation_error, gain);

    // Convert error to rotation matrix (small angle: R ≈ I + [error]×)
    mat3_t error_rotation;
    mat3_t error_skew;
    mat3_skew(&error_skew, &rotation_error);
    mat3_identity(&error_rotation);
    mat3_add(&error_rotation, &error_rotation, &error_skew);

    // Apply correction: G_R_I = G_R_I * error_rotation
    mat3_t corrected_rotation;
    mat3_multiply(&corrected_rotation, &eskf->state.G_R_I, &error_rotation);
    eskf->state.G_R_I = corrected_rotation;

    // ===== NEW: Orthonormalize to maintain rotation matrix validity =====
    orthonormalize_rotation(&eskf->state.G_R_I);
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

        // ===== NEW: Orthonormalize after rotation update =====
        // Prevents numerical drift from repeated matrix multiplications
        orthonormalize_rotation(&eskf->state.G_R_I);
    }

    // ===== NEW: Apply gravity-based rotation correction during IMU prediction =====
    // This provides continuous attitude correction even without GPS
    // Very low gain (0.001) to avoid interfering with dynamic motion
    // Only corrects slow gyro drift, not actual vehicle rotation
    correct_rotation_with_gravity(eskf, &acc_unbias, 0.001f);

    // Update Euler angles for debugging
    update_euler_angles(&eskf->state);

    // ===== IMPROVED: Proper covariance propagation =====
    // Update covariance based on process noise
    // State order: [δp(0-2), δv(3-5), δθ(6-8), δba(9-11), δbg(12-14)]

    // Add process noise to covariance diagonal
    // Position uncertainty increases with velocity and time
    float vel_norm = vec3_norm(&eskf->state.G_v_I);
    float pos_noise = eskf->config.acc_noise * dt * dt * 0.5f + vel_norm * dt * 0.01f;
    for (int i = 0; i < 3; i++) {
        eskf->state.cov.data[i][i] += pos_noise * pos_noise;
    }

    // Velocity uncertainty increases with acceleration noise
    float vel_noise = eskf->config.acc_noise * dt;
    for (int i = 3; i < 6; i++) {
        eskf->state.cov.data[i][i] += vel_noise * vel_noise;
    }

    // Rotation uncertainty increases with gyro noise
    float rot_noise = eskf->config.gyro_noise * dt;
    for (int i = 6; i < 9; i++) {
        eskf->state.cov.data[i][i] += rot_noise * rot_noise;
    }

    // Accelerometer bias random walk
    for (int i = 9; i < 12; i++) {
        eskf->state.cov.data[i][i] += eskf->config.acc_bias_noise * eskf->config.acc_bias_noise * dt;
    }

    // Gyroscope bias random walk
    for (int i = 12; i < 15; i++) {
        eskf->state.cov.data[i][i] += eskf->config.gyro_bias_noise * eskf->config.gyro_bias_noise * dt;
    }

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

    // ===== IMPROVED: Kalman update with measurement noise consideration =====
    // Measurement noise from GPS (position measurement)
    // Typical GPS accuracy: 2-5m (consumer), better with more satellites
    float gps_noise_base = 5.0f;  // Base GPS noise in meters
    float gps_noise = gps_noise_base / sqrtf((float)gps->satellites);  // Better accuracy with more satellites
    float R = gps_noise * gps_noise;  // Measurement noise variance

    // Compute Kalman gain for position
    // K = P * H^T / (H * P * H^T + R)
    // For position measurement, H selects position states (first 3 elements)
    float K_pos = 0.0f;
    for (int i = 0; i < 3; i++) {
        float S = eskf->state.cov.data[i][i] + R;  // Innovation covariance
        K_pos += eskf->state.cov.data[i][i] / S;
    }
    K_pos /= 3.0f;  // Average gain for 3 position dimensions

    // Compute Kalman gain for velocity (coupled with position)
    float K_vel = K_pos * 0.1f;  // Velocity correction is weaker

    // Update position
    vec3_t pos_correction;
    vec3_scale(&pos_correction, &residual, K_pos);
    vec3_add(&eskf->state.G_p_I, &eskf->state.G_p_I, &pos_correction);

    // Update velocity
    vec3_t vel_correction;
    vec3_scale(&vel_correction, &residual, K_vel);
    vec3_add(&eskf->state.G_v_I, &eskf->state.G_v_I, &vel_correction);

    // Update covariance: P = (I - K*H) * P
    // Reduce uncertainty in position states
    for (int i = 0; i < 3; i++) {
        eskf->state.cov.data[i][i] *= (1.0f - K_pos);
    }
    // Reduce uncertainty in velocity states (less reduction)
    for (int i = 3; i < 6; i++) {
        eskf->state.cov.data[i][i] *= (1.0f - K_vel);
    }
    // Rotation uncertainty slightly reduced due to improved position estimate
    for (int i = 6; i < 9; i++) {
        eskf->state.cov.data[i][i] *= 0.98f;
    }

    // ===== NEW: Rotation correction using gravity alignment =====
    // Apply gravity-based rotation correction when GPS is available
    // This prevents long-term gyroscope drift accumulation
    if (eskf->imu_buffer_count > 0) {
        // Get latest IMU measurement from buffer
        int latest_idx = (eskf->imu_buffer_index > 0) ?
                         eskf->imu_buffer_index - 1 : eskf->imu_buffer_count - 1;
        const imu_data_t* latest_imu = &eskf->imu_buffer[latest_idx];

        // Remove accelerometer bias
        vec3_t acc_unbias;
        vec3_subtract(&acc_unbias, &latest_imu->acc, &eskf->state.acc_bias);

        // Apply rotation correction with conservative gain
        // Lower gain (0.02) for GPS updates to avoid overcorrection
        // This gradually aligns the rotation with gravity over multiple GPS measurements
        correct_rotation_with_gravity(eskf, &acc_unbias, 0.02f);

        // Update Euler angles for debugging
        update_euler_angles(&eskf->state);
    }
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

            // ===== NEW: Adjust heading in tunnel using rail direction =====
            if (eskf->in_tunnel && eskf->rail_node_count > 1) {
                // Find the rail segment we're on
                int closest_segment = -1;
                float min_segment_dist = 1e6f;

                for (int i = 0; i < eskf->rail_node_count - 1; i++) {
                    float lat1 = eskf->rail_nodes[i].lat;
                    float lon1 = eskf->rail_nodes[i].lon;
                    float lat2 = eskf->rail_nodes[i + 1].lat;
                    float lon2 = eskf->rail_nodes[i + 1].lon;

                    // Check if we're near this segment
                    float dx = lon2 - lon1;
                    float dy = lat2 - lat1;
                    float t = ((snapped_lon - lon1) * dx + (snapped_lat - lat1) * dy) / (dx * dx + dy * dy);

                    if (t >= 0.0f && t <= 1.0f) {
                        float seg_dist = fabsf(t * sqrtf(dx * dx + dy * dy));
                        if (seg_dist < min_segment_dist) {
                            min_segment_dist = seg_dist;
                            closest_segment = i;
                        }
                    }
                }

                // Apply heading correction if we found a valid segment
                if (closest_segment >= 0) {
                    float lat1 = eskf->rail_nodes[closest_segment].lat;
                    float lon1 = eskf->rail_nodes[closest_segment].lon;
                    float lat2 = eskf->rail_nodes[closest_segment + 1].lat;
                    float lon2 = eskf->rail_nodes[closest_segment + 1].lon;

                    // Compute rail direction (yaw angle)
                    float dx = (lon2 - lon1) * cosf(lat1 * DEG_TO_RAD) * 111000.0f;
                    float dy = (lat2 - lat1) * 111000.0f;
                    float rail_yaw = atan2f(dx, dy);  // North = 0, East = π/2

                    // Gradually align IMU yaw with rail yaw
                    float current_yaw = eskf->state.yaw;
                    float yaw_error = rail_yaw - current_yaw;

                    // Normalize angle difference to [-π, π]
                    while (yaw_error > M_PI) yaw_error -= 2.0f * M_PI;
                    while (yaw_error < -M_PI) yaw_error += 2.0f * M_PI;

                    // Apply correction with smoothing
                    float yaw_correction = yaw_error * eskf->heading_smoothing_factor;
                    float corrected_yaw = current_yaw + yaw_correction;

                    // Update rotation matrix from corrected Euler angles
                    mat3_from_euler(&eskf->state.G_R_I, eskf->state.roll, eskf->state.pitch, corrected_yaw);
                    orthonormalize_rotation(&eskf->state.G_R_I);
                    update_euler_angles(&eskf->state);
                }
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

        // Initialize Euler angles
        update_euler_angles(&eskf->state);

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