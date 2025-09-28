import struct
import pandas as pd
import os

def read_shp_binary(shp_file):
    """Shapefile 바이너리 읽기 (유니코드 이슈 회피)"""
    print("Reading Shapefile...")

    try:
        with open(shp_file, 'rb') as f:
            # SHP 헤더 읽기
            header = f.read(100)

            # 파일 코드 확인
            file_code = struct.unpack('>I', header[0:4])[0]
            if file_code != 9994:
                print(f"Invalid Shapefile: {file_code}")
                return []

            # Shape 타입
            shape_type = struct.unpack('<I', header[32:36])[0]
            print(f"Shape type: {shape_type} (PolyLine={shape_type==3})")

            # 바운딩 박스
            bbox = struct.unpack('<dddd', header[36:68])
            print(f"Bounds: X({bbox[0]:.6f}, {bbox[2]:.6f}) Y({bbox[1]:.6f}, {bbox[3]:.6f})")

            coords = []
            record_num = 0

            while True:
                # 레코드 헤더
                record_header = f.read(8)
                if len(record_header) < 8:
                    break

                record_number = struct.unpack('>I', record_header[0:4])[0]
                content_length = struct.unpack('>I', record_header[4:8])[0] * 2

                # 레코드 내용
                record_data = f.read(content_length)
                if len(record_data) < content_length:
                    break

                # PolyLine 파싱
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
                                    coords.append([y, x])  # [lat, lon]

                record_num += 1
                if record_num % 100 == 0:
                    print(f"Processed records: {record_num}")

            print(f"Total: {record_num} records, {len(coords)} coordinates")
            return coords

    except Exception as e:
        print(f"Error: {e}")
        return []

# 실행
print("="*60)
print("National Railway Data Analysis")
print("="*60)

# GPS 데이터 범위
gps_bbox = [37.502775, 37.547443, 126.881396, 126.971283]
print(f"GPS range: lat({gps_bbox[0]:.6f}-{gps_bbox[1]:.6f}) lon({gps_bbox[2]:.6f}-{gps_bbox[3]:.6f})")
print()

# Shapefile 읽기
shp_file = r"C:\Users\jegil\Desktop\Work\work\data\국가기본도_철도링크\TN_RLROAD_LINK.shp"
all_coords = read_shp_binary(shp_file)

if all_coords:
    # 전체 범위
    lats = [coord[0] for coord in all_coords]
    lons = [coord[1] for coord in all_coords]
    print(f"\nRailway range: lat({min(lats):.6f}-{max(lats):.6f}) lon({min(lons):.6f}-{max(lons):.6f})")

    # GPS 범위와 겹치는지 확인
    margin = 0.01
    filter_bbox = [
        gps_bbox[0] - margin, gps_bbox[1] + margin,
        gps_bbox[2] - margin, gps_bbox[3] + margin
    ]

    # 필터링
    filtered = []
    for lat, lon in all_coords:
        if (filter_bbox[0] <= lat <= filter_bbox[1] and
            filter_bbox[2] <= lon <= filter_bbox[3]):
            filtered.append([lat, lon])

    print(f"\nFiltered: {len(filtered)} nodes in GPS area")

    if filtered:
        # CSV 저장
        df = pd.DataFrame(filtered, columns=['lat', 'lng'])
        output_file = r"C:\Users\jegil\Desktop\Work\work\data\railway_nodes_national.csv"
        df.to_csv(output_file, index=False)
        print(f"Saved: {output_file}")

        # 샘플 표시
        print(f"\nSample nodes:")
        for i in range(min(10, len(filtered))):
            print(f"  {i+1}: ({filtered[i][0]:.6f}, {filtered[i][1]:.6f})")

        # 기존 데이터 비교
        old_file = r"C:\Users\jegil\Desktop\Work\work\data\railway_nodes.csv"
        if os.path.exists(old_file):
            old_df = pd.read_csv(old_file)
            print(f"\nComparison:")
            print(f"  Old file: {len(old_df)} nodes")
            print(f"  New file: {len(df)} nodes")
            print(f"  Old range: lat({old_df['lat'].min():.6f}-{old_df['lat'].max():.6f})")
            print(f"  New range: lat({df['lat'].min():.6f}-{df['lat'].max():.6f})")
    else:
        print("No railway nodes found in GPS area!")
else:
    print("Failed to read Shapefile")

print("\n" + "="*60)