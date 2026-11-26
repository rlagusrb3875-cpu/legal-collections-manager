# -*- coding: utf-8 -*-
"""나의사건검색 사이트의 기본 정보 (법원 목록, 사건구분, 업무유형별 조회 주소, 칸 이름).

사이트가 화면을 바꿔도 따라갈 수 있게, 사이트의 화면 파일에서 직접 읽어 만든다.
- 프로그램에는 만들 때 받아 둔 사본(data/court_meta.json)이 들어 있고,
- 설정 화면의 「법원 정보 새로 받기」로 언제든 다시 만들 수 있다.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
BUILTIN = os.path.join(os.path.dirname(HERE), "data", "court_meta.json")


# ---------------------------------------------------------------- 사이트 파일 읽기

def _parse_courts(cbx_js):
    i = cbx_js.find("ssgocbx.setCortCd")
    body = cbx_js[i:]
    j = body.find("\n}")
    body = body[:j] if j > 0 else body
    out = []
    for code, name in re.findall(r'addItem\(\s*"([^"]+)"\s*,\s*"([^"]*)"\s*\)', body):
        if code.startswith("A") or not name.strip() or set(name) <= {"-"}:
            continue
        out.append({"code": code, "name": name.strip()})
    return out


def _parse_case_types(cbx_js):
    """법원코드별 사건구분 목록. {"default": [[코드, 이름]...], "000100": [...], ...}"""
    i = cbx_js.find("ssgocbx.setCsDvsCd")
    j = cbx_js.find("ssgocbx.setCortCd")
    body = cbx_js[i:j if j > i else None]
    # if (...) {  /  } else if (...) {  /  } else {  로 나뉜 덩어리
    heads = list(re.finditer(r'(?:else\s+)?if\s*\(([^{]*?)\)\s*\{|else\s*\{', body))
    result = {}
    for n, h in enumerate(heads):
        end = heads[n + 1].start() if n + 1 < len(heads) else len(body)
        items = [[c, nm.strip()] for c, nm in re.findall(r'addItem\(\s*"([^"]+)"\s*,\s*"([^"]*)"\s*\)', body[h.end():end])
                 if not c.startswith("A") and nm.strip()]
        if not items:
            continue
        cond = h.group(1)
        codes = re.findall(r'"(\d{6})"', cond or "")
        keys = codes if codes else ["default"]
        for k in keys:
            result.setdefault(k, [])
            seen = {c for c, _ in result[k]}
            result[k] += [it for it in items if it[0] not in seen]
    return result


def _parse_properties(index_html):
    m = re.search(r'var\s+properties\s*=\s*(\{.*?\})\s*;', index_html, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except ValueError:
        return {}


def _parse_tasks(ssgo_js):
    i = ssgo_js.find("_TASK:")
    body = ssgo_js[i:i + 20000]
    out = {}
    for m in re.finditer(r'(\w+)\s*:\s*\{\s*ID\s*:\s*"(\w+)"\s*,\s*NM\s*:\s*"([^"]*)"\s*,\s*URL\s*:\s*\{([^}]*)\}', body):
        urls = dict(re.findall(r'(\w+)\s*:\s*"([^"]*)"', m.group(4)))
        out[m.group(2)] = {"name": m.group(3), "gnrl_xml": urls.get("CS_GNRL_CTT", ""), "prog_xml": urls.get("CS_PROG_CTT", "")}
    return out


def _parse_screen(xml):
    """화면 파일 하나에서: 조회 주소, 요청 묶음 이름, 칸 이름(id→한글), 함께 쓰는 하위 화면."""
    info = {"action": "", "ref": [], "labels": {}, "subs": []}
    for m in re.finditer(r'<xf:submission\s[^>]*id="sbm_search"[^>]*>', xml):
        tag = m.group(0)
        a = re.search(r'action="([^"]+)"', tag)
        r = re.search(r"ref='([^']*)'|ref=\"([^\"]*)\"", tag)
        info["action"] = a.group(1) if a else ""
        ref = (r.group(1) or r.group(2)) if r else ""
        info["ref"] = re.findall(r'(dma_\w+)', ref)
        break
    for kid, name in re.findall(r'<w2:(?:key|column)\s+id="([^"]+)"\s+name="([^"]*)"', xml):
        if name and not re.fullmatch(r'name\d*', name):
            info["labels"].setdefault(kid, name)
    info["subs"] = sorted(set(re.findall(r'getCtxtPathUrl\(\s*"(/ui/ssgo\d+/SSGO\w+\.xml)"', xml)))
    return info


def build(fetch):
    """fetch(경로) -> 글자. 사이트 파일을 받아 정보를 만든다."""
    index = fetch("/ssgo/index.on?cortId=www")
    cbx = fetch("/ssgo/cm/js/biz/ssgocbx.js")
    sjs = fetch("/ssgo/cm/js/ssgo.js")
    props = _parse_properties(index)
    tasks = _parse_tasks(sjs)
    labels = {}
    seen_subs = set()
    for tid, t in tasks.items():
        for kind in ("gnrl", "prog"):
            path = t.get(kind + "_xml")
            if not path:
                continue
            try:
                s = _parse_screen(fetch("/ssgo" + path))
            except Exception:
                continue
            t[kind] = {"action": s["action"], "ref": s["ref"]}
            for k, v in s["labels"].items():
                labels.setdefault(k, v)
            for sub in s["subs"]:
                if sub in seen_subs:
                    continue
                seen_subs.add(sub)
                try:
                    for k, v in _parse_screen(fetch("/ssgo" + sub))["labels"].items():
                        labels.setdefault(k, v)
                except Exception:
                    pass
    dvs_task = {k.split(".", 2)[2]: v for k, v in props.items() if k.startswith("ctt.csDvsCd.")}
    dvsnm_task = {k.split(".", 2)[2]: v for k, v in props.items() if k.startswith("ctt.csDvsNm.")}
    meta = {
        "courts": _parse_courts(cbx),
        "case_types": _parse_case_types(cbx),
        "dvs_task": dvs_task,
        "dvsnm_task": dvsnm_task,
        "tasks": tasks,
        "labels": labels,
    }
    if not meta["courts"] or not meta["tasks"]:
        raise RuntimeError("사이트에서 법원 정보를 읽지 못했습니다 (사이트 구조가 바뀌었을 수 있음)")
    return meta


# ---------------------------------------------------------------- 사용

class Meta:
    def __init__(self, data):
        self.d = data
        self.courts = data["courts"]
        self._court_by_name = {c["name"]: c for c in self.courts}
        self._court_by_code = {c["code"]: c for c in self.courts}

    @classmethod
    def load(cls, override_path=None):
        for p in (override_path, BUILTIN):
            if p and os.path.isfile(p):
                with open(p, encoding="utf-8") as f:
                    return cls(json.load(f))
        raise FileNotFoundError("법원 정보 파일이 없습니다")

    def court(self, code_or_name):
        return self._court_by_code.get(code_or_name) or self._court_by_name.get(code_or_name)

    def court_names(self):
        return [c["name"] for c in self.courts]

    def case_types(self, court_code):
        ct = self.d["case_types"]
        return ct.get(court_code) or ct.get("default") or []

    def case_type_code(self, court_code, dvs_name):
        for code, nm in self.case_types(court_code):
            if nm == dvs_name:
                return code
        # 법원 목록에 없으면 다른 법원 목록에서라도 찾는다
        for lst in self.d["case_types"].values():
            for code, nm in lst:
                if nm == dvs_name:
                    return code
        return None

    def all_dvs_names(self):
        names = set()
        for lst in self.d["case_types"].values():
            names.update(nm for _, nm in lst)
        return names

    def task_of(self, dvs_code, dvs_name=""):
        t = self.d["dvs_task"].get(dvs_code) or self.d["dvsnm_task"].get(dvs_name)
        return t if t in self.d["tasks"] else None

    def task(self, tid):
        return self.d["tasks"].get(tid)

    def label(self, key):
        return self.d["labels"].get(key, key)
