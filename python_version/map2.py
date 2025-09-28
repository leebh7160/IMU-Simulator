import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.spatial.transform import Rotation as R
from scipy.linalg import block_diag
import pyproj
import time  # For timestamp comparisons

print("ROS-Style ESKF Implementation with Railway Map Matching")
print("=" * 60)

class ImuData:
    def __init__(self, timestamp, acc, gyro):
        self.timestamp = timestamp
        self.acc = np.array(acc)  # m/s^2
        self.gyro = np.array(gyro)  # rad/s

class GpsPositionData:
    def __init__(self, timestamp, lla, cov):
        self.timestamp = timestamp
        self.lla = np.array(lla)  # [lat(deg), lon(deg), alt(m)]
        self.cov = cov  # 3x3 covariance matrix in m^2

class State:
    def __init__(self):
        self.timestamp = 0.0
        self.lla = np.zeros(3)  # WGS84 position
        self.G_p_I = np.zeros(3)  # IMU origin in Global frame
        self.G_v_I = np.zeros(3)  # IMU velocity in Global frame
        self.G_R_I = np.eye(3)  # Rotation from IMU to Global frame
        self.acc_bias = np.zeros(3)  # Accelerometer bias
        self.gyro_bias = np.zeros(3)  # Gyroscope bias
        self.cov = np.eye(15) * 0.01  # 15x15 covariance matrix
        self.imu_data_ptr = None  # Last IMU data

def get_skew_matrix(v):
    """Create skew-symmetric matrix from vector"""
    return np.array([
        [0, -v[2], v[1]],
        [v[2], 0, -v[0]],
        [-v[1], v[0], 0]
    ])

def convert_lla_to_enu(init_lla, target_lla):
    """Convert WGS84 coordinates to ENU using pyproj"""
    proj_wgs84 = pyproj.Proj(proj='latlong', datum='WGS84')
    proj_enu = pyproj.Proj(proj='aeqd', lat_0=init_lla[0], lon_0=init_lla[1], datum='WGS84')
    transformer = pyproj.Transformer.from_proj(proj_wgs84, proj_enu)
    e, n = transformer.transform(target_lla[1], target_lla[0])
    u = target_lla[2] - init_lla[2] if len(target_lla) > 2 and len(init_lla) > 2 else 0
    return np.array([e, n, u])

def convert_enu_to_lla(init_lla, enu_pos):
    """Convert ENU coordinates to WGS84"""
    proj_wgs84 = pyproj.Proj(proj='latlong', datum='WGS84')
    proj_enu = pyproj.Proj(proj='aeqd', lat_0=init_lla[0], lon_0=init_lla[1], datum='WGS84')
    transformer = pyproj.Transformer.from_proj(proj_enu, proj_wgs84)
    lon, lat = transformer.transform(enu_pos[0], enu_pos[1])
    alt = init_lla[2] + enu_pos[2] if len(init_lla) > 2 else enu_pos[2]
    return np.array([lat, lon, alt])

