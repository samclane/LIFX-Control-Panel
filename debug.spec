# -*- mode: python -*-
import datetime

bd = datetime.datetime.now().isoformat()
auth = "Sawyer McLane"
vers = "1.6.1"
is_debug = True

# Write version info into _constants.py resource file
with open('_constants.py', 'w') as f:
    f.write("VERSION = \"{}\"\n".format(vers))
    f.write("BUILD_DATE = \"{}\"\n".format(bd))
    f.write("AUTHOR = \"{}\"\n".format(auth))
    f.write("DEBUGGING = {}".format(str(is_debug)))

# Write version info into default config file
with open('default.ini', 'r') as f:
    initdata = f.readlines()
initdata[-1] = "builddate = {}\n".format(bd)
initdata[-2] = "author = {}\n".format(auth)
initdata[-3] = "version = {}\n".format(vers)
with open('default.ini', 'w') as f:
    f.writelines(initdata)


block_cipher = None


a = Analysis(['gui.pyw', 'utilities//color_thread.py', 'utilities//audio.py', 'ui//settings.py', 'ui//SysTrayIcon.py', 'utilities//utils.py', '_constants.py', 'ui//splashscreen.py'],
             pathex=['\\.'],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)

for d in a.datas:
    if 'pyconfig' in d[0]:
        a.datas.remove(d)
        break

a.datas += [('res//splash_vector_png.png', 'res/splash_vector_png.png', 'Data')]
a.datas += [('res//icon_vector_9fv_icon.ico', 'res/icon_vector_9fv_icon.ico', 'Data')]
a.datas += [('res//lightbulb.png', 'res/lightbulb.png', 'Data')]
a.datas += [('res//group.png', 'res/group.png', 'Data')]
a.datas += [('default.ini', 'default.ini', '.')]

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='LIFX-Control-Panel-debug',
          debug=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=is_debug,
          icon='icons//icon_vector_9fv_icon.ico')
