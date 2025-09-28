import pandas as pd
import numpy as np

print("GPS 경로 분석")
print("="*50)

# GPS 데이터 로드
df = pd.read_csv('data/data.csv')

# GPS 좌표가 있는 데이터만 필터링
gps_data = df[(df['gps_available'] == True) &
              (df['gps_lat'].notna()) &
              (df['gps_lng'].notna()) &
              (df['gps_lat'] != 0) &
              (df['gps_lng'] != 0)]

print(f"전체 GPS 좌표 수: {len(gps_data)}")

if len(gps_data) > 0:
    # 시작점과 끝점
    start_lat, start_lng = gps_data.iloc[0]['gps_lat'], gps_data.iloc[0]['gps_lng']
    end_lat, end_lng = gps_data.iloc[-1]['gps_lat'], gps_data.iloc[-1]['gps_lng']

    print(f"시작점: ({start_lat:.6f}, {start_lng:.6f})")
    print(f"끝점:   ({end_lat:.6f}, {end_lng:.6f})")

    # 전체 범위
    min_lat, max_lat = gps_data['gps_lat'].min(), gps_data['gps_lat'].max()
    min_lng, max_lng = gps_data['gps_lng'].min(), gps_data['gps_lng'].max()

    print(f"위도 범위: {min_lat:.6f} ~ {max_lat:.6f}")
    print(f"경도 범위: {min_lng:.6f} ~ {max_lng:.6f}")

    # 방향성 분석
    lat_diff = end_lat - start_lat
    lng_diff = end_lng - start_lng

    print(f"\n방향성:")
    print(f"위도 변화: {lat_diff:.6f} ({'북쪽' if lat_diff > 0 else '남쪽'})")
    print(f"경도 변화: {lng_diff:.6f} ({'동쪽' if lng_diff > 0 else '서쪽'})")

    # 각도 계산 (북쪽 기준)
    import math
    angle = math.degrees(math.atan2(lng_diff, lat_diff))
    print(f"진행 방향: {angle:.1f}도 (북쪽 기준)")

    # 샘플 좌표 출력
    print(f"\n첫 10개 GPS 좌표:")
    for i, (idx, row) in enumerate(gps_data.head(10).iterrows()):
        print(f"  {i+1:2d}: ({row['gps_lat']:.6f}, {row['gps_lng']:.6f})")

    print(f"\n마지막 10개 GPS 좌표:")
    for i, (idx, row) in enumerate(gps_data.tail(10).iterrows()):
        print(f"  {i+1:2d}: ({row['gps_lat']:.6f}, {row['gps_lng']:.6f})")

    # CSV로 저장
    gps_coords = gps_data[['gps_lat', 'gps_lng']].rename(columns={'gps_lat': 'lat', 'gps_lng': 'lng'})
    gps_coords.to_csv('data/actual_gps_route.csv', index=False)
    print(f"\n실제 GPS 경로 저장: data/actual_gps_route.csv ({len(gps_coords)}개 좌표)")
else:
    print("GPS 좌표 데이터가 없습니다!")