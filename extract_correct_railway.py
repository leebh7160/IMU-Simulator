import pandas as pd
import numpy as np
import math

print("GPS 경로와 일치하는 철도선 추출")
print("="*50)

# 국가기본도 전체 철도 데이터 로드
df_all = pd.read_csv('data/railway_nodes_national.csv')
print(f"전체 국가기본도 철도 노드: {len(df_all)}")

# GPS 시작점과 끝점
gps_start = (37.502775, 126.881396)
gps_end = (37.551884, 126.970314)
gps_direction = 61.1  # 북동쪽

print(f"GPS 시작점: {gps_start}")
print(f"GPS 끝점: {gps_end}")
print(f"GPS 방향: {gps_direction}도")

# GPS 시작점 근처의 철도 노드들 찾기 (반경 0.01도 = 약 1km)
def distance(lat1, lng1, lat2, lng2):
    return ((lat1-lat2)**2 + (lng1-lng2)**2)**0.5

# GPS 시작점에서 가까운 노드들 찾기
df_all['dist_to_start'] = df_all.apply(lambda row: distance(row['lat'], row['lng'], gps_start[0], gps_start[1]), axis=1)
near_start = df_all[df_all['dist_to_start'] < 0.02].sort_values('dist_to_start')

print(f"\nGPS 시작점 근처 철도 노드 (반경 2km): {len(near_start)}개")
if len(near_start) > 0:
    print("가장 가까운 5개:")
    for i, (idx, row) in enumerate(near_start.head(5).iterrows()):
        print(f"  {i+1}: ({row['lat']:.6f}, {row['lng']:.6f}) - 거리: {row['dist_to_start']:.6f}")

# 각 시작점 후보에서 북동쪽으로 가는 철도선 찾기
def find_railway_line_from_start(start_lat, start_lng, all_nodes, target_direction=61.1, tolerance=30):
    """시작점에서 특정 방향으로 가는 철도선 찾기"""
    current_lat, current_lng = start_lat, start_lng
    line_nodes = [(current_lat, current_lng)]
    used_indices = set()

    for step in range(100):  # 최대 100단계
        # 현재 위치에서 가장 가까운 미사용 노드들 찾기
        remaining = all_nodes[~all_nodes.index.isin(used_indices)]
        remaining['dist'] = remaining.apply(lambda row: distance(row['lat'], row['lng'], current_lat, current_lng), axis=1)
        candidates = remaining[remaining['dist'] < 0.005].sort_values('dist')  # 500m 이내

        if len(candidates) == 0:
            break

        # 각 후보의 방향 확인
        best_candidate = None
        best_score = float('inf')

        for idx, candidate in candidates.head(10).iterrows():
            lat_diff = candidate['lat'] - current_lat
            lng_diff = candidate['lng'] - current_lng

            if abs(lat_diff) < 1e-6 and abs(lng_diff) < 1e-6:
                continue

            angle = math.degrees(math.atan2(lng_diff, lat_diff))
            angle_diff = abs(angle - target_direction)
            if angle_diff > 180:
                angle_diff = 360 - angle_diff

            if angle_diff < tolerance and angle_diff < best_score:
                best_score = angle_diff
                best_candidate = (idx, candidate)

        if best_candidate is None:
            break

        idx, candidate = best_candidate
        used_indices.add(idx)
        current_lat, current_lng = candidate['lat'], candidate['lng']
        line_nodes.append((current_lat, current_lng))

        # GPS 끝점에 가까워지면 성공
        dist_to_end = distance(current_lat, current_lng, gps_end[0], gps_end[1])
        if dist_to_end < 0.01:  # 1km 이내
            print(f"    GPS 끝점에 도달: 거리 {dist_to_end:.6f}")
            break

    return line_nodes

# 가장 유망한 시작점들에서 철도선 추출 시도
best_railway_line = []
best_score = float('inf')

for i, (idx, start_node) in enumerate(near_start.head(3).iterrows()):
    print(f"\n=== 시작점 {i+1}: ({start_node['lat']:.6f}, {start_node['lng']:.6f}) ===")

    railway_line = find_railway_line_from_start(
        start_node['lat'], start_node['lng'],
        df_all, target_direction=61.1, tolerance=45
    )

    print(f"  추출된 노드 수: {len(railway_line)}")

    if len(railway_line) > 10:  # 최소 10개 노드 이상
        # 끝점이 GPS 끝점에 얼마나 가까운지 확인
        end_dist = distance(railway_line[-1][0], railway_line[-1][1], gps_end[0], gps_end[1])
        print(f"  GPS 끝점과의 거리: {end_dist:.6f}")

        if end_dist < best_score:
            best_score = end_dist
            best_railway_line = railway_line
            print(f"  ★ 현재 최적 후보")

# 최적 철도선 저장
if len(best_railway_line) > 0:
    railway_df = pd.DataFrame(best_railway_line, columns=['lat', 'lng'])
    railway_df.to_csv('data/railway_nodes_corrected.csv', index=False)

    print(f"\n=== 최종 결과 ===")
    print(f"추출된 철도 노드 수: {len(railway_df)}")
    print(f"시작점: ({railway_df.iloc[0]['lat']:.6f}, {railway_df.iloc[0]['lng']:.6f})")
    print(f"끝점:   ({railway_df.iloc[-1]['lat']:.6f}, {railway_df.iloc[-1]['lng']:.6f})")

    # 방향성 확인
    lat_diff = railway_df.iloc[-1]['lat'] - railway_df.iloc[0]['lat']
    lng_diff = railway_df.iloc[-1]['lng'] - railway_df.iloc[0]['lng']
    angle = math.degrees(math.atan2(lng_diff, lat_diff))
    print(f"진행 방향: {angle:.1f}도")

    print(f"\nGPS와의 비교:")
    print(f"  방향 차이: {abs(angle - 61.1):.1f}도")
    print(f"  끝점 거리: {best_score:.6f}")

    print(f"\n파일 저장: data/railway_nodes_corrected.csv")
else:
    print("\n적절한 철도선을 찾지 못했습니다!")