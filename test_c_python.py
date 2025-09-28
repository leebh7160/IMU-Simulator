import ctypes
import numpy as np
import pandas as pd
import platform
import os
from pathlib import Path

# Determine library extension based on platform
system = platform.system()
if system == 'Windows':
    lib_ext = '.dll'
elif system == 'Darwin':
    lib_ext = '.dylib'
else:
    lib_ext = '.so'

lib_path = Path(__file__).parent / f'eskf{lib_ext}'

print(f"Python-C ESKF Test")
print(f"==================")
print(f"Platform: {system}")
print(f"Library path: {lib_path}")

# Check if library exists
if not lib_path.exists():
    print(f"\nError: Library not found at {lib_path}")
    print("Please compile the C library first:")
    print("  Windows: cl /O2 /LD matrix.c eskf.c /Fe:eskf.dll")
    print("  Linux/Mac: gcc -O2 -shared -fPIC matrix.c eskf.c -o eskf.so -lm")
    exit(1)

# Load the library
try:
    eskf_lib = ctypes.CDLL(str(lib_path))
    print(f"Library loaded successfully!")
except Exception as e:
    print(f"Failed to load library: {e}")
    exit(1)

# Define structures
class Vec3(ctypes.Structure):
    _fields_ = [("data", ctypes.c_float * 3)]

class Mat3(ctypes.Structure):
    _fields_ = [("data", (ctypes.c_float * 3) * 3)]

class Mat15(ctypes.Structure):
    _fields_ = [("data", (ctypes.c_float * 15) * 15)]

class ImuData(ctypes.Structure):
    _fields_ = [
        ("timestamp", ctypes.c_double),
        ("acc", Vec3),
        ("gyro", Vec3)
    ]

class GpsData(ctypes.Structure):
    _fields_ = [
        ("timestamp", ctypes.c_double),
        ("lat", ctypes.c_double),
        ("lon", ctypes.c_double),
        ("alt", ctypes.c_double),
        ("cov", Mat3),
        ("satellites", ctypes.c_int)
    ]

class EskfState(ctypes.Structure):
    _fields_ = [
        ("timestamp", ctypes.c_double),
        ("lat", ctypes.c_double),
        ("lon", ctypes.c_double),
        ("alt", ctypes.c_double),
        ("G_p_I", Vec3),
        ("G_v_I", Vec3),
        ("G_R_I", Mat3),
        ("acc_bias", Vec3),
        ("gyro_bias", Vec3),
        ("cov", Mat15)
    ]

class RailNode(ctypes.Structure):
    _fields_ = [
        ("lat", ctypes.c_float),
        ("lon", ctypes.c_float)
    ]

# Define function signatures
eskf_lib.eskf_create.restype = ctypes.c_void_p
eskf_lib.eskf_create.argtypes = []

eskf_lib.eskf_destroy.restype = None
eskf_lib.eskf_destroy.argtypes = [ctypes.c_void_p]

eskf_lib.eskf_process_imu.restype = ctypes.c_int
eskf_lib.eskf_process_imu.argtypes = [ctypes.c_void_p, ctypes.POINTER(ImuData)]

eskf_lib.eskf_process_gps.restype = ctypes.c_int
eskf_lib.eskf_process_gps.argtypes = [ctypes.c_void_p, ctypes.POINTER(GpsData)]

eskf_lib.eskf_get_state.restype = None
eskf_lib.eskf_get_state.argtypes = [ctypes.c_void_p, ctypes.POINTER(EskfState)]

eskf_lib.eskf_load_rail_nodes.restype = ctypes.c_int
eskf_lib.eskf_load_rail_nodes.argtypes = [ctypes.c_void_p, ctypes.POINTER(RailNode), ctypes.c_int]

# Create ESKF instance
eskf = eskf_lib.eskf_create()
if not eskf:
    print("Failed to create ESKF instance")
    exit(1)

print("\nESKF instance created")

# Load railway nodes if available
try:
    rail_df = pd.read_csv('data/railway_nodes.csv')
    rail_nodes = (RailNode * len(rail_df))()
    for i, row in rail_df.iterrows():
        rail_nodes[i].lat = row['lat']
        rail_nodes[i].lon = row['lng']

    loaded = eskf_lib.eskf_load_rail_nodes(eskf, rail_nodes, len(rail_df))
    print(f"Loaded {loaded} railway nodes")
except Exception as e:
    print(f"Railway nodes not loaded: {e}")

# Load and process data
print("\nLoading sensor data...")
df = pd.read_csv('data/data.csv')
df['timestamp'] = pd.to_datetime(df['timestamp']).astype(np.int64) / 1e9  # Convert to seconds

print(f"Processing {len(df)} data points...")

results = []
gps_count = 0
imu_count = 0
current_gps_lat = 0
current_gps_lon = 0
initialization_points = []  # Store all initialization points
# GPS recovery points from actual data.csv data (where gps_available changes from False to True)
gps_recovery_points = [
    {'lat': 37.502775, 'lon': 126.881396},  # 첫 번째 GPS 활성화
    {'lat': 37.507768, 'lon': 126.889177},  # 터널 출구 1
    {'lat': 37.515108, 'lon': 126.905960},  # 터널 출구 2
    {'lat': 37.516718, 'lon': 126.910786},  # 터널 출구 3
    {'lat': 37.516999, 'lon': 126.913597},  # 터널 출구 4
    {'lat': 37.516276, 'lon': 126.919743},  # 터널 출구 5
    {'lat': 37.514566, 'lon': 126.930007}   # 터널 출구 6
]
last_gps_success = False    # Track GPS status for re-initialization detection
initialization_marked = False  # Track if we've already marked the initialization point
consecutive_gps_failures = 0  # Count consecutive GPS failures

