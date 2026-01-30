# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['syft_space/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('syft_space/alembic.ini', 'syft_space'),
        ('syft_space/alembic', 'syft_space/alembic'),
        ('syft_space/components/dataset_types/weaviate_local/docker-compose.yml',
        'syft_space/components/dataset_types/weaviate_local'),
    ],
    hiddenimports=['aiosqlite'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='syft-space',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
