@echo off
echo Building Repairs Dashboard executable...

REM Check if PyInstaller is installed
pip show pyinstaller > nul 2>&1
if %errorlevel% neq 0 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    if %errorlevel% neq 0 (
        echo Failed to install PyInstaller. Please install it manually.
        pause
        exit /b 1
    )
)

REM Run the setup script
python setup.py
if %errorlevel% neq 0 (
    echo Build failed. See error messages above.
    pause
    exit /b 1
)

echo.
echo Build completed successfully!
echo The executable can be found in the dist folder.
echo.
pause