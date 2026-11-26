# -*- coding: utf-8 -*-
"""경매 (법원경매정보 · 프로그램 안 브라우저 창)"""
import datetime as dt
import json
import os
import subprocess
import sys
import threading
import time

from appbase import DEFAULT_BOOK, LOCAL, _desktop, _save_pointer, log_event
from core import auction as AU
from core import excel, rules
from core.caseno import CourtNames, name_variants, parse_case_no
from core.meta import Meta
from core.site import Court, SiteError
from core.store import SUMMARY_COLS, Store, now


class AuctionMixin:
    # ================================================================ 경매 (법원경매정보 · 프로그램 안 브라우저 창)

    @property
    def auct(self):
        root = self.store.root
        if getattr(self, "_auct", None) is None or self._auct.root != root:
            self._auct = AU.AuctionStore(root)
        return self._auct

    def _auct_courts(self):
        if not getattr(self, "_acourts", None):
            self._acourts = AU.load_courts()
        return self._acourts

    def _auct_parse(self, text):
        """한 줄에 법원 · 2025타경12345 (· 메모). 탭·쉼표·띄어쓰기 모두."""
        import re
        courts = self._auct_courts()
        names = CourtNames([c["name"] for c in courts], self.store.settings.get("aliases"))
        code_of = {c["name"]: c["code"] for c in courts}
        good, bad = [], []
        for n, line in enumerate(str(text or "").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            p = AU.parse_auction_no(line)
            if not p:
                bad.append({"line": n, "text": line, "problem": "「2025타경12345」 모양의 사건번호가 없어요"})
                continue
            m = re.search(r"\d{4}\s*타\s*경\s*[\d,]+", line)
            rest = (line[:m.start()] + "\t" + line[m.end():]).strip()
            cells = [x.strip() for x in re.split(r"\t|,|，|\|", rest) if x.strip()]
            court, memo = None, []
            for i, cell in enumerate(cells):
                if not court:
                    c, _, _ = names.match(cell)
                    if not c:  # 띄어쓰기로만 나뉜 경우: 앞쪽 몇 단어를 법원으로
                        toks = cell.split()
                        for k in range(len(toks), 0, -1):
                            c, _, _ = names.match(" ".join(toks[:k]))
                            if c:
                                memo += toks[k:]
                                break
                    if c:
                        court = c
                        continue
                memo.append(cell)
            if not court:
                bad.append({"line": n, "text": line, "problem": "법원 이름을 알 수 없어요 (법원경매정보의 법원·지원 이름)"})
                continue
            good.append({"court": court, "court_code": code_of[court], "year": p[0], "serial": p[1],
                         "memo1": " ".join(memo).strip()})
        return good, bad

    def auction_list(self, archived=False):
        out = [dict(a) for a in self.auct.items.values() if bool(a.get("archived")) == bool(archived)]
        out.sort(key=lambda a: (a.get("next_sale", {}).get("date") or "9999", a["case_no"]))
        # 사건 대장의 소송과 연결: 메모(계좌번호, 하이픈·띄어쓰기 무시) 또는 경매 「관련사건」 번호
        by_memo, by_no = {}, {}
        for c in self.store.active_cases():
            if AU.norm_memo(c.get("memo1")):
                by_memo.setdefault(AU.norm_memo(c["memo1"]), []).append(c)
            by_no.setdefault(self.store.case_no(c), []).append(c)
        for a in out:
            links = {}
            for c in by_memo.get(AU.norm_memo(a.get("memo1")), []):
                links[c["id"]] = {"cid": c["id"], "case_no": self.store.case_no(c), "why": "메모"}
            for no in a.get("related_nos") or []:
                for c in by_no.get(no, []):
                    links.setdefault(c["id"], {"cid": c["id"], "case_no": self.store.case_no(c), "why": "관련사건"})
            a["linked"] = list(links.values())[:3]
        return out

    def auction_check(self, text):
        good, bad = self._auct_parse(text)
        return {"good": [dict(g, case_no=f"{g['year']}타경{g['serial']}") for g in good], "bad": bad}

    def auction_add(self, text):
        good, bad = self._auct_parse(text)
        added = 0
        ids = []
        for g in good:
            a, new = self.auct.add(g["court"], g["court_code"], g["year"], g["serial"], g["memo1"], self.store.settings.get("me", ""))
            added += new
            ids.append(a["id"])
        self.auct.save()
        return {"added": added, "same": len(good) - added, "bad": bad, "ids": ids}

    def auction_import(self, path):
        _, rows = excel.read_table(path)
        lines = ["\t".join(r) for r in rows if any(x for x in r)]
        r = self.auction_add("\n".join(lines))
        r["bad"] = [b for b in r["bad"] if "사건번호" not in b["problem"] or b["line"] > 1]  # 머리글 줄은 빼고
        return r

    def auction_archive(self, ids, archived=True):
        for i in ids:
            if i in self.auct.items:
                self.auct.items[i]["archived"] = bool(archived)
        self.auct.save()
        return len(ids)

    def auction_delete(self, ids):
        """경매 사건을 지운다 (결과 파일·할 일·조회 기록에서도). 지우기 전에 채권 폴더를 자동 백업한다."""
        ids = [i for i in ids if i in self.auct.items]
        if not ids:
            return 0
        if self.asess:
            raise ValueError("경매 조회 중에는 지울 수 없어요 — 「멈추기」를 누른 뒤 지워 주세요")
        try:
            self.store.backup()
        except Exception:
            pass
        drop = set(ids)
        for i in ids:
            self.auct.items.pop(i, None)
            p = os.path.join(self.auct.root, "auction", i + ".json")
            if os.path.isfile(p):
                os.remove(p)
        for r in list(self.auct.runs):
            r["ids"] = [x for x in r["ids"] if x not in drop]
            r["done"] = [d for d in r["done"] if d["aid"] not in drop]
            if not r["ids"]:
                self.auct.runs.remove(r)
        for k in [k for k in self.store.todos if k.startswith("A|") and k.split("|")[1] in drop]:
            self.store.todos.pop(k)
        self.auct.save()
        self.auct.save_runs()
        self.store.save_todos()
        return len(ids)

    def auction_run_remove(self, aids=None, scope=""):
        """경매 조회 중 「이번 조회」 목록에서 빼기 (경매 사건과 저장된 결과는 그대로)"""
        s = self.asess
        if not s:
            raise ValueError("지금 하는 경매 조회가 없어요")
        drop = set(aids or [])
        gone = [d["aid"] for d in s["done"] if scope == "done" or d["aid"] in drop]
        s["done"] = [d for d in s["done"] if d["aid"] not in gone]
        run = self.auct.run(s.get("rid"))
        if run:
            run["ids"] = [x for x in run["ids"] if x not in gone]
        self._arun_save()
        return dict(self.auction_state(), removed=len(gone))

    def auction_memo(self, aid, memo1):
        self.auct.items[aid]["memo1"] = memo1
        self.auct.save()
        return True

    def auction_detail(self, aid):
        a = self.auct.items[aid]
        d = AU.detail(a, self.auct.result(aid))
        d["linked"] = [x for x in self.auction_list() if x["id"] == aid][0]["linked"] if not a.get("archived") else []
        return d

    def auction_export(self, ids):
        rows_sum, rows_doc, rows_dlvr, rows_date = [], [], [], []
        for aid in ids:
            a = self.auct.items.get(aid)
            if not a:
                continue
            d = AU.detail(a, self.auct.result(aid))
            s = a.get("next_sale") or {}
            rows_sum.append([a["case_no"], a["court"], a.get("csNm", ""), a.get("claim", ""), a.get("debtor", ""), a.get("status", ""),
                             " ".join(x for x in (s.get("date"), s.get("time")) if x), s.get("price", ""),
                             (a.get("last_doc") or {}).get("date", ""), (a.get("last_doc") or {}).get("text", ""), a.get("new_docs", 0),
                             a.get("memo1", ""), a.get("last_checked", "")])
            rows_doc += [[a["case_no"], x["date"], x["who"], x["text"], x["result"], "새로" if x["new"] else ""] for x in d["docs"]]
            rows_dlvr += [[a["case_no"], x["date"], x["text"], x["result"], "새로" if x["new"] else ""] for x in d["dlvr"]]
            rows_date += [[a["case_no"], x["seq"], x["time"], x["kind"], x["place"], x["eval"], x["min"], x["result"]] for x in d["dates"]]
        wb = excel._wb()
        excel._sheet(wb, "경매 사건", ["사건번호", "법원", "사건명", "청구금액", "채무자", "진행", "다음 매각기일", "최저매각가격",
                                     "최근 문건·송달일", "최근 문건·송달", "새 문건·송달", "메모", "마지막 조회"], rows_sum, first=True)
        excel._sheet(wb, "문건처리내역", ["사건번호", "접수일", "구분", "접수내역", "결과", "이번에 새로"], rows_doc, widths={"접수내역": 60})
        excel._sheet(wb, "송달내역", ["사건번호", "송달일", "송달내역", "송달결과", "이번에 새로"], rows_dlvr, widths={"송달내역": 60})
        excel._sheet(wb, "기일내역", ["사건번호", "물건번호", "기일", "기일종류", "장소", "감정평가액", "최저매각가격", "결과"], rows_date)
        path = excel.unique_path(self.export_dir(), f"{self.book} 경매사건_{dt.date.today():%y%m%d}")
        wb.save(path)
        self.reveal(path)
        return path

    # ------------------------------------------------------------ 법원경매정보 창

    def _auction_window(self):
        if self.awin:
            return self.awin
        if self.mode != "app" or not self.window:
            raise ValueError("법원경매정보 창은 프로그램 창에서만 열 수 있어요 (브라우저 모드에서는 안 돼요)")
        import webview
        w = webview.create_window("법원경매정보 — 종합관리", AU.SEARCH_URL, width=1180, height=900, text_select=True)

        def loaded():
            try:
                w.evaluate_js(AU.HOOK_JS)  # 채우기·검색은 auction_state 가 화면 준비를 확인하고 한다
            except Exception:
                pass

        def closed():
            self.awin = None
            if self.asess and self.asess.get("phase") != "finished":
                self.asess["phase"] = "closed"
        w.events.loaded += loaded
        w.events.closed += closed
        self.awin = w
        return w

    def auction_window(self):
        self._auction_window()
        return True

    def auction_start(self, ids=None, rid=None):
        items = self.auct.items
        if rid:  # 멈췄던 경매 조회 이어서
            run = self.auct.run(rid)
            if not run:
                raise ValueError("경매 조회 기록을 찾지 못했어요")
            done_ids = {d["aid"] for d in run["done"]}
            ids = [i for i in run["ids"] if i in items and i not in done_ids]
            run["finished"] = ""
        else:
            ids = [i for i in (ids or [a["id"] for a in items.values() if not a.get("archived")]) if i in items]
            run = None
        if not ids:
            raise ValueError("조회할 경매 사건이 없어요")
        run = run or self.auct.new_run(ids, "전체 경매 조회" if len(ids) == sum(1 for a in items.values() if not a.get("archived")) else "고른 경매 조회")
        self.asess = {"ids": ids, "idx": 0, "phase": "load", "read": 0, "caps": [], "t": time.time(), "done": list(run["done"]),
                      "msg": "", "tabs": False, "started": time.time(), "how": "open", "rid": run["id"]}
        fresh = self.awin is None
        self._auction_window()
        self._auction_go(first=fresh)
        return self.auction_state()

    def _auction_go(self, first=False, reload=False):
        """다음 사건으로: 결과 화면에서 사이트 안의 처음 검색 화면으로 돌아간다 (새로 고침·창 다시 열기 없이)."""
        s = self.asess
        s.update(phase="load", read=0, caps=[], tabs=False, msg="", t=time.time(), searched=0.0)
        w = self._auction_window()
        try:  # 창 제목에 진행 표시
            a = self.auct.items[s["ids"][s["idx"]]]
            w.set_title(f"법원경매정보 — {s['idx'] + 1}/{len(s['ids'])} {a['case_no']} · 종합관리")
        except Exception:
            pass
        if first:
            s["how"] = "open"  # 창을 막 열었으면 그 화면이 뜨기를 기다린다
            return
        if not reload:
            try:
                if str(w.evaluate_js(AU.BACK_JS)).startswith("back"):
                    s["how"] = "back"
                    return
            except Exception:
                pass
        s["how"] = "reload"
        try:  # 같은 주소면 새로 고침이 안 될 수 있어 주소 끝을 바꿔서 연다
            w.load_url(AU.SEARCH_URL + f"&_t={int(time.time() * 1000)}")
        except Exception:
            pass

    def _auction_fill(self):
        s = self.asess
        a = self.auct.items[s["ids"][s["idx"]]]
        press = self.store.settings.get("auction", {}).get("auto_search", True)
        try:
            ready = json.loads(self.awin.evaluate_js(AU.READY_JS) or "{}")
        except Exception:
            ready = {}
        if not ready.get("ready"):
            s["last_ready"] = ready
            return False
        try:
            if not ready.get("hook"):
                self.awin.evaluate_js(AU.HOOK_JS)
            r = str(self.awin.evaluate_js(AU.fill_js(a["court_code"], a["year"], a["serial"], press=press)))
        except Exception:
            return False
        if r != "filled":
            return False
        s.update(phase="wait", read=0, caps=[], t=time.time(), searched=time.time() if press else 0.0)
        return True

    def auction_state(self):
        s = self.asess
        if not s:
            return {"active": False}
        cfg = self.store.settings.get("auction", {})
        if s["idx"] >= len(s["ids"]):
            s["phase"] = "finished"
        elif self.awin and s["phase"] == "load":
            if not self._auction_fill():
                waited = time.time() - s["t"]
                if s.get("how") == "back" and waited > 8:  # 사이트 안에서 돌아가기가 안 되면 새로 열기
                    self._auction_go(reload=True)
                elif waited > 40 and not s.get("logged"):
                    s["logged"] = True
                    lr = s.get("last_ready") or {}
                    log_event("경매 검색 화면 준비 안 됨", lr)
                    s["msg"] = ("법원경매정보 검색 화면의 모양이 바뀐 것 같아요 (검색칸을 찾지 못함) · 「다시 시도」 해 보고, 계속 안 되면 진단 기록을 담당자에게 보내 주세요"
                                if lr.get("src") else "법원경매정보 화면이 뜨지 않아요 · 「다시 시도」를 눌러 주세요")
        elif self.awin and s["phase"] in ("wait", "tabs"):
            try:
                raw = self.awin.evaluate_js(AU.READ_JS % s["read"])
                info = json.loads(raw) if isinstance(raw, str) else (raw or {})
            except Exception:
                info = {}
            if info.get("l"):
                s["caps"] += info["l"]
                s["read"] += len(info["l"])
            if info and not info.get("h"):  # 사이트가 새로 고쳐져 자료 읽기가 사라짐 → 다시 채우기부터
                s["phase"], s["t"], s["how"] = "load", time.time(), "open"
            got = AU.digest(s["caps"])
            aid = s["ids"][s["idx"]]
            if s["caps"] and not (got["gnrl"] or got["notfound"] or got["robot"] or got["dates"] or got["docs"]) and not s.get("logged"):
                s["logged"] = True  # 받은 자료 모양이 예상과 다름 → 사이트가 바뀐 것
                log_event("경매 응답 모양이 다름", [c.get("t", "")[:1500] for c in s["caps"][:3]])
                s["msg"] = "법원경매정보 응답 모양이 바뀐 것 같아요 · 진단 기록을 담당자에게 보내 주세요"
            if got["robot"]:
                s["phase"], s["msg"] = "robot", got["robot"]
            elif got["notfound"] and not got["gnrl"]:
                a = self.auct.items[aid]
                a["last_result"], a["last_checked"] = "notfound", now()
                self.auct.save()
                s["done"].append({"aid": aid, "state": "notfound", "msg": got["notfound"]})
                self._arun_save()
                s["phase"], s["msg"], s["t"] = "saved", got["notfound"], time.time()
            elif got["gnrl"]:
                if not s["tabs"] and cfg.get("auto_tabs", True):
                    s["tabs"] = True
                    s["phase"] = "tabs"
                    try:
                        self.awin.evaluate_js(AU.TABS_JS)
                    except Exception:
                        pass
                if got["dates"] is not None and got["docs"] is not None:
                    new = self.auct.record(aid, got)
                    s["done"].append({"aid": aid, "state": "ok", "new": new})
                    self._arun_save()
                    s["phase"], s["msg"], s["t"] = "saved", "", time.time()
                elif time.time() - s["t"] > 25 and s["phase"] == "tabs":
                    s["msg"] = "기일내역·문건/송달내역 탭이 안 열리면 법원경매정보 창에서 직접 눌러 주세요"
            elif s.get("searched") and time.time() - s["searched"] > 15:
                s["msg"] = "결과가 안 나오면 법원경매정보 창에서 「검색」을 직접 눌러 주세요"
        if s["phase"] == "saved" and cfg.get("auto_next", True) and time.time() - s["t"] >= float(cfg.get("delay", 5) or 0):
            s["idx"] += 1
            if s["idx"] < len(s["ids"]):
                self._auction_go()
            else:
                s["phase"] = "finished"
                self._arun_save(finished=True)
        cur = self.auct.items.get(s["ids"][s["idx"]]) if s["idx"] < len(s["ids"]) else None
        got = AU.digest(s["caps"]) if cur else {}
        return {"active": True, "phase": s["phase"], "msg": s["msg"], "idx": s["idx"], "total": len(s["ids"]),
                "window": bool(self.awin), "current": cur and {"id": cur["id"], "case_no": cur["case_no"], "court": cur["court"]},
                "parts": {"gnrl": bool(got.get("gnrl")), "dates": got.get("dates") is not None, "docs": got.get("docs") is not None},
                "done": [dict(d, case_no=self.auct.items[d["aid"]]["case_no"]) for d in s["done"]][-50:],
                "auto_search": bool(cfg.get("auto_search", True)),
                "wait": max(0, round(float(cfg.get("delay", 5) or 0) - (time.time() - s["t"]))) if s["phase"] == "saved" else 0}

    def auction_next(self, skip=False):
        s = self.asess
        if not s:
            return {"active": False}
        if skip and s["idx"] < len(s["ids"]):
            s["done"].append({"aid": s["ids"][s["idx"]], "state": "skip"})
            self._arun_save()
        s["idx"] += 1
        if s["idx"] < len(s["ids"]):
            self._auction_go()
        return self.auction_state()

    def auction_retry(self):
        if self.asess and self.asess["idx"] < len(self.asess["ids"]):
            self._auction_go(first=self.awin is None)
        return self.auction_state()

    def auction_stop(self):
        if self.asess:
            self._arun_save(finished=self.asess["idx"] >= len(self.asess["ids"]))
        self.asess = None
        return True

    def _arun_save(self, finished=False):
        s = self.asess
        run = self.auct.run(s.get("rid")) if s else None
        if not run:
            return
        run["done"] = list(s["done"])
        if finished:
            run["finished"] = now()
        self.auct.save_runs()

    def auction_runs(self):
        out = []
        for r in self.auct.runs:
            out.append({"id": r["id"], "name": r["name"], "created": r["created"], "finished": r.get("finished", ""),
                        "total": len(r["ids"]), "done": len(r["done"]), "kind": "경매",
                        "changed": sum(1 for d in r["done"] if d.get("new")), "notfound": sum(1 for d in r["done"] if d["state"] == "notfound"),
                        "running": bool(self.asess and self.asess.get("rid") == r["id"])})
        return out
