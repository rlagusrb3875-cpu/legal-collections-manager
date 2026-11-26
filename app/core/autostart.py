# -*- coding: utf-8 -*-
"""PC를 켜면 자동으로 실행 (Windows) — 사용자 시작 프로그램 목록(HKCU …\\Run)에 이 PC의 실행 파일을 넣고 뺀다.

관리자 권한이 필요 없고, 설정에서 끄면 바로 목록에서 빠진다. 다른 사용자·다른 PC에는 영향이 없다.
실행 파일 위치는 실행기(exe)가 알려 준다 (환경 변수 CSH_LAUNCHER = %LOCALAPPDATA%\\CourtSearch\\…exe).
"""
import os
import sys

WIN = sys.platform == "win32"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "CourtSearch"


def target():
    p = os.environ.get("CSH_LAUNCHER", "")
    return p if p.lower().endswith(".exe") and os.path.isfile(p) else ""


def _read():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            return winreg.QueryValueEx(k, NAME)[0]
    except OSError:
        return ""


def status():
    exe = target()
    if not WIN or not exe:
        return {"supported": False, "on": False, "path": exe,
                "why": "회사 PC(Windows)에서 프로그램(exe)으로 실행할 때 쓸 수 있어요"}
    cur = _read()
    return {"supported": True, "on": bool(cur) and os.path.normcase(exe) in os.path.normcase(cur), "path": exe,
            "other": bool(cur) and os.path.normcase(exe) not in os.path.normcase(cur)}


def migrate():
    """시작 프로그램이 예전 이름(같은 CourtSearch 폴더의 다른 exe)을 가리키면 지금 exe로 바꾼다. 켠 적이 없으면 아무것도 안 함."""
    st = status()
    if st["supported"] and st.get("other"):
        cur = _read()
        if "\\courtsearch\\" in cur.lower():
            return set_on(True)
    return st


def set_on(on):
    st = status()
    if not st["supported"]:
        raise ValueError(st["why"])
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, f'"{st["path"]}" --autostart')
        else:
            try:
                winreg.DeleteValue(k, NAME)
            except FileNotFoundError:
                pass
    return status()
