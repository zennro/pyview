import sys
import mimetypes
import getopt
import re
import weakref

from PyQt4.QtGui import * 
from PyQt4.QtCore import *
from numpy import complex128

from pyview.gui.patterns import ObserverWidget

#This is our directory model...
class DatacubeViewModel(QAbstractItemModel,ObserverWidget):

  def updated(self,cube,property = None,value = None):
    if cube != self._cube:
      cube.detach(self)
    else:
      self.emit(SIGNAL("layoutChanged()"))
  
  def flags(self,index):
    return QAbstractItemModel.flags(self,index) | Qt.ItemIsEditable
  
  def __init__(self,cube):
    QAbstractItemModel.__init__(self)
    ObserverWidget.__init__(self)
    self.setDatacube(cube)
    
  def datacube(self):
    return self._cube
  
  def setDatacube(self,cube):
    if hasattr(self,'_cube') and self._cube != None:
      self._cube.detach(self)
    self._cube = cube
    self.emit(SIGNAL("modelReset()"))
    if cube != None:
      self._cube.attach(self)
    
  def setElement(self,index,value):
    iy = index.column()
    ix = index.row()
    if value == "":
      return
    if ix >= len(self._cube):
      self._cube.addRow()
      self.emit(SIGNAL("layoutChanged()"))
    if self._cube.table().dtype == complex128:
      self._cube.table()[ix,iy] = complex(value)
    else:
      self._cube.table()[ix,iy] = float(value)
    

  def getElement(self,index):
    iy = index.column()
    ix = index.row()
    if ix >= len(self._cube):
      return ""
    value = self._cube.table()[ix,iy]
    if self._cube.table().dtype == complex128:
      if value == 0:
        return "0"
      return str(value)[1:-1]
    return str(value)
          
  def index(self,row,column,parent):
    return self.createIndex(row,column,None)
    
  def parent(self,index):
    return QModelIndex()

  def headerData(self,section,orientation,role = Qt.DisplayRole):
    if role == Qt.DisplayRole and orientation == Qt.Vertical:
      return QString(str(section))
    if role == Qt.DisplayRole and orientation == Qt.Horizontal and self._cube != None:
      name = self._cube.columnName(section)
      if name != None:
        return QString(name)
    return QAbstractItemModel.headerData(self,section,orientation,role)

  #Returns the data for the given node...
  def data(self,index,role):
    if role == Qt.DisplayRole:
      element = self.getElement(index)
      return QVariant(element)
    return QVariant()
    
  def hasChildren(self,index):
    return False
  
  def rowCount(self,index):
    if self._cube == None:
      return 0
    return len(self._cube)+1
    
  #Returns the rowCount of a given node. If the corresponding directory has never been parsed, we call buildDirectory to do so.
  def columnCount(self,index):
    if self._cube == None:
      return 0
    return len(self._cube.names())

class ElementDelegate(QItemDelegate):
  
  def setModel(self,model):
    self._model = model
  
  def setModelData(self,editor,model,index):    
    self._model.setElement(index,str(editor.text()))
  
  def setEditorData(self,editor,index):
    value = self._model.getElement(index)
    editor.setText(str(value))
  
  def createEditor(self,parent,option,index):
    return QLineEdit(parent)
    

class DatacubeTableView(QTableView):

  def setDatacube(self,cube):
    self.dirModel.setDatacube(cube)
    self.dirModel.reset()
    self.setContextMenuPolicy(Qt.CustomContextMenu)
    self.connect(self, SIGNAL("customContextMenuRequested(const QPoint &)"), self.getContextMenu)

  def removeRow(self):
    indices = self.selectedIndexes()
    rows = []
    for index in indices:
      rows.append(index.row())
    self.dirModel.datacube().removeRows(rows)

  def getContextMenu(self,p):
    menu = QMenu()
    selectedItems = self.selectedIndexes()
    if len(selectedItems) >= 1:
      removeAction = menu.addAction("Remove selected rows")
      self.connect(removeAction,SIGNAL("triggered()"),self.removeRow)
    menu.exec_(self.viewport().mapToGlobal(p))

  def __init__(self,cube = None,parent = None):
    QTableView.__init__(self,parent)
    self.delegate = ElementDelegate(self)
    self.dirModel = DatacubeViewModel(cube)
    self.delegate.setModel(self.dirModel)
    self.setModel(self.dirModel)
    self.setItemDelegate(self.delegate)
    self.setAutoScroll(True)
    self.setEditTriggers(QAbstractItemView.AnyKeyPressed | QAbstractItemView.SelectedClicked | QAbstractItemView.DoubleClicked)
    self.setSelectionMode(QAbstractItemView.ContiguousSelection)
    self.connect(self,SIGNAL("doubleClicked(QModelIndex)"),self.doubleClicked)

  def doubleClicked(self,index):
    pass
