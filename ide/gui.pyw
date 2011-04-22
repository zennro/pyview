import sys

import os
import os.path


import mimetypes
import threading

import random
import time

#Matplotlib settings: Enable interactive plotting with custom backend.
import matplotlib
matplotlib.use('module://pyview.ide.mpl.backend_agg')
import matplotlib.pyplot
import pyview.ide.mpl.backend_agg as mpl_backend

from PyQt4.QtGui import * 
from PyQt4.QtCore import *
from pyview.ide.editor.codeeditor import *
from pyview.ide.preferences import *
from pyview.helpers.coderunner import MultiProcessCodeRunner

import settings
import datetime
import time
import re

from pyview.ide.patterns import ObserverWidget
from pyview.config.parameters import params

import pyview.helpers.instrumentsmanager

class LogProxy:
  
  def __init__(self,callback,filename = None,timeStampInterval = 60):
    self._callback = callback
    self._fh = None
    self._timeStampInterval = 60
    self._filename = filename
    self._lastTime = time.time()
    self.openLogfile()
    
  
  def openLogfile(self):
    if self._filename == None:
      return
    if not self._fh == None:  
      try:
        self._fh.close()
      except:
        pass
    try:
      self._fh = open(self._filename,"a")
      self._fh.write(self.timeStamp())
    except IOError:
      print "Cannot open logfile!"
      self._fh = None
  
  def timeStamp(self):
    today = str(datetime.datetime.today())
    return "\n\n------------------------------\n"+today+"\n------------------------------\n\n"
  
  def write(self,text):
    if not self._fh == None:
      try:
        self._fh.write(text)
        self._fh.flush()
      except IOError:
        self._fh = None
        print "Error when writing to logfile, closing..."
    self._callback(text)

class Log(LineTextWidget):

    """
    Log text window.
    
    To do:
      -Add a context menu with a "clear all" menu entry
      -Add a search function
    """

    def __init__(self,parent = None ):
        LineTextWidget.__init__(self,parent)
        MyFont = QFont("Courier",10)
        MyDocument = self.document() 
        MyDocument.setDefaultFont(MyFont)
        self.setDocument(MyDocument)
        self.setMinimumHeight(200)
        self.setReadOnly(True)
        self.timer = QTimer(self)
        self._writing = False
        self.timer.setInterval(300)
        self.queuedStdoutText = ""
        self.queuedStderrText = ""
        self.connect(self.timer,SIGNAL("timeout()"),self.addQueuedText)
        self.timer.start()
        self.cnt=0
        
    def contextMenuEvent(self,event):
      MyMenu = self.createStandardContextMenu()
      MyMenu.addSeparator()
      clearLog = MyMenu.addAction("clear log")
      self.connect(clearLog,SIGNAL("triggered()"),self.clearLog)
      MyMenu.exec_(self.cursor().pos())

    def clearLog(self):
      self.clear()
        
    def addQueuedText(self): 
      if self._writing:
        return
      if self.queuedStderrText == "" and self.queuedStdoutText == "":
        return
      self.moveCursor(QTextCursor.End)
      if self.queuedStdoutText != "":
        self.textCursor().insertText(self.queuedStdoutText)
      #Insert error messages with an orange background color.
      if self.queuedStderrText != "":
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        oldFormat = cursor.blockFormat()
        format = QTextBlockFormat()
        format.setBackground(QColor(255,200,140))
        cursor.insertBlock(format)
        cursor.insertText(self.queuedStderrText)
        cursor.movePosition(QTextCursor.EndOfBlock,QTextCursor.KeepAnchor)
        cursor.setBlockFormat(oldFormat)

      self.queuedStdoutText = ""
      self.queuedStderrText = ""
        
    def writeStderr(self,text):
      while self._writing:
        time.sleep(0.1)
      try:
        self._writing = True
#        parsedText = re.sub(r'\0',r'\\0',text)
        self.queuedStderrText += text      
      finally:
        self._writing = False
        
    def writeStdout(self,text):
      while self._writing:
        time.sleep(0.1)
      try:
        self._writing = True
#        parsedText = re.sub(r'\0',r'\\0',text)
        self.queuedStdoutText += text
      finally:
        self._writing = False
        
