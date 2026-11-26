# -*- coding: utf-8 -*-
"""자료 저장 (이 PC 안의 폴더에 JSON 파일로).

폴더 구성
  cases.json        사건 대장
  results/<id>.json 사건별 조회 결과 (일반내용 최신본 + 진행내용 누적 + 회차 기록)
  runs.json         조회 기록
  todos.json        확인할 것 처리 상태·직접 넣은 기한
  settings.json     설정,  settings_log.json 설정 바꾼 기록
  backups/          자동 백업 (zip)
"""
import copy
import datetime as dt
import json
import os
import threading
import uuid
import zipfile

from .caseno import format_case_no

DEFAULT_RULES = [
    {"id": "r_cfm", "words": ["확정", "확정증명"], "status": "확정", "color": "green", "todo": True, "days": 0, "ask": False, "skip": True},
    {"id": "r_end", "words": ["취하", "각하", "조정성립", "화해성립", "종결", "이송"], "status": "종결", "color": "gray", "todo": False, "days": 0, "ask": False, "skip": True},
    {"id": "r_fix", "words": ["보정명령"], "status": "보정명령", "color": "red", "todo": True, "days": 7, "ask": True, "skip": False},
    {"id": "r_pub", "words": ["공시송달"], "status": "공시송달", "color": "orange", "todo": True, "days": 0, "ask": False, "skip": False},
    {"id": "r_dlv", "words": ["송달불능", "폐문부재", "이사불명", "수취인불명", "주소불명"], "status": "송달불능", "color": "orange", "todo": True, "days": 7, "ask": False, "skip": False},
    {"id": "r_jdg", "words": ["판결선고", "판결정본", "이행권고결정", "지급명령정본", "결정정본"], "status": "판결 선고", "color": "blue", "todo": True, "days": 0, "ask": False, "skip": False},
    {"id": "r_run", "words": ["도달", "변론기일", "준비서면", "접수"], "status": "진행 중", "color": "blue", "todo": False, "days": 0, "ask": False, "skip": False},
]

DEFAULT_SETTINGS = {
    "rules": DEFAULT_RULES,
    "default_status": "진행 중",
    "rule_rows": 5,
    "todo": {"confirm_days": 14, "hearing_days": 14, "hot_days": 3, "lookback_days": 60,
             "memo_on_done": True, "hide_done": "day", "start": "home"},
    "run": {"auto_submit": True, "digits": 0, "learned_digits": 0, "zoom": 1.5, "delay": 1.0, "cycle_days": 14,
            "retry_names": True, "name_patterns": ["㈜{}", "주식회사 {}", "{}(주)"]},
    "conditions": {"closed": True, "recent": True, "recent_days": 7, "stale": True, "stale_months": 6,
                   "stale_every": 30, "hearing_first": True, "hearing_days": 14, "owner": False, "owner_value": "",
                   "court": False, "court_value": "", "only_notfound": False, "only_hearing": False},
    "presets": [
        {"name": "정기 조회", "cond": {}},
        {"name": "기일 임박만", "cond": {"only_hearing": True}},
        {"name": "찾을 수 없음 다시", "cond": {"only_notfound": True, "closed": False, "recent": False, "stale": False}},
        {"name": "전체 점검", "cond": {"closed": False, "recent": False, "stale": False, "owner": False, "court": False}},
    ],
    "menu_hidden": [],
    "look": {"theme": "light", "font": "normal", "dense": False, "accent": ""},
    "excel": {"name": "{채권} 사건조회_{조건}_{날짜}", "sheets": ["요약", "일반내용", "진행내용", "당사자"], "only_changed": False,
              "cols": ["사건번호", "법원", "당사자", "사건명", "상태", "마지막 진행", "마지막 진행일", "종국결과", "확정일",
                       "다음 기일", "담당", "메모 1"]},
    "sihyo": {"folder": "", "auto": False, "key": "memo1"},
    "auction": {"auto_tabs": True, "auto_next": True, "auto_search": True, "delay": 5},
    "legal": {"creditor": {"name": "", "addr": "", "rep": "", "phone": ""}, "court": "", "days": 7, "ecfs": True, "basis": "약정",
              "agent": "", "form_tasks": {}, "form_items": [], "form_font": "myeongjo"},
    "save": {"backups": 10, "export_dir": "", "update_folder": ""},
    "aliases": {},
    "me": "",
}