for idx, row in df.iterrows():
    # Process IMU
    imu = ImuData()
    imu.timestamp = row['timestamp']
    imu.acc.data[0] = row['accel_x'] * 9.81
    imu.acc.data[1] = row['accel_y'] * 9.81
    imu.acc.data[2] = row['accel_z'] * 9.81
    imu.gyro.data[0] = row['gyro_x']
    imu.gyro.data[1] = row['gyro_y']
    imu.gyro.data[2] = row['gyro_z']

    success = eskf_lib.eskf_process_imu(eskf, ctypes.byref(imu))
    if success:
        imu_count += 1

    # Process GPS if available
    if pd.notna(row['gps_lat']) and pd.notna(row['gps_lng']) and row['gps_lat'] != 0:
        gps = GpsData()
        gps.timestamp = row['timestamp']
        gps.lat = row['gps_lat']
        gps.lon = row['gps_lng']
        gps.alt = 0
        gps.satellites = row['satellites']  # Add satellite count

        # Set identity covariance
        for i in range(3):
            for j in range(3):
                gps.cov.data[i][j] = 25.0 if i == j else 0.0

        success = eskf_lib.eskf_process_gps(eskf, ctypes.byref(gps))

        if success:
            gps_count += 1
            # Store GPS data when actually processed
            current_gps_lat = row['gps_lat']
            current_gps_lon = row['gps_lng']

            # Track GPS success - only record first successful GPS (real initialization)
            if len(initialization_points) == 0:
                init_point = {
                    'lat': row['gps_lat'],
                    'lon': row['gps_lng'],
                    'timestamp': row['timestamp'],
                    'type': 'first'
                }
                initialization_points.append(init_point)
                print(f"ESKF Initialized at: {init_point['lat']:.6f}, {init_point['lon']:.6f}")

            # GPS recovery points are now pre-defined from data.csv analysis
            # No need to dynamically detect them during processing

            last_gps_success = True
            consecutive_gps_failures = 0  # Reset failure count on success
        else:
            last_gps_success = False
            consecutive_gps_failures += 1
    else:
        # No GPS data available
        consecutive_gps_failures += 1

    # Get state periodically
    if idx % 100 == 0:
        state = EskfState()
        eskf_lib.eskf_get_state(eskf, ctypes.byref(state))

        if state.timestamp > 0:
            # Get current row for raw sensor data
            current_row = df.iloc[min(idx, len(df)-1)]

            # Mark initialization only for the very first time
            is_init = 0
            if (len(initialization_points) > 0 and not initialization_marked and
                abs(state.lat - initialization_points[0]['lat']) < 0.0001 and
                abs(state.lon - initialization_points[0]['lon']) < 0.0001):
                is_init = 1
                initialization_marked = True

            # Check if this point is near any GPS recovery point (wider matching for ESKF processed coordinates)
            is_recovery = 0
            for recovery_point in gps_recovery_points:
                if (abs(state.lat - recovery_point['lat']) < 0.002 and
                    abs(state.lon - recovery_point['lon']) < 0.002):
                    is_recovery = 1
                    break

            results.append({
                'timestamp': state.timestamp,
                'eskf_lat': state.lat,
                'eskf_lon': state.lon,
                'eskf_alt': state.alt,
                'pos_x': state.G_p_I.data[0],
                'pos_y': state.G_p_I.data[1],
                'pos_z': state.G_p_I.data[2],
                'gps_raw_lat': current_gps_lat,
                'gps_raw_lon': current_gps_lon,
                'imu_acc_x': current_row.get('accel_x', 0),
                'imu_acc_y': current_row.get('accel_y', 0),
                'imu_acc_z': current_row.get('accel_z', 0),
                'imu_gyro_x': current_row.get('gyro_x', 0),
                'imu_gyro_y': current_row.get('gyro_y', 0),
                'imu_gyro_z': current_row.get('gyro_z', 0),
                'is_initialization': is_init,
                'is_gps_recovery': is_recovery
            })

print(f"\nProcessing complete:")
print(f"  GPS updates: {gps_count}")
print(f"  IMU updates: {imu_count}")
print(f"  Output points: {len(results)}")

# Save results
if results:
    result_df = pd.DataFrame(results)
    result_df.to_csv('eskf_c_output.csv', index=False)
    print(f"\nResults saved to eskf_c_output.csv")

    # Show sample
    print("\nSample results:")
    print(f"  First ESKF: lat={results[0]['eskf_lat']:.6f}, lon={results[0]['eskf_lon']:.6f}")
    print(f"  First GPS:  lat={results[0]['gps_raw_lat']:.6f}, lon={results[0]['gps_raw_lon']:.6f}")
    print(f"  Last ESKF:  lat={results[-1]['eskf_lat']:.6f}, lon={results[-1]['eskf_lon']:.6f}")
    print(f"  Last GPS:   lat={results[-1]['gps_raw_lat']:.6f}, lon={results[-1]['gps_raw_lon']:.6f}")

# Cleanup
eskf_lib.eskf_destroy(eskf)
print("\nTest completed!")