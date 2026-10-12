# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — ListersForm 自動送信ツール（是正版）
# ビルド: pyinstaller build.spec   → 生成物: dist/ListersForm.exe（onefile・GUI）
# ChromeDriver は実行時に Selenium Manager / webdriver-manager が解決します。

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [("app/listersform_settings.template.json", ".")]
binaries = []
hiddenimports = []

# GUI（customtkinter）とテーマ判定（darkdetect）は data/アセットを同梱しないと起動時に失敗する
for pkg in ("customtkinter", "darkdetect"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

hiddenimports += collect_submodules("selenium")
hiddenimports += collect_submodules("webdriver_manager")
hiddenimports += ["openpyxl", "bs4", "requests", "tkinter"]

a = Analysis(
    ["app/main_gui.py"],
    pathex=["app"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ListersForm",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # GUIアプリ（コンソール非表示）
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
