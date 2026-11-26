# -*- coding: utf-8 -*-
"""법조치: 채무자 원장 · 서류 작성 · 송달·주소보정 · 회생·파산 · 집행 대상 · 배당 예상 · 기준표"""
import copy
import datetime as dt
import json
import os
import re
import uuid

from core import excel
from core import legal as L
from core import legal_docs as LD
from core.legal_store import STAGES, LegalStore, now
from core.rules import row_text, ymd
from core.store import Store
from core.caseno import CourtNames, parse_case_no

D_FIELDS = [
    ("name", "채무자", ["채무자", "채무자명", "성명", "이름", "고객명", "차주", "차주명"]),
    ("birth", "생년월일", ["생년월일", "생년", "주민번호", "주민등록번호", "실명번호"]),
    ("key", "계좌·고객번호", ["계좌번호", "계좌", "고객번호", "대출번호", "채권번호", "가상계좌", "관리번호"]),
    ("principal", "원금", ["원금", "대출원금", "채권원금", "잔액", "대출잔액"]),
    ("interest", "이자", ["미수이자", "이자", "연체이자", "미수금"]),
    ("addr", "주소", ["주소", "주민등록주소", "거주지", "송달주소"]),
    ("sihyo", "시효 완성일", ["시효완성일", "완성일", "소멸시효", "시효"]),
    ("default_date", "기한이익 상실일", ["기한이익상실일", "기한이익", "상실일", "연체시작일"]),
    ("rate", "연체이율(%)", ["연체이율", "지연이율", "이율", "금리"]),
    ("contract_date", "대출일", ["대출일", "약정일", "계약일", "실행일"]),
    ("court", "관할 법원", ["관할법원", "관할", "법원"]),
]
NUM = ("principal", "interest")
DATE = ("sihyo", "default_date", "contract_date")


def _num(v):
    s = re.sub(r"[^\d.\-]", "", str(v or ""))
    try:
        return float(s) if s else 0
    except ValueError:
        return 0


def _date(v):
    s = str(v or "").strip()
    m = re.match(r"(\d{4})[.\-/년\s]*(\d{1,2})[.\-/월\s]*(\d{1,2})", s)
    if m:
        try:
            return dt.date(int(m[1]), int(m[2]), int(m[3])).isoformat()
        except ValueError:
            return ""
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", s)
    if m:
        try:
            return dt.date(int(m[1]), int(m[2]), int(m[3])).isoformat()
        except ValueError:
            return ""
    return ""


def _birth(v):
    """주민번호가 와도 앞 6자리(생년월일)만 남긴다"""
    d = L.digits(v)
    return d[:6] if len(d) >= 6 else d


