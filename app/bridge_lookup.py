# -*- coding: utf-8 -*-
"""나의사건검색: 엑셀 넣기 · 조회할 사건 고르기 · 직접 입력 · 조회 진행 · 결과"""
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


class LookupMixin:
    # ------------------------------------------------------------ 엑셀로 추가·갱신

    def import_preview(self, path, mapping=None):
        if mapping:
            mapping = {k: int(v) for k, v in mapping.items() if v not in (None, "", -1, "-1")}
        p = excel.preview(path, self.meta, self.store, mapping, lambda h: self._xl_pref("case", h))
        p["path"] = path
        p["name"] = os.path.basename(path)
        p["gone_cases"] = [{"id": i, "case_no": self.store.case_no(self.store.cases[i]), "party": self.store.cases[i].get("party", "")}
                           for i in p["gone"][:50]]
        p["good_count"] = len(p.pop("good"))
        return p

    def import_apply(self, path, mapping=None, gone_action="archive", temp=False):
        if mapping:
            mapping = {k: int(v) for k, v in mapping.items() if v not in (None, "", -1, "-1")}
        p = excel.preview(path, self.meta, self.store, mapping, lambda h: self._xl_pref("case", h))
        self._xl_save("case", p["header"], p["mapping"])
        added = updated = 0
        ids = []
        for g in p["good"]:
            cid = self.store.find_key(self.store.key_of(g["court"], g["year"], g["dvs"], g["serial"]))
            if cid:
                c = self.store.cases[cid]
                for k in ("party", "owner", "memo1", "memo2", "extra", "court_code"):
                    if g.get(k):
                        c[k] = g[k]
                if c.get("archived") and temp:
                    c["temp"] = True
                c["archived"] = False
                updated += 1
            else:
                cid = self.store.add_case(dict(g, temp=True) if temp else g)["id"]
                added += 1
            if cid not in ids:
                ids.append(cid)
        self._last_import_ids = ids
        archived = 0
        if gone_action == "archive":
            for i in p["gone"]:
                self.store.cases[i]["archived"] = True
                archived += 1
        self.store.save_cases()
        self._act(f"사건 대장에 엑셀을 넣었어요 — 새로 {added} · 갱신 {updated}" + (f" · 보관함으로 {archived}" if archived else ""), "xl", "ledger")
        return {"added": added, "updated": updated, "archived": archived, "skipped": len(p["skips"])}

    def bulk_search(self, path, mapping=None, keep=True):
        """엑셀을 넣어 대량 조회: 읽은 사건을 대장에 넣고(또는 잠시만) 바로 조회 시작."""
        r = self.import_apply(path, mapping, gone_action="keep", temp=not keep)
        ids = self._last_import_ids
        if not ids:
            raise ValueError("조회할 수 있는 줄이 없어요. 칸을 맞게 골랐는지 확인해 주세요")
        st = self.run_start(name=f"엑셀 대량 조회 · {os.path.splitext(os.path.basename(path))[0]}", case_ids=ids)
        st["imported"] = r
        return st

    def template_save(self):
        path = excel.template(self.export_dir())
        self.reveal(path)
        return path

    # ------------------------------------------------------------ 조회할 사건 고르기

    def pick_preview(self, cond=None):
        cases, removed = rules.pick(self.store, cond or {})
        sec = 4.5 + float(self.store.settings["run"].get("delay") or 0)
        return {"total": len(self.store.active_cases()), "count": len(cases), "removed": removed,
                "eta_min": max(1, round(len(cases) * sec / 60)), "saved_min": round(sum(removed.values()) * sec / 60),
                "first": [{"case_no": self.store.case_no(c), "party": c.get("party", "")} for c in cases[:5]]}

    # ------------------------------------------------------------ 직접 입력해서 조회 (수기 검색)

    def quick_parse(self, text):
        """한 줄에 '법원 · 사건번호 · 당사자'. 엑셀에서 붙여넣은 칸(탭)·쉼표·띄어쓰기 모두 읽는다."""
        import re
        names = CourtNames(self.meta.court_names(), self.store.settings.get("aliases"))
        good, bad = [], []
        for n, line in enumerate(str(text or "").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            parts = [x.strip() for x in re.split(r"\t|,|，|\|", line) if x.strip()]
            if len(parts) < 3:
                parts = self._split_spaces(line, names) or parts
            if len(parts) < 3:
                bad.append({"line": n, "text": line, "problem": "법원 · 사건번호 · 당사자 이름 세 가지가 필요해요"})
                continue
            # 칸 순서가 달라도 사건번호처럼 생긴 칸을 찾는다
            ci = next((i for i, x in enumerate(parts) if parse_case_no(x)), None)
            if ci is None:
                bad.append({"line": n, "text": line, "problem": "사건번호를 읽지 못했어요 (예: 2025가소123456)"})
                continue
            p = parse_case_no(parts[ci])
            rest = [x for i, x in enumerate(parts) if i != ci]
            court, cands = None, []
            for i, x in enumerate(rest):
                court, _, cands = names.match(x)
                if court:
                    rest.pop(i)
                    break
            if not court:
                bad.append({"line": n, "text": line, "problem": "법원 이름을 알 수 없어요" + (f" (혹시: {', '.join(cands[:3])})" if cands else "")})
                continue
            party = rest[0] if rest else ""
            if len(party.replace(" ", "")) < 2:
                bad.append({"line": n, "text": line, "problem": "당사자 이름은 2글자 이상이어야 조회돼요"})
                continue
            if p[1] not in self.meta.all_dvs_names():
                bad.append({"line": n, "text": line, "problem": f"「{p[1]}」은 나의사건검색에 없는 사건구분이에요"})
                continue
            good.append({"court": court, "court_code": self.meta.court(court)["code"], "year": p[0], "dvs": p[1],
                         "serial": p[2], "party": party, "memo1": rest[1] if len(rest) > 1 else ""})
        return good, bad

    @staticmethod
    def _split_spaces(line, names):
        """띄어쓰기로만 나눈 줄: 사건번호를 어디서든 찾고, 남은 말의 앞쪽이나 뒤쪽에서 법원 이름을 찾는다."""
        import re
        m = re.search(r"(?<!\d)((?:\d{4}|\d{2})\s*[가-힣]{1,5}\s*\d[\d,]*)", line)
        if not m:
            return None
        case = m.group(1)
        toks = (line[:m.start()] + " " + line[m.end():]).split()
        for k in range(len(toks), 0, -1):
            for court_toks, rest in ((toks[:k], toks[k:]), (toks[-k:], toks[:-k])):
                if rest and names.match(" ".join(court_toks))[0]:
                    return [" ".join(court_toks), case, " ".join(rest)]
        return None

    def quick_check(self, text):
        good, bad = self.quick_parse(text)
        return {"good": [dict(g, case_no=f"{g['year']}{g['dvs']}{g['serial']}") for g in good], "bad": bad}

    def quick_search(self, text, keep=True):
        good, bad = self.quick_parse(text)
        if not good:
            raise ValueError(bad[0]["problem"] if bad else "조회할 사건을 넣어 주세요")
        ids = []
        for g in good:
            cid = self.store.find_key(self.store.key_of(g["court"], g["year"], g["dvs"], g["serial"]))
            if cid:
                c = self.store.cases[cid]
                c["party"] = g["party"]
                if c.get("archived") and keep:
                    c["archived"] = False
            else:
                c = self.store.add_case(dict(g, owner=self.store.settings.get("me", ""), temp=not keep))
                cid = c["id"]
            ids.append(cid)
        self.store.save_cases()
        st = self.run_start(name="직접 입력 조회", case_ids=ids)
        st["skipped"] = bad
        return st

    # ------------------------------------------------------------ 조회 진행

    def _sess_brief(self):
        s = self.sess
        if not s:
            return None
        run = self.store.run(s["rid"])
        if not run:
            return None
        items = run["items"]
        done = sum(1 for i in items if i["state"] != "wait")
        return {"rid": s["rid"], "name": run["name"], "done": done, "total": len(items)}

    def run_start(self, name="정기 조회", cond=None, case_ids=None):
        if case_ids:
            ids = [i for i in case_ids if i in self.store.cases]
        else:
            ids = [c["id"] for c in rules.pick(self.store, cond or {})[0]]
        if not ids:
            raise ValueError("조회할 사건이 없어요")
        desc = ", ".join(k for k, v in (cond or {}).items() if v is True)
        run = self.store.new_run(name, ids, desc)
        self.sess = {"rid": run["id"], "idx": 0, "cap": None, "variant": 0,
                     "party": None, "wrong": 0, "started": time.time(), "paused": False, "new_total": 0, "confirmed": []}
        return self.run_state(fetch=True)

    def run_resume(self, rid):
        run = self.store.run(rid)
        if not run:
            raise ValueError("조회 기록을 찾지 못했어요")
        self.sess = {"rid": rid, "idx": 0, "cap": None, "variant": 0, "party": None, "wrong": 0,
                     "started": time.time(), "paused": False, "new_total": 0, "confirmed": []}
        return self.run_state(fetch=True)

    def _current(self):
        run = self.store.run(self.sess["rid"])
        for n, it in enumerate(run["items"]):
            if it["state"] == "wait":
                return run, n, it
        return run, None, None

    def run_state(self, fetch=False, message=None, last=None):
        if not self.sess:
            return {"active": False}
        run, n, it = self._current()
        items = run["items"]
        stat = {"done": sum(1 for i in items if i["state"] == "done"), "notfound": sum(1 for i in items if i["state"] == "notfound"),
                "error": sum(1 for i in items if i["state"] in ("error", "skip")), "total": len(items),
                "new": sum(i.get("new", 0) for i in items if i["state"] == "done"), "wrong": self.sess["wrong"]}
        took = [i["sec"] for i in items if i.get("sec")]
        stat["avg"] = round(sum(took) / len(took), 1) if took else None
        left = len(items) - sum(1 for i in items if i["state"] != "wait")
        stat["left"] = left
        stat["eta_min"] = round(left * ((stat["avg"] or 4.5) + float(self.store.settings["run"].get("delay") or 0)) / 60, 1)
        queue = []
        for j, x in enumerate(items):
            if x["state"] == "wait" or (n is not None and n - 2 <= j < n):
                c = self.store.cases.get(x["cid"], {})
                queue.append({"no": j + 1, "cid": x["cid"], "case_no": self.store.case_no(c) if c else "", "court": c.get("court", ""),
                              "party": c.get("party", ""), "state": x["state"], "cur": j == n})
            if len(queue) >= 8:
                break
        done_list = []
        for x in reversed(items):
            if x["state"] == "wait":
                continue
            c = self.store.cases.get(x["cid"])
            if not c:
                continue
            done_list.append({"cid": c["id"], "case_no": self.store.case_no(c), "court": c.get("court", ""),
                              "party": c.get("party", ""), "state": x["state"], "status": c.get("status", ""),
                              "color": c.get("color", ""), "last_prog": c.get("last_prog") or {}, "new": x.get("new", 0),
                              "msg": x.get("msg", ""), "memo1": c.get("memo1", "")})
        out = {"active": True, "rid": run["id"], "name": run["name"], "stat": stat, "queue": queue, "message": message,
               "last": last, "finished": n is None, "done_list": done_list}
        if n is None:
            self._finish(run)
            out["finished_at"] = run["finished"]
            return out
        c = self.store.cases[it["cid"]]
        party = self.sess["party"] or c.get("party", "")
        out["case"] = {"no": n + 1, "cid": c["id"], "case_no": self.store.case_no(c), "court": c["court"], "party": party,
                       "memo1": c.get("memo1", ""), "variant": self.sess["variant"], "orig_party": c.get("party", "")}
        if fetch or not self.sess["cap"]:
            try:
                self.sess["cap"] = self.court.captcha()
            except SiteError as ex:
                out["error"] = {"kind": ex.kind, "text": str(ex)}
                return out
        out["captcha"] = {"image": self.sess["cap"]["image"], "mime": self.sess["cap"].get("mime", "image/png")}
        return out

    def result_card(self, cid):
        """조회 화면에 바로 보여줄 결과 한 장: 마지막 진행, 최근 진행, 주요 일반내용."""
        c = self.store.cases[cid]
        res = self.store.result(cid)
        b = res.get("basic") or {}
        last_at = (res.get("checks") or [{}])[-1].get("at", "")[:19]
        prog = [{"date": str(rules.ymd(r.get("progYmd")) or ""), "text": rules.row_text(r),
                 "new": (not r.get("_first")) and r.get("_seen", "")[:19] == last_at} for r in (res.get("prog") or [])[:12]]

        def d(k):
            v = rules.ymd(b.get(k))
            return v.isoformat() if v else ""
        keys = [("사건명", b.get("csNm", "")), ("재판부", b.get("jdbnNm", "")), ("접수일", d("csRcptYmd")),
                ("원고", b.get("rprsClmntNm", "")), ("피고", b.get("rprsAcsdNm", "")),
                ("종국결과", " ".join(x for x in (d("csUltmtYmd"), b.get("csUltmtDvsNm", "")) if x)),
                ("확정일", d("csCfmtnYmd")), ("판결송달일", d("lastAdjdocRchYmd"))]
        nh = c.get("next_hearing") or {}
        return {"cid": cid, "case_no": self.store.case_no(c), "court": c.get("court", ""), "party": c.get("party", ""),
                "status": c.get("status", ""), "color": c.get("color", ""), "last_prog": c.get("last_prog") or {},
                "new": c.get("new_count", 0), "prog": prog, "prog_total": len(res.get("prog") or []),
                "basic": [{"label": k, "value": v} for k, v in keys if v], "memo1": c.get("memo1", ""),
                "next_hearing": " ".join(x for x in (nh.get("date"), nh.get("time"), nh.get("kind"), nh.get("place")) if x),
                "checked": c.get("last_checked", ""), "cfm": bool(c.get("cfm_date")), "rehab": c.get("rehab")}

    def run_audio(self):
        cap = self.sess and self.sess.get("cap")
        return cap.get("audio", "") if cap else ""

    def run_new_captcha(self):
        return self.run_state(fetch=True)

    def run_submit(self, answer, cid=None):
        if not self.sess or not self.sess.get("cap"):
            return self.run_state(fetch=True)
        with self.lock:
            if not self.sess.get("cap"):  # 바로 앞 제출이 그림을 이미 썼음 (두 번 눌림)
                return self.run_state(fetch=True)
            run, n, it = self._current()
            if n is None:
                return self.run_state()
            if cid and it["cid"] != cid:  # 화면에 보이던 사건과 지금 조회할 사건이 다름 (목록을 바꾼 직후 등) → 조회하지 않고 다시 보여 줌
                return self.run_state(fetch=False, message={"kind": "retry", "text": "조회 목록이 바뀌어 지금 차례 사건을 다시 보여 드려요. 숫자를 다시 넣어 주세요."})
            c = self.store.cases[it["cid"]]
            wait = float(self.store.settings["run"].get("delay") or 0) - (time.time() - self.last_search)
            if wait > 0:
                time.sleep(min(wait, 10))
            t0 = time.time()
            token = self.sess["cap"]["token"]
            self.sess["cap"] = None
            party = self.sess["party"] or c.get("party", "")
            self.last_search = time.time()
            try:
                got = self.court.search(c, answer, token, party=party)
            except SiteError as ex:
                if ex.kind == "captcha":
                    self.sess["wrong"] += 1
                    return self.run_state(fetch=True, message={"kind": "captcha", "text": "숫자가 맞지 않아 새 그림을 가져왔어요"})
                if ex.kind == "notfound":
                    variants = name_variants(c.get("party", ""), self.store.settings["run"].get("name_patterns")) \
                        if self.store.settings["run"].get("retry_names") else []
                    if self.sess["variant"] < len(variants):
                        self.sess["party"] = variants[self.sess["variant"]]
                        self.sess["variant"] += 1
                        return self.run_state(fetch=True, message={"kind": "retry", "text": f"찾지 못해서 이름을 「{self.sess['party']}」로 바꿔 다시 조회해요"})
                    it.update(state="notfound", msg=str(ex), sec=round(time.time() - t0, 1))
                    c["last_result"] = "notfound"
                    c["last_checked"] = now()
                    self._next_case(run)
                    return self.run_state(fetch=True, last={"kind": "notfound", "case_no": self.store.case_no(c),
                                                            "party": c.get("party", ""), "text": str(ex)})
                if ex.kind == "input":
                    it.update(state="skip", msg=str(ex))
                    c["last_result"] = "error"
                    self._next_case(run)
                    return self.run_state(fetch=True, last={"kind": "skip", "case_no": self.store.case_no(c), "text": str(ex)})
                # 접속 문제: 이 사건은 그대로 두고 멈춤
                self.sess["paused"] = True
                return self.run_state(fetch=False, message={"kind": ex.kind, "text": str(ex)})
            new, res = self.store.record(c["id"], run["id"], got)
            if self.sess["party"] and self.sess["party"] != c.get("party"):
                c["used_party"] = self.sess["party"]
            was_cfm = bool(c.get("cfm_date"))
            c["last_checked"] = now()
            c["last_result"] = "ok"
            c["new_count"] = new
            rules.refresh_case(self.store, c, res)
            if c.get("cfm_date") and not was_cfm:
                self.sess["confirmed"].append(c["id"])
            it.update(state="done", new=new, sec=round(time.time() - t0, 1), msg=got.get("prog_error", ""))
            self._next_case(run)
            last = {"kind": "ok", "case_no": self.store.case_no(c), "party": c.get("party", ""),
                    "prog": len(got.get("prog") or []), "new": new, "sec": it["sec"], "status": c.get("status"),
                    "color": c.get("color"), "prog_error": got.get("prog_error", ""), "card": self.result_card(c["id"])}
            return self.run_state(fetch=True, last=last)

    def _next_case(self, run):
        self.sess["variant"] = 0
        self.sess["party"] = None
        self.store.save_cases()
        self.store.save_runs()

    def run_skip(self):
        run, n, it = self._current()
        if n is not None:
            it.update(state="skip", msg="건너뜀")
            self._next_case(run)
        return self.run_state(fetch=True, last={"kind": "skip", "text": "건너뛰었어요"})

    def run_remove(self, cids=None, scope=""):
        """이번 조회 목록에서 빼기. cids: 고른 사건, scope='done': 조회한 것 모두.
        사건 대장과 저장된 조회 결과는 그대로 둔다 (이번 조회 목록·엑셀에서만 빠짐)."""
        if not self.sess:
            raise ValueError("지금 하는 조회가 없어요")
        run = self.store.run(self.sess["rid"])
        _, _, cur = self._current()
        drop = set(cids or [])
        keep, removed = [], 0
        for it in run["items"]:
            if it["cid"] in drop or (scope == "done" and it["state"] != "wait"):
                removed += 1
                c = self.store.cases.get(it["cid"])
                if c and c.pop("temp", False):  # 「사건 대장에 남기기」를 끄고 넣은 사건은 보관함으로
                    c["archived"] = True
            else:
                keep.append(it)
        run["items"] = keep
        if cur is not None and cur["cid"] in drop:
            self.sess["variant"], self.sess["party"] = 0, None
        if not keep:  # 다 뺐으면 이 조회 기록은 지운다
            self.store.runs.remove(run)
            self.sess = None
        self.store.save_runs()
        self.store.save_cases()
        if not self.sess:
            return {"active": False, "removed": removed}
        return dict(self.run_state(), removed=removed)

    def run_stop(self):
        if self.sess:
            run = self.store.run(self.sess["rid"])
            for it in (run or {}).get("items", []):
                c = self.store.cases.get(it["cid"])
                if c and c.pop("temp", False):
                    c["archived"] = True
            self.store.save_runs()
            self.store.save_cases()
        self.sess = None
        return True

    def _finish(self, run):
        if run.get("finished"):
            return
        run["finished"] = now()
        run["elapsed"] = round(time.time() - self.sess["started"])
        done = sum(1 for it in run["items"] if it.get("state") == "done")
        new = sum(1 for it in run["items"] if it.get("new"))
        self._act(f"「{run.get('name', '조회')}」 {done}/{len(run['items'])}건 조회를 마쳤어요" + (f" · 새 진행 {new}건" if new else ""), "run", "hist")
        # 「사건 대장에 남기기」를 끄고 직접 조회한 사건은 끝나면 보관함으로 (결과는 남아 있음)
        for it in run["items"]:
            c = self.store.cases.get(it["cid"])
            if c and c.pop("temp", False):
                c["archived"] = True
        self.store.save_runs()
        self.store.save_cases()
        try:
            self.store.backup()
        except Exception:
            pass
        if self.store.settings["sihyo"].get("auto") and self.store.settings["sihyo"].get("folder") and self.sess["confirmed"]:
            try:
                excel.export_sihyo(self.store, self.sess["confirmed"], self.store.settings["sihyo"]["folder"])
            except Exception:
                pass

    # ------------------------------------------------------------ 결과 · 기록

    def runs(self):
        out = []
        for r in self.store.runs:
            items = r["items"]
            out.append({"id": r["id"], "name": r["name"], "created": r["created"], "finished": r.get("finished", ""),
                        "total": len(items), "done": sum(1 for i in items if i["state"] != "wait"),
                        "changed": sum(1 for i in items if i.get("new")), "notfound": sum(1 for i in items if i["state"] == "notfound"),
                        "elapsed": r.get("elapsed", 0)})
        return out

    def run_result(self, rid):
        run = self.store.run(rid)
        if not run:
            raise ValueError("조회 기록을 찾지 못했어요")
        rows = []
        for it in run["items"]:
            c = self.store.cases.get(it["cid"])
            if not c:
                continue
            rows.append(dict(c, case_no=self.store.case_no(c), state=it["state"], new=it.get("new", 0), msg=it.get("msg", "")))
        return {"run": {k: run[k] for k in ("id", "name", "created") if k in run} | {"finished": run.get("finished", "")},
                "rows": rows}

    def export_run(self, rid):
        run = self.store.run(rid)
        ids = [i["cid"] for i in run["items"] if i["state"] in ("done", "notfound")]
        changed = {i["cid"] for i in run["items"] if i.get("new")}
        name = self.store.settings["excel"]["name"].replace("{채권}", self.book).replace("{조건}", run["name"]).replace(
            "{날짜}", dt.date.today().strftime("%y%m%d")).replace("{날짜:YYMMDD}", dt.date.today().strftime("%y%m%d"))
        path = excel.export_results(self.store, self.meta, ids, self.export_dir(), name, changed)
        self.reveal(path)
        return path

    def export_cases(self, ids):
        path = excel.export_results(self.store, self.meta, ids, self.export_dir(), f"{self.book} 사건대장_{dt.date.today():%y%m%d}")
        self.reveal(path)
        return path

    def sihyo_send(self, ids):
        folder = self.store.settings["sihyo"].get("folder") or self.export_dir()
        path, n = excel.export_sihyo(self.store, ids, folder)
        if not n:
            os.remove(path)
            raise ValueError("확정된 사건이 없어서 보낼 것이 없어요")
        return {"path": path, "count": n}
