import struct
import pandas as pd
import math
import os

def kucs_to_wgs84(x, y):
    """
    한국통합좌표계(KUCS)를 WGS84로 변환
    간단한 근사 변환식 사용 (정확한 변환을 위해서는 pyproj 필요)
    """
    # KUCS 파라미터 (TM 투영)
    false_easting = 1000000.0
    false_northing = 2000000.0
    central_meridian = 127.5
    scale_factor = 0.9996
    latitude_of_origin = 38.0

    # 투영 좌표를 지리 좌표로 역변환 (근사식)
    # 이는 간단한 근사치이며, 정확한 변환을 위해서는 전문 라이브러리 필요

    # False 값 제거
    x_adj = x - false_easting
    y_adj = y - false_northing

    # 근사 변환 (한반도 지역에서만 유효)
    # 1도 ≈ 111km, 한국 지역 보정 계수 적용

    lat_factor = 111000.0  # 위도 1도당 미터
    lon_factor = 88000.0   # 경도 1도당 미터 (위도 37도 기준)

    # 중앙 경선에서의 오프셋 계산
    lat = latitude_of_origin + (y_adj / lat_factor)
    lon = central_meridian + (x_adj / lon_factor)

    return lat, lon

def read_railway_and_convert(shp_file):
    """철도 데이터 읽기 및 WGS84 변환"""
    print("Reading and converting railway data...")

    try:
        with open(shp_file, 'rb') as f:
            header = f.read(100)

            file_code = struct.unpack('>I', header[0:4])[0]
            if file_code != 9994:
                print(f"Invalid Shapefile: {file_code}")
                return []

            shape_type = struct.unpack('<I', header[32:36])[0]
            bbox = struct.unpack('<dddd', header[36:68])

            print(f"Original bounds (KUCS): X({bbox[0]:.1f}-{bbox[2]:.1f}) Y({bbox[1]:.1f}-{bbox[3]:.1f})")

            coords = []
            record_num = 0

            while True:
                record_header = f.read(8)
                if len(record_header) < 8:
                    break

                record_number = struct.unpack('>I', record_header[0:4])[0]
                content_length = struct.unpack('>I', record_header[4:8])[0] * 2

                record_data = f.read(content_length)
                if len(record_data) < content_length:
                    break

                if len(record_data) >= 4:
                    shape_type_record = struct.unpack('<I', record_data[0:4])[0]

                    if shape_type_record == 3:  # PolyLine
                        if len(record_data) >= 44:
                            num_parts = struct.unpack('<I', record_data[36:40])[0]
                            num_points = struct.unpack('<I', record_data[40:44])[0]

                            points_start = 44 + num_parts * 4

                            for i in range(num_points):
                                point_offset = points_start + i * 16
                                if point_offset + 16 <= len(record_data):
                                    x, y = struct.unpack('<dd', record_data[point_offset:point_offset+16])

                                    # KUCS를 WGS84로 변환
                                    lat, lon = kucs_to_wgs84(x, y)
                                    coords.append([lat, lon])

                record_num += 1
                if record_num % 1000 == 0:
                    print(f"Processed: {record_num} records")

            print(f"Total: {record_num} records, {len(coords)} coordinates")

            if coords:
                lats = [coord[0] for coord in coords]
                lons = [coord[1] for coord in coords]
                print(f"Converted bounds (WGS84): lat({min(lats):.6f}-{max(lats):.6f}) lon({min(lons):.6f}-{max(lons):.6f})")

            return coords

    except Exception as e:
        print(f"Error: {e}")
        return []

# 실행
print("="*60)
print("Railway Coordinate Conversion (KUCS to WGS84)")
print("="*60)

# GPS 데이터 범위
gps_bbox = [37.502775, 37.547443, 126.881396, 126.971283]
print(f"Target GPS range: lat({gps_bbox[0]:.6f}-{gps_bbox[1]:.6f}) lon({gps_bbox[2]:.6f}-{gps_bbox[3]:.6f})")
print()

