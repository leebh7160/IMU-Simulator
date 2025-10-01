#ifndef ESKF_H
#define ESKF_H

#include "matrix.h"

#ifdef __cplusplus
extern "C" {
#endif

// Constants
#define MAX_RAIL_NODES 5000
#define IMU_BUFFER_SIZE 500

// Data structures
typedef struct {
    double timestamp;
    vec3_t acc;   // m/s^2
    vec3_t gyro;  // rad/s
} imu_data_t;

typedef struct {
    double timestamp;
    double lat;   // degrees
    double lon;   // degrees
    double alt;   // meters
    mat3_t cov;   // 3x3 covariance matrix in m^2
    int satellites; // Number of satellites
} gps_data_t;

typedef struct {
    double timestamp;
    double lat, lon, alt;  // WGS84 position
    vec3_t G_p_I;         // IMU position in global frame (ENU)
    vec3_t G_v_I;         // IMU velocity in global frame
    mat3_t G_R_I;         // Rotation from IMU to global frame
    vec3_t acc_bias;      // Accelerometer bias
    vec3_t gyro_bias;     // Gyroscope bias
    mat15_t cov;          // 15x15 covariance matrix
    // Euler angles for debugging (extracted from G_R_I)
    float roll;           // Roll angle in radians
    float pitch;          // Pitch angle in radians
    float yaw;            // Yaw angle in radians
} eskf_state_t;

typedef struct {
    float lat;
    float lon;
} rail_node_t;

// ESKF Configuration
typedef struct {
    float acc_noise;       // Accelerometer noise (m/s^2)
    float gyro_noise;      // Gyroscope noise (rad/s)
    float acc_bias_noise;  // Accelerometer bias noise
    float gyro_bias_noise; // Gyroscope bias noise
    vec3_t gravity;        // Gravity vector
    vec3_t I_p_Gps;       // GPS antenna offset in IMU frame
} eskf_config_t;

// Main ESKF structure
typedef struct {
    // Configuration
    eskf_config_t config;

    // State
    eskf_state_t state;
    int initialized;

    // Reference position
    double init_lla[3];

    // IMU buffer for initialization
    imu_data_t imu_buffer[IMU_BUFFER_SIZE];
    int imu_buffer_count;
    int imu_buffer_index;

    // Railway map
    rail_node_t rail_nodes[MAX_RAIL_NODES];
    int rail_node_count;

    // Tunnel detection
    double last_gps_time;
    int in_tunnel;
    float tunnel_threshold;
    float heading_smoothing_factor;

    // GPS quality tracking
    int current_satellites;

    // Last IMU data for prediction
    imu_data_t last_imu;
} eskf_t;

// API Functions
eskf_t* eskf_create(void);
void eskf_destroy(eskf_t* eskf);
void eskf_reset(eskf_t* eskf);

// Configure ESKF
void eskf_set_config(eskf_t* eskf, const eskf_config_t* config);

// Process sensor data
int eskf_process_imu(eskf_t* eskf, const imu_data_t* imu);
int eskf_process_gps(eskf_t* eskf, const gps_data_t* gps);

// Get current state
void eskf_get_state(const eskf_t* eskf, eskf_state_t* state);

// Load railway nodes for route projection
int eskf_load_rail_nodes(eskf_t* eskf, const rail_node_t* nodes, int count);

// Coordinate transformations
void lla_to_enu(const double* init_lla, const double* target_lla, vec3_t* enu);
void enu_to_lla(const double* init_lla, const vec3_t* enu, double* lla);

#ifdef __cplusplus
}
#endif

#endif // ESKF_H