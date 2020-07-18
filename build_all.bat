cd .\lifx_control_panel
set PYTHONOPTIMIZE=1 && ..\venv\Scripts\pyinstaller.exe --onefile --noupx build_all.spec
cd ..