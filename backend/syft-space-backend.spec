# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata

# Packages that are lazily/conditionally imported in syft_space code and thus
# invisible to PyInstaller's static analysis. When adding a new lazy import,
# add the top-level package name here.
LAZY_IMPORTS = [
    'chromadb',
    'weaviate',
    'openai',
    'opentelemetry',
    'docling',
    'docling_core',
    'docling_ibm_models',
    'docling_parse',
]

# Packages that bundle data files (migrations, configs, etc.) needed at runtime.
PACKAGES_WITH_DATA = [
    'chromadb',
    'docling',
    'docling_core',
    'docling_ibm_models',
    'docling_parse',
]

# Packages that use importlib.metadata at runtime (need their dist-info).
# collect_data_files only gets files *inside* the package directory;
# copy_metadata gets the .dist-info directory from site-packages.
PACKAGES_WITH_METADATA = [
    'docling',
    'docling_core',
    'docling_ibm_models',
    'docling_parse',
]

# Packages with native extensions that PyInstaller may not auto-detect.
PACKAGES_WITH_BINARIES = [
    'chromadb',
    'chromadb_rust_bindings',
    'docling_parse',
]

a = Analysis(
    ['syft_space/__main__.py'],
    pathex=[],
    binaries=[
        lib for pkg in PACKAGES_WITH_BINARIES
        for lib in collect_dynamic_libs(pkg)
    ],
    datas=[
        ('syft_space/alembic.ini', 'syft_space'),
        ('syft_space/alembic', 'syft_space/alembic'),
        *(data for pkg in PACKAGES_WITH_DATA for data in collect_data_files(pkg)),
        *(meta for pkg in PACKAGES_WITH_METADATA for meta in copy_metadata(pkg)),
    ],
    hiddenimports=[
        'aiosqlite',
        *collect_submodules('syft_space'),
        *(mod for pkg in LAZY_IMPORTS for mod in collect_submodules(pkg)),
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

import sys

_is_win = sys.platform == 'win32'

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='syft-space-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=not _is_win,
    upx=not _is_win,
    upx_exclude=[],
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=not _is_win,
    upx=not _is_win,
    upx_exclude=[],
    name='syft-space-backend',
)
