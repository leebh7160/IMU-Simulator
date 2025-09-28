import pandas as pd
import numpy as np
import math

print("기존 철도 데이터 방향성 분석")
print("="*50)

# 기존 철도 데이터 로드
df = pd.read_csv('data/railway_nodes_old.csv')

print(f"기존 철도 노드 수: {len(df)}")

# 시작점과 끝점
start_lat, start_lng = df.iloc[0]['lat'], df.iloc[0]['lng']
end_lat, end_lng = df.iloc[-1]['lat'], df.iloc[-1]['lng']

print(f"시작점: ({start_lat:.6f}, {start_lng:.6f})")
print(f"끝점:   ({end_lat:.6f}, {end_lng:.6f})")

# 전체 범위
min_lat, max_lat = df['lat'].min(), df['lat'].max()
min_lng, max_lng = df['lng'].min(), df['lng'].max()

print(f"위도 범위: {min_lat:.6f} ~ {max_lat:.6f}")
print(f"경도 범위: {min_lng:.6f} ~ {max_lng:.6f}")

# 방향성 분석
lat_diff = end_lat - start_lat
lng_diff = end_lng - start_lng

print(f"\n방향성:")
print(f"위도 변화: {lat_diff:.6f} ({'북쪽' if lat_diff > 0 else '남쪽'})")
print(f"경도 변화: {lng_diff:.6f} ({'동쪽' if lng_diff > 0 else '서쪽'})")

# 각도 계산 (북쪽 기준)
angle = math.degrees(math.atan2(lng_diff, lat_diff))
print(f"진행 방향: {angle:.1f}도 (북쪽 기준)")

print(f"\n=== GPS 경로와 비교 ===")
print("GPS 경로:")
print("  시작: (37.502775, 126.881396)")
print("  끝:   (37.551884, 126.970314)")
print("  방향: 61.1도 (북동쪽)")

print(f"\n기존 철도 경로:")
print(f"  시작: ({start_lat:.6f}, {start_lng:.6f})")
print(f"  끝:   ({end_lat:.6f}, {end_lng:.6f})")
print(f"  방향: {angle:.1f}도")

# 비교 분석
print(f"\n=== 패턴 매칭 분석 ===")
if abs(angle - 61.1) < 30:  # 30도 이내
    print("✓ 방향성 매칭: 유사함")
else:
    print("✗ 방향성 매칭: 다름")

# GPS 시작점과의 거리 계산
def distance(lat1, lng1, lat2, lng2):
    return ((lat1-lat2)**2 + (lng1-lng2)**2)**0.5

dist_to_gps_start = distance(start_lat, start_lng, 37.502775, 126.881396)
dist_to_gps_end = distance(end_lat, end_lng, 37.551884, 126.970314)

print(f"GPS 시작점과의 거리: {dist_to_gps_start:.6f}")
print(f"GPS 끝점과의 거리: {dist_to_gps_end:.6f}")

# 첫 10개, 마지막 10개 출력
print(f"\n첫 10개 철도 노드:")
for i, (idx, row) in enumerate(df.head(10).iterrows()):
    print(f"  {i+1:2d}: ({row['lat']:.6f}, {row['lng']:.6f})")

print(f"\n마지막 10개 철도 노드:")
for i, (idx, row) in enumerate(df.tail(10).iterrows()):
    print(f"  {i+1:2d}: ({row['lat']:.6f}, {row['lng']:.6f})")