SUMMARY_COLS = ["사건번호", "법원", "당사자", "사건명", "상태", "마지막 진행", "마지막 진행일", "종국결과", "확정일",
                "재판부", "접수일", "원고소가", "인지액", "다음 기일", "마지막 조회", "담당", "메모 1", "메모 2", "처리 메모"]


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today():
    return dt.date.today().isoformat()


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class Store:
    def __init__(self, root, settings_root=None):
        self.root = root
        self.rev = 0  # 자료가 바뀔 때마다 늘어남 (계산 결과를 다시 쓸지 판단)
        self.sroot = settings_root or root  # 설정은 모든 채권이 함께 쓴다
        self.lock = threading.RLock()
        os.makedirs(os.path.join(root, "results"), exist_ok=True)
        os.makedirs(os.path.join(root, "backups"), exist_ok=True)
        self.cases = self._read("cases.json", {})
        self.runs = self._read("runs.json", [])
        self.todos = self._read("todos.json", {})
        self.settings = _merge(DEFAULT_SETTINGS, self._read(os.path.join(self.sroot, "settings.json"), {}))
        self.settings_log = self._read(os.path.join(self.sroot, "settings_log.json"), [])

    # ------------------------------------------------------------ 파일

    def _path(self, name):
        return os.path.join(self.root, name)

    def _read(self, name, default):
        p = self._path(name)
        if not os.path.isfile(p):
            return copy.deepcopy(default)
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # 깨진 파일은 옆에 남겨 두고 빈 값으로 시작
            os.replace(p, p + f".broken-{dt.datetime.now():%Y%m%d%H%M%S}")
            return copy.deepcopy(default)

    def _write(self, name, data):
        p = self._path(name)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, p)

    def save_cases(self):
        self.rev += 1
        with self.lock:
            self._write("cases.json", self.cases)

    def save_runs(self):
        with self.lock:
            self._write("runs.json", self.runs)

    def save_todos(self):
        self.rev += 1
        with self.lock:
            self._write("todos.json", self.todos)

    # ------------------------------------------------------------ 사건

    @staticmethod
    def key_of(court, year, dvs, serial):
        return f"{court}|{format_case_no(year, dvs, serial)}"

    def find_key(self, key):
        for cid, c in self.cases.items():
            if self.key_of(c["court"], c["year"], c["dvs"], c["serial"]) == key:
                return cid
        return None

    def add_case(self, data):
        with self.lock:
            cid = uuid.uuid4().hex[:10]
            c = {"id": cid, "court": "", "court_code": "", "year": 0, "dvs": "", "serial": "", "party": "",
                 "owner": "", "memo1": "", "memo2": "", "extra": {}, "archived": False, "added": now(),
                 "last_checked": "", "last_result": "", "status": "", "color": "", "csNm": "", "last_prog": {},
                 "next_hearing": {}, "cfm_date": "", "ultmt": "", "memos": [], "new_count": 0, "used_party": ""}
            c.update(data)
            c["id"] = cid
            self.cases[cid] = c
            return c

    def case_no(self, c):
        return format_case_no(c["year"], c["dvs"], c["serial"])

    def active_cases(self):
        return [c for c in self.cases.values() if not c.get("archived")]

    # ------------------------------------------------------------ 조회 결과

    def result(self, cid):
        return self._read(os.path.join("results", cid + ".json"), {"checks": [], "prog": [], "basic": {}, "lists": {}})

    def save_result(self, cid, res):
        self.rev += 1
        with self.lock:
            self._write(os.path.join("results", cid + ".json"), res)

    @staticmethod
    def row_key(r):
        return "|".join(str(r.get(k) or "").strip() for k in ("progYmd", "progCtt", "progRslt"))

    def record(self, cid, run_id, got):
        """조회 결과 하나를 저장. 새로 생긴 진행 줄 수를 돌려준다.

        진행내용은 법원이 지금 보여 주는 목록 그대로 둔다(v1.14.2). 예전에는 줄을 계속 쌓아서
        ① 송달 결과가 나중에 채워지면 같은 줄이 두 줄(결과 없음 · 도달)로 남고 ② 법원이 고치거나 지운 줄도 남아
        법원 화면과 달라졌다. 처음 본 때(_seen)와 '새 진행' 표시는 같은 줄끼리 이어 간다.
        진행을 못 받았으면(오류·빈 응답) 예전 줄을 그대로 둔다."""
        res = self.result(cid)
        first = not res["checks"]
        at = now()
        old = {}
        for r in res["prog"]:
            old.setdefault(r.get("_k") or self.row_key(r) + "#1", r)
        rows_in = got.get("prog") or []
        new_keys, gone = [], 0
        if rows_in:
            seen, out = {}, []
            for r in rows_in:
                base = self.row_key(r)
                seen[base] = seen.get(base, 0) + 1  # 같은 날 같은 내용이 여러 줄이어도 모두 남긴다
                k = f"{base}#{seen[base]}"
                row = dict(r)
                row["_k"] = k
                prev = old.get(k)
                if prev:
                    row["_seen"] = prev.get("_seen") or at
                    row["_first"] = bool(prev.get("_first"))
                else:
                    row["_seen"] = at
                    row["_first"] = first  # 처음 조회 때 이미 있던 줄은 '새 진행'으로 치지 않는다
                    if not first:
                        new_keys.append(k)
                out.append(row)
            keep = {r["_k"] for r in out}
            gone = sum(1 for k in old if k not in keep)
            res["prog"] = out
        res["prog"].sort(key=lambda r: (str(r.get("progYmd") or ""), r.get("_seen", "")), reverse=True)
        if got.get("basic"):
            res["basic"] = got["basic"]
            res["lists"] = got.get("lists") or {}  # 기일 목록이 비면 비운다 (지난 기일이 남지 않게)
        res["task"] = got.get("task", res.get("task"))
        res["checks"].append({"at": at, "run": run_id, "new": new_keys, "prog_count": len(rows_in),
                              "prog_error": got.get("prog_error", ""), "gone": gone})
        res["checks"] = res["checks"][-60:]
        self.save_result(cid, res)
        return len(new_keys), res

    def reset_result(self, cid):
        """사건번호·법원을 고쳤을 때: 예전 사건의 조회 결과를 떼어 두고(.old) 처음부터 다시 조회하게 한다."""
        with self.lock:
            p = os.path.join(self.root, "results", cid + ".json")
            if os.path.isfile(p):
                os.replace(p, p[:-5] + f".old-{dt.datetime.now():%Y%m%d%H%M%S}.json")
        self.rev += 1

    # ------------------------------------------------------------ 조회 기록

    def new_run(self, name, case_ids, cond_text=""):
        with self.lock:
            run = {"id": uuid.uuid4().hex[:8], "name": name, "cond": cond_text, "created": now(), "finished": "",
                   "items": [{"cid": c, "state": "wait", "msg": "", "new": 0, "sec": 0} for c in case_ids]}
            self.runs.insert(0, run)
            self.runs = self.runs[:200]
            self.save_runs()
            return run

    def run(self, rid):
        for r in self.runs:
            if r["id"] == rid:
                return r
        return None

    # ------------------------------------------------------------ 설정

    def set_setting(self, path, value, note=""):
        """path: 'run.delay' 처럼 점으로 구분"""
        with self.lock:
            keys = path.split(".")
            cur = self.settings
            for k in keys[:-1]:
                cur = cur.setdefault(k, {})
            old = cur.get(keys[-1])
            if old == value:
                return
            cur[keys[-1]] = value
            self.rev += 1
            self._write(os.path.join(self.sroot, "settings.json"), self.settings)
            if path.startswith("look.") and not note:
                return  # 화면 밝기 같은 것은 기록하지 않음
            self.settings_log.insert(0, {"at": now(), "path": path, "old": old, "new": value, "note": note})
            self.settings_log = self.settings_log[:300]
            self._write(os.path.join(self.sroot, "settings_log.json"), self.settings_log)

    def undo_setting(self, idx):
        with self.lock:
            e = self.settings_log[idx]
            keys = e["path"].split(".")
            cur = self.settings
            for k in keys[:-1]:
                cur = cur.setdefault(k, {})
            cur[keys[-1]] = e["old"]
            self.rev += 1
            self._write(os.path.join(self.sroot, "settings.json"), self.settings)
            self.settings_log.insert(0, {"at": now(), "path": e["path"], "old": e["new"], "new": e["old"],
                                         "note": "되돌리기: " + (e.get("note") or e["path"])})
            self._write(os.path.join(self.sroot, "settings_log.json"), self.settings_log)

    # ------------------------------------------------------------ 백업

    def backup(self, keep=None):
        keep = keep or int(self.settings["save"].get("backups") or 10)
        name = os.path.join(self.root, "backups", f"백업_{dt.datetime.now():%Y%m%d_%H%M%S}.zip")
        with self.lock, zipfile.ZipFile(name, "w", zipfile.ZIP_DEFLATED) as z:
            for base, dirs, files in os.walk(self.root):
                if os.path.basename(base) == "backups" or "backups" in os.path.relpath(base, self.root).split(os.sep):
                    continue
                for f in files:
                    if f.endswith(".tmp"):
                        continue
                    full = os.path.join(base, f)
                    z.write(full, os.path.relpath(full, self.root))
        olds = sorted(f for f in os.listdir(os.path.join(self.root, "backups")) if f.endswith(".zip"))
        for f in olds[:-keep]:
            try:
                os.remove(os.path.join(self.root, "backups", f))
            except OSError:
                pass
        return name

    def backups(self):
        d = os.path.join(self.root, "backups")
        return sorted((f for f in os.listdir(d) if f.endswith(".zip")), reverse=True)

    def restore(self, fname):
        path = os.path.join(self.root, "backups", os.path.basename(fname))
        self.backup()  # 되살리기 전 지금 상태도 남겨 둔다
        with self.lock, zipfile.ZipFile(path) as z:
            for n in z.namelist():
                dst = os.path.normpath(os.path.join(self.root, n))
                if not dst.startswith(os.path.normpath(self.root)):
                    continue
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with z.open(n) as src, open(dst, "wb") as out:
                    out.write(src.read())
        self.__init__(self.root, self.sroot)