class ImuProcessor:
    def __init__(self, acc_noise=0.5, gyro_noise=0.01,
                 acc_bias_noise=0.01, gyro_bias_noise=0.001,
                 gravity=np.array([0., 0., -9.81007])):
        self.acc_noise = acc_noise
        self.gyro_noise = gyro_noise
        self.acc_bias_noise = acc_bias_noise
        self.gyro_bias_noise = gyro_bias_noise
        self.gravity = gravity

    def predict(self, last_imu, cur_imu, state):
        delta_t = cur_imu.timestamp - last_imu.timestamp
        delta_t2 = delta_t * delta_t
        last_state = State()
        last_state.G_p_I = state.G_p_I.copy()
        last_state.G_v_I = state.G_v_I.copy()
        last_state.G_R_I = state.G_R_I.copy()
        last_state.acc_bias = state.acc_bias.copy()
        last_state.gyro_bias = state.gyro_bias.copy()
        last_state.cov = state.cov.copy()
        acc_unbias = 0.5 * (last_imu.acc + cur_imu.acc) - last_state.acc_bias
        gyro_unbias = 0.5 * (last_imu.gyro + cur_imu.gyro) - last_state.gyro_bias
        state.G_p_I = last_state.G_p_I + last_state.G_v_I * delta_t + \
                      0.5 * (last_state.G_R_I @ acc_unbias + self.gravity) * delta_t2
        state.G_v_I = last_state.G_v_I + (last_state.G_R_I @ acc_unbias + self.gravity) * delta_t
        delta_angle_axis = gyro_unbias * delta_t
        if np.linalg.norm(delta_angle_axis) > 1e-12:
            delta_R = R.from_rotvec(gyro_unbias * delta_t).as_matrix()
            state.G_R_I = last_state.G_R_I @ delta_R
        Fx = np.eye(15)
        Fx[0:3, 3:6] = np.eye(3) * delta_t
        Fx[3:6, 6:9] = -state.G_R_I @ get_skew_matrix(acc_unbias) * delta_t
        Fx[3:6, 9:12] = -state.G_R_I * delta_t
        if np.linalg.norm(delta_angle_axis) > 1e-12:
            Fx[6:9, 6:9] = R.from_rotvec(delta_angle_axis).as_matrix().T
        else:
            Fx[6:9, 6:9] = np.eye(3)
        Fx[6:9, 12:15] = -np.eye(3) * delta_t
        Fi = np.zeros((15, 12))
        Fi[3:15, 0:12] = np.eye(12)
        Qi = np.zeros((12, 12))
        Qi[0:3, 0:3] = delta_t2 * self.acc_noise * np.eye(3)
        Qi[3:6, 3:6] = delta_t2 * self.gyro_noise * np.eye(3)
        Qi[6:9, 6:9] = delta_t * self.acc_bias_noise * np.eye(3)
        gyro_norm = np.linalg.norm(0.5 * (last_imu.gyro + cur_imu.gyro))
        gyro_bias_scale = 1 + (gyro_norm / 0.5)
        Qi[9:12,9:12] = delta_t * self.gyro_bias_noise * np.eye(3) * gyro_bias_scale
        state.cov = Fx @ last_state.cov @ Fx.T + Fi @ Qi @ Fi.T
        state.timestamp = cur_imu.timestamp
        state.imu_data_ptr = cur_imu

class GpsProcessor:
    def __init__(self, I_p_Gps=np.zeros(3)):
        self.I_p_Gps = I_p_Gps

    def update_state_by_gps_position(self, init_lla, gps_data, state):
        H, residual = self.compute_jacobian_and_residual(init_lla, gps_data, state)
        V = gps_data.cov
        P = state.cov
        S = H @ P @ H.T + V
        K = P @ H.T @ np.linalg.inv(S)
        delta_x = K @ residual
        self.add_delta_to_state(delta_x, state)
        I_KH = np.eye(15) - K @ H
        state.cov = I_KH @ P @ I_KH.T + K @ V @ K.T

    def compute_jacobian_and_residual(self, init_lla, gps_data, state):
        G_p_I = state.G_p_I
        G_R_I = state.G_R_I
        G_p_Gps = convert_lla_to_enu(init_lla, gps_data.lla)
        residual = G_p_Gps - (G_p_I + G_R_I @ self.I_p_Gps)
        H = np.zeros((3, 15))
        H[0:3, 0:3] = np.eye(3)
        H[0:3, 6:9] = -G_R_I @ get_skew_matrix(self.I_p_Gps)
        return H, residual

    def add_delta_to_state(self, delta_x, state):
        state.G_p_I += delta_x[0:3]
        state.G_v_I += delta_x[3:6]
        delta_theta = delta_x[6:9]
        if np.linalg.norm(delta_theta) > 1e-12:
            delta_R = R.from_rotvec(delta_theta).as_matrix()
            state.G_R_I = state.G_R_I @ delta_R
        state.acc_bias += delta_x[9:12]
        state.gyro_bias += delta_x[12:15]
        state.gyro_bias += delta_x[12:15] * 1.2

