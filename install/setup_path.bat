@echo off
echo Setting up MSYS2 MinGW64 path...

REM Add MSYS2 MinGW64 to PATH temporarily for this session
set PATH=C:\msys64\mingw64\bin;C:\msys64\usr\bin;%PATH%

REM Verify gcc is now available
where gcc >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo Error: gcc still not found!
    echo.
    echo Please check if MSYS2 is installed in C:\msys64
    echo If installed in a different location, edit this file to update the path.
    echo.
    echo To permanently add to PATH:
    echo 1. Press Win+X and select "System"
    echo 2. Click "Advanced system settings"
    echo 3. Click "Environment Variables"
    echo 4. Edit PATH and add: C:\msys64\mingw64\bin
    echo.
    pause
    exit /b 1
)

echo GCC found successfully!
gcc --version | findstr gcc
echo.

echo You can now run build.bat to compile the ESKF library.
echo Note: This PATH change is temporary for this command prompt session only.
echo.