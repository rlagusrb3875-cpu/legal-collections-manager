# -*- coding: utf-8 -*-
"""화면(HTML) ↔ 기능 연결. 화면은 api('이름', {인자}) 로 여기 메서드를 부른다.
기능별 메서드는 bridge_books / bridge_lookup / bridge_settings / bridge_auction / bridge_legal 에 나눠 있다."""
import datetime as dt
import json
import os
import subprocess
import sys
import threading
import time

from appbase import DEFAULT_BOOK, LOCAL, _desktop, _save_pointer
from core import auction as AU
from core import excel, rules
from core.caseno import CourtNames, name_variants, parse_case_no
from core.meta import Meta
from core.site import Court, SiteError
from core.store import SUMMARY_COLS, Store, now
from appbase import APP_NAME, POINTER, _load_pointer, default_data_dir, is_network_path, lock_check, newer_version  # noqa: F401
from bridge_auction import AuctionMixin
from bridge_books import BooksMixin
from bridge_console import ConsoleMixin
from bridge_dividend import DividendMixin
from bridge_links import LinksMixin
from bridge_forms import FormsMixin
from bridge_xl import XlMixin
from bridge_legal import LegalMixin
from bridge_recovery import RecoveryMixin
from bridge_lookup import LookupMixin
from bridge_settings import SettingsMixin

VERSION = "1.15.0"


