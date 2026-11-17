#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for PyQuadDir core helpers, v2.4 diagnostics, build script, and v3.1.1 address bar regressions."""

import os
import atexit
from contextlib import contextmanager
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import build_exe
import pyquaddir


@contextmanager
def _scoped_exit_callbacks():
    """A mocked application must not outlive its temporary profile."""
    callbacks = []
    original_register = atexit.register

    def register(callback, *args, **kwargs):
        callbacks.append(callback)
        return original_register(callback, *args, **kwargs)

    try:
        with mock.patch.object(atexit, "register", side_effect=register):
            yield
    finally:
        for callback in callbacks:
            atexit.unregister(callback)


def _build_qt_propagation_stub_modules():
    """
    Headless fallback stub of PyQt6 that faithfully reproduces Qt C++ behavior when PyQt6 is unavailable:
      1. `QLineEdit.keyPressEvent` emits `returnPressed` on Key_Return/Key_Enter and calls `event.ignore()`.
      2. Unaccepted key events bubble up the parent widget hierarchy to `QMainWindow.keyPressEvent`.
      3. `QAbstractItemView.focusInEvent` snaps an invalid `currentIndex` to `(0, 0)` (row 0 = '..').
    """
    qtcore = types.ModuleType("PyQt6.QtCore")
    qtgui = types.ModuleType("PyQt6.QtGui")
    qtwidgets = types.ModuleType("PyQt6.QtWidgets")
    pyqt6_pkg = types.ModuleType("PyQt6")

    class BoundSignal:
        def __init__(self):
            self._slots = []

        def connect(self, slot):
            self._slots.append(slot)

        def emit(self, *args):
            for slot in list(self._slots):
                try:
                    slot(*args)
                except TypeError:
                    slot()

    class SignalDescriptor:
        def __init__(self):
            self._name = f"_sig_{id(self)}"

        def __get__(self, instance, owner):
            if instance is None:
                return self
            sig = instance.__dict__.get(self._name)
            if sig is None:
                sig = BoundSignal()
                instance.__dict__[self._name] = sig
            return sig

    def pyqtSignal(*_args, **_kwargs):
        return SignalDescriptor()

    class Qt:
        class Key:
            Key_Return = 0x01000004
            Key_Enter = 0x01000005
            Key_Escape = 0x01000000
            Key_Backspace = 0x01000003

        class KeyboardModifier:
            NoModifier = 0
            ControlModifier = 0x04000000
            ShiftModifier = 0x02000000

        class MouseButton:
            LeftButton = 1
            MiddleButton = 4

        class AlignmentFlag:
            AlignLeft = 1
            AlignRight = 2
            AlignHCenter = 4
            AlignTop = 32
            AlignVCenter = 128
            AlignCenter = 132

        class TextElideMode:
            ElideRight = 1
            ElideMiddle = 2

        class Orientation:
            Horizontal = 1
            Vertical = 2

        class FocusPolicy:
            NoFocus = 0
            StrongFocus = 11

        class ContextMenuPolicy:
            CustomContextMenu = 3

        class ItemDataRole:
            UserRole = 0x0100

        class ItemFlag:
            ItemIsEnabled = 32
            ItemIsSelectable = 1

        class SortOrder:
            AscendingOrder = 0
            DescendingOrder = 1

        class GlobalColor:
            transparent = 0

        class PenStyle:
            NoPen = 0
            SolidLine = 1
            DotLine = 3

        class PenCapStyle:
            RoundCap = 1

        class PenJoinStyle:
            RoundJoin = 1

        class BrushStyle:
            NoBrush = 0

        class AspectRatioMode:
            KeepAspectRatio = 1

        class TransformationMode:
            SmoothTransformation = 1

        class ToolBarArea:
            TopToolBarArea = 4

        class ToolButtonStyle:
            ToolButtonIconOnly = 0
            ToolButtonTextBesideIcon = 2

        class CursorShape:
            PointingHandCursor = 13

        class TextInteractionFlag:
            TextSelectableByMouse = 1

        class DropAction:
            CopyAction = 1
            MoveAction = 2

    class QSize:
        def __init__(self, w=0, h=0):
            self._w, self._h = int(w), int(h)

        def width(self):
            return self._w

        def height(self):
            return self._h

        def isValid(self):
            return self._w >= 0 and self._h >= 0

        def scaled(self, other, *_args):
            return QSize(other.width(), other.height())

    class QPoint:
        def __init__(self, x=0, y=0):
            self._x, self._y = int(x), int(y)

        def x(self):
            return self._x

        def y(self):
            return self._y

        def manhattanLength(self):
            return abs(self._x) + abs(self._y)

        def __sub__(self, other):
            return QPoint(self._x - other._x, self._y - other._y)

    class QPointF:
        def __init__(self, x=0.0, y=0.0):
            self._x, self._y = float(x), float(y)

    class QRect:
        def __init__(self, *args):
            if len(args) == 4:
                self._x, self._y, self._w, self._h = [int(v) for v in args]
            elif len(args) == 2:
                p1, p2 = args
                self._x = min(p1.x(), p2.x())
                self._y = min(p1.y(), p2.y())
                self._w = abs(p2.x() - p1.x())
                self._h = abs(p2.y() - p1.y())
            else:
                self._x = self._y = 0
                self._w = self._h = 100

        def x(self):
            return self._x

        def y(self):
            return self._y

        def width(self):
            return self._w

        def height(self):
            return self._h

        def left(self):
            return self._x

        def top(self):
            return self._y

        def right(self):
            return self._x + self._w - 1

        def bottom(self):
            return self._y + self._h - 1

        def center(self):
            return QPoint(self._x + self._w // 2, self._y + self._h // 2)

        def intersects(self, _other):
            return True

        def normalized(self):
            return self

        def isValid(self):
            return self._w > 0 and self._h > 0

    class QRectF:
        def __init__(self, *_args):
            pass

    class QFileInfo:
        def __init__(self, path=""):
            self.path = path

    class QUrl:
        def __init__(self, url=""):
            self._url = url

        @staticmethod
        def fromLocalFile(p):
            return QUrl(p)

        def toString(self):
            return self._url

    class QMimeData:
        def __init__(self):
            self._urls = []

        def setUrls(self, urls):
            self._urls = list(urls)

        def hasUrls(self):
            return bool(self._urls)

        def urls(self):
            return self._urls

    class QTimer:
        @staticmethod
        def singleShot(_ms, callback):
            # Do not auto-fire delayed close timers during synchronous probe
            return None

    class ModelIndex:
        def __init__(self, row=-1, col=-1):
            self._r, self._c = int(row), int(col)

        def row(self):
            return self._r

        def column(self):
            return self._c

        def isValid(self):
            return self._r >= 0 and self._c >= 0

    class ItemModel:
        def __init__(self, owner):
            self._owner = owner

        def index(self, row, col=0):
            if row < 0 or col < 0:
                return ModelIndex(-1, -1)
            return ModelIndex(row, col)

    class QItemSelection:
        def __init__(self):
            self.rows = set()

        def select(self, left_idx, _right_idx):
            if left_idx.isValid():
                self.rows.add(left_idx.row())

    class QItemSelectionModel:
        class SelectionFlag:
            NoUpdate = 0
            Clear = 1
            Select = 2
            ClearAndSelect = 3
            Rows = 0x10
            SelectCurrent = 2

        def __init__(self, view):
            self._view = view
            self._current = ModelIndex(-1, -1)

        def currentIndex(self):
            return self._current

        def setCurrentIndex(self, index, flag=0):
            self._current = index
            if (flag & QItemSelectionModel.SelectionFlag.ClearAndSelect) == QItemSelectionModel.SelectionFlag.ClearAndSelect:
                self._view.clearSelection()
                if index.isValid():
                    self._view._select_index_row(index.row())
            elif flag & QItemSelectionModel.SelectionFlag.Select:
                if index.isValid():
                    self._view._select_index_row(index.row())

        def select(self, selection, flag=0):
            if flag & QItemSelectionModel.SelectionFlag.Clear:
                self._view.clearSelection()
            for r in selection.rows:
                self._view._select_index_row(r)

        def isSelected(self, index):
            if not index.isValid() or not hasattr(self._view, 'selectedItems'):
                return False
            return any(getattr(it, '_row', -2) == index.row() for it in self._view.selectedItems())

        def selectedRows(self, column=0):
            if not hasattr(self._view, 'selectedItems'):
                return []
            rows = sorted({it.row() for it in self._view.selectedItems() if hasattr(it, 'row')})
            return [ModelIndex(r, column) for r in rows]

    class KeyEvent:
        def __init__(self, key, modifiers=0):
            self._key = key
            self._modifiers = modifiers
            self._accepted = True

        def key(self):
            return self._key

        def modifiers(self):
            return self._modifiers

        def accept(self):
            self._accepted = True

        def ignore(self):
            self._accepted = False

        def isAccepted(self):
            return self._accepted

    class QApplication:
        _instance = None
        _focus_widget = None
        _top_widgets = []

        def __init__(self, _argv=None):
            QApplication._instance = self
            QApplication._focus_widget = None
            QApplication._top_widgets = []

        @classmethod
        def instance(cls):
            return cls._instance

        @classmethod
        def focusWidget(cls):
            return cls._focus_widget

        @classmethod
        def topLevelWidgets(cls):
            return list(cls._top_widgets)

        @staticmethod
        def screens():
            return []

        @staticmethod
        def startDragDistance():
            return 10

        @staticmethod
        def clipboard():
            return types.SimpleNamespace(setText=lambda _t: None, text=lambda: "")

        def setApplicationName(self, _name):
            pass

        def setFont(self, _font):
            pass

        def exec(self):
            return 0

        def quit(self):
            pass

    def dispatch_key_to_focused(key):
        w = QApplication.focusWidget()
        ev = KeyEvent(key)
        curr = w
        while curr is not None:
            ev.accept()  # In Qt, QKeyEvent starts accepted before each handler unless ignored
            curr.keyPressEvent(ev)
            if ev.isAccepted():
                break
            curr = curr.parent()
        return ev

    class QStyleStub:
        def unpolish(self, _w):
            pass

        def polish(self, _w):
            pass

    class QWidget:
        customContextMenuRequested = pyqtSignal(object)

        def __init__(self, parent=None):
            self._parent = parent
            self._visible = True
            self._enabled = True
            self._tooltip = ""
            self._obj_name = ""
            self._props = {}
            self._style = QStyleStub()
            self._w = 800
            self._h = 600
            self._x = 0
            self._y = 0
            self._layout = None
            self._focus_policy = 11

        def setFocusPolicy(self, p):
            self._focus_policy = p

        def focusPolicy(self):
            return self._focus_policy

        def parent(self):
            return self._parent

        def setParent(self, p):
            self._parent = p

        def setFocus(self):
            if QApplication._focus_widget is not self:
                QApplication._focus_widget = self
                self.focusInEvent(types.SimpleNamespace())

        def hasFocus(self):
            return QApplication._focus_widget is self

        def focusInEvent(self, _event):
            pass

        def keyPressEvent(self, event):
            event.ignore()

        def showEvent(self, _event):
            pass

        def resizeEvent(self, _event):
            pass

        def closeEvent(self, _event):
            pass

        def show(self):
            self._visible = True

        def hide(self):
            self._visible = False

        def isVisible(self):
            return self._visible

        def isHidden(self):
            return not self._visible

        def close(self):
            self._visible = False

        def deleteLater(self):
            pass

        def setEnabled(self, val):
            self._enabled = bool(val)

        def setToolTip(self, t):
            self._tooltip = str(t)

        def setObjectName(self, name):
            self._obj_name = name

        def setProperty(self, k, v):
            self._props[k] = v

        def style(self):
            return self._style

        def setStyleSheet(self, _s):
            pass

        def setMinimumWidth(self, _w):
            pass

        def setMinimumHeight(self, _h):
            pass

        def setMaximumHeight(self, _h):
            pass

        def setMinimumSize(self, *_a):
            pass

        def setFixedSize(self, *_a):
            pass

        def setFixedWidth(self, w):
            self._w = w

        def setSizePolicy(self, *_a):
            pass

        def setAcceptDrops(self, *_a):
            pass

        def setContextMenuPolicy(self, *_a):
            pass

        def setCursor(self, *_a):
            pass

        def width(self):
            return self._w

        def height(self):
            return self._h

        def resize(self, w, h):
            self._w, self._h = int(w), int(h)

        def setGeometry(self, x, y, w, h):
            self._x, self._y, self._w, self._h = int(x), int(y), int(w), int(h)

        def geometry(self):
            return QRect(self._x, self._y, self._w, self._h)

        def normalGeometry(self):
            return self.geometry()

        def contentsRect(self):
            return QRect(0, 0, self._w, self._h)

        def layout(self):
            return self._layout

        def font(self):
            return QFont()

    class _Layout:
        def __init__(self, parent=None):
            self._widgets = []
            self._subs = []
            if isinstance(parent, QWidget):
                parent._layout = self
                self._parent_widget = parent
            else:
                self._parent_widget = None

        def _propagate_parent(self, pw):
            self._parent_widget = pw
            for w in self._widgets:
                if isinstance(w, QWidget) and w.parent() is None:
                    w.setParent(pw)
            for sub in self._subs:
                sub._propagate_parent(pw)

        def setContentsMargins(self, *_a):
            pass

        def contentsMargins(self):
            return types.SimpleNamespace(left=lambda: 0, right=lambda: 0, top=lambda: 0, bottom=lambda: 0)

        def setSpacing(self, *_a):
            pass

        def addWidget(self, w, **_kw):
            self._widgets.append(w)
            if self._parent_widget is not None and isinstance(w, QWidget) and w.parent() is None:
                w.setParent(self._parent_widget)

        def insertWidget(self, _idx, w, **_kw):
            self.addWidget(w)

        def addLayout(self, sub, **_kw):
            if isinstance(sub, _Layout):
                self._subs.append(sub)
                if self._parent_widget is not None:
                    sub._propagate_parent(self._parent_widget)

        def addRow(self, *args):
            for a in args:
                if isinstance(a, QWidget):
                    self.addWidget(a)

    class QVBoxLayout(_Layout):
        pass

    class QHBoxLayout(_Layout):
        pass

    class QFormLayout(_Layout):
        pass

    class QFrame(QWidget):
        class Shape:
            StyledPanel = 1

        def setFrameShape(self, *_a):
            pass

    class QLabel(QWidget):
        def __init__(self, text="", parent=None):
            super().__init__(parent)
            self._text = str(text)
            self._align = 0

        def setText(self, t):
            self._text = str(t)

        def text(self):
            return self._text

        def setAlignment(self, a):
            self._align = a

        def alignment(self):
            return self._align

        def setWordWrap(self, _w):
            pass

        def setPixmap(self, _p):
            pass

        def minimumSizeHint(self):
            return QSize(10, 20)

        def sizeHint(self):
            return QSize(100, 20)

    class QLineEdit(QWidget):
        returnPressed = pyqtSignal()
        textChanged = pyqtSignal(str)

        def __init__(self, text="", parent=None):
            super().__init__(parent)
            self._text = str(text)
            self._cursor = len(self._text)

        def setText(self, t):
            self._text = str(t)
            self._cursor = len(self._text)
            self.textChanged.emit(self._text)

        def text(self):
            return self._text

        def clear(self):
            self.setText("")

        def setPlaceholderText(self, _t):
            pass

        def setReadOnly(self, _r):
            pass

        def setClearButtonEnabled(self, _c):
            pass

        def setCursorPosition(self, pos):
            self._cursor = int(pos)

        def keyPressEvent(self, event):
            # Exact Qt C++ QLineEdit::keyPressEvent contract!
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.returnPressed.emit()
                event.ignore()
                return
            super().keyPressEvent(event)

    class QToolButton(QWidget):
        clicked = pyqtSignal(bool)

        class ToolButtonPopupMode:
            InstantPopup = 2

        def __init__(self, parent=None):
            super().__init__(parent)
            self._text = ""
            self._checked = False

        def setText(self, t):
            self._text = str(t)

        def text(self):
            return self._text

        def setIcon(self, _ic):
            pass

        def setIconSize(self, _sz):
            pass

        def setToolButtonStyle(self, _st):
            pass

        def setPopupMode(self, _m):
            pass

        def setMenu(self, _m):
            pass

        def setCheckable(self, _c):
            pass

        def setChecked(self, c):
            self._checked = bool(c)

        def click(self):
            self.clicked.emit(self._checked)

    class QPushButton(QToolButton):
        def __init__(self, text="", parent=None):
            super().__init__(parent)
            self._text = str(text)

    class QCheckBox(QPushButton):
        def isChecked(self):
            return self._checked

    class QStackedWidget(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._widgets = []
            self._idx = 0

        def addWidget(self, w):
            w.setParent(self)
            self._widgets.append(w)

        def setCurrentWidget(self, w):
            if w in self._widgets:
                self._idx = self._widgets.index(w)

        def currentWidget(self):
            return self._widgets[self._idx] if self._widgets else None

    class QTabBar(QWidget):
        def tabAt(self, _pos):
            return 0

        def setDrawBase(self, _b):
            pass

        def setExpanding(self, _b):
            pass

        def setElideMode(self, _m):
            pass

    class QTabWidget(QWidget):
        tabCloseRequested = pyqtSignal(int)
        currentChanged = pyqtSignal(int)
        tabBarClicked = pyqtSignal(int)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._tabs = []
            self._curr = -1
            self._bar = QTabBar(self)

        def tabBar(self):
            return self._bar

        def setTabsClosable(self, _b):
            pass

        def setMovable(self, _b):
            pass

        def setDocumentMode(self, _b):
            pass

        def setUsesScrollButtons(self, _b):
            pass

        def addTab(self, widget, label):
            widget.setParent(self)
            self._tabs.append([widget, str(label), ""])
            idx = len(self._tabs) - 1
            if self._curr < 0:
                self._curr = 0
            return idx

        def removeTab(self, index):
            if 0 <= index < len(self._tabs):
                self._tabs.pop(index)
                if self._curr >= len(self._tabs):
                    self._curr = len(self._tabs) - 1

        def count(self):
            return len(self._tabs)

        def widget(self, index):
            return self._tabs[index][0] if 0 <= index < len(self._tabs) else None

        def currentIndex(self):
            return self._curr

        def setCurrentIndex(self, index):
            if 0 <= index < len(self._tabs):
                changed = self._curr != index
                self._curr = index
                if changed:
                    self.currentChanged.emit(index)

        def currentWidget(self):
            return self.widget(self._curr)

        def setTabText(self, index, text):
            if 0 <= index < len(self._tabs):
                self._tabs[index][1] = str(text)

        def tabText(self, index):
            return self._tabs[index][1] if 0 <= index < len(self._tabs) else ''

        def setTabToolTip(self, index, tip):
            if 0 <= index < len(self._tabs):
                self._tabs[index][2] = str(tip)

    class QAbstractItemView(QWidget):
        class SelectionBehavior:
            SelectRows = 1

        class SelectionMode:
            ExtendedSelection = 3

        class EditTrigger:
            NoEditTriggers = 0

        class DragDropMode:
            DropOnly = 2

        class ScrollHint:
            EnsureVisible = 0
            PositionAtCenter = 3

        def __init__(self, parent=None):
            super().__init__(parent)
            self._viewport = QWidget(self)
            self._model = ItemModel(self)
            self._sel_model = QItemSelectionModel(self)
            self._scrolled_to = None

        def viewport(self):
            return self._viewport

        def model(self):
            return self._model

        def selectionModel(self):
            return self._sel_model

        def focusInEvent(self, event):
            super().focusInEvent(event)
            # Exact Qt QAbstractItemView::focusInEvent behavior: if currentIndex is invalid and rows > 0, snap to (0, 0)
            if not self._sel_model.currentIndex().isValid() and self._item_count() > 0:
                self._sel_model.setCurrentIndex(
                    self._model.index(0, 0), QItemSelectionModel.SelectionFlag.NoUpdate
                )

        def _item_count(self):
            return 0

        def _select_index_row(self, _row):
            pass

        def setSelectionBehavior(self, *_a):
            pass

        def setSelectionMode(self, *_a):
            pass

        def setEditTriggers(self, *_a):
            pass

        def setAlternatingRowColors(self, *_a):
            pass

        def setTextElideMode(self, *_a):
            pass

        def setIconSize(self, *_a):
            pass

        def setDragEnabled(self, *_a):
            pass

        def setAcceptDrops(self, *_a):
            pass

        def setDropIndicatorShown(self, *_a):
            pass

        def setDragDropMode(self, *_a):
            pass

    class QHeaderView(QWidget):
        class ResizeMode:
            Stretch = 1
            Interactive = 0

        def setSectionResizeMode(self, *_a):
            pass

        def setSortIndicatorShown(self, *_a):
            pass

        def sortIndicatorOrder(self):
            return Qt.SortOrder.AscendingOrder

        def setVisible(self, *_a):
            pass

        def setDefaultSectionSize(self, *_a):
            pass

        def setMinimumSectionSize(self, *_a):
            pass

    class QTableWidgetItem:
        def __init__(self, text=""):
            self._text = str(text)
            self._data = {}
            self._flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            self._selected = False
            self._row = -1
            self._table = None

        def text(self):
            return self._text

        def setData(self, role, val):
            self._data[role] = val

        def data(self, role):
            return self._data.get(role)

        def setFlags(self, flags):
            self._flags = int(flags)

        def flags(self):
            return self._flags

        def font(self):
            return QFont()

        def setFont(self, _f):
            pass

        def setIcon(self, _ic):
            pass

        def setForeground(self, _c):
            pass

        def setTextAlignment(self, _a):
            pass

        def isSelected(self):
            return self._selected

        def setSelected(self, val):
            if not (self._flags & Qt.ItemFlag.ItemIsSelectable) and val:
                return
            self._selected = bool(val)

        def row(self):
            return self._row

        def tableWidget(self):
            return self._table

        def __lt__(self, other):
            return self._text < other._text

    class QTableWidget(QAbstractItemView):
        doubleClicked = pyqtSignal(object)
        itemSelectionChanged = pyqtSignal()

        def __init__(self, parent=None):
            super().__init__(parent)
            self._cols = 0
            self._rows = []
            self._hidden_rows = set()
            self._h_header = QHeaderView(self)
            self._v_header = QHeaderView(self)

        def _item_count(self):
            return len(self._rows)

        def horizontalHeader(self):
            return self._h_header

        def verticalHeader(self):
            return self._v_header

        def setColumnCount(self, c):
            self._cols = int(c)

        def columnCount(self):
            return self._cols

        def setHorizontalHeaderLabels(self, _labels):
            pass

        def setShowGrid(self, _b):
            pass

        def setWordWrap(self, _b):
            pass

        def setColumnWidth(self, *_a):
            pass

        def setColumnHidden(self, *_a):
            pass

        def setSortingEnabled(self, _b):
            pass

        def setRowCount(self, r):
            r = int(r)
            if r == 0:
                self._rows = []
                self._hidden_rows.clear()
                self._sel_model.setCurrentIndex(ModelIndex(-1, -1), 0)
            else:
                while len(self._rows) < r:
                    self._rows.append([None] * max(1, self._cols))
                self._rows = self._rows[:r]

        def rowCount(self):
            return len(self._rows)

        def setItem(self, row, col, item):
            item._row = row
            item._table = self
            self._rows[row][col] = item

        def item(self, row, col=0):
            if 0 <= row < len(self._rows) and 0 <= col < len(self._rows[row]):
                return self._rows[row][col]
            return None

        def setRowHidden(self, row, hidden):
            if hidden:
                self._hidden_rows.add(row)
            else:
                self._hidden_rows.discard(row)

        def isRowHidden(self, row):
            return row in self._hidden_rows

        def clearSelection(self):
            changed = False
            for r_items in self._rows:
                for it in r_items:
                    if it is not None and it._selected:
                        it._selected = False
                        changed = True
            if changed:
                self.itemSelectionChanged.emit()

        def _select_index_row(self, row):
            if 0 <= row < len(self._rows):
                changed = False
                for it in self._rows[row]:
                    if it is not None and (it._flags & Qt.ItemFlag.ItemIsSelectable) and not it._selected:
                        it._selected = True
                        changed = True
                if changed:
                    self.itemSelectionChanged.emit()

        def selectRow(self, row):
            self.clearSelection()
            self._select_index_row(row)

        def setCurrentCell(self, row, col):
            self._sel_model.setCurrentIndex(
                self._model.index(row, col), QItemSelectionModel.SelectionFlag.ClearAndSelect
            )

        def currentRow(self):
            return self._sel_model.currentIndex().row()

        def selectedItems(self):
            out = []
            for r_items in self._rows:
                for it in r_items:
                    if it is not None and it._selected:
                        out.append(it)
            return out

        def scrollToItem(self, item, _hint=0):
            self._scrolled_to = item

    class QListView(QAbstractItemView):
        class ViewMode:
            ListMode = 0
            IconMode = 1

        class Flow:
            LeftToRight = 0
            TopToBottom = 1

        class ResizeMode:
            Adjust = 1

        class Movement:
            Static = 0

    class QListWidgetItem:
        def __init__(self, text=""):
            self._text = str(text)
            self._data = {}
            self._flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            self._selected = False
            self._hidden = False

        def text(self):
            return self._text

        def setData(self, role, val):
            self._data[role] = val

        def data(self, role):
            return self._data.get(role)

        def setFlags(self, flags):
            self._flags = int(flags)

        def setSizeHint(self, _s):
            pass

        def setTextAlignment(self, _a):
            pass

        def setToolTip(self, _t):
            pass

        def setIcon(self, _ic):
            pass

        def setForeground(self, _c):
            pass

        def font(self):
            return QFont()

        def setFont(self, _f):
            pass

        def isSelected(self):
            return self._selected

        def setSelected(self, val):
            if not (self._flags & Qt.ItemFlag.ItemIsSelectable) and val:
                return
            self._selected = bool(val)

        def setHidden(self, h):
            self._hidden = bool(h)

        def isHidden(self):
            return self._hidden

    class QListWidget(QListView):
        itemDoubleClicked = pyqtSignal(object)
        itemSelectionChanged = pyqtSignal()

        def __init__(self, parent=None):
            super().__init__(parent)
            self._items = []

        def _item_count(self):
            return len(self._items)

        def setUpdatesEnabled(self, _b):
            pass

        def setResizeMode(self, _m):
            pass

        def setMovement(self, _m):
            pass

        def setWrapping(self, _b):
            pass

        def setWordWrap(self, _b):
            pass

        def setUniformItemSizes(self, _b):
            pass

        def setViewMode(self, _m):
            pass

        def setFlow(self, _f):
            pass

        def setGridSize(self, _s):
            pass

        def setSpacing(self, _s):
            pass

        def clear(self):
            self._items = []
            self._sel_model.setCurrentIndex(ModelIndex(-1, -1), 0)

        def addItem(self, item):
            self._items.append(item)

        def count(self):
            return len(self._items)

        def item(self, idx):
            return self._items[idx] if 0 <= idx < len(self._items) else None

        def clearSelection(self):
            changed = False
            for it in self._items:
                if it._selected:
                    it._selected = False
                    changed = True
            if changed:
                self.itemSelectionChanged.emit()

        def _select_index_row(self, idx):
            if 0 <= idx < len(self._items):
                it = self._items[idx]
                if (it._flags & Qt.ItemFlag.ItemIsSelectable) and not it._selected:
                    it._selected = True
                    self.itemSelectionChanged.emit()

        def setCurrentItem(self, item, *_a):
            if item in self._items:
                idx = self._items.index(item)
                self._sel_model.setCurrentIndex(
                    self._model.index(idx, 0), QItemSelectionModel.SelectionFlag.ClearAndSelect
                )

        def currentItem(self):
            r = self._sel_model.currentIndex().row()
            return self.item(r)

        def setCurrentRow(self, row):
            self._sel_model.setCurrentIndex(
                self._model.index(row, 0), QItemSelectionModel.SelectionFlag.ClearAndSelect
            )

        def currentRow(self):
            return self._sel_model.currentIndex().row()

        def selectedItems(self):
            return [it for it in self._items if it._selected]

        def scrollToItem(self, item, _hint=0):
            self._scrolled_to = item

    class QSplitter(QWidget):
        splitterMoved = pyqtSignal(int, int)

        def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None):
            super().__init__(parent)
            self._ori = orientation
            self._children = []
            self._sizes = []

        def setOrientation(self, ori):
            self._ori = ori

        def orientation(self):
            return self._ori

        def setChildrenCollapsible(self, _b):
            pass

        def setHandleWidth(self, _w):
            pass

        def addWidget(self, w):
            w.setParent(self)
            if w not in self._children:
                self._children.append(w)

        def count(self):
            return len(self._children)

        def setStretchFactor(self, *_a):
            pass

        def setSizes(self, sizes):
            self._sizes = list(sizes)

        def sizes(self):
            return list(self._sizes)

    class QToolBar(QWidget):
        def __init__(self, _title="", parent=None):
            super().__init__(parent)

        def setMovable(self, _b):
            pass

        def setIconSize(self, _s):
            pass

        def addWidget(self, w):
            w.setParent(self)

        def addSeparator(self):
            pass

        def clear(self):
            pass

    class QStatusBar(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.last_message = ""

        def showMessage(self, msg, _timeout=0):
            self.last_message = str(msg)

    class QMenu(QWidget):
        aboutToShow = pyqtSignal()

        def clear(self):
            pass

        def addAction(self, _text):
            return types.SimpleNamespace(triggered=BoundSignal(), setEnabled=lambda _b: None)

        def addMenu(self, _text):
            return QMenu(self)

        def addSeparator(self):
            pass

        def addSection(self, _text):
            pass

        def exec(self, *_a):
            return None

    class QMainWindow(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            QApplication._top_widgets.append(self)
            self._central = None
            self._sb = QStatusBar(self)
            self._title = ""

        def setWindowTitle(self, t):
            self._title = str(t)

        def windowTitle(self):
            return self._title

        def addToolBar(self, _area, tb):
            tb.setParent(self)

        def addToolBarBreak(self, _area):
            pass

        def setCentralWidget(self, w):
            w.setParent(self)
            self._central = w

        def centralWidget(self):
            return self._central

        def setStatusBar(self, sb):
            sb.setParent(self)
            self._sb = sb

        def statusBar(self):
            return self._sb

        def isMaximized(self):
            return False

        def showMaximized(self):
            self.show()

        def showNormal(self):
            self.show()

    class QDialog(QWidget):
        class DialogCode:
            Accepted = 1

        def exec(self):
            return 0

        def accept(self):
            pass

        def reject(self):
            pass

    class QDialogButtonBox(QWidget):
        accepted = pyqtSignal()
        rejected = pyqtSignal()

        class StandardButton:
            Ok = 1
            Cancel = 2
            Close = 4

        def __init__(self, *_a, **_kw):
            super().__init__()

    class QMessageBox(QDialog):
        warnings = []

        class Icon:
            Warning = 2

        class ButtonRole:
            AcceptRole = 0
            RejectRole = 1
            DestructiveRole = 2
            ActionRole = 3

        class StandardButton:
            Yes = 1
            No = 2

        @classmethod
        def warning(cls, _parent, title, text):
            cls.warnings.append((str(title), str(text)))

        @classmethod
        def information(cls, *_a):
            pass

        @classmethod
        def question(cls, *_a):
            return cls.StandardButton.No

    class QPlainTextEdit(QWidget):
        def __init__(self, text="", parent=None):
            super().__init__(parent)
            self._text = str(text)

        def setReadOnly(self, _b):
            pass

        def setWordWrapMode(self, _m):
            pass

        def setPlainText(self, t):
            self._text = str(t)

        def toPlainText(self):
            return self._text

    class QTextBrowser(QPlainTextEdit):
        def setOpenExternalLinks(self, _b):
            pass

        def setSearchPaths(self, _p):
            pass

        def setHtml(self, h):
            self._text = str(h)

        def setTextInteractionFlags(self, _f):
            pass

        def setAlignment(self, _a):
            pass

    class QRubberBand(QWidget):
        class Shape:
            Rectangle = 0

        def __init__(self, *_a):
            super().__init__()
            self._visible = False

    class QSizePolicy:
        class Policy:
            Fixed = 0
            Expanding = 7
            Ignored = 13
            Preferred = 5

    class QColor:
        def __init__(self, *_a):
            pass

    class QFont:
        def __init__(self, *_a):
            pass

        def setBold(self, _b):
            pass

    class QFontMetrics:
        def __init__(self, _f=None):
            pass

        def elidedText(self, text, _mode, _w):
            return str(text)

    class QIcon:
        def __init__(self, *_a):
            pass

        def isNull(self):
            return False

        def pixmap(self, _sz):
            return QPixmap()

    class QPixmap:
        def __init__(self, *_a):
            pass

        def fill(self, *_a):
            pass

        @staticmethod
        def fromImage(_img):
            return QPixmap()

        def scaled(self, *_a):
            return self

        def width(self):
            return 16

        def height(self):
            return 16

    class QPainter:
        class RenderHint:
            Antialiasing = 1

        def __init__(self, *_a):
            pass

        def setRenderHint(self, *_a):
            pass

        def setPen(self, *_a):
            pass

        def setBrush(self, *_a):
            pass

        def drawEllipse(self, *_a):
            pass

        def drawLine(self, *_a):
            pass

        def drawRoundedRect(self, *_a):
            pass

        def drawArc(self, *_a):
            pass

        def drawRect(self, *_a):
            pass

        def drawPixmap(self, *_a):
            pass

        def drawText(self, *_a):
            pass

        def end(self):
            pass

    class QPen:
        def __init__(self, *_a):
            pass

    class QImageReader:
        def __init__(self, _p=""):
            pass

        def setAutoTransform(self, _b):
            pass

        def size(self):
            return QSize(0, 0)

        def read(self):
            return types.SimpleNamespace(isNull=lambda: True)

    class QFileIconProvider:
        def icon(self, _fi):
            return QIcon()

    class QKeySequence:
        def __init__(self, seq=""):
            self.seq = seq

    class QShortcut:
        registry = []

        def __init__(self, seq, parent, activated=None):
            self.seq = seq.seq if hasattr(seq, "seq") else str(seq)
            self.parent = parent
            self.activated = activated
            QShortcut.registry.append(self)

    class QTextOption:
        class WrapMode:
            WrapAnywhere = 3

    class QDesktopServices:
        @staticmethod
        def openUrl(_u):
            return True

    class QDrag:
        def __init__(self, _p=None):
            pass

        def setMimeData(self, _m):
            pass

        def exec(self, _a):
            return 0

    class QColorDialog:
        @staticmethod
        def getColor(*_a):
            return types.SimpleNamespace(isValid=lambda: False)

    class QInputDialog:
        @staticmethod
        def getText(*_a, **_kw):
            return "", False

    for name, val in {
        "QFileInfo": QFileInfo,
        "QItemSelection": QItemSelection,
        "QItemSelectionModel": QItemSelectionModel,
        "QMimeData": QMimeData,
        "QPoint": QPoint,
        "QPointF": QPointF,
        "QRect": QRect,
        "QRectF": QRectF,
        "QSize": QSize,
        "QTimer": QTimer,
        "Qt": Qt,
        "QUrl": QUrl,
        "pyqtSignal": pyqtSignal,
    }.items():
        setattr(qtcore, name, val)

    for name, val in {
        "QColor": QColor,
        "QDesktopServices": QDesktopServices,
        "QDrag": QDrag,
        "QFont": QFont,
        "QFontMetrics": QFontMetrics,
        "QIcon": QIcon,
        "QImageReader": QImageReader,
        "QKeySequence": QKeySequence,
        "QPainter": QPainter,
        "QPen": QPen,
        "QPixmap": QPixmap,
        "QShortcut": QShortcut,
        "QTextOption": QTextOption,
    }.items():
        setattr(qtgui, name, val)

    for name, val in {
        "QAbstractItemView": QAbstractItemView,
        "QApplication": QApplication,
        "QCheckBox": QCheckBox,
        "QColorDialog": QColorDialog,
        "QDialog": QDialog,
        "QDialogButtonBox": QDialogButtonBox,
        "QFileIconProvider": QFileIconProvider,
        "QFormLayout": QFormLayout,
        "QFrame": QFrame,
        "QHBoxLayout": QHBoxLayout,
        "QHeaderView": QHeaderView,
        "QInputDialog": QInputDialog,
        "QLabel": QLabel,
        "QLineEdit": QLineEdit,
        "QListView": QListView,
        "QListWidget": QListWidget,
        "QListWidgetItem": QListWidgetItem,
        "QMainWindow": QMainWindow,
        "QMenu": QMenu,
        "QMessageBox": QMessageBox,
        "QPlainTextEdit": QPlainTextEdit,
        "QPushButton": QPushButton,
        "QRubberBand": QRubberBand,
        "QSizePolicy": QSizePolicy,
        "QSplitter": QSplitter,
        "QStackedWidget": QStackedWidget,
        "QStatusBar": QStatusBar,
        "QTableWidget": QTableWidget,
        "QTableWidgetItem": QTableWidgetItem,
        "QTabWidget": QTabWidget,
        "QTextBrowser": QTextBrowser,
        "QToolBar": QToolBar,
        "QToolButton": QToolButton,
        "QVBoxLayout": QVBoxLayout,
        "QWidget": QWidget,
    }.items():
        setattr(qtwidgets, name, val)

    pyqt6_pkg.QtCore = qtcore
    pyqt6_pkg.QtGui = qtgui
    pyqt6_pkg.QtWidgets = qtwidgets
    return (
        {
            "PyQt6": pyqt6_pkg,
            "PyQt6.QtCore": qtcore,
            "PyQt6.QtGui": qtgui,
            "PyQt6.QtWidgets": qtwidgets,
        },
        QApplication,
        QMessageBox,
        QShortcut,
        Qt,
        dispatch_key_to_focused,
    )


def _build_tk_stub_modules():
    """Headless stub of tkinter/ttk when _tkinter is not compiled into the Python runtime."""
    tk_mod = types.ModuleType("tkinter")
    ttk_mod = types.ModuleType("tkinter.ttk")
    msg_mod = types.ModuleType("tkinter.messagebox")
    dlg_mod = types.ModuleType("tkinter.simpledialog")

    tk_mod.X = "x"
    tk_mod.Y = "y"
    tk_mod.BOTH = "both"
    tk_mod.LEFT = "left"
    tk_mod.RIGHT = "right"
    tk_mod.END = "end"
    tk_mod.E = "e"

    class StringVar:
        def __init__(self, value=""):
            self._val = str(value)
            self._traces = []

        def get(self):
            return self._val

        def set(self, val):
            self._val = str(val)
            for cb in list(self._traces):
                cb()

        def trace_add(self, _mode, callback):
            self._traces.append(callback)

    class BaseWidget:
        def __init__(self, master=None, **_kwargs):
            self.master = master
            self.bindings = {}
            self._children_widgets = []
            if master is not None and hasattr(master, "_children_widgets"):
                master._children_widgets.append(self)

        def pack(self, **_kw):
            pass

        def grid(self, **_kw):
            pass

        def grid_forget(self):
            pass

        def grid_propagate(self, _b):
            pass

        def rowconfigure(self, *_a, **_kw):
            pass

        def columnconfigure(self, *_a, **_kw):
            pass

        def bind(self, seq, func):
            self.bindings[seq] = func

        def focus_set(self):
            Tk._focused = self

        def winfo_children(self):
            return list(self._children_widgets)

        def destroy(self):
            if self.master and hasattr(self.master, "_children_widgets"):
                if self in self.master._children_widgets:
                    self.master._children_widgets.remove(self)

        def configure(self, **_kw):
            pass

        def __setitem__(self, k, v):
            setattr(self, k, v)

    class Tk(BaseWidget):
        _instance = None
        _focused = None

        def __init__(self):
            super().__init__(None)
            Tk._instance = self

        def title(self, _t):
            pass

        def geometry(self, _g):
            pass

        def minsize(self, *_a):
            pass

        def after_idle(self, cb):
            cb()

        def after(self, _ms, cb):
            cb()

        def protocol(self, *_a):
            pass

        def mainloop(self):
            pass

    class Notebook(BaseWidget):
        def __init__(self, master=None, **_kw):
            super().__init__(master, **_kw)
            self._tabs = []
            self._sel = None

        def add(self, child, text=""):
            tid = f"tab_{len(self._tabs)}"
            self._tabs.append((tid, child, text))
            if self._sel is None:
                self._sel = tid

        def select(self, tab_Or_none=None):
            if tab_Or_none is None:
                return self._sel or ""
            for tid, w, _ in self._tabs:
                if tid == tab_Or_none or w is tab_Or_none:
                    self._sel = tid
                    break
            return self._sel or ""

        def tabs(self):
            return tuple(tid for tid, _, _ in self._tabs)

        def nametowidget(self, tid):
            for t, w, _ in self._tabs:
                if t == tid:
                    return w
            return None

        def tab(self, tab_obj, **_kw):
            pass

    class Treeview(BaseWidget):
        def __init__(self, master=None, **_kw):
            super().__init__(master, **_kw)
            self._items = []
            self._sel = ()
            self._focus_iid = ""
            self._seen = []

        def heading(self, *_a, **_kw):
            pass

        def column(self, *_a, **_kw):
            pass

        def yview(self, *_a):
            pass

        def tag_configure(self, *_a, **_kw):
            pass

        def get_children(self):
            return tuple(self._items)

        def delete(self, item):
            if item in self._items:
                self._items.remove(item)

        def insert(self, _parent, _idx, iid=None, **_kw):
            key = str(iid)
            self._items.append(key)
            return key

        def selection(self):
            return tuple(self._sel)

        def selection_set(self, items):
            if isinstance(items, str):
                self._sel = (items,) if items else ()
            else:
                self._sel = tuple(items)

        def focus(self, iid=None):
            if iid is None:
                return self._focus_iid
            self._focus_iid = str(iid)
            return self._focus_iid

        def see(self, iid):
            self._seen.append(str(iid))

    warnings = []
    msg_mod.showwarning = lambda title, text: warnings.append((str(title), str(text)))
    msg_mod.askyesno = lambda *_a: False
    msg_mod.askyesnocancel = lambda *_a: None
    dlg_mod.askstring = lambda *_a, **_kw: None

    tk_mod.StringVar = StringVar
    tk_mod.Tk = Tk
    class Menu(BaseWidget):
        def add_command(self, **_kw):
            pass

        def add_separator(self):
            pass

        def tk_popup(self, *_a):
            pass

    tk_mod.Menu = Menu
    tk_mod.messagebox = msg_mod
    tk_mod.simpledialog = dlg_mod
    tk_mod.ttk = ttk_mod

    ttk_mod.Frame = BaseWidget
    ttk_mod.LabelFrame = BaseWidget
    ttk_mod.Button = BaseWidget
    ttk_mod.Entry = BaseWidget
    ttk_mod.Label = BaseWidget
    class Scrollbar(BaseWidget):
        def set(self, *_a):
            pass

    ttk_mod.Scrollbar = Scrollbar
    ttk_mod.Menubutton = BaseWidget
    ttk_mod.Notebook = Notebook
    ttk_mod.Treeview = Treeview
    ttk_mod.Style = lambda *_a: types.SimpleNamespace(configure=lambda *_a, **_kw: None)

    return (
        {
            "tkinter": tk_mod,
            "tkinter.ttk": ttk_mod,
            "tkinter.messagebox": msg_mod,
            "tkinter.simpledialog": dlg_mod,
        },
        Tk,
        warnings,
    )


class TestPyQuadDirCore(unittest.TestCase):
    def test_format_size(self) -> None:
        self.assertEqual(pyquaddir.format_size(0), "0 B")
        self.assertEqual(pyquaddir.format_size(512), "512 B")
        self.assertEqual(pyquaddir.format_size(2048), "2.0 KB")

    def test_unique_target_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            first = pyquaddir.get_unique_target_path(tmp_path, "sample.txt")
            self.assertEqual(first.name, "sample.txt")
            first.write_text("hello", encoding="utf-8")

            second = pyquaddir.get_unique_target_path(tmp_path, "sample.txt")
            self.assertEqual(second.name, "sample (1).txt")

    def test_match_color_hex(self) -> None:
        rules = pyquaddir.DEFAULT_COLOR_RULES
        dir_col = pyquaddir.match_color_hex(rules, dark_mode=True, color_filter_enabled=True, is_dir=True, ext="")
        self.assertEqual(dir_col, "#FBBF24")

        py_col = pyquaddir.match_color_hex(rules, dark_mode=True, color_filter_enabled=True, is_dir=False, ext=".py")
        self.assertEqual(py_col, "#A3E635")

        disabled_col = pyquaddir.match_color_hex(rules, dark_mode=True, color_filter_enabled=False, is_dir=False, ext=".py")
        self.assertIsNone(disabled_col)

    def test_icon_generator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ico_file = Path(tmp) / "pyquaddir.ico"
            out = build_exe.generate_quaddir_ico(ico_file, size=64)
            self.assertTrue(out.exists())
            data = out.read_bytes()
            self.assertGreater(len(data), 100)
            self.assertEqual(data[:4], b"\x00\x00\x01\x00")

    def test_v22_zoom_wheel_order_and_view_modes(self) -> None:
        self.assertEqual(len(pyquaddir.ZOOM_WHEEL_ORDER), 8)
        self.assertEqual(pyquaddir.ZOOM_WHEEL_ORDER[0], "details")
        self.assertEqual(pyquaddir.ZOOM_WHEEL_ORDER[-1], "extra_large_icons")
        for mode in pyquaddir.ZOOM_WHEEL_ORDER:
            self.assertIn(mode, pyquaddir.VIEW_MODE_LABELS)

    def test_v24_url_decode_and_safe_norm_path(self) -> None:
        norm = pyquaddir.safe_norm_path(r"\\?\G:\CloudDrive\Project\report.xlsx")
        self.assertFalse(norm.startswith(r"\\?\\"))
        self.assertTrue(norm.endswith(r"CloudDrive\Project\report.xlsx"))

        decoded = pyquaddir.normalize_user_input_path(
            "file:///G:/%EB%82%B4%20%EB%93%9C%EB%9D%BC%EC%9D%B4%EB%B8%8C/Docs/400.html"
        )
        self.assertIn("내 드라이브", decoded)
        self.assertTrue(decoded.endswith("400.html"))

    def test_v24_diagnose_file_health_and_xlsx_parser(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)

            # 1) Empty 0-byte file
            empty_f = tmp_p / "empty.pdf"
            empty_f.write_bytes(b"")
            res_empty = pyquaddir.diagnose_file_health(str(empty_f))
            self.assertEqual(res_empty["status"], "empty")

            # 2) OLE2 (.xls) saved with .xlsx extension
            fake_xlsx = tmp_p / "legacy.xlsx"
            fake_xlsx.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64)
            res_xls = pyquaddir.diagnose_file_health(str(fake_xlsx))
            self.assertEqual(res_xls["status"], "ext_mismatch")
            self.assertEqual(res_xls["suggested_ext"], ".xls")

            # 3) DRM encrypted signature
            drm_f = tmp_p / "secured.xlsx"
            drm_f.write_bytes(b"FASOO DRM HEADER v5.0" + b"\x00" * 64)
            res_drm = pyquaddir.diagnose_file_health(str(drm_f))
            self.assertEqual(res_drm["status"], "drm_encrypted")

            # 4) Valid minimal .xlsx file & built-in sheet parser
            valid_xlsx = tmp_p / "valid.xlsx"
            with zipfile.ZipFile(valid_xlsx, "w") as zf:
                zf.writestr(
                    "xl/workbook.xml",
                    '<?xml version="1.0"?><workbook><sheets><sheet name="Summary" sheetId="1"/></sheets></workbook>',
                )
                zf.writestr(
                    "xl/sharedStrings.xml",
                    '<?xml version="1.0"?><sst><si><t>Item</t></si><si><t>Status</t></si></sst>',
                )
                zf.writestr(
                    "xl/worksheets/sheet1.xml",
                    '<?xml version="1.0"?><worksheet><sheetData>'
                    '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
                    "</sheetData></worksheet>",
                )
            res_ok = pyquaddir.diagnose_file_health(str(valid_xlsx))
            self.assertEqual(res_ok["status"], "ok")

            sheets, err = pyquaddir.parse_xlsx_preview_sheets(str(valid_xlsx))
            self.assertEqual(err, "")
            self.assertEqual(len(sheets), 1)
            self.assertEqual(sheets[0][0], "Summary")
            self.assertEqual(sheets[0][1][0], ["Item", "Status"])

    def test_v25_resolve_restorable_dir_and_config_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            sub_dir = tmp_p / "existing_parent" / "deleted_child" / "grandchild"
            (tmp_p / "existing_parent").mkdir(parents=True, exist_ok=True)

            # Even when deleted_child/grandchild no longer exists, resolve_restorable_dir finds existing_parent
            restored = pyquaddir.resolve_restorable_dir(str(sub_dir))
            self.assertEqual(restored, pyquaddir.safe_norm_path(str(tmp_p / "existing_parent")))

            candidates = pyquaddir.get_config_candidate_paths()
            self.assertGreaterEqual(len(candidates), 2)


class TestAddressBarNavigationRegression(unittest.TestCase):
    """v3.1.1+ regression tests for address bar Enter propagation, path normalization, and file selection."""

    def test_normalize_quotes_slashes_unicode_bidi_and_file_urls(self) -> None:
        # 1) Explorer 'Copy as path' quotes, trailing slashes, whitespace/newlines, and Windows Properties bidi chars
        cases = [
            ('  "D:\\a\\b\\last_dir"  ', r"D:\a\b\last_dir"),
            ('  "D:\\a\\b\\last_dir\\" \r\n', r"D:\a\b\last_dir"),
            ("'\u202aD:/a/b/last_dir/\u202c'", r"D:\a\b\last_dir"),
            ("\u202a\"D:\\a\\b\\last_dir\\report.xlsx\"\u200b\ufeff", r"D:\a\b\last_dir\report.xlsx"),
            ("\u200e\u2066D:\\한글 폴더\\최종 보고서\\\u2069", r"D:\한글 폴더\최종 보고서"),
            ('"file:///D:/a/b/last%20dir/%EB%B3%B4%EA%B3%A0%EC%84%9C.xlsx"', r"D:\a\b\last dir\보고서.xlsx"),
            ("file://localhost/D:/a/b/last_dir/", r"D:\a\b\last_dir"),
            ("file:///D|/a/b/last_dir/", r"D:\a\b\last_dir"),
            (r"\\?\D:\a\b\last_dir\\", r"D:\a\b\last_dir"),
            (r"\\?\UNC\fileserver\share\team_docs\\", r"\\fileserver\share\team_docs"),
            ("D:", r"D:\\"[:-1]),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(pyquaddir.normalize_user_input_path(raw), expected)

        # 2) Valid trailing apostrophe in unquoted folder name must NOT be stripped, whereas paired quotes ARE stripped
        with tempfile.TemporaryDirectory() as tmp:
            apostrophe_dir = Path(tmp) / "teachers'"
            apostrophe_dir.mkdir(parents=True, exist_ok=True)
            norm_unquoted = pyquaddir.normalize_user_input_path(str(apostrophe_dir))
            self.assertTrue(norm_unquoted.endswith("teachers'"))

            # Literal '%20' filename that actually exists on disk must NOT be corrupted by URL unquoting
            literal_pct_file = apostrophe_dir / "rate_100%20verified.txt"
            literal_pct_file.write_text("ok", encoding="utf-8")
            norm_pct = pyquaddir.normalize_user_input_path(f'"{literal_pct_file}"')
            self.assertEqual(pyquaddir.safe_norm_path(norm_pct), pyquaddir.safe_norm_path(str(literal_pct_file)))

    def test_resolve_address_bar_target_leaf_dir_existing_file_and_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            last_dir = root / "a" / "b" / "last_dir"
            last_dir.mkdir(parents=True, exist_ok=True)
            report_file = last_dir / "report.xlsx"
            report_file.write_bytes(b"PK\x03\x04dummy")

            norm_last_dir = pyquaddir.safe_norm_path(str(last_dir))
            norm_report = pyquaddir.safe_norm_path(str(report_file))

            # Directory variants (quoted, trailing slash, bidi control chars, file:/// URL) -> stays in last_dir
            dir_inputs = [
                str(last_dir),
                f'  "{last_dir}{os.sep}" \r\n',
                f"\u202a{last_dir}\u202c",
                last_dir.as_uri() + "/",
            ]
            for inp in dir_inputs:
                res = pyquaddir.resolve_address_bar_target(inp)
                self.assertEqual(res["kind"], "dir", inp)
                self.assertEqual(res["target_dir"], norm_last_dir, inp)
                self.assertEqual(res["select_file"], "", inp)

            # Existing file variants -> navigates to last_dir and marks report.xlsx for selection
            file_inputs = [
                str(report_file),
                f'\u202a"{report_file}"\ufeff',
                report_file.as_uri(),
            ]
            for inp in file_inputs:
                res = pyquaddir.resolve_address_bar_target(inp)
                self.assertEqual(res["kind"], "existing_file", inp)
                self.assertEqual(res["target_dir"], norm_last_dir, inp)
                self.assertEqual(res["select_file"], norm_report, inp)

            # Non-existent leaf file inside existing last_dir -> falls back safely to last_dir
            missing_file_path = last_dir / "new_file.txt"
            res_missing_file = pyquaddir.resolve_address_bar_target(f'"{missing_file_path}"')
            self.assertEqual(res_missing_file["kind"], "missing_file_in_existing_dir")
            self.assertEqual(res_missing_file["target_dir"], norm_last_dir)
            self.assertEqual(res_missing_file["missing_leaf_name"], "new_file.txt")

            # Non-existent directory or trailing-slash path -> must report not_found (never silently misrouted)
            for bad_inp in [
                str(last_dir / "missing_subfolder"),
                str(last_dir / "2026.11"),
                f"{missing_file_path}{os.sep}",
                str(root / "no_such_parent" / "new_file.txt"),
            ]:
                res_bad = pyquaddir.resolve_address_bar_target(bad_inp)
                self.assertEqual(res_bad["kind"], "not_found", bad_inp)

    def test_qt_address_bar_enter_does_not_bounce_to_parent_and_selects_file(self) -> None:
        """
        Verifies across all 4 panes (both Details table view and Icon list view, populated and empty leaf dirs):
          1) Pasting a directory path + Enter stays in `last_dir` and NEVER bounces to parent `b` via `..` row 0.
          2) Pasting an existing file path + Enter navigates to `last_dir`, selects the file, and does NOT execute it.
          3) Explicit `navigate_to(file_path, activate_file=True)` preserves backward-compatible activation.
          4) Pasting `last_dir/new_file.txt` safely enters `last_dir` with status notice and zero modal warning.
        """
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            profile_dir = base / "profile"
            profile_dir.mkdir(parents=True, exist_ok=True)
            start_dir = base / "start_here"
            start_dir.mkdir(parents=True, exist_ok=True)

            parent_b = base / "a" / "b"
            leaf_dir = parent_b / "last_dir"
            empty_leaf = parent_b / "empty_last_dir"
            sub_inside_leaf = leaf_dir / "00_child_folder"
            sub_inside_leaf.mkdir(parents=True, exist_ok=True)
            empty_leaf.mkdir(parents=True, exist_ok=True)

            alpha_file = leaf_dir / "alpha.txt"
            target_file = leaf_dir / "target_report.txt"
            alpha_file.write_text("alpha", encoding="utf-8")
            target_file.write_text("report body", encoding="utf-8")

            norm_leaf = pyquaddir.safe_norm_path(str(leaf_dir))
            norm_empty_leaf = pyquaddir.safe_norm_path(str(empty_leaf))
            norm_target_file = pyquaddir.safe_norm_path(str(target_file))

            has_real_pyqt6 = False
            try:
                import PyQt6.QtWidgets  # noqa: F401
                has_real_pyqt6 = True
            except ImportError:
                has_real_pyqt6 = False

            if has_real_pyqt6:
                probe_code = (
                    "import os, sys\n"
                    "from unittest import mock\n"
                    "from PyQt6.QtCore import QTimer, Qt\n"
                    "from PyQt6.QtWidgets import QApplication, QMessageBox\n"
                    "from PyQt6.QtTest import QTest\n"
                    f"sys.path.insert(0, {str(ROOT_DIR)!r})\n"
                    "import pyquaddir\n"
                    f"pyquaddir.set_active_profile({str(profile_dir)!r})\n"
                    f"pyquaddir.save_app_config({{'pane_tabs': [[{str(start_dir)!r}]] * 4}})\n"
                    "orig_exec = QApplication.exec\n"
                    "errors = []\n"
                    "def run_Scenario():\n"
                    "    app = QApplication.instance()\n"
                    "    win = next(w for w in app.topLevelWidgets() if hasattr(w, 'panes'))\n"
                    "    try:\n"
                    "        win._is_initializing = False\n"
                    "        with mock.patch.object(pyquaddir, 'open_path_with_os') as mock_open, \\\n"
                    "             mock.patch.object(QMessageBox, 'warning') as mock_warn:\n"
                    "            for p_idx, v_mode in enumerate(['details', 'medium_icons', 'tiles', 'content']):\n"
                    "                pane = win.panes[p_idx]\n"
                    "                tab = pane.current_tab()\n"
                    "                tab.set_view_mode(v_mode)\n"
                    "                tab.address_edit.setFocus()\n"
                    f"                tab.address_edit.setText('\\u202a\"' + {str(leaf_dir)!r} + '\\\\\"')\n"
                    "                QTest.keyClick(tab.address_edit, Qt.Key.Key_Return)\n"
                    "                app.processEvents()\n"
                    f"                assert tab.current_path == {norm_leaf!r}, (p_idx, v_mode, tab.current_path)\n"
                    "                assert win.active_pane_index == p_idx\n"
                    "                # Empty leaf dir must also stay in empty_last_dir (never bounce via '..')\n"
                    "                tab.address_edit.setFocus()\n"
                    f"                tab.address_edit.setText({str(empty_leaf)!r})\n"
                    "                QTest.keyClick(tab.address_edit, Qt.Key.Key_Return)\n"
                    "                app.processEvents()\n"
                    f"                assert tab.current_path == {norm_empty_leaf!r}, (p_idx, tab.current_path)\n"
                    "                # Existing file path selects file in leaf_dir without launching external app\n"
                    "                tab.address_edit.setFocus()\n"
                    f"                tab.address_edit.setText('\"' + {str(target_file)!r} + '\"')\n"
                    "                QTest.keyClick(tab.address_edit, Qt.Key.Key_Return)\n"
                    "                app.processEvents()\n"
                    f"                assert tab.current_path == {norm_leaf!r}\n"
                    f"                assert [pyquaddir.safe_norm_path(x) for x in tab.selected_file_paths()] == [{norm_target_file!r}]\n"
                    "                assert mock_open.call_count == 0\n"
                    "            # Non-existent file in existing leaf_dir lands in leaf_dir without warning dialog\n"
                    "            tab0 = win.panes[0].current_tab()\n"
                    f"            tab0.navigate_to({str(start_dir)!r})\n"
                    "            tab0.address_edit.setFocus()\n"
                    f"            tab0.address_edit.setText({str(leaf_dir / 'new_draft.xlsx')!r})\n"
                    "            QTest.keyClick(tab0.address_edit, Qt.Key.Key_Return)\n"
                    "            app.processEvents()\n"
                    f"            assert tab0.current_path == {norm_leaf!r}\n"
                    "            assert mock_warn.call_count == 0\n"
                    "            # Explicit activate_file=True still invokes activation\n"
                    f"            assert tab0.navigate_to({str(target_file)!r}, activate_file=True) is True\n"
                    "            assert mock_open.call_count == 1\n"
                    "    except BaseException as exc:\n"
                    "        import traceback\n"
                    "        errors.append(traceback.format_exc())\n"
                    "    finally:\n"
                    "        win.close()\n"
                    "        app.quit()\n"
                    "QApplication.exec = lambda self=None: (QTimer.singleShot(120, run_Scenario), orig_exec())[1]\n"
                    "try:\n"
                    "    pyquaddir.run_pyqt6_app()\n"
                    "except SystemExit as e:\n"
                    "    assert e.code == 0\n"
                    "assert not errors, '\\n'.join(errors)\n"
                )
                env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONUTF8="1")
                proc = subprocess.run(
                    [sys.executable, "-c", probe_code],
                    cwd=str(ROOT_DIR),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            else:
                stub_mods, QApplication, QMessageBox, _QShortcut, Qt, dispatch_key = _build_qt_propagation_stub_modules()
                pyquaddir.set_active_profile(str(profile_dir))
                try:
                    pyquaddir.save_app_config({"pane_tabs": [[str(start_dir)]] * 4})
                    captured = {}

                    def _probe_exec(_self=None):
                        win = QApplication.topLevelWidgets()[-1]
                        win._is_initializing = False
                        captured["win"] = win
                        with mock.patch.object(pyquaddir, "open_path_with_os") as mock_open:
                            for p_idx, v_mode in enumerate(["details", "medium_icons", "tiles", "content"]):
                                pane = win.panes[p_idx]
                                tab = pane.current_tab()
                                tab.set_view_mode(v_mode)

                                # 1) Directory path paste + Key_Return (with bidi + quotes + trailing slash)
                                QMessageBox.warnings.clear()
                                tab.address_edit.setFocus()
                                self.assertEqual(win.active_pane_index, p_idx)
                                tab.address_edit.setText(str(leaf_dir))
                                ev = dispatch_key(Qt.Key.Key_Return)
                                self.assertEqual(tab.current_path, norm_leaf, "Must stay in leaf_dir and not bounce to parent")
                                self.assertTrue(ev.isAccepted(), "AddressLineEdit must accept Key_Return")
                                tab.address_edit.setFocus()
                                tab.address_edit.setText(f'\u202a"{leaf_dir}{os.sep}"\u202c')
                                dispatch_key(Qt.Key.Key_Return)
                                self.assertEqual(tab.current_path, norm_leaf)
                                self.assertEqual(tab.address_edit.text(), norm_leaf)
                                # Safe focus index: current item must NOT be row 0 ('..') when entries exist
                                if v_mode in ("details", "content"):
                                    self.assertGreater(tab.table.currentRow(), 0)
                                else:
                                    self.assertGreater(tab.icon_list.currentRow(), 0)

                                # 2) Empty leaf directory paste + Key_Enter must ALSO stay in empty_last_dir
                                tab.address_edit.setFocus()
                                tab.address_edit.setText(str(empty_leaf))
                                ev_empty = dispatch_key(Qt.Key.Key_Enter)
                                self.assertTrue(ev_empty.isAccepted())
                                self.assertEqual(tab.current_path, norm_empty_leaf)

                                # 3) Existing file path paste + Key_Return -> enters leaf_dir, selects file, zero external launch
                                tab.address_edit.setFocus()
                                tab.address_edit.setText(f'"{target_file}"')
                                dispatch_key(Qt.Key.Key_Return)
                                self.assertEqual(tab.current_path, norm_leaf)
                                self.assertEqual(
                                    [pyquaddir.safe_norm_path(p) for p in tab.selected_file_paths()],
                                    [norm_target_file],
                                )
                                self.assertEqual(mock_open.call_count, 0)

                            # 4) Non-existent leaf file in existing folder -> lands in leaf_dir with status message
                            tab0 = win.panes[0].current_tab()
                            tab0.navigate_to(str(start_dir))
                            QMessageBox.warnings.clear()
                            tab0.address_edit.setFocus()
                            tab0.address_edit.setText(str(leaf_dir / "new_file.txt"))
                            dispatch_key(Qt.Key.Key_Return)
                            self.assertEqual(tab0.current_path, norm_leaf)
                            self.assertEqual(len(QMessageBox.warnings), 0)
                            self.assertIn("new_file.txt", win.statusBar().last_message)

                            # 5) Non-existent directory -> warns and preserves current_path
                            bad_dir = str(leaf_dir / "missing_folder")
                            tab0.address_edit.setFocus()
                            tab0.address_edit.setText(bad_dir)
                            dispatch_key(Qt.Key.Key_Return)
                            self.assertEqual(tab0.current_path, norm_leaf)
                            self.assertEqual(tab0.address_edit.text(), norm_leaf)
                            self.assertEqual(len(QMessageBox.warnings), 1)

                            # 6) Shortcuts (Backspace / Delete) must be suppressed while address_edit has focus
                            tab0.address_edit.setFocus()
                            win._shortcut_up()
                            win._shortcut_delete()
                            self.assertEqual(tab0.current_path, norm_leaf)
                            self.assertTrue(target_file.exists())

                            # 7) Explicit activate_file=True preserves legacy activation API
                            self.assertTrue(tab0.navigate_to(str(target_file), activate_file=True))
                            self.assertEqual(mock_open.call_count, 1)
                        return 0

                    QApplication.exec = _probe_exec
                    with _scoped_exit_callbacks(), mock.patch.dict(sys.modules, stub_mods):
                        with self.assertRaises(SystemExit) as cm:
                            pyquaddir.run_pyqt6_app()
                        self.assertEqual(cm.exception.code, 0)
                finally:
                    pyquaddir.set_active_profile(None, None)

    def test_tk_address_bar_return_break_and_file_selection(self) -> None:
        """Verifies Tkinter fallback address bar `<Return>`/`<KP_Enter>` returns `'break'` and selects pasted files."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            profile_dir = base / "tk_profile"
            profile_dir.mkdir(parents=True, exist_ok=True)
            start_dir = base / "tk_start"
            leaf_dir = base / "a" / "b" / "last_dir"
            start_dir.mkdir(parents=True, exist_ok=True)
            leaf_dir.mkdir(parents=True, exist_ok=True)
            report_file = leaf_dir / "Report_Final.txt"
            report_file.write_text("tk report", encoding="utf-8")

            norm_leaf = pyquaddir.safe_norm_path(str(leaf_dir))
            norm_report = pyquaddir.safe_norm_path(str(report_file))

            stub_mods, TkStub, tk_warnings = _build_tk_stub_modules()
            pyquaddir.set_active_profile(str(profile_dir))
            try:
                pyquaddir.save_app_config({"pane_tabs": [[str(start_dir)]] * 4}, engine="tk")
                created_tabs = []
                orig_mainloop = TkStub.mainloop

                def _probe_mainloop(root_self):
                    def _walk_notebooks(w):
                        if hasattr(w, "_tabs"):
                            for _, tab_w, _ in w._tabs:
                                created_tabs.append(tab_w)
                        for ch in getattr(w, "_children_widgets", []):
                            _walk_notebooks(ch)

                    _walk_notebooks(root_self)

                    self.assertEqual(len(created_tabs), 4)
                    with mock.patch.object(pyquaddir, "open_path_with_os") as mock_open:
                        tab = created_tabs[1]
                        self.assertIn("<Return>", tab.addr_entry.bindings)
                        self.assertIn("<KP_Enter>", tab.addr_entry.bindings)

                        # 1) Directory path paste + <Return> returns "break" and lands on leaf_dir
                        tab.addr_var.set(f'\u202a"{leaf_dir}{os.sep}"')
                        ret = tab.addr_entry.bindings["<Return>"](None)
                        self.assertEqual(ret, "break")
                        self.assertEqual(tab.current_path, norm_leaf)
                        self.assertEqual(tab.app.active_pane_idx, 1)
                        # Tree initial focus must be on real child rather than '..parent..'
                        self.assertEqual(tab.tree.focus(), norm_report)

                        # 2) Existing file paste (even with altered letter case on case-insensitive match)
                        tab.navigate_to(str(start_dir))
                        altered_case = str(leaf_dir / "report_final.txt") if os.name == "nt" else str(report_file)
                        tab.addr_var.set(f'"{altered_case}"')
                        ret_kp = tab.addr_entry.bindings["<KP_Enter>"](None)
                        self.assertEqual(ret_kp, "break")
                        self.assertEqual(tab.current_path, norm_leaf)
                        self.assertEqual(list(tab.tree.selection()), [norm_report])
                        self.assertEqual(tab.tree.focus(), norm_report)
                        self.assertEqual(mock_open.call_count, 0)

                        # 3) Missing file leaf in existing parent directory -> lands in leaf_dir safely
                        tk_warnings.clear()
                        tab.navigate_to(str(start_dir))
                        tab.addr_var.set(str(leaf_dir / "upcoming_draft.md"))
                        self.assertEqual(tab.addr_entry.bindings["<Return>"](None), "break")
                        self.assertEqual(tab.current_path, norm_leaf)
                        self.assertEqual(len(tk_warnings), 0)
                        self.assertIn("upcoming_draft.md", tab.summary_var.get())
                    return orig_mainloop(root_self)

                TkStub.mainloop = _probe_mainloop
                with _scoped_exit_callbacks(), mock.patch.dict(sys.modules, stub_mods):
                    pyquaddir.run_tkinter_app()
            finally:
                pyquaddir.set_active_profile(None, None)


if __name__ == "__main__":
    unittest.main()
