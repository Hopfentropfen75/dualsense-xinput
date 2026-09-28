"""Erkennt laufende Spiele, damit die Bruecke das passende Profil nimmt.

Nur ctypes - ein Toolhelp-Snapshot der Prozessliste dauert wenige
Millisekunden und laeuft deshalb nie im Eingabe-Loop.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes as wt

TH32CS_SNAPPROCESS = 0x2


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wt.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
_k32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
_k32.Process32FirstW.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
_k32.Process32NextW.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
_k32.CloseHandle.argtypes = [wt.HANDLE]
_INVALID = wt.HANDLE(-1).value


def running() -> set[str]:
    """Namen aller laufenden Programme, kleingeschrieben."""
    snap = _k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == _INVALID:
        return set()
    names: set[str] = set()
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = _k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            names.add(entry.szExeFile.lower())
            ok = _k32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        _k32.CloseHandle(snap)
    return names


def detect(data: dict) -> tuple[str, str] | None:
    """(Exe-Name, Profil) des ersten laufenden Spiels aus den Profilen."""
    if not data.get("auto_game"):
        return None
    exes = running()
    for name, prof in data["profiles"].items():
        for pat in prof.get("games", []):
            pat = str(pat).strip().lower()
            if not pat:
                continue
            for exe in exes:
                if pat in exe:
                    return exe, name
    return None


if __name__ == "__main__":
    import settings

    hit = detect(settings.load())
    print(f"erkannt: {hit[0]} -> Profil {hit[1]}" if hit else "kein Spiel erkannt")
