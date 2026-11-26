# -*- coding: utf-8 -*-
"""종합관리 (사건 조회 · 법조치) — 시작 파일.

실행 방식
  1) 앱 창 모드 (기본): pywebview (Windows는 Edge WebView2) 창
  2) 브라우저 모드 (예비): 창을 못 띄우면 내 PC 안(127.0.0.1)에서만 열리는 화면을 Edge로 띄움
     --browser 로 강제 가능
  --self-test : 바탕화면에 자가진단 결과 TXT
  --demo <폴더>: 법원 사이트 대신 꾸며 낸 결과로 화면 점검 (개발용)
"""
import json
import os
import sys
import threading
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE, os.path.join(ROOT, "lib")):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

LOG_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.local/share"), "CourtSearch")
APP_PORT = 42001  # 앱 창 주소 고정 (파일 업무 도구는 42011)
UI_DIR = os.path.join(HERE, "ui")


def _log_error(msg):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, "오류기록.txt"), "a", encoding="utf-8") as f:
            f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg + "\n")
    except Exception:
        pass


if sys.stdout is None:  # pythonw 로 실행하면 print 가 막히지 않게
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from bridge import APP_NAME, VERSION, Bridge  # noqa: E402

_demo_dir = None
if "--demo" in sys.argv:
    i = sys.argv.index("--demo")
    _demo_dir = sys.argv[i + 1] if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--") else os.path.join(LOG_DIR, "demo")
bridge = Bridge(_demo_dir) if _demo_dir else Bridge()
if _demo_dir:
    from demo import install
    install(bridge)


def dispatch(name, args):
    """화면에서 온 호출 하나를 처리. {ok, data|error}"""
    if name.startswith("_") or not hasattr(bridge, name):
        return {"ok": False, "error": f"알 수 없는 기능: {name}"}
    try:
        fn = getattr(bridge, name)
        data = fn(**(args or {})) if isinstance(args, dict) else fn(*(args or []))
        return {"ok": True, "data": data}
    except Exception as ex:
        _log_error(f"{name}: {traceback.format_exc()}")
        return {"ok": False, "error": str(ex) or ex.__class__.__name__}


class JsApi:
    """pywebview 에 노출하는 유일한 객체 (속성 탐색을 피하려고 메서드 하나만)."""

    def call(self, name, args=None):
        return dispatch(name, args)


# ---------------------------------------------------------------- 앱 창 모드

def _register_drops(window):
    from webview.dom import DOMEventHandler

    def on_drop(e):
        files = (e.get("dataTransfer") or {}).get("files") or []
        paths = [f.get("pywebviewFullPath") for f in files if f.get("pywebviewFullPath")]
        bridge.emit({"type": "drop", "paths": paths})

    def noop(e):
        pass

    body = window.dom.body
    body.events.dragenter += DOMEventHandler(noop, prevent_default=True, stop_propagation=True)
    body.events.dragover += DOMEventHandler(noop, prevent_default=True, stop_propagation=True, debounce=500)
    body.events.drop += DOMEventHandler(on_drop, prevent_default=True, stop_propagation=True)


def run_app():
    import webview

    theme = bridge.store.settings["look"].get("theme", "light")
    window = webview.create_window(
        APP_NAME, url=os.path.join(UI_DIR, "index.html"), js_api=JsApi(),
        width=1366, height=880, min_size=(1100, 700), background_color="#0A0D14" if theme == "dark" else "#F3F4F7",
        text_select=True)
    bridge.window = window

    def on_loaded():
        try:
            _register_drops(window)
        except Exception:
            _log_error("끌어다 놓기 등록 실패: " + traceback.format_exc())

    window.events.loaded += on_loaded
    storage = os.path.join(LOG_DIR, "webview")
    # Windows 는 Edge(WebView2)만 사용 — 없으면 예외 → 브라우저 모드로 넘어감 (구형 IE 화면 방지)
    gui = "edgechromium" if sys.platform == "win32" else None
    # 주소(포트 42001)는 고정 — 화면 설정(localStorage: 홈 필터·접기 상태)이 주소별로 저장되기 때문.
    # 대신 판이 바뀌면 캐시를 비워 예전 판 화면이 남지 않게 한다.
    _clear_old_cache(storage)
    port = APP_PORT
    if not _port_free(port):  # 다른 프로그램(예: 예전 판 파일 업무 도구)이 차지 → 남의 화면 대신 빈 번호로
        port = _free_port()
        _log_error(f"포트 {APP_PORT} 사용 중 — 이번에는 {port}로 엽니다 (화면 설정은 이번 한 번 기본값)")
    webview.start(gui=gui, private_mode=False, storage_path=storage, debug="--debug" in sys.argv, http_port=port,
                  icon=os.path.join(HERE, "app.ico"))


