import sys
import glob
import os
import re
import datetime

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

import pyqtgraph as pg

import numpy as np
import h5py
import fabio
from PIL import Image

__version__ = '0.9'

## build with
# pyinstaller  pattern_viewer.spec

from pyqtgraph.graphicsItems import GradientEditorItem

GradientEditorItem.Gradients.update(
    {'viridis': {'ticks': [(0.0, (68, 1, 84, 255)), (0.25, (58, 82, 139, 255)), (0.5, (32, 144, 140, 255)), (0.75, (94, 201, 97, 255)), (1.0, (253, 231, 36, 255))], 'mode': 'rgb'},
    'inferno': {'ticks': [(0.0, (0, 0, 3, 255)), (0.25, (87, 15, 109, 255)), (0.5, (187, 55, 84, 255)), (0.75, (249, 142, 8, 255)), (1.0, (252, 254, 164, 255))], 'mode': 'rgb'},
    'plasma':  {'ticks': [(0.0, (12, 7, 134, 255)), (0.25, (126, 3, 167, 255)), (0.5, (203, 71, 119, 255)), (0.75, (248, 149, 64, 255)), (1.0, (239, 248, 33, 255))], 'mode': 'rgb'},
    'magma':   {'ticks': [(0.0, (0, 0, 3, 255)), (0.25, (80, 18, 123, 255)), (0.5, (182, 54, 121, 255)), (0.75, (251, 136, 97, 255)), (1.0, (251, 252, 191, 255))], 'mode': 'rgb'}})


class CBFreader:
    '''Reader for CBF files

    :param fname: file name of cbf file
    :type fname: string

    .. autoinstanceattribute:: map
       :annotation:

        array of the image
    '''
    def __init__(self, fname):
        self.fname = fname
        self.name = os.path.basename(self.fname)

    def image(self):
        print('opening file %s' %self.name)
        self.file = fabio.open(self.fname)
        return self.file.data
    
    def close(self):
        print('closing file %s' %self.name)
        self.file.close()


class LambdaReader:
    def __init__(self, fname):
        self.fname = fname
        self.name = os.path.basename(self.fname)
        self.is_open = False
        self.sub_item_map = {}

    def open(self):
        print('opening file %s' %self.name)
        self.file = h5py.File(self.fname, 'r')
        self.data = self.file['/entry/instrument/detector/data']
        self.images = range(self.data.shape[0])
        self.is_open = True

    def close(self):
        print('closing file %s' %self.name)
        self.file.close()
        self.sub_item_map = {}
        self.is_open = False

    def image(self, idx):
        return self.data[idx]

class LambdaItem:
    def __init__(self, reader, item):
        self.reader = reader
        self.item = item
        self.name = self.reader.name + '_%05d' %(item+1)

    def image(self):
        return self.reader.image(self.item)

class Lambda3MReader:
    def __init__(self, fname):
        self.fname = fname
        self.name = os.path.basename(self.fname)
        self.is_open = False
        self.sub_item_map = {}

        self.tile_x=1556
        self.tile_y=516

    def open(self):
        print('opening file %s' %self.name)
        ## initial code from A.R.
        # hdf5 convention is [z,y,x]
        # for lambda, float32 is sufficient
        ### would be better to init with NaNs
        self.merged_im = np.zeros([1834,3147], dtype='float32')
        #self.merged_im[:] = np.nan  # pyqtgraph gets confused?

        self.f01 = h5py.File(self.fname+"_m01.nxs", "r")
        self.f01_dset = self.f01['/entry/instrument/detector/data']
        self.f02 = h5py.File(self.fname+"_m02.nxs", "r")
        self.f02_dset = self.f02['/entry/instrument/detector/data']
        self.f03 = h5py.File(self.fname+"_m03.nxs", "r")
        self.f03_dset = self.f03['/entry/instrument/detector/data']
        self.f04 = h5py.File(self.fname+"_m04.nxs", "r")
        self.f04_dset = self.f04['/entry/instrument/detector/data']

        self.images = range(self.f01_dset.shape[0])
        self.is_open = True

    def close(self):
        print('closing file %s' %self.name)
        self.f01.close()
        self.f02.close()
        self.f03.close()
        self.f04.close()
        self.sub_item_map = {}
        self.is_open = False

    def image(self, idx):
        # the stitching code is from  Andre Rothkirch <andre.rothkirch@desy.de>
        self.merged_im[:] = 0# np.nan
        self.merged_im[1311:1311+self.tile_y,0:self.tile_x] = self.f01_dset[idx,:,:]
        self.merged_im[0:self.tile_y,1587:1587+self.tile_x] = self.f02_dset[idx,:,:]
        self.merged_im[658:658+self.tile_y,1591:1591+self.tile_x] = self.f03_dset[idx,:,:]
        self.merged_im[1318:1318+self.tile_y,1584:1584+self.tile_x] = self.f04_dset[idx,:,:]
        return self.merged_im


class PatternViewerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_lambda = False
        self.new = True
        self.pattern = None
        self.pattern_name = ''
        self.curr_item = None
        self.prev_item = None
        self._last_dir = ''

        self._lambda3m_regex = re.compile(r'(.*)_(m\d\d).nxs')

        self._sort_regex = re.compile(r'((.*)[\\/]+)?(.*)([\d]{5})(r([\d]{1,3}))?(_(\d))?_([\d]{5}).*')
        ## matches
        # pvdf_5b04_yscan_full_t_00002_00001.cbf
        # pvdf_5b04_yscan_full_t_00002r3_00001.cbf
        # pvdf_5b_02_yscan_0_ii_00004_2_00011.cbf

        self._reader_map = dict()

        self.open_button = QPushButton('Open')
        self.path_edit = QLineEdit('enter path (you can use glob syntax; if no glob is used opens all files in folder)')
        self.path_edit.setToolTip('enter path (you can use glob syntax; if no glob is used opens all files in folder)')
        self.pattern_list = QTreeWidget()
        self.pattern_list.setHeaderLabel('pattern')
        self.pattern_list.header().hide()
        self.pattern_list.setMinimumWidth(50)

        self.image_label = QLabel()
        self.image_label.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred))
        self.fname_label = QLabel()
        self.coord_label = QLabel()     
    
        self.transComboBox = QComboBox(self)
        self.transComboBox.addItem("None")
        self.transComboBox.addItem("rotate 90")
        self.transComboBox.addItem("rotate 180")
        self.transComboBox.addItem("rotate 270")
        self.transComboBox.addItem("flip up/down")
        self.transComboBox.addItem("flip left/right")
        self.transComboBox.addItem("rotate 90 & flip up/down")
        self.transComboBox.addItem("rotate 90 & flip left/right")

        self.scaleComboBox = QComboBox(self)
        self.scaleComboBox.addItem("lin")
        self.scaleComboBox.addItem("log10")
        self.scaleComboBox.addItem("sqrt")

        self.scale_checkbox = QCheckBox("keep scale")
        self.scale_checkbox.setChecked(True)
        self.scale_checkbox.setToolTip("remember the current scale for all images")
        
        ## monkey patch export method to fix bug in pyqtgraph for now
        # pg.ImageView.export = lambda self, fileName: self.imageItem.save(fileName[0])
        pg.ImageView.exportClicked = self.export_tiff
        self.image_widget = pg.ImageView(view=pg.PlotItem())

        self.layout = QVBoxLayout()

        open_layout = QHBoxLayout()
        open_layout.addWidget(self.path_edit)
        open_layout.addWidget(self.open_button)
        
        label_layout = QHBoxLayout()
        label_layout.addWidget(self.image_label)
        label_layout.addWidget(self.scale_checkbox)
        
        image_layout = QVBoxLayout()
        image_layout.addLayout(label_layout)
        image_layout.addWidget(self.image_widget)
        image_layout.addWidget(self.coord_label)
        image_widget = QWidget(self)
        image_widget.setLayout(image_layout)

        file_layout = QVBoxLayout()
        file_layout.addWidget(self.fname_label)
        file_layout.addWidget(QLabel('transform'))
        file_layout.addWidget(self.transComboBox)
        file_layout.addWidget(QLabel('scale'))
        file_layout.addWidget(self.scaleComboBox)       
        file_layout.addWidget(self.pattern_list)
        file_widget = QFrame()
       # file_widget.setFrameShape(QFrame.StyledPanel)
        file_widget.setLayout(file_layout)

        self.layout.addLayout(open_layout)
        splitter_lr = QSplitter(Qt.Horizontal)
        splitter_lr.addWidget(file_widget)
        splitter_lr.addWidget(image_widget)
        splitter_lr.setCollapsible(0, False)
        splitter_lr.setCollapsible(1, False)
        splitter_lr.setSizes([150,600])
        splitter_lr.setStyleSheet("""QSplitter::handle:horizontal{background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #eee, stop:1 #ccc);
                                     border: 1px solid #bbb;
                                     width: 5px; 
                                     margin-top: 100px; 
                                     margin-bottom: 100px; 
                                     border-radius: 4px;}""")
        self.layout.addWidget(splitter_lr)


        self.path_edit.returnPressed.connect(self.retPressed)
        self.open_button.clicked.connect(self.getfile)
        self.pattern_list.currentItemChanged.connect(self.show_pattern)
        self.scaleComboBox.currentIndexChanged.connect(self._set_pattern)
        self.transComboBox.currentIndexChanged.connect(self._set_pattern)
        
        self.proxy = pg.SignalProxy(self.image_widget.scene.sigMouseMoved, rateLimit=60, slot=self.mouseMoved)
        # self.image_widget.scene.sigMouseMoved.connect(self.mouseMoved)

        self.setLayout(self.layout)
        
    def mouseMoved(self, event):
        if self.pattern is None:
            self.coord_label.setText("no data")
            return

        pos = event[0]
        data = self.image_widget.image
        nRows, nCols = data.shape 

        scenePos = self.image_widget.getImageItem().mapFromScene(pos)
        row, col = int(scenePos.x()), int(scenePos.y())

        if (0 <= row < nRows) and (0 <= col < nCols):
            value = self.pattern[row, col]  #data[row, col]
            self.coord_label.setText("pos = ({:d}, {:d}), value = {!r} (unscaled!)".format(row, col, value))
        else:
            self.coord_label.setText("no data at cursor")
 
    def retPressed(self):
        self.find_files()

    def getfile(self):
        dlg = QFileDialog()
        dlg.setFileMode(QFileDialog.ExistingFile)
        if dlg.exec_():
            self.path_edit.setText( dlg.selectedFiles()[0] )
        self.find_files()

    def _sort_keys(self, name):
        m = self._sort_regex.match(name)
        print(name)
        print(m)
        if m.group(5) is not None:
            print(m.group(3), int(m.group(4)), int(m.group(6)), int(m.group(9)))
            return (m.group(3), int(m.group(4)), int(m.group(6)), int(m.group(9)))
        elif m.group(7) is not None:
            print(m.group(3), int(m.group(4)), int(m.group(8)), int(m.group(9)))
            return (m.group(3), int(m.group(4)), int(m.group(8)), int(m.group(9)))
        else:
            print(m.group(3), int(m.group(4)), int(m.group(9)))
            return (m.group(3), int(m.group(4)), int(m.group(9)))

    def find_files(self):
        self.prev_item = None
        self.pattern_list.clear()
        name = self.path_edit.text()
        self.new = True

        if any([i in name for i in '[*?']):
            self.flist = glob.glob(name)
            if not self.flist:
                self.image_label.setText('no files found')
                return
        else:
            # use all files in folder
            dirname = os.path.dirname(name)
            self.flist = [os.path.join(dirname, i) for i in os.listdir(os.path.dirname(name))]
            self.flist = list(filter(lambda x: x.endswith('.cbf') or x.endswith('.nxs'), self.flist))

        self.flist = sorted(self.flist, key=self._sort_keys)

        #print(self.flist)
        with pg.BusyCursor():
            for f in self.flist:
                if f.endswith('.cbf'):
                    self._add_cbf(f)
                elif f.endswith('.nxs'):
                    m = self._lambda3m_regex.match(f)
                    if m:
                        self._add_lambda3m(f)
                    else:
                        self._add_lambda(f)
        try:
            self.pattern_list.setCurrentItem(self.pattern_list.topLevelItem(0), 0, QItemSelectionModel.Select)
        except: pass

    def _add_cbf(self, name):
        alias = os.path.basename(name)
        reader = CBFreader(name)
        item = QTreeWidgetItem(self.pattern_list)
        item.setText(0, alias)
        item.setFlags(item.flags() | Qt.ItemIsSelectable)
        self._reader_map[alias] = reader

    def _add_lambda(self, name):
        reader = LambdaReader(name)
        alias = reader.name
        item = QTreeWidgetItem(self.pattern_list)
        reader.item = item
        item.setText(0, alias)
        item.setFlags(item.flags() | Qt.ItemIsSelectable)
        self._reader_map[alias] = reader

    def _add_lambda3m(self, name):
        m = self._lambda3m_regex.match(name)
        if not m.group(2) == 'm01':
            return
        reader = Lambda3MReader(m.group(1))
        alias = reader.name
        item = QTreeWidgetItem(self.pattern_list)
        reader.item = item
        item.setText(0, alias)
        item.setFlags(item.flags() | Qt.ItemIsSelectable)
        self._reader_map[alias] = reader

    def _set_pattern(self):
        if self.pattern is None:
            return
        trans_text = self.transComboBox.currentText()
        if trans_text == "None":
            self.pattern = self.pattern_o
        elif trans_text == "rotate 90":
            self.pattern = np.rot90(self.pattern_o, k=1, axes=(1,0))
        elif trans_text == "rotate 180":
            self.pattern = np.fliplr(np.flipud(self.pattern_o))
        elif trans_text == "rotate 270":
            self.pattern = np.rot90(self.pattern_o)
        elif trans_text == "flip up/down":
            self.pattern = np.fliplr(self.pattern_o)
        elif trans_text == "flip left/right":
            self.pattern = np.flipud(self.pattern_o)
        elif trans_text == "rotate 90 & flip up/down":
            self.pattern = np.fliplr(np.rot90(self.pattern_o, k=1, axes=(1,0)))
        elif trans_text == "rotate 90 & flip left/right":
            self.pattern = np.flipud(np.rot90(self.pattern_o, k=1, axes=(1,0)))

        scaled_pattern = self.pattern[:]
        scale_text = self.scaleComboBox.currentText()
        if scale_text == "lin":
            pass
        elif scale_text == 'log10':
            scaled_pattern[self.pattern<0] = 0
            scaled_pattern = np.log10(scaled_pattern+1)
        elif scale_text == 'sqrt':
            scaled_pattern[self.pattern<0] = 0
            scaled_pattern = np.sqrt(scaled_pattern)
    
        if self.pattern is None:
            self.image_widget.setImage(scaled_pattern, levels=(0, 100), autoRange=True, autoHistogramRange=False)
        elif self.scale_checkbox.isChecked():
            self.image_widget.setImage(scaled_pattern, autoLevels=False, autoRange=True if self.new else False, autoHistogramRange=False)
        else:
            self.image_widget.setImage(scaled_pattern, autoLevels=True, autoRange=True if self.new else False, autoHistogramRange=False)


    def show_pattern(self):
        self.curr_item = self.pattern_list.currentItem()
        if not self.curr_item: return
        if self.curr_item.childCount() > 0:
            # if we have children, select first child (does not highlight it?)
            self.pattern_list.setCurrentItem(self.curr_item.child(0), 0, QItemSelectionModel.Select)
            return
        if self.curr_item.parent() is not None:
            print('has parent')
            parent_selected = False
            self.curr_item = self.curr_item.parent()

        item = self.curr_item.text(0)

        ## Hack: if we empty the pattern list when opening a new file show_pattern is called
        # in this case item is None and I just return
        if item is None: return
        r = self._reader_map[item]

        if isinstance(r, (LambdaReader, Lambda3MReader)):
            print('is lambda')
            if r.is_open:
                pattern_reader = r.sub_item_map[self.pattern_list.currentItem().text(0)]   
            else:
                print('opening nxs')
                r.open()
                # if we have multiple pattern in the nexus file we add children to the current item
                if len(r.images) > 1 and not self.curr_item.childCount():
                    for x in r.images:
                        alias = "%05d" %(x+1)
                        child = QTreeWidgetItem(self.curr_item)
                        child.setFlags(child.flags() | Qt.ItemIsSelectable)
                        child.setText(0, alias)
                        r.sub_item_map["%05d" %(x+1)] = LambdaItem(r, x)
                else:
                    # children have been previously created, if we reopen the
                    #  file we only need to recreate the map of the names to 
                    # the pattern in the file
                    for x in r.images:
                        alias = "%05d" %(x+1)
                        r.sub_item_map["%05d" %(x+1)] = LambdaItem(r, x)
                if self.pattern_list.currentItem().text(0) == r.name:
                    if len(r.images) == 1:
                        pattern_reader = LambdaItem(r, 0)
                    else:
                        pattern_reader = r.sub_item_map['00001']  # not nice, should not be hardcoded
                else:
                    pattern_reader = r.sub_item_map[self.pattern_list.currentItem().text(0)]
                    
        else:
            pattern_reader = r
        self.pattern_o = np.asarray(pattern_reader.image(), dtype=np.float32)   
        self.pattern = self.pattern_o    
        
        self._set_pattern()
        self.pattern_name = pattern_reader.name
        self.image_label.setText("pattern: %s" %pattern_reader.name)

        # if we need to open a new file close the previous file
        if self.prev_item is not None and self.prev_item is not self.curr_item: self._reader_map[self.prev_item.text(0)].close()
        self.prev_item = self.curr_item
        self.new = False

    def export_tiff(self):
        if self.pattern is None:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setText("You need to select a patter to be exported.")
            msg.setWindowTitle("No Pattern to export")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
            return
        fn = QFileDialog().getSaveFileName(self, 
                          'Export TIFF: 32bit signed int, lzw compressed',
                           os.path.join(self._last_dir, '%s.tiff' %self.pattern_name),
                           "TIFF (*.tiff)")
        if fn[0]:
            #print(fn)
            img = Image.fromarray(self.pattern.T, 'I')
            self._last_dir = os.path.dirname(fn[0])
            img.save(fn[0], compression='tiff_lzw')



