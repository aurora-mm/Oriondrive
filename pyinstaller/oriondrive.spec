# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the native Oriondrive macOS app bundle."""

from pathlib import Path


project_root = Path(SPECPATH).parent
# Rebuild with `python assets/make_icon.py` after editing the icon script.
ICON = project_root / "assets" / "Oriondrive.icns"
ICON_PATH = str(ICON) if ICON.exists() else None

INFO_PLIST = {
    "CFBundleName": "Oriondrive",
    "CFBundleDisplayName": "Oriondrive",
    "CFBundleIdentifier": "app.oriondrive.desktop",
    "CFBundleShortVersionString": "0.4.0",
    "CFBundleVersion": "0.4.0",
    "NSHighResolutionCapable": True,
    "NSRequiresAquaSystemAppearance": False,
    "LSMinimumSystemVersion": "11.0",
    "LSApplicationCategoryType": "public.app-category.music",
    "NSHumanReadableCopyright": "Oriondrive",
    "CFBundleIconFile": "Oriondrive.icns",
    "CFBundleDocumentTypes": [
        {
            "CFBundleTypeName": "Oriondrive Project",
            "CFBundleTypeExtensions": ["ori"],
            "CFBundleTypeRole": "Editor",
            "LSHandlerRank": "Owner",
            "LSItemContentTypes": ["app.oriondrive.project"],
        }
    ],
    "UTExportedTypeDeclarations": [
        {
            "UTTypeIdentifier": "app.oriondrive.project",
            "UTTypeDescription": "Oriondrive Project",
            "UTTypeConformsTo": ["public.json", "public.text"],
            "UTTypeTagSpecification": {"public.filename-extension": ["ori"]},
        }
    ],
}

a = Analysis(
    [str(project_root / "main_gui.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "examples"), "examples"),
        (str(project_root / "assets" / "Oriondrive.icns"), "assets"),
    ],
    hiddenimports=[
        "objc",
        "AppKit",
        "Foundation",
        "PyObjCTools.AppHelper",
        "UniformTypeIdentifiers",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Oriondrive",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
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
    name="Oriondrive",
)

app = BUNDLE(
    coll,
    name="Oriondrive.app",
    icon=ICON_PATH,
    bundle_identifier="app.oriondrive.desktop",
    info_plist=INFO_PLIST,
)
