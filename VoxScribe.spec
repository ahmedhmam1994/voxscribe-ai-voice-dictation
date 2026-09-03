# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# VoxScribe only uses PySide6.QtCore/QtGui/QtWidgets (see app/main_window.py,
# app/floating_indicator.py, main.py). Deliberately NOT collect_all('PySide6') --
# that bundles the entire framework (WebEngine/Chromium, QML/Quick3D, Designer,
# Charts, Multimedia, Sql, translations for every module...) and was the single
# biggest contributor to distributable size (~640MB of the ~886MB total).
# PyInstaller's own PySide6 hooks pull in exactly what the static imports need;
# the excludes below are a belt-and-suspenders backstop against any hook pulling
# in an unused Qt module transitively.
PYSIDE6_EXCLUDES = [
    'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick',
    'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuick3D', 'PySide6.QtQuickWidgets',
    'PySide6.QtQuickControls2', 'PySide6.QtDesigner', 'PySide6.QtGraphs',
    'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.Qt3DAnimation', 'PySide6.Qt3DExtras',
    'PySide6.Qt3DInput', 'PySide6.Qt3DLogic',
    'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets', 'PySide6.QtPdf', 'PySide6.QtPdfWidgets',
    'PySide6.QtBluetooth', 'PySide6.QtNfc', 'PySide6.QtSensors', 'PySide6.QtPositioning',
    'PySide6.QtLocation', 'PySide6.QtSql', 'PySide6.QtCharts', 'PySide6.QtDataVisualization',
    'PySide6.QtStateMachine', 'PySide6.QtScxml', 'PySide6.QtRemoteObjects',
    'PySide6.QtSerialPort', 'PySide6.QtSerialBus', 'PySide6.QtHelp', 'PySide6.QtNetworkAuth',
    'PySide6.QtTest',
]

# Substrings (path, case-sensitive is fine on Windows paths as PyInstaller emits them)
# identifying binaries/datas that only belong to the excluded modules above, to catch
# anything a hook adds by folder/DLL name rather than as an importable submodule.
_BLOAT_MARKERS = [
    'Qt6WebEngine', 'qtwebengine', 'Qt6Designer', 'Qt6Qml', 'Qt6Quick', 'Qt63D',
    'Qt6Charts', 'Qt6DataVis', 'Qt6Graphs', 'Qt6Multimedia', 'Qt6Pdf',
    'Qt6Bluetooth', 'Qt6Nfc', 'Qt6Sensors', 'Qt6Positioning', 'Qt6Location',
    'Qt6Sql', 'Qt6StateMachine', 'Qt6Scxml', 'Qt6RemoteObjects', 'Qt6SerialPort',
    'Qt6SerialBus', 'Qt6Help', 'Qt6NetworkAuth',
    '\\qml\\', '/qml/', '\\translations\\', '/translations/',
    'opengl32sw.dll', 'libEGL.dll', 'libGLESv2.dll', 'd3dcompiler_47.dll',
    'plugins\\multimedia', 'plugins\\sqldrivers', 'plugins\\sensors',
    'plugins\\position', 'plugins\\geoservices', 'plugins\\qmltooling',
    'plugins\\webengine', 'resources\\qtwebengine',
]

def _strip_bloat(entries):
    return [e for e in entries if not any(m in e[0] for m in _BLOAT_MARKERS)]

datas = [('app/icon.ico', 'app')]
binaries = []
hiddenimports = ['sounddevice']
tmp_ret = collect_all('keyboard')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('faster_whisper')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('ctranslate2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('onnxruntime')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('av')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('tokenizers')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('huggingface_hub')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=PYSIDE6_EXCLUDES,
    noarchive=False,
    optimize=0,
)
a.binaries = _strip_bloat(a.binaries)
a.datas = _strip_bloat(a.datas)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VoxScribe',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX packing tripped Windows Defender's heuristics (flagged the exe as
    # Trojan:Win32/Bearfoos.A!ml and silently quarantined it post-install --
    # a well-documented false-positive pattern for UPX-packed PyInstaller
    # builds, since real malware also uses UPX to evade detection). Not
    # worth the smaller installer size for an app that hooks the keyboard,
    # which already reads as suspicious to AV heuristics on its own.
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app/icon.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='VoxScribe',
)
