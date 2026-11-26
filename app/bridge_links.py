# -*- coding: utf-8 -*-
"""「이어진 것」 — 사건 · 채무자 · 배당 어디서 열어도 같은 사람 · 같은 사건으로 묶인 것을 한 줄로.

원장 ↔ 사건: 설정 → 연결 기준(메모 1 = 원장 키 / 당사자 이름) 그대로
사건 ↔ 경매: 경매 메모(계좌번호) 또는 경매 관련사건 번호
사건 ↔ 배당: 배당 줄의 당사 사건(법원 + 사건번호) · 채무자키 = 원장 키
"""
from core import legal as L
from core import dividend as DV
from core import auction as AU


class LinksMixin:
    def links(self, cid="", did="", dv=""):
        cases, debtor = [], None
        dvrow = None
        if dv:
            dvrow = next((r for r in self.dv.ledger if r["id"] == dv), None)
        if cid and cid in self.store.cases:
            cases = [self.store.cases[cid]]
            debtor = self._debtor_of_case(cid)
        if did:
            debtor = self.legal.debtor(did)
        if dvrow is not None and not debtor:
            k = L.digits(dvrow.get("dkey"))
            for d in self.legal.active_debtors():
                if k and L.digits(d.get("key")) == k:
                    debtor = d
                    break
        if dvrow is not None and not cases:
            on = DV.norm_no(DV.ours_no(dvrow))
            if on:
                cases = [c for c in self.store.active_cases() if DV.norm_no(self.store.case_no(c)) == on]
            if cases and not debtor:
                debtor = self._debtor_of_case(cases[0]["id"])
        if debtor:
            for c in self._linked(debtor):
                if c["id"] not in {x["id"] for x in cases}:
                    cases.append(c)
        cids = {c["id"] for c in cases}
        nos = {DV.norm_no(self.store.case_no(c)) for c in cases}
        out = []
        if debtor:
            out.append({"k": "원장", "v": debtor.get("name", "") + (f" · {debtor['key']}" if debtor.get("key") else ""), "go": "lg_debtors", "arg": {"did": debtor["id"]}, "on": bool(did)})
        if cases:
            c0 = cases[0]
            out.append({"k": "사건", "v": self.store.case_no(c0) + (f" 외 {len(cases) - 1}" if len(cases) > 1 else ""), "go": "case", "arg": {"cid": c0["id"]},
                        "on": bool(cid), "list": [{"t": self.store.case_no(c), "go": "case", "arg": {"cid": c["id"]}} for c in cases[:8]]})
        # 경매
        memos = {AU.norm_memo(c.get("memo1")) for c in cases if AU.norm_memo(c.get("memo1"))}
        au = [a for a in self.auct.items.values() if not a.get("archived") and
              ((AU.norm_memo(a.get("memo1")) and AU.norm_memo(a.get("memo1")) in memos) or any(DV.norm_no(n) in nos for n in a.get("related_nos") or []))]
        if au:
            out.append({"k": "경매", "v": au[0]["case_no"] + (f" 외 {len(au) - 1}" if len(au) > 1 else ""), "go": "auction_case", "arg": {"aid": au[0]["id"]}})
        # 회생·파산
        if debtor:
            rh = [r for r in self.legal.data["rehab"].values() if r.get("did") == debtor["id"] and not r.get("closed")]
            if rh:
                st = self._rstatus(rh[0]) if hasattr(self, "_rstatus") else {}
                out.append({"k": "회생·파산", "v": (st.get("label") or st.get("code") or "추적 중") + (f" · {rh[0].get('no')}" if rh[0].get('no') else ""), "go": "lg_rehab", "arg": {},
                            "warn": (st.get("code") or "") in getattr(L, "BLOCKING", ())})
        # 보정 · 송달
        dl = [x for x in self.legal.data["dlv"].values() if x.get("cid") in cids and not x.get("done")]
        if dl:
            out.append({"k": "보정", "v": f"{len(dl)}건 · {dl[0].get('reason') or dl[0].get('why') or '처리할 것'}", "go": "lg_dlv", "arg": {}, "warn": True})
        # 배당
        dvs = [r for r in self.dv.ledger if not r.get("deleted") and (
            (r["id"] == dv) or (DV.norm_no(DV.ours_no(r)) and DV.norm_no(DV.ours_no(r)) in nos) or
            (debtor and L.digits(r.get("dkey")) and L.digits(r.get("dkey")) == L.digits(debtor.get("key"))))]
        if dvs:
            r = dvs[0]
            s, _c = DV.stage(r)
            out.append({"k": "배당", "v": f"{r.get('no', '')} · {s}" + (f" 외 {len(dvs) - 1}" if len(dvs) > 1 else ""), "go": "dv_ledger", "arg": {"open": r["id"], "lf": "all", "q": ""}, "on": bool(dv)})
        # 서류
        if debtor:
            docs = [x for x in self.legal.data["docs"] if x.get("did") == debtor["id"]]
            if docs:
                out.append({"k": "서류", "v": f"{docs[0].get('type', '')} · {docs[0]['at'][5:10].replace('-', '.')}" + (f" 외 {len(docs) - 1}" if len(docs) > 1 else ""),
                            "go": "lg_debtors", "arg": {"did": debtor["id"]}})
        return out
