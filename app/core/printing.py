# -*- coding: utf-8 -*-
"""인쇄기 목록 · PDF를 고른 인쇄기로 실제 크기(100%)로 인쇄 (Windows GDI).

PDF 프로그램(엣지 등)에 맡기면 인쇄기를 고를 수 없거나 크기가 줄어드는 일이 있어,
pdfium으로 쪽을 그림으로 만들어 인쇄기 해상도에 맞춰 종이 위치 그대로 보낸다.
"""
import json
import os
import subprocess
import sys

WIN = sys.platform == "win32"
MAX_DPI = 300


def list_printers():
    """[{name, default}] — 못 읽으면 빈 목록."""
    try:
        if WIN:
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                   "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
                   "Get-CimInstance Win32_Printer | Select-Object Name,Default | ConvertTo-Json -Compress"]
            out = subprocess.run(cmd, capture_output=True, timeout=15, creationflags=0x08000000).stdout.decode("utf-8", "ignore").strip()
            if not out:
                return []
            data = json.loads(out)
            if isinstance(data, dict):
                data = [data]
            return [{"name": d["Name"], "default": bool(d.get("Default"))} for d in data if d.get("Name")]
        out = subprocess.run(["lpstat", "-p", "-d"], capture_output=True, text=True, timeout=10).stdout
        default, names = "", []
        for line in out.splitlines():
            if line.startswith("printer ") or line.startswith("프린터 "):
                names.append(line.split()[1])
            elif "default destination" in line or "기본 대상" in line:
                default = line.split(":")[-1].strip()
        return [{"name": n, "default": n == default} for n in names]
    except Exception:
        return []


def _gdi():
    import ctypes
    from ctypes import wintypes

    class DOCINFOW(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_int), ("lpszDocName", wintypes.LPCWSTR), ("lpszOutput", wintypes.LPCWSTR),
                    ("lpszDatatype", wintypes.LPCWSTR), ("fwType", wintypes.DWORD)]

    gdi = ctypes.WinDLL("gdi32", use_last_error=True)
    gdi.CreateDCW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p]
    gdi.CreateDCW.restype = ctypes.c_void_p
    gdi.GetDeviceCaps.argtypes = [ctypes.c_void_p, ctypes.c_int]
    gdi.GetDeviceCaps.restype = ctypes.c_int
    gdi.StartDocW.argtypes = [ctypes.c_void_p, ctypes.POINTER(DOCINFOW)]
    gdi.StartDocW.restype = ctypes.c_int
    for fn in ("StartPage", "EndPage", "EndDoc", "AbortDoc", "DeleteDC"):
        getattr(gdi, fn).argtypes = [ctypes.c_void_p]
        getattr(gdi, fn).restype = ctypes.c_int
    return ctypes, gdi, DOCINFOW


def print_pdf(path, printer, copies=1):
    """PDF 한 파일을 인쇄기 하나로. 보낸 쪽 수를 돌려준다."""
    if not WIN:
        raise OSError("인쇄기로 바로 보내기는 Windows에서만 돼요")
    if not printer:
        raise OSError("인쇄기를 골라 주세요")
    import pypdfium2 as pdfium
    from PIL import ImageWin
    ctypes, gdi, DOCINFOW = _gdi()
    hdc = gdi.CreateDCW("WINSPOOL", printer, None, None)
    if not hdc:
        raise OSError(f"인쇄기를 열 수 없어요: {printer}")
    started = False
    doc = pdfium.PdfDocument(path)
    try:
        dpi_x = gdi.GetDeviceCaps(hdc, 88) or 300            # LOGPIXELSX
        dpi_y = gdi.GetDeviceCaps(hdc, 90) or dpi_x          # LOGPIXELSY
        off_x, off_y = gdi.GetDeviceCaps(hdc, 112), gdi.GetDeviceCaps(hdc, 113)  # PHYSICALOFFSETX/Y (종이 끝 ~ 인쇄 가능 영역)
        di = DOCINFOW(ctypes.sizeof(DOCINFOW), os.path.basename(path), None, None, 0)
        if gdi.StartDocW(hdc, ctypes.byref(di)) <= 0:
            raise OSError(f"인쇄를 시작하지 못했어요 (오류 {ctypes.get_last_error()})")
        started = True
        n = 0
        for _ in range(max(1, int(copies or 1))):
            for page in doc:
                w_pt, h_pt = page.get_size()
                scale = min(dpi_x, MAX_DPI) / 72
                img = page.render(scale=scale).to_pil().convert("RGB")
                W, H = round(w_pt / 72 * dpi_x), round(h_pt / 72 * dpi_y)   # 실제 크기 (100%)
                gdi.StartPage(hdc)
                ImageWin.Dib(img).draw(int(hdc), (-off_x, -off_y, W - off_x, H - off_y))
                gdi.EndPage(hdc)
                n += 1
        gdi.EndDoc(hdc)
        started = False
        return n
    except BaseException:
        if started:
            gdi.AbortDoc(hdc)
        raise
    finally:
        doc.close()
        gdi.DeleteDC(hdc)