class IDE(QMainWindow,ObserverWidget):

    """
    The main code IDE
    
    To do:
      -Add standard menu entries (edit, view, etc...)
      -Add explicit support for plugins
    """

    def fileBrowser(self):
      return self.FileBrowser

    def directory(self):
      return self.FileBrowser.directory()

    def closeEvent(self,e):
      MyMessageBox = QMessageBox()
      MyMessageBox.setWindowTitle("Warning!")
      MyMessageBox.setText("Do you really want to close the IDE?")
      yes = MyMessageBox.addButton("Yes",QMessageBox.YesRole)
      no = MyMessageBox.addButton("No",QMessageBox.NoRole)
      MyMessageBox.exec_()
      choice = MyMessageBox.clickedButton()
      if choice == no:
        e.ignore()
        return
      self.Editor.closeEvent(e)
      print "Stopping code runner..."
      self._codeRunner.terminate()
            
    def preferences(self):
      if not hasattr(self,'_preferences'):
        self._preferences = Preferences(path = params["directories.setup"]+"\\config\\")
      return self._preferences

    def changeWorkingPath(self,path = None):
      if path == None:
        path = QFileDialog.getExistingDirectory(self,"Change Working Path")
      if not os.path.exists(path):
        return
      os.chdir(unicode(path)) 
      self.preferences().set('defaultDir',path)
      self.preferences().save()
      self.workingPathLabel.setText("Working path:"+os.getcwd())
        
    def onTimer(self):
      mpl_backend.updateFigures()
              
    def setupCodeEnvironmentCallback(self,thread):
      print "Done setting up code environment..."
      
    def setupCodeEnvironment(self):
      self._codeRunner.clear()
      self._codeRunner.executeCode("""import sys;
if "config.startup" in sys.modules:
  reload(sys.modules["config.startup"])
__import__("config.startup",globals(),globals())
""",-1,"<init script>",self._codeRunner.gv(),self._codeRunner.gv())
      
    def codeRunner(self):
      return self._codeRunner

    def __init__(self,parent=None):
        QMainWindow.__init__(self,parent)
        ObserverWidget.__init__(self)

        self.setWindowTitle("Python Lab IDE, A. Dewes")
        
        
        self.setDockOptions(QMainWindow.AllowTabbedDocks	)

        self.LeftBottomDock = QDockWidget()
        self.RightBottomDock = QDockWidget()
                
          
        self.LeftBottomDock.setWindowTitle("Log")
        self.RightBottomDock.setWindowTitle("File Browser")

        self.MyLog = Log()
        
        horizontalSplitter = QSplitter(Qt.Horizontal)
        verticalSplitter = QSplitter(Qt.Vertical)      

        gv = dict()

        self._codeRunner = CodeRunner(gv = gv,lv = gv)
        self.Editor = CodeEditorWindow(codeRunner = self._codeRunner,preferences = self.preferences())
        self.errorConsole = ErrorConsole(codeEditorWindow = self.Editor,codeRunner = self._codeRunner)
        
        self.tabs = QTabWidget()
        self.logTabs = QTabWidget()
        
        self.logTabs.addTab(self.MyLog,"Log")
        self.logTabs.addTab(self.errorConsole,"Traceback")
        
        self.tabs.setMaximumWidth(350)
        horizontalSplitter.addWidget(self.tabs)
        horizontalSplitter.addWidget(self.Editor)
        verticalSplitter.addWidget(horizontalSplitter)
        verticalSplitter.addWidget(self.logTabs)

        StatusBar = self.statusBar()
        self.workingPathLabel = QLabel("Working path: ?")
        StatusBar.addWidget(self.workingPathLabel)  

        self.setCentralWidget(verticalSplitter)
        
        self.MyMenuBar = self.menuBar()
        
        FileMenu = self.MyMenuBar.addMenu("File")
        
        newIcon = QIcon(params['path']+params['directories.crystalIcons']+'/actions/filenew.png')
        openIcon = QIcon(params['path']+params['directories.crystalIcons']+'/actions/fileopen.png')
        saveIcon = QIcon(params['path']+params['directories.crystalIcons']+'/actions/filesave.png')
        saveAsIcon = QIcon(params['path']+params['directories.crystalIcons']+'/actions/filesaveas.png')
        closeIcon = QIcon(params['path']+params['directories.crystalIcons']+'/actions/fileclose.png')
        exitIcon = QIcon(params['path']+params['directories.crystalIcons']+'/actions/exit.png')
        workingPathIcon = QIcon(params['path']+params['directories.crystalIcons']+'/actions/gohome.png')
        killThreadIcon = QIcon(params['path']+params['directories.crystalIcons']+'/actions/stop.png')
        
        fileNew = FileMenu.addAction(newIcon,"&New")
        fileNew.setShortcut(QKeySequence("CTRL+n"))
        fileOpen = FileMenu.addAction(openIcon,"&Open")
        fileOpen.setShortcut(QKeySequence("CTRL+o"))
        fileClose = FileMenu.addAction(closeIcon,"&Close")
        fileClose.setShortcut(QKeySequence("CTRL+F4"))
        fileSave = FileMenu.addAction(saveIcon,"&Save")
        fileSave.setShortcut(QKeySequence("CTRL+s"))
        fileSaveAs = FileMenu.addAction(saveAsIcon,"Save &As")
        fileSaveAs.setShortcut(QKeySequence("CTRL+F12"))

        FileMenu.addSeparator()

        fileExit = FileMenu.addAction(exitIcon,"Exit")
        fileExit.setShortcut(QKeySequence("CTRL+ALT+F4"))
        
        self.connect(fileNew, SIGNAL('triggered()'), self.Editor.newEditor)
        self.connect(fileOpen, SIGNAL('triggered()'), self.Editor.openFile)
        self.connect(fileClose, SIGNAL('triggered()'), lambda : self.Editor.closeTab(self.Editor.Tab.currentIndex()))
        self.connect(fileSave, SIGNAL('triggered()'), lambda : self.Editor.Tab.currentWidget().saveFile())
        self.connect(fileSaveAs, SIGNAL('triggered()'), lambda : self.Editor.Tab.currentWidget().saveFileAs())
        self.connect(fileExit, SIGNAL('triggered()'), self.close)

        
        FileMenu.addSeparator()  

        self.editMenu = self.MyMenuBar.addMenu("Edit")
        self.viewMenu = self.MyMenuBar.addMenu("View")
        self.toolsMenu = self.MyMenuBar.addMenu("Tools")
        self.settingsMenu = self.MyMenuBar.addMenu("Settings")
        self.windowMenu = self.MyMenuBar.addMenu("Window")
        self.helpMenu = self.MyMenuBar.addMenu("Help")
        self.MyToolbar = self.addToolBar("Tools")
        
        newFile = self.MyToolbar.addAction(newIcon,"New")
        openFile = self.MyToolbar.addAction(openIcon,"Open")
        saveFile = self.MyToolbar.addAction(saveIcon,"Save")
        saveFileAs = self.MyToolbar.addAction(saveAsIcon,"Save As")

        self.MyToolbar.addSeparator()
        
        executeAll = self.MyToolbar.addAction(QIcon(params['path']+params['directories.crystalIcons']+'/actions/run.png'),"Run")
        executeBlock = self.MyToolbar.addAction(QIcon(params['path']+params['directories.crystalIcons']+'/actions/kde1.png'),"Run Block")
        executeSelection = self.MyToolbar.addAction(QIcon(params['path']+params['directories.crystalIcons']+'/actions/kde4.png'),"Run Selection")

        self.MyToolbar.addSeparator()

        changeWorkingPath = self.MyToolbar.addAction(workingPathIcon,"Change working path")
        killThread = self.MyToolbar.addAction(killThreadIcon,"Kill Thread")

        self.connect(executeBlock, SIGNAL('triggered()'), lambda : self.Editor.Tab.currentWidget().executeBlock())
        self.connect(executeSelection, SIGNAL('triggered()'), lambda : self.Editor.Tab.currentWidget().executeSelection())
        self.connect(executeAll, SIGNAL('triggered()'), lambda :  self.Editor.Tab.currentWidget().executeAll())
        self.connect(changeWorkingPath, SIGNAL('triggered()'), self.changeWorkingPath)
        self.connect(killThread, SIGNAL('triggered()'), self.Editor.stopExecution)

        self.connect(newFile, SIGNAL('triggered()'), self.Editor.newEditor)
        self.connect(openFile, SIGNAL('triggered()'), self.Editor.openFile)
        self.connect(saveFile, SIGNAL('triggered()'), lambda : self.Editor.Tab.currentWidget().saveFile())
        self.connect(saveFileAs, SIGNAL('triggered()'), lambda : self.Editor.Tab.currentWidget().saveFileAs())
        
        self.setWindowIcon(QIcon(params['path']+params['directories.crystalIcons']+'/apps/penguin.png'))
        
        #We add a timer
        self.timer = QTimer(self)
        self.timer.setInterval(400)
        self.queuedText = ""
        self.connect(self.timer,SIGNAL("timeout()"),self.onTimer)
        self.timer.start()
        
                
        self.errorProxy = LogProxy(self.MyLog.writeStderr)
        self.eventProxy = LogProxy(self.MyLog.writeStdout)

        if self.preferences().get('defaultDir') != None:
          self.changeWorkingPath(self.preferences().get('defaultDir'))

        settings.InitIDE(self)

        sys.stdout = self.eventProxy
        sys.stderr = self.errorProxy

def startIDE(qApp = None):
  if qApp == None:
    qApp = QApplication(sys.argv)
  qApp.setStyle(QStyleFactory.create("QMacStyle"))
  qApp.setStyleSheet("""
QTreeWidget:Item {padding:6;}
QTreeView:Item {padding:6;}
  """)
  qApp.connect(qApp, SIGNAL('lastWindowClosed()'), qApp,
                    SLOT('quit()'))
  MyIDE = IDE()
  MyIDE.showMaximized()
  qApp.exec_()
  
  print "Exiting..."
          
if __name__ == '__main__':
  startIDE()
