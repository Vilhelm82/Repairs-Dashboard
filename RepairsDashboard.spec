# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('images', 'images'), ('AutoSequenceRepo', 'AutoSequenceRepo'), ('search_regions.json', '.'), ('user_assets.json', '.'), ('requirements.txt', '.')],
    hiddenimports=['PIL._tkinter_finder', 'skimage.metrics.structural_similarity', 'utils.automation_helpers', 'utils.debug_ui_widgets', 'core.db', 'ui_tabs.calendar_tab', 'ui_tabs.importer_tab', 'ui_tabs.job_card_manager_tab', 'ui_tabs.job_indexer_tab', 'ui_tabs.tag_manager_tab', 'ui_tabs.batch_tasker_tab', 'ui_tabs.job_card_instance', 'ui_tabs.overview_tab', 'ui_tabs.milwaukee_warranties_tab', 'services.aden_controller', 'services.aden_automation'],
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
    name='RepairsDashboard',
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
    icon=['images\\job_card_loaded_cue.png'],
)