def _port_free(port):
    """그 번호(포트)를 다른 프로그램이 쓰고 있지 않은지 — 쓰고 있으면 남의 화면이 뜬다"""
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return False  # 누가 이미 받고 있음
    except OSError:
        pass
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def _free_port():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


def _clear_old_cache(storage):
    """판이 바뀌면 앱 창(WebView2)의 캐시만 비운다 — localStorage 등 화면 설정은 그대로 둔다"""
    import shutil
    mark = os.path.join(LOG_DIR, "webview_version.txt")
    stamp = VERSION
    try:  # 빌드본에는 판-지문(1.12.1-ab12cd34)이 들어 있다 — 같은 판을 다시 빌드해도 캐시를 비우게
        with open(os.path.join(HERE, "VERSION"), encoding="utf-8") as f:
            stamp = f.read().strip() or VERSION
    except OSError:
        pass
    try:
        with open(mark, encoding="utf-8") as f:
            if f.read().strip() == stamp:
                return
    except OSError:
        pass
    left = False
    for sub in ("Cache", "Code Cache", "Service Worker"):
        d = os.path.join(storage, "EBWebView", "Default", sub)
        shutil.rmtree(d, ignore_errors=True)
        left = left or os.path.exists(d)
    if left:  # 다른 창이 열려 있어 못 지웠으면 다음 실행 때 다시 시도
        return
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(mark, "w", encoding="utf-8") as f:
            f.write(stamp)
    except OSError:
        pass


# ---------------------------------------------------------------- 브라우저 모드 (예비)

def run_browser(open_window=True, port=0):
    import mimetypes
    import webbrowser
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import unquote, urlparse

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = unquote(urlparse(self.path).path).lstrip("/") or "index.html"
            full = os.path.normpath(os.path.join(UI_DIR, path))
            if not full.startswith(UI_DIR) or not os.path.isfile(full):
                return self._send(404, b"not found", "text/plain")
            with open(full, "rb") as f:
                body = f.read()
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith("javascript"):
                ctype += "; charset=utf-8"
            self._send(200, body, ctype)

        def do_POST(self):
            if self.path != "/api":
                return self._send(404, b"", "text/plain")
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n) or b"{}")
            res = dispatch(req.get("name", ""), req.get("args"))
            self._send(200, json.dumps(res, ensure_ascii=False).encode("utf-8"), "application/json")

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)  # 내 PC 안에서만 접속 가능
    url = f"http://127.0.0.1:{srv.server_address[1]}/index.html?mode=browser"
    print("브라우저 모드:", url, flush=True)
    if open_window:
        opened = False
        if sys.platform == "win32":
            import subprocess
            for exe in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
                if os.path.exists(exe):
                    subprocess.Popen([exe, f"--app={url}", "--window-size=1366,880"])
                    opened = True
                    break
        if not opened:
            webbrowser.open(url)

        def watchdog():  # 화면을 닫으면 (호출이 끊기면) 스스로 종료
            while True:
                time.sleep(5)
                if time.time() - bridge.last_poll > 25:
                    os._exit(0)
        bridge.last_poll = time.time() + 30
        threading.Thread(target=watchdog, daemon=True).start()
    srv.serve_forever()


