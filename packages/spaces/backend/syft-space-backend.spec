# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

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
    'mpp',
    'spacy',
    'en_core_web_sm',
]

# Packages that bundle data files (migrations, configs, etc.) needed at runtime.
PACKAGES_WITH_DATA = [
    'chromadb',
    'docling',
    'docling_core',
    'docling_ibm_models',
    'docling_parse',
    'rapidocr',
    'spacy',
    'en_core_web_sm',
]

# Packages that use importlib.metadata at runtime (need their dist-info).
# collect_data_files only gets files *inside* the package directory;
# copy_metadata gets the .dist-info directory from site-packages.
PACKAGES_WITH_METADATA = [
    # py_ecc reads its own version at import time, reached via
    # payments.mpp -> web3 -> eth_account -> eth_keyfile.
    'py_ecc',
    'docling',
    'docling_slim',
    'docling_core',
    'docling_ibm_models',
    'docling_parse',
    'spacy',
    'thinc',
    'srsly',
    'en_core_web_sm',
]

# Packages with native extensions that PyInstaller may not auto-detect.
PACKAGES_WITH_BINARIES = [
    'chromadb',
    'chromadb_rust_bindings',
    'docling_parse',
    'torch',
    'torchvision',
]

def _flatten_license_trees(datas):
    """Fold each dist-info's nested licence tree into one file.

    torch vendors licences up to 15 directories deep, which puts two of them
    past Windows' 260-character path limit once NSIS stages the bundle and
    aborts the installer. Every notice is kept, prefixed with the path it came
    from, so attribution survives the flattening. Licence files sitting
    directly in ``licenses/`` are left alone.
    """
    nested: dict[str, list[tuple[str, str]]] = {}
    kept = []
    for entry in datas:
        dest, source = entry[0], entry[1]
        parts = dest.replace("\\", "/").split("/")
        # <name>.dist-info/licenses/<subdir>/.../<file>
        if (
            len(parts) > 3
            and parts[0].endswith(".dist-info")
            and parts[1] == "licenses"
        ):
            nested.setdefault(parts[0], []).append(("/".join(parts[2:]), source))
        else:
            kept.append(entry)

    for dist_info, files in nested.items():
        combined = []
        for relative, source in sorted(files):
            combined.append("=" * 72)
            combined.append(relative)
            combined.append("=" * 72)
            combined.append(Path(source).read_text(encoding="utf-8", errors="replace"))
            combined.append("")
        out = Path(workpath) / dist_info / "THIRD_PARTY_NOTICES.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(combined), encoding="utf-8")
        kept.append(
            (f"{dist_info}/licenses/THIRD_PARTY_NOTICES.txt", str(out), "DATA")
        )
        print(f"[spec] flattened {len(files)} licence files in {dist_info}")

    return kept


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
a.datas = _flatten_license_trees(a.datas)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='syft-space-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    console=False,
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
    strip=False,
    upx=False,
    upx_exclude=[],
    name='syft-space-backend',
)
