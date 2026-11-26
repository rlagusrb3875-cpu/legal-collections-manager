# -*- coding: utf-8 -*-
"""회수 분석 — 화면(recovery.html)에서 부르는 rc_* 메서드.

rc_info · rc_load        넣은 자료 알려 주기 · 화면으로 넘기기 (크면 나눠서)
rc_check · rc_apply      공통 양식 엑셀 점검 → 넣기
rc_report                점검표 엑셀
rc_state · rc_state_save 압류 판단 · 처리함 · 계획 · 기준값 기록
rc_save_table            화면 표 → 엑셀 (내보내기 폴더)
rc_sample · rc_template  예시 파일 · 빈 공통 양식
rc_clear                 넣은 자료 지우기 (백업은 남김)
rc_raw_open · rc_raw_values · rc_raw_stage   원자료 칸·값 맞추기 → 담아 두기 (채권마다 기억)
rc_staged · rc_unstage · rc_apply_staged     담아 둔 자료 점검표 → 넣기
rc_maps · rc_forget                          기억한 칸·값 맞추기 보기 · 지우기
rc_rehab                                     회생·파산 관리의 폐지결정 (채무자키 · 날짜)
"""
import base64
import datetime as dt
import os

from core import excel
from core import recovery as RC
from core.rawmap import Matcher

CHUNK = 3_000_000  # 화면으로 한 번에 넘기는 글자 수


