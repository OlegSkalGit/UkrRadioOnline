# -*- mode: python ; coding: utf-8 -*-
import os


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtSql',
        'PyQt6.QtXml',
        'PyQt6.Qt3DCore',
        'PyQt6.Qt3DRender',
        'PyQt6.Qt3DInput',
        'PyQt6.Qt3DLogic',
        'PyQt6.Qt3DExtras',
        'PyQt6.Qt3DAnimation',
        'PyQt6.QtDesigner',
        'PyQt6.QtBluetooth',
        'PyQt6.QtDBus',
        'PyQt6.QtNfc',
        'PyQt6.QtPdf',
        'PyQt6.QtPdfWidgets',
        'PyQt6.QtPositioning',
        'PyQt6.QtPrintSupport',
        'PyQt6.QtQuick',
        'PyQt6.QtQuickWidgets',
        'PyQt6.QtQuick3D',
        'PyQt6.QtRemoteObjects',
        'PyQt6.QtSensors',
        'PyQt6.QtSerialPort',
        'PyQt6.QtSpatialAudio',
        'PyQt6.QtWebChannel',
        'PyQt6.QtWebSockets',
        'PyQt6.QtQml',
        'PyQt6.QtTest',
        'PyQt6.QtCharts',
        'PyQt6.QtDataVisualization',
        'tkinter',
        'sqlite3',
        'unittest',
        'pydoc',
        'distutils'
    ],
    noarchive=False,
    optimize=0,
)

# Filter out unused dynamic libraries (DLLs) and plugins
excluded_binaries = {
    'Qt6Pdf.dll',
    'Qt6PdfQuick.dll',
    'Qt6PdfWidgets.dll',
    'Qt6Qml.dll',
    'Qt6Quick.dll',
    'Qt6Quick3D.dll',
    'Qt6VirtualKeyboard.dll',
    'qpdf.dll',
    'qtga.dll',
    'qicns.dll',
    'qwbmp.dll',
    'qtiff.dll',
    'qwebp.dll',
    'qsvg.dll',
    'Qt6Svg.dll',
    'qsvgicon.dll',
    'opengl32sw.dll',
    'd3dcompiler_47.dll'
}

a.binaries = [x for x in a.binaries if os.path.basename(x[0]).lower() not in {b.lower() for b in excluded_binaries}]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='UkrRadioOnline',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
