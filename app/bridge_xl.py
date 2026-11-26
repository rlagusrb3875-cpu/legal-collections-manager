# -*- coding: utf-8 -*-
"""엑셀 넣기 한 곳 — 파일을 넣고 「넣을 곳」을 고르면 같은 짝짓기 화면으로 넣는다.

넣을 곳: 사건 대장 · 채무자 원장 · 송달·보정 관리 · 회생·파산 등재(공공정보) · 회사 양식 서류 대상
각 화면의 엑셀 넣기도 그대로 쓰고, 짝지은 열은 어디서 넣든 함께 기억한다 (core/xlmap).
"""
import json
import os
import re

from core import excel
from core import xlmap as XM

DESTS = [("case", "사건 대장", "조회할 사건 목록 (법원·사건번호·당사자)"),
         ("debtor", "채무자 원장", "채권 엑셀 (이름·계좌번호·원금·주소)"),
         ("dlv", "송달·보정 관리", "보정 대장 (사건번호·보정명령일·기한·조치)"),
         ("rehab", "회생·파산 등재", "신용정보 공공정보 (성명·생년월일·등록 사유)"),
         ("form", "회사 양식 서류 대상", "서류에 채울 값 (이름·사건번호·법원·주소…)")]


class XlMixin:
    # ------------------------------------------------------------ 기억 · 연결 기준

    def _xlmem(self):
        p = os.path.join(self.data_dir, "xlmem.json")
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _xl_pref(self, dest, header):
        return XM.prefer(self._xlmem(), self.store.settings, dest, header)

    def _xl_auto(self, dest, header, auto):
        """자동으로 찾은 짝 + 기억한 짝 → (짝, 어디서 왔는지)"""
        return XM.merge(auto, self._xl_pref(dest, header))

    def _xl_save(self, dest, header, mapping):
        new = XM.remember(self._xlmem(), dest, header, mapping)
        if new is not None:
            p = os.path.join(self.data_dir, "xlmem.json")
            with open(p + ".tmp", "w", encoding="utf-8") as f:
                json.dump(new, f, ensure_ascii=False)
            os.replace(p + ".tmp", p)

    def _link(self, what):
        return XM.link(self.store.settings, what)

    def link_get(self):
        return {"link": {k: self._link(k) for k in XM.LINK_DEFAULT}, "methods": XM.METHODS, "mem": len(self._xlmem())}

    def link_set(self, what, value):
        if what not in XM.LINK_DEFAULT:
            raise ValueError("알 수 없는 기능이에요")
        cur = dict(self._link(what))
        for k, v in (value or {}).items():
            if k == "by" and isinstance(v, list):
                v = [m for m in v if m in XM.METHODS]
            cur[k] = v
        link = dict(self.store.settings.get("link") or {})
        link[what] = cur
        self.store.set_setting("link", link, f"연결 기준: {what}")
        return self.link_get()

    def xl_forget(self):
        p = os.path.join(self.data_dir, "xlmem.json")
        if os.path.isfile(p):
            os.remove(p)
        return True

    # ------------------------------------------------------------ 한 곳에서 넣기

    def _xl_guess_dest(self, header):
        h = " ".join(re.sub(r"\s", "", str(x)) for x in header)
        if re.search("보정|불능|송달", h):
            return "dlv"
        if re.search("등록사유|공공정보|등재|면책|파산", h):
            return "rehab"
        if re.search("원금|이자|대출|잔액|기한이익|시효", h):
            return "debtor"
        if re.search("사건번호|사건", h) and re.search("법원|관할", h):
            return "case"
        return "debtor"

    def xl_open(self, path, dest="", mapping=None, fid=""):
        """파일을 열어 넣을 곳의 항목·짝짓기·미리보기를 돌려준다."""
        _, rows = excel.read_table(path)
        hi = excel.find_header(rows)
        header = [str(h) for h in (rows[hi] if rows else [])]
        body = [r for r in rows[hi + 1:] if any(str(x).strip() for x in r)]
        dest = dest or self._xl_guess_dest(header)
        if mapping is not None:
            mapping = {k: int(v) for k, v in mapping.items() if str(v) not in ("", "-1", "None")}
        out = {"path": path, "name": os.path.basename(path), "header": header, "rows": len(body), "peek": [r[:len(header)] for r in body[:5]],
               "dests": [list(x) for x in DESTS], "dest": dest, "link": self._link({"case": "case", "debtor": "debtor", "dlv": "dlv", "rehab": "rehab",
                                                                                     "form": "form"}[dest]), "methods": XM.METHODS}
        if dest == "case":
            p = self.import_preview(path, mapping)
            out.update(fields=[[f["key"], f["name"]] for f in p["fields"]], mapping=p["mapping"], src=p.get("src") or {},
                       summary=f"사건 {p['good_count']}건 · 새로 {p['new']} · 이미 있음 {p['same']}" + (f" · 못 읽은 줄 {len(p['skips'])}" if p.get("skips") else ""))
        elif dest == "debtor":
            p = self.lg_import_preview(path, mapping)
            out.update(fields=p["fields"], mapping=p["mapping"], src=p.get("src") or {},
                       summary=f"새로 {p['new']}명 · 원장에 있는 사람 갱신 {p['update']}명" + (f" (이름만으로 찾은 {p['by_name']}명 — 동명이인 확인)" if p.get("by_name") else "") +
                       (f" · 이름 없어 뺌 {p['skip']}" if p["skip"] else ""))
        elif dest == "dlv":
            p = self.lg_dlv_import_preview(path, mapping)
            out.update(fields=p["fields"], mapping=p["mapping"], src=p.get("src") or {},
                       summary=f"보정 {p['rows']}건 · 새로 {p['new']} · 이미 있는 건 갱신 {p['update']}")
        elif dest == "rehab":
            p = self.lg_rehab_public_preview(path, mapping)
            out.update(fields=p["fields"], mapping=p["mapping"], src=p.get("src") or {},
                       summary=f"{len(p['rows'])}명 중 원장과 이어진 {sum(1 for x in p['rows'] if x['did'])}명 · 새로 추적 {p['matched']}명")
        else:
            from core import forms as FM
            its = [i for i in FM.items(self._fset()["items"]) if not i.get("image") and i["k"] != "date" and i["g"] != "고정값"]
            auto = {}
            for j, h in enumerate(header):
                hn = re.sub(r"\s", "", h)
                from bridge_forms import XL_ALIAS
                for k, al in XL_ALIAS.items():
                    if k not in auto and hn in [re.sub(r"\s", "", a) for a in al]:
                        auto[k] = j
                        break
            m, src = self._xl_auto("form", header, auto)
            if mapping is not None:
                m, src = mapping, {}
            out.update(fields=[[i["k"], i["n"]] for i in its], mapping=m, src=src, summary=f"{len(body)}줄 → 서류 {len(body)}장 (양식은 다음 화면에서 골라요)",
                       forms=[{"id": f["id"], "name": f["name"]} for f in self._forms() if not f.get("draft")])
        return out

    def xl_apply(self, path, dest, mapping=None, opts=None):
        opts = opts or {}
        if mapping is not None:
            mapping = {k: int(v) for k, v in mapping.items() if str(v) not in ("", "-1", "None")}
        if dest == "case":
            r = self.import_apply(path, mapping, opts.get("gone_action") or "keep")
            return {"text": f"사건 대장에 넣었어요 — 새로 {r.get('added', 0)}건 · 갱신 {r.get('updated', 0)}건", "go": "ledger"}
        if dest == "debtor":
            r = self.lg_import_apply(path, mapping)
            return {"text": f"채무자 원장에 넣었어요 — {r['count']}명 (새로 {r['new']} · 갱신 {r['update']})", "go": "lg_debtors"}
        if dest == "dlv":
            r = self.lg_dlv_import_apply(path, mapping, bool(opts.get("overwrite")))
            return {"text": f"보정 관리에 넣었어요 — 새로 {r['new']}건 · 갱신 {r['update']}건", "go": "lg_dlv"}
        if dest == "rehab":
            n = self.lg_rehab_public_apply(path, mapping)
            return {"text": f"회생·파산 추적에 {n}명을 넣었어요", "go": "lg_rehab"}
        _, rows = excel.read_table(path)
        hi = excel.find_header(rows)
        self._xl_save("form", [str(h) for h in (rows[hi] if rows else [])], mapping)
        return {"text": "짝지은 열을 기억했어요. 양식을 고르고 서류를 만들어요.", "go": "fm_make",
                "arg": {"fid": opts.get("fid") or "", "src": "xl", "path": path, "mapping": mapping}}
