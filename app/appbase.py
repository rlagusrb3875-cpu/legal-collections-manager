# -*- coding: utf-8 -*-
"""여러 기능 파일이 함께 쓰는 값과 도움 함수."""
import json
import os

APP_NAME = "종합관리"
DEFAULT_BOOK = "기본 채권"
HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.local/share"), "CourtSearch")
POINTER = os.path.join(LOCAL, "config.json")


def _desktop():
    home = os.path.expanduser("~")
    for d in (os.path.join(home, "Desktop"), os.path.join(home, "바탕 화면"), os.path.join(home, "OneDrive", "Desktop"),
              os.path.join(home, "OneDrive", "바탕 화면")):
        if os.path.isdir(d):
            return d
    return home


def default_data_dir():
    return os.path.join(os.path.expanduser("~"), "Documents", "사건조회도우미")


def _load_pointer():
    try:
        with open(POINTER, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_pointer(d):
    os.makedirs(LOCAL, exist_ok=True)
    with open(POINTER, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)


# ---------------------------------------------------------------- 진단 기록 (사이트가 바뀌었을 때 원인 찾기용)

def log_event(kind, detail):
    """예상과 다른 사이트 응답 등을 %LOCALAPPDATA%\\CourtSearch\\진단\\응답기록_날짜.txt 에 남긴다."""
    import time
    try:
        d = os.path.join(LOCAL, "진단")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, time.strftime("응답기록_%Y%m%d.txt")), "a", encoding="utf-8") as f:
            f.write(time.strftime("[%H:%M:%S] ") + kind + "\n" + str(detail)[:6000] + "\n\n")
    except Exception:
        pass


def diag_files():
    d = os.path.join(LOCAL, "진단")
    return sorted((os.path.join(d, f) for f in os.listdir(d)), reverse=True) if os.path.isdir(d) else []


# ---------------------------------------------------------------- 같은 자료 폴더를 여러 PC가 쓰지 않게

def is_network_path(path):
    p = os.path.abspath(path)
    if p.startswith("\\\\"):
        return True
    if os.name == "nt":
        try:
            import ctypes
            return ctypes.windll.kernel32.GetDriveTypeW(os.path.splitdrive(p)[0] + "\\") == 4  # DRIVE_REMOTE
        except Exception:
            return False
    return False


def lock_check(data_dir, touch=True):
    """사용중.txt 로 지금 이 자료 폴더를 쓰는 PC를 표시. 다른 PC가 3분 안에 쓴 흔적이 있으면 그 정보를 돌려준다."""
    import socket
    import time
    p = os.path.join(data_dir, "사용중.txt")
    me = {"host": socket.gethostname(), "user": os.environ.get("USERNAME") or os.environ.get("USER", ""), "pid": os.getpid()}
    other = None
    try:
        with open(p, encoding="utf-8") as f:
            cur = json.load(f)
        if (cur.get("host"), cur.get("pid")) != (me["host"], me["pid"]) and time.time() - float(cur.get("at", 0)) < 180:
            other = cur
    except Exception:
        pass
    if touch and not other:
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(dict(me, at=time.time()), f, ensure_ascii=False)
        except Exception:
            pass
    return other


# ---------------------------------------------------------------- 새 판 알림

def newer_version(folder, current):
    """folder 안의 「종합관리_v1.2.3.zip/exe」(예전 이름 사건조회도우미_v… 도) 중 지금보다 새 판이 있으면 (판, 경로)"""
    import re
    if not folder or not os.path.isdir(folder):
        return None
    def key(v):
        return tuple(int(x) for x in v.split("."))
    best = None
    for f in os.listdir(folder):
        m = re.search(r"(?:종합관리|사건조회도우미)_v(\d+\.\d+\.\d+)\.(zip|exe)$", f)
        if m and key(m.group(1)) > key(current) and (not best or key(m.group(1)) > key(best[0])):
            best = (m.group(1), os.path.join(folder, f))
    return best
