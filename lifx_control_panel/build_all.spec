# -*- mode: python -*-
import datetime

bd = datetime.datetime.now().isoformat()
auth = "Sawyer McLane"
vers = "1.8.0"
is_debug = False

# Write version info into _constants.py resource file
with open('_constants.py', 'w') as f:
    f.write("VERSION = \"{}\"\n".format(vers))
    f.write("BUILD_DATE = \"{}\"\n".format(bd))
    f.write("AUTHOR = \"{}\"\n".format(auth))
    f.write("DEBUGGING = {}".format(str(is_debug)))

block_cipher = None

a = Analysis(
    ['__main__.pyw', 'utilities//color_thread.py', 'utilities//audio.py', 'ui//settings.py', 'ui//SysTrayIcon.py',
              'utilities//utils.py', '_constants.py', 'ui//splashscreen.py'],
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

a.datas += [('res//splash_vector.png', '../res/splash_vector.png', 'Data')]
a.datas += [('res//icon_vector.ico', '../res/icon_vector.ico', 'Data')]
a.datas += [('res//lightbulb.png', '../res/lightbulb.png', 'Data')]
a.datas += [('res//group.png', '../res/group.png', 'Data')]
a.datas += [('default.ini', '../default.ini', '.')]

pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)

################################################################################
# Main
################################################################################

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='lifx_control_panel',
          debug=False,
          strip=False,
          upx=False,
          runtime_tmpdir=None,
          console=is_debug,
          icon='../res/icon_vector.ico')

################################################################################
# Debug
################################################################################

is_debug = True

# Write version info into _constants.py resource file
with open('_constants.py', 'w') as f:
    f.write("VERSION = \"{}\"\n".format(vers))
    f.write("BUILD_DATE = \"{}\"\n".format(bd))
    f.write("AUTHOR = \"{}\"\n".format(auth))
    f.write("DEBUGGING = {}".format(str(is_debug)))

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='lifx_control_panel-debug',
          debug=False,
          strip=False,
          upx=False,
          runtime_tmpdir=None,
          console=is_debug,
          icon='../res/icon_vector.ico')

################################################################################
# Demo
################################################################################


a = Analysis(
    ['tests//dummy_devices.py', '__main__.pyw', 'utilities//color_thread.py', 'utilities//audio.py', 'ui//settings.py',
     'ui//SysTrayIcon.py', 'utilities//utils.py', '_constants.py', 'ui//splashscreen.py'],
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

a.datas += [('res//splash_vector.png', '../res/splash_vector.png', 'Data')]
a.datas += [('res//icon_vector.ico', '../res/icon_vector.ico', 'Data')]
a.datas += [('res//lightbulb.png', '../res/lightbulb.png', 'Data')]
a.datas += [('res//group.png', '../res/group.png', 'Data')]
a.datas += [('default.ini', '../default.ini', '.')]

pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='lifx_control_panel-demo',
          debug=False,
          strip=False,
          upx=False,
          runtime_tmpdir=None,
          console=is_debug,
          icon='../res/icon_vector.ico')

# Set debugging back to false
with open('_constants.py', 'w') as f:
    f.write("VERSION = \"{}\"\n".format(vers))
    f.write("BUILD_DATE = \"{}\"\n".format(bd))
    f.write("AUTHOR = \"{}\"\n".format(auth))
    f.write("DEBUGGING = {}".format(str(False)))
