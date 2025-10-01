import ctypes
import numpy as np
import pandas as pd
import platform
import os
import argparse
from pathlib import Path

# Determine library extension based on platform
system = platform.system()
if system == 'Windows':
    lib_ext = '.dll'
elif system == 'Darwin':
    lib_ext = '.dylib'
else:
    lib_ext = '.so'

# Parse command line arguments
parser = argparse.ArgumentParser(description='ESKF C Test with Railway Direction')
parser.add_argument('--direction', choices=['up', 'down'], default='up',
                   help='Railway direction: up (상행) or down (하행)')
args = parser.parse_args()

lib_path = Path(__file__).parent / f'eskf{lib_ext}'

print(f"Python-C ESKF Test")
print(f"==================")
print(f"Platform: {system}")
print(f"Library path: {lib_path}")
print(f"Railway Direction: {args.direction} ({'상행' if args.direction == 'up' else '하행'})")

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

# Load railway nodes based on direction
try:
    railway_file = f'data/railway_nodes_{args.direction}.csv'
    if not os.path.exists(railway_file):
        # Fallback to default railway_nodes.csv
        railway_file = 'data/railway_nodes.csv'
        print(f"Warning: {railway_file} not found, using default railway_nodes.csv")

    rail_df = pd.read_csv(railway_file)
    rail_nodes = (RailNode * len(rail_df))()
    for i, row in rail_df.iterrows():
        rail_nodes[i].lat = row['lat']
        # Handle both 'lng' and 'lon' column names
        if 'lng' in row:
            rail_nodes[i].lon = row['lng']
        elif 'lon' in row:
            rail_nodes[i].lon = row['lon']
        else:
            raise ValueError("No longitude column found (expected 'lng' or 'lon')")

    loaded = eskf_lib.eskf_load_rail_nodes(eskf, rail_nodes, len(rail_df))
    print(f"Loaded {loaded} railway nodes from {railway_file}")
except Exception as e:
    print(f"Railway nodes not loaded: {e}")

# Load and process data
print("\nLoading sensor data...")
# Use corrected data if available, otherwise use original
try:
    df = pd.read_csv('data/data_corrected.csv')
    print("Using corrected IMU data (data_corrected.csv)")
except FileNotFoundError:
    df = pd.read_csv('data/data.csv')
    print("Using original IMU data (data.csv)")

df['timestamp'] = pd.to_datetime(df['timestamp']).astype(np.int64) / 1e9  # Convert to seconds

print(f"Processing {len(df)} data points...")

results = []
gps_count = 0
imu_count = 0
current_gps_lat = 0
current_gps_lon = 0
initialization_points = []  # Store all initialization points
# Find gps_available True -> False transitions
print("Finding gps_available True->False transitions...")
temp_df = pd.read_csv('data/data.csv')
temp_df['prev_gps_available'] = temp_df['gps_available'].shift(1)
temp_df['gps_available_loss'] = (temp_df['prev_gps_available'] == True) & (temp_df['gps_available'] == False)
gps_loss_indices = set(temp_df[temp_df['gps_available_loss'] == True].index.tolist())
print(f"Found {len(gps_loss_indices)} gps_available True->False transitions at indices: {list(gps_loss_indices)}")
initialization_marked = False

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
        gps.satellites = int(row['satellites']) if not pd.isna(row['satellites']) else 0  # Add satellite count

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

            # GPS data processed successfully
            pass
        else:
            # GPS processing failed but data was available
            pass
    else:
        # No GPS data available
        pass

    # Get state periodically or at GPS loss points
    if idx % 100 == 0 or idx in gps_loss_indices:
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

            # Check if this data point corresponds to a gps_available True->False transition
            is_loss = 1 if idx in gps_loss_indices else 0

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
                'is_gps_loss': is_loss
            })

print(f"\nProcessing complete:")
print(f"  GPS updates: {gps_count}")
print(f"  IMU updates: {imu_count}")
print(f"  GPS available transitions (True->False): {len(gps_loss_indices)}")
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