class Initializer:
    def __init__(self, I_p_Gps=np.zeros(3)):
        self.I_p_Gps = I_p_Gps
        self.imu_buffer = []
        self.max_imu_buffer = 500

    def add_imu_data(self, imu_data):
        self.imu_buffer.append(imu_data)
        if len(self.imu_buffer) > self.max_imu_buffer:
            self.imu_buffer.pop(0)

    def add_gps_position_data(self, gps_data, state):
        if len(self.imu_buffer) < 10:
            return False
        state.G_p_I = np.zeros(3)
        state.G_v_I = np.zeros(3)
        acc_mean = np.mean([imu.acc for imu in self.imu_buffer], axis=0)
        gravity_norm = acc_mean / np.linalg.norm(acc_mean)
        z_axis = np.array([0, 0, 1])
        if np.linalg.norm(gravity_norm - z_axis) > 1e-6:
            v = np.cross(gravity_norm, z_axis)
            s = np.linalg.norm(v)
            c = np.dot(gravity_norm, z_axis)
            vx = get_skew_matrix(v)
            state.G_R_I = np.eye(3) + vx + vx @ vx * (1 - c) / (s ** 2) if s > 1e-6 else np.eye(3)
        else:
            state.G_R_I = np.eye(3)
        state.gyro_bias = np.mean([imu.gyro for imu in self.imu_buffer], axis=0)
        state.acc_bias = np.zeros(3)
        state.cov = np.eye(15)
        state.cov[0:3, 0:3] *= 1.0
        state.cov[3:6, 3:6] *= 0.1
        state.cov[6:9, 6:9] *= 0.1
        state.cov[9:12, 9:12] *= 0.01
        state.cov[12:15, 12:15] *= 0.01
        state.timestamp = gps_data.timestamp
        state.lla = gps_data.lla
        if self.imu_buffer:
            state.imu_data_ptr = self.imu_buffer[-1]
        return True