class Bridge(BooksMixin, LookupMixin, SettingsMixin, AuctionMixin, LegalMixin, FormsMixin, XlMixin, ConsoleMixin, DividendMixin, LinksMixin, RecoveryMixin):
    def __init__(self, data_dir=None):
        self.window = None
        self.mode = "app"
        self.last_poll = time.time()
        self.data_dir = data_dir or _load_pointer().get("data_dir") or default_data_dir()
        os.makedirs(self.data_dir, exist_ok=True)
        self._migrate()
        self.book = self._books_info().get("current") or ""
        if self.book not in self.book_names():
            self.book = (self.book_names() or [DEFAULT_BOOK])[0]
        self.store = self._open_book(self.book)
        self._upgrade_settings()
        self.meta = Meta.load(os.path.join(self.data_dir, "court_meta.json"))
        self.court = Court(self.meta)
        self.lock = threading.Lock()
        self.sess = None  # 지금 하는 조회
        self.awin = None  # 법원경매정보 창
        self.asess = None  # 지금 하는 경매 조회
        self.last_search = 0.0
        self.other_user = lock_check(self.data_dir)
        try:  # v1.10: 시작 프로그램이 예전 이름(사건조회도우미.exe)을 가리키면 새 이름으로
            from core import autostart
            autostart.migrate()
        except Exception:
            pass

    # ------------------------------------------------------------ 판이 바뀔 때 설정 맞추기 (차례대로 한 번씩)

    SETTINGS_SCHEMA = [
        (1, "v1.2.1: 경매 「검색」 자동 누르기 켬", lambda st: st.set_setting("auction.auto_search", True, "v1.2.1: 경매 「검색」 자동 누르기 켬")),
        (2, "v1.11: 첫 화면을 현황 콘솔로", lambda st: st.set_setting("todo.start", "console", "v1.11: 첫 화면을 현황 콘솔로")
         if (st.settings.get("todo") or {}).get("start", "home") == "home" else None),
    ]

    def _upgrade_settings(self):
        st = self.store
        cur = int(st.settings.get("_schema") or (1 if st.settings.get("_v121") else 0))
        for ver, _, fn in self.SETTINGS_SCHEMA:
            if ver > cur:
                fn(st)
                cur = ver
        if st.settings.get("_schema") != cur:
            st.set_setting("_schema", cur, "")

    # ------------------------------------------------------------ 공통

    def info(self, mode=None):
        if mode:
            self.mode = mode
        self.last_poll = time.time()
        s = self.store
        if time.time() - getattr(self, "_lock_t", 0) > 60:  # 1분마다 「이 PC가 쓰는 중」 표시를 새로
            self._lock_t = time.time()
            self.other_user = lock_check(self.data_dir)
        upd = newer_version(s.settings["save"].get("update_folder", ""), VERSION)
        return {"app": APP_NAME, "version": VERSION, "mode": self.mode, "data_dir": self.data_dir,
                "other_user": self.other_user, "network_dir": is_network_path(self.data_dir),
                "update": {"version": upd[0], "path": upd[1]} if upd else None,
                "book": self.book, "books": self.books(),
                "auction_count": sum(1 for a in self.auct.items.values() if not a.get("archived")),
                "legal": self._legal_counts(), "dividend": self._dv_counts(),
                "demo": bool(getattr(self, "demo", False)), "export_dir": self.export_dir(), "settings": s.settings, "counts": self._counts(),
                "running": self._sess_brief(), "summary_cols": SUMMARY_COLS, "today": dt.date.today().isoformat(),
                "courts": self.meta.court_names(), "owners": sorted({c.get("owner") for c in s.active_cases() if c.get("owner")})}

    def _legal_counts(self):
        rh = [r for r in self.legal.data["rehab"].values() if not r.get("closed")]
        from core import legal as _L
        return {"debtors": len(self.legal.active_debtors()), "dlv": sum(1 for x in self.legal.data["dlv"].values() if not x.get("done")),
                "stop": sum(1 for r in rh if not r.get("stop_ok") and r.get("code") in _L.BLOCKING),
                "rehab": sum(1 for r in rh if r.get("code") in ("stop", "ban", "warn"))}

    def ping(self):
        self.last_poll = time.time()
        return True

    def export_dir(self):
        return self.store.settings["save"].get("export_dir") or os.path.join(_desktop(), "사건조회 결과")

    def _todos(self, show_done=False):
        """소송(나의사건검색) + 경매 할 일을 한 목록으로"""
        key = (self.auct.rev, self.store.rev, dt.datetime.now().strftime("%Y%m%d%H"))
        if getattr(self, "_atodo", (None,))[0] != key:
            self._atodo = (key, AU.todos(self.auct, self.store.settings, self.store.todos))
        import copy
        items = rules.todos(self.store, show_done=True) + copy.deepcopy(self._atodo[1]) + self._legal_todos() + self._dv_todos()
        items = rules.finish(items, self.store.settings["todo"], show_done)
        return items

    def _counts(self):
        cases = self.store.active_cases()
        todo = [t for t in self._todos() if not t["done"]]
        return {"cases": len(cases), "todo": len(todo), "todo_hot": sum(1 for t in todo if t["group"] == "급한 것"),
                "status": rules.label_status_counts(cases)}

    def open_path(self, path):
        if not path:
            return False
        if sys.platform == "win32":
            os.startfile(path)  # noqa
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True

    def reveal(self, path):
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            self.open_path(os.path.dirname(path))
        return True

    def choose_file(self, kind="excel"):
        if not self.window:
            return None
        import webview
        types = {"pdf": ("PDF 파일 (*.pdf)", "모든 파일 (*.*)"), "image": ("그림 파일 (*.png;*.jpg;*.jpeg;*.bmp)", "모든 파일 (*.*)"),
                 "form": ("양식 파일 (*.zip)", "모든 파일 (*.*)")}.get(kind, ("엑셀 파일 (*.xlsx;*.xls;*.xlsm;*.csv)", "모든 파일 (*.*)"))
        r = self.window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=types)
        return r[0] if r else None

    def choose_folder(self):
        if not self.window:
            return None
        import webview
        r = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        return r[0] if r else None

    # ------------------------------------------------------------ 확인할 것

    def home(self, show_done=False):
        items = self._todos(show_done)
        cases = self.store.cases
        for it in items:
            if it.get("auction") or it.get("legal"):
                continue
            c = cases.get(it["cid"], {})
            it["case_no"] = self.store.case_no(c) if c else ""
            it["party"] = c.get("party", "")
            it["court"] = c.get("court", "")
            it["memo1"] = c.get("memo1", "")
            it["owner"] = c.get("owner", "")
        today = dt.date.today().isoformat()
        hear = []
        for c in self.store.active_cases():
            h = c.get("next_hearing") or {}
            if h.get("date") and h["date"] >= today:
                hear.append(dict(h, cid=c["id"], case_no=self.store.case_no(c), party=c.get("party", ""), court=c["court"]))
        hear.sort(key=lambda h: (h["date"], h.get("time", "")))
        last = next((r for r in self.store.runs if r.get("finished")), None)
        cycle = int(self.store.settings["run"].get("cycle_days") or 14)
        nxt = ""
        if last:
            nxt = (dt.date.fromisoformat(last["finished"][:10]) + dt.timedelta(days=cycle)).isoformat()
        for a in self.auct.items.values():  # 경매 매각기일도 다가오는 기일에
            s = a.get("next_sale") or {}
            if not a.get("archived") and s.get("date") and s["date"] >= today:
                hear.append({"date": s["date"], "time": s.get("time", ""), "kind": s.get("kind") or "매각기일", "place": s.get("place", ""),
                             "aid": a["id"], "case_no": a["case_no"], "party": a.get("debtor", ""), "court": a["court"]})
        hear.sort(key=lambda h: (h["date"], h.get("time", "")))
        exp = self.export_dir()
        old = 0
        if os.path.isdir(exp):
            lim = time.time() - 90 * 86400
            old = sum(1 for f in os.listdir(exp) if f.endswith(".xlsx") and os.path.getmtime(os.path.join(exp, f)) < lim)
        return {"items": items, "hearings": hear[:8], "last_run": last["finished"] if last else "", "next_run": nxt,
                "cycle": cycle, "counts": self._counts(), "old_exports": old, "export_dir": exp,
                "first_use": not self.store.active_cases() and not any(not a.get("archived") for a in self.auct.items.values())}

    def todo_done(self, key, note=""):
        st = self.store.todos.setdefault(key, {})
        st.update({"done": now(), "note": note, "by": self.store.settings.get("me") or os.environ.get("USERNAME", "")})
        cid = key.split("|", 1)[0]
        if note and key.startswith("A|"):  # 경매 할 일 메모는 경매 사건 메모에
            aid = key.split("|")[1]
            if aid in self.auct.items:
                self.auct.items[aid].setdefault("memos", []).insert(0, {"at": now(), "by": st["by"], "text": note, "from": "확인할 것"})
                self.auct.save()
        if note and cid in self.store.cases:
            self.store.cases[cid].setdefault("memos", []).insert(0, {"at": now(), "by": st["by"], "text": note, "from": "확인할 것"})
            self.store.save_cases()
        self.store.save_todos()
        self._act(f"확인할 것 처리함{' — ' + note if note else ''}", "todo", "home")
        return True

    def todo_undo(self, key):
        st = self.store.todos.get(key)
        if st:
            st.pop("done", None)
            self.store.save_todos()
        return True

    def deadline_set(self, key, date, note=""):
        if key == "new":
            key = f"manual|{now()}"
        st = self.store.todos.setdefault(key, {})
        st["deadline"] = date
        if note:
            st["note"] = note
        self.store.save_todos()
        return True

    def manual_deadline(self, cid, date, note):
        key = f"manual|{now()}"
        self.store.todos[key] = {"deadline": date, "note": note, "cid": cid}
        self.store.save_todos()
        return True

    # ------------------------------------------------------------ 기일·기한

    def calendar(self, year, month):
        ev = rules.calendar(self.store, int(year), int(month))
        for e in ev:
            c = self.store.cases.get(e.get("cid") or "", {})
            e["case_no"] = self.store.case_no(c) if c else ""
            e["party"] = c.get("party", "")
        first, last = f"{int(year)}-{int(month):02d}-01", f"{int(year)}-{int(month):02d}-31"
        # 보정 관리 기한 (같은 건이 확인할 것 기한으로도 잡히면 보정 쪽 하나만)
        dl = self.legal.data["dlv"]
        drop = set(dl) | set(self.legal.data.get("dlv_removed") or [])
        ev = [e for e in ev if e.get("key") not in drop]
        std = self._std()
        for x in dl.values():
            due = None if x.get("done") else self._dlv_due(x, std)
            if due and first <= due["due"] <= last:
                left = (dt.date.fromisoformat(due["due"]) - dt.date.today()).days
                ev.append({"date": due["due"], "cid": x.get("cid", ""), "key": x["key"], "dlv": True, "type": "기한", "case_no": x["case_no"],
                           "party": x.get("party", ""), "left": left,
                           "text": f"보정 기한 · {x.get('reason') or '송달불능'} · {x.get('act') or '조치 정하기'}"})
        # 경매 매각기일
        for a in self.auct.items.values():
            s = a.get("next_sale") or {}
            if not a.get("archived") and s.get("date") and first <= s["date"] <= last:
                ev.append({"date": s["date"], "cid": "", "aid": a["id"], "type": "매각", "case_no": a["case_no"],
                           "party": a.get("debtor", ""), "text": " ".join(x for x in (s.get("kind"), s.get("time"), s.get("price")) if x)})
        ev.sort(key=lambda e: e["date"])
        return ev

    # ------------------------------------------------------------ 사건 대장

    def ledger(self, archived=False):
        out = []
        for c in self.store.cases.values():
            if bool(c.get("archived")) != bool(archived):
                continue
            out.append(dict(c, case_no=self.store.case_no(c), memos=len(c.get("memos") or [])))
        out.sort(key=lambda c: (c.get("court", ""), c["case_no"]))
        return out

    def case_detail(self, cid):
        c = self.store.cases[cid]
        res = self.store.result(cid)
        basic = [{"key": k, "label": self.meta.label(k), "value": excel._fmt_value(k, v)}
                 for k, v in (res.get("basic") or {}).items()
                 if v not in (None, "") and not isinstance(v, (list, dict)) and not k.startswith("enc")
                 and not k.endswith("Cd") and not k.endswith("Yn") and k not in ("userCsNo",)]
        lists = []
        from core.site import LIST_NAMES
        for k, rows in (res.get("lists") or {}).items():
            if not rows:
                continue
            cols = [col for col in rows[0].keys() if not col.endswith("Cd") and not col.startswith("enc") and not col.endswith("Yn")]
            cols = [col for col in cols if any(str(r.get(col) or "").strip() for r in rows)]
            lists.append({"name": LIST_NAMES.get(k, self.meta.label(k)), "cols": [self.meta.label(x) for x in cols],
                          "rows": [[excel._fmt_value(x, r.get(x, "")) for x in cols] for r in rows]})
        checks = res.get("checks") or []
        rounds = []
        rows = res.get("prog") or []
        for chk in reversed(checks):
            got = [r for r in rows if r.get("_seen", "")[:19] == chk["at"][:19]]
            rounds.append({"at": chk["at"], "first": bool(got and got[0].get("_first")), "count": len(got),
                           "rows": [{"date": str(rules.ymd(r.get("progYmd")) or ""), "text": rules.row_text(r),
                                     "new": not r.get("_first")} for r in got], "error": chk.get("prog_error", "")})
        return {"case": dict(c, case_no=self.store.case_no(c)), "basic": basic, "lists": lists, "rounds": rounds,
                "hearings": rules.hearings(res.get("lists")), "checked": bool(checks)}

    def case_save(self, data):
        p = parse_case_no(data.get("case_no", ""))
        if not p:
            raise ValueError("사건번호를 읽지 못했어요 (예: 2025가소123456)")
        names = CourtNames(self.meta.court_names(), self.store.settings.get("aliases"))
        court, _, cands = names.match(data.get("court", ""))
        if not court:
            raise ValueError("법원 이름을 알 수 없어요" + (f" (혹시: {', '.join(cands[:3])})" if cands else ""))
        if len((data.get("party") or "").replace(" ", "")) < 2:
            raise ValueError("당사자 이름은 2글자 이상이어야 조회돼요")
        fields = {"court": court, "court_code": self.meta.court(court)["code"], "year": p[0], "dvs": p[1], "serial": p[2],
                  "party": data.get("party", "").strip(), "owner": data.get("owner", "").strip(),
                  "memo1": data.get("memo1", "").strip(), "memo2": data.get("memo2", "").strip()}
        if data.get("id") and data["id"] in self.store.cases:
            cid = data["id"]
            c = self.store.cases[cid]
            ident = lambda x: (x.get("court"), int(x.get("year") or 0), x.get("dvs"), str(x.get("serial")))  # noqa: E731
            if ident(c) != ident(fields):
                other = self.store.find_key(self.store.key_of(court, *p))
                if other and other != cid:
                    raise ValueError("이미 사건 대장에 있는 사건이에요")
                # 다른 사건으로 바뀜 → 예전 사건의 진행·상태가 새 사건에 섞이지 않게 비우고 처음부터 다시 조회
                self.store.reset_result(cid)
                c.update({"status": "", "color": "", "csNm": "", "last_prog": {}, "next_hearing": {}, "cfm_date": "",
                          "ultmt": "", "new_count": 0, "last_checked": "", "last_result": "", "used_party": "", "rule": ""})
            c.update(fields)
        else:
            key = self.store.key_of(court, *p)
            if self.store.find_key(key):
                raise ValueError("이미 사건 대장에 있는 사건이에요")
            cid = self.store.add_case(fields)["id"]
        self.store.save_cases()
        return cid

    def case_archive(self, ids, archived=True):
        for i in ids:
            if i in self.store.cases:
                self.store.cases[i]["archived"] = bool(archived)
        self.store.save_cases()
        return len(ids)

    def memo_add(self, cid, text):
        c = self.store.cases[cid]
        c.setdefault("memos", []).insert(0, {"at": now(), "by": self.store.settings.get("me") or os.environ.get("USERNAME", ""), "text": text})
        self.store.save_cases()
        return True

    def emit(self, ev):
        if self.window:
            try:
                self.window.evaluate_js(f"window.onAppEvent && window.onAppEvent({json.dumps(ev, ensure_ascii=False)})")
            except Exception:
                pass