class LegalMixin:
    # ------------------------------------------------------------ 자료 열기

    @property
    def legal(self):
        root = self.store.root
        if getattr(self, "_legal", None) is None or self._legal.root != root:
            self._legal = LegalStore(root)
        return self._legal

    def _std(self):
        p = os.path.join(self.data_dir, "standards.json")
        saved = None
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    saved = json.load(f)
            except Exception:
                saved = None
        return L.merge_standards(saved)

    def _std_save(self, std, text):
        p = os.path.join(self.data_dir, "standards.json")
        lp = os.path.join(self.data_dir, "standards_log.json")
        before = self._std()
        log = []
        if os.path.isfile(lp):
            try:
                with open(lp, encoding="utf-8") as f:
                    log = json.load(f)
            except Exception:
                log = []
        log.insert(0, {"at": now(), "by": self._me(), "text": text, "before": before})
        with open(p, "w", encoding="utf-8") as f:
            json.dump(std, f, ensure_ascii=False, indent=1)
        with open(lp, "w", encoding="utf-8") as f:
            json.dump(log[:50], f, ensure_ascii=False)
        self.legal.rev += 1

    def _me(self):
        return self.store.settings.get("me") or os.environ.get("USERNAME", "")

    def _lset(self):
        return self.store.settings.get("legal") or {}

    # ------------------------------------------------------------ 원장 · 연결

    def _rehab_of(self, did):
        """이 채무자의 법조치를 멈춰야 하는 회생·파산 (정지·금지·회수 불가)"""
        return [r for r in self.legal.data["rehab"].values() if r.get("did") == did and not r.get("closed")
                and (r.get("code") or self._rstatus(r)["code"]) in L.BLOCKING]

    def _linked(self, d):
        key, out = L.digits(d.get("key")), []
        by = self._link("case_debtor")["by"]
        for c in self.store.active_cases():
            if ("key" in by and key and L.digits(c.get("memo1")) == key) or ("name" in by and d.get("name") and c.get("party") == d.get("name")):
                out.append(c)
        return out

    def _stage(self, d, linked=None, stop=None):
        stop = self._rehab_of(d["id"]) if stop is None else stop
        if stop:
            return "회생·파산"
        linked = self._linked(d) if linked is None else linked
        order = {s: i for i, s in enumerate(STAGES)}
        best = d.get("stage") or "준비"
        for c in linked:
            kind = L.case_kind(c.get("dvs"))
            st = c.get("status") or ""
            got = "집행" if kind in ("채권압류", "경매") else "확정" if st == "확정" else "종결" if st == "종결" else \
                  "독촉" if kind == "지급명령" else "소송" if kind == "소송" else "준비"
            if order[got] > order[best]:
                best = got
        return best

    def _flags(self, d, stage, linked):
        f = []
        if stage == "회생·파산":
            f.append(["멈춤 · 회생·파산", "red"])
        for x in self.legal.data["dlv"].values():
            due = self._dlv_due(x) if not x.get("done") and (x.get("cid") in {c["id"] for c in linked} or x.get("did") == d["id"]) else None
            if due:
                f.append([f"보정 {due['due'][5:].replace('-', '.')}", "orange"])
        if stage == "준비" and d.get("sihyo"):
            left = (dt.date.fromisoformat(d["sihyo"]) - dt.date.today()).days
            if left <= 90:
                f.append([f"시효 {left}일" if left >= 0 else "시효 지남", "red" if left <= 30 else "orange"])
        if not d.get("addr"):
            f.append(["주소 없음", "gray"])
        return f

    def _dview(self, d):
        linked = self._linked(d)
        stage = self._stage(d, linked)
        return dict(d, stage_view=stage, claim=_num(d.get("principal")) + _num(d.get("interest")),
                    flags=self._flags(d, stage, linked), cases=[{"id": c["id"], "case_no": self.store.case_no(c), "kind": L.case_kind(c.get("dvs")),
                                                                 "status": c.get("status") or "조회 전", "color": c.get("color", "gray"),
                                                                 "last": (c.get("last_prog") or {}).get("text", "")} for c in linked],
                    log=(d.get("log") or [])[:8], assets_n=len(d.get("assets") or []))

    def lg_debtors(self, q="", flt="전체", archived=False):
        out = []
        for d in self.legal.debtors.values():
            if bool(d.get("archived")) != bool(archived):
                continue
            if q and q not in (d.get("name", "") + L.digits(d.get("key")) + d.get("key", "")):
                continue
            v = self._dview(d)
            v.pop("log", None)
            if flt == "할 일" and not v["flags"]:
                continue
            if flt == "멈춤" and v["stage_view"] != "회생·파산":
                continue
            if flt in STAGES and flt != "회생·파산" and v["stage_view"] != flt:
                continue
            out.append(v)
        out.sort(key=lambda v: (0 if v["flags"] else 1, v.get("name", "")))
        return {"items": out, "stages": STAGES, "total": len(self.legal.active_debtors())}

    def lg_debtor(self, did):
        d = self.legal.debtor(did)
        if not d:
            raise ValueError("채무자를 찾지 못했어요")
        v = self._dview(d)
        v["rehab"] = self._rehab_of(did)
        v["dlv"] = [x for x in self.legal.data["dlv"].values() if x.get("cid") in {c["id"] for c in v["cases"]}]
        return v

    def lg_debtor_save(self, data):
        f = {k: data.get(k) for k, _, _ in D_FIELDS if k in data}
        f.update({k: data[k] for k in ("id", "memo", "stage", "title_no") if k in data})
        if not (f.get("name") or "").strip() and not data.get("id"):
            raise ValueError("채무자 이름을 넣어 주세요")
        for k in NUM:
            if k in f:
                f[k] = _num(f[k])
        for k in DATE:
            if k in f and f[k]:
                f[k] = _date(f[k]) or f[k]
        if "birth" in f:
            f["birth"] = _birth(f["birth"])
        if f.get("addr") and data.get("id"):
            old = (self.legal.debtor(data["id"]) or {}).get("addr")
            if old and old != f["addr"]:
                f["addr_changed"] = L.today()
        d, new = self.legal.upsert_debtor(f, self._me())
        if not new:
            self.legal.log(d, "정보 고침", self._me())
        self.legal.save()
        return d["id"]

    def lg_debtor_archive(self, ids, archived=True):
        for i in ids:
            if i in self.legal.debtors:
                self.legal.debtors[i]["archived"] = bool(archived)
        self.legal.save()
        return len(ids)

    # ------------------------------------------------------------ 원장 엑셀 불러오기

    def _d_guess(self, header):
        used, out = set(), {}
        for key, _, words in D_FIELDS:
            for w in words:
                for j, h in enumerate(header):
                    hn = re.sub(r"\s+", "", h or "")
                    if j in used or not hn:
                        continue
                    if hn == w or (len(w) >= 2 and w in hn):
                        out[key] = j
                        used.add(j)
                        break
                if key in out:
                    break
        return out

    def lg_import_preview(self, path, mapping=None):
        _, rows = excel.read_table(path)
        hi = excel.find_header(rows)
        header, body = rows[hi] if rows else [], [r for r in rows[hi + 1:] if any(r)]
        auto, src = self._xl_auto("debtor", header, self._d_guess(header))
        m = {k: int(v) for k, v in (mapping or {}).items() if v not in (None, "", -1, "-1")} if mapping else auto
        order = self._link("debtor")["by"]
        new = upd = bad = by_name = 0
        sample = []
        for r in body:
            g = lambda k: (r[m[k]] if k in m and m[k] < len(r) else "").strip()  # noqa: E731
            name = g("name")
            if not name:
                bad += 1
                continue
            d, how = self.legal.match_debtor(g("key"), name, _birth(g("birth")), order)
            if d:
                upd += 1
                by_name += how == "name"
            else:
                new += 1
            if len(sample) < 6:
                sample.append({k: g(k) for k, _, _ in D_FIELDS})
        return {"path": path, "name": os.path.basename(path), "header": header, "auto": auto, "mapping": m, "src": src if not mapping else {},
                "fields": [[k, t] for k, t, _ in D_FIELDS], "new": new, "update": upd, "skip": bad, "sample": sample, "rows": len(body), "by_name": by_name}

    def lg_import_apply(self, path, mapping=None):
        p = self.lg_import_preview(path, mapping)
        m = p["mapping"]
        _, rows = excel.read_table(path)
        hi = excel.find_header(rows)
        self._xl_save("debtor", p["header"], m)
        order = self._link("debtor")["by"]
        n = 0
        for r in rows[hi + 1:]:
            if not any(r):
                continue
            data = {k: (r[m[k]] if m[k] < len(r) else "").strip() for k in m}
            if not data.get("name"):
                continue
            for k in NUM:
                if k in data:
                    data[k] = _num(data[k])
            for k in DATE:
                if k in data:
                    data[k] = _date(data[k])
            if "birth" in data:
                data["birth"] = _birth(data["birth"])
            if "rate" in data:
                data["rate"] = re.sub(r"[^\d.]", "", data["rate"])
            data = {k: v for k, v in data.items() if v not in ("", None)}
            self.legal.upsert_debtor(data, self._me(), order)
            n += 1
        self.legal.save()
        self._act(f"채무자 원장에 엑셀을 넣었어요 — {n}명 (새로 {p['new']} · 갱신 {p['update']})", "xl", "lg_debtors")
        return {"count": n, "new": p["new"], "update": p["update"]}

    def lg_template_save(self):
        wb = excel._wb()
        excel._sheet(wb, "채무자 원장", [t for _, t, _ in D_FIELDS],
                     [["홍길동", "800101", "110-123-456789", 7800000, 550000, "서울 ○○구 ○○로 12", "2027-06-30", "2025-03-15", "15", "2019-03-14", "서울중앙지방법원"]],
                     first=True)
        path = excel.unique_path(self.export_dir(), "채무자 원장 양식")
        wb.save(path)
        self.reveal(path)
        return path

    def lg_info_save(self, info):
        self.legal.data["info"] = {k: (v or "").strip() if isinstance(v, str) else v for k, v in info.items()}
        self.legal.save()
        return self.legal.data["info"]

    # ------------------------------------------------------------ 송달·주소보정 (보정 관리 대장)
    # 한 대장에 세 길로 들어온다: 사건 조회 결과에서 자동 · 엑셀 넣기 · 직접 등록.
    # 키: 자동 = 「사건|줄」(확인할 것과 같음), 엑셀·직접 = 「M|…」. 지운 자동 건은 dlv_removed에 남겨 다시 들어오지 않게.

    DLV_COLS = [("case_no", "사건번호"), ("court", "법원"), ("party", "당사자"), ("kind", "사건 종류"), ("doc", "송달 서류"),
                ("reason", "불능 사유"), ("date", "불능일"), ("recv", "보정명령 받은 날"), ("days", "보정 기간(일)"), ("due", "기한"),
                ("left", "남은 날"), ("act", "조치"), ("status", "진행"), ("submit", "제출일"), ("new_addr", "새 주소"),
                ("owner", "담당"), ("memo", "메모"), ("src", "들어온 곳"), ("done", "완료일")]
    DLV_DEFAULT = ["case_no", "court", "party", "reason", "recv", "due", "left", "act", "status", "submit", "owner", "memo"]
    DLV_ALIAS = {
        "case_no": ["사건번호", "사건", "사건 번호"], "court": ["법원", "관할법원", "관할 법원", "계속법원"],
        "party": ["당사자", "채무자", "채무자명", "성명", "이름", "피고", "상대방"], "doc": ["송달서류", "송달 서류", "서류", "송달문서"],
        "reason": ["불능사유", "불능 사유", "송달결과", "사유", "송달불능사유"], "date": ["불능일", "송달일", "결과일", "송달불능일"],
        "recv": ["보정명령일", "보정명령 받은 날", "보정명령받은날", "명령일", "수령일", "보정명령수령일"], "days": ["보정기간", "보정 기간", "기간", "보정기간(일)"],
        "due": ["기한", "보정기한", "마감일", "제출기한", "보정 기한"], "act": ["조치", "처리", "처리방법", "조치방법"],
        "new_addr": ["새주소", "새 주소", "신주소", "보정주소"], "owner": ["담당", "담당자"], "memo": ["메모", "비고"],
        "submit": ["제출일", "보정일", "제출한 날"], "status": ["진행", "상태", "진행상태"],
    }
    DLV_SRC = {"auto": "사건 조회", "xl": "엑셀", "manual": "직접 등록"}

    def _dlv_sync(self):
        """사건 조회 결과에서 「송달 안 됨」 줄을 찾아 대장에 넣는다 (사건마다 가장 최근 것 하나)."""
        items, changed = self.legal.data["dlv"], False
        removed = set(self.legal.data.setdefault("dlv_removed", []))
        look = dt.date.today() - dt.timedelta(days=120)
        cnos = {re.sub(r"\s", "", x.get("case_no", "")): x for x in items.values() if x["key"].startswith("M|") and not x.get("done")}
        for c in self.store.active_cases():
            if not c.get("last_checked"):
                continue
            prog = self.store.result(c["id"]).get("prog") or []
            for r in prog:  # 최근 줄부터
                d = ymd(r.get("progYmd"))
                if not d or d < look:
                    break
                text = row_text(r)
                reason = L.dlv_reason(text)
                if not reason:
                    continue
                key = f"{c['id']}|{Store.row_key(r)}"
                cno = self.store.case_no(c)
                if key not in items and key not in removed:
                    m = cnos.get(cno)
                    if m:  # 엑셀·직접으로 먼저 넣은 같은 사건 → 사건과 잇기만
                        if not m.get("cid"):
                            m.update({"cid": c["id"], "kind": m.get("kind") or L.case_kind(c.get("dvs")), "court": m.get("court") or c.get("court", ""),
                                      "text": text, "date": m.get("date") or d.isoformat()})
                            changed = True
                        break
                    cnt = sum(1 for x in prog if L.dlv_reason(row_text(x)) == reason)
                    items[key] = {"key": key, "cid": c["id"], "case_no": cno, "court": c.get("court", ""), "party": c.get("party", ""),
                                  "kind": L.case_kind(c.get("dvs")), "reason": reason, "cnt": cnt, "date": d.isoformat(),
                                  "text": text, "recv": "", "days": int(self._lset().get("days") or 7), "act": "", "done": "",
                                  "src": "auto", "auto": True, "created": now()}
                    changed = True
                break
        for k, x in items.items():  # 확인할 것에서 처리하면 여기도
            st = self.store.todos.get(k) or {}
            if st.get("done") and not x.get("done"):
                x["done"] = st["done"]
                changed = True
        if changed:
            self.legal.save()

    def _debtor_of_case(self, cid):
        c = self.store.cases.get(cid) or {}
        k = L.digits(c.get("memo1"))
        by = self._link("case_debtor")["by"]
        if "key" in by and k:
            for d in self.legal.active_debtors():
                if L.digits(d.get("key")) == k:
                    return d
        if "name" in by and c.get("party"):
            for d in self.legal.active_debtors():
                if d.get("name") == c.get("party"):
                    return d
        return None

    def _dlv_due(self, x, std=None):
        """기한: 직접 넣은 기한이 먼저, 없으면 보정명령 받은 날 + 보정 기간 (초일 불산입, 쉬는 날이면 다음 평일)."""
        if x.get("due_set"):
            return {"due": x["due_set"], "raw": x["due_set"], "moved": False, "set": True}
        if x.get("recv"):
            try:
                return L.due_of(std or self._std(), x["recv"], x.get("days") or 7)
            except ValueError:
                return None
        return None

    def _dlv_debtor(self, x):
        d = self._debtor_of_case(x["cid"]) if x.get("cid") else None
        if not d and x.get("did"):
            d = self.legal.debtor(x["did"])
        if not d and x.get("party"):
            d = self.legal.find_debtor("", x["party"])
        return d

    @staticmethod
    def _dlv_status(x):
        return "완료" if x.get("done") else "제출함" if x.get("submit") else "조치 정함" if x.get("act") else "접수"

    def _dlv_view(self, x, std):
        d = self._dlv_debtor(x)
        new_addr = bool(x.get("new_addr")) or bool(d and d.get("addr_changed") and d["addr_changed"] >= (x.get("date") or ""))
        rec = L.recommend(x.get("kind") or "", x.get("reason") or "", x.get("cnt", 1), new_addr)
        due = self._dlv_due(x, std)
        acts = [{"name": a, "ok": L.action_allowed(x.get("kind") or "", a)[0], "why": L.action_allowed(x.get("kind") or "", a)[1]} for a in L.ACTIONS]
        sib = [y["key"] for y in self.legal.data["dlv"].values() if y["key"] != x["key"] and not y.get("done") and d and
               ((y.get("cid") and self._debtor_of_case(y["cid"]) is d) or y.get("did") == d["id"])]
        src = x.get("src") or ("auto" if x.get("cid") and x.get("auto") else "manual")
        return dict(x, rec=rec, due=due, left=(dt.date.fromisoformat(due["due"]) - dt.date.today()).days if due else None,
                    status=self._dlv_status(x), src=src, src_label=self.DLV_SRC.get(src, src),
                    debtor={"id": d["id"], "name": d["name"], "addr": d.get("addr", ""), "hist": d.get("addr_hist", []),
                            "addr_changed": d.get("addr_changed", "")} if d else None,
                    acts=acts, siblings=sib)

    def _dlv_rows(self, tab="todo", flt="", q=""):
        self._dlv_sync()
        std = self._std()
        rows = [self._dlv_view(x, std) for x in self.legal.data["dlv"].values()]
        if tab == "todo":
            rows = [r for r in rows if not r.get("done")]
        elif tab == "done":
            rows = [r for r in rows if r.get("done")]
        if flt == "over":
            rows = [r for r in rows if r["left"] is not None and r["left"] < 0]
        elif flt == "soon":
            rows = [r for r in rows if r["left"] is not None and 0 <= r["left"] <= 3]
        elif flt == "nodue":
            rows = [r for r in rows if r["left"] is None]
        if q:
            qq = re.sub(r"\s", "", q)
            rows = [r for r in rows if qq in re.sub(r"\s", "", " ".join(str(r.get(k) or "") for k in ("case_no", "party", "court", "owner", "memo", "reason", "act")))]
        rows.sort(key=lambda v: (bool(v.get("done")), v["left"] if v["left"] is not None else 999, v.get("date", "")))
        if tab == "done":
            rows.sort(key=lambda v: v.get("done") or "", reverse=True)
        return rows

    def lg_dlv(self, tab="todo", flt="", q=""):
        rows = self._dlv_rows(tab, flt, q)
        allx = [self._dlv_view(x, self._std()) for x in self.legal.data["dlv"].values()]
        op = [x for x in allx if not x.get("done")]
        cols = self._lset().get("dlv_cols") or self.DLV_DEFAULT
        return {"items": rows, "todo": len(op), "done": len(allx) - len(op), "all": len(allx), "actions": L.ACTIONS,
                "counts": {"over": sum(1 for x in op if x["left"] is not None and x["left"] < 0),
                           "soon": sum(1 for x in op if x["left"] is not None and 0 <= x["left"] <= 3),
                           "nodue": sum(1 for x in op if x["left"] is None)},
                "cols": [[k, t] for k, t in self.DLV_COLS], "cols_on": cols, "reasons": L.DLV_WORDS[:4]}

    DLV_FIELDS = ("recv", "days", "act", "court", "party", "doc", "reason", "date", "due_set", "submit", "new_addr", "owner", "memo", "case_no")

    def lg_dlv_set(self, key, field, value):
        x = self.legal.data["dlv"][key]
        if field not in self.DLV_FIELDS:
            raise ValueError("바꿀 수 없는 칸이에요")
        if field == "act" and value:
            ok, why = L.action_allowed(x.get("kind") or "", value)
            if not ok:
                raise ValueError(why)
        if field in ("recv", "date", "due_set", "submit") and value and not _date(value):
            raise ValueError("날짜를 2026-11-04 처럼 넣어 주세요")
        if field == "case_no":
            value = re.sub(r"\s", "", value or "")
            if not value:
                raise ValueError("사건번호는 비울 수 없어요")
            p = parse_case_no(value)
            x["kind"] = L.case_kind(p[1]) if p else x.get("kind", "")
        x[field] = int(value or 7) if field == "days" else _date(value) if field in ("recv", "date", "due_set", "submit") else (value or "").strip()
        self._dlv_todo(x)
        self.legal.save()
        return self._dlv_view(x, self._std())

    def _dlv_todo(self, x):
        """기한이 있으면 확인할 것·기일·기한에도 같은 키로 넣는다."""
        due = self._dlv_due(x)
        st = self.store.todos.setdefault(x["key"], {})
        if due:
            st["deadline"] = due["due"]
        else:
            st.pop("deadline", None)
        self.store.save_todos()

    def _dlv_new(self, data, src):
        cno = re.sub(r"\s", "", data.get("case_no") or "")
        if not cno:
            raise ValueError("사건번호를 넣어 주세요")
        p = parse_case_no(cno)
        c = next((c for c in self.store.active_cases() if self.store.case_no(c) == cno), None)
        key = f"M|{uuid.uuid4().hex[:8]}"
        d = self.legal.debtor(data.get("did") or "") if data.get("did") else self.legal.find_debtor("", data.get("party", ""))
        x = {"key": key, "cid": (c or {}).get("id", ""), "did": (d or {}).get("id", ""), "case_no": cno,
             "court": data.get("court") or (c or {}).get("court", ""), "party": data.get("party") or (c or {}).get("party", "") or (d or {}).get("name", ""),
             "kind": L.case_kind(p[1] if p else ""), "doc": data.get("doc", ""), "reason": data.get("reason") or "", "cnt": int(data.get("cnt") or 1),
             "date": _date(data.get("date")) or L.today(), "text": {"xl": "엑셀로 넣음", "manual": "직접 넣음"}[src], "recv": _date(data.get("recv")),
             "days": int(data.get("days") or self._lset().get("days") or 7), "due_set": _date(data.get("due_set") or data.get("due")),
             "act": data.get("act", ""), "submit": _date(data.get("submit")), "new_addr": data.get("new_addr", ""), "owner": data.get("owner") or self._me(),
             "memo": data.get("memo", ""), "done": now() if "완료" in str(data.get("status") or "") else "", "src": src, "created": now()}
        if x["act"] and not L.action_allowed(x["kind"], x["act"])[0]:
            x["act"] = ""
        self.legal.data["dlv"][key] = x
        self._dlv_todo(x)
        return x

    def lg_dlv_add(self, data):
        x = self._dlv_new(data, "manual")
        self.legal.save()
        self._act(f"{x['case_no']} 보정을 직접 등록했어요", "dlv", "lg_dlv", {"key": x["key"]})
        return x["key"]

    def lg_dlv_done(self, keys, use_rec=True, note=""):
        std, n = self._std(), 0
        for k in keys:
            x = self.legal.data["dlv"].get(k)
            if not x or x.get("done"):
                continue
            if use_rec and not x.get("act"):
                x["act"] = self._dlv_view(x, std)["rec"]
            x["done"] = now()
            st = self.store.todos.setdefault(k, {})
            st.update({"done": x["done"], "note": note or x.get("act", ""), "by": self._me()})
            d = self._dlv_debtor(x)
            if d:
                self.legal.log(d, f"{x['case_no']} {x.get('act') or '처리'} — 보정 완료", self._me())
            n += 1
        self.store.save_todos()
        self.legal.save()
        if n:
            self._act(f"보정 {n}건을 완료로 바꿨어요" + (f" — {note}" if note else ""), "dlv", "lg_dlv")
        return n

    def lg_dlv_undo(self, key):
        x = self.legal.data["dlv"][key]
        x["done"] = ""
        (self.store.todos.get(key) or {}).pop("done", None)
        self.store.save_todos()
        self.legal.save()
        return True

    def lg_dlv_delete(self, keys):
        """대장에서 지운다. 사건 조회에서 자동으로 온 건은 다시 들어오지 않게 표시해 둔다."""
        rm = self.legal.data.setdefault("dlv_removed", [])
        n = 0
        for k in keys:
            x = self.legal.data["dlv"].pop(k, None)
            if not x:
                continue
            n += 1
            if x.get("cid") and not k.startswith("M|"):
                rm.append(k)
                st = self.store.todos.setdefault(k, {})
                st.update({"done": now(), "note": "보정 관리에서 지움", "by": self._me()})
            else:
                self.store.todos.pop(k, None)
        del rm[:-500]
        self.store.save_todos()
        self.legal.save()
        if n:
            self._act(f"보정 {n}건을 대장에서 지웠어요", "dlv", "lg_dlv")
        return n

    # ── 엑셀 넣기 · 내보내기

    def _dlv_xl(self, path, mapping=None):
        _, rows = excel.read_table(path)
        hi = excel.find_header(rows)
        header, body = (rows[hi] if rows else []), [r for r in rows[hi + 1:] if any(str(v).strip() for v in r)]
        auto = {}
        for j, h in enumerate(header):
            hn = re.sub(r"\s", "", str(h))
            for k, al in self.DLV_ALIAS.items():
                if k not in auto and hn in [re.sub(r"\s", "", a) for a in al]:
                    auto[k] = j
                    break
        if "case_no" not in auto:  # 머리글이 달라도 사건번호 모양인 열을 찾는다
            for j in range(len(header)):
                vals = [str(r[j]) for r in body[:30] if j < len(r) and r[j]]
                if vals and sum(1 for v in vals if parse_case_no(re.sub(r"\s", "", v))) >= len(vals) * 0.6:
                    auto["case_no"] = j
                    break
        auto, self._dlv_src = self._xl_auto("dlv", header, auto)
        m = {k: int(v) for k, v in mapping.items() if str(v) not in ("", "-1")} if mapping else auto
        recs = []
        for r in body:
            g = {k: str(r[j]).strip() if j < len(r) and r[j] is not None else "" for k, j in m.items()}
            if not g.get("case_no"):
                continue
            g["case_no"] = re.sub(r"\s", "", g["case_no"])
            if g.get("reason"):
                g["reason"] = L.dlv_reason(g["reason"]) or g["reason"]
            if g.get("days"):
                g["days"] = L.digits(g["days"]) or ""
            recs.append(g)
        return header, auto, m, recs

    def _dlv_match(self, g):
        by = self._link("dlv")["by"]
        if by == "none":
            return None
        cno = g["case_no"]
        same = [x for x in self.legal.data["dlv"].values() if re.sub(r"\s", "", x.get("case_no", "")) == cno]
        if g.get("recv") and by == "case_recv":
            hit = next((x for x in same if x.get("recv") == _date(g["recv"])), None)
            if hit:
                return hit
        return next((x for x in same if not x.get("done")), None)

    def lg_dlv_import_preview(self, path, mapping=None):
        header, auto, m, recs = self._dlv_xl(path, mapping)
        new = upd = 0
        sample = []
        for g in recs:
            x = self._dlv_match(g)
            if x:
                upd += 1
            else:
                new += 1
            if len(sample) < 6:
                sample.append(dict(g, _upd=bool(x)))
        return {"path": path, "name": os.path.basename(path), "header": [str(h) for h in header], "auto": auto, "mapping": m,
                "src": {} if mapping else getattr(self, "_dlv_src", {}),
                "fields": [[k, t] for k, t in self.DLV_COLS if k in self.DLV_ALIAS], "new": new, "update": upd, "rows": len(recs), "sample": sample,
                "need": "case_no" not in m}

    def lg_dlv_import_apply(self, path, mapping=None, overwrite=False):
        header, auto, m, recs = self._dlv_xl(path, mapping)
        if "case_no" not in m:
            raise ValueError("사건번호 칸을 골라 주세요")
        self._xl_save("dlv", [str(h) for h in header], m)
        new = upd = 0
        for g in recs:
            x = self._dlv_match(g)
            if not x:
                self._dlv_new(g, "xl")
                new += 1
                continue
            for k, v in g.items():  # 엑셀에 값이 있는 칸만 (덮어쓰기를 켜면 이미 있는 값도 바꿈)
                if not v or k in ("case_no", "status"):
                    continue
                kk = "due_set" if k == "due" else k
                if x.get(kk) and not overwrite:
                    continue
                x[kk] = int(v) if kk == "days" else _date(v) if kk in ("recv", "date", "due_set", "submit") else v
            if "완료" in (g.get("status") or "") and not x.get("done"):
                x["done"] = now()
            self._dlv_todo(x)
            upd += 1
        self.legal.save()
        self._act(f"보정 관리에 엑셀을 넣었어요 — 새로 {new} · 갱신 {upd}", "xl", "lg_dlv")
        return {"new": new, "update": upd}

    def lg_dlv_template(self):
        wb = excel._wb()
        ks = ["case_no", "court", "party", "doc", "reason", "date", "recv", "days", "due", "act", "owner", "memo"]
        names = dict(self.DLV_COLS)
        excel._sheet(wb, "보정 관리", [names[k] for k in ks],
                     [["2026가소12345", "서울중앙지방법원", "홍길동", "소장부본", "폐문부재", "2026-10-28", "2026-11-02", 7, "", "야간·휴일 특별송달", "김담당", "초본 신청함"]],
                     first=True)
        path = excel.unique_path(self.export_dir(), "보정 관리 양식")
        wb.save(path)
        self.reveal(path)
        return path

    def lg_dlv_export(self, cols=None, tab="todo", flt="", q="", keys=None, save_cols=True):
        cols = [c for c in (cols or self._lset().get("dlv_cols") or self.DLV_DEFAULT) if c in dict(self.DLV_COLS)]
        if not cols:
            raise ValueError("내보낼 칸을 하나 이상 골라 주세요")
        if save_cols:
            self.store.set_setting("legal.dlv_cols", cols, "보정 관리 내보내기 칸")
        rows = self._dlv_rows(tab, flt, q)
        if keys:
            rows = [r for r in rows if r["key"] in keys]
        names = dict(self.DLV_COLS)

        def val(r, k):
            if k == "due":
                return r["due"]["due"] if r.get("due") else ""
            if k == "left":
                return "" if r["left"] is None else ("오늘" if r["left"] == 0 else f"D-{r['left']}" if r["left"] > 0 else f"{-r['left']}일 지남")
            if k == "src":
                return r["src_label"]
            if k == "done":
                return (r.get("done") or "")[:10]
            if k == "act":
                return r.get("act") or (f"(추천) {r['rec']}" if not r.get("done") else "")
            return r.get(k, "")
        wb = excel._wb()
        excel._sheet(wb, "보정 관리", [names[k] for k in cols], [[val(r, k) for k in cols] for r in rows], first=True)
        tag = {"todo": "처리할 것", "done": "끝난 것"}.get(tab, "전체")
        path = excel.unique_path(self.export_dir(), f"{self.store.root and os.path.basename(self.store.root) or '채권'} 보정 관리_{tag}_{dt.date.today():%Y%m%d}")
        wb.save(path)
        self.reveal(path)
        self._act(f"보정 관리 {len(rows)}건을 엑셀로 내보냈어요", "dlv", "lg_dlv")
        return {"path": path, "count": len(rows)}

    # ------------------------------------------------------------ 회생·파산 (관리 가부 추적)
    # 사건 대장의 회생·파산 사건(개회·하단·하면 …)은 조회할 때마다 관리 가부가 다시 계산된다.
    # 받은 문서만 등록한 것은 사건번호·법원이 있으면 사건 대장에도 넣어 같은 방법으로 조회한다.

    KIND_OF = {"개인회생": "개인회생", "파산": "파산·면책", "면책": "파산·면책", "회생": "법인회생"}
    STAGE_OF = {"금지·중지명령": 1, "개시결정": 2, "계획 인가": 4, "면책결정": 6, "파산선고": 1, "면책신청": 3}

    def _rcase(self, r):
        c = self.store.cases.get(r.get("cid") or "")
        return c if c and not c.get("archived") else None

    def _rstatus(self, r):
        c = self._rcase(r)
        if c and c.get("rehab"):
            return c["rehab"]
        dvs = (c or {}).get("dvs") or (parse_case_no(r.get("no") or "") or (0, ""))[1]
        return L.rehab_status(dvs, [], {}, doc=r.get("doc", ""))

    def _rehab_sync(self):
        """사건 대장의 회생·파산 사건을 추적 목록에 넣고, 관리 가부가 바뀌었으면 알린다."""
        items, changed = self.legal.data["rehab"], False
        by_cid = {r.get("cid"): r for r in items.values() if r.get("cid")}
        for c in self.store.active_cases():
            kind = L.rehab_kind(c.get("dvs"))
            if not kind:
                continue
            r = by_cid.get(c["id"])
            if not r:  # 등록만 한 것과 사건번호가 같으면 잇는다
                cno = self.store.case_no(c)
                r = next((x for x in items.values() if not x.get("cid") and re.sub(r"\s", "", x.get("no", "")) == cno), None)
                if r:
                    r["cid"] = c["id"]
                else:
                    d = self._debtor_of_case(c["id"])
                    rid = "r" + uuid.uuid4().hex[:8]
                    r = items[rid] = {"id": rid, "cid": c["id"], "did": d["id"] if d else "", "name": c.get("party", ""),
                                      "kind": self.KIND_OF.get(kind, "개인회생"), "no": cno, "court": c.get("court", ""), "stage": 0,
                                      "got": L.today(), "doc": "사건 조회", "created": now(), "log": [], "stop_ok": True}
                changed = True
        for r in items.values():
            if r.get("closed"):
                continue
            m = self._rstatus(r)
            if r.get("code") != m["code"]:
                old = r.get("code")
                if old:  # 처음이 아니면 바뀐 것을 알린다
                    r["change"] = {"from": old, "to": m["code"], "at": now(), "event": m["event"]}
                    r.setdefault("log", []).insert(0, {"at": now(), "text": f"관리 가부 {L.MANAGE[old][0]} → {m['label']} ({m['event']})"})
                if m["code"] in ("stop", "ban") and old not in ("stop", "ban"):
                    r["stop_ok"] = not self._rview_live(r)
                r["code"] = m["code"]
                changed = True
            st = self.STAGE_OF.get(m["event"])
            if st is not None and st > int(r.get("stage") or 0) and st < len(L.FLOW[r["kind"]]):
                r["stage"] = st
                changed = True
        if changed:
            self.legal.save()

    def _rview_live(self, r):
        d = self.legal.debtor(r.get("did") or "") or {}
        if not d:
            return []
        live = [c for c in self._linked(d) if L.case_kind(c.get("dvs")) in ("지급명령", "소송", "채권압류", "경매")
                and (c.get("status") or "") not in ("종결", "확정")]
        out = [{"case_no": self.store.case_no(c), "kind": L.case_kind(c.get("dvs")), "status": c.get("status") or "진행"} for c in live]
        out += [{"case_no": x["case_no"], "kind": "송달 처리", "status": "보정 진행"} for x in self.legal.data["dlv"].values()
                if not x.get("done") and x.get("cid") and self._debtor_of_case(x["cid"]) is d]
        return out

    def _rview(self, r):
        d = self.legal.debtor(r.get("did") or "") or {}
        c = self._rcase(r)
        m = self._rstatus(r)
        flow = L.FLOW[r["kind"]]
        return dict(r, debtor={"id": d.get("id"), "name": d.get("name") or r.get("name") or (c or {}).get("party", ""),
                               "birth": d.get("birth") or r.get("birth", ""), "claim": _num(d.get("principal")) + _num(d.get("interest"))},
                    m=m, case={"id": c["id"], "checked": c.get("last_checked", ""), "last": (c.get("last_prog") or {}),
                               "party": c.get("party", "")} if c else None,
                    flow=flow, stage_name=flow[min(r.get("stage", 0), len(flow) - 1)],
                    actions=[a for a in L.rehab_action(r["kind"], r.get("stage", 0)) if a != "다음 단계로"],
                    live=self._rview_live(r) if m["code"] in L.BLOCKING else [],
                    left=(dt.date.fromisoformat(r["due"]) - dt.date.today()).days if r.get("due") else None)

    def lg_rehab(self, closed=False, flt="", q=""):
        self._rehab_sync()
        allv = [self._rview(r) for r in self.legal.data["rehab"].values() if bool(r.get("closed")) == bool(closed)]
        counts = {k: sum(1 for v in allv if v["m"]["code"] == k) for k in L.MANAGE}
        items = [v for v in allv if (not flt or v["m"]["code"] == flt)
                 and (not q or q in (v["debtor"]["name"] + v.get("no", "") + v.get("court", "")))]
        order = {"stop": 0, "ban": 1, "warn": 2, "ok": 3, "end": 4}
        items.sort(key=lambda v: (bool(v.get("stop_ok")), not v.get("change"), order[v["m"]["code"]], v["left"] if v["left"] is not None else 999))
        stale = [v["cid"] for v in allv if v.get("cid") and self._rcase(v) and (not v["case"]["checked"] or v["case"]["checked"][:10]
                 <= (dt.date.today() - dt.timedelta(days=int(self._lset().get("rehab_days") or 30))).isoformat())]
        return {"items": items, "counts": counts, "total": len(allv), "manage": {k: list(v) for k, v in L.MANAGE.items()},
                "kinds": list(L.FLOW), "docs": list(L.DOC_STAGE), "stale": stale, "stale_days": int(self._lset().get("rehab_days") or 30),
                "blocking": [v["cid"] for v in allv if v.get("cid") and v["m"]["code"] in ("stop", "ban", "warn")],
                "all_ids": [v["cid"] for v in allv if v.get("cid") and self._rcase(v)],
                "candidates": [{"id": d["id"], "name": d["name"], "birth": d.get("birth", ""), "key": d.get("key", ""),
                                "stage": self._stage(d)} for d in self.legal.active_debtors() if not self._rehab_of(d["id"])]}

    def lg_rehab_search(self, text, keep=True):
        """회생·파산 사건만 골라 바로 조회 (사건 조회와 같은 순서: 숫자 입력 → 바로 조회)"""
        good, bad = self.quick_parse(text)
        not_rehab = [g for g in good if not L.rehab_kind(g["dvs"])]
        good = [g for g in good if L.rehab_kind(g["dvs"])]
        bad += [{"line": 0, "text": f"{g['year']}{g['dvs']}{g['serial']}", "problem": "회생·파산 사건번호가 아니에요 (개회·하단·하면·회단 등)"} for g in not_rehab]
        if not good:
            raise ValueError(bad[0]["problem"] if bad else "조회할 사건을 넣어 주세요")
        lines = "\n".join(f"{g['court']}\t{g['year']}{g['dvs']}{g['serial']}\t{g['party']}" for g in good)
        st = self.quick_search(lines, keep=keep)
        self._rehab_sync()
        st["skipped"] = bad
        return st

    def lg_rehab_recheck(self, scope="blocking"):
        """추적 중인 회생·파산 사건을 다시 조회: blocking(정지·금지·주의) / stale(오래 안 본 것) / all"""
        d = self.lg_rehab()
        ids = {"blocking": d["blocking"], "stale": d["stale"], "all": d["all_ids"]}.get(scope) or []
        if not ids:
            raise ValueError("다시 조회할 회생·파산 사건이 없어요")
        return self.run_start(name={"blocking": "회생·파산 확인 (정지·금지·주의)", "stale": "회생·파산 확인 (오래 안 본 것)",
                                    "all": "회생·파산 전체 확인"}[scope], case_ids=ids)

    def lg_rehab_register(self, data):
        did = data.get("did") or ""
        if not did:
            if not (data.get("name") or "").strip():
                raise ValueError("채무자를 고르거나 이름을 넣어 주세요")
            d, _ = self.legal.upsert_debtor({"name": data["name"].strip(), "birth": _birth(data.get("birth"))}, self._me())
            did = d["id"]
        d = self.legal.debtor(did)
        doc = data.get("doc") or "금지명령"
        kind = data.get("kind") or L.DOC_STAGE.get(doc, ("개인회생", 0))[0] or "개인회생"
        stage = L.DOC_STAGE.get(doc, (None, 0))[1] if L.DOC_STAGE.get(doc, (None,))[0] in (kind, None) else 0
        no = re.sub(r"\s", "", data.get("no") or "")
        cid = ""
        if no and (data.get("court") or "").strip() and parse_case_no(no) and L.rehab_kind(parse_case_no(no)[1]):
            try:  # 사건 대장에도 넣어 「사건 조회」로 관리 가부를 확인할 수 있게
                cid = self.case_save({"court": data["court"], "case_no": no, "party": d.get("name", ""), "memo1": d.get("key", "")})
            except ValueError as ex:
                if "이미" in str(ex):
                    p = parse_case_no(no)
                    names = CourtNames(self.meta.court_names(), self.store.settings.get("aliases"))
                    court = names.match(data["court"])[0]
                    cid = self.store.find_key(self.store.key_of(court, *p)) or ""
        rid = "r" + uuid.uuid4().hex[:8]
        r = {"id": rid, "did": did, "cid": cid, "kind": kind, "no": no, "court": (data.get("court") or "").strip(),
             "stage": min(stage, len(L.FLOW[kind]) - 1), "got": data.get("got") or L.today(), "doc": doc, "due": data.get("due", ""),
             "list_amt": _num(data.get("list_amt")), "created": now(), "check": not no, "log": []}
        self.legal.data["rehab"][rid] = r
        r["code"] = self._rstatus(r)["code"]
        r["stop_ok"] = not self._rview_live(r)
        self.legal.log(d, f"{doc} 등록 ({kind} {r['no']}) → {L.MANAGE[r['code']][0]}", self._me())
        self.legal.save()
        return rid

    RP_FIELDS = [("name", "성명"), ("birth", "생년월일"), ("kind", "등록 사유"), ("date", "등록일"), ("no", "사건번호")]

    def lg_rehab_public_preview(self, path, mapping=None):
        """신용정보 공공정보(회생·파산 등재) 엑셀 → 원장과 맞추기"""
        _, rows = excel.read_table(path)
        hi = excel.find_header(rows)
        header = rows[hi] if rows else []
        idx = lambda *ws: next((j for j, h in enumerate(header) for w in ws if w in re.sub(r"\s+", "", h or "")), None)  # noqa: E731
        auto = {k: j for k, j in zip(("name", "birth", "kind", "date", "no"), (idx("성명", "이름", "채무자", "고객명"), idx("생년", "주민"),
                idx("등록사유", "구분", "종류", "사유"), idx("등록일", "발생일", "일자"), idx("사건번호"))) if j is not None}
        auto, src = self._xl_auto("rehab", [str(h) for h in header], auto)
        m = {k: int(v) for k, v in mapping.items() if str(v) not in ("", "-1")} if mapping is not None else auto
        jn, jb, jk, jd, jno = (m.get(k) for k in ("name", "birth", "kind", "date", "no"))
        order = self._link("rehab")["by"]
        out = []
        for r in rows[hi + 1:]:
            if jn is None or jn >= len(r) or not r[jn].strip():
                continue
            name, birth = r[jn].strip(), _birth(r[jb]) if jb is not None and jb < len(r) else ""
            d = self.legal.find_debtor("", name, birth, order)
            kindtxt = r[jk] if jk is not None and jk < len(r) else ""
            kind = "파산·면책" if ("파산" in kindtxt or "면책" in kindtxt) else "법인회생" if "법인" in kindtxt else "개인회생"
            out.append({"name": name, "birth": birth, "kind": kind, "kindtxt": kindtxt, "did": d["id"] if d else "",
                        "date": _date(r[jd]) if jd is not None and jd < len(r) else "", "no": r[jno].strip() if jno is not None and jno < len(r) else "",
                        "already": bool(d and any(x.get("did") == d["id"] and not x.get("closed") for x in self.legal.data["rehab"].values()))})
        return {"path": path, "rows": out, "matched": sum(1 for x in out if x["did"] and not x["already"]), "header": [str(h) for h in header],
                "mapping": m, "auto": auto, "src": src if mapping is None else {}, "fields": [list(x) for x in self.RP_FIELDS]}

    def lg_rehab_public_apply(self, path, mapping=None):
        p = self.lg_rehab_public_preview(path, mapping)
        self._xl_save("rehab", p["header"], p["mapping"])
        n = 0
        for x in p["rows"]:
            if x["did"] and not x["already"]:
                self.lg_rehab_register({"did": x["did"], "doc": "공공정보 등재", "kind": x["kind"], "no": x["no"], "got": x["date"] or L.today()})
                n += 1
        self._act(f"회생·파산 공공정보로 {n}명을 추적에 넣었어요", "rehab", "lg_rehab")
        return n

    def lg_rehab_set(self, rid, field, value):
        r = self.legal.data["rehab"][rid]
        if field in ("list_amt", "stage"):
            value = int(_num(value))
        r[field] = value
        if field == "no":
            r["check"] = not str(value).strip()
        self.legal.save()
        return self._rview(r)

    def lg_rehab_seen(self, rid):
        """관리 가부가 바뀐 것을 확인함"""
        r = self.legal.data["rehab"][rid]
        ch = r.pop("change", None)
        if ch:
            self.store.todos.setdefault(f"L|rchg|{rid}|{ch['to']}", {}).update({"done": now(), "by": self._me(), "note": "확인"})
            self.store.save_todos()
        self.legal.save()
        return True

    def lg_rehab_stop_ok(self, rid):
        r = self.legal.data["rehab"][rid]
        r["stop_ok"] = now()
        d = self.legal.debtor(r["did"])
        if d:
            self.legal.log(d, f"{r['no']} — 진행 중 법조치 멈춤 확인", self._me())
        self.store.todos.setdefault(f"L|stop|{rid}", {}).update({"done": now(), "by": self._me(), "note": "멈춤 확인"})
        self.store.save_todos()
        self.legal.save()
        return True

    def lg_rehab_do(self, rid, action, note=""):
        r = self.legal.data["rehab"][rid]
        d = self.legal.debtor(r["did"]) or {}
        flow = L.FLOW[r["kind"]]
        out = {"file": ""}
        if action.endswith("만들기"):
            kind = action.replace(" 만들기", "")
            amount = _num(d.get("principal")) + _num(d.get("interest"))
            paras = LD.rehab_doc(kind, r, d, self._lset().get("creditor") or {}, amount)
            folder = os.path.join(self.export_dir(), "법조치 서류", f"{L.today()} 회생·파산")
            out["file"] = LD.write_docx(paras, excel.unique_path(folder, f"{d.get('name', '')}_{kind}", ".docx"))
            self.legal.data["docs"].insert(0, {"at": now(), "type": kind, "did": r["did"], "name": d.get("name", ""), "file": out["file"]})
            text = f"{kind} 만듦"
        elif "사유" in action:
            text = f"{action.split(' · ')[0]} — {note}"
        else:
            text = "다음 단계로"
        if r.get("stage", 0) < len(flow) - 1:
            r["stage"] = r.get("stage", 0) + 1
            if action != "다음 단계로":
                r["due"] = ""
        r.setdefault("log", []).insert(0, {"at": now(), "text": text})
        if d:
            self.legal.log(d, f"{r['no']} {text}", self._me())
        self.legal.save()
        if out["file"]:
            self.reveal(out["file"])
        return out

    def lg_rehab_close(self, rid, reason):
        r = self.legal.data["rehab"][rid]
        r["closed"] = now()
        r["close_reason"] = reason
        d = self.legal.debtor(r["did"])
        if d:
            if reason == "면책 확정":
                d["stage"] = "종결"
            self.legal.log(d, f"{r['no']} 끝 — {reason}", self._me())
        self.legal.save()
        return True

    # ------------------------------------------------------------ 집행 대상

    def lg_assets(self, did):
        d = self.legal.debtor(did)
        if not d:
            raise ValueError("채무자를 찾지 못했어요")
        std = self._std()
        claim = _num(d.get("principal")) + _num(d.get("interest"))
        calc = L.assets_calc(std, d.get("assets") or [], claim)
        fee = L.garnish_fee(std, len(calc["third"]))
        title = d.get("title_no") or next((self.store.case_no(c) for c in self._linked(d) if c.get("status") == "확정"), "")
        return {"debtor": self._dview(d), "calc": calc, "fee": fee, "claim": claim, "title_no": title, "kinds": L.ASSET_KINDS,
                "stop": bool(self._rehab_of(did)),
                "candidates": [{"id": x["id"], "name": x["name"], "stage": self._stage(x)} for x in self.legal.active_debtors()]}

    def lg_asset_save(self, did, asset):
        d = self.legal.debtor(did)
        a = dict(asset)
        a["amt"], a["amt2"] = _num(a.get("amt")), _num(a.get("amt2"))
        if not a.get("id"):
            a["id"] = "a" + uuid.uuid4().hex[:8]
            d.setdefault("assets", []).append(a)
        else:
            for i, x in enumerate(d.get("assets") or []):
                if x["id"] == a["id"]:
                    d["assets"][i] = a
        self.legal.save()
        return self.lg_assets(did)

    def lg_asset_delete(self, did, aid):
        d = self.legal.debtor(did)
        d["assets"] = [x for x in d.get("assets") or [] if x["id"] != aid]
        self.legal.save()
        return self.lg_assets(did)

    # ------------------------------------------------------------ 서류 작성

    def _doc_rows(self, kind, opts):
        std, out = self._std(), []
        ecfs = bool(opts.get("ecfs", True))
        if kind == "지급명령":
            for d in self.legal.active_debtors():
                stage = self._stage(d)
                recent = (dt.datetime.now() - dt.timedelta(days=7)).strftime("%Y-%m-%d")
                made = any(x.get("did") == d["id"] and x.get("type") == "지급명령" and x["at"] >= recent for x in self.legal.data["docs"])
                base = self._stage(d, stop=[]) if stage == "회생·파산" else stage
                if not (stage == "준비" or (stage == "회생·파산" and base == "준비") or (made and stage == "독촉")):
                    continue
                claim = _num(d.get("principal")) + _num(d.get("interest"))
                fee = L.pay_order_fee(std, claim, 2, ecfs)
                st = ["ok", "준비됨"]
                if made:
                    st = ["made", "만듦"]
                elif stage == "회생·파산":
                    st = ["no", "회생·파산 — 제외"]
                elif not d.get("addr"):
                    st = ["no", "주소 없음 — 초본 먼저"]
                elif not claim:
                    st = ["no", "금액 없음"]
                elif d.get("sihyo") and (dt.date.fromisoformat(d["sihyo"]) - dt.date.today()).days < 60:
                    st = ["warn", f"시효 {(dt.date.fromisoformat(d['sihyo']) - dt.date.today()).days}일 — 먼저 내기"]
                court = d.get("court") or self._lset().get("court", "")
                out.append({"id": d["id"], "name": d["name"], "key": d.get("key", ""), "claim": claim, "court": court,
                            "stamp": fee["stamp"], "svc": fee["svc"], "st": st,
                            "warn": LD.warnings_for(kind, d, self.legal.data["info"], self._lset().get("creditor") or {}, opts.get("basis", "약정")) + ([] if court else ["관할 법원이 비어 있어요 — 원장이나 서류 정보에서"])})
        elif kind == "채권압류":
            for d in self.legal.active_debtors():
                stage = self._stage(d)
                if stage not in ("확정", "집행") and not d.get("assets"):
                    continue
                calc = L.assets_calc(std, d.get("assets") or [], _num(d.get("principal")) + _num(d.get("interest")))
                n3 = len(calc["third"])
                fee = L.garnish_fee(std, n3)
                made = any(x.get("did") == d["id"] and x.get("type") == "채권압류" for x in self.legal.data["docs"])
                st = ["made", "만듦"] if made else ["no", "회생·파산 — 제외"] if stage == "회생·파산" else \
                     ["ok", f"제3채무자 {n3}곳"] if n3 else ["no", "제3채무자 없음 — 집행 대상 먼저"]
                out.append({"id": d["id"], "name": d["name"], "key": d.get("key", ""), "claim": _num(d.get("principal")) + _num(d.get("interest")),
                            "court": d.get("court") or self._lset().get("court", ""), "stamp": fee["stamp"], "svc": fee["svc"], "st": st,
                            "warn": LD.warnings_for(kind, d, self.legal.data["info"], self._lset().get("creditor") or {})})
        else:
            for x in self.legal.data["dlv"].values():
                if x.get("done") or not x.get("act") or x["act"] == "초본 발급 요청":
                    continue
                d = self._debtor_of_case(x["cid"]) if x.get("cid") else self.legal.debtor(x.get("did") or "")
                out.append({"id": x["key"], "name": (d or {}).get("name") or x.get("party", ""), "key": x["case_no"], "claim": 0,
                            "court": "", "stamp": 0, "svc": 0, "st": ["ok", x["act"]], "case_no": x["case_no"], "warn": []})
        return out

    def lg_doc_rows(self, kind, opts=None):
        opts = opts or {}
        rows = self._doc_rows(kind, opts)
        return {"rows": rows, "info": self.legal.data["info"], "creditor": self._lset().get("creditor") or {},
                "std": {"svc": L.value(self._std(), "svc"), "pay_times": L.value(self._std(), "pay_times"),
                        "ecfs": L.value(self._std(), "ecfs"), "garn_times": L.value(self._std(), "garn_times")}}

    def _doc_paras(self, kind, rid, opts):
        std, cr, info = self._std(), self._lset().get("creditor") or {}, self.legal.data["info"]
        if kind == "주소보정":
            x = self.legal.data["dlv"][rid]
            d = self._debtor_of_case(x["cid"]) if x.get("cid") else self.legal.debtor(x.get("did") or "")
            return LD.address_fix(x, d, cr, (d or {}).get("addr", "")), d, x
        d = self.legal.debtor(rid)
        court = d.get("court") or self._lset().get("court", "")
        if kind == "지급명령":
            claim = _num(d.get("principal")) + _num(d.get("interest"))
            fee = L.pay_order_fee(std, claim, 2, bool(opts.get("ecfs", True)))
            return LD.pay_order(d, info, cr, fee, opts.get("basis", "약정"), court), d, None
        calc = L.assets_calc(std, d.get("assets") or [], _num(d.get("principal")) + _num(d.get("interest")))
        fee = L.garnish_fee(std, len(calc["third"]))
        title = d.get("title_no") or next((self.store.case_no(c) for c in self._linked(d) if c.get("status") == "확정"), "")
        return LD.garnish(d, info, cr, fee, calc["third"], title, court), d, None

    def lg_doc_preview(self, kind, rid, opts=None):
        paras, d, _ = self._doc_paras(kind, rid, opts or {})
        return {"paras": paras, "paste": LD.paste_text(paras),
                "warn": LD.warnings_for(kind, d or {}, self.legal.data["info"], self._lset().get("creditor") or {}, (opts or {}).get("basis", "약정"))}

    def lg_doc_make(self, kind, ids, opts=None):
        opts = opts or {}
        rows = {r["id"]: r for r in self._doc_rows(kind, opts)}
        folder = os.path.join(self.export_dir(), "법조치 서류", f"{dt.datetime.now():%Y-%m-%d %H%M} {kind}")
        made, listing = [], []
        for rid in ids:
            r = rows.get(rid)
            if not r or r["st"][0] in ("no", "made"):
                continue
            paras, d, x = self._doc_paras(kind, rid, opts)
            name = (d or {}).get("name") or r["name"]
            path = LD.write_docx(paras, excel.unique_path(folder, f"{name}_{kind if kind != '주소보정' else x['act'].split(' ')[0]}", ".docx"))
            made.append(path)
            listing.append([name, r.get("key", ""), int(r["claim"]), r.get("court", ""), r["stamp"], r["svc"], r["stamp"] + r["svc"], os.path.basename(path)])
            self.legal.data["docs"].insert(0, {"at": now(), "type": kind, "did": (d or {}).get("id", ""), "name": name, "file": path,
                                               "stamp": r["stamp"], "svc": r["svc"]})
            if d and kind == "지급명령":
                d["stage"] = "독촉"
                self.legal.log(d, f"지급명령 신청서 만듦 (인지 {r['stamp']:,}원 · 송달료 {r['svc']:,}원)", self._me())
            elif d and kind == "채권압류":
                d["stage"] = "집행"
                self.legal.log(d, "채권압류 및 추심명령 신청서 만듦", self._me())
            elif x:
                self.lg_dlv_done([x["key"]], note=f"{x['act']} — 서류 만듦")
        if not made:
            raise ValueError("만들 대상이 없어요")
        wb = excel._wb()
        excel._sheet(wb, "만든 서류", ["채무자", "계좌·사건", "청구액", "법원", "인지대", "송달료", "합계", "파일"], listing, first=True)
        lst = os.path.join(folder, "_목록.xlsx")
        wb.save(lst)
        self.legal.save()
        self.reveal(made[0])
        self._act(f"기본 서류 {kind} {len(made)}건을 만들었어요", "doc", "lg_doc")
        return {"count": len(made), "folder": folder, "list": lst, "stamp": sum(r[4] for r in listing), "svc": sum(r[5] for r in listing)}

    # ------------------------------------------------------------ 배당 예상

    # ------------------------------------------------------------ 기준표

    def lg_std(self):
        std = self._std()
        items = []
        for k, it in std["items"].items():
            rows = sorted(it["rows"], key=lambda r: r["from"])
            cur = L.row_at(std, k)
            items.append({"key": k, "name": it["name"], "unit": it["unit"], "basis": it["basis"], "rows": rows,
                          "cur": cur["v"], "cur_from": cur["from"], "check": cur.get("check", "")})
        lp = os.path.join(self.data_dir, "standards_log.json")
        log = []
        if os.path.isfile(lp):
            with open(lp, encoding="utf-8") as f:
                log = [{k: x[k] for k in ("at", "by", "text")} for x in json.load(f)]
        return {"items": items, "small": std["small"], "holidays": std["holidays"], "zones": L.ZONES, "log": log[:10]}

    def lg_std_set(self, key, rows):
        std = self._std()
        clean = []
        for r in rows:
            if not r.get("from"):
                continue
            clean.append({"from": _date(r["from"]) or r["from"], "v": float(r["v"]) if key == "ecfs" else int(_num(r["v"])), "check": r.get("check", "")})
        if not clean:
            raise ValueError("값이 하나는 있어야 해요")
        std["items"][key]["rows"] = clean
        self._std_save(std, f"{std['items'][key]['name']} 바꿈")
        return self.lg_std()

    def lg_std_check(self, key, src=""):
        """지금 쓰는 줄을 「확인함」으로"""
        std = self._std()
        cur = L.row_at(std, key)
        for r in std["items"][key]["rows"]:
            if r["from"] == cur["from"]:
                r["check"] = f"{L.today()} · {self._me() or '담당자'}" + (f" · {src}" if src else "")
        self._std_save(std, f"{std['items'][key]['name']} 확인")
        return self.lg_std()

    def lg_std_small(self, rows):
        std = self._std()
        std["small"] = sorted(rows, key=lambda r: r["from"])
        self._std_save(std, "소액임차인 기준 바꿈")
        return self.lg_std()

    def lg_std_holidays(self, days):
        std = self._std()
        std["holidays"] = sorted({_date(d) for d in days if _date(d)})
        self._std_save(std, "쉬는 날 바꿈")
        return self.lg_std()

    def lg_std_undo(self):
        lp = os.path.join(self.data_dir, "standards_log.json")
        with open(lp, encoding="utf-8") as f:
            log = json.load(f)
        if not log:
            raise ValueError("되돌릴 기록이 없어요")
        last = log.pop(0)
        with open(os.path.join(self.data_dir, "standards.json"), "w", encoding="utf-8") as f:
            json.dump(last["before"], f, ensure_ascii=False, indent=1)
        with open(lp, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False)
        self.legal.rev += 1
        return self.lg_std()

    # ------------------------------------------------------------ 법조치 현황 · 확인할 것

    def _legal_todos(self):
        out, td = [], self.store.todos

        def item(key, kind, color, date, text, due, party, go, arg, ask=False, owner=""):
            st = td.get(key, {})
            out.append({"key": key, "cid": "", "kind": kind, "color": color, "date": date, "text": text, "due": st.get("deadline") or due,
                        "due_manual": True, "ask": ask and not st.get("done"), "done": st.get("done", ""), "done_note": st.get("note", ""),
                        "done_by": st.get("by", ""), "new": False, "legal": True, "go": go, "arg": arg, "case_no": "", "party": party,
                        "court": "", "memo1": "", "owner": owner})
        self._rehab_sync()
        for r in self.legal.data["rehab"].values():
            if r.get("closed"):
                continue
            d = self.legal.debtor(r["did"]) or {}
            name = d.get("name") or r.get("name", "")
            ch = r.get("change")
            if ch:
                item(f"L|rchg|{r['id']}|{ch['to']}", "회생·파산 관리 가부 바뀜", L.MANAGE[ch["to"]][1].replace("black", "gray"), ch["at"][:10],
                     f"{L.MANAGE[ch['from']][0]} → {L.MANAGE[ch['to']][0]} ({ch['event']}) · {r['no']}", L.today(), name, "lg_rehab", {"rid": r["id"]})
            if not r.get("stop_ok") and (r.get("code") or "") in L.BLOCKING:
                item(f"L|stop|{r['id']}", "회생 멈춤 확인", "red", r.get("got", ""), f"{L.MANAGE[r['code']][0]} — 진행 중 법조치를 멈췄는지 확인 ({r['no']})",
                     L.today(), name, "lg_rehab", {"rid": r["id"]})
            if r.get("due"):
                item(f"L|rehab|{r['id']}|{r['due']}", "회생·파산 기한", "orange", r.get("got", ""),
                     f"{L.FLOW[r['kind']][min(r.get('stage', 0), len(L.FLOW[r['kind']]) - 1)]} 기한 ({r['no']})", r["due"], d.get("name", ""),
                     "lg_rehab", {"rid": r["id"]})
        std = self._std()
        for x in self.legal.data["dlv"].values():  # 엑셀·직접 등록한 보정 (사건 조회에서 온 것은 「송달불능」으로 이미 있음)
            if not x["key"].startswith("M|") or x.get("done"):
                continue
            due = self._dlv_due(x, std)
            if due:
                left = (dt.date.fromisoformat(due["due"]) - dt.date.today()).days
                item(x["key"], "보정 기한", "red" if left <= 3 else "orange", x.get("recv") or x.get("date", ""),
                     f"{x['case_no']} {x.get('reason') or '송달불능'} — {x.get('act') or '조치 정하기'}{' · ' + x['owner'] if x.get('owner') else ''}",
                     due["due"], x.get("party", ""), "lg_dlv", {"key": x["key"]}, owner=x.get("owner", ""))
        for d in self.legal.active_debtors():
            if d.get("sihyo") and self._stage(d) == "준비":
                left = (dt.date.fromisoformat(d["sihyo"]) - dt.date.today()).days
                if left <= 90:
                    item(f"L|sihyo|{d['id']}|{d['sihyo']}", "시효 임박", "red", d["sihyo"], f"시효 완성 예정 {d['sihyo']} — 아직 법조치 전",
                         d["sihyo"], d["name"], "lg_doc", {})
        return out

    def lg_home(self):
        self._dlv_sync()
        std = self._std()
        today = dt.date.today()
        debtors = self.legal.active_debtors()
        stages = {}
        for d in debtors:
            s = self._stage(d)
            stages[s] = stages.get(s, 0) + 1
        dl = list(self.legal.data["dlv"].values())
        dlv_open = [x for x in dl if not x.get("done")]
        due7 = sum(1 for x in dlv_open if self._dlv_due(x, std) and (dt.date.fromisoformat(self._dlv_due(x, std)["due"]) - today).days <= 7)
        rh = [r for r in self.legal.data["rehab"].values() if not r.get("closed")]
        due7 += sum(1 for r in rh if r.get("due") and (dt.date.fromisoformat(r["due"]) - today).days <= 7)
        # 10주 추이
        mon = today - dt.timedelta(days=today.weekday())
        weeks = [mon - dt.timedelta(weeks=9 - i) for i in range(10)]

        def wk(s):
            if not s:
                return None
            d = dt.date.fromisoformat(s[:10])
            for i in range(9, -1, -1):
                if d >= weeks[i]:
                    return i if d < weeks[i] + dt.timedelta(days=7) else None
            return None
        chart = [{"label": f"{w.month}/{w.day}", "docs": 0, "dlv": 0, "rehab": 0} for w in weeks]
        for x in self.legal.data["docs"]:
            i = wk(x.get("at"))
            if i is not None:
                chart[i]["docs"] += 1
        for x in dl:
            i = wk(x.get("done"))
            if i is not None:
                chart[i]["dlv"] += 1
        for r in self.legal.data["rehab"].values():
            i = wk(r.get("created"))
            if i is not None:
                chart[i]["rehab"] += 1
        week_docs = chart[-1]["docs"]
        prev_docs = chart[-2]["docs"]
        return {"kpi": {"active": sum(v for k, v in stages.items() if k in ("독촉", "소송", "확정", "집행")), "due7": due7,
                        "stop": sum(1 for r in rh if r.get("code") in L.BLOCKING),
                        "stop_pending": sum(1 for r in rh if not r.get("stop_ok") and r.get("code") in L.BLOCKING),
                        "docs_week": week_docs, "docs_prev": prev_docs, "debtors": len(debtors)},
                "stages": [[s, stages.get(s, 0)] for s in STAGES], "chart": chart,
                "dlv_rate": {"done": sum(1 for x in dl if x.get("done")), "total": len(dl)},
                "todos": [t for t in self._legal_todos() if not t["done"]],
                "dlv_due": sorted([{"key": x["key"], "party": x.get("party", ""), "case_no": x["case_no"], "due": self._dlv_due(x, std)["due"]}
                                   for x in dlv_open if self._dlv_due(x, std)], key=lambda x: x["due"])[:6],
                "dlv_wait": sum(1 for x in dlv_open if not self._dlv_due(x, std)),
                "std_unchecked": sum(1 for it in self.lg_std()["items"] if not it["check"]),
                "creditor_ok": bool((self._lset().get("creditor") or {}).get("name"))}