class ImuGpsLocalizer:
    def __init__(self, acc_noise=0.5, gyro_noise=0.01,
                 acc_bias_noise=0.01, gyro_bias_noise=0.001,
                 I_p_Gps=np.zeros(3)):
        self.initialized = False
        self.initializer = Initializer(I_p_Gps)
        self.imu_processor = ImuProcessor(acc_noise, gyro_noise,
                                         acc_bias_noise, gyro_bias_noise)
        self.gps_processor = GpsProcessor(I_p_Gps)
        self.state = State()
        self.init_lla = None
        try:
            self.rail_nodes = pd.read_csv('railway_nodes.csv')[['lat', 'lng']].values
            print(f"Loaded {len(self.rail_nodes)} railway nodes for map matching")
        except:
            self.rail_nodes = None
            print("No railway_nodes.csv found - proceeding without map matching")
        self.last_gps_time = None
        self.in_tunnel = False
        self.tunnel_threshold = 5.0  # seconds without GPS to detect tunnel
        self.heading_smoothing_factor = 0.5  # For gradual heading alignment (0-1)

    def find_closest_rail_point(self, lat, lon):
        if self.rail_nodes is None or len(self.rail_nodes) < 2:
            return lat, lon
        min_dist = float('inf')
        best_lat, best_lon = lat, lon
        for i in range(len(self.rail_nodes) - 1):
            lat1, lon1 = self.rail_nodes[i]
            lat2, lon2 = self.rail_nodes[i + 1]
            dx = lon2 - lon1
            dy = lat2 - lat1
            if dx == 0 and dy == 0:
                continue
            t = ((lon - lon1) * dx + (lat - lat1) * dy) / (dx * dx + dy * dy)
            t = max(0, min(1, t))
            closest_lon = lon1 + t * dx
            closest_lat = lat1 + t * dy
            dist_lat = (lat - closest_lat) * 111000
            dist_lon = (lon - closest_lon) * 111000 * np.cos(np.radians(lat))
            dist = np.sqrt(dist_lat**2 + dist_lon**2)
            if dist < min_dist:
                min_dist = dist
                best_lat = closest_lat
                best_lon = closest_lon
        if min_dist < 30:
            return best_lat, best_lon
        else:
            return lat, lon

    def process_imu_data(self, imu_data):
        current_time = imu_data.timestamp
        if self.last_gps_time is not None:
            time_since_gps = current_time - self.last_gps_time
            self.in_tunnel = time_since_gps > self.tunnel_threshold
        else:
            self.in_tunnel = False
        if not self.initialized:
            self.initializer.add_imu_data(imu_data)
            return False, self.state
        if self.state.imu_data_ptr is not None:
            self.imu_processor.predict(self.state.imu_data_ptr, imu_data, self.state)
        if self.init_lla is not None:
            self.state.lla = convert_enu_to_lla(self.init_lla, self.state.G_p_I)
            if self.rail_nodes is not None:
                original_lat = self.state.lla[0]
                original_lon = self.state.lla[1]
                snapped_lat, snapped_lon = self.find_closest_rail_point(original_lat, original_lon)
                self.state.lla[0] = snapped_lat
                self.state.lla[1] = snapped_lon
                snapped_enu = convert_lla_to_enu(self.init_lla, [snapped_lat, snapped_lon, self.state.lla[2]])
                self.state.G_p_I = snapped_enu
                if self.in_tunnel or (self.last_gps_time and time_since_gps < 1.0):
                    closest_idx = self._get_closest_rail_idx(snapped_lat, snapped_lon)
                    if closest_idx < len(self.rail_nodes) - 1:
                        next_point = self.rail_nodes[closest_idx + 1]
                        direction_vec = np.array([next_point[1] - snapped_lon, next_point[0] - snapped_lat, 0])
                        direction_vec /= np.linalg.norm(direction_vec) + 1e-6
                        target_yaw = np.arctan2(direction_vec[0], direction_vec[1])
                        current_rot = R.from_matrix(self.state.G_R_I)
                        current_euler = current_rot.as_euler('xyz')
                        smoothed_yaw = current_euler[2] * (1 - self.heading_smoothing_factor) + target_yaw * self.heading_smoothing_factor
                        target_euler = [current_euler[0], current_euler[1], smoothed_yaw]
                        self.state.G_R_I = R.from_euler('xyz', target_euler).as_matrix()
        return True, self.state

    def process_gps_position_data(self, gps_data):
        self.last_gps_time = gps_data.timestamp
        self.in_tunnel = False
        if not self.initialized:
            if not self.initializer.add_gps_position_data(gps_data, self.state):
                return False
            self.init_lla = gps_data.lla
            self.initialized = True
            return True
        self.gps_processor.update_state_by_gps_position(self.init_lla, gps_data, self.state)
        return True

    def _get_closest_rail_idx(self, lat, lon):
        dists = np.sqrt((self.rail_nodes[:,0] - lat)**2 + (self.rail_nodes[:,1] - lon)**2)
        return np.argmin(dists)

