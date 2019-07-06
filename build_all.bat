set PYTHONOPTIMIZE=1 && pyinstaller --onefile --noupx build_all.spec
python sign_all.py
