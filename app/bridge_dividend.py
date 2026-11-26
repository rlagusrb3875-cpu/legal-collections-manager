# -*- coding: utf-8 -*-
"""배당기일 관리 — 화면에서 부르는 dv_* 메서드.

① 조회·매칭  dv_state · dv_check · dv_search · dv_search_result · dv_law_* · dv_match · dv_save
② 현황      dv_board · dv_board_*
③ 대장      dv_ledger · dv_row_* · dv_bulk · dv_paste_* · dv_import_* · dv_link_* · dv_diffs*
④ 통계      dv_stats · dv_drill · dv_dash_save · dv_report · dv_stats_xl
오늘 할 일   dv_today
DATA 가공    dv_xlsm_*
"""
import copy
import datetime as dt
import os
import re

from core import dividend as DV
from core import dividend_out as DO
from core import excel
from core.caseno import CourtNames, parse_case_no


class DividendMixin:
    @property
    def dv(self):
        root = self.store.root
        if getattr(self, "_dv", None) is None or self._dv.root != root:
            self._dv = DV.DividendStore(root)
        return self._dv

    def _dv_me(self):
        return self.store.settings.get("me") or os.environ.get("USERNAME", "") or os.environ.get("USER", "")

    def _dv_save(self):
        self.dv.save()
        try:
            self.dv.backup()
        except Exception:
            pass

    def _dv_nopay(self):
        n = self.dv.data.get("nopay_n")
        return int(n) if n else int(round(DV.pay_lag_median(self.dv.ledger) * 1.5))

    # ============================================================ ① 조회 · 매칭

    def dv_state(self):
        d = self.dv.data
        s = d.get("search") or {}
        law = d.get("law") or {}
        out = {"search": self._dv_searched_view(), "law": {"text": "" if law.get("hidden") else law.get("text", ""), "n": len(law.get("rows") or []),
                                                        "hidden": bool(law.get("hidden")), "guessed": bool(law.get("guessed")), "names": [DV.FIELD_NAMES.get(k, "") for k in law.get("map") or [] if k], "src": law.get("src", ""),
                                                        "at": law.get("at", ""), "missing": law.get("missing", [])},
               "case_text": s.get("text", ""), "rid": s.get("rid", ""),
               "running": bool(self.sess and s.get("rid") == self.sess.get("rid") and not (self.store.run(s.get("rid", "")) or {}).get("finished")),
               "matched": self._dv_match_view() if s.get("matched") is not None else None,
               "xlsm": self._dv_xlsm_info(), "me": self._dv_me()}
        return out

    def _dv_parse_cases(self, text):
        """한 줄에 채무자 · 법원 · 사건번호 (머리글·순서 상관없음)"""
        names = CourtNames(self.meta.court_names(), self.store.settings.get("aliases"))
        t = DV.read_text(text, DV.CASE_WANT)
        good, bad = [], []
        for n, r in enumerate(t["rows"], 1):
            no = r.get("no", "")
            p = parse_case_no(DV.norm_no(no))
            if not p:
                bad.append({"line": n, "text": " · ".join(r.values()), "problem": "사건번호를 읽지 못했어요 (예: 2026타배99004)"})
                continue
            court, _, cands = names.match(r.get("court", ""))
            if not court:
                court, _, cands = names.match(DV.norm_court(r.get("court", "")))
            if not court:
                bad.append({"line": n, "text": " · ".join(r.values()), "problem": "법원 이름을 알 수 없어요" + (f" (혹시: {', '.join(cands[:3])})" if cands else "")})
                continue
            debtor = (r.get("debtor") or "").strip()
            if len(debtor.replace(" ", "")) < 2:
                bad.append({"line": n, "text": " · ".join(r.values()), "problem": "채무자 이름이 있어야 나의사건검색에서 찾을 수 있어요"})
                continue
            if p[1] not in self.meta.all_dvs_names():
                bad.append({"line": n, "text": " · ".join(r.values()), "problem": f"「{p[1]}」은 나의사건검색에 없는 사건구분이에요"})
                continue
            good.append({"court": court, "court_code": self.meta.court(court)["code"], "year": p[0], "dvs": p[1], "serial": p[2],
                         "party": debtor, "no": f"{p[0]}{p[1]}{p[2]}"})
        return t, good, bad

    def dv_check(self, text):
        t, good, bad = self._dv_parse_cases(text)
        return {"n": len(t["rows"]), "good": len(good), "bad": bad, "missing": t.get("missing", []), "has_head": t["has_head"]}

    def dv_search(self, text):
        t, good, bad = self._dv_parse_cases(text)
        if not good:
            raise ValueError(bad[0]["problem"] if bad else "조회할 배당사건을 넣어 주세요")
        ids, items = [], []
        for g in good:
            cid = self.store.find_key(self.store.key_of(g["court"], g["year"], g["dvs"], g["serial"]))
            if cid:
                c = self.store.cases[cid]
                c["party"] = g["party"]
            else:
                data = {k: g[k] for k in ("court", "court_code", "year", "dvs", "serial", "party")}
                data.update(owner=self.store.settings.get("me", ""), temp=True, memo1="배당 조회")
                c = self.store.add_case(data)
                cid = c["id"]
            ids.append(cid)
            items.append({"cid": cid, "debtor": g["party"], "court": DV.norm_court(g["court"]), "no": g["no"]})
        self.store.save_cases()
        st = self.run_start(name="배당 조회", case_ids=ids)
        self.dv.data["search"] = {"rid": st.get("rid") or (self.sess or {}).get("rid", ""), "text": text, "items": items,
                                  "at": DV.now(), "del": [], "order": [], "matched": None, "mdel": [], "morder": []}
        self._dv_save()
        st["skipped"] = bad
        self._act(f"배당 조회 시작 · {len(ids)}건", "dv", "dv_run")
        return st

    def _dv_searched(self):
        s = self.dv.data.get("search") or {}
        run = self.store.run(s.get("rid", "")) if s.get("rid") else None
        st = {it["cid"]: it for it in (run or {}).get("items", [])}
        out = []
        for it in s.get("items") or []:
            k = DV.key_of(it["court"], it["no"])
            if k in (s.get("del") or []):
                continue
            ri = st.get(it["cid"], {})
            state = ri.get("state", "wait")
            res = self.store.result(it["cid"]) if state == "done" else {}
            ex = DV.extract(res, it["court"], it["debtor"], it["no"]) if state == "done" else {"date": "", "rel": [], "third": ""}
            out.append({"cid": it["cid"], "debtor": it["debtor"], "court": it["court"], "no": it["no"], "state": state,
                        "ok": state == "done", "msg": ri.get("msg", ""), "date": ex["date"], "rel": ex["rel"], "third": ex["third"]})
        order = s.get("order") or []
        if order:
            ix = {k: i for i, k in enumerate(order)}
            out.sort(key=lambda x: ix.get(DV.key_of(x["court"], x["no"]), 1e6))
        return out

    def _dv_searched_view(self):
        L = self._dv_searched()
        return {"rows": L, "done": sum(1 for x in L if x["state"] != "wait"), "ok": sum(1 for x in L if x["ok"]),
                "fail": sum(1 for x in L if x["state"] in ("notfound", "skip")), "total": len(L)}

    def dv_search_result(self):
        return self.dv_state()

    def dv_search_del(self, key, undo=False):
        s = self.dv.data.get("search") or {}
        d = set(s.get("del") or [])
        d.discard(key) if undo else d.add(key)
        s["del"] = list(d)
        if s.get("matched") is not None:
            s["matched"] = None if not undo else s["matched"]
        self._dv_save()
        return self.dv_state()

    def dv_search_order(self, keys):
        (self.dv.data.get("search") or {})["order"] = list(keys)
        self._dv_save()
        return self.dv_state()

    # ------------------------------------------------------------ 법조치 자료

    LAW_NEED = ("dkey", "lkey", "no")

    def _dv_law_set(self, rows_tbl, src, text="", mapping=None, has_head=None):
        """법조치 자료 읽기. 칸 짝은 ① 사람이 고른 것 ② 같은 머리글로 전에 고른 것(기억) ③ 머리글 이름 ④ 값 모양 순서."""
        rows_tbl = [list(r) for r in rows_tbl if any(str(c or "").strip() for c in r)]
        if not rows_tbl:
            raise ValueError("법조치 자료가 비어 있어요")
        mem = self.dv.data.setdefault("law_maps", {})
        t0 = DV.read_rows(rows_tbl, DV.LAW_WANT)
        sig = DV.head_sig(t0["head"], t0["has_head"])
        remembered = False
        if mapping is None and sig in mem:
            mapping, has_head, remembered = mem[sig]["map"], mem[sig]["has_head"], True
        t = DV.read_rows(rows_tbl, DV.LAW_WANT, mapping, has_head) if mapping is not None else t0
        if mapping is not None:
            mem[DV.head_sig(t["head"], t["has_head"])] = {"map": list(t["map"]), "has_head": t["has_head"]}
        for r in t["rows"]:
            r["court"] = DV.norm_court(r.get("court", ""))
            r["no"] = DV.norm_no(r.get("no", ""))
            if r.get("dno"):
                r["dno"] = DV.norm_no(r["dno"])
        got = [k for k in t["map"] if k]
        missing = [DV.FIELD_NAMES[k] for k in self.LAW_NEED if k not in got and not (k == "no" and "dno" in got)]
        self.dv.data["law"] = {"text": text[:200000], "rows": t["rows"], "raw": rows_tbl[:30000], "src": src, "at": DV.now(),
                               "head": t["head"], "map": t["map"], "has_head": t["has_head"], "missing": missing,
                               "guessed": t.get("guessed", False) and not remembered}
        self._dv_save()
        return self._dv_law_info()

    def _dv_law_info(self):
        law = self.dv.data.get("law") or {}
        return {"n": len(law.get("rows") or []), "head": law.get("head", []), "map": law.get("map", []), "has_head": law.get("has_head", True),
                "names": [DV.FIELD_NAMES.get(k, "") if k else "" for k in law.get("map", [])], "missing": law.get("missing", []),
                "guessed": law.get("guessed", False), "sample": [list(map(str, r)) for r in (law.get("raw") or [])[(1 if law.get("has_head") else 0):][:5]],
                "fields": [[k, DV.FIELD_NAMES[k]] for k in DV.LAW_WANT]}

    def dv_law_info(self):
        return self._dv_law_info()

    def dv_law_map(self, mapping, has_head=True):
        """「칸 맞추기」에서 고른 칸 짝으로 다시 읽고, 같은 머리글이면 다음에도 이 짝을 쓴다"""
        law = self.dv.data.get("law") or {}
        if not law.get("raw"):
            raise ValueError("법조치 자료를 먼저 넣어 주세요")
        return self._dv_law_set(law["raw"], law.get("src", ""), law.get("text", ""), [m or None for m in mapping], bool(has_head))

    def dv_law_text(self, text):
        return self._dv_law_set(DV.split_lines(text), "붙여넣기", text)

    def dv_law_file(self, path):
        _, rows = excel.read_table(path)
        hi = next((i for i, r in enumerate(rows[:15]) if DV.map_header(r, DV.LAW_WANT)), 0)
        return self._dv_law_set(rows[hi:], os.path.basename(path))

    def dv_case_file(self, path):
        """1번 칸에 넣을 엑셀 → 붙여넣기 글자로 돌려준다 (채무자·법원·사건번호 칸만)"""
        _, rows = excel.read_table(path)
        hi = next((i for i, r in enumerate(rows[:15]) if DV.map_header(r, DV.CASE_WANT)), 0)
        t = DV.read_rows(rows[hi:], DV.CASE_WANT)
        return "채무자\t법원\t사건번호\n" + "\n".join(f"{r.get('debtor', '')}\t{r.get('court', '')}\t{r.get('no', '')}" for r in t["rows"])

    # ------------------------------------------------------------ 매칭

    def dv_match(self):
        s = self.dv.data.get("search") or {}
        L = self.dv.data.get("law") or {}
        law = L.get("rows") or []
        if not law:
            raise ValueError("당사 법조치 자료를 먼저 넣어 주세요")
        if L.get("missing"):
            raise ValueError("칸 맞추기: 법조치 자료에서 " + " · ".join(L["missing"]) + " 칸을 못 찾았어요. 「칸 맞추기」에서 골라 주세요")
        searched = [x for x in self._dv_searched() if x["state"] != "wait"]
        if not searched:
            raise ValueError("사건검색이 끝난 건이 없어요")
        s["matched"] = DV.match(searched, law, self.dv.data["linkmem"], self.dv.data["notours"])
        s["mdel"], s["morder"] = [], []
        self._dv_save()
        return self.dv_state()

    def _dv_match_rows(self):
        s = self.dv.data.get("search") or {}
        rows = [r for r in DV.out_rows(s.get("matched") or []) if DV.row_key(r) not in (s.get("mdel") or [])]
        order = s.get("morder") or []
        if order:
            ix = {k: i for i, k in enumerate(order)}
            rows = [r for _, r in sorted(enumerate(rows), key=lambda x: (ix.get(DV.row_key(x[1]), 1e6 + x[0])))]
        return rows

    def _dv_match_view(self):
        s = self.dv.data.get("search") or {}
        M = s.get("matched") or []
        cnt = {k: sum(1 for m in M if m["status"] == k) for k in ("ok", "multi", "none", "fail", "notours")}
        cnt["remembered"] = sum(1 for m in M if m.get("remembered"))
        return {"rows": [dict(r, rk=DV.row_key(r)) for r in self._dv_match_rows()], "count": cnt}

    def dv_match_del(self, rk, undo=False):
        s = self.dv.data.get("search") or {}
        d = set(s.get("mdel") or [])
        d.discard(rk) if undo else d.add(rk)
        s["mdel"] = list(d)
        self._dv_save()
        return self.dv_state()

    def dv_match_order(self, keys):
        (self.dv.data.get("search") or {})["morder"] = list(keys)
        self._dv_save()
        return self.dv_state()

    def dv_save(self):
        """매칭 결과 → ② 현황 · ③ 대장"""
        s = self.dv.data.get("search") or {}
        rows = self._dv_match_rows()
        if not rows:
            raise ValueError("저장할 매칭 결과가 없어요")
        n = self.dv.to_ledger(rows, self._dv_me())
        keep = {DV.row_key(r) for r in rows}
        board = {DV.key_of(b["court"], b["no"]): b for b in self.dv.data["board"]}
        for m in s.get("matched") or []:
            if m["status"] in ("fail", "notours"):
                continue
            mm = copy.deepcopy(m)
            mm["hits"] = [h for h in mm.get("hits") or [] if f"{DV.norm_court(mm['court'])}|{DV.norm_no(mm['no'])}|{h.get('lkey') or mm.get('debtor', '')}" in keep]
            mm["saved_at"] = DV.now()
            board[DV.key_of(m["court"], m["no"])] = mm
        self.dv.data["board"] = list(board.values())
        fails = [{"debtor": x["debtor"], "court": x["court"], "no": x["no"]} for x in self._dv_searched() if x["state"] in ("notfound", "skip")]
        self.dv.data["last_search"] = {"at": DV.now()[:10], "fail": fails}
        self._dv_save()
        self._act(f"배당 매칭 저장 · 대장 새로 {n['add']}줄 · 기일 바뀜 {n['upd']}줄", "dv", "dv_ledger")
        return dict(n, board=len(self.dv.data["board"]), diffs=len(self.dv.data["diffs"]))

    def dv_diag(self):
        """매칭이 안 될 때 원인 찾기용 파일 (사건번호 · 칸 이름 · 건수만 — 이름 등 개인정보는 넣지 않음)"""
        import json as _j
        import re as _re
        s = self.dv.data.get("search") or {}
        law = self.dv.data.get("law") or {}
        L = [f"종합관리 배당 매칭 진단 · {DV.now()} · 판 {__import__('bridge').VERSION}", ""]
        rows = law.get("rows") or []
        L += ["■ 법조치 자료", f"  줄 수 {len(rows)} · 머리글 {law.get('head')}", f"  읽은 칸 {law.get('map')} · 못 찾은 칸 {law.get('missing')}",
              "  사건번호(앞 15개): " + ", ".join(r.get("no", "") for r in rows[:15]),
              "  법원 비어 있는 줄: " + str(sum(1 for r in rows if not r.get("court"))),
              "  채무자키 비어 있는 줄: " + str(sum(1 for r in rows if not r.get("dkey"))) + " · 법조치키 비어 있는 줄: " + str(sum(1 for r in rows if not r.get("lkey"))), ""]
        law_nos = {r.get("no") for r in rows}
        mres = {DV.key_of(m["court"], m["no"]): m for m in s.get("matched") or []}
        L.append("■ 배당사건별")
        for it in s.get("items") or []:
            res = self.store.result(it["cid"])
            lists = res.get("lists") or {}
            ex = DV.extract(res, it["court"], it["debtor"], it["no"])
            m = mres.get(DV.key_of(it["court"], it["no"]), {})
            L.append(f"- {it['court']} {it['no']} · 조회 {'됨' if res.get('checks') else '안 됨'} · 매칭 {m.get('status', '—')} · 붙은 법조치키 {len(m.get('hits') or [])}")
            L.append("    사이트 목록: " + ", ".join(f"{k}({len(v)})" for k, v in lists.items() if isinstance(v, list)) + f" · 진행내용 {len(res.get('prog') or [])}줄")
            for r in (lists.get("dlt_reltCsLst") or [])[:5]:
                L.append("    관련사건 줄 칸: " + _j.dumps({k: (v if _re.search(r"\d|법원|지원|타|명령", str(v)) else "…") for k, v in r.items()}, ensure_ascii=False))
            L.append("    뽑은 관련사건: " + (", ".join(f"{x[1]}[{x[3] if len(x) > 3 else ''}]" for x in ex["rel"]) or "없음"))
            L.append("    법조치 자료에 있는 번호: " + (", ".join(x[1] for x in ex["rel"] if x[1] in law_nos) or "없음"))
            L.append(f"    배당기일 {ex['date'] or '못 찾음'} · 공탁자 {'있음' if ex['third'] else '못 찾음'}")
        p = excel.unique_path(self.export_dir(), f"배당매칭_진단_{dt.datetime.now():%y%m%d_%H%M}", ".txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(L))
        return {"path": p}

    def dv_pick(self):
        last = self.dv.data.get("last_search") or {}
        r = DV.pick_candidates(self.dv.ledger, self.dv.data["board"], last.get("fail", []), set(self.dv.data["notours"]))
        r["last"] = last.get("at", "")
        return r

    # ============================================================ ② 현황

    def dv_board(self):
        rows = DV.out_rows(self.dv.data["board"])
        order = self.dv.data.get("board_order") or []
        if self.dv.data.get("board_sort") == "manual" and order:
            ix = {k: i for i, k in enumerate(order)}
            rows = [r for _, r in sorted(enumerate(rows), key=lambda x: ix.get(DV.row_key(x[1]), 1e6 + x[0]))]
        else:
            rows.sort(key=lambda r: r.get("date") or "9999")
        cases = [{"court": b["court"], "no": b["no"], "debtor": b.get("debtor", ""), "date": b.get("date", ""),
                  "hits": len(b.get("hits") or []), "mgrs": sorted({h.get("mgr", "") for h in b.get("hits") or []} - {""}),
                  "dkeys": [h.get("dkey", "") for h in b.get("hits") or []]} for b in self.dv.data["board"]]
        return {"rows": [dict(r, rk=DV.row_key(r)) for r in rows], "cases": cases, "sort": self.dv.data.get("board_sort", "date"),
                "last": (self.dv.data.get("last_search") or {}).get("at", "")}

    def dv_board_order(self, keys=None, sort=None):
        if keys is not None:
            self.dv.data["board_order"] = list(keys)
            self.dv.data["board_sort"] = "manual"
        if sort:
            self.dv.data["board_sort"] = sort
        self._dv_save()
        return self.dv_board()

    def dv_board_del(self, rk, undo_snapshot=None):
        """현황에서 한 줄 지우기 (대장은 그대로). undo_snapshot 이 오면 되돌리기"""
        if undo_snapshot is not None:
            self.dv.data["board"] = undo_snapshot
            self._dv_save()
            return self.dv_board()
        snap = copy.deepcopy(self.dv.data["board"])
        court, no, k = rk.split("|", 2)
        out = []
        for b in self.dv.data["board"]:
            if DV.key_of(b["court"], b["no"]) != court + "|" + no:
                out.append(b)
                continue
            hits = [h for h in b.get("hits") or [] if (h.get("lkey") or b.get("debtor", "")) != k]
            if hits and len(hits) != len(b.get("hits") or []):
                out.append(dict(b, hits=hits))
        self.dv.data["board"] = out
        self._dv_save()
        return dict(self.dv_board(), undo=snap)

    # ============================================================ ③ 대장

    def _dv_row_out(self, r):
        s, c = DV.stage(r)
        return dict(r, stage=s, stage_c=c, ours_court=DV.ours_court(r), ours_no=DV.ours_no(r), done=DV.is_done(r),
                    need_send=DV.need_send(r), dif=any(d["id"] == r["id"] for d in self.dv.data["diffs"]))

    def dv_ledger(self):
        L = self.dv.ledger
        rows = [self._dv_row_out(r) for r in L]
        if self.dv.data.get("ledger_sort") != "manual":
            rows.sort(key=lambda r: r.get("date") or "9999")
        return {"rows": rows, "sort": self.dv.data.get("ledger_sort", "date"), "diffs": len(self.dv.data["diffs"]),
                "me": self._dv_me(), "nopay_n": self._dv_nopay(), "decision_dir": self._dv_set().get("decision_dir", "")}

    def _dv_set(self):
        return self.store.settings.get("dividend") or {}

    def dv_ledger_order(self, ids=None, sort=None):
        if ids is not None:
            pos = {i: n for n, i in enumerate(ids)}
            self.dv.data["ledger"].sort(key=lambda r: pos.get(r["id"], 1e6))
            self.dv.data["ledger_sort"] = "manual"
        if sort:
            self.dv.data["ledger_sort"] = sort
        self._dv_save()
        return {"ok": True}

    LABEL = {"dkey": "채무자키", "lkey": "법조치키", "debtor": "채무자명", "mgr": "담당자", "third": "제3채무자", "ours": "당사 관련사건",
             "claim": "청구액", "amt": "배당액", "send_at": "발송일", "recv_at": "수령일", "memo": "메모", "date": "배당기일",
             "court": "배당법원", "no": "배당사건번호", "check": "검수", "recv": "수령 단계"}

    def dv_row_save(self, rid, fields):
        r = self.dv.row(rid)
        if not r:
            raise ValueError("줄을 찾지 못했어요")
        me = self._dv_me()
        ch = []
        for k, v in (fields or {}).items():
            if k not in self.LABEL:
                continue
            if k in ("amt", "claim"):
                v = DV.won(v)
            elif k in ("send_at", "recv_at", "date"):
                v = DV.norm_date(v)
            elif k in ("court",):
                v = DV.norm_court(v)
            elif k in ("no",):
                v = DV.norm_no(v)
            else:
                v = str(v or "").strip()
            if str(r.get(k, "") if r.get(k) is not None else "") == str(v):
                continue
            show = lambda x: (f"{int(x):,}" if k in ("amt", "claim") and x not in ("", None) else DV.RECV_LABEL.get(x, x) if k == "recv" else x) or "—"
            ch.append(f"{self.LABEL[k]} {show(r.get(k))} → {show(v)}")
            r[k] = v
            if k == "check" and v == "완료":
                r["check_by"] = me
            if k == "recv" and v == "수령" and not r.get("recv_at"):
                r["recv_at"] = dt.date.today().isoformat()
            if k == "recv" and v == "발송" and not r.get("send_at"):
                r["send_at"] = dt.date.today().isoformat()
            if k == "third":
                r["third_src"] = "직접"
        if ch:
            r["fresh"] = False
            r["changed"] = False
            DV.DividendStore.log(r, " · ".join(ch), me)
            self._dv_save()
        return {"row": self._dv_row_out(r), "changed": len(ch)}

    def dv_row_add(self):
        r = self.dv.new_row({"no": "", "memo": ""}, "직접", self._dv_me())
        DV.DividendStore.log(r, "직접 넣음", self._dv_me())
        self._dv_save()
        return self._dv_row_out(r)

    def dv_bulk(self, ids, action):
        me = self._dv_me()
        today = dt.date.today().isoformat()
        n = 0
        for rid in ids or []:
            r = self.dv.row(rid)
            if not r:
                continue
            if action == "check" and r.get("check") != "완료":
                r.update(check="완료", check_by=me)
                DV.DividendStore.log(r, "검수 완료 (한꺼번에)", me)
            elif action == "send" and r.get("recv") == "대기":
                r.update(recv="발송", send_at=r.get("send_at") or today)
                DV.DividendStore.log(r, "발송 (한꺼번에)", me)
            elif action == "recv" and r.get("recv") != "수령":
                r.update(recv="수령", recv_at=r.get("recv_at") or today)
                DV.DividendStore.log(r, "수령완료 (한꺼번에)", me)
            elif action == "none":
                r.update(recv="수령", amt=0, recv_at=r.get("recv_at") or today)
                DV.DividendStore.log(r, "배당 없음 (0원)", me)
            elif action == "delete" and not r.get("deleted"):
                r["deleted"] = True
                DV.DividendStore.log(r, "지움 (지운 줄로 옮김)", me)
            elif action == "restore" and r.get("deleted"):
                r["deleted"] = False
                DV.DividendStore.log(r, "되살림", me)
            else:
                continue
            r["fresh"] = False
            r["changed"] = False
            n += 1
        if n:
            self._dv_save()
        return {"n": n}


    def dv_reset(self):
        """① 조회·매칭만 처음으로: 붙여넣기 칸 · 사건검색 결과 · 매칭 결과를 비운다. 대장 · 현황은 그대로."""
        self.dv.data["search"] = {}
        law = self.dv.data.get("law") or {}
        if law.get("rows"):
            law["hidden"] = True  # 법조치 자료는 「지난번 자료」로 다시 쓸 수 있게 남긴다
        self._dv_save()
        self._act("배당 조회·매칭을 처음으로 (대장은 그대로)", "dv", "dv_run")
        return self.dv_state()

    def dv_law_last(self):
        law = self.dv.data.get("law") or {}
        law["hidden"] = False
        self._dv_save()
        return law.get("text", "")

    # ------------------------------------------------------------ 대장 칸 비우기 (하나 · 고른 칸 한꺼번에)

    CELL_FIELD = {"date": "date", "debtor": "debtor", "dkey": "dkey", "lkey": "lkey", "mgr": "mgr", "oc": "ours", "on": "ours",
                  "third": "third", "amt": "amt"}

    def dv_cells_clear(self, cells):
        """cells: [{id, k(화면 칸)}] → 값 비우기. 되돌리기용 원래 값을 돌려준다. 배당법원·사건번호·단계는 비우지 않는다."""
        me = self._dv_me()
        undo, n, skip = [], 0, 0
        seen = set()
        for c in cells or []:
            f = self.CELL_FIELD.get(c.get("k"))
            r = self.dv.row(c.get("id"))
            if not r or not f:
                skip += 1
                continue
            if (r["id"], f) in seen:
                continue
            seen.add((r["id"], f))
            if r.get(f) in ("", None):
                continue
            undo.append({"id": r["id"], "f": f, "v": r.get(f)})
            DV.DividendStore.log(r, f"칸 비움 · {self.LABEL.get(f, f)} {r.get(f)} → —", me)
            r[f] = ""
            if f == "third":
                r["third_src"] = "직접"
            n += 1
        if n:
            self._dv_save()
        return {"n": n, "skip": skip, "undo": undo}

    def dv_cells_set(self, cells):
        """되돌리기: [{id, f, v}]"""
        me = self._dv_me()
        for c in cells or []:
            r = self.dv.row(c["id"])
            if r:
                r[c["f"]] = c["v"]
                DV.DividendStore.log(r, f"되돌림 · {self.LABEL.get(c['f'], c['f'])} → {c['v']}", me)
        self._dv_save()
        return {"n": len(cells or [])}

    # ------------------------------------------------------------ 붙여넣어 고치기

    def dv_paste_preview(self, text):
        return DV.paste_parse(text, self.dv.ledger)

    def dv_paste_apply(self, changes):
        me = self._dv_me()
        n = 0
        for c in changes or []:
            r = self.dv.row(c["id"])
            if not r:
                continue
            show = lambda x: (f"{int(x):,}" if c["f"] in ("amt", "claim") and x not in ("", None) else DV.RECV_LABEL.get(x, x) if c["f"] == "recv" else x) or "—"
            DV.DividendStore.log(r, f"붙여넣기 · {c['n']} {show(r.get(c['f']))} → {show(c['to'])}", me)
            r[c["f"]] = c["to"]
            if c["f"] == "check" and c["to"] == "완료":
                r["check_by"] = me
            n += 1
        if n:
            self._dv_save()
        return {"n": n}

    # ------------------------------------------------------------ 기존 엑셀 대장 가져오기

    IMPORT_MAP = [("dkey", r"채무자\s*키|고객\s*번호"), ("lkey", r"법조치\s*키"), ("debtor", r"^채무자(명)?$|성명|고객명"), ("mgr", r"담당"),
                  ("court", r"^(배당)?\s*법원$|관할"), ("no", r"^(배당)?\s*사건\s*번호$|^사건$"), ("date", r"배당\s*기일"),
                  ("amt", r"배당\s*액|배당금"), ("claim", r"청구\s*액"), ("check", r"검수"), ("recv", r"수령\s*(여부|단계)?$"),
                  ("send_at", r"발송\s*일"), ("recv_at", r"수령\s*일|입금\s*일"), ("memo", r"메모|비고"), ("third", r"제\s*3\s*채무자|공탁자"),
                  ("ours", r"당사\s*(관련)?\s*사건|압류\s*사건|타채")]

    def _dv_import_rows(self, path=None, text=None):
        rows = excel.read_table(path)[1] if path else DV.split_lines(text)
        hi = 0
        for i, r in enumerate(rows[:15]):
            if sum(1 for c in r if any(re.search(rx, str(c or "").strip()) for _, rx in self.IMPORT_MAP)) >= 3:
                hi = i
                break
        head = [str(c or "").strip() for c in rows[hi]]
        used, m = set(), []
        for h in head:
            k = next((k for k, rx in self.IMPORT_MAP if k not in used and re.search(rx, h)), None)
            if k:
                used.add(k)
            m.append(k)
        if "no" not in m:
            raise ValueError("「사건번호」 칸을 찾지 못했어요")
        out = []
        for r in rows[hi + 1:]:
            o = {}
            for i, k in enumerate(m):
                if k and i < len(r) and r[i] not in (None, ""):
                    o[k] = r[i]
            if not o.get("no"):
                continue
            o["court"] = DV.norm_court(o.get("court", ""))
            o["no"] = DV.norm_no(o["no"])
            for k in ("date", "send_at", "recv_at"):
                if k in o:
                    o[k] = DV.norm_date(o[k])
            for k in ("amt", "claim"):
                if k in o:
                    o[k] = DV.won(o[k])
            if "check" in o:
                v = str(o["check"]).strip()
                o["check"] = "완료" if re.search(r"완료|^[OoYy○]$|^예$", v) else "보류" if "보류" in v else "대기"
            if "recv" in o:
                v = str(o["recv"])
                o["recv"] = "수령" if re.search(r"완료|수령|^[OoYy○]$", v) else "발송" if "발송" in v else "수령" if "없음" in v else "대기"
                if "없음" in v:
                    o["amt"] = 0
            if o.get("ours") and not re.search(r"(법원|지원)\s", str(o["ours"])) and o.get("court"):
                o["ours"] = f"{o['court']} {DV.norm_no(o['ours'])}"
            out.append({k: (str(v).strip() if isinstance(v, str) else v) for k, v in o.items()})
        return head, [DV.FIELD_NAMES.get(k) or self.LABEL.get(k, "") if k else "" for k in m], out

    def dv_import_preview(self, path=None, text=None):
        head, names, rows = self._dv_import_rows(path, text)
        new = same = 0
        conflicts = []
        for o in rows:
            ex = self.dv.find(o.get("court", ""), o["no"], o.get("lkey", ""), o.get("debtor", ""))
            if not ex:
                new += 1
                continue
            same += 1
            for k, v in o.items():
                if v not in ("", None) and ex.get(k) not in ("", None) and str(ex.get(k)) != str(v):
                    conflicts.append({"id": ex["id"], "no": ex["no"], "f": k, "n": self.LABEL.get(k, k), "mine": ex.get(k), "file": v})
        return {"head": head, "names": names, "n": len(rows), "new": new, "same": same, "conflicts": conflicts[:200]}

    def dv_import_apply(self, path=None, text=None, take_file=None):
        """take_file: 다른 값 중 파일 값으로 바꿀 것 [[id, 칸]]"""
        _, _, rows = self._dv_import_rows(path, text)
        take = {(a, b) for a, b in (take_file or [])}
        me = self._dv_me()
        src = f"엑셀 가져옴 ({os.path.basename(path) if path else '붙여넣기'})"
        new = fill = 0
        for o in rows:
            ex = self.dv.find(o.get("court", ""), o["no"], o.get("lkey", ""), o.get("debtor", ""))
            if not ex:
                r = self.dv.new_row(dict(o, fresh=False), src, me)
                r["fresh"] = False
                if r.get("check") == "완료" and not r.get("check_by"):
                    r["check_by"] = r.get("mgr", "")
                DV.DividendStore.log(r, src, me)
                new += 1
                continue
            ch = []
            for k, v in o.items():
                if v in ("", None):
                    continue
                if ex.get(k) in ("", None) or (ex["id"], k) in take:
                    if str(ex.get(k)) != str(v):
                        ch.append(f"{self.LABEL.get(k, k)} → {v}")
                        ex[k] = v
            if ch:
                DV.DividendStore.log(ex, f"{src} · " + " · ".join(ch), me)
                fill += 1
        self._dv_save()
        self._act(f"배당 대장 엑셀 가져오기 · 새로 {new}줄 · 채움 {fill}줄", "dv", "dv_ledger")
        return {"new": new, "fill": fill}

    # ------------------------------------------------------------ 못 찾은 건 연결 · 우리 사건 아님

    def dv_link_search(self, q):
        q = (q or "").replace(" ", "")
        law = (self.dv.data.get("law") or {}).get("rows") or []
        out = [r for r in law if not q or q in "".join(str(r.get(k, "")) for k in ("debtor", "no", "dkey", "lkey")).replace(" ", "")]
        return out[:30]

    def dv_link(self, rid, lkey):
        r = self.dv.row(rid)
        x = next((y for y in (self.dv.data.get("law") or {}).get("rows") or [] if y.get("lkey") == lkey), None)
        if not r or not x:
            raise ValueError("연결할 줄을 찾지 못했어요")
        r.update(dkey=x.get("dkey", ""), lkey=x.get("lkey", ""), mgr=x.get("mgr", ""), debtor=x.get("debtor") or r.get("debtor", ""),
                 ours=f"{DV.norm_court(x.get('court', ''))} {DV.norm_no(x.get('no', ''))}")
        if not r.get("third") and x.get("third"):
            r.update(third=x["third"], third_src="법조치 자료")
        if r.get("memo", "").startswith("우리 사건 못 찾음"):
            r["memo"] = ""
        self.dv.data["linkmem"][DV.key_of(r["court"], r["no"])] = x["lkey"]
        DV.DividendStore.log(r, f"직접 연결 · {x['lkey']} ({x.get('court', '')} {x.get('no', '')}) — 다음 매칭 때 자동", self._dv_me())
        self._dv_save()
        return self._dv_row_out(r)

    def dv_notours(self, rid):
        r = self.dv.row(rid)
        if not r:
            raise ValueError("줄을 찾지 못했어요")
        k = DV.key_of(r["court"], r["no"])
        if k not in self.dv.data["notours"]:
            self.dv.data["notours"].append(k)
        r["deleted"] = True
        DV.DividendStore.log(r, "우리 사건 아님 — 다음 조회·매칭에서 뺌", self._dv_me())
        self._dv_save()
        return {"ok": True}

    # ------------------------------------------------------------ 법조치 자료와 다른 값

    def dv_diffs(self):
        out = []
        for i, d in enumerate(self.dv.data["diffs"]):
            r = self.dv.row(d["id"])
            if r:
                out.append(dict(d, i=i, no=r["no"], lkey=r.get("lkey", ""), n=self.LABEL.get(d["f"], d["f"])))
        return out

    def dv_diffs_apply(self, idx=None, skip=False):
        D = self.dv.data["diffs"]
        if skip:
            self.dv.data["diffs"] = []
            self._dv_save()
            return {"n": 0}
        pick = set(idx or [])
        n = 0
        for i, d in enumerate(D):
            if i not in pick:
                continue
            r = self.dv.row(d["id"])
            if not r:
                continue
            r[d["f"]] = d["to"]
            if d["f"] == "third":
                r["third_src"] = "법조치 자료"
            r["changed"] = True
            DV.DividendStore.log(r, f"법조치 자료 반영 · {self.LABEL.get(d['f'])} {d['from'] or '—'} → {d['to']}", self._dv_me())
            n += 1
        self.dv.data["diffs"] = [d for i, d in enumerate(D) if i not in pick]
        self._dv_save()
        return {"n": n}

    # ------------------------------------------------------------ 결정문 (사건번호로 파일 찾기)

    def dv_decision(self, ours, action="open"):
        folder = self._dv_set().get("decision_dir", "")
        no = DV.ours_no({"ours": ours}) or DV.norm_no(ours)
        if not folder or not os.path.isdir(folder):
            raise ValueError("설정 → 배당기일에서 결정문 폴더를 먼저 정해 주세요")
        hits = []
        for base, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(".pdf") and no and no in re.sub(r"\s", "", f):
                    hits.append(os.path.join(base, f))
            if len(hits) > 5:
                break
        if not hits:
            raise ValueError(f"결정문 폴더에 「{no}」가 들어간 PDF가 없어요")
        p = sorted(hits)[0]
        if action == "print" and os.name == "nt":
            os.startfile(p, "print")  # noqa
        else:
            self.open_path(p)
        return {"path": p}

    def dv_decision_dir(self):
        d = self.choose_folder()
        if d:
            self.store.set_setting("dividend.decision_dir", d, "배당: 결정문 폴더")
        return d or ""

    # ============================================================ 오늘 할 일

    def dv_today(self, mine=True):
        me = self._dv_me()
        n = self._dv_nopay()
        G = DV.today_groups(self.dv.ledger, me, mine, n, self.dv.data["diffs"])
        by = {r["id"]: r for r in self.dv.ledger}
        for g in G:
            g["rows"] = [self._dv_row_out(by[i]) for i in g["ids"][:6]]
            g["n"] = len(g["ids"])
        return {"groups": G, "me": me, "nopay_n": n, "lag": DV.pay_lag_median(self.dv.ledger), "total": sum(g["n"] for g in G)}

    def dv_nopay_set(self, n):
        self.dv.data["nopay_n"] = int(n) if n else None
        self._dv_save()
        return self._dv_nopay()

    def _dv_todos(self):
        """배당 할 일을 「확인할 것」 한 목록으로 (7일 안 기일 · 발송 전 · 입금 없음 · 검수 대기 · 바뀐 건). 담당자는 법조치 자료의 담당자명."""
        out, td = [], self.store.todos
        try:
            G = DV.today_groups(self.dv.ledger, "", False, self._dv_nopay(), self.dv.data["diffs"])
        except Exception:
            return out
        by = {r["id"]: r for r in self.dv.ledger}
        color = {"soon": "red", "send": "red", "pay": "orange", "check": "orange", "chg": "blue"}
        for g in G:
            for i in g["ids"]:
                r = by.get(i)
                if not r:
                    continue
                key = f"D|{g['k']}|{i}|{r.get('date', '')}"
                st = td.get(key, {})
                due = r.get("date", "") if g["k"] in ("soon", "send") else ""
                out.append({"key": key, "cid": "", "kind": {"soon": "배당 · 7일 안 기일", "send": "배당 · 발송 전", "pay": "배당 · 입금 없음", "check": "배당 · 검수 대기"}.get(g["k"], "배당 · 바뀐 건"),
                            "color": color.get(g["k"], "blue"), "date": r.get("date", ""), "text": f"{g['sub']} · {r.get('court', '')} · 법조치키 {r.get('lkey') or '없음'}",
                            "due": st.get("deadline") or due, "due_manual": True, "ask": False, "done": st.get("done", ""), "done_note": st.get("note", ""),
                            "done_by": st.get("by", ""), "new": False, "legal": True, "dv": True, "go": "dv_ledger", "arg": {"open": i, "lf": "all", "q": ""},
                            "case_no": r.get("no", ""), "party": r.get("debtor", ""), "court": "", "memo1": "", "owner": r.get("mgr", "")})
        return out

    def _dv_counts(self):
        try:
            G = DV.today_groups(self.dv.ledger, self._dv_me(), True, self._dv_nopay(), self.dv.data["diffs"])
            return {"today": sum(len(g["ids"]) for g in G), "ledger": sum(1 for r in self.dv.ledger if not r.get("deleted") and (r.get("check") != "완료" or DV.need_send(r)))}
        except Exception:
            return {"today": 0, "ledger": 0}

    # ============================================================ ④ 통계

    def _dv_f(self, f):
        d = self.dv.data["dash"]
        out = {"period": d.get("period", "12m"), "basis": d.get("basis", "date"), "third": "", "mgr": "", "court": ""}
        out.update({k: v for k, v in (f or {}).items() if k in out})
        return out

    def dv_stats(self, f=None):
        F = self._dv_f(f)
        D = DV.dashboard(self.dv.ledger, F, self.dv.data["dash"], self._dv_nopay())
        D.update(f=F, dash=self.dv.data["dash"], nopay_n=self._dv_nopay(), periods=DV.PERIODS, today=dt.date.today().isoformat())
        by = {r["id"]: r for r in self.dv.ledger}
        D["old_rows"] = [dict(self._dv_row_out(by[x["id"]]), days=x["days"]) for x in D["aging"]["old"][:20] if x["id"] in by]
        return D

    def dv_drill(self, f, key):
        F = self._dv_f(f)
        d = DV.drill(self.dv.ledger, F, self.dv.data["dash"], key, self._dv_nopay())
        by = {r["id"]: r for r in self.dv.ledger}
        d["rows"] = [self._dv_row_out(by[i]) for i in d["ids"]]
        d["cond"] = self._dv_cond(F)
        return d

    def _dv_cond(self, F):
        ms = DV.Stats(self.dv.ledger, F).months()
        return f"{DV.PERIODS.get(F['period'], F['period'])} ({ms[0].replace('-', '.')}~{ms[-1].replace('-', '.')}) · " \
               f"{'수령일' if F['basis'] == 'recv' else '배당기일'} 기준" + "".join(f" · {F[k]}" for k in ("third", "mgr", "court") if F.get(k))

    def dv_dash_save(self, dash, nopay_n=None):
        d = dict(DV.DASH_DEFAULT)
        d.update({k: v for k, v in (dash or {}).items() if k in DV.DASH_DEFAULT})
        self.dv.data["dash"] = d
        if nopay_n:
            self.dv.data["nopay_n"] = int(nopay_n)
        self._dv_save()
        return d

    def dv_report(self, f=None, save=False):
        F = self._dv_f(f)
        html = DO.report_html(self.dv.ledger, F, self.dv.data["dash"], self._dv_nopay(), self.book, self._dv_me(), self._dv_cond(F))
        name = f"{self.book} 배당통계보고서_{DV.PERIODS.get(F['period'], F['period']).replace(' ', '')}_{dt.date.today():%y%m%d}"
        if not save:
            return {"html": html, "name": name + ".html"}
        p = excel.unique_path(self.export_dir(), name, ".html")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(html)
        self._act("배당 통계 보고서 저장", "dv", "dv_stats")
        return {"path": p}

    def dv_stats_xl(self, f=None):
        F = self._dv_f(f)
        p = excel.unique_path(self.export_dir(), f"{self.book} 배당통계_{dt.date.today():%y%m%d}")
        DO.stats_xlsx(p, self.dv.ledger, F, self.dv.data["dash"], self._dv_nopay())
        return {"path": p}

    # ============================================================ 엑셀로 내보내기 (① · ② · ③ · 근거 목록)

    def dv_export(self, what, ids=None, rks=None):
        name = {"match": "배당기일", "board": "배당기일현황", "ledger": "배당관리대장", "drill": "배당_근거목록"}.get(what, "배당")
        p = excel.unique_path(self.export_dir(), f"{self.book} {name}_{dt.date.today():%y%m%d}")
        if what in ("match", "board"):
            rows = self._dv_match_rows() if what == "match" else self.dv_board()["rows"]
            if rks:
                pos = {k: i for i, k in enumerate(rks)}
                rows = sorted([r for r in rows if DV.row_key(r) in pos], key=lambda r: pos[DV.row_key(r)])
            DO.match_xlsx(p, rows)
        else:
            by = {r["id"]: r for r in self.dv.ledger}
            rows = [by[i] for i in (ids or []) if i in by] if ids is not None else [r for r in self.dv.ledger if not r.get("deleted")]
            DO.ledger_xlsx(p, rows, self.dv.ledger if what == "ledger" else None)
        self._act(f"배당 {name} 엑셀로 내보냄", "dv", "dv_ledger")
        return {"path": p}

    # ============================================================ DATA 가공 (매크로 엑셀 열기)

    def _dv_xlsm_info(self):
        x = self.dv.data.get("xlsm") or {}
        p = x.get("path", "")
        info = None
        if p and os.path.isfile(p):
            st = os.stat(p)
            info = {"mod": dt.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"), "size": f"{max(1, st.st_size // 1024):,}KB"}
        return {"path": p, "ok": bool(info), "info": info,
                "recent": [dict(r, ok=os.path.isfile(r["path"])) for r in x.get("recent") or []]}

    def dv_xlsm_set(self, path):
        path = (path or "").strip().strip('"')
        x = self.dv.data.setdefault("xlsm", {"path": "", "recent": []})
        x["path"] = path
        if path:
            rec = [r for r in x.get("recent") or [] if r["path"] != path]
            x["recent"] = [{"path": path, "when": dt.date.today().strftime("%y.%m.%d")}] + rec[:7]
        self._dv_save()
        return self._dv_xlsm_info()

    def dv_xlsm_pick(self):
        p = self.choose_file("excel")
        return self.dv_xlsm_set(p) if p else self._dv_xlsm_info()

    def dv_xlsm_open(self):
        x = self._dv_xlsm_info()
        if not x["ok"]:
            raise ValueError("연결된 매크로 엑셀 파일이 없어요. 「경로」에서 파일을 정해 주세요")
        self.open_path(x["path"])
        return x
