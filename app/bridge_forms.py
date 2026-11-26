# -*- coding: utf-8 -*-
"""회사 양식 서류 — 양식 PDF를 그대로 두고 바뀌는 칸에만 원장·송달·엑셀 값을 채운다.

  양식 보관: <자료 폴더>/forms/<id>/form.pdf + form.json (모든 채권이 같이 씀)
  흐름: 양식 넣기 → 칸 자동 찾기·확인 → 대상 고르기(송달·원장·엑셀) → 검수 → 마지막 확인 → PDF 저장·인쇄
"""
import datetime as dt
import json
import os
import re
import shutil
import uuid
import zipfile

from core import excel
from core import forms as FM
from core import legal as L
from core.legal_store import now

GROUPS = ["송달", "지급명령", "집행", "회생·파산", "기타"]
TASKS = [("송달불능", "송달 화면에서 「회사 양식으로」"), ("지급명령 대상", "원장의 준비 단계"), ("집행권원 확보", "확정 뒤 압류")]
XL_ALIAS = {
    "debtor": ["채무자", "채무자명", "성명", "이름", "고객명", "피고", "차주", "차주명"],
    "case_no": ["사건번호", "사건", "사건 번호"], "court": ["법원", "관할법원", "관할", "관할 법원"],
    "new_addr": ["새주소", "신주소", "보정주소", "보정할주소", "변경주소", "새 주소"], "debtor_addr": ["주소", "채무자주소", "주민등록주소", "송달주소"],
    "reason": ["불능사유", "송달불능사유", "사유", "송달결과"], "req": ["신청종류", "신청", "조치"],
    "amount": ["청구금액", "청구액", "금액", "원금", "채권액"], "mgmt_no": ["관리번호", "계좌번호", "계좌", "고객번호", "대출번호"],
    "case_name": ["사건명"], "creditor": ["원채권사", "양도인", "채권사", "원채권자"],
}
REASON_OF = {"수취인부재": "폐문부재", "송달불능": ""}
REQ_OF = {"재송달": "재송달", "야간·휴일 특별송달": "특별송달", "공시송달 신청": "공시송달"}


