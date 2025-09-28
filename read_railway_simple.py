import struct
import os

def read_shp_simple(shp_file):
    """간단한 Shapefile 리더 (폴리라인용)"""
    print(f"Shapefile 읽기: {shp_file}")

    try:
        with open(shp_file, 'rb') as f:
            # SHP 헤더 읽기
            header = f.read(100)

            # 파일 코드 확인 (앞 4바이트, big-endian)
            file_code = struct.unpack('>I', header[0:4])[0]
            if file_code != 9994:
                print(f"❌ 잘못된 Shapefile 형식: {file_code}")
                return []

            # Shape 타입 (28-32바이트, little-endian)
            shape_type = struct.unpack('<I', header[32:36])[0]
            print(f"✓ Shape 타입: {shape_type} ({'PolyLine' if shape_type == 3 else 'Other'})")

            # 바운딩 박스 (36-100바이트, little-endian doubles)
            bbox = struct.unpack('<dddd', header[36:68])
            print(f"✓ 경계 (Xmin, Ymin, Xmax, Ymax): {bbox}")

            # 레코드 읽기
            coords = []
            record_num = 0

            while True:
                # 레코드 헤더 (8바이트)
                record_header = f.read(8)
                if len(record_header) < 8:
                    break

                record_number = struct.unpack('>I', record_header[0:4])[0]
                content_length = struct.unpack('>I', record_header[4:8])[0] * 2  # words to bytes

                # 레코드 내용 읽기
                record_data = f.read(content_length)
                if len(record_data) < content_length:
                    break

                # Shape 타입 확인 (첫 4바이트)
                if len(record_data) >= 4:
                    shape_type_record = struct.unpack('<I', record_data[0:4])[0]

                    if shape_type_record == 3:  # PolyLine
                        # PolyLine 구조 파싱
                        if len(record_data) >= 44:
                            # 바운딩 박스 건너뛰기 (4-36바이트)
                            # NumParts (36-40바이트)
                            num_parts = struct.unpack('<I', record_data[36:40])[0]
                            # NumPoints (40-44바이트)
                            num_points = struct.unpack('<I', record_data[40:44])[0]

                            # Parts 배열 건너뛰기 (44 + num_parts*4 바이트)
                            points_start = 44 + num_parts * 4

                            # 포인트 배열 읽기 (각 포인트는 16바이트: X, Y doubles)
                            line_coords = []
                            for i in range(num_points):
                                point_offset = points_start + i * 16
                                if point_offset + 16 <= len(record_data):
                                    x, y = struct.unpack('<dd', record_data[point_offset:point_offset+16])
                                    # [위도, 경도] 형태로 저장 (x=경도, y=위도)
                                    line_coords.append([y, x])

                            coords.extend(line_coords)

                record_num += 1
                if record_num % 100 == 0:
                    print(f"  처리된 레코드: {record_num}")

            print(f"✓ 총 {record_num}개 레코드, {len(coords)}개 좌표점 추출")
            return coords

    except Exception as e:
        print(f"❌ 파일 읽기 오류: {e}")
        return []

def filter_coordinates(coords, bbox):
    """좌표 범위 필터링"""
    min_lat, max_lat, min_lon, max_lon = bbox
    filtered = []

    for lat, lon in coords:
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            filtered.append([lat, lon])

    return filtered

# 메인 실행
print("="*60)
print("국가기본도 철도링크 데이터 분석 (Simple)")
print("="*60)

shp_file = r"C:\Users\jegil\Desktop\Work\work\data\국가기본도_철도링크\TN_RLROAD_LINK.shp"

# GPS 데이터 범위 (data.csv 기준)
data_min_lat, data_max_lat = 37.502775, 37.547443
data_min_lon, data_max_lon = 126.881396, 126.971283

print(f"GPS 데이터 범위:")
print(f"  위도: {data_min_lat:.6f} ~ {data_max_lat:.6f}")
print(f"  경도: {data_min_lon:.6f} ~ {data_max_lon:.6f}")
print()

# Shapefile 읽기
all_coords = read_shp_simple(shp_file)

if all_coords:
    print(f"\n전체 철도 좌표 범위:")
    lats = [coord[0] for coord in all_coords]
    lons = [coord[1] for coord in all_coords]
    print(f"  위도: {min(lats):.6f} ~ {max(lats):.6f}")
    print(f"  경도: {min(lons):.6f} ~ {max(lons):.6f}")

    # 여유분 추가
    margin = 0.01
    bbox = (
        data_min_lat - margin,
        data_max_lat + margin,
        data_min_lon - margin,
        data_max_lon + margin
    )

    print(f"\n필터링 범위 (여유분 포함):")
    print(f"  위도: {bbox[0]:.6f} ~ {bbox[1]:.6f}")
    print(f"  경도: {bbox[2]:.6f} ~ {bbox[3]:.6f}")

    # 좌표 필터링
    filtered_coords = filter_coordinates(all_coords, bbox)

    print(f"\n✓ 필터링 완료: {len(filtered_coords)}개 철도 노드 발견")

    if filtered_coords:
        # CSV 저장
        import pandas as pd

        rail_df = pd.DataFrame(filtered_coords, columns=['lat', 'lng'])
        output_file = r"C:\Users\jegil\Desktop\Work\work\data\railway_nodes_national.csv"
        rail_df.to_csv(output_file, index=False)
        print(f"✓ 철도 노드 저장: {output_file}")

        # 샘플 데이터 표시
        print(f"\n샘플 철도 노드 (처음 10개):")
        for i, (lat, lon) in enumerate(filtered_coords[:10]):
            print(f"  {i+1}: ({lat:.6f}, {lon:.6f})")

        # 기존 데이터와 비교
        if os.path.exists(r"C:\Users\jegil\Desktop\Work\work\data\railway_nodes.csv"):
            old_df = pd.read_csv(r"C:\Users\jegil\Desktop\Work\work\data\railway_nodes.csv")
            print(f"\n데이터 비교:")
            print(f"  기존 railway_nodes.csv: {len(old_df)} 개 노드")
            print(f"  새 national 데이터:     {len(rail_df)} 개 노드")

            print(f"\n좌표 범위 비교:")
            print(f"  기존 - 위도: {old_df['lat'].min():.6f} ~ {old_df['lat'].max():.6f}")
            print(f"  기존 - 경도: {old_df['lng'].min():.6f} ~ {old_df['lng'].max():.6f}")
            print(f"  새   - 위도: {rail_df['lat'].min():.6f} ~ {rail_df['lat'].max():.6f}")
            print(f"  새   - 경도: {rail_df['lng'].min():.6f} ~ {rail_df['lng'].max():.6f}")
    else:
        print("❌ 해당 범위에서 철도 노드를 찾을 수 없습니다.")
else:
    print("❌ Shapefile 읽기 실패")

print("\n" + "="*60)