# Shapefile 변환
shp_file = r"C:\Users\jegil\Desktop\Work\work\data\국가기본도_철도링크\TN_RLROAD_LINK.shp"
all_coords = read_railway_and_convert(shp_file)

if all_coords:
    # GPS 범위와 매칭되는 노드 필터링
    margin = 0.02  # 2km 여유
    filter_bbox = [
        gps_bbox[0] - margin, gps_bbox[1] + margin,
        gps_bbox[2] - margin, gps_bbox[3] + margin
    ]

    print(f"\nFiltering range: lat({filter_bbox[0]:.6f}-{filter_bbox[1]:.6f}) lon({filter_bbox[2]:.6f}-{filter_bbox[3]:.6f})")

    filtered = []
    for lat, lon in all_coords:
        if (filter_bbox[0] <= lat <= filter_bbox[1] and
            filter_bbox[2] <= lon <= filter_bbox[3]):
            filtered.append([lat, lon])

    print(f"Filtered result: {len(filtered)} nodes in target area")

    if filtered:
        # CSV 저장
        df = pd.DataFrame(filtered, columns=['lat', 'lng'])
        output_file = r"C:\Users\jegil\Desktop\Work\work\data\railway_nodes_national.csv"
        df.to_csv(output_file, index=False)
        print(f"Saved: {output_file}")

        # 샘플 데이터 표시
        print(f"\nSample railway nodes:")
        for i in range(min(15, len(filtered))):
            print(f"  {i+1:2d}: ({filtered[i][0]:.6f}, {filtered[i][1]:.6f})")

        # 기존 데이터 비교
        old_file = r"C:\Users\jegil\Desktop\Work\work\data\railway_nodes.csv"
        if os.path.exists(old_file):
            old_df = pd.read_csv(old_file)
            print(f"\nData comparison:")
            print(f"  Old railway_nodes.csv: {len(old_df):4d} nodes")
            print(f"  New national data:     {len(df):4d} nodes")
            print(f"  Old lat range: {old_df['lat'].min():.6f} ~ {old_df['lat'].max():.6f}")
            print(f"  New lat range: {df['lat'].min():.6f} ~ {df['lat'].max():.6f}")
            print(f"  Old lon range: {old_df['lng'].min():.6f} ~ {old_df['lng'].max():.6f}")
            print(f"  New lon range: {df['lng'].min():.6f} ~ {df['lng'].max():.6f}")

            # GPS 경로와의 거리 확인
            gps_center_lat = (gps_bbox[0] + gps_bbox[1]) / 2
            gps_center_lon = (gps_bbox[2] + gps_bbox[3]) / 2

            print(f"\nProximity to GPS center ({gps_center_lat:.6f}, {gps_center_lon:.6f}):")

            # 가장 가까운 철도 노드 찾기
            min_dist = float('inf')
            closest_node = None

            for _, row in df.head(50).iterrows():  # 처음 50개만 체크
                dist = ((row['lat'] - gps_center_lat) ** 2 + (row['lng'] - gps_center_lon) ** 2) ** 0.5
                if dist < min_dist:
                    min_dist = dist
                    closest_node = (row['lat'], row['lng'])

            if closest_node:
                dist_km = min_dist * 111  # 대략적인 km 변환
                print(f"  Closest railway node: ({closest_node[0]:.6f}, {closest_node[1]:.6f})")
                print(f"  Distance: {dist_km:.2f} km")
    else:
        print("No railway nodes found in target area after conversion!")

        # 변환된 전체 범위 다시 확인
        if all_coords:
            lats = [coord[0] for coord in all_coords]
            lons = [coord[1] for coord in all_coords]
            print(f"Full converted range: lat({min(lats):.6f}-{max(lats):.6f}) lon({min(lons):.6f}-{max(lons):.6f})")
else:
    print("Failed to read and convert Shapefile")

print("\n" + "="*60)