import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point
import os

# 철도 데이터 파일 경로
railway_shapefile = r"C:\Users\jegil\Desktop\Work\work\data\국가기본도_철도링크\TN_RLROAD_LINK.shp"

print("="*60)
print("국가기본도 철도링크 데이터 분석")
print("="*60)

# Shapefile 읽기
try:
    gdf = gpd.read_file(railway_shapefile, encoding='cp949')
    print(f"✓ 철도 데이터 로드 완료: {len(gdf)} 개 철도링크")
    print(f"✓ 좌표계: {gdf.crs}")
    print(f"✓ 컬럼: {list(gdf.columns)}")
    print()

    # 데이터 샘플 확인
    print("데이터 샘플:")
    print(gdf.head(3))
    print()

    # 서울역-광명역 구간 필터링 (대략적인 좌표 범위)
    # 서울역: 37.5547, 126.9706
    # 광명역: 37.4163, 126.8842
    seoul_lat, seoul_lon = 37.5547, 126.9706
    gwangmyeong_lat, gwangmyeong_lon = 37.4163, 126.8842

    # 실제 GPS 데이터 범위 (data.csv 기준)
    data_min_lat, data_max_lat = 37.502775, 37.547443
    data_min_lon, data_max_lon = 126.881396, 126.971283

    print(f"GPS 데이터 범위:")
    print(f"  위도: {data_min_lat:.6f} ~ {data_max_lat:.6f}")
    print(f"  경도: {data_min_lon:.6f} ~ {data_max_lon:.6f}")
    print()

    # WGS84로 변환 (필요한 경우)
    if gdf.crs.to_string() != 'EPSG:4326':
        print(f"좌표계 변환: {gdf.crs} → WGS84")
        gdf = gdf.to_crs('EPSG:4326')
        print("✓ WGS84 변환 완료")
        print()

    # 경계 박스 생성 (GPS 데이터 범위 + 여유분)
    margin = 0.01  # 1km 정도 여유
    bbox_min_lat = data_min_lat - margin
    bbox_max_lat = data_max_lat + margin
    bbox_min_lon = data_min_lon - margin
    bbox_max_lon = data_max_lon + margin

    print(f"필터링 범위 (여유분 포함):")
    print(f"  위도: {bbox_min_lat:.6f} ~ {bbox_max_lat:.6f}")
    print(f"  경도: {bbox_min_lon:.6f} ~ {bbox_max_lon:.6f}")
    print()

    # 해당 범위 내 철도 링크 필터링
    # geometry의 bounds를 이용해서 필터링
    filtered_gdf = gdf.cx[bbox_min_lon:bbox_max_lon, bbox_min_lat:bbox_max_lat]

    print(f"✓ 필터링 완료: {len(filtered_gdf)} 개 철도링크 발견")
    print()

    if len(filtered_gdf) > 0:
        print("필터링된 철도 데이터:")
        for idx, row in filtered_gdf.head(10).iterrows():
            geom = row.geometry
            if hasattr(geom, 'coords'):
                coords = list(geom.coords)
                print(f"  링크 {idx}: {len(coords)}개 좌표점")
                print(f"    시작: ({coords[0][1]:.6f}, {coords[0][0]:.6f})")
                print(f"    끝:   ({coords[-1][1]:.6f}, {coords[-1][0]:.6f})")
            print()

        # 모든 좌표점 추출
        all_coords = []
        for _, row in filtered_gdf.iterrows():
            geom = row.geometry
            if hasattr(geom, 'coords'):
                coords = list(geom.coords)
                for coord in coords:
                    # coord는 (경도, 위도) 순서
                    all_coords.append([coord[1], coord[0]])  # [위도, 경도]로 변환

        print(f"✓ 총 {len(all_coords)}개 철도 노드 추출")

        # CSV 파일로 저장
        rail_df = pd.DataFrame(all_coords, columns=['lat', 'lng'])
        output_file = r"C:\Users\jegil\Desktop\Work\work\data\railway_nodes_national.csv"
        rail_df.to_csv(output_file, index=False)
        print(f"✓ 철도 노드 저장: {output_file}")

        # 기존 railway_nodes.csv와 비교
        if os.path.exists(r"C:\Users\jegil\Desktop\Work\work\data\railway_nodes.csv"):
            old_df = pd.read_csv(r"C:\Users\jegil\Desktop\Work\work\data\railway_nodes.csv")
            print(f"\n기존 railway_nodes.csv: {len(old_df)} 개 노드")
            print(f"새 national 데이터:     {len(rail_df)} 개 노드")

            # 좌표 범위 비교
            print(f"\n좌표 범위 비교:")
            print(f"기존 데이터 - 위도: {old_df['lat'].min():.6f} ~ {old_df['lat'].max():.6f}")
            print(f"기존 데이터 - 경도: {old_df['lng'].min():.6f} ~ {old_df['lng'].max():.6f}")
            print(f"새 데이터   - 위도: {rail_df['lat'].min():.6f} ~ {rail_df['lat'].max():.6f}")
            print(f"새 데이터   - 경도: {rail_df['lng'].min():.6f} ~ {rail_df['lng'].max():.6f}")
    else:
        print("❌ 해당 범위에서 철도 데이터를 찾을 수 없습니다.")

        # 전체 데이터의 범위 확인
        bounds = gdf.total_bounds
        print(f"전체 철도 데이터 범위:")
        print(f"  경도: {bounds[0]:.6f} ~ {bounds[2]:.6f}")
        print(f"  위도: {bounds[1]:.6f} ~ {bounds[3]:.6f}")

except Exception as e:
    print(f"❌ 오류 발생: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)