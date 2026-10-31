# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

block_cipher = None

# Base directories
project_dir = os.path.abspath(SPECPATH)

# Data files to collect
datas = [
    (os.path.join(project_dir, 'index.html'), '.'),
    (os.path.join(project_dir, 'models', 'tiny.en'), os.path.join('models', 'tiny.en')),
]

# Collect sounddevice data (PortAudio binaries)
datas += collect_data_files('_sounddevice_data')
datas += collect_data_files('pywebview')

# Binary dynamic libraries
binaries = []
binaries += collect_dynamic_libs('ctranslate2')
binaries += collect_dynamic_libs('_sounddevice_data')

# Hidden imports required by dynamic dispatch
hiddenimports = [
    'sounddevice',
    '_sounddevice_data',
    'faster_whisper',
    'ctranslate2',
    'keyboard',
    'pyperclip',
    'pywebview',
    'webview.platforms.winforms',
    'webview.platforms.edgechromium',
    'clr_loader',
    'pythonnet',
    'engine_audio',
    'engine_transcription',
    'engine_injector',
    'utils_paths',
]
hiddenimports += collect_submodules('ctranslate2')
hiddenimports += collect_submodules('faster_whisper')

a = Analysis(
    ['main.py'],
    pathex=[project_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'pandas', 'IPython', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OpenFlow',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True, # Console visible for diagnostic purposes during Milestone 1
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='OpenFlow',
)
