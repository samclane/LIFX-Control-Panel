cd .\lifx_control_panel
set PYTHONOPTIMIZE=1 && pyinstaller --onefile --noupx build_all.spec
cd ..