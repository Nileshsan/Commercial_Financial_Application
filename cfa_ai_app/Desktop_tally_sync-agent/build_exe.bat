@echo off
echo Building CFA Tally Sync Agent EXE...

pyinstaller --clean --onefile --noconsole ^
--hidden-import=xmltodict ^
--hidden-import=dotenv ^
--hidden-import=requests ^
--hidden-import=cv2 ^
--hidden-import=PIL ^
--hidden-import=PIL.Image ^
--hidden-import=PIL.ImageTk ^
--add-data "config.env;." ^
--add-data "build_output\appicon.ico;." ^
--icon="build_output\appicon.ico" ^
--name "CFA_Tally_Sync_Agent" ^
--distpath ./build_output ^
--log-level=INFO main.py

echo.
echo ✅ Build Completed. Check the build_output folder.
pause
