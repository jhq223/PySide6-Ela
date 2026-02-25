from PySide6 import QtCore, QtWidgets, QtGui
from .PySide6_Ela import *

def __wrapsingleton(T):
    class __Wrapper:
        def __getattr__(self, name):
            return getattr(T.getInstance(), name)
    return __Wrapper()

eTheme = __wrapsingleton(ElaTheme)
eApp = __wrapsingleton(ElaApplication)

def ElaThemeColor(themeMode, themeColor):
    return eTheme.getThemeColor(themeMode, themeColor)