def ui_smoke(timeout=25):
    """화면을 숨긴 앱 창으로 띄워 화면↔기능 호출이 실제로 되는지 확인. (성공여부, 내용)"""
    import webview

    result = {}
    window = webview.create_window("smoke", url=os.path.join(UI_DIR, "index.html"), js_api=JsApi(), hidden=True)
    bridge.window = window

    def probe():
        try:
            deadline = time.time() + timeout
            while time.time() < deadline:
                time.sleep(0.5)
                try:
                    window.evaluate_js("window.__smoke || (window.__smoke = 'wait', api('info').then("
                                       "i => window.__smoke = 'ok:' + i.mode, e => window.__smoke = 'err:' + e.message))")
                    v = window.evaluate_js("window.__smoke")
                except Exception as ex:
                    v = f"err:{ex}"
                if v and v != "wait":
                    result["v"] = v
                    break
            else:
                result["v"] = "err:시간 초과 (화면이 응답하지 않음)"
            # 경매: 법원경매정보 창을 숨겨서 열고 검색칸이 준비되는지
            try:
                import json as _j
                from core import auction as AU
                aw = webview.create_window("auction-check", AU.SEARCH_URL, hidden=True)
                ok = False
                for _ in range(60):
                    time.sleep(0.5)
                    try:
                        if _j.loads(aw.evaluate_js(AU.READY_JS) or "{}").get("ready"):
                            ok = True
                            break
                    except Exception:
                        pass
                result["auction"] = "ok" if ok else "검색 화면을 30초 안에 찾지 못함"
                aw.destroy()
            except Exception as ex:
                result["auction"] = f"err:{ex}"
        except Exception as ex:
            result["v"] = f"err:{ex}"
        finally:
            window.destroy()

    gui = "edgechromium" if sys.platform == "win32" else None
    webview.start(probe, gui=gui, private_mode=True)
    v = result.get("v", "err:알 수 없음")
    ui_smoke.auction = result.get("auction", "확인 못 함")
    return v.startswith("ok:"), v


def self_test(with_ui=True):
    """설치·접속이 제대로 되는지 확인 → 바탕화면에 결과 TXT."""
    lines = [f"{APP_NAME} {VERSION} 자가 진단 ({time.strftime('%Y-%m-%d %H:%M')})",
             f"Python {sys.version.split()[0]} / {sys.platform}", f"위치: {ROOT}", f"자료 폴더: {bridge.data_dir}", ""]
    for mod in ("openpyxl", "xlrd", "truststore", "webview", "clr"):
        try:
            m = __import__(mod)
            lines.append(f"[정상] {mod} {getattr(m, '__version__', '')}")
        except Exception as ex:
            lines.append(f"[문제] {mod}: {ex}")
    try:
        cap = bridge.court.captcha()
        lines.append(f"[정상] 법원 사이트 접속 · 자동입력방지 그림 받기 ({len(cap['image'])}자)")
    except Exception as ex:
        lines.append(f"[문제] 법원 사이트 접속: {ex}")
    if with_ui:
        try:
            ok, msg = ui_smoke()
            lines.append(f"[{'정상' if ok else '문제'}] 앱 창 화면 연결: {msg}")
            au = getattr(ui_smoke, "auction", "")
            lines.append(f"[{'정상' if au == 'ok' else '문제'}] 법원경매정보 창 · 검색 화면: {au}")
        except Exception as ex:
            lines.append(f"[문제] 앱 창 화면 연결: {ex}")
    from appbase import diag_files, is_network_path
    if is_network_path(bridge.data_dir):
        lines.append("[주의] 자료 폴더가 네트워크(공용) 폴더예요 — 여러 PC가 함께 쓰면 자료가 깨질 수 있어요")
    if bridge.other_user:
        lines.append(f"[주의] 다른 PC({bridge.other_user.get('host')})가 이 자료 폴더를 쓰는 중이에요")
    logs = diag_files()
    lines.append(f"진단 기록: {len(logs)}개" + (f" (최근: {os.path.basename(logs[0])})" if logs else ""))
    if logs:
        try:
            with open(logs[0], encoding="utf-8") as f:
                lines += ["", "---- 최근 진단 기록 (끝부분) ----", f.read()[-4000:]]
        except Exception:
            pass
    from bridge import _desktop
    out = os.path.join(_desktop(), "종합관리_자가진단.txt")
    try:
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception:
        pass
    print("\n".join(lines))
    return lines


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test(with_ui="--no-ui" not in sys.argv)
    elif "--browser" in sys.argv or "--serve" in sys.argv:
        port = 0
        if "--port" in sys.argv:
            port = int(sys.argv[sys.argv.index("--port") + 1])
        run_browser(open_window="--serve" not in sys.argv, port=port)
    else:
        try:
            run_app()
        except Exception:
            _log_error("앱 창을 열지 못해 브라우저 모드로 전환: " + traceback.format_exc())
            run_browser()
