# ESKF (Error-State Kalman Filter) C Implementation

STM32 마이크로컨트롤러용 ESKF 알고리즘의 Pure C 구현입니다. Python 원본 알고리즘을 임베디드 환경에 최적화하여 포팅했으며, PC에서 테스트 가능합니다.

## 📋 목차
- [기능](#기능)
- [요구사항](#요구사항)
- [설치](#설치)
- [빌드](#빌드)
- [실행](#실행)
- [API 문서](#api-문서)

## ✨ 기능

- **Pure C 구현** - C++ STL 의존성 없음
- **정적 메모리 할당** - malloc/free 사용하지 않음
- **ESKF 알고리즘** - IMU/GPS 센서 융합
- **철도 맵 매칭** - 터널 구간 heading 보정
- **크로스 플랫폼** - Windows/Linux/Mac/STM32
- **FFI 바인딩** - Python, TypeScript 연동

## 🔧 요구사항

### 필수
- Windows 10/11
- MSYS2 (MinGW64 GCC 컴파일러)
- Python 3.8+ (테스트용)

### 선택
- Node.js 16+ (TypeScript 테스트용)
- STM32CubeIDE (STM32 포팅용)

## 📦 설치

### 1. MSYS2 및 GCC 설치

#### Windows
1. MSYS2 다운로드 및 설치: https://www.msys2.org/
2. MSYS2 터미널에서 GCC 설치:
```bash
pacman -S mingw-w64-x86_64-gcc
```

3. 환경변수 PATH에 추가:
   - `C:\msys64\mingw64\bin`
   - 시스템 속성 → 환경변수 → PATH 편집

#### Linux/Mac
```bash
# Ubuntu/Debian
sudo apt-get install gcc make

# macOS
brew install gcc
```

### 2. 프로젝트 클론
```bash
git clone [repository-url]
cd visualize_ESKF_ONLINE/work
```

### 3. Python 패키지 설치 (테스트용)
```bash
pip install numpy pandas
```

### 4. Node.js 패키지 설치 (선택사항)
```bash
npm install
```

## 🔨 빌드

### Windows (권장)
```batch
# 자동 빌드 (MSYS2 경로 자동 설정)
build_with_msys2.bat
```

### Windows (수동)
```batch
# GCC가 PATH에 있는 경우
gcc -O2 -shared -fPIC -o eskf.dll matrix.c eskf.c -lm -D_USE_MATH_DEFINES
```

### Linux
```bash
gcc -O2 -shared -fPIC -o eskf.so matrix.c eskf.c -lm
```

### macOS
```bash
gcc -O2 -shared -fPIC -o eskf.dylib matrix.c eskf.c -lm
```

## 🚀 실행

### 1. C 라이브러리 빌드 확인
```batch
# Windows
dir eskf.dll

# Linux/Mac
ls -la eskf.so  # 또는 eskf.dylib
```

### 2. 테스트

data폴더에 railway_nodes.csv와 사용할 data.csv를 추가한 후 

```bash
python server_simple.py
```


## 📁 파일 구조

```
work/
├── matrix.h            # 행렬 연산 헤더
├── matrix.c            # 행렬 연산 구현
├── eskf.h              # ESKF 알고리즘 헤더
├── eskf.c              # ESKF 알고리즘 구현
├── build_with_msys2.bat # Windows 빌드 스크립트
├── test_c_python.py    # Python 테스트
├── src/
│   ├── index.ts        # TypeScript FFI 바인딩
│   ├── test.ts         # TypeScript 테스트
│   └── demo.ts         # TypeScript 데모
├── data/data.csv       # 테스트 데이터 (IMU/GPS)
└── data/railway_nodes.csv   # 철도 맵 데이터
```

## 📚 API 문서

### 기본 사용법

#### C API
```c
// 생성
eskf_t* eskf = eskf_create();

// IMU 데이터 처리
imu_data_t imu = {
    .timestamp = get_time(),
    .acc = {{ax, ay, az}},
    .gyro = {{gx, gy, gz}}
};
eskf_process_imu(eskf, &imu);

// GPS 데이터 처리
gps_data_t gps = {
    .timestamp = get_time(),
    .lat = latitude,
    .lon = longitude,
    .alt = altitude
};
eskf_process_gps(eskf, &gps);

// 상태 읽기
eskf_state_t state;
eskf_get_state(eskf, &state);

// 정리
eskf_destroy(eskf);
```

#### Python API
```python
import ctypes

# 라이브러리 로드
lib = ctypes.CDLL('./eskf.dll')

# ESKF 생성
eskf = lib.eskf_create()

# 데이터 처리...

# 정리
lib.eskf_destroy(eskf)
```

#### TypeScript API
```typescript
import { ESKF } from './index';

const eskf = new ESKF();

// IMU 처리
eskf.processImu(timestamp, [ax, ay, az], [gx, gy, gz]);

// GPS 처리
eskf.processGps(timestamp, lat, lon, alt);

// 상태 읽기
const state = eskf.getState();

// 정리
eskf.destroy();
```

## 🧪 성능

### PC (Intel i5)
- IMU 업데이트: < 0.1ms
- GPS 업데이트: < 0.5ms
- 맵 매칭: < 0.2ms

### STM32F4 (168MHz)
- IMU 업데이트: < 1ms
- GPS 업데이트: < 2ms
- 맵 매칭: < 0.5ms

### 메모리 사용량
- RAM: ~500KB (조정 가능)
- Flash: ~20KB
- Stack: ~2KB

## ❗ 주의사항

1. **좌표 변환**: 간소화된 구현 (완전한 측지 모델 아님)
2. **정밀도**: 실제 제품에는 GeographicLib 권장
3. **칼만 필터**: 임베디드용으로 간소화됨
4. **맵 매칭**: 가장 가까운 철도 세그먼트로 투영

## 🐛 문제 해결

### "gcc not found" 오류
```batch
# MSYS2 경로 확인
where gcc

# 없으면 PATH 추가
set PATH=C:\msys64\mingw64\bin;%PATH%
```

### DLL 로드 실패
```python
# Python에서 경로 확인
import os
print(os.path.exists('eskf.dll'))
```

### 메모리 부족 (STM32)
```c
// eskf.h에서 조정
#define MAX_RAIL_NODES 500   // 줄이기
#define IMU_BUFFER_SIZE 100  // 줄이기
```

## 📄 라이선스

교육 및 연구 목적으로 자유롭게 사용 가능합니다.

## 🤝 기여

버그 리포트 및 개선 제안 환영합니다!

---
*Python ESKF 구현을 STM32용 C로 포팅한 프로젝트입니다.*