# Main execution
if __name__ == "__main__":
    df = pd.read_csv('3.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    print(f"Total rows: {len(df)}")
    df['has_gps'] = (df['gps_lat'].notna()) & (df['gps_lng'].notna()) & \
                     (df['gps_lat'] != 0) & (df['gps_lng'] != 0)
    print(f"Rows with GPS: {df['has_gps'].sum()}")
    localizer = ImuGpsLocalizer(
        acc_noise=0.5,
        gyro_noise=0.01,
        acc_bias_noise=0.01,
        gyro_bias_noise=0.00005,
        I_p_Gps=np.zeros(3)
    )
    eskf_path = []
    gps_path = []
    rail_path = []
    try:
        rail_df = pd.read_csv('railway_nodes.csv')
        for _, row in rail_df.iterrows():
            rail_path.append({'lat': row['lat'], 'lon': row['lng']})
        print(f"Railway path loaded with {len(rail_path)} points")
    except:
        print("No railway path for visualization")
    last_time = None
    gps_update_count = 0
    imu_update_count = 0
    for i in range(len(df)):
        row = df.iloc[i]
        imu_data = ImuData(
            row['timestamp'].timestamp(),
            np.array([row['accel_x'], row['accel_y'], row['accel_z']]) * 9.81,
            np.array([row['gyro_x'], row['gyro_y'], row['gyro_z']])
        )
        success, state = localizer.process_imu_data(imu_data)
        if success:
            imu_update_count += 1
            if localizer.init_lla is not None:
                eskf_path.append({
                    'lat': state.lla[0],
                    'lon': state.lla[1],
                    'time': row['timestamp']
                })
        if row['has_gps']:
            gps_data = GpsPositionData(
                row['timestamp'].timestamp(),
                np.array([row['gps_lat'], row['gps_lng'], 0]),
                np.eye(3) * 25.0
            )
            if localizer.process_gps_position_data(gps_data):
                gps_update_count += 1
                gps_path.append({
                    'lat': row['gps_lat'],
                    'lon': row['gps_lng'],
                    'time': row['timestamp']
                })
    print(f"\nProcessing complete:")
    print(f"GPS updates: {gps_update_count}")
    print(f"IMU updates: {imu_update_count}")
    print(f"ESKF path points: {len(eskf_path)}")
    fig = go.Figure()
    sample_interval = 50
    eskf_display = eskf_path[::sample_interval]
    gps_display = gps_path[::sample_interval]
    if rail_path:
        fig.add_trace(go.Scattermapbox(
            mode="lines",
            lon=[p['lon'] for p in rail_path],
            lat=[p['lat'] for p in rail_path],
            line=dict(width=4, color='green'),
            name='Railway Track',
            opacity=0.8
        ))
    if gps_display:
        fig.add_trace(go.Scattermapbox(
            mode="lines+markers",
            lon=[p['lon'] for p in gps_display],
            lat=[p['lat'] for p in gps_display],
            marker=dict(size=10, color='red'),
            line=dict(width=3, color='red'),
            name='GPS Measurements'
        ))
    if eskf_display:
        fig.add_trace(go.Scattermapbox(
            mode="lines+markers",
            lon=[p['lon'] for p in eskf_display],
            lat=[p['lat'] for p in eskf_display],
            marker=dict(size=8, color='blue'),
            line=dict(width=2, color='blue'),
            name='ESKF Path (Map-Matched)' if localizer.rail_nodes is not None else 'ESKF Path'
        ))
    if eskf_path:
        fig.add_trace(go.Scattermapbox(
            mode="markers+text",
            lon=[eskf_path[0]['lon'], eskf_path[-1]['lon']],
            lat=[eskf_path[0]['lat'], eskf_path[-1]['lat']],
            marker=dict(size=20, color=['green', 'purple']),
            text=["START", "END"],
            textposition="top center",
            showlegend=False
        ))
    if eskf_path:
        all_lats = [p['lat'] for p in eskf_path]
        all_lons = [p['lon'] for p in eskf_path]
        center_lat = np.mean(all_lats)
        center_lon = np.mean(all_lons)
        lat_range = max(all_lats) - min(all_lats)
        lon_range = max(all_lons) - min(all_lons)
        max_range = max(lat_range, lon_range)
        zoom = 18 - np.log2(max_range * 111) if max_range > 0 else 11
        zoom = max(10, min(14, zoom))
    else:
        center_lat, center_lon, zoom = 37.5, 126.9, 11
    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=zoom
        ),
        title=f"ESKF with Railway Map Matching<br><sub>GPS: {gps_update_count}, IMU: {imu_update_count}, Rail Nodes: {len(rail_path)}</sub>",
        height=800,
        showlegend=True
    )
    config = {'scrollZoom': True}
    fig.write_html('eskf_rail_matched.html', config=config)
    print("\n" + "=" * 60)
    print("Saved to eskf_rail_matched.html")
    fig.show(config=config)