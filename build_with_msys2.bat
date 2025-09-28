@echo off
echo ESKF Library Build Script for MSYS2 MinGW64
echo =============================================
echo.

REM Temporarily add MSYS2 to PATH
set PATH=C:\msys64\mingw64\bin;C:\msys64\usr\bin;%PATH%

REM Check if gcc is available
gcc --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] gcc not found!
    echo.
    echo Please ensure MSYS2 is installed and gcc is available:
    echo   1. Install MSYS2 from https://www.msys2.org/
    echo   2. Run: pacman -S mingw-w64-x86_64-gcc
    echo.
    echo If MSYS2 is installed elsewhere, edit the PATH in this script.
    echo.
    pause
    exit /b 1
)

echo [OK] Found GCC:
gcc --version | findstr gcc
echo.

echo [1/3] Cleaning old files...
del /Q eskf.dll 2>nul
del /Q *.o 2>nul
del /Q libeskf.a 2>nul

echo [2/3] Building ESKF shared library (DLL)...
gcc -O2 -shared -fPIC -o eskf.dll matrix.c eskf.c -lm -D_USE_MATH_DEFINES -Wall

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo [OK] Successfully created eskf.dll
echo.

echo [3/3] Building static library (for STM32 reference)...
gcc -O2 -c matrix.c -o matrix.o -D_USE_MATH_DEFINES -Wall
gcc -O2 -c eskf.c -o eskf.o -D_USE_MATH_DEFINES -Wall
ar rcs libeskf.a matrix.o eskf.o

if %errorlevel% == 0 (
    echo [OK] Successfully created libeskf.a
    del /Q *.o 2>nul
) else (
    echo [WARNING] Static library build failed (DLL is still OK)
)

echo.
echo =============================================
echo Build Complete!
echo =============================================
echo.
echo Generated files:
echo   - eskf.dll    : Dynamic library for Windows
echo   - libeskf.a   : Static library for embedded
echo.
echo Next steps:
echo   1. Test with Python:
echo      python test_c_python.py
echo.
echo   2. Test with TypeScript:
echo      npm install
echo      npm test
echo.
echo   3. For STM32:
echo      Copy matrix.h, matrix.c, eskf.h, eskf.c to your project
echo.
pause