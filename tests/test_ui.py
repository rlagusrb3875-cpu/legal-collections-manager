# -*- coding: utf-8 -*-
"""화면 점검 (개발 PC용 · 크롬 필요): 시연 자료로 모든 화면을 열어 오류가 없는지,
1366×768 노트북 크기에서 오른쪽으로 넘치는 곳이 없는지 확인한다.

    python tests/test_ui.py            (결과 캡처는 임시 폴더에)
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = next((p for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                           r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                           r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe") if os.path.exists(p)), None)

# 화면이 다 그려지면 결과를 제목에 적는다 (오류 문구 · 오른쪽 넘침)
PROBE = """<script>setTimeout(function(){var v=document.getElementById('view');var bad=v.innerText.indexOf('화면을 열지 못했어요')>=0;
var over=[...document.querySelectorAll('main *')].filter(function(e){var r=e.getBoundingClientRect();return r.width&&r.right>window.innerWidth+2}).slice(0,3).map(function(e){return e.tagName+'.'+e.className}).join(',');
document.title='RESULT '+JSON.stringify({bad:bad,h1:(document.querySelector('h1')||{}).innerText||'',over:over});},3500)</script>"""


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    if not CHROME:
        print("크롬이 없어 화면 점검을 건너뜀")
        return True
    tmp = tempfile.mkdtemp(prefix="court_ui_")
    port = free_port()
    env = dict(os.environ, LOCALAPPDATA=os.path.join(tmp, "la"))
    srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "app", "main.py"), "--serve", "--port", str(port), "--demo", os.path.join(tmp, "demo")],
                           env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = fail = 0
    try:
        base = f"http://127.0.0.1:{port}"
        for _ in range(40):
            try:
                urllib.request.urlopen(base + "/index.html", timeout=1)
                break
            except Exception:
                time.sleep(0.3)

        def api(name, args=None):
            req = urllib.request.Request(base + "/api", data=json.dumps({"name": name, "args": args or {}}).encode(), headers={"Content-Type": "application/json"})
            return json.loads(urllib.request.urlopen(req).read())["data"]
        aid = api("auction_list")[0]["id"]
        cid = api("ledger")[0]["id"]
        fid = api("fm_list")["forms"][0]["id"]
        screens = ["home", "pick", "cal", "ledger", "hist", "report", "auction", "settings", "settings/look", "settings/run", "settings/save",
                   "auction_case/" + json.dumps({"aid": aid, "tab": "t1"}), "auction_case/" + json.dumps({"aid": aid, "tab": "t3"}),
                   "case/" + json.dumps({"cid": cid}),
                   "lg_home", "lg_debtors", "lg_doc", "lg_dlv", "lg_rehab", "lg_std",
                   "fm", "fm_edit/" + json.dumps({"id": fid}), "fm_make/" + json.dumps({"fid": fid, "src": "dlv", "from": "dlv"}),
                   "fm_make/" + json.dumps({"fid": fid, "src": "ledger"}), "fm_company", "xl", "console", "settings/link", "settings/menu",
                   "dv_run", "dv_board", "dv_ledger", "dv_stats"]
        # 시험용 페이지: index.html 에 PROBE 를 붙인 사본
        ui = os.path.join(ROOT, "app", "ui")
        probe_dir = os.path.join(tmp, "ui")
        shutil.copytree(ui, probe_dir)
        with open(os.path.join(probe_dir, "index.html"), encoding="utf-8") as f:
            html = f.read().replace("</body>", PROBE + "</body>")
        with open(os.path.join(ui, "_probe.html"), "w", encoding="utf-8") as f:
            f.write(html)
        shots = os.path.join(tmp, "shots")
        os.makedirs(shots)
        for s in screens:
            url = f"{base}/_probe.html?mode=browser#" + urllib.parse.quote(s)
            name = s.split("/")[0] + ("_" + str(abs(hash(s)) % 1000) if "/" in s else "")
            out = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={tmp}/chrome",
                                  "--window-size=1366,768", "--virtual-time-budget=6000", "--dump-dom", url],
                                 capture_output=True, text=True, timeout=60).stdout
            subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={tmp}/chrome",
                            "--window-size=1366,768", "--virtual-time-budget=6000", f"--screenshot={shots}/{name}.png", url],
                           capture_output=True, timeout=60)
            i = out.find("RESULT ")
            res = json.loads(out[i + 7:out.find("</title>", i)]) if i >= 0 else {"bad": True, "h1": "", "over": "결과 없음"}
            good = not res["bad"] and res["h1"] and not res["over"]
            ok += bool(good)
            fail += not good
            print(f"  [{'정상' if good else '문제'}] {s.split('/')[0]:14s} {res['h1'][:20]:20s} {('넘침: ' + res['over']) if res['over'] else ''}")
        print(f"\n화면 정상 {ok} · 문제 {fail} · 캡처: {shots}")
    finally:
        srv.terminate()
        try:
            os.remove(os.path.join(ROOT, "app", "ui", "_probe.html"))
        except OSError:
            pass
    return fail == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
