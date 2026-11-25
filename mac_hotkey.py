"""Carbon hotkeys, loaded only when a macOS shortcut is requested."""

import ctypes
import sys

from shortcuts import Shortcut


class EventTypeSpec(ctypes.Structure):
    _fields_ = [("eventClass", ctypes.c_uint32), ("eventKind", ctypes.c_uint32)]


class EventHotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]


HANDLER = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
SIGNATURE = int.from_bytes(b"StDD", "big")
KEYCODES = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", (0, 11, 8, 2, 14, 3, 5, 4, 34, 38, 40, 37, 46, 45, 31, 35, 12, 15, 1, 17, 32, 9, 13, 7, 16, 6)))
KEYCODES.update(dict(zip("0123456789", (29, 18, 19, 20, 21, 23, 22, 26, 28, 25))))
KEYCODES.update({0x70 + index: code for index, code in enumerate((122, 120, 99, 118, 96, 97, 98, 100, 101, 109, 103, 111, 105, 107, 113, 106, 64, 79, 80, 90))})


class MacHotkey:
    def __init__(self, callback) -> None:
        self._callback = callback
        self._carbon = None
        self._handler = ctypes.c_void_p()
        self._hotkey = ctypes.c_void_p()
        self._shortcut = None
        self._id = 0
        self._event_callback = HANDLER(self._handle_event)

    def _load(self) -> bool:
        if self._carbon is not None:
            return True
        if sys.platform != "darwin":
            return False
        try:
            carbon = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")
        except OSError:
            return False
        ptr = ctypes.c_void_p
        uint = ctypes.c_uint32
        status = ctypes.c_int32
        carbon.GetApplicationEventTarget.argtypes = []
        carbon.GetApplicationEventTarget.restype = ptr
        carbon.InstallEventHandler.argtypes = [ptr, HANDLER, ctypes.c_ulong, ctypes.POINTER(EventTypeSpec), ptr, ctypes.POINTER(ptr)]
        carbon.InstallEventHandler.restype = status
        carbon.RegisterEventHotKey.argtypes = [uint, uint, EventHotKeyID, ptr, uint, ctypes.POINTER(ptr)]
        carbon.RegisterEventHotKey.restype = status
        carbon.UnregisterEventHotKey.argtypes = [ptr]
        carbon.UnregisterEventHotKey.restype = status
        carbon.RemoveEventHandler.argtypes = [ptr]
        carbon.RemoveEventHandler.restype = status
        carbon.GetEventParameter.argtypes = [ptr, uint, uint, ctypes.POINTER(uint), ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ptr]
        carbon.GetEventParameter.restype = status
        spec = EventTypeSpec(int.from_bytes(b"keyb", "big"), 6)
        if carbon.InstallEventHandler(carbon.GetApplicationEventTarget(), self._event_callback, 1,
                                      ctypes.byref(spec), None, ctypes.byref(self._handler)):
            return False
        self._carbon = carbon
        return True

    def set_shortcut(self, shortcut: Shortcut) -> bool:
        if shortcut == self._shortcut:
            return True
        key = KEYCODES.get(shortcut.virtual_key) if shortcut.virtual_key >= 0x70 else KEYCODES.get(chr(shortcut.virtual_key))
        if key is None or not self._load():
            return False
        modifiers = ((shortcut.modifiers & 1) * 2048
                     | ((shortcut.modifiers >> 1) & 1) * 4096
                     | ((shortcut.modifiers >> 2) & 1) * 512)
        new_id = 2 if self._id == 1 else 1
        hotkey = ctypes.c_void_p()
        result = self._carbon.RegisterEventHotKey(key, modifiers, EventHotKeyID(SIGNATURE, new_id),
                                                  self._carbon.GetApplicationEventTarget(), 0, ctypes.byref(hotkey))
        if result:
            return False
        previous = self._hotkey
        self._hotkey, self._id, self._shortcut = hotkey, new_id, shortcut
        if previous:
            self._carbon.UnregisterEventHotKey(previous)
        return True

    def _handle_event(self, next_handler, event, user_data) -> int:
        identifier = EventHotKeyID()
        result = self._carbon.GetEventParameter(event, int.from_bytes(b"----", "big"), int.from_bytes(b"hkid", "big"),
                                                None, ctypes.sizeof(identifier), None, ctypes.byref(identifier))
        if result or identifier.signature != SIGNATURE or identifier.id != self._id or not self._hotkey:
            return -9874  # eventNotHandledErr: leave other handlers' hotkeys alone.
        try:
            self._callback()
        except Exception:
            return -9874
        return 0

    def close(self) -> None:
        if self._carbon is not None:
            if self._hotkey:
                self._carbon.UnregisterEventHotKey(self._hotkey)
                self._hotkey = ctypes.c_void_p()
            if self._handler:
                self._carbon.RemoveEventHandler(self._handler)
                self._handler = ctypes.c_void_p()
        self._shortcut = None
        self._id = 0
        self._carbon = None
