"""Portable shortcut validation shared by desktop backends."""

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence


@dataclass(frozen=True)
class Shortcut:
    portable: str
    modifiers: int
    virtual_key: int

    @classmethod
    def parse(cls, value: str) -> "Shortcut | None":
        sequence = QKeySequence.fromString(value, QKeySequence.SequenceFormat.PortableText)
        if sequence.count() != 1:
            return None
        combination = sequence[0]
        flags = combination.keyboardModifiers()
        allowed = (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
                   | Qt.KeyboardModifier.ShiftModifier)
        if not flags.value or flags.value & ~allowed.value:
            return None
        ctrl = bool(flags & Qt.KeyboardModifier.ControlModifier)
        alt = bool(flags & Qt.KeyboardModifier.AltModifier)
        shift = bool(flags & Qt.KeyboardModifier.ShiftModifier)
        key = int(combination.key())
        if 0x01000030 <= key <= 0x01000047 and key != int(Qt.Key.Key_F12):
            virtual_key = 0x70 + key - int(Qt.Key.Key_F1)
        elif (ctrl or alt) and (ord("A") <= key <= ord("Z") or ord("0") <= key <= ord("9")):
            virtual_key = key
        else:
            return None
        modifiers = 0x4000 | int(alt) | (int(ctrl) << 1) | (int(shift) << 2)
        return cls(sequence.toString(QKeySequence.SequenceFormat.PortableText), modifiers, virtual_key)


DEFAULT_SHORTCUT = Shortcut("Ctrl+Shift+F9", 0x4006, 0x78)
