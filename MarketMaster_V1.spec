# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('webapp/templates', 'webapp/templates'),
        ('webapp/static', 'webapp/static'),
        ('ui/style.qss', 'ui'),
    ],
    hiddenimports=[
        'flask', 'werkzeug', 'werkzeug.serving', 'jinja2',
        'PySide6', 'PySide6.QtWidgets', 'PySide6.QtCore', 'PySide6.QtGui',
        'pandas', 'numpy', 'openpyxl',
        'requests', 'urllib3', 'certifi', 'charset_normalizer',
        'sqlite3', 'json', 'threading', 'socket',
        'bcrypt',
        'cryptography', 'cryptography.hazmat.primitives.ciphers.aead',
        'cryptography.hazmat.primitives.ciphers', 'cryptography.hazmat.primitives',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'sklearn', 'scipy', 'matplotlib', 'IPython', 'IPython.core',
        'jupyter', 'notebook', 'sphinx', 'babel', 'zmq',
        'black', 'yapf', 'astroid', 'pylint', 'pydocstyle',
        'PyQt5', 'PyQt6',
        'tkinter', '_tkinter',
        'test', 'unittest',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MarketMaster_V1',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MarketMaster_V1',
)
