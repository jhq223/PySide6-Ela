from PySide6 import QtCore, QtWidgets, QtGui
from .PySide6_Ela import *

class _SingletonWrapper:
    def __init__(self, cls):
        self.__dict__['_cls'] = cls
        
    def __getattr__(self, name):
        return getattr(self._cls.getInstance(), name)
        
    def __dir__(self):
        return dir(self._cls.getInstance())

eTheme = _SingletonWrapper(ElaTheme)
eApp = _SingletonWrapper(ElaApplication)

def ElaThemeColor(themeMode, themeColor):
    return eTheme.getThemeColor(themeMode, themeColor)