class PatternViewer(QMainWindow):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pattern Viewer (Version %s)" %__version__)
        self.pattern_viewer_widget = PatternViewerWidget(self)
        self.setCentralWidget(self.pattern_viewer_widget)

        exitAct = QAction('Exit', self)
        exitAct.setShortcut('Ctrl+Q')
        exitAct.setStatusTip('Exit application')
        exitAct.triggered.connect(self.close)

        exportTIFF = QAction('Export TIFF', self)
        exportTIFF.setShortcut('Ctrl+E')
        exportTIFF.setStatusTip('Export TIFF')
        exportTIFF.triggered.connect(self.pattern_viewer_widget.export_tiff)

        menubar = self.menuBar()
        fileMenu = menubar.addMenu('File')
        fileMenu.addAction(exportTIFF) 
        fileMenu.addAction(exitAct)


        aboutAct = QAction('About', self)
        aboutAct.triggered.connect(self.helpAbout)
        helpMenu = menubar.addMenu('Help')
        helpMenu.addAction(aboutAct)

    def helpAbout(self):
        QMessageBox.about(self, "About pattern viewer",
          """<b>Pattern Viewer v%s (2020)</b>
            <p>
            Website:
            <a href="https://github.com/ipf-scattering/pattern-viewer">https://github.com/ipf-scattering/pattern-viewer</a>
            </p>
            """ %(__version__))

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller 
    
    https://stackoverflow.com/a/51061279
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def main():
    app = QApplication(sys.argv)
    form = PatternViewer()
    app.setApplicationName("Pattern Viewer")
    if sys.platform == 'win32':
        app.setWindowIcon(QIcon('images/pattern_viewer.ico'))
    elif sys.platform == 'darwin':
        app.setWindowIcon(QIcon(resource_path('images/pattern_viewer.icns')))
    form.show()
    app.exec_()


main()
