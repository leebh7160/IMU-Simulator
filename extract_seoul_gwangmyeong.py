import pandas as pd
import numpy as np
import math

print("서울역-광명역 철도선 정확 추출")
print("="*50)

# 국가기본도 전체 철도 데이터 로드
df_all = pd.read_csv('data/railway_nodes_national.csv')
print(f"전체 국가기본도 철도 노드: {len(df_all)}")

# 서울역-광명역 GPS 좌표
seoul_station = (37.502775, 126.881396)
gwangmyeong_station = (37.551884, 126.970314)

print(f"서울역: {seoul_station}")
print(f"광명역: {gwangmyeong_station}")

# 거리 계산
def distance(lat1, lng1, lat2, lng2):
    return ((lat1-lat2)**2 + (lng1-lng2)**2)**0.5

# 두 점 사이의 모든 중간 지점들을 커버하는 철도 노드들 찾기
def find_railway_between_stations(start_station, end_station, all_nodes, search_radius=0.02):
    """두 역 사이의 철도선 찾기"""

    # 시작역과 끝역 근처의 모든 철도 노드 찾기
    start_candidates = []
    end_candidates = []

    for idx, row in all_nodes.iterrows():
        start_dist = distance(row['lat'], row['lng'], start_station[0], start_station[1])
        end_dist = distance(row['lat'], row['lng'], end_station[0], end_station[1])

        if start_dist < search_radius:
            start_candidates.append((idx, row, start_dist))
        if end_dist < search_radius:
            end_candidates.append((idx, row, end_dist))

    print(f"\n서울역 근처 철도 노드: {len(start_candidates)}개")
    print(f"광명역 근처 철도 노드: {len(end_candidates)}개")

    # 가장 가까운 시작점과 끝점 찾기
    if not start_candidates or not end_candidates:
        return []

    start_candidates.sort(key=lambda x: x[2])
    end_candidates.sort(key=lambda x: x[2])

    best_start = start_candidates[0]
    best_end = end_candidates[0]

    print(f"가장 가까운 시작 노드: ({best_start[1]['lat']:.6f}, {best_start[1]['lng']:.6f}) - 거리 {best_start[2]:.6f}")
    print(f"가장 가까운 끝 노드: ({best_end[1]['lat']:.6f}, {best_end[1]['lng']:.6f}) - 거리 {best_end[2]:.6f}")

    # 두 점 사이의 경로 상에 있는 모든 철도 노드 찾기
    # 직선 경로 상에서 ±2km 이내에 있는 모든 노드들을 수집
    route_nodes = []

    # 서울-광명 사이의 직선 방향
    total_lat_diff = end_station[0] - start_station[0]
    total_lng_diff = end_station[1] - start_station[1]
    total_distance = (total_lat_diff**2 + total_lng_diff**2)**0.5

    for idx, row in all_nodes.iterrows():
        node_lat, node_lng = row['lat'], row['lng']

        # 이 노드가 서울-광명 직선 경로에서 얼마나 떨어져 있는지 계산
        # 점에서 직선까지의 거리 공식 사용

        # 서울역에서 현재 노드까지의 벡터
        to_node_lat = node_lat - start_station[0]
        to_node_lng = node_lng - start_station[1]

        # 서울-광명 방향 벡터에 투영
        projection_ratio = (to_node_lat * total_lat_diff + to_node_lng * total_lng_diff) / (total_distance**2)

        # 투영점 좌표
        proj_lat = start_station[0] + projection_ratio * total_lat_diff
        proj_lng = start_station[1] + projection_ratio * total_lng_diff

        # 노드에서 투영점까지의 거리 (직선으로부터의 거리)
        line_distance = distance(node_lat, node_lng, proj_lat, proj_lng)

        # 서울역-광명역 구간 내에 있고, 직선에서 2km 이내인 노드들만 선택
        if 0 <= projection_ratio <= 1 and line_distance < 0.02:
            node_distance_from_seoul = distance(node_lat, node_lng, start_station[0], start_station[1])
            route_nodes.append((idx, row, projection_ratio, line_distance, node_distance_from_seoul))

    print(f"\n서울-광명 직선 경로 상의 철도 노드: {len(route_nodes)}개")

    # 서울역부터의 거리 순으로 정렬
    route_nodes.sort(key=lambda x: x[4])

    # 결과 반환
    result_nodes = []
    for node_info in route_nodes:
        idx, row, projection_ratio, line_distance, dist_from_seoul = node_info
        result_nodes.append((row['lat'], row['lng']))

    return result_nodes

# 서울-광명 철도선 추출
railway_line = find_railway_between_stations(seoul_station, gwangmyeong_station, df_all)

if len(railway_line) > 0:
    print(f"\n=== 추출 결과 ===")
    print(f"총 노드 수: {len(railway_line)}")

    # DataFrame으로 변환
    railway_df = pd.DataFrame(railway_line, columns=['lat', 'lng'])

    # 방향성 확인
    if len(railway_df) > 1:
        lat_diff = railway_df.iloc[-1]['lat'] - railway_df.iloc[0]['lat']
        lng_diff = railway_df.iloc[-1]['lng'] - railway_df.iloc[0]['lng']
        angle = math.degrees(math.atan2(lng_diff, lat_diff))
        print(f"철도선 방향: {angle:.1f}도")

        # GPS 경로와 비교
        gps_lat_diff = gwangmyeong_station[0] - seoul_station[0]
        gps_lng_diff = gwangmyeong_station[1] - seoul_station[1]
        gps_angle = math.degrees(math.atan2(gps_lng_diff, gps_lat_diff))
        print(f"GPS 경로 방향: {gps_angle:.1f}도")
        print(f"방향 차이: {abs(angle - gps_angle):.1f}도")

    # 시작점과 끝점 확인
    start_dist = distance(railway_df.iloc[0]['lat'], railway_df.iloc[0]['lng'], seoul_station[0], seoul_station[1])
    end_dist = distance(railway_df.iloc[-1]['lat'], railway_df.iloc[-1]['lng'], gwangmyeong_station[0], gwangmyeong_station[1])

    print(f"\n서울역과의 거리: {start_dist:.6f}")
    print(f"광명역과의 거리: {end_dist:.6f}")

    # 파일 저장
    railway_df.to_csv('data/railway_nodes_seoul_gwangmyeong.csv', index=False)
    print(f"\n파일 저장: data/railway_nodes_seoul_gwangmyeong.csv")

    # 샘플 출력
    print(f"\n첫 10개 노드:")
    for i, (idx, row) in enumerate(railway_df.head(10).iterrows()):
        print(f"  {i+1:2d}: ({row['lat']:.6f}, {row['lng']:.6f})")

    print(f"\n마지막 10개 노드:")
    for i, (idx, row) in enumerate(railway_df.tail(10).iterrows()):
        print(f"  {len(railway_df)-9+i:2d}: ({row['lat']:.6f}, {row['lng']:.6f})")

else:
    print("\n서울-광명 철도선을 찾을 수 없습니다!")