import pandas as pd
import numpy as np
import math

print("철도선과 GPS 경로 매칭 검증")
print("="*50)

# 데이터 로드
railway_df = pd.read_csv('data/railway_nodes_corrected.csv')
gps_df = pd.read_csv('data/actual_gps_route.csv')

print(f"추출된 철도 노드: {len(railway_df)}개")
print(f"실제 GPS 좌표: {len(gps_df)}개")

# 거리 계산 함수
def distance(lat1, lng1, lat2, lng2):
    return ((lat1-lat2)**2 + (lng1-lng2)**2)**0.5

# 방향 계산 함수
def calculate_direction(lat1, lng1, lat2, lng2):
    lat_diff = lat2 - lat1
    lng_diff = lng2 - lng1
    return math.degrees(math.atan2(lng_diff, lat_diff))

# 철도선 방향성 확인
railway_direction = calculate_direction(
    railway_df.iloc[0]['lat'], railway_df.iloc[0]['lng'],
    railway_df.iloc[-1]['lat'], railway_df.iloc[-1]['lng']
)

# GPS 경로 방향성 확인
gps_direction = calculate_direction(
    gps_df.iloc[0]['lat'], gps_df.iloc[0]['lng'],
    gps_df.iloc[-1]['lat'], gps_df.iloc[-1]['lng']
)

print(f"\n=== 방향성 비교 ===")
print(f"철도선 방향: {railway_direction:.1f}도")
print(f"GPS 경로 방향: {gps_direction:.1f}도")
print(f"방향 차이: {abs(railway_direction - gps_direction):.1f}도")

# 시작점과 끝점 비교
railway_start = (railway_df.iloc[0]['lat'], railway_df.iloc[0]['lng'])
railway_end = (railway_df.iloc[-1]['lat'], railway_df.iloc[-1]['lng'])
gps_start = (gps_df.iloc[0]['lat'], gps_df.iloc[0]['lng'])
gps_end = (gps_df.iloc[-1]['lat'], gps_df.iloc[-1]['lng'])

start_distance = distance(*railway_start, *gps_start)
end_distance = distance(*railway_end, *gps_end)

print(f"\n=== 위치 비교 ===")
print(f"철도 시작점: ({railway_start[0]:.6f}, {railway_start[1]:.6f})")
print(f"GPS 시작점:  ({gps_start[0]:.6f}, {gps_start[1]:.6f})")
print(f"시작점 거리: {start_distance:.6f}")

print(f"\n철도 끝점:   ({railway_end[0]:.6f}, {railway_end[1]:.6f})")
print(f"GPS 끝점:    ({gps_end[0]:.6f}, {gps_end[1]:.6f})")
print(f"끝점 거리:   {end_distance:.6f}")

# GPS 경로와 철도선의 평균 거리 계산
total_distances = []
for _, gps_point in gps_df.iterrows():
    min_dist = float('inf')
    for _, railway_point in railway_df.iterrows():
        dist = distance(gps_point['lat'], gps_point['lng'],
                       railway_point['lat'], railway_point['lng'])
        min_dist = min(min_dist, dist)
    total_distances.append(min_dist)

avg_distance = np.mean(total_distances)
max_distance = np.max(total_distances)

print(f"\n=== 거리 분석 ===")
print(f"GPS-철도간 평균 거리: {avg_distance:.6f}")
print(f"GPS-철도간 최대 거리: {max_distance:.6f}")

# 커버리지 분석 (철도선이 GPS 경로를 얼마나 잘 커버하는지)
covered_points = sum(1 for dist in total_distances if dist < 0.01)  # 1km 이내
coverage_ratio = covered_points / len(gps_df) * 100

print(f"1km 이내 커버된 GPS 점: {covered_points}/{len(gps_df)} ({coverage_ratio:.1f}%)")

# 매칭 품질 평가
print(f"\n=== 매칭 품질 평가 ===")

if abs(railway_direction - gps_direction) < 20:
    print("✓ 방향성: 우수 (20도 이내)")
elif abs(railway_direction - gps_direction) < 45:
    print("△ 방향성: 보통 (45도 이내)")
else:
    print("✗ 방향성: 불량 (45도 초과)")

if start_distance < 0.01:
    print("✓ 시작점: 우수 (1km 이내)")
elif start_distance < 0.02:
    print("△ 시작점: 보통 (2km 이내)")
else:
    print("✗ 시작점: 불량 (2km 초과)")

if end_distance < 0.05:
    print("✓ 끝점: 우수 (5km 이내)")
elif end_distance < 0.1:
    print("△ 끝점: 보통 (10km 이내)")
else:
    print("✗ 끝점: 불량 (10km 초과)")

if coverage_ratio > 80:
    print("✓ 커버리지: 우수 (80% 이상)")
elif coverage_ratio > 60:
    print("△ 커버리지: 보통 (60% 이상)")
else:
    print("✗ 커버리지: 불량 (60% 미만)")

# 개선 제안
print(f"\n=== 개선 제안 ===")
if end_distance > 0.02:
    print("- 철도선이 GPS 끝점에 도달하지 못함. 더 긴 경로 추출 필요")
if coverage_ratio < 70:
    print("- GPS 경로 커버리지 부족. 더 정밀한 철도선 추출 필요")
if abs(railway_direction - gps_direction) > 15:
    print("- 방향성 차이 있음. 경로 추출 알고리즘 조정 필요")

print(f"\n전체 매칭 점수: {(100 - abs(railway_direction - gps_direction)*2 + coverage_ratio)/2:.1f}/100")