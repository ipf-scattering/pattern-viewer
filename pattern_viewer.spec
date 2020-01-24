# -*- mode: python -*-
import sys
import os

sys.setrecursionlimit(5000)

dir_path = os.path.dirname(os.path.realpath('__file__'))

block_cipher = None

# if the icon doesn't update, clear the Windows 10 icon cache by restarting or: ie4uinit.exe -show

a = Analysis(['pattern_viewer.py'],
             pathex=[dir_path],
             binaries=[],
             datas=[('images/pattern_viewer.ico', 'images/'),
                    ('images/pattern_viewer.icns', 'images/'),],
             hiddenimports=['h5py.defs', 'h5py.utils', 'h5py.h5ac', 'h5py._proxy', 
                            'fabio.edfimage', 'fabio.dtrekimage', 'fabio.tifimage', 'fabio.marccdimage',
                            'fabio.mar345image', 'fabio.fit2dmaskimage', 'fabio.brukerimage',
                            'fabio.bruker100image', 'fabio.pnmimage', 'fabio.GEimage', 'fabio.OXDimage',
                            'fabio.dm3image', 'fabio.HiPiCimage', 'fabio.pilatusimage', 'fabio.fit2dspreadsheetimage',
                            'fabio.kcdimage', 'fabio.cbfimage', 'fabio.xsdimage', 'fabio.binaryimage',
                            'fabio.pixiimage', 'fabio.raxisimage', 'fabio.numpyimage', 'fabio.eigerimage',
                            'fabio.hdf5image', 'fabio.fit2dimage', 'fabio.speimage', 'fabio.jpegimage',
                            'fabio.jpeg2kimage', 'fabio.mpaimage', 'fabio.mrcimage', 'fabio.adscimage'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
            # excludes=['matplotlib', 'pandas', 'sklearn', 
            #            'bokeh', 'torch', 'tensorflow',
            #            'algopy', 'altair', 'altair_widgets',
            #            'astropy', 'cartopy', 'edward', 'keras',
            #            'keras_applications', 'keras_preprocessing',
            #            'keras_vis'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

if sys.platform == 'win32':
    exe = EXE(pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='pattern_viewer',
        debug=True,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=True,
        icon='images/pattern_viewer.ico')
    coll = COLLECT(exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        name='pattern_viewer')
elif sys.platform == 'darwin':
    exe = EXE(pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='pattern_viewer',
        debug=True,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        runtime_tmpdir=None,
        console=False,
        icon='images/pattern_viewer.icns')
    coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='pattern_viewer')
    app = BUNDLE(coll,
                name='PatternViewer.app',
                info_plist={
                  'NSHighResolutionCapable': 'True'
                },
                icon='images/pattern_viewer.icns',
                bundle_identifier=None)