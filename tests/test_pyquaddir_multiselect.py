#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyQuadDir v3.1.1 다중 선택 이동/복사 전수 회귀 테스트 스위트 (unittest)
========================================================================
- 실제 `pyquaddir.py`의 AST에서 `perform_file_transfer_qt`, `FileTableView`,
  `FileIconListView`, `DirectoryTab`, `ExplorerPane`, `QDirMainWindow`,
  `TkDirectoryTab`, `TkQDirApp` 및 공통 헬퍼를 직접 추출·컴파일하여 검증합니다.
- 호스트 환경에 PyQt6 / tkinter가 설치되어 있든 헤드리스 CI 샌드박스 환경이든
  동일하게 동작하도록 Qt6 `ExtendedSelection`(`setCurrentIndex` / `setCurrentItem`
  단일 인자 호출 시 `ClearAndSelect` 강제 발동, `NoUpdate` 전달 시 다중 선택 보존)과
  Tcl/Tk `ttk.Treeview`(`<ButtonPress-1>`에서 `"break"` 미반환 시 기본 클래스
  바인딩이 단일 선택으로 초기화하는 시맨틱)을 정확히 재현하는 상태 기반 하네스를 내장합니다.
"""

from __future__ import annotations

import ast
import atexit
import importlib.util
import inspect
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


def _resolve_target_pyquaddir_path() -> Path:
    env_override = os.environ.get("QDIR_TEST_TARGET")
    if env_override:
        return Path(env_override).resolve()
    here = Path(__file__).resolve().parent
    for candidate in (here / "pyquaddir.py", here.parent / "pyquaddir.py"):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"대상 pyquaddir.py 파일을 찾을 수 없습니다: {candidate}")


# ===========================================================================
# 1. Qt6 ExtendedSelection & Drag/Drop 상태 기반 시맨틱 하네스
# ===========================================================================
class _SignalInstance:
    def __init__(self) -> None:
        self._slots: List[Callable[..., Any]] = []

    def connect(self, slot: Callable[..., Any]) -> None:
        self._slots.append(slot)

    def emit(self, *args: Any) -> None:
        for slot in list(self._slots):
            try:
                sig = inspect.signature(slot)
                params = list(sig.parameters.values())
                if any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params):
                    slot(*args)
                else:
                    positional = [
                        p
                        for p in params
                        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                    ]
                    slot(*args[: len(positional)])
            except (TypeError, ValueError):
                slot(*args)


class _SignalDescriptor:
    def __init__(self, *_types: Any) -> None:
        self._attr_name = f"_sig_{id(self)}"

    def __get__(self, instance: Any, owner: Any = None) -> Any:
        if instance is None:
            return self
        sig = instance.__dict__.get(self._attr_name)
        if sig is None:
            sig = _SignalInstance()
            instance.__dict__[self._attr_name] = sig
        return sig


class _QtNamespace:
    class MouseButton:
        NoButton = 0
        LeftButton = 1
        RightButton = 2
        MiddleButton = 4

    class KeyboardModifier:
        NoModifier = 0
        ShiftModifier = 0x02000000
        ControlModifier = 0x04000000
        AltModifier = 0x08000000

    class ItemDataRole:
        DisplayRole = 0
        UserRole = 0x0100

    class ItemFlag:
        NoItemFlags = 0
        ItemIsSelectable = 1
        ItemIsEnabled = 32

    class DropAction:
        IgnoreAction = 0
        CopyAction = 1
        MoveAction = 2

    class TextElideMode:
        ElideRight = 1
        ElideMiddle = 2

    class Orientation:
        Horizontal = 1
        Vertical = 2

    class AlignmentFlag:
        AlignLeft = 1
        AlignRight = 2
        AlignHCenter = 4
        AlignCenter = 132
        AlignTop = 32
        AlignVCenter = 128

    class TextInteractionFlag:
        TextSelectableByMouse = 1

    class ContextMenuPolicy:
        CustomContextMenu = 3

    class ToolButtonStyle:
        ToolButtonIconOnly = 0
        ToolButtonTextBesideIcon = 2

    class ToolBarArea:
        TopToolBarArea = 4

    class CursorShape:
        PointingHandCursor = 13

    class FocusPolicy:
        NoFocus = 0
        StrongFocus = 11

    class Key:
        Key_Return = 0x01000004
        Key_Enter = 0x01000005
        Key_Backspace = 0x01000003


class _QPoint:
    def __init__(self, x: int = 0, y: int = 0) -> None:
        self._x = int(x)
        self._y = int(y)

    def x(self) -> int:
        return self._x

    def y(self) -> int:
        return self._y

    def __sub__(self, other: "_QPoint") -> "_QPoint":
        return _QPoint(self._x - other._x, self._y - other._y)

    def manhattanLength(self) -> int:
        return abs(self._x) + abs(self._y)


class _QPointF:
    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self._x = float(x)
        self._y = float(y)

    def toPoint(self) -> _QPoint:
        return _QPoint(int(self._x), int(self._y))


class _QSize:
    def __init__(self, w: int = 0, h: int = 0) -> None:
        self._w = int(w)
        self._h = int(h)

    def width(self) -> int:
        return self._w

    def height(self) -> int:
        return self._h


class _QRect:
    def __init__(self, *args: Any) -> None:
        if len(args) == 2 and isinstance(args[0], _QPoint) and isinstance(args[1], _QPoint):
            self._x = args[0].x()
            self._y = args[0].y()
            self._w = args[1].x() - args[0].x()
            self._h = args[1].y() - args[0].y()
        elif len(args) == 4:
            self._x, self._y, self._w, self._h = (int(v) for v in args)
        else:
            self._x, self._y, self._w, self._h = 0, 0, 0, 0

    def normalized(self) -> "_QRect":
        x1, x2 = sorted((self._x, self._x + self._w))
        y1, y2 = sorted((self._y, self._y + self._h))
        return _QRect(x1, y1, max(1, x2 - x1), max(1, y2 - y1))

    def isValid(self) -> bool:
        return self._w > 0 and self._h > 0

    def top(self) -> int:
        return self._y

    def height(self) -> int:
        return self._h

    def width(self) -> int:
        return self._w

    def left(self) -> int:
        return self._x

    def right(self) -> int:
        return self._x + self._w - 1

    def bottom(self) -> int:
        return self._y + self._h - 1

    def center(self) -> _QPoint:
        return _QPoint(self._x + self._w // 2, self._y + self._h // 2)

    def intersects(self, other: "_QRect") -> bool:
        return not (
            self.right() < other.left()
            or other.right() < self.left()
            or self.bottom() < other.top()
            or other.bottom() < self.top()
        )


class _QUrl:
    def __init__(self, url_str: str = "", local_path: Optional[str] = None) -> None:
        self._url = url_str
        self._local = local_path

    @classmethod
    def fromLocalFile(cls, path_str: str) -> "_QUrl":
        return cls(f"file://{path_str}", local_path=str(path_str))

    def isLocalFile(self) -> bool:
        return self._local is not None or self._url.startswith("file://")

    def toLocalFile(self) -> str:
        if self._local is not None:
            return self._local
        return self._url[7:]


class _QMimeData:
    def __init__(self) -> None:
        self._urls: List[_QUrl] = []

    def setUrls(self, urls: List[_QUrl]) -> None:
        self._urls = list(urls)

    def hasUrls(self) -> bool:
        return len(self._urls) > 0

    def urls(self) -> List[_QUrl]:
        return list(self._urls)


class _QDrag:
    last_executed_mime: Optional[_QMimeData] = None
    last_supported_actions: int = 0

    def __init__(self, source: Any) -> None:
        self.source = source
        self._mime: Optional[_QMimeData] = None

    def setMimeData(self, mime: _QMimeData) -> None:
        self._mime = mime

    def exec(self, actions: int = 0) -> int:
        _QDrag.last_executed_mime = self._mime
        _QDrag.last_supported_actions = actions
        return _QtNamespace.DropAction.MoveAction


class _QModelIndex:
    def __init__(self, row: int = -1, col: int = -1) -> None:
        self._row = row
        self._col = col

    def isValid(self) -> bool:
        return self._row >= 0 and self._col >= 0

    def row(self) -> int:
        return self._row

    def column(self) -> int:
        return self._col

    def parent(self) -> "_QModelIndex":
        return _QModelIndex(-1, -1)


class _QItemSelection:
    def __init__(self, top_left: Optional[_QModelIndex] = None, bottom_right: Optional[_QModelIndex] = None) -> None:
        self.ranges: List[Tuple[int, int]] = []
        if top_left is not None and bottom_right is not None and top_left.isValid() and bottom_right.isValid():
            self.select(top_left, bottom_right)

    def select(self, top_left: _QModelIndex, bottom_right: _QModelIndex) -> None:
        if top_left.isValid() and bottom_right.isValid():
            r1, r2 = sorted((top_left.row(), bottom_right.row()))
            self.ranges.append((r1, r2))


class _QItemSelectionModel:
    class SelectionFlag:
        NoUpdate = 0x0000
        Clear = 0x0001
        Select = 0x0002
        Deselect = 0x0004
        Toggle = 0x0008
        Current = 0x0010
        Rows = 0x0020
        ClearAndSelect = Clear | Select

    def __init__(self, owner_view: Any) -> None:
        self._view = owner_view
        self._current = _QModelIndex(-1, -1)

    def currentIndex(self) -> _QModelIndex:
        return self._current

    def isSelected(self, index: _QModelIndex) -> bool:
        if not index.isValid():
            return False
        return index.row() in self._view._selected_rows_state

    def isRowSelected(self, row: int, _parent: Any = None) -> bool:
        return row in self._view._selected_rows_state

    def selectedRows(self, column: int = 0) -> List[_QModelIndex]:
        return [_QModelIndex(r, column) for r in sorted(self._view._selected_rows_state)]

    def setCurrentIndex(self, index: _QModelIndex, command: int) -> None:
        self._current = index
        if command == self.SelectionFlag.NoUpdate:
            return
        if command & self.SelectionFlag.Clear:
            self._view._clear_selection_internal()
        if index.isValid() and (command & self.SelectionFlag.Select):
            self._view._select_row_internal(index.row(), True)
        elif index.isValid() and (command & self.SelectionFlag.Toggle):
            curr = index.row() in self._view._selected_rows_state
            self._view._select_row_internal(index.row(), not curr)
        self._view._sync_items_from_rows()

    def select(self, selection: Any, command: int) -> None:
        if command & self.SelectionFlag.Clear:
            self._view._clear_selection_internal()
        rows_to_apply: List[int] = []
        if isinstance(selection, _QModelIndex):
            if selection.isValid():
                rows_to_apply.append(selection.row())
        elif isinstance(selection, _QItemSelection):
            for r1, r2 in selection.ranges:
                rows_to_apply.extend(range(r1, r2 + 1))
        for r in rows_to_apply:
            if command & self.SelectionFlag.Select:
                self._view._select_row_internal(r, True)
            elif command & self.SelectionFlag.Deselect:
                self._view._select_row_internal(r, False)
        self._view._sync_items_from_rows()


class _QModelStub:
    def __init__(self, view: Any) -> None:
        self._view = view

    def index(self, row: int, col: int = 0) -> _QModelIndex:
        if 0 <= row < self._view._row_count_internal():
            return _QModelIndex(row, col)
        return _QModelIndex(-1, -1)


class _QClipboard:
    def __init__(self) -> None:
        self._text = ""

    def setText(self, text: str) -> None:
        self._text = str(text)

    def text(self) -> str:
        return self._text


class _QApplication:
    _clipboard = _QClipboard()
    _drag_dist = 10

    def __init__(self, *_args: Any) -> None:
        pass

    @classmethod
    def startDragDistance(cls) -> int:
        return cls._drag_dist

    @classmethod
    def clipboard(cls) -> _QClipboard:
        return cls._clipboard

    @classmethod
    def screens(cls) -> List[Any]:
        return []


class _QWidget:
    def __init__(self, parent: Any = None) -> None:
        self._parent = parent
        self._focus_policy = _QtNamespace.FocusPolicy.StrongFocus
        self._visible = True
        self._width = 1520
        self._height = 940
        self.customContextMenuRequested = _SignalInstance()

    def contentsRect(self) -> _QRect:
        return _QRect(0, 0, self._width, self._height)

    def setParent(self, p: Any) -> None:
        self._parent = p

    def deleteLater(self) -> None:
        pass

    def setVisible(self, v: bool) -> None:
        self._visible = bool(v)

    def setFocusPolicy(self, policy: int) -> None:
        self._focus_policy = policy

    def focusPolicy(self) -> int:
        return self._focus_policy

    def setFocus(self) -> None:
        pass

    def hasFocus(self) -> bool:
        return False

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height

    def mapToGlobal(self, pos: _QPoint) -> _QPoint:
        return pos

    def cursor(self) -> Any:
        class _Cur:
            @staticmethod
            def pos() -> _QPoint:
                return _QPoint(100, 100)

        return _Cur()

    def setContextMenuPolicy(self, _p: int) -> None:
        pass

    def setMinimumSize(self, _w: int, _h: int) -> None:
        pass

    def setSizePolicy(self, *_args: Any) -> None:
        pass

    def setFixedSize(self, *_args: Any) -> None:
        pass

    def setFixedWidth(self, *_args: Any) -> None:
        pass

    def setMinimumWidth(self, *_args: Any) -> None:
        pass

    def setMinimumHeight(self, *_args: Any) -> None:
        pass

    def setMaximumHeight(self, *_args: Any) -> None:
        pass

    def setAlignment(self, *_args: Any) -> None:
        pass

    def setWordWrap(self, *_args: Any) -> None:
        pass

    def setReadOnly(self, *_args: Any) -> None:
        pass

    def setWordWrapMode(self, *_args: Any) -> None:
        pass

    def setOpenExternalLinks(self, *_args: Any) -> None:
        pass

    def setPlainText(self, *_args: Any) -> None:
        pass

    def setTextInteractionFlags(self, *_args: Any) -> None:
        pass

    def resize(self, w: int, h: int) -> None:
        self._width = int(w)
        self._height = int(h)

    def showNormal(self) -> None:
        pass

    def setAcceptDrops(self, *_args: Any) -> None:
        pass

    def setObjectName(self, _name: str) -> None:
        pass

    def setToolTip(self, _t: str) -> None:
        pass

    def setStyleSheet(self, _s: str) -> None:
        pass

    def setUpdatesEnabled(self, _b: bool) -> None:
        pass

    def show(self) -> None:
        self._visible = True

    def hide(self) -> None:
        self._visible = False

    def isVisible(self) -> bool:
        return self._visible

    def isHidden(self) -> bool:
        return not self._visible

    def layout(self) -> Any:
        return None


class _QRubberBand(_QWidget):
    class Shape:
        Rectangle = 0

    def __init__(self, _shape: int, parent: Any = None) -> None:
        super().__init__(parent)
        self._visible = False
        self._geom = _QRect(0, 0, 0, 0)

    def setGeometry(self, rect: _QRect) -> None:
        self._geom = rect


class _QAbstractItemView(_QWidget):
    class SelectionBehavior:
        SelectRows = 1

    class SelectionMode:
        ExtendedSelection = 3

    class EditTrigger:
        NoEditTriggers = 0

    class DragDropMode:
        DropOnly = 2

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._viewport = _QWidget(self)
        self._viewport._width = 600
        self._selected_rows_state: Set[int] = set()
        self._sel_model = _QItemSelectionModel(self)
        self._model = _QModelStub(self)
        self._qt_pressed_index: _QModelIndex = _QModelIndex(-1, -1)
        self.customContextMenuRequested = _SignalInstance()

    def viewport(self) -> _QWidget:
        return self._viewport

    def selectionModel(self) -> _QItemSelectionModel:
        return self._sel_model

    def model(self) -> _QModelStub:
        return self._model

    def rootIndex(self) -> _QModelIndex:
        return _QModelIndex(-1, -1)

    def setSelectionBehavior(self, *_a: Any) -> None:
        pass

    def setSelectionMode(self, *_a: Any) -> None:
        pass

    def setEditTriggers(self, *_a: Any) -> None:
        pass

    def setDragEnabled(self, *_a: Any) -> None:
        pass

    def setAcceptDrops(self, *_a: Any) -> None:
        pass

    def setDropIndicatorShown(self, *_a: Any) -> None:
        pass

    def setDragDropMode(self, *_a: Any) -> None:
        pass

    def setIconSize(self, *_a: Any) -> None:
        pass

    def setTextElideMode(self, *_a: Any) -> None:
        pass

    def setWordWrap(self, *_a: Any) -> None:
        pass

    def _row_count_internal(self) -> int:
        return 0

    def _is_row_selectable(self, _row: int) -> bool:
        return True

    def _clear_selection_internal(self) -> None:
        self._selected_rows_state.clear()
        self._sync_items_from_rows()

    def _select_row_internal(self, row: int, selected: bool) -> None:
        if not self._is_row_selectable(row):
            return
        if selected:
            self._selected_rows_state.add(row)
        else:
            self._selected_rows_state.discard(row)

    def _sync_items_from_rows(self) -> None:
        pass

    def clearSelection(self) -> None:
        self._clear_selection_internal()

    def setCurrentIndex(self, index: _QModelIndex) -> None:
        # Qt6 QAbstractItemView::setCurrentIndex(idx) 정확한 시맨틱:
        # ExtendedSelection에서 단일 인자 호출 시 selectionCommand(idx, nullptr) == ClearAndSelect 발동!
        self._sel_model.setCurrentIndex(
            index,
            _QItemSelectionModel.SelectionFlag.ClearAndSelect | _QItemSelectionModel.SelectionFlag.Rows,
        )

    def focusInEvent(self, _event: Any) -> None:
        pass

    def mousePressEvent(self, event: Any) -> None:
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        idx = self.indexAt(pos)
        self._qt_pressed_index = idx
        mods = event.modifiers()
        if idx.isValid() and self._is_row_selectable(idx.row()):
            if mods & _QtNamespace.KeyboardModifier.ControlModifier:
                self._sel_model.setCurrentIndex(
                    idx,
                    _QItemSelectionModel.SelectionFlag.Toggle | _QItemSelectionModel.SelectionFlag.Rows,
                )
            else:
                self._sel_model.setCurrentIndex(
                    idx,
                    _QItemSelectionModel.SelectionFlag.ClearAndSelect | _QItemSelectionModel.SelectionFlag.Rows,
                )
        elif not (mods & (_QtNamespace.KeyboardModifier.ControlModifier | _QtNamespace.KeyboardModifier.ShiftModifier)):
            self.clearSelection()

    def mouseDoubleClickEvent(self, event: Any) -> None:
        # Qt6 QAbstractItemView::mouseDoubleClickEvent 정확한 시맨틱:
        # d->pressedIndex != index 이면 doubleClicked를 삼키고 mousePressEvent로 폴백함!
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        idx = self.indexAt(pos)
        if not idx.isValid() or idx.row() != self._qt_pressed_index.row():
            self.mousePressEvent(event)
            return
        if hasattr(self, "doubleClicked"):
            self.doubleClicked.emit(idx)

    def mouseMoveEvent(self, _event: Any) -> None:
        pass

    def mouseReleaseEvent(self, _event: Any) -> None:
        pass

    def dragEnterEvent(self, _event: Any) -> None:
        pass

    def dragMoveEvent(self, _event: Any) -> None:
        pass


class _QFont:
    def __init__(self, *_a: Any) -> None:
        self._bold = False

    def setBold(self, b: bool) -> None:
        self._bold = b


class _QIcon:
    def isNull(self) -> bool:
        return False


class _QColor:
    def __init__(self, hex_str: str = "#000000") -> None:
        self._hex = hex_str

    def isValid(self) -> bool:
        return True

    def name(self) -> str:
        return self._hex


class _QTableWidgetItem:
    def __init__(self, text: str = "") -> None:
        self._text = str(text)
        self._data: Dict[int, Any] = {}
        self._flags = _QtNamespace.ItemFlag.ItemIsEnabled | _QtNamespace.ItemFlag.ItemIsSelectable
        self._selected = False
        self._row = -1
        self._col = -1
        self._table: Any = None
        self._font = _QFont()

    def text(self) -> str:
        return self._text

    def setData(self, role: int, value: Any) -> None:
        self._data[role] = value

    def data(self, role: int) -> Any:
        return self._data.get(role)

    def setFlags(self, flags: int) -> None:
        self._flags = flags

    def flags(self) -> int:
        return self._flags

    def font(self) -> _QFont:
        return self._font

    def setFont(self, f: _QFont) -> None:
        self._font = f

    def setIcon(self, _ic: Any) -> None:
        pass

    def setForeground(self, _c: Any) -> None:
        pass

    def setTextAlignment(self, _a: int) -> None:
        pass

    def row(self) -> int:
        return self._row

    def isSelected(self) -> bool:
        return self._selected

    def setSelected(self, sel: bool) -> None:
        if not (self._flags & _QtNamespace.ItemFlag.ItemIsSelectable):
            return
        self._selected = bool(sel)
        if self._table is not None and self._row >= 0:
            self._table._select_row_internal(self._row, bool(sel))


class _QHeaderView:
    class ResizeMode:
        Interactive = 0
        Stretch = 1

    def setVisible(self, _b: bool) -> None:
        pass

    def setDefaultSectionSize(self, _s: int) -> None:
        pass

    def setMinimumSectionSize(self, _s: int) -> None:
        pass

    def setMinimumHeight(self, _h: int) -> None:
        pass

    def setSectionResizeMode(self, *_a: Any) -> None:
        pass

    def setSortIndicatorShown(self, _b: bool) -> None:
        pass


class _QTableWidget(_QAbstractItemView):
    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._rows = 0
        self._cols = 4
        self._cells: Dict[Tuple[int, int], _QTableWidgetItem] = {}
        self._hidden_rows: Set[int] = set()
        self._vheader = _QHeaderView()
        self._hheader = _QHeaderView()
        self._row_height = 34
        self.doubleClicked = _SignalInstance()
        self.itemSelectionChanged = _SignalInstance()

    def _row_count_internal(self) -> int:
        return self._rows

    def _is_row_selectable(self, row: int) -> bool:
        it = self._cells.get((row, 0))
        if it is None:
            return False
        return bool(it.flags() & _QtNamespace.ItemFlag.ItemIsSelectable)

    def _sync_items_from_rows(self) -> None:
        for (r, _c), it in self._cells.items():
            it._selected = r in self._selected_rows_state
        self.itemSelectionChanged.emit()

    def setColumnCount(self, c: int) -> None:
        self._cols = c

    def columnCount(self) -> int:
        return self._cols

    def setRowCount(self, r: int) -> None:
        self._rows = r
        if r == 0:
            self._cells.clear()
            self._hidden_rows.clear()
            self._selected_rows_state.clear()

    def rowCount(self) -> int:
        return self._rows

    def setHorizontalHeaderLabels(self, _labels: List[str]) -> None:
        pass

    def setAlternatingRowColors(self, _b: bool) -> None:
        pass

    def setShowGrid(self, _b: bool) -> None:
        pass

    def verticalHeader(self) -> _QHeaderView:
        return self._vheader

    def horizontalHeader(self) -> _QHeaderView:
        return self._hheader

    def setColumnWidth(self, *_a: Any) -> None:
        pass

    def setColumnHidden(self, *_a: Any) -> None:
        pass

    def setSortingEnabled(self, _b: bool) -> None:
        pass

    def setRowHidden(self, row: int, hide: bool) -> None:
        if hide:
            self._hidden_rows.add(row)
        else:
            self._hidden_rows.discard(row)

    def isRowHidden(self, row: int) -> bool:
        return row in self._hidden_rows

    def setItem(self, row: int, col: int, item: _QTableWidgetItem) -> None:
        item._row = row
        item._col = col
        item._table = self
        item._selected = row in self._selected_rows_state
        self._cells[(row, col)] = item

    def item(self, row: int, col: int) -> Optional[_QTableWidgetItem]:
        return self._cells.get((row, col))

    def selectedItems(self) -> List[_QTableWidgetItem]:
        res: List[_QTableWidgetItem] = []
        for r in sorted(self._selected_rows_state):
            for c in range(self._cols):
                it = self._cells.get((r, c))
                if it is not None and it._selected:
                    res.append(it)
        return res

    def selectRow(self, row: int) -> None:
        if 0 <= row < self._rows and self._is_row_selectable(row):
            self._selected_rows_state.add(row)
            self._sync_items_from_rows()

    def setCurrentCell(self, row: int, col: int) -> None:
        self.setCurrentIndex(_QModelIndex(row, col))

    def currentRow(self) -> int:
        return self._sel_model.currentIndex().row()

    def scrollToItem(self, _it: Any) -> None:
        pass

    def visualRect(self, idx: _QModelIndex) -> _QRect:
        if not idx.isValid() or idx.row() in self._hidden_rows:
            return _QRect(0, 0, 0, 0)
        return _QRect(0, idx.row() * self._row_height, 600, self._row_height)

    def indexAt(self, pos: _QPoint) -> _QModelIndex:
        if pos.y() < 0 or pos.x() < 0:
            return _QModelIndex(-1, -1)
        row = pos.y() // self._row_height
        col = min(self._cols - 1, max(0, pos.x() // 150))
        if 0 <= row < self._rows and row not in self._hidden_rows:
            return _QModelIndex(row, col)
        return _QModelIndex(-1, -1)


class _QListView(_QAbstractItemView):
    class ResizeMode:
        Adjust = 1

    class Movement:
        Static = 0

    class ViewMode:
        ListMode = 0
        IconMode = 1

    class Flow:
        LeftToRight = 0
        TopToBottom = 1


class _QListWidgetItem:
    def __init__(self, text: str = "") -> None:
        self._text = str(text)
        self._data: Dict[int, Any] = {}
        self._flags = _QtNamespace.ItemFlag.ItemIsEnabled | _QtNamespace.ItemFlag.ItemIsSelectable
        self._selected = False
        self._hidden = False
        self._list_widget: Any = None
        self._font = _QFont()

    def text(self) -> str:
        return self._text

    def setData(self, role: int, val: Any) -> None:
        self._data[role] = val

    def data(self, role: int) -> Any:
        return self._data.get(role)

    def setFlags(self, flags: int) -> None:
        self._flags = flags

    def flags(self) -> int:
        return self._flags

    def setSizeHint(self, _sz: Any) -> None:
        pass

    def setTextAlignment(self, _a: int) -> None:
        pass

    def setToolTip(self, _t: str) -> None:
        pass

    def setIcon(self, _ic: Any) -> None:
        pass

    def setForeground(self, _c: Any) -> None:
        pass

    def font(self) -> _QFont:
        return self._font

    def setFont(self, f: _QFont) -> None:
        self._font = f

    def isHidden(self) -> bool:
        return self._hidden

    def setHidden(self, h: bool) -> None:
        self._hidden = bool(h)

    def isSelected(self) -> bool:
        return self._selected

    def setSelected(self, sel: bool) -> None:
        if not (self._flags & _QtNamespace.ItemFlag.ItemIsSelectable):
            return
        self._selected = bool(sel)
        if self._list_widget is not None:
            idx = self._list_widget.row(self)
            if idx >= 0:
                self._list_widget._select_row_internal(idx, bool(sel))
                self._list_widget._sync_items_from_rows()


class _QListWidget(_QListView):
    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._items: List[_QListWidgetItem] = []
        self._current_item: Optional[_QListWidgetItem] = None
        self._grid_h = 80
        self._spacing = 6
        self.itemDoubleClicked = _SignalInstance()
        self.itemSelectionChanged = _SignalInstance()

    def _row_count_internal(self) -> int:
        return len(self._items)

    def _is_row_selectable(self, row: int) -> bool:
        if not (0 <= row < len(self._items)):
            return False
        return bool(self._items[row].flags() & _QtNamespace.ItemFlag.ItemIsSelectable)

    def _sync_items_from_rows(self) -> None:
        for i, it in enumerate(self._items):
            it._selected = i in self._selected_rows_state
        self.itemSelectionChanged.emit()

    def setResizeMode(self, *_a: Any) -> None:
        pass

    def setMovement(self, *_a: Any) -> None:
        pass

    def setWrapping(self, *_a: Any) -> None:
        pass

    def setUniformItemSizes(self, *_a: Any) -> None:
        pass

    def setViewMode(self, *_a: Any) -> None:
        pass

    def setFlow(self, *_a: Any) -> None:
        pass

    def setGridSize(self, sz: _QSize) -> None:
        self._grid_h = max(30, sz.height())

    def setSpacing(self, sp: int) -> None:
        self._spacing = max(0, int(sp))

    def clear(self) -> None:
        self._items.clear()
        self._selected_rows_state.clear()
        self._current_item = None

    def addItem(self, item: _QListWidgetItem) -> None:
        item._list_widget = self
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def item(self, index: int) -> Optional[_QListWidgetItem]:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def row(self, item: _QListWidgetItem) -> int:
        try:
            return self._items.index(item)
        except ValueError:
            return -1

    def indexFromItem(self, item: _QListWidgetItem) -> _QModelIndex:
        r = self.row(item)
        return _QModelIndex(r, 0) if r >= 0 else _QModelIndex(-1, -1)

    def selectedItems(self) -> List[_QListWidgetItem]:
        return [it for i, it in enumerate(self._items) if i in self._selected_rows_state and it._selected]

    def currentItem(self) -> Optional[_QListWidgetItem]:
        return self._current_item

    def setCurrentItem(
        self,
        item: Optional[_QListWidgetItem],
        command: Optional[int] = None,
    ) -> None:
        # Qt6 QListWidget::setCurrentItem 정확한 시맨틱:
        # 1-인자 호출(command is None) -> ClearAndSelect 발동하여 기존 다중 선택 파괴!
        # 2-인자 호출(command == NoUpdate) -> 선택 상태 변경 없이 현재 포커스 아이템만 변경!
        self._current_item = item
        r = self.row(item) if item is not None else -1
        idx = _QModelIndex(r, 0) if r >= 0 else _QModelIndex(-1, -1)
        effective_cmd = (
            _QItemSelectionModel.SelectionFlag.ClearAndSelect
            if command is None
            else command
        )
        self._sel_model.setCurrentIndex(idx, effective_cmd)

    def setCurrentRow(self, row: int) -> None:
        self.setCurrentItem(self.item(row))

    def scrollToItem(self, _it: Any) -> None:
        pass

    def visualItemRect(self, item: _QListWidgetItem) -> _QRect:
        r = self.row(item)
        if r < 0 or item.isHidden():
            return _QRect(0, 0, 0, 0)
        top = r * self._grid_h
        body_h = max(16, self._grid_h - self._spacing)
        return _QRect(0, top, 280, body_h)

    def itemAt(self, pos: _QPoint) -> Optional[_QListWidgetItem]:
        if pos.x() < 0 or pos.y() < 0 or pos.x() > 280:
            return None
        slot = pos.y() // self._grid_h
        offset_in_slot = pos.y() % self._grid_h
        body_h = max(16, self._grid_h - self._spacing)
        if offset_in_slot >= body_h:
            return None  # 타일 간 여백(spacing) 구간 재현
        if 0 <= slot < len(self._items) and not self._items[slot].isHidden():
            return self._items[slot]
        return None

    def indexAt(self, pos: _QPoint) -> _QModelIndex:
        it = self.itemAt(pos)
        return self.indexFromItem(it) if it is not None else _QModelIndex(-1, -1)

    def mouseDoubleClickEvent(self, event: Any) -> None:
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        idx = self.indexAt(pos)
        if not idx.isValid() or idx.row() != self._qt_pressed_index.row():
            self.mousePressEvent(event)
            return
        it = self.item(idx.row())
        if it is not None:
            self.itemDoubleClicked.emit(it)


class _QAction:
    def __init__(self, text: str) -> None:
        self._text = str(text)
        self._enabled = True
        self.triggered = _SignalInstance()

    def text(self) -> str:
        return self._text

    def setEnabled(self, b: bool) -> None:
        self._enabled = bool(b)

    def trigger(self) -> None:
        if self._enabled:
            self.triggered.emit(False)


class _QMenu(_QWidget):
    next_exec_selector: Optional[Callable[["_QMenu"], Optional[_QAction]]] = None
    last_created_menu: Optional["_QMenu"] = None

    def __init__(self, parent: Any = None, title: str = "") -> None:
        super().__init__(parent)
        self._title = title
        self.actions_list: List[_QAction] = []
        self.submenus: Dict[str, "_QMenu"] = {}
        self.sections: List[str] = []
        self.aboutToShow = _SignalInstance()
        _QMenu.last_created_menu = self

    def clear(self) -> None:
        self.actions_list.clear()
        self.submenus.clear()
        self.sections.clear()

    def addAction(self, text: str) -> _QAction:
        act = _QAction(text)
        self.actions_list.append(act)
        return act

    def addMenu(self, title: str) -> "_QMenu":
        sub = _QMenu(self, title=title)
        self.submenus[title] = sub
        return sub

    def addSeparator(self) -> None:
        pass

    def addSection(self, text: str) -> None:
        self.sections.append(text)

    def exec(self, _pos: Any = None) -> Optional[_QAction]:
        if _QMenu.next_exec_selector is not None:
            return _QMenu.next_exec_selector(self)
        return None


class _QMessageBox(_QWidget):
    class ButtonRole:
        AcceptRole = 0
        RejectRole = 1
        DestructiveRole = 2
        ActionRole = 3

    class StandardButton:
        Yes = 1
        No = 2

    class Icon:
        Warning = 2

    conflict_responder: Optional[Callable[["_QMessageBox"], Tuple[str, bool]]] = None
    warnings: List[Tuple[str, str]] = []

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._title = ""
        self._text = ""
        self._buttons: List[Tuple[str, int, object]] = []
        self._checkbox: Any = None
        self._clicked: Any = None

    def setWindowTitle(self, t: str) -> None:
        self._title = t

    def setText(self, t: str) -> None:
        self._text = t

    def setIcon(self, _i: int) -> None:
        pass

    def addButton(self, text: str, role: int) -> object:
        tok = object()
        self._buttons.append((text, role, tok))
        return tok

    def setCheckBox(self, chk: Any) -> None:
        self._checkbox = chk

    def exec(self) -> int:
        if _QMessageBox.conflict_responder is not None:
            label_match, check_all = _QMessageBox.conflict_responder(self)
            if self._checkbox is not None:
                self._checkbox.setChecked(check_all)
            for b_text, _role, tok in self._buttons:
                if label_match in b_text:
                    self._clicked = tok
                    break
        return 0

    def clickedButton(self) -> Any:
        return self._clicked

    @classmethod
    def warning(cls, _parent: Any, title: str, text: str) -> None:
        cls.warnings.append((title, text))

    @classmethod
    def information(cls, *_a: Any) -> None:
        pass

    @classmethod
    def question(cls, *_a: Any) -> int:
        return cls.StandardButton.Yes


class _QCheckBox(_QWidget):
    def __init__(self, text: str = "", parent: Any = None) -> None:
        super().__init__(parent)
        self._text = text
        self._checked = False

    def setChecked(self, b: bool) -> None:
        self._checked = bool(b)

    def isChecked(self) -> bool:
        return self._checked


class _QLineEdit(_QWidget):
    def __init__(self, text: str = "", parent: Any = None) -> None:
        super().__init__(parent)
        self._text = text
        self.returnPressed = _SignalInstance()
        self.textChanged = _SignalInstance()

    def setText(self, t: str) -> None:
        self._text = str(t)
        self.textChanged.emit(self._text)

    def text(self) -> str:
        return self._text

    def setPlaceholderText(self, _t: str) -> None:
        pass

    def setClearButtonEnabled(self, _b: bool) -> None:
        pass

    def setReadOnly(self, _b: bool) -> None:
        pass

    def setCursorPosition(self, _i: int) -> None:
        pass


class _QToolButton(_QWidget):
    class ToolButtonPopupMode:
        InstantPopup = 2

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.clicked = _SignalInstance()
        self._menu: Any = None

    def setText(self, _t: str) -> None:
        pass

    def setIcon(self, _i: Any) -> None:
        pass

    def setIconSize(self, _s: Any) -> None:
        pass

    def setToolButtonStyle(self, _s: int) -> None:
        pass

    def setPopupMode(self, _m: int) -> None:
        pass

    def setMenu(self, m: Any) -> None:
        self._menu = m

    def setCheckable(self, _b: bool) -> None:
        pass

    def setChecked(self, _b: bool) -> None:
        pass

    def setEnabled(self, _b: bool) -> None:
        pass

    def setCursor(self, _c: int) -> None:
        pass


class _QLabel(_QWidget):
    def __init__(self, text: str = "", parent: Any = None) -> None:
        super().__init__(parent)
        self._text = str(text)

    def setText(self, t: str) -> None:
        self._text = str(t)

    def text(self) -> str:
        return self._text


class _QStackedWidget(_QWidget):
    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._widgets: List[_QWidget] = []
        self._curr: Optional[_QWidget] = None

    def addWidget(self, w: _QWidget) -> None:
        self._widgets.append(w)
        if self._curr is None:
            self._curr = w

    def setCurrentWidget(self, w: _QWidget) -> None:
        self._curr = w

    def currentWidget(self) -> Optional[_QWidget]:
        return self._curr


class _QLayout:
    def __init__(self, *_a: Any) -> None:
        pass

    def setContentsMargins(self, *_a: Any) -> None:
        pass

    def setSpacing(self, *_a: Any) -> None:
        pass

    def addWidget(self, *_a: Any, **_k: Any) -> None:
        pass

    def addLayout(self, *_a: Any, **_k: Any) -> None:
        pass

    def insertWidget(self, *_a: Any, **_k: Any) -> None:
        pass

    def contentsMargins(self) -> Any:
        class _M:
            @staticmethod
            def left() -> int:
                return 0

            @staticmethod
            def right() -> int:
                return 0

        return _M()


class _QTabBar(_QWidget):
    def setDrawBase(self, _b: bool) -> None:
        pass

    def setExpanding(self, _b: bool) -> None:
        pass

    def setElideMode(self, _m: int) -> None:
        pass


class _QTabWidget(_QWidget):
    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._tabs: List[_QWidget] = []
        self._titles: List[str] = []
        self._curr_idx = -1
        self._bar = _QTabBar(self)
        self.tabCloseRequested = _SignalInstance()
        self.currentChanged = _SignalInstance()
        self.tabBarClicked = _SignalInstance()

    def tabBar(self) -> _QTabBar:
        return self._bar

    def setTabsClosable(self, _b: bool) -> None:
        pass

    def setMovable(self, _b: bool) -> None:
        pass

    def setDocumentMode(self, _b: bool) -> None:
        pass

    def setUsesScrollButtons(self, _b: bool) -> None:
        pass

    def addTab(self, widget: _QWidget, label: str) -> int:
        self._tabs.append(widget)
        self._titles.append(label)
        idx = len(self._tabs) - 1
        if self._curr_idx < 0:
            self._curr_idx = 0
        return idx

    def count(self) -> int:
        return len(self._tabs)

    def widget(self, idx: int) -> Optional[_QWidget]:
        return self._tabs[idx] if 0 <= idx < len(self._tabs) else None

    def currentIndex(self) -> int:
        return self._curr_idx

    def currentWidget(self) -> Optional[_QWidget]:
        return self.widget(self._curr_idx)

    def setCurrentIndex(self, idx: int) -> None:
        if 0 <= idx < len(self._tabs):
            self._curr_idx = idx
            self.currentChanged.emit(idx)

    def setTabText(self, idx: int, text: str) -> None:
        if 0 <= idx < len(self._titles):
            self._titles[idx] = text

    def setTabToolTip(self, *_a: Any) -> None:
        pass

    def removeTab(self, idx: int) -> None:
        if 0 <= idx < len(self._tabs):
            self._tabs.pop(idx)
            self._titles.pop(idx)
            self._curr_idx = min(self._curr_idx, len(self._tabs) - 1)


class _QFrame(_QWidget):
    class Shape:
        StyledPanel = 6

    def setFrameShape(self, _s: int) -> None:
        pass

    def setProperty(self, _k: str, _v: Any) -> None:
        pass

    def style(self) -> Any:
        class _St:
            @staticmethod
            def unpolish(_w: Any) -> None:
                pass

            @staticmethod
            def polish(_w: Any) -> None:
                pass

        return _St()


class _QStatusBar(_QWidget):
    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.last_message = ""

    def showMessage(self, msg: str, _timeout: int = 0) -> None:
        self.last_message = str(msg)

    def font(self) -> _QFont:
        return _QFont()


class _QToolBar(_QWidget):
    def __init__(self, *_a: Any) -> None:
        super().__init__()

    def setMovable(self, _b: bool) -> None:
        pass

    def setIconSize(self, _s: Any) -> None:
        pass

    def addWidget(self, _w: Any) -> None:
        pass

    def indexOf(self, _w: Any) -> int:
        return 0

    def addSeparator(self) -> None:
        pass

    def clear(self) -> None:
        pass


class _QSplitter(_QWidget):
    def __init__(self, orient: int = 1, *_a: Any) -> None:
        super().__init__()
        self._orient = orient
        self.splitterMoved = _SignalInstance()

    def setOrientation(self, orient: int) -> None:
        self._orient = orient

    def orientation(self) -> int:
        return self._orient

    def setStretchFactor(self, _idx: int, _f: int) -> None:
        pass

    def setChildrenCollapsible(self, _b: bool) -> None:
        pass

    def setHandleWidth(self, _w: int) -> None:
        pass

    def addWidget(self, _w: Any) -> None:
        pass

    def count(self) -> int:
        return 2

    def setSizes(self, _s: List[int]) -> None:
        pass

    def sizes(self) -> List[int]:
        return [500, 500]


class _QMainWindow(_QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._sb = _QStatusBar(self)
        self._central: Optional[_QWidget] = None

    def setWindowTitle(self, _t: str) -> None:
        pass

    def setGeometry(self, x: int, y: int, w: int, h: int) -> None:
        self._width = w
        self._height = h

    def geometry(self) -> _QRect:
        return _QRect(80, 60, self._width, self._height)

    def normalGeometry(self) -> _QRect:
        return self.geometry()

    def isMaximized(self) -> bool:
        return False

    def addToolBar(self, *_a: Any) -> None:
        pass

    def addToolBarBreak(self, *_a: Any) -> None:
        pass

    def setCentralWidget(self, w: _QWidget) -> None:
        self._central = w

    def centralWidget(self) -> Optional[_QWidget]:
        return self._central

    def setStatusBar(self, sb: _QStatusBar) -> None:
        self._sb = sb

    def statusBar(self) -> _QStatusBar:
        return self._sb


class _QFontMetrics:
    def __init__(self, _f: Any = None) -> None:
        pass

    def elidedText(self, msg: str, _mode: int, _w: int) -> str:
        return str(msg)


class _MouseEvent:
    def __init__(
        self,
        pos: _QPoint,
        button: int = _QtNamespace.MouseButton.LeftButton,
        buttons: int = _QtNamespace.MouseButton.LeftButton,
        modifiers: int = _QtNamespace.KeyboardModifier.NoModifier,
    ) -> None:
        self._pos = pos
        self._button = button
        self._buttons = buttons
        self._modifiers = modifiers
        self.accepted = False

    def position(self) -> _QPointF:
        return _QPointF(self._pos.x(), self._pos.y())

    def pos(self) -> _QPoint:
        return self._pos

    def button(self) -> int:
        return self._button

    def buttons(self) -> int:
        return self._buttons

    def modifiers(self) -> int:
        return self._modifiers

    def accept(self) -> None:
        self.accepted = True


class _DropEvent:
    def __init__(
        self,
        mime: _QMimeData,
        pos: _QPoint,
        modifiers: int = _QtNamespace.KeyboardModifier.NoModifier,
    ) -> None:
        self._mime = mime
        self._pos = pos
        self._modifiers = modifiers
        self.accepted_proposed = False

    def mimeData(self) -> _QMimeData:
        return self._mime

    def position(self) -> _QPointF:
        return _QPointF(self._pos.x(), self._pos.y())

    def pos(self) -> _QPoint:
        return self._pos

    def modifiers(self) -> int:
        return self._modifiers

    def acceptProposedAction(self) -> None:
        self.accepted_proposed = True


# ===========================================================================
# 2. Tkinter / ttk.Treeview 이벤트 & 기본 클래스 바인딩 시맨틱 하네스
# ===========================================================================
class _TkEvent:
    def __init__(
        self,
        x: int = 10,
        y: int = 10,
        x_root: int = 100,
        y_root: int = 100,
        state: int = 0,
        delta: int = 0,
    ) -> None:
        self.x = x
        self.y = y
        self.x_root = x_root
        self.y_root = y_root
        self.state = state
        self.delta = delta


class _TkVar:
    def __init__(self, value: str = "") -> None:
        self._val = str(value)
        self._traces: List[Callable[..., Any]] = []

    def get(self) -> str:
        return self._val

    def set(self, val: str) -> None:
        self._val = str(val)
        for cb in list(self._traces):
            cb()

    def trace_add(self, _mode: str, cb: Callable[..., Any]) -> None:
        self._traces.append(cb)


class _TkWidget:
    _clipboard_text: str = ""
    _coord_target_map: Dict[Tuple[int, int], Any] = {}

    def __init__(self, master: Any = None, **_kw: Any) -> None:
        self.master = master
        self._children_widgets: List["_TkWidget"] = []
        if isinstance(master, _TkWidget):
            master._children_widgets.append(self)
        self._bindings: Dict[str, Callable[..., Any]] = {}

    def pack(self, **_kw: Any) -> None:
        pass

    def grid(self, **_kw: Any) -> None:
        pass

    def grid_forget(self) -> None:
        pass

    def grid_propagate(self, _b: bool) -> None:
        pass

    def rowconfigure(self, *_a: Any, **_k: Any) -> None:
        pass

    def columnconfigure(self, *_a: Any, **_k: Any) -> None:
        pass

    def configure(self, **_kw: Any) -> None:
        pass

    def bind(self, seq: str, func: Callable[..., Any]) -> None:
        self._bindings[seq] = func

    def winfo_children(self) -> List["_TkWidget"]:
        return list(self._children_widgets)

    def destroy(self) -> None:
        pass

    def focus_set(self) -> None:
        pass

    def clipboard_clear(self) -> None:
        _TkWidget._clipboard_text = ""

    def clipboard_append(self, text: str) -> None:
        _TkWidget._clipboard_text += str(text)

    def set(self, *_a: Any) -> None:
        pass

    def update_idletasks(self) -> None:
        pass

    def winfo_containing(self, x_root: int, y_root: int) -> Any:
        return _TkWidget._coord_target_map.get((x_root, y_root))


class _TkTreeview(_TkWidget):
    """
    실제 Tcl/Tk `ttk.Treeview`의 bindtags 실행 순서(위젯 바인딩 -> Treeview 클래스 기본 바인딩)를
    100% 동일하게 재현합니다. `<ButtonPress-1>` 핸들러가 `"break"`를 반환하지 않으면
    `ttk::treeview::Press` 기본 바인딩이 실행되어 다중 선택이 클릭 행 1개로 초기화됩니다.
    """

    ROW_HEIGHT = 24
    HEADER_HEIGHT = 24

    def __init__(self, master: Any = None, **_kw: Any) -> None:
        super().__init__(master)
        self._items_order: List[str] = []
        self._selection: List[str] = []
        self._focus_iid: str = ""

    def heading(self, *_a: Any, **_k: Any) -> None:
        pass

    def column(self, *_a: Any, **_k: Any) -> None:
        pass

    def yview(self, *_a: Any) -> None:
        pass

    def tag_configure(self, *_a: Any, **_k: Any) -> None:
        pass

    def insert(self, _parent: str, _index: Any, iid: str = "", **_kw: Any) -> str:
        if iid not in self._items_order:
            self._items_order.append(iid)
        return iid

    def delete(self, item: str) -> None:
        if item in self._items_order:
            self._items_order.remove(item)
        if item in self._selection:
            self._selection.remove(item)

    def get_children(self) -> Tuple[str, ...]:
        return tuple(self._items_order)

    def selection(self) -> Tuple[str, ...]:
        return tuple(self._selection)

    def selection_set(self, items: Any) -> None:
        if isinstance(items, str):
            seq = [items] if items else []
        else:
            seq = list(items)
        self._selection = [i for i in seq if i in self._items_order]
        if "<<TreeviewSelect>>" in self._bindings:
            self._bindings["<<TreeviewSelect>>"](_TkEvent())

    def selection_remove(self, *items: Any) -> None:
        flat: List[str] = []
        for x in items:
            if isinstance(x, (list, tuple, set)):
                flat.extend(x)
            else:
                flat.append(str(x))
        for it in flat:
            if it in self._selection:
                self._selection.remove(it)

    def focus(self, item: Optional[str] = None) -> str:
        if item is not None:
            self._focus_iid = str(item)
        return self._focus_iid

    def see(self, _iid: str) -> None:
        pass

    def y_for_iid(self, iid: str) -> int:
        idx = self._items_order.index(iid)
        return self.HEADER_HEIGHT + idx * self.ROW_HEIGHT + 8

    def identify_row(self, y: int) -> str:
        if y < self.HEADER_HEIGHT:
            return ""
        idx = (y - self.HEADER_HEIGHT) // self.ROW_HEIGHT
        if 0 <= idx < len(self._items_order):
            return self._items_order[idx]
        return ""

    def dispatch_button_press_1(self, event: _TkEvent) -> None:
        res = None
        if "<ButtonPress-1>" in self._bindings:
            res = self._bindings["<ButtonPress-1>"](event)
        if res == "break":
            return
        # Tcl/Tk ttk::treeview::Press 클래스 바인딩 시맨틱 재현!
        clicked = self.identify_row(event.y)
        if not clicked:
            return
        if event.state & 0x0004:  # Control toggle
            cur = list(self._selection)
            if clicked in cur:
                cur.remove(clicked)
            else:
                cur.append(clicked)
            self.selection_set(cur)
            self.focus(clicked)
        elif event.state & 0x0001:  # Shift extend
            anchor = self._focus_iid if self._focus_iid in self._items_order else clicked
            i1, i2 = self._items_order.index(anchor), self._items_order.index(clicked)
            lo, hi = min(i1, i2), max(i1, i2)
            self.selection_set(self._items_order[lo : hi + 1])
        else:
            # 수식키 없는 일반 클릭 시 기본 바인딩은 무조건 단일 항목으로 덮어씀!
            self.selection_set([clicked])
            self.focus(clicked)

    def dispatch_b1_motion(self, event: _TkEvent) -> None:
        if "<B1-Motion>" in self._bindings:
            self._bindings["<B1-Motion>"](event)

    def dispatch_button_release_1(self, event: _TkEvent) -> None:
        if "<ButtonRelease-1>" in self._bindings:
            self._bindings["<ButtonRelease-1>"](event)

    def dispatch_right_click(self, event: _TkEvent) -> None:
        if "<Button-3>" in self._bindings:
            self._bindings["<Button-3>"](event)


class _TkMenu(_TkWidget):
    last_popup_menu: Optional["_TkMenu"] = None

    def __init__(self, master: Any = None, **_kw: Any) -> None:
        super().__init__(master)
        self.commands: List[Tuple[str, Callable[[], Any]]] = []

    def add_command(self, label: str = "", command: Optional[Callable[[], Any]] = None) -> None:
        if command is not None:
            self.commands.append((label, command))

    def add_separator(self) -> None:
        pass

    def tk_popup(self, _x: int, _y: int) -> None:
        _TkMenu.last_popup_menu = self


class _TkNotebook(_TkWidget):
    def __init__(self, master: Any = None, **_kw: Any) -> None:
        super().__init__(master)
        self._tabs_map: Dict[str, Any] = {}
        self._order: List[str] = []
        self._selected_id: str = ""

    def add(self, child: Any, text: str = "") -> None:
        tid = f"tab_{len(self._order)}_{id(child)}"
        self._tabs_map[tid] = child
        self._order.append(tid)
        if not self._selected_id:
            self._selected_id = tid

    def select(self, tab_Or_id: Any = None) -> str:
        if tab_Or_id is None:
            return self._selected_id
        if isinstance(tab_Or_id, str) and tab_Or_id in self._tabs_map:
            self._selected_id = tab_Or_id
        else:
            for tid, w in self._tabs_map.items():
                if w is tab_Or_id:
                    self._selected_id = tid
                    break
        return self._selected_id

    def tabs(self) -> Tuple[str, ...]:
        return tuple(self._order)

    def nametowidget(self, tid: str) -> Any:
        return self._tabs_map[tid]

    def tab(self, *_a: Any, **_k: Any) -> None:
        pass


class _TkRoot(_TkWidget):
    def title(self, _t: str) -> None:
        pass

    def geometry(self, _g: str) -> None:
        pass

    def minsize(self, _w: int, _h: int) -> None:
        pass

    def after_idle(self, _cb: Any) -> None:
        pass

    def after(self, _ms: int, _cb: Any) -> None:
        pass

    def protocol(self, *_a: Any) -> None:
        pass

    def mainloop(self) -> None:
        pass


class _TkMessageBox:
    askyesnocancel_return: Optional[bool] = True  # True=copy, False=move, None=cancel
    askyesno_return: bool = True
    warnings: List[Tuple[str, str]] = []

    @classmethod
    def askyesnocancel(cls, _title: str, _msg: str) -> Optional[bool]:
        return cls.askyesnocancel_return

    @classmethod
    def askyesno(cls, _title: str, _msg: str) -> bool:
        return cls.askyesno_return

    @classmethod
    def showwarning(cls, title: str, msg: str) -> None:
        cls.warnings.append((title, msg))


# ===========================================================================
# 3. `pyquaddir.py` 실제 코드 추출 로더 (AST 정밀 추출 — 코드 복제 제로)
# ===========================================================================
def load_pyquaddir_symbols(target_file: Path) -> Dict[str, Any]:
    spec = importlib.util.spec_from_file_location("pyquaddir_under_test", str(target_file))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    source = target_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(target_file))

    qt_ns: Dict[str, Any] = dict(mod.__dict__)
    qt_ns.update({
        "QFileInfo": object,
        "QItemSelection": _QItemSelection,
        "QItemSelectionModel": _QItemSelectionModel,
        "QMimeData": _QMimeData,
        "QPoint": _QPoint,
        "QPointF": _QPointF,
        "QRect": _QRect,
        "QRectF": _QRect,
        "QSize": _QSize,
        "QTimer": type("QTimer", (), {"singleShot": staticmethod(lambda _ms, _cb: None)}),
        "Qt": _QtNamespace,
        "QUrl": _QUrl,
        "pyqtSignal": _SignalDescriptor,
        "QColor": _QColor,
        "QDesktopServices": object,
        "QDrag": _QDrag,
        "QFont": _QFont,
        "QFontMetrics": _QFontMetrics,
        "QIcon": _QIcon,
        "QImageReader": object,
        "QKeySequence": lambda s: s,
        "QPainter": object,
        "QPen": object,
        "QPixmap": object,
        "QShortcut": lambda *_a, **_k: None,
        "QTextOption": type("QTextOption", (), {"WrapMode": type("WM", (), {"WrapAnywhere": 1})}),
        "QAbstractItemView": _QAbstractItemView,
        "QApplication": _QApplication,
        "QCheckBox": _QCheckBox,
        "QColorDialog": object,
        "QDialog": _QWidget,
        "QDialogButtonBox": object,
        "QFileIconProvider": lambda: object(),
        "QFormLayout": _QLayout,
        "QFrame": _QFrame,
        "QHBoxLayout": _QLayout,
        "QHeaderView": _QHeaderView,
        "QInputDialog": object,
        "QLabel": _QLabel,
        "QLineEdit": _QLineEdit,
        "QListView": _QListView,
        "QListWidget": _QListWidget,
        "QListWidgetItem": _QListWidgetItem,
        "QMainWindow": _QMainWindow,
        "QMenu": _QMenu,
        "QMessageBox": _QMessageBox,
        "QPlainTextEdit": _QWidget,
        "QPushButton": _QToolButton,
        "QRubberBand": _QRubberBand,
        "QSizePolicy": type("QSizePolicy", (), {"Policy": type("P", (), {"Ignored": 0, "Fixed": 1, "Expanding": 2, "Preferred": 3})}),
        "QSplitter": _QSplitter,
        "QStackedWidget": _QStackedWidget,
        "QStatusBar": _QStatusBar,
        "QTableWidget": _QTableWidget,
        "QTableWidgetItem": _QTableWidgetItem,
        "QTabWidget": _QTabWidget,
        "QTextBrowser": _QWidget,
        "QToolBar": _QToolBar,
        "QToolButton": _QToolButton,
        "QVBoxLayout": _QLayout,
        "QWidget": _QWidget,
        "create_ui_icon": lambda *_a, **_k: _QIcon(),
        "get_entry_icon_or_thumbnail": lambda *_a, **_k: _QIcon(),
    })

    tk_mod = types.SimpleNamespace(
        Tk=_TkRoot,
        Frame=_TkWidget,
        Menu=_TkMenu,
        StringVar=_TkVar,
        X="x",
        Y="y",
        BOTH="both",
        LEFT="left",
        RIGHT="right",
        E="e",
        END="end",
    )
    ttk_mod = types.SimpleNamespace(
        Frame=_TkWidget,
        LabelFrame=_TkWidget,
        Button=_TkWidget,
        Entry=_TkWidget,
        Label=_TkWidget,
        Scrollbar=_TkWidget,
        Menubutton=type("_MB", (_TkWidget,), {"__setitem__": lambda self, _k, _v: None}),
        Treeview=_TkTreeview,
        Notebook=_TkNotebook,
        Style=lambda _r=None: types.SimpleNamespace(configure=lambda *_a, **_k: None),
    )
    tk_ns: Dict[str, Any] = dict(mod.__dict__)
    tk_ns.update({
        "tk": tk_mod,
        "ttk": ttk_mod,
        "messagebox": _TkMessageBox,
        "simpledialog": types.SimpleNamespace(askstring=lambda *_a, **_k: None),
    })

    qt_target_names = {
        "ElidedLabel",
        "AddressLineEdit",
        "FilterLineEdit",
        "SortableTableWidgetItem",
        "perform_file_transfer_qt",
        "FileTableView",
        "FileIconListView",
        "DirectoryTab",
        "InspectorPane",
        "ExplorerPane",
        "QDirMainWindow",
    }

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "run_pyqt6_app":
            extracted_nodes: List[ast.stmt] = []
            for sub in node.body:
                if isinstance(sub, (ast.ClassDef, ast.FunctionDef)) and sub.name in qt_target_names:
                    extracted_nodes.append(sub)
            mod_ast = ast.Module(body=extracted_nodes, type_ignores=[])
            exec(compile(mod_ast, str(target_file), "exec"), qt_ns)
        elif isinstance(node, ast.FunctionDef) and node.name == "run_tkinter_app":
            extracted_tk: List[ast.stmt] = [
                sub for sub in node.body if isinstance(sub, ast.ClassDef) and sub.name in ("TkDirectoryTab", "TkQDirApp")
            ]
            mod_tk_ast = ast.Module(body=extracted_tk, type_ignores=[])
            exec(compile(mod_tk_ast, str(target_file), "exec"), tk_ns)

    return {
        "mod": mod,
        "qt": qt_ns,
        "tk": tk_ns,
    }


# ===========================================================================
# 4. 전수 회귀 테스트 케이스 (15개 시나리오)
# ===========================================================================
class TestPyQuadDirMultiSelectTransfer(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.target_path = _resolve_target_pyquaddir_path()
        cls.bundle = load_pyquaddir_symbols(cls.target_path)
        cls.mod = cls.bundle["mod"]
        cls.qt = cls.bundle["qt"]
        cls.tk = cls.bundle["tk"]

    def setUp(self) -> None:
        self._exit_callbacks = []
        register = atexit.register

        def scoped_register(callback, *args, **kwargs):
            self._exit_callbacks.append(callback)
            return register(callback, *args, **kwargs)

        exit_patch = mock.patch.object(atexit, "register", side_effect=scoped_register)
        exit_patch.start()
        self.addCleanup(exit_patch.stop)
        self.addCleanup(lambda: [atexit.unregister(callback) for callback in self._exit_callbacks])
        # These are state-machine tests, not native Qt widgets.  Keep optional
        # addon construction in its own real-Qt integration tests.
        addon_patch = mock.patch("pyquaddir_addons.install_pyquaddir_addons", return_value=None)
        addon_patch.start()
        self.addCleanup(addon_patch.stop)
        self.tmp_root = Path(tempfile.mkdtemp(prefix="qdir_test_"))
        self.prof_dir = self.tmp_root / "profile"
        self.prof_dir.mkdir(parents=True, exist_ok=True)
        self.mod.set_active_profile(profile_dir=str(self.prof_dir))

        self.pane_dirs: List[Path] = []
        for i in range(4):
            d = self.tmp_root / f"pane_{i + 1}"
            d.mkdir(parents=True, exist_ok=True)
            self.pane_dirs.append(d)

        # Pane 1 테스트 파일/폴더 구성
        self.f1 = self.pane_dirs[0] / "alpha.txt"
        self.f2 = self.pane_dirs[0] / "beta.md"
        self.f3 = self.pane_dirs[0] / "gamma.csv"
        self.sub_dir = self.pane_dirs[0] / "sub_bundle"
        self.sub_dir.mkdir()
        (self.sub_dir / "inside.txt").write_text("nested", encoding="utf-8")
        for idx, fp in enumerate((self.f1, self.f2, self.f3), 1):
            fp.write_text(f"payload-{idx}", encoding="utf-8")

        self.mod.save_app_config(
            {
                "default_view_mode": "tiles",
                "pane_tabs": [[str(d)] for d in self.pane_dirs],
                "pane_active_tab_indices": [0, 0, 0, 0],
                "pane_tab_view_modes": [["tiles"], ["tiles"], ["details"], ["details"]],
            },
            engine="qt",
        )
        _QDrag.last_executed_mime = None
        _QMenu.next_exec_selector = None
        _QMessageBox.conflict_responder = None
        _QMessageBox.warnings.clear()
        _TkMessageBox.warnings.clear()
        _TkWidget._coord_target_map.clear()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    # -----------------------------------------------------------------------
    # 1. FileTableView (details / content 보기) 다중 선택 드래그·클릭·우클릭
    # -----------------------------------------------------------------------
    def test_01_table_view_multiselect_drag_and_drop_moves_all_items(self) -> None:
        """FileTableView(details): 4개 항목 다중 선택 후 선택된 행을 좌클릭 드래그해 다른 패널에 Shift+드롭 시 4개 모두 이동"""
        win = self.qt["QDirMainWindow"]()
        src_tab = win.panes[0].current_tab()
        dst_tab = win.panes[1].current_tab()
        src_tab.set_view_mode("details")
        dst_tab.set_view_mode("details")

        table = src_tab.table
        table.selectAll()
        selected_before = table.selected_file_paths()
        self.assertEqual(len(selected_before), 4, ".. 상위 폴더를 제외한 4개 항목 전체가 선택되어야 합니다.")

        # row 0은 '.. (상위 폴더)', row 2(두 번째 항목)를 수식키 없이 좌클릭
        press_pos = _QPoint(40, 2 * table._row_height + 10)
        table.mousePressEvent(_MouseEvent(press_pos, _QtNamespace.MouseButton.LeftButton))

        # NoUpdate 검증: 좌클릭 직후에도 다중 선택 4개가 절대 해제되지 않아야 함
        self.assertEqual(len(table.selected_file_paths()), 4)
        self.assertEqual(len(table._drag_paths), 4)

        # 드래그 임계 거리 이상 이동 -> startDrag 호출
        drag_pos = _QPoint(40, 2 * table._row_height + 35)
        table.mouseMoveEvent(_MouseEvent(drag_pos, _QtNamespace.MouseButton.NoButton, _QtNamespace.MouseButton.LeftButton))
        self.assertIsNotNone(_QDrag.last_executed_mime)
        self.assertEqual(len(_QDrag.last_executed_mime.urls()), 4)

        # 대상 패널(2번 창) 빈 영역에 Shift+드롭(이동)
        dst_table = dst_tab.table
        dst_table.dropEvent(
            _DropEvent(
                _QDrag.last_executed_mime,
                _QPoint(50, 400),
                modifiers=_QtNamespace.KeyboardModifier.ShiftModifier,
            )
        )

        for name in ("alpha.txt", "beta.md", "gamma.csv", "sub_bundle"):
            self.assertFalse((self.pane_dirs[0] / name).exists(), f"원본 {name}이 남아있으면 안 됩니다.")
            self.assertTrue((self.pane_dirs[1] / name).exists(), f"대상 폴더에 {name}이 이동되어야 합니다.")
        self.assertTrue((self.pane_dirs[1] / "sub_bundle" / "inside.txt").exists())

    def test_02_table_view_plain_click_release_collapses_to_single_selection(self) -> None:
        """FileTableView(details): 다중 선택 상태에서 드래그 없이 단순 클릭 후 마우스를 떼면 클릭한 1개 항목만 선택"""
        win = self.qt["QDirMainWindow"]()
        tab = win.panes[0].current_tab()
        tab.set_view_mode("details")
        table = tab.table
        table.selectAll()
        self.assertEqual(len(table.selected_file_paths()), 4)

        # row 3 클릭 후 미세 흔들림(2px < startDragDistance) 뒤 릴리즈
        p_down = _QPoint(60, 3 * table._row_height + 12)
        p_up = _QPoint(62, 3 * table._row_height + 12)
        expected_path = table.item(3, 0).data(_QtNamespace.ItemDataRole.UserRole)

        table.mousePressEvent(_MouseEvent(p_down, _QtNamespace.MouseButton.LeftButton))
        self.assertEqual(len(table.selected_file_paths()), 4, "마우스를 누른 순간에는 다중 선택이 유지되어야 합니다.")

        table.mouseReleaseEvent(_MouseEvent(p_up, _QtNamespace.MouseButton.LeftButton, _QtNamespace.MouseButton.NoButton))
        self.assertEqual(table.selected_file_paths(), [expected_path])

    def test_03_table_view_right_click_preserves_multiselect_and_switches_unselected(self) -> None:
        """FileTableView(details): 우클릭 시 선택된 항목 위에서는 다중 선택을 보존하고, 미선택 항목/빈 공간에서는 정확히 전환"""
        win = self.qt["QDirMainWindow"]()
        tab = win.panes[0].current_tab()
        tab.set_view_mode("details")
        table = tab.table

        # row 1, row 2 두 개만 선택
        table.clearSelection()
        table.selectRow(1)
        table.selectRow(2)
        two_paths = table.selected_file_paths()
        self.assertEqual(len(two_paths), 2)

        # 이미 선택된 row 2 우클릭 -> 2개 선택 그대로 보존
        table.mousePressEvent(
            _MouseEvent(_QPoint(80, 2 * table._row_height + 10), _QtNamespace.MouseButton.RightButton, _QtNamespace.MouseButton.RightButton)
        )
        self.assertEqual(table.selected_file_paths(), two_paths)

        # 미선택 상태인 row 4 우클릭 -> row 4 단일 선택으로 전환
        row4_path = table.item(4, 0).data(_QtNamespace.ItemDataRole.UserRole)
        table.mousePressEvent(
            _MouseEvent(_QPoint(80, 4 * table._row_height + 10), _QtNamespace.MouseButton.RightButton, _QtNamespace.MouseButton.RightButton)
        )
        self.assertEqual(table.selected_file_paths(), [row4_path])

        # 빈 공간 우클릭 -> 선택 해제
        table.mousePressEvent(
            _MouseEvent(_QPoint(80, 500), _QtNamespace.MouseButton.RightButton, _QtNamespace.MouseButton.RightButton)
        )
        self.assertEqual(table.selected_file_paths(), [])

    def test_04_table_and_icon_double_click_on_marquee_selected_folder_navigates(self) -> None:
        """마키(RubberBand)로 이미 선택된 폴더를 더블클릭해도 2번째 클릭이 삼켜지지 않고 즉시 폴더 진입"""
        win = self.qt["QDirMainWindow"]()
        tab = win.panes[0].current_tab()

        # 1) Table(details) 모드 검증
        tab.set_view_mode("details")
        tab.table.selectAll()  # super().mousePressEvent 없이 선택된 상태
        folder_pos = _QPoint(50, 1 * tab.table._row_height + 10)  # row 1 == sub_bundle
        tab.table.mousePressEvent(_MouseEvent(folder_pos, _QtNamespace.MouseButton.LeftButton))
        tab.table.mouseReleaseEvent(_MouseEvent(folder_pos, _QtNamespace.MouseButton.LeftButton, 0))
        tab.table.mouseDoubleClickEvent(_MouseEvent(folder_pos, _QtNamespace.MouseButton.LeftButton))
        self.assertEqual(Path(tab.current_path).name, "sub_bundle")

        # 2) Icon(tiles) 모드 검증
        tab.go_up()
        tab.set_view_mode("tiles")
        tab.icon_list.selectAll()
        tile_pos = _QPoint(50, 1 * tab.icon_list._grid_h + 15)  # index 1 == sub_bundle
        tab.icon_list.mousePressEvent(_MouseEvent(tile_pos, _QtNamespace.MouseButton.LeftButton))
        tab.icon_list.mouseReleaseEvent(_MouseEvent(tile_pos, _QtNamespace.MouseButton.LeftButton, 0))
        tab.icon_list.mouseDoubleClickEvent(_MouseEvent(tile_pos, _QtNamespace.MouseButton.LeftButton))
        self.assertEqual(Path(tab.current_path).name, "sub_bundle")

    # -----------------------------------------------------------------------
    # 2. FileIconListView (기본 tiles 보기 포함) 다중 선택 드래그·클릭·우클릭
    # -----------------------------------------------------------------------
    def test_05_icon_list_tiles_multiselect_drag_and_drop_copies_and_moves_all(self) -> None:
        """FileIconListView(기본 tiles 보기): 다중 선택 후 타일 클릭 드래그 시 NoUpdate로 4개 모두 복사 및 이동"""
        win = self.qt["QDirMainWindow"]()
        src_tab = win.panes[0].current_tab()
        dst_tab = win.panes[1].current_tab()
        self.assertEqual(src_tab.view_mode, "tiles")

        icon_list = src_tab.icon_list
        icon_list.selectAll()
        self.assertEqual(len(icon_list.selected_file_paths()), 4)

        # index 2 타일을 좌클릭하여 드래그 시작
        press_pos = _QPoint(60, 2 * icon_list._grid_h + 20)
        icon_list.mousePressEvent(_MouseEvent(press_pos, _QtNamespace.MouseButton.LeftButton))
        self.assertEqual(len(icon_list.selected_file_paths()), 4, "tiles 보기에서 클릭 직후 다중 선택이 1개로 줄어들면 안 됩니다.")
        self.assertEqual(len(icon_list._drag_paths), 4)

        icon_list.mouseMoveEvent(
            _MouseEvent(_QPoint(60, 2 * icon_list._grid_h + 45), _QtNamespace.MouseButton.NoButton, _QtNamespace.MouseButton.LeftButton)
        )
        self.assertIsNotNone(_QDrag.last_executed_mime)
        self.assertEqual(len(_QDrag.last_executed_mime.urls()), 4)

        # 수식키 없는 일반 드롭 시 팝업 메뉴에서 '여기에 이동 (4개 항목)' 선택 검증
        def _choose_move(menu: _QMenu) -> Optional[_QAction]:
            for act in menu.actions_list:
                if "여기에 이동 (4개 항목)" in act.text():
                    return act
            return None

        _QMenu.next_exec_selector = _choose_move
        dst_tab.icon_list.dropEvent(_DropEvent(_QDrag.last_executed_mime, _QPoint(50, 500), modifiers=0))

        for name in ("alpha.txt", "beta.md", "gamma.csv", "sub_bundle"):
            self.assertFalse((self.pane_dirs[0] / name).exists())
            self.assertTrue((self.pane_dirs[1] / name).exists())

    def test_06_icon_list_tiles_click_release_and_gap_jitter_single_select(self) -> None:
        """FileIconListView(tiles): 드래그 없이 타일 클릭 후 릴리즈(타일 사이 여백 미세 이동 포함) 시 클릭한 타일 1개로 전환"""
        win = self.qt["QDirMainWindow"]()
        tab = win.panes[0].current_tab()
        icon_list = tab.icon_list
        icon_list.selectAll()
        self.assertEqual(len(icon_list.selected_file_paths()), 4)

        target_item = icon_list.item(3)
        expected_path = target_item.data(_QtNamespace.ItemDataRole.UserRole)

        # 타일 하단 경계 근처 클릭 후 여백(spacing) 구간으로 3px 이동해 릴리즈하더라도 _pressed_item으로 정확히 복구
        body_h = icon_list._grid_h - icon_list._spacing
        down_pos = _QPoint(50, 3 * icon_list._grid_h + body_h - 1)
        gap_up_pos = _QPoint(50, 3 * icon_list._grid_h + body_h + 1)
        self.assertIsNone(icon_list.itemAt(gap_up_pos), "테스트 좌표는 타일 간 여백이어야 합니다.")

        icon_list.mousePressEvent(_MouseEvent(down_pos, _QtNamespace.MouseButton.LeftButton))
        icon_list.mouseReleaseEvent(_MouseEvent(gap_up_pos, _QtNamespace.MouseButton.LeftButton, 0))
        self.assertEqual(icon_list.selected_file_paths(), [expected_path])

    def test_07_icon_list_tiles_right_click_preserves_multiselect(self) -> None:
        """FileIconListView(tiles): 다중 선택 상태에서 우클릭 시 다중 선택 보존 및 미선택 타일/빈 공간 우클릭 처리"""
        win = self.qt["QDirMainWindow"]()
        tab = win.panes[0].current_tab()
        icon_list = tab.icon_list
        icon_list.clearSelection()
        icon_list.item(1).setSelected(True)
        icon_list.item(2).setSelected(True)
        two_sel = icon_list.selected_file_paths()
        self.assertEqual(len(two_sel), 2)

        # 선택된 index 2 우클릭 -> 2개 그대로 유지
        icon_list.mousePressEvent(
            _MouseEvent(_QPoint(40, 2 * icon_list._grid_h + 15), _QtNamespace.MouseButton.RightButton, _QtNamespace.MouseButton.RightButton)
        )
        self.assertEqual(icon_list.selected_file_paths(), two_sel)

        # 미선택 index 4 우클릭 -> index 4 단일 선택
        expected_4 = icon_list.item(4).data(_QtNamespace.ItemDataRole.UserRole)
        icon_list.mousePressEvent(
            _MouseEvent(_QPoint(40, 4 * icon_list._grid_h + 15), _QtNamespace.MouseButton.RightButton, _QtNamespace.MouseButton.RightButton)
        )
        self.assertEqual(icon_list.selected_file_paths(), [expected_4])

        # 상위 폴더('..', index 0) 우클릭 -> 선택 해제
        icon_list.mousePressEvent(
            _MouseEvent(_QPoint(40, 10), _QtNamespace.MouseButton.RightButton, _QtNamespace.MouseButton.RightButton)
        )
        self.assertEqual(icon_list.selected_file_paths(), [])

    # -----------------------------------------------------------------------
    # 3. 컨텍스트 메뉴 전송·줄바꿈 경로 복사 / 상단 툴바 전송 / 클립보드 / 충돌 처리
    # -----------------------------------------------------------------------
    def test_08_context_menu_multiline_copy_path_and_pane_transfer(self) -> None:
        """컨텍스트 메뉴: 다중 선택 시 줄바꿈 전체 경로 복사 및 '다른 패널로 즉시 이동'이 모든 항목을 처리"""
        win = self.qt["QDirMainWindow"]()
        tab = win.panes[0].current_tab()
        tab.icon_list.selectAll()
        all_paths = tab.selected_file_paths()
        self.assertEqual(len(all_paths), 4)

        # 1) 줄바꿈 전체 경로 복사 검증
        def _trigger_copy_path(menu: _QMenu) -> Optional[_QAction]:
            for act in menu.actions_list:
                if "클립보드 복사" in act.text():
                    act.trigger()
                    return act
            return None

        _QMenu.next_exec_selector = _trigger_copy_path
        tab._show_context_menu(_QPoint(30, 30))
        copied_text = _QApplication.clipboard().text()
        self.assertEqual(copied_text.splitlines(), all_paths)

        # 선택 없을 때는 현재 폴더 경로 복사
        tab.icon_list.clearSelection()
        tab._show_context_menu(_QPoint(30, 500))
        self.assertEqual(_QApplication.clipboard().text(), tab.current_path)

        # 2) 컨텍스트 메뉴 -> '📦 다른 패널로 즉시 이동' -> [3번 창]
        tab.icon_list.selectAll()

        def _trigger_move_to_pane3(menu: _QMenu) -> Optional[_QAction]:
            move_sub = menu.submenus.get("📦 다른 패널로 즉시 이동")
            self.assertIsNotNone(move_sub)
            for act in move_sub.actions_list:
                if "[3번 창]" in act.text():
                    act.trigger()
                    return act
            return None

        _QMenu.next_exec_selector = _trigger_move_to_pane3
        tab._show_context_menu(_QPoint(30, 90))
        for name in ("alpha.txt", "beta.md", "gamma.csv", "sub_bundle"):
            self.assertTrue((self.pane_dirs[2] / name).exists())
            self.assertFalse((self.pane_dirs[0] / name).exists())

    def test_09_toolbar_send_menu_and_nofocus_policy(self) -> None:
        """상단 툴바 `📤 다른 패널로 전송`(_populate_send_menu): 포커스 탈취 방지(NoFocus) 및 다중 항목 일괄 복사/이동"""
        win = self.qt["QDirMainWindow"]()
        self.assertEqual(win.btn_send.focusPolicy(), _QtNamespace.FocusPolicy.NoFocus)
        self.assertEqual(win.act_copy.focusPolicy(), _QtNamespace.FocusPolicy.NoFocus)
        self.assertEqual(win.act_cut.focusPolicy(), _QtNamespace.FocusPolicy.NoFocus)
        self.assertEqual(win.act_paste.focusPolicy(), _QtNamespace.FocusPolicy.NoFocus)

        src_tab = win.panes[0].current_tab()
        src_tab.icon_list.selectAll()
        self.assertEqual(len(src_tab.selected_file_paths()), 4)

        win._populate_send_menu()
        # 메뉴 생성 직후 원본 뷰의 선택을 인위적으로 지워도 스냅샷 클로저로 4개가 안전하게 이동되는지 검증
        src_tab.icon_list.clearSelection()

        move_pane4_act = None
        for act in win.send_menu.actions_list:
            if "✂️ [4번 창]으로 이동" in act.text():
                move_pane4_act = act
                break
        self.assertIsNotNone(move_pane4_act)
        move_pane4_act.trigger()

        for name in ("alpha.txt", "beta.md", "gamma.csv", "sub_bundle"):
            self.assertTrue((self.pane_dirs[3] / name).exists())
            self.assertFalse((self.pane_dirs[0] / name).exists())

    def test_10_clipboard_copy_cut_paste_and_deduplication(self) -> None:
        """Ctrl+C / Ctrl+X / Ctrl+V: 중복 경로 제거, 다중 복사 후 재붙여넣기 가능, 다중 잘라내기 이동 후 클립보드 비움"""
        win = self.qt["QDirMainWindow"]()
        src_tab = win.panes[0].current_tab()
        dst_tab_2 = win.panes[1].current_tab()
        dst_tab_3 = win.panes[2].current_tab()

        # 중복 경로 전달 시 자동 정규화·중복 제거 검증
        win.set_clipboard_files([str(self.f1), str(self.f1), str(self.f2), str(self.f3)], "copy")
        self.assertEqual(len(win.clipboard_paths), 3)

        # Ctrl+V 복사 -> 3개 파일 모두 복사되고 copy 모드에서는 clipboard_paths 유지
        win._set_active_pane(1)
        win._shortcut_paste()
        for name in ("alpha.txt", "beta.md", "gamma.csv"):
            self.assertTrue((self.pane_dirs[0] / name).exists())
            self.assertTrue((self.pane_dirs[1] / name).exists())
        self.assertEqual(len(win.clipboard_paths), 3)

        # Pane 1에서 전체 선택 후 Ctrl+X -> Pane 3에 Ctrl+V 이동
        win._set_active_pane(0)
        src_tab.icon_list.selectAll()
        win._shortcut_cut()
        self.assertEqual(len(win.clipboard_paths), 4)
        self.assertEqual(win.clipboard_mode, "move")

        win._set_active_pane(2)
        dst_tab_3.paste_files_here()
        for name in ("alpha.txt", "beta.md", "gamma.csv", "sub_bundle"):
            self.assertFalse((self.pane_dirs[0] / name).exists())
            self.assertTrue((self.pane_dirs[2] / name).exists())
        self.assertEqual(win.clipboard_paths, [])

    def test_11_drop_event_guards_self_folder_and_supports_subfolder_target(self) -> None:
        """dropEvent: 드래그 목록에 포함된 폴더 자신 위에 드롭되면 현재 폴더로 안전 폴백하고, 별도 하위 폴더 위 드롭은 해당 폴더로 일괄 이동"""
        win = self.qt["QDirMainWindow"]()
        src_tab = win.panes[0].current_tab()
        dst_tab = win.panes[1].current_tab()
        other_sub = self.pane_dirs[1] / "target_sub"
        other_sub.mkdir()
        dst_tab.set_view_mode("details")

        # 1) 별도 하위 폴더(row 1 == target_sub) 위에 드롭 시 3개 파일 모두 target_sub 내부로 이동
        mime = _QMimeData()
        mime.setUrls([_QUrl.fromLocalFile(str(p)) for p in (self.f1, self.f2, self.f3)])
        dst_tab.table.dropEvent(
            _DropEvent(mime, _QPoint(40, 1 * dst_tab.table._row_height + 10), _QtNamespace.KeyboardModifier.ShiftModifier)
        )
        for name in ("alpha.txt", "beta.md", "gamma.csv"):
            self.assertTrue((other_sub / name).exists())

        # 2) 자기 자신이 포함된 다중 드래그([sub_bundle, ...])가 sub_bundle 위에 드롭될 때 재귀 오류 없이 현재 폴더 처리
        f_extra = self.pane_dirs[0] / "extra.txt"
        f_extra.write_text("ok", encoding="utf-8")
        src_tab.set_view_mode("details")
        mime_self = _QMimeData()
        mime_self.setUrls([_QUrl.fromLocalFile(str(self.sub_dir)), _QUrl.fromLocalFile(str(f_extra))])
        _QMessageBox.warnings.clear()
        src_tab.table.dropEvent(
            _DropEvent(mime_self, _QPoint(40, 1 * src_tab.table._row_height + 10), _QtNamespace.KeyboardModifier.ShiftModifier)
        )
        self.assertEqual(_QMessageBox.warnings, [], "자기 자신 폴더 위 드롭 시 하위 폴더 재귀 경고가 발생하면 안 됩니다.")

    def test_12_perform_file_transfer_qt_batch_conflict_apply_all(self) -> None:
        """perform_file_transfer_qt: 다중 파일 이름 충돌 시 '다음 충돌 항목에도 모두 동일하게 적용'으로 전체 항목 연속 처리"""
        for name in ("alpha.txt", "beta.md", "gamma.csv"):
            (self.pane_dirs[1] / name).write_text("existing", encoding="utf-8")

        dialog_calls = 0

        def _auto_rename_all(_box: _QMessageBox) -> Tuple[str, bool]:
            nonlocal dialog_calls
            dialog_calls += 1
            return ("자동 번호 붙이기", True)

        _QMessageBox.conflict_responder = _auto_rename_all
        fn = self.qt["perform_file_transfer_qt"]
        cnt, errs = fn(
            _QWidget(),
            [str(self.f1), str(self.f2), str(self.f3)],
            str(self.pane_dirs[1]),
            mode="copy",
        )
        self.assertEqual(cnt, 3)
        self.assertEqual(errs, [])
        self.assertEqual(dialog_calls, 1, "'모두 적용' 체크 시 충돌 대화상자는 최초 1회만 호출되어야 합니다.")
        self.assertTrue((self.pane_dirs[1] / "alpha (1).txt").exists())
        self.assertTrue((self.pane_dirs[1] / "beta (1).md").exists())
        self.assertTrue((self.pane_dirs[1] / "gamma (1).csv").exists())

    # -----------------------------------------------------------------------
    # 4. Tkinter 폴백 엔진 (TkDirectoryTab / TkQDirApp) 다중 선택 드래그·클릭·우클릭
    # -----------------------------------------------------------------------
    def _create_tk_app(self) -> Tuple[Any, Any, Any]:
        self.mod.save_app_config(
            {
                "pane_tabs": [[str(d)] for d in self.pane_dirs],
                "pane_active_tab_indices": [0, 0, 0, 0],
            },
            engine="tk",
        )
        app = self.tk["TkQDirApp"]()
        tab0 = app.notebooks[0].nametowidget(app.notebooks[0].select())
        tab1 = app.notebooks[1].nametowidget(app.notebooks[1].select())
        return app, tab0, tab1

    def test_13_tkinter_multiselect_drag_returns_break_and_moves_all_items(self) -> None:
        """TkDirectoryTab: 다중 선택 항목 위 좌클릭 드래그 시 'break' 반환으로 Treeview 초기화를 막고 4개 모두 이동"""
        _app, tab0, tab1 = self._create_tk_app()
        tab0._on_select_all(_TkEvent())
        self.assertEqual(len(tab0.selected_paths()), 4)

        target_iid = self.mod.safe_norm_path(str(self.f2))
        press_y = tab0.tree.y_for_iid(target_iid)

        # 실제 Treeview 이벤트 디스패치(위젯 바인딩 -> 클래스 기본 바인딩) 실행!
        tab0.tree.dispatch_button_press_1(_TkEvent(x=40, y=press_y, state=0))
        self.assertEqual(
            len(tab0.selected_paths()),
            4,
            "_on_drag_start가 'break'를 반환하지 않으면 Treeview 기본 바인딩이 선택을 1개로 초기화합니다.",
        )

        tab0.tree.dispatch_b1_motion(_TkEvent(x=65, y=press_y + 20, state=0))
        self.assertTrue(tab0._did_drag_tk)

        # 패널 2 위젯 좌표 매핑 후 드롭(이동 선택: askyesnocancel -> False)
        _TkWidget._coord_target_map[(500, 300)] = tab1.tree
        _TkMessageBox.askyesnocancel_return = False
        tab0.tree.dispatch_button_release_1(_TkEvent(x=65, y=press_y + 20, x_root=500, y_root=300))

        for name in ("alpha.txt", "beta.md", "gamma.csv", "sub_bundle"):
            self.assertFalse((self.pane_dirs[0] / name).exists())
            self.assertTrue((self.pane_dirs[1] / name).exists())

    def test_14_tkinter_plain_click_release_and_ctrl_click_compatibility(self) -> None:
        """TkDirectoryTab: 드래그 없는 단순 클릭 릴리즈 시 단일 선택 전환, Ctrl+클릭 시 기본 토글 동작 유지"""
        _app, tab0, _tab1 = self._create_tk_app()
        tab0._on_select_all(_TkEvent())
        self.assertEqual(len(tab0.selected_paths()), 4)

        iid_beta = self.mod.safe_norm_path(str(self.f2))
        y_beta = tab0.tree.y_for_iid(iid_beta)

        # 1) 드래그 없는 단순 클릭 후 릴리즈 -> beta.md 1개만 선택
        tab0.tree.dispatch_button_press_1(_TkEvent(x=35, y=y_beta, state=0))
        tab0.tree.dispatch_button_release_1(_TkEvent(x=36, y=y_beta, state=0))
        self.assertEqual(tab0.selected_paths(), [iid_beta])

        # 2) Ctrl(0x0004)+클릭 -> gamma.csv 추가 선택 (2개)
        iid_gamma = self.mod.safe_norm_path(str(self.f3))
        y_gamma = tab0.tree.y_for_iid(iid_gamma)
        tab0.tree.dispatch_button_press_1(_TkEvent(x=35, y=y_gamma, state=0x0004))
        self.assertEqual(set(tab0.selected_paths()), {iid_beta, iid_gamma})

    def test_15_tkinter_right_click_selection_multiline_copy_and_same_dir_move_guard(self) -> None:
        """TkDirectoryTab._on_right_click & transfer_files_tk: 다중 선택 보존, 미선택 우클릭 전환, 줄바꿈 경로 복사 및 동일 폴더 이동 가드"""
        app, tab0, _tab1 = self._create_tk_app()
        iid_a = self.mod.safe_norm_path(str(self.f1))
        iid_b = self.mod.safe_norm_path(str(self.f2))
        iid_c = self.mod.safe_norm_path(str(self.f3))
        tab0.tree.selection_set([iid_a, iid_b])

        # 1) 이미 선택된 iid_b 우클릭 -> 2개 선택 유지 & 줄바꿈 경로 복사
        tab0.tree.dispatch_right_click(_TkEvent(x=40, y=tab0.tree.y_for_iid(iid_b), x_root=120, y_root=120))
        self.assertEqual(tab0.selected_paths(), [iid_a, iid_b])
        self.assertIsNotNone(_TkMenu.last_popup_menu)
        for lbl, cmd in _TkMenu.last_popup_menu.commands:
            if "경로" in lbl and "복사" in lbl:
                cmd()
                break
        self.assertEqual(_TkWidget._clipboard_text.splitlines(), [iid_a, iid_b])

        # 2) 미선택 항목 iid_c 우클릭 -> iid_c 단일 선택 전환
        tab0.tree.dispatch_right_click(_TkEvent(x=40, y=tab0.tree.y_for_iid(iid_c), x_root=120, y_root=140))
        self.assertEqual(tab0.selected_paths(), [iid_c])

        # 3) 빈 공간 우클릭 -> 선택 해제
        tab0.tree.dispatch_right_click(_TkEvent(x=40, y=600, x_root=120, y_root=600))
        self.assertEqual(tab0.selected_paths(), [])

        # 4) 동일 폴더로 move 호출 시 파일명이 'alpha (1).txt'로 변형되지 않고 그대로 보존되는지 검증
        app.transfer_files_tk([iid_a, iid_b], str(self.pane_dirs[0]), mode="move")
        self.assertTrue(self.f1.exists())
        self.assertTrue(self.f2.exists())
        self.assertFalse((self.pane_dirs[0] / "alpha (1).txt").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
