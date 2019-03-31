set PYTHONOPTIMIZE=1 && pyinstaller --onefile build_all.spec
python sign_all.py
