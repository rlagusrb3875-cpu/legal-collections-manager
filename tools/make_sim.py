# -*- coding: utf-8 -*-
"""시뮬레이션용 HTML 하나 만들기 — 실제 프로그램 코드를 브라우저 안 파이썬(Pyodide)에서 시연 자료로 돌린다.

    python tools/make_sim.py            → dist/사건조회도우미_시뮬레이션.html

- 화면(app/ui)과 기능 코드(app/*.py, app/core, app/data)를 그대로 넣는다. 고친 코드를 다시 반영하려면 이 파일을 다시 실행.
- 처음 열 때 Pyodide(브라우저용 파이썬)를 인터넷(cdn.jsdelivr.net)에서 받는다. 법원 사이트에는 접속하지 않는다.
- 자료는 브라우저 메모리에만 있고 새로 고치면 처음 시연 상태로 돌아간다.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")
PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/"


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def sources():
    out = {}
    for base, dirs, files in os.walk(APP):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "ui", ".claude")]
        for f in files:
            if f.endswith((".py", ".json")) and f != "main.py":
                full = os.path.join(base, f)
                out[os.path.relpath(full, APP).replace(os.sep, "/")] = read(full)
    return out


BOOT_PY = r'''
import json, os, sys
for p, c in json.loads(SRC).items():
    full = "/sim/app/" + p
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(c)
sys.path.insert(0, "/sim/app")
os.environ["LOCALAPPDATA"] = "/sim/local"
os.environ["USERNAME"] = "시연"
os.makedirs(os.path.expanduser("~/Desktop"), exist_ok=True)

import base64, shutil
import traceback
import js
from bridge import Bridge
from demo import install, install_forms
from core import forms as FM
import form_sample

# 브라우저 안에는 PDF 부품(pdfium·reportlab)이 없다 → 견본 양식의 그림·칸은 미리 만들어 넣은 것을 쓴다
SIMF = json.loads(SIMFORM)


def _sample_make(path):
    with open(path, "wb") as f:
        f.write(base64.b64decode(SIMF["pdf"]))
    return path


def _tw(s, size, kind="myeongjo", bold=False):  # 글자 폭 어림 (한글 1em, 영문·숫자 0.55em)
    return sum(1.0 if ord(ch) > 0x2E80 else 0.3 if ch == " " else 0.55 for ch in s) * size * (1.04 if bold else 1)


def _build(src, pages, fields, sets, out, kind="myeongjo", seal=None):
    out = out[:-4] + "_시뮬레이션_값목록.txt"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    names = {i["k"]: i["n"] for i in FM.ITEMS}
    with open(out, "w", encoding="utf-8") as f:
        f.write("시뮬레이션에서는 PDF를 만들지 않아요. 실제 프로그램에서는 회사 양식 PDF 위에 아래 값이 채워져요.\n\n")
        for i, v in enumerate(sets, 1):
            f.write(f"[{i}]\n")
            for fd in fields:
                k = fd.get("item")
                if fd["type"] == "check":
                    if v.get(k) == fd.get("opt"):
                        f.write(f"  ✓ {names.get(k, k)} = {fd['opt']}\n")
                elif fd["type"] != "seal":
                    f.write(f"  {names.get(k, k)}: {FM.fmt_value(k, fd.get('fmt'), v.get(k))}{fd.get('suffix', '') if v.get(k) else ''}\n")
            f.write("\n")
    return out


form_sample.make = _sample_make
FM.normalize = lambda src, dst: shutil.copyfile(src, dst)
FM.page_info = lambda path: json.loads(json.dumps(SIMF["pages"]))
FM.render_png = lambda path, index=0, scale=2.0: SIMF["png"]
FM.detect = lambda path: json.loads(json.dumps(SIMF["detect"]))
FM.text_width = _tw
FM.build = _build

bridge = Bridge("/sim/data")
install(bridge)
install_forms(bridge, force=True)
bridge.store.set_setting("run.delay", 0)
bridge.store.set_setting("me", "시연")


def _download(path):
    """프로그램이 파일·폴더를 열려고 하면 → 브라우저 내려받기로"""
    import shutil
    if os.path.isdir(path) or os.path.exists(os.path.join(os.path.dirname(path), "_목록.xlsx")):
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        z = shutil.make_archive("/tmp/" + os.path.basename(folder), "zip", folder)
        js.simDownload(z, os.path.basename(folder) + ".zip")
    elif os.path.isfile(path):
        js.simDownload(path, os.path.basename(path))
    return True


def _blocked(text):
    def f(*a, **k):
        raise ValueError(text)
    return f


bridge.reveal = _download
bridge.open_path = _download
bridge.auction_start = _blocked("시뮬레이션에서는 법원경매정보 창을 열 수 없어요 (경매 결과 화면은 시연 자료로 볼 수 있어요)")
bridge.auction_window = bridge.auction_start
bridge.meta_refresh = _blocked("시뮬레이션에서는 법원 사이트에 접속하지 않아요")
bridge.data_dir_change = _blocked("시뮬레이션에서는 자료 폴더를 바꿀 수 없어요")
bridge.choose_folder = lambda: None
_fm_make = bridge.fm_make
bridge.fm_make = lambda *a, **k: dict(_fm_make(*a, **k), sim=True)
for _n in ("fm_add", "fm_import", "fm_seal_set"):
    setattr(bridge, _n, _blocked("시뮬레이션에서는 내 PDF·그림을 넣을 수 없어요 — 양식함의 견본 양식으로 시연해 보세요 (실제 프로그램에서는 돼요)"))


def dispatch(name, args_json):
    args = json.loads(args_json or "{}")
    if name.startswith("_") or not hasattr(bridge, name):
        return json.dumps({"ok": False, "error": f"알 수 없는 기능: {name}"}, ensure_ascii=False)
    try:
        fn = getattr(bridge, name)
        data = fn(**args) if isinstance(args, dict) else fn(*args)
        return json.dumps({"ok": True, "data": data}, ensure_ascii=False, default=str)
    except Exception as ex:
        print(traceback.format_exc())
        return json.dumps({"ok": False, "error": str(ex) or ex.__class__.__name__}, ensure_ascii=False)
'''

BOOT_JS = r'''
<div id="simLoad"><div class="box"><div class="lg"><i class="ci"><img src="data:image/png;base64,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" alt="법조치 통합관리"></i>종합관리</div><b>시뮬레이션 준비 중</b><span id="simStep">브라우저용 파이썬을 받는 중… (처음 한 번 10~30초)</span><div class="pb"><i id="simBar"></i></div>
<small>실제 프로그램 코드를 시연용 가짜 자료로 돌려요. 법원 사이트에는 접속하지 않고, 자료는 이 창 안에만 있어요.</small></div></div>
<div id="simBadge" title="새로 고치면 처음 시연 상태로 돌아가요">시뮬레이션 · 가짜 자료 <button onclick="location.reload()">처음으로</button></div>
<input type="file" id="simFile" accept=".xlsx,.xlsm,.xls,.csv" hidden>
<script src="__PYODIDE__pyodide.js"></script>
<script>
(async () => {
  const step = (t, p) => { document.getElementById('simStep').textContent = t; document.getElementById('simBar').style.width = p + '%'; };
  try {
    step('브라우저용 파이썬을 받는 중… (처음 한 번 10~30초)', 10);
    const py = await loadPyodide({indexURL: '__PYODIDE__'});
    step('엑셀 부품을 받는 중…', 45);
    await py.loadPackage('ssl');
    await py.loadPackage('openpyxl').catch(async () => { await py.loadPackage('micropip'); await py.pyimport('micropip').install(['openpyxl']); });
    step('프로그램과 시연 자료를 준비하는 중…', 75);
    window.simDownload = (path, name) => {
      const data = py.FS.readFile(path);
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([data]));
      a.download = name; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      toast('내려받기: ' + name);
    };
    py.globals.set('SRC', document.getElementById('pysrc').textContent);
    py.globals.set('SIMFORM', document.getElementById('pyform').textContent);
    await py.runPythonAsync(document.getElementById('pyboot').textContent);
    const dispatch = py.globals.get('dispatch');
    const pickFile = () => new Promise(res => {
      const inp = document.getElementById('simFile');
      inp.value = '';
      inp.onchange = async () => {
        const f = inp.files[0]; if (!f) return res(null);
        const p = '/sim/upload/' + f.name;
        py.FS.mkdirTree('/sim/upload');
        py.FS.writeFile(p, new Uint8Array(await f.arrayBuffer()));
        res(p);
      };
      inp.click();
    });
    window.pywebview = {api: {call: async (name, args) => {
      if (name === 'choose_file') return {ok: true, data: await pickFile()};
      await new Promise(r => setTimeout(r, 0));
      return JSON.parse(dispatch(name, JSON.stringify(args || {})));
    }}};
    step('다 됐어요', 100);
    document.getElementById('simLoad').remove();
    window.dispatchEvent(new Event('pywebviewready'));
  } catch (e) {
    step('준비하지 못했어요: ' + e.message + ' — 인터넷 연결(cdn.jsdelivr.net)을 확인해 주세요', 100);
    console.error(e);
  }
})();
</script>
'''

SIM_CSS = """
#simLoad{position:fixed;inset:0;background:var(--bg);z-index:999;display:grid;place-items:center}
#simLoad .box{width:440px;max-width:calc(100% - 32px);background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:26px 26px 22px;display:flex;flex-direction:column;gap:10px}
#simLoad .lg{display:flex;align-items:center;gap:10px;font-weight:700;font-size:16px;margin-bottom:6px}
#simLoad .lg i{width:42px;height:28px;border-radius:8px;background:#fff;border:1px solid var(--line);display:grid;place-items:center;font-style:normal}
#simLoad .lg i img{width:28px;height:auto;display:block}
#simLoad span,#simLoad small{color:var(--sub);font-size:13px;line-height:1.6}
#simLoad small{color:var(--faint);font-size:12px}
#simLoad .pb{height:5px;background:var(--line);border-radius:4px;overflow:hidden}
#simLoad .pb i{display:block;height:100%;width:0;background:var(--text);transition:width .4s}
#simBadge{position:fixed;right:16px;bottom:14px;z-index:60;background:var(--dark-btn);color:var(--dark-btn-text);font-size:12px;border-radius:20px;padding:5px 6px 5px 13px;display:flex;gap:8px;align-items:center;opacity:.92}
#simBadge button{border:0;border-radius:14px;padding:3px 9px;font-size:11.5px;background:rgba(127,127,127,.35);color:inherit}
"""


def sim_form():
    """견본 주소보정서: PDF · 쪽 크기 · 그림 · 칸 찾기 결과를 이 PC에서 미리 만들어 둔다."""
    import base64
    import tempfile
    sys.path.insert(0, APP)
    from core import forms as FM
    from form_sample import make
    p = make(os.path.join(tempfile.mkdtemp(), "sample.pdf"))
    with open(p, "rb") as f:
        pdf = base64.b64encode(f.read()).decode()
    return {"pdf": pdf, "pages": FM.page_info(p), "png": FM.render_png(p, 0, 2.0), "detect": FM.detect(p)}


def main():
    ui = os.path.join(APP, "ui")
    html = read(os.path.join(ui, "index.html"))
    html = re.sub(r'<link rel="stylesheet" href="([\w.]+)">', lambda m: f"<style>\n{read(os.path.join(ui, m[1]))}\n</style>", html)
    html = html.replace("</head>", f"<style>{SIM_CSS}</style>\n</head>")
    html = html.replace("<title>종합관리</title>", "<title>종합관리 (시뮬레이션)</title>")
    src = json.dumps(sources(), ensure_ascii=False).replace("</", "<\\/")
    form = json.dumps(sim_form(), ensure_ascii=False).replace("</", "<\\/")
    boot = (f'<script type="application/json" id="pysrc">{src}</script>\n'
            f'<script type="application/json" id="pyform">{form}</script>\n'
            f'<script type="text/x-python" id="pyboot">{BOOT_PY}</script>\n' + BOOT_JS.replace("__PYODIDE__", PYODIDE))
    scripts = re.findall(r'<script src="([\w.]+)"></script>', html)
    for s in scripts:
        js = read(os.path.join(ui, s))
        if "</script" in js:
            sys.exit(f"{s} 안에 </script 글자가 있어요")
        html = html.replace(f'<script src="{s}"></script>', f"<script>\n{js}\n</script>")
    html = html.replace("</body>", boot + "\n</body>")
    out = os.path.join(ROOT, "dist", "종합관리_시뮬레이션.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{out} ({os.path.getsize(out) // 1024}KB)")


if __name__ == "__main__":
    main()