class FormsMixin:
    # ------------------------------------------------------------ 보관

    def _fdir(self, fid=""):
        root = os.path.join(self.data_dir, "forms")
        return os.path.join(root, fid) if fid else root

    def _form(self, fid):
        p = os.path.join(self._fdir(fid), "form.json")
        if not re.fullmatch(r"[0-9a-f]{12}", fid or "") or not os.path.isfile(p):
            raise ValueError("양식을 찾지 못했어요")
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def _form_save(self, fm):
        d = self._fdir(fm["id"])
        os.makedirs(d, exist_ok=True)
        tmp = os.path.join(d, "form.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(fm, f, ensure_ascii=False, indent=1)
        os.replace(tmp, os.path.join(d, "form.json"))

    def _forms(self):
        out = []
        root = self._fdir()
        if os.path.isdir(root):
            for fid in os.listdir(root):
                try:
                    out.append(self._form(fid))
                except Exception:
                    continue
        return out

    def _fset(self):
        lg = self.store.settings.get("legal") or {}
        return {"tasks": lg.get("form_tasks") or {}, "items": lg.get("form_items") or [], "agent": lg.get("agent", ""),
                "font": lg.get("form_font") or "myeongjo"}

    def _names(self):
        return {i["k"]: i["n"] for i in FM.items(self._fset()["items"])}

    def _seal_path(self):
        p = os.path.join(self._fdir(), "_seal.png")
        return p if os.path.isfile(p) else ""

    def _fsum(self, fm):
        used = []
        for f in fm.get("fields", []):
            if f.get("item") and f["item"] not in used:
                used.append(f["item"])
        tasks = [t for t, fid in self._fset()["tasks"].items() if fid == fm["id"]]
        return {k: fm.get(k) for k in ("id", "name", "grp", "file", "fav", "uses", "used", "ver", "created", "draft", "font")} | {
            "n": len(fm.get("fields", [])), "items": used, "pages": len(fm.get("pages", [])), "tasks": tasks}

    # ------------------------------------------------------------ 양식함

    def fm_list(self):
        forms = [self._fsum(f) for f in self._forms() if not f.get("draft")]
        forms.sort(key=lambda f: f.get("name") or "")
        forms.sort(key=lambda f: f.get("used") or "", reverse=True)
        forms.sort(key=lambda f: not f.get("fav"))
        return {"forms": forms, "groups": GROUPS, "tasks": [[t, s, self._fset()["tasks"].get(t, "")] for t, s in TASKS],
                "items": FM.items(self._fset()["items"])}

    def fm_add(self, path=None):
        """PDF를 양식함에 넣는다 (칸은 아직 없음 — 칸 정하기 화면에서 정해 저장)."""
        path = path or self.choose_file("pdf")
        if not path:
            return None
        if not str(path).lower().endswith(".pdf") or not os.path.isfile(path):
            raise ValueError("PDF 파일을 골라 주세요")
        fid = uuid.uuid4().hex[:12]
        d = self._fdir(fid)
        os.makedirs(d, exist_ok=True)
        try:
            FM.normalize(path, os.path.join(d, "form.pdf"))
            pages = FM.page_info(os.path.join(d, "form.pdf"))
        except Exception as e:
            shutil.rmtree(d, ignore_errors=True)
            raise ValueError(str(e) if isinstance(e, ValueError) else "PDF를 열지 못했어요. 다른 PDF로 저장해서 다시 넣어 주세요.")
        name = re.sub(r"[_\-]?(회사)?양식$", "", os.path.splitext(os.path.basename(path))[0]).strip() or "새 양식"
        grp = "송달" if re.search("송달|보정", name) else "지급명령" if "지급명령" in name else "집행" if re.search("압류|추심|경매|집행", name) else "기타"
        self._form_save({"id": fid, "name": name, "grp": grp, "file": os.path.basename(path), "pages": pages, "fields": [],
                         "font": self._fset()["font"], "fav": False, "uses": 0, "used": "", "ver": 0, "created": now(), "by": self._me(), "draft": True})
        return fid

    def fm_get(self, fid):
        fm = self._form(fid)
        return {"form": fm, "items": FM.items(self._fset()["items"]), "groups": GROUPS, "css": FM.FONT_CSS}

    def fm_page(self, fid, p=0, scale=2.0):
        key = (fid, int(p), float(scale), os.path.getmtime(os.path.join(self._fdir(fid), "form.pdf")))
        cache = getattr(self, "_fpage", None)
        if cache is None:
            cache = self._fpage = {}
        if key not in cache:
            if len(cache) > 30:
                cache.clear()
            cache[key] = FM.render_png(os.path.join(self._fdir(fid), "form.pdf"), int(p), float(scale))
        return cache[key]

    def fm_detect(self, fid):
        self._form(fid)
        return FM.detect(os.path.join(self._fdir(fid), "form.pdf"))

    def fm_save(self, fid, data):
        fm = self._form(fid)
        fields = []
        for f in data.get("fields") or []:
            if f.get("type") not in FM.TYPES:
                raise ValueError("칸 종류가 이상해요")
            if not f.get("item"):
                raise ValueError("항목을 고르지 않은 칸이 있어요")
            g = {k: f[k] for k in ("p", "type", "item", "opt", "fmt", "suffix", "orig", "optional", "size") if f.get(k) not in (None, "")}
            g.update({k: round(float(f[k]), 1) for k in ("x", "y", "w", "h")})
            g["p"] = int(f.get("p") or 0)
            fields.append(g)
        if not fields:
            raise ValueError("칸이 하나도 없어요")
        name = (data.get("name") or fm["name"]).strip()
        if not name:
            raise ValueError("양식 이름을 넣어 주세요")
        changed = fields != fm.get("fields")
        if changed and fm.get("fields"):  # 예전 칸은 보관해 둔다 (그 판으로 만든 서류를 설명할 수 있게)
            old = os.path.join(self._fdir(fid), "versions")
            os.makedirs(old, exist_ok=True)
            with open(os.path.join(old, f"v{fm.get('ver', 0)}.json"), "w", encoding="utf-8") as f:
                json.dump(fm["fields"], f, ensure_ascii=False)
        fm.update({"name": name, "grp": data.get("grp") or fm.get("grp") or "기타", "font": data.get("font") or fm.get("font") or "myeongjo",
                   "fields": fields, "draft": False, "ver": fm.get("ver", 0) + (1 if changed else 0), "saved": now()})
        self._form_save(fm)
        self._act(f"양식 「{name}」을 저장했어요 (칸 {len(fields)}개 · {fm['ver']}판)", "doc", "fm")
        return self._fsum(fm)

    def fm_delete(self, fid):
        self._form(fid)
        shutil.rmtree(self._fdir(fid), ignore_errors=True)
        tasks = {k: v for k, v in self._fset()["tasks"].items() if v != fid}
        self.store.set_setting("legal.form_tasks", tasks, "양식 지움")
        return True

    def fm_fav(self, fid, on=True):
        fm = self._form(fid)
        fm["fav"] = bool(on)
        self._form_save(fm)
        return True

    def fm_task(self, task, fid):
        tasks = dict(self._fset()["tasks"])
        if fid:
            self._form(fid)
            tasks[task] = fid
        else:
            tasks.pop(task, None)
        self.store.set_setting("legal.form_tasks", tasks, f"업무별 기본 양식: {task}")
        return tasks

    def fm_export(self, fid):
        fm = self._form(fid)
        path = excel.unique_path(self.export_dir(), f"{fm['name']}.양식", ".zip")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(os.path.join(self._fdir(fid), "form.pdf"), "form.pdf")
            z.writestr("form.json", json.dumps({k: fm[k] for k in ("name", "grp", "file", "pages", "fields", "font", "ver")}, ensure_ascii=False))
        self.reveal(path)
        return path

    def fm_import(self, path=None):
        path = path or self.choose_file("form")
        if not path:
            return None
        try:
            with zipfile.ZipFile(path) as z:
                meta = json.loads(z.read("form.json").decode("utf-8"))
                pdf = z.read("form.pdf")
        except Exception:
            raise ValueError("양식 파일(.양식.zip)이 아니에요")
        fid = uuid.uuid4().hex[:12]
        os.makedirs(self._fdir(fid), exist_ok=True)
        with open(os.path.join(self._fdir(fid), "form.pdf"), "wb") as f:
            f.write(pdf)
        fm = {"id": fid, "name": meta.get("name") or "가져온 양식", "grp": meta.get("grp") or "기타", "file": meta.get("file", ""),
              "pages": FM.page_info(os.path.join(self._fdir(fid), "form.pdf")), "fields": meta.get("fields") or [],
              "font": meta.get("font") or "myeongjo", "fav": False, "uses": 0, "used": "", "ver": meta.get("ver", 1),
              "created": now(), "by": self._me(), "draft": not meta.get("fields")}
        self._form_save(fm)
        return fid

    # ------------------------------------------------------------ 우리 회사 정보

    def fm_company(self):
        lg = self.store.settings.get("legal") or {}
        return {"creditor": lg.get("creditor") or {}, "agent": lg.get("agent", ""), "court": lg.get("court", ""),
                "info": self.legal.data.get("info") or {}, "items": self._fset()["items"], "font": self._fset()["font"],
                "seal": bool(self._seal_path()), "tasks": [[t, s, self._fset()["tasks"].get(t, "")] for t, s in TASKS],
                "forms": [{"id": f["id"], "name": f["name"]} for f in self._forms() if not f.get("draft")], "book": self.store.root}

    def fm_item_add(self, name, value=""):
        name = (name or "").strip()
        if not name:
            raise ValueError("항목 이름을 넣어 주세요")
        its = list(self._fset()["items"])
        if any(i["n"] == name for i in its) or any(i["n"] == name for i in FM.ITEMS):
            raise ValueError("같은 이름의 항목이 있어요")
        its.append({"k": "x_" + uuid.uuid4().hex[:6], "n": name, "value": value})
        self.store.set_setting("legal.form_items", its, f"양식 항목 더함: {name}")
        return its

    def fm_item_set(self, k, value=None, delete=False):
        its = [dict(i) for i in self._fset()["items"]]
        if delete:
            its = [i for i in its if i["k"] != k]
        else:
            for i in its:
                if i["k"] == k:
                    i["value"] = value or ""
        self.store.set_setting("legal.form_items", its, "양식 항목 바꿈")
        return its

    def fm_seal_set(self, path=None, remove=False):
        p = os.path.join(self._fdir(), "_seal.png")
        if remove:
            if os.path.isfile(p):
                os.remove(p)
            return False
        path = path or self.choose_file("image")
        if not path:
            return None
        from PIL import Image
        os.makedirs(self._fdir(), exist_ok=True)
        img = Image.open(path).convert("RGBA")
        img.thumbnail((600, 600))
        img.save(p, "PNG")
        return True

    # ------------------------------------------------------------ 대상 고르기

    def _base_vals(self):
        lg = self.store.settings.get("legal") or {}
        cr, info = lg.get("creditor") or {}, self.legal.data.get("info") or {}
        v = {"company": cr.get("name", ""), "company_addr": cr.get("addr", ""), "ceo": cr.get("rep", ""), "phone": cr.get("phone", ""),
             "agent": lg.get("agent", ""), "date": dt.date.today().isoformat(), "creditor": info.get("assignor", ""), "case_name": info.get("cause", "")}
        for i in self._fset()["items"]:
            if i.get("value"):
                v[i["k"]] = i["value"]
        return v

    def _case_index(self):
        return {self.store.case_no(c): c for c in self.store.active_cases()}

    def _case_of_debtor(self, d):
        cs = [c for c in (self._linked(d) if d else []) if not L.rehab_kind(c.get("dvs"))]  # 회생·파산 사건번호는 빼고
        if not cs:
            return None
        order = {"확정": 0, "진행": 1}
        return sorted(cs, key=lambda c: (order.get(c.get("status"), 2), -(c.get("year") or 0)))[0]

    def _from_debtor(self, d, v):
        v.update({"debtor": d.get("name", ""), "debtor_addr": d.get("addr", ""), "mgmt_no": d.get("key", ""),
                  "amount": int(float(d.get("principal") or 0) + float(d.get("interest") or 0)) or ""})
        c = self._case_of_debtor(d)
        if c:
            v["case_no"], v["court"] = self.store.case_no(c), c.get("court", "")
            v["case_name"] = (self.store.result(c["id"]).get("basic") or {}).get("csNm") or v.get("case_name", "")
        v["court"] = v.get("court") or d.get("court") or (self.store.settings.get("legal") or {}).get("court", "")
        return v

    def _target(self, tid, src, vals, did="", dlv="", notes=None, fid=""):
        d = self.legal.debtor(did) if did else None
        blk = self._rehab_of(did) if did else []
        cases = self._case_index()
        ref = {}
        c = cases.get(vals.get("case_no") or "")
        if c and c.get("court"):
            ref["court"] = c["court"]
        return {"tid": tid, "src": src, "did": did, "dlv": dlv, "name": vals.get("debtor") or (d or {}).get("name", ""), "vals": vals,
                "notes": notes or [], "ref": ref, "dup": self._dup(fid, did, vals.get("case_no", "")),
                "block": {"label": self._rstatus(blk[0])["label"]} if blk else None}

    def _dup(self, fid, did, case_no, days=30):
        if not fid:
            return ""
        since = (dt.datetime.now() - dt.timedelta(days=days)).strftime("%Y-%m-%d")
        for x in self.legal.data["docs"]:
            if x.get("form") == fid and x.get("at", "") >= since and ((did and x.get("did") == did) or (case_no and x.get("key") == case_no)):
                return x["at"][5:10].replace("-", ".")
        return ""

    def fm_targets(self, fid, src="dlv", keys=None, path=None, mapping=None):
        fm = self._form(fid)
        base = self._base_vals()
        out = []
        if src == "dlv":
            self._dlv_sync()
            for x in self.legal.data["dlv"].values():
                if x.get("done") or (keys and x["key"] not in keys):
                    continue
                d = self._dlv_debtor(x)
                c = self.store.cases.get(x.get("cid") or "") or {}
                v = dict(base)
                if d:
                    self._from_debtor(d, v)
                v.update({"case_no": x["case_no"], "court": c.get("court") or x.get("court") or v.get("court", ""), "debtor": (d or {}).get("name") or x.get("party", ""),
                          "reason": REASON_OF.get(x["reason"], x["reason"])})
                if c:
                    v["case_name"] = (self.store.result(c["id"]).get("basic") or {}).get("csNm") or v.get("case_name", "")
                act = x.get("act") or self._dlv_view(x, self._std())["rec"]
                v["req"] = REQ_OF.get(act, "")
                v["new_addr"] = x.get("new_addr") or (d["addr"] if d and d.get("addr") and (d.get("addr_changed") or "") >= (x.get("date") or "9") else "")
                out.append(self._target(x["key"], "dlv", v, (d or {}).get("id", ""), x["key"], fid=fid))
        elif src == "ledger":
            for d in self.legal.active_debtors():
                if keys and d["id"] not in keys:
                    continue
                out.append(self._target(d["id"], "ledger", self._from_debtor(d, dict(base)), d["id"], fid=fid))
        else:
            if not path:
                raise ValueError("엑셀 파일을 골라 주세요")
            _, rows = excel.read_table(path)
            hi = excel.find_header(rows)
            header, body = (rows[hi] if rows else []), [r for r in rows[hi + 1:] if any(str(x).strip() for x in r)]
            names = FM.items(self._fset()["items"])
            auto = {}
            for j, h in enumerate(header):
                hn = re.sub(r"\s", "", str(h))
                for k, al in XL_ALIAS.items():
                    if k not in auto and hn in [re.sub(r"\s", "", a) for a in al]:
                        auto[k] = j
                        break
                else:
                    for it in names:
                        if it.get("custom") and hn == re.sub(r"\s", "", it["n"]) and it["k"] not in auto:
                            auto[it["k"]] = j
            auto, src = self._xl_auto("form", [str(h) for h in header], auto)
            m = {k: int(v) for k, v in (mapping or {}).items() if str(v) not in ("", "-1")} if mapping is not None else auto
            if mapping is not None:
                self._xl_save("form", [str(h) for h in header], m)
            order = self._link("form")["by"]
            for ri, r in enumerate(body):
                g = lambda k: str(r[m[k]]).strip() if k in m and m[k] < len(r) and r[m[k]] is not None else ""  # noqa: E731
                raw = {k: g(k) for k in m}
                if not any(raw.values()):
                    continue
                v, notes = dict(base), []
                d, how = self.legal.match_debtor(raw.get("mgmt_no", ""), raw.get("debtor", ""), "", order)
                if d:
                    self._from_debtor(d, v)
                    if how == "name":
                        notes.append({"k": "debtor", "m": "이름만으로 채무자 원장과 이었어요. 동명이인이 아닌지 확인해 주세요."})
                for k, x in raw.items():
                    if not x:
                        continue
                    if k == "case_no":
                        y = FM.clean_case_no(x)
                        if y != x:
                            notes.append({"k": k, "m": f"사건번호 「{x}」 → 「{y}」로 정리했어요."})
                        x = y
                    elif k == "amount":
                        x = FM.to_int(x) or ""
                    elif k == "reason":
                        x = next((o for o in ("주소불명", "폐문부재", "수취인불명", "이사불명") if o in x.replace(" ", "")), x)
                    elif k == "req":
                        x = next((o for o in ("재송달", "특별송달", "공시송달") if o in x.replace(" ", "")), x)
                    v[k] = x
                for k in ("case_no", "court", "debtor_addr", "amount"):
                    if k in m and not raw.get(k) and v.get(k) and d:
                        notes.append({"k": k, "m": f"엑셀의 「{self._names().get(k, k)}」 칸이 비어 있어 채권 원장 값으로 채웠어요.", "filled": True})
                out.append(self._target(f"x{ri}", "xl", v, (d or {}).get("id", ""), notes=notes, fid=fid))
            return {"targets": out, "excel": {"name": os.path.basename(path), "header": [str(h) for h in header], "mapping": m, "auto": auto, "src": src if mapping is None else {},
                                              "rows": len(body)}, "items": names, "form": self._fsum(fm)}
        for t in out:  # 원장·송달 값도 사건번호 띄어쓰기는 정리
            cn = t["vals"].get("case_no")
            if cn and FM.clean_case_no(cn) != cn:
                t["notes"].append({"k": "case_no", "m": f"사건번호 「{cn}」 → 「{FM.clean_case_no(cn)}」로 정리했어요."})
                t["vals"]["case_no"] = FM.clean_case_no(cn)
        return {"targets": out, "items": FM.items(self._fset()["items"]), "form": self._fsum(fm)}

    # ------------------------------------------------------------ 검수

    def fm_check(self, fid, items, full=False, fields=None, font=None):
        """items: [{tid, vals, ref}] → 사람마다 빈 칸·넘침·대장과 다른 값 (fields를 주면 저장 전 칸으로 본다)"""
        fm = self._form(fid)
        names = self._names()
        out = {}
        for t in items:
            out[t["tid"]] = FM.check(fields if fields is not None else fm["fields"], t.get("vals") or {}, names,
                                     font or fm.get("font") or "myeongjo", t.get("ref"), full)
        return out

    def fm_precheck(self, fid, items):
        """저장 직전: 회생·파산 관리 가부와 중복을 다시 본다."""
        late, dups = [], []
        for t in items:
            did = t.get("did")
            if did:
                self._rehab_sync()
                blk = self._rehab_of(did)
                if blk:
                    late.append({"tid": t["tid"], "name": t.get("name", ""), "label": self._rstatus(blk[0])["label"],
                                 "event": blk[0].get("event") or (self._rstatus(blk[0]).get("event") or "")})
            dd = self._dup(fid, did, (t.get("vals") or {}).get("case_no", ""))
            if dd:
                dups.append({"tid": t["tid"], "name": t.get("name", ""), "date": dd})
        return {"late": late, "dups": dups, "at": now()[11:16]}

    # ------------------------------------------------------------ 저장 · 인쇄

    def fm_make(self, fid, items, mode="each", opts=None):
        opts = opts or {}
        fm = self._form(fid)
        if fm.get("draft"):
            raise ValueError("칸을 정하고 저장한 양식만 쓸 수 있어요")
        pre = self.fm_precheck(fid, items)
        skip = {x["tid"] for x in pre["late"]}
        items = [t for t in items if t["tid"] not in skip]
        if not items:
            raise ValueError("만들 서류가 없어요" + (" — 회생·파산으로 빠졌어요" if skip else ""))
        names = self._names()
        bad = [t.get("name") for t in items if FM.check(fm["fields"], t["vals"], names, fm.get("font"), None, False)["status"] == "bad"]
        if bad:
            raise ValueError(f"빈 칸이 남은 서류가 있어요: {', '.join(bad[:5])}")
        seal = self._seal_path() if opts.get("seal") else ""
        if any(f["type"] == "seal" for f in fm["fields"]) and opts.get("seal") and not seal:
            raise ValueError("인감 그림이 없어요 — 우리 회사 정보에서 넣어 주세요")
        src = os.path.join(self._fdir(fid), "form.pdf")
        folder = os.path.join(self.export_dir(), "법조치 서류", f"{dt.datetime.now():%Y-%m-%d %H%M} {excel.safe_name(fm['name'])}")
        made = []
        for t in items:
            t["vals"]["__seal"] = bool(seal)
        if mode == "each":
            for t in items:
                v = t["vals"]
                nm = "_".join(x for x in (fm["name"], v.get("debtor") or t.get("name"), v.get("case_no")) if x)
                made.append(FM.build(src, fm["pages"], fm["fields"], [v], excel.unique_path(folder, excel.safe_name(nm), ".pdf"),
                                     fm.get("font") or "myeongjo", seal))
        else:
            made.append(FM.build(src, fm["pages"], fm["fields"], [t["vals"] for t in items],
                                 excel.unique_path(folder, excel.safe_name(f"{fm['name']}_묶음_{len(items)}건_{dt.date.today():%Y%m%d}"), ".pdf"),
                                 fm.get("font") or "myeongjo", seal))
        printed = False
        if mode == "print":
            from core import printing
            pr = opts.get("printer") or ""
            if pr:
                printing.print_pdf(made[0], pr, int(opts.get("copies") or 1))
                self.store.set_setting("legal.printer", pr)
                printed = pr
            else:
                printed = FM.print_file(made[0]) and "기본 PDF 프로그램"
        for i, t in enumerate(items):
            v = t["vals"]
            self.legal.data["docs"].insert(0, {"at": now(), "type": f"양식:{fm['name']}", "form": fid, "ver": fm.get("ver", 0), "did": t.get("did", ""),
                                               "name": v.get("debtor") or t.get("name", ""), "key": v.get("case_no", ""),
                                               "file": made[i] if mode == "each" else made[0], "seal": bool(seal), "by": self._me()})
            d = self.legal.debtor(t["did"]) if t.get("did") else None
            if d and opts.get("log", True):
                self.legal.log(d, f"{fm['name']} 작성 (회사 양식{' · 인감' if seal else ''})", self._me())
        if opts.get("dlv_done", True):
            keys = [t["dlv"] for t in items if t.get("dlv")]
            if keys:
                self.legal.save()
                self.lg_dlv_done(keys, use_rec=True, note=f"{fm['name']} — 회사 양식으로 만듦")
        fm["uses"] = fm.get("uses", 0) + len(items)
        fm["used"] = dt.date.today().isoformat()
        self._form_save(fm)
        self.legal.save()
        if not printed:
            self.reveal(made[0])
        self._act(f"{fm['name']} {len(items)}건을 " + (f"「{printed}」로 인쇄했어요" if printed else "PDF로 저장했어요") +
                  (f" · 회생·파산으로 {len(pre['late'])}건 뺌" if pre["late"] else ""), "doc", "fm")
        return {"count": len(items), "files": len(made), "folder": folder, "skipped": pre["late"], "printed": printed}

    def fm_printers(self):
        """이 PC에 연결된 인쇄기 (PDF로 저장하는 인쇄기도 포함)"""
        from core import printing
        lst = printing.list_printers()
        last = (self.store.settings.get("legal") or {}).get("printer", "")
        pick = last if any(p["name"] == last for p in lst) else next((p["name"] for p in lst if p["default"]), "")
        return {"printers": lst, "pick": pick, "win": printing.WIN}

    def fm_sample(self):
        """시연·처음 쓰는 사람용: 견본 주소보정서 양식을 넣는다."""
        from form_sample import make
        os.makedirs(self._fdir(), exist_ok=True)
        tmp = os.path.join(self._fdir(), "_sample_tmp.pdf")
        make(tmp)
        try:
            fid = self.fm_add(tmp)
        finally:
            os.remove(tmp)
        fm = self._form(fid)
        fm["name"], fm["file"], fm["grp"] = "주소보정서 (견본)", "주소보정서_견본.pdf", "송달"
        self._form_save(fm)
        return fid
