# PyInstaller 打包配置：把 Python 后端打成单个可执行文件（server.exe）。
# 用法（在 Windows 上）：  npm run build:backend
# 说明：Mock 模式依赖很轻，能顺利打包。Real 模式含 torch/funasr，
#       体积很大且需额外收集数据文件，建议先打 Mock 版验证流程。
# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

a = Analysis(
    ['server.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=[],
    hiddenimports=[
        'websockets', 'config', 'analysis', 'speaker', 'store',
        'mock_engine',
        # Real 模式如需打包，取消下面注释（体积会很大）：
        # 'real_engine', 'funasr', 'pyaudiowpatch', 'torch', 'torchaudio', 'numpy',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,           # 保留控制台便于看日志；正式版可改 False
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
