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
    (os.path.join(project_dir, 'models', 'shruti-hi'), os.path.join('models', 'shruti-hi')),
]

# Collect package data
datas += collect_data_files('_sounddevice_data')
datas += collect_data_files('webview')
datas += collect_data_files('onnxruntime')

# Explicitly ensure all pywebview / Edge WebView2 interop libraries and platform runtimes are packaged
import webview
webview_base = os.path.dirname(webview.__file__)
webview_lib = os.path.join(webview_base, 'lib')
if os.path.exists(webview_lib):
    datas.append((webview_lib, os.path.join('webview', 'lib')))
    runtimes_dir = os.path.join(webview_lib, 'runtimes')
    if os.path.exists(runtimes_dir):
        for arch in os.listdir(runtimes_dir):
            arch_native = os.path.join(runtimes_dir, arch, 'native')
            if os.path.exists(arch_native):
                datas.append((arch_native, arch))
                datas.append((arch_native, os.path.join('runtimes', arch, 'native')))
                datas.append((arch_native, os.path.join('webview', 'lib', 'runtimes', arch, 'native')))

# Binary dynamic libraries
binaries = []
binaries += collect_dynamic_libs('ctranslate2')
binaries += collect_dynamic_libs('_sounddevice_data')
binaries += collect_dynamic_libs('onnxruntime')
binaries += collect_dynamic_libs('webview')

# Hidden imports required by dynamic dispatch
hiddenimports = [
    'sounddevice',
    '_sounddevice_data',
    'faster_whisper',
    'ctranslate2',
    'onnxruntime',
    'keyboard',
    'pyperclip',
    'pywebview',
    'webview.platforms.winforms',
    'webview.platforms.edgechromium',
    'clr_loader',
    'pythonnet',
    'engine_audio',
    'engine_transcription',
    'engine_shruti',
    'engine_transliterate',
    'engine_corrections',
    'engine_injector',
    'language_config',
    'ui_overlay',
    'utils_paths',
    'utils_logger',
    'utils_single_instance',
    'engine_hotkey',
]
hiddenimports += collect_submodules('ctranslate2')
hiddenimports += collect_submodules('faster_whisper')
hiddenimports += collect_submodules('onnxruntime')

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
    console=False, # Windowed desktop app
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