class RecoveryMixin:
    @property
    def rc(self):
        root = self.store.root
        if getattr(self, "_rc", None) is None or self._rc.root != os.path.join(root, "recovery"):
            self._rc = RC.RecoveryStore(root)
        return self._rc

    def _rc_out(self, name):
        d = self.export_dir()
        os.makedirs(d, exist_ok=True)
        return excel.unique_path(d, excel.safe_name(name))

    def rc_info(self):
        h = self.rc.history()
        return {"has": self.rc.has(), "demo": bool(getattr(self, "demo", False)), "last": h[0] if h else None, "history": h[:12],
                "export_dir": self.export_dir(), "book": self.book}

    def rc_load(self, i=0):
        s = self.rc.blob()
        if s is None:
            return None
        n = max(1, -(-len(s) // CHUNK))
        i = int(i or 0)
        return {"n": n, "i": i, "s": s[i * CHUNK:(i + 1) * CHUNK]}

    def _rc_parse(self, path):
        if not path or not os.path.isfile(path):
            raise ValueError("파일을 찾을 수 없어요: " + str(path or ""))
        if os.path.splitext(path)[1].lower() not in (".xlsx", ".xlsm"):
            raise ValueError("공통 양식 엑셀(.xlsx · .xlsm)만 넣을 수 있어요")
        key = (path, os.path.getmtime(path))
        c = getattr(self, "_rc_cache", None)
        if c and c[0] == key:
            return c[1], c[2]
        data, rep = RC.parse(path)
        rep["file"] = os.path.basename(path)
        self._rc_cache = (key, data, rep)
        return data, rep

    def rc_check(self, path):
        _, rep = self._rc_parse(path)
        return rep

    def rc_apply(self, path):
        data, rep = self._rc_parse(path)
        if not rep["ok"]:
            raise ValueError("01_채권 · 02_법조치가 있어야 넣을 수 있어요. 점검표의 오류를 먼저 고쳐 주세요.")
        info = {"at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "file": rep["file"], "asof": rep["asof"], "counts": rep["counts"],
                "errors": rep["errors"], "warns": rep["warns"], "by": self.store.settings.get("me") or os.environ.get("USERNAME", "")}
        self.rc.save_data(data, info)
        self._rc_cache = None
        return info

    def rc_report(self, path):
        _, rep = self._rc_parse(path)
        out = self._rc_out(f"회수자료_점검표_{dt.date.today():%y%m%d}")
        return RC.write_report(out, rep, rep.get("file", ""))

    def rc_state(self, demo=False):
        return self.rc.state(bool(demo))

    def rc_state_save(self, state, demo=False):
        self.rc.save_state(state or {}, bool(demo))
        return True

    def rc_save_table(self, name, head, rows):
        from openpyxl import Workbook
        from openpyxl.styles import Font
        base = os.path.splitext(name)[0]
        out = self._rc_out(base)
        wb = Workbook(write_only=True)
        ws = wb.create_sheet(base[:31])
        from openpyxl.cell import WriteOnlyCell
        hr = []
        for h in head:
            c = WriteOnlyCell(ws, value=h)
            c.font = Font(bold=True)
            hr.append(c)
        ws.append(hr)
        for r in rows or []:
            ws.append(r)
        ws.freeze_panes = "A2"
        wb.save(out)
        return out

    def rc_sample(self, sheets):
        out = self._rc_out(f"회수자료_예시_{dt.date.today():%y%m%d}")
        return RC.write_template_rows(out, sheets or {})

    def rc_template(self, b64):
        out = self._rc_out("법조치회수분석_공통양식_v2")
        with open(out, "wb") as f:
            f.write(base64.b64decode(b64))
        return out

    # ------------------------------------------------------------ 원자료 맞추기 → 담아 두기 → 넣기
    @property
    def rcm(self):
        root = self.store.root
        if getattr(self, "_rcm", None) is None or self._rcm.root != os.path.join(root, "recovery"):
            self._rcm = Matcher(root)
        return self._rcm

    def rc_raw_open(self, path):
        return self.rcm.open(path)

    def rc_raw_values(self, path, sheet, kind, cols):
        return self.rcm.values(path, sheet, kind, cols or {})

    def rc_raw_stage(self, path, items):
        done = self.rcm.stage(path, items or [])
        self._rc_stage_rep = None
        return {"done": done, **self.rc_staged()}

    def _rc_staged_parse(self):
        st = self.rcm.staged()
        key = tuple((k, v.get("at"), v.get("n")) for k, v in sorted(st.items()))
        c = getattr(self, "_rc_stage_rep", None)
        if c and c[0] == key:
            return c[1], c[2]
        if not st:
            return None, None
        data, rep = RC.parse_raw(self.rcm.raw())
        rep["file"] = " · ".join(sorted({v["file"] for v in st.values()}))
        self._rc_stage_rep = (key, data, rep)
        return data, rep

    def rc_staged(self):
        st = self.rcm.staged()
        kinds = [{"kind": k, "name": RC.SHEET_NAMES[k], "need": k in RC.NEED_SHEETS, **({"file": st[k]["file"], "sheet": st[k].get("sheet"), "at": st[k]["at"],
                                                                                     "n": st[k]["n"]} if k in st else {})} for k in RC.SHEETS]
        _, rep = self._rc_staged_parse()
        return {"kinds": kinds, "report": rep}

    def rc_unstage(self, kind=None):
        self.rcm.unstage(kind)
        self._rc_stage_rep = None
        return self.rc_staged()

    def rc_apply_staged(self):
        data, rep = self._rc_staged_parse()
        if not rep or not rep["ok"]:
            raise ValueError("채권 목록(01)과 법조치(02)를 담아야 넣을 수 있어요. 점검표의 오류를 먼저 확인해 주세요.")
        info = {"at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "file": rep["file"], "asof": rep["asof"], "counts": rep["counts"],
                "errors": rep["errors"], "warns": rep["warns"], "by": self.store.settings.get("me") or os.environ.get("USERNAME", "")}
        self.rc.save_data(data, info)
        return info

    def rc_staged_report(self):
        _, rep = self._rc_staged_parse()
        if not rep:
            raise ValueError("담아 둔 자료가 없어요")
        out = self._rc_out(f"회수자료_점검표_{dt.date.today():%y%m%d}")
        return RC.write_report(out, rep, rep.get("file", ""))

    def rc_maps(self):
        m = self.rcm.maps()
        return {"cols": sorted(({"kind": v["kind"], "name": RC.SHEET_NAMES.get(v["kind"], v["kind"]), "file": v.get("file", ""), "at": v.get("at", ""),
                                 "n": len(v.get("cols") or {})} for v in m["cols"].values()), key=lambda x: x["at"], reverse=True),
                "values": {k: len(v) for k, v in m["values"].items()}}

    def rc_forget(self, kind=None):
        self.rcm.forget(kind)
        return self.rc_maps()

    def rc_rehab(self):
        """종합관리 회생·파산 관리에서 폐지결정이 난 사건 → [채무자키, 구분, 날짜(YYYY-MM-DD)]"""
        out = []
        try:
            items = self.legal.data["rehab"].values()
        except Exception:
            return out
        for r in items:
            try:
                m = self._rstatus(r)
            except Exception:
                continue
            if "폐지" not in (m.get("event") or ""):
                continue
            d = self.legal.debtors.get(r.get("did") or "") or {}
            key = str(d.get("key") or "").strip()
            day = RC.parse_date(m.get("date") or "")
            if key and day:
                out.append([key, "파산" if "파산" in (r.get("kind") or "") else "개인회생", RC.date_of(day).isoformat()])
        return out

    def rc_clear(self):
        self.rc.clear()
        return True
