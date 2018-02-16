#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PyQt5 import QtWidgets, QtCore, QtGui


class ValLineEdit(QtWidgets.QLineEdit):
    """Change style according to validator"""
    color_valid = QtCore.Qt.black
    color_invalid = QtCore.Qt.red

    def __init__(self, *a, **kw):
        super(ValLineEdit, self).__init__(*a, **kw)
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Text, self.color_valid)
        self.textChanged.connect(self.adapt_color)

    def adapt_color(self):
        color = self.color_valid if self.hasAcceptableInput() else self.color_invalid
        p = self.palette()
        p.setColor(QtGui.QPalette.Text, color)
        self.setPalette(p)

