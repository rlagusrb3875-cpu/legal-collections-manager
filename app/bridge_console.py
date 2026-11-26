# -*- coding: utf-8 -*-
"""현황 콘솔 · 작업 기록 · 찾기(Ctrl K)

작업 기록: 채권 폴더 activity.json (최근 300개). 조회 끝·보정·서류·엑셀 넣기 같은 「한 일」만 남긴다.
"""
import datetime as dt
import json
import os
import threading

_LOCK = threading.Lock()


class ConsoleMixin:
    # ------------------------------------------------------------ 작업 기록

    def _act_path(self):
        return os.path.join(self.store.root, "activity.json")

    def _acts(self):
        try:
            with open(self._act_path(), encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _act(self, text, kind="", go="", arg=None):
        """한 일을 작업 기록에 남긴다. 기록에 실패해도 하던 일은 그대로 끝낸다."""
        try:
            with _LOCK:
                items = self._acts()
                items.insert(0, {"at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "by": self._me(), "kind": kind, "text": text,
                                 "go": go, "arg": arg or {}})
                tmp = self._act_path() + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(items[:300], f, ensure_ascii=False)
                os.replace(tmp, self._act_path())
        except Exception:
            pass

    def activity(self, limit=50):
        return self._acts()[:int(limit)]

    # ------------------------------------------------------------ 현황 콘솔

    def console(self):
        today = dt.date.today()
        h = self.home()
        items = [i for i in h["items"] if not i.get("done")]
        hot = [i for i in items if (i.get("left") is not None and i["left"] <= 0) or i.get("ask") or i.get("new")]
        std = self._std()
        self._dlv_sync()
        dl = [x for x in self.legal.data["dlv"].values() if not x.get("done")]
        soon = [x for x in dl if self._dlv_due(x, std) and (dt.date.fromisoformat(self._dlv_due(x, std)["due"]) - today).days <= 3]
        self._rehab_sync()
        from core import legal as L
        blk = [r for r in self.legal.data["rehab"].values() if not r.get("closed") and (r.get("code") or "") in L.BLOCKING]
        week = (dt.datetime.now() - dt.timedelta(days=7)).strftime("%Y-%m-%d")
        docs = [x for x in self.legal.data["docs"] if x.get("at", "") >= week and x.get("did")]
        forms = [f for f in self._forms() if not f.get("draft")]
        order = sorted(items, key=lambda i: (0 if i in hot else 1, i["left"] if i.get("left") is not None else 999))
        last = next((r for r in self.store.runs if r.get("finished")), None)
        # 숫자는 모두 「확인할 것」 목록에서 센다 (어디서 보든 같게)
        isdlv = lambda i: not i.get("aid") and not str(i.get("key", "")).startswith(("A|", "D|")) and not i.get("dv") \
            and not any(w in i.get("kind", "") for w in ("회생", "파산", "시효")) and any(w in i.get("kind", "") for w in ("보정", "송달", "공시"))
        k_soon = [i for i in items if isdlv(i) and i.get("left") is not None and i["left"] <= 3]
        k_dlv = [i for i in items if isdlv(i)]
        k_reh = [i for i in items if "회생" in i.get("kind", "") or "파산" in i.get("kind", "")]
        k_dv = [i for i in items if i.get("dv")]
        return {"kpi": {"todo": len(items), "hot": len(hot), "dlv": len(k_dlv), "soon": len(k_soon), "stop": len(k_reh),
                        "dv": len(k_dv), "dv_hot": sum(1 for i in k_dv if i.get("color") == "red"),
                        "stop_pending": sum(1 for i in k_reh if i.get("kind") == "회생 멈춤 확인"), "docs": len(docs), "forms": len(forms)},
                "flow": {"cases": len(self.store.active_cases()), "todo": len(items), "dlv": len(dl), "forms": len(forms), "soon": len(soon)},
                "today": order[:8], "log": self.activity(12), "last_run": (last or {}).get("finished", ""), "next_run": h.get("next_run", ""),
                "book": self.book}

    # ------------------------------------------------------------ 찾기 (Ctrl K)

    def palette(self, q=""):
        q = (q or "").replace(" ", "")
        if not q:
            return {"cases": [], "debtors": []}
        cases = []
        for c in self.store.active_cases():
            no = self.store.case_no(c)
            if q in no.replace(" ", "") or q in (c.get("party") or "").replace(" ", "") or q in (c.get("memo1") or ""):
                cases.append({"id": c["id"], "t": f"{no} · {c.get('party', '')}", "s": c.get("court", "")})
            if len(cases) >= 8:
                break
        debtors = []
        for d in self.legal.active_debtors():
            if q in (d.get("name") or "").replace(" ", "") or q in (d.get("key") or ""):
                debtors.append({"id": d["id"], "t": f"{d['name']} · {d.get('key', '')}", "s": d.get("court", "")})
            if len(debtors) >= 6:
                break
        return {"cases": cases, "debtors": debtors}
