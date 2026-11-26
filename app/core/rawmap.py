# -*- coding: utf-8 -*-
"""회수 분석 — 채권마다 다른 원자료를 공통 양식으로 맞추기.

전산에서 뽑은 원자료는 채권(포트폴리오)마다 칸 이름과 값이 다르다.
  · 칸 맞추기: 「차주번호」 → 채무자키, 「수납일자」 → 입금일 …  (머리글 낱말 · 비슷한 말로 자동 제안)
  · 값 맞추기: 「가상계좌입금」 → 본인변제, 「채권압류및추심명령」 → 압류추심 …  (낱말 규칙으로 자동 제안)
한 번 맞춘 것은 채권 폴더에 기억해 두고, 같은 머리글의 파일은 다음부터 그대로 채운다.
맞춘 결과는 「담아 둔 자료」(시트별 1개)에 쌓았다가, 점검표를 보고 한꺼번에 넣는다.
"""
import datetime as dt
import gzip
import json
import os
import re

from . import recovery as RC

# ---------------------------------------------------------------- 칸 이름 비슷한 말
SYN = {
    "채무자키": ["채무자번호", "차주번호", "고객번호", "채무자id", "차주id", "고객id", "채무자코드", "고객코드", "차주코드", "채무자관리번호"],
    "계좌키": ["계좌번호", "대출번호", "여신번호", "채권번호", "계약번호", "계좌id", "대출계좌", "채권관리번호"],
    "채무자명": ["성명", "이름", "고객명", "차주명", "채무자"],
    "담당자": ["담당", "담당자명", "관리자", "채권관리자", "관리담당", "담당직원"],
    "포트폴리오": ["채권명", "매입채권", "풀", "pool", "채권구분", "매각사"],
    "채권잔액": ["잔액", "총잔액", "채권액", "미수잔액", "잔존채권", "채권잔액(원)", "총채권액"],
    "원금": ["원금잔액", "대출원금", "잔존원금"],
    "법비용": ["법적비용", "소송비용", "집행비용"],
    "시효도래일": ["시효", "시효완성일", "소멸시효", "시효만료일", "시효일"],
    "주민번호앞7": ["주민번호", "주민등록번호", "생년월일"],
    "기준일": ["기준일자", "추출일", "기준"],
    "법조치키": ["법조치번호", "법적조치번호", "조치번호", "법조치id", "조치id", "법조치관리번호"],
    "법조치구분": ["조치구분", "법조치유형", "조치유형", "법적조치구분", "법조치종류", "조치종류"],
    "법조치세부": ["세부구분", "상세구분", "조치세부", "법조치상세", "세부유형"],
    "법원": ["관할법원", "법원명", "관할"],
    "사건번호": ["사건no", "법원사건번호"],
    "신청일": ["신청일자", "접수일", "접수일자", "신청접수일"],
    "확정일자": ["확정일", "확정"],
    "인용일자": ["인용일", "결정일", "결정일자", "명령일"],
    "송달일": ["송달일자", "송달"],
    "제3채무자유형": ["제3채무자구분", "제삼채무자유형", "피압류채권종류", "압류대상", "제3채무자종류", "압류채권구분"],
    "제3채무자명": ["제3채무자", "제삼채무자", "제삼채무자명", "은행명", "금융기관"],
    "결정금액": ["압류금액", "결정액", "안분금액", "압류액", "청구금액"],
    "입금일": ["입금일자", "수납일", "수납일자", "거래일자", "거래일", "회수일", "회수일자"],
    "입금액": ["수납액", "입금금액", "금액", "회수금액", "회수액", "거래금액"],
    "입금구분": ["입금유형", "수납구분", "입금종류", "거래구분", "회수구분", "수납유형", "입금방법"],
    "제3채무자": ["입금은행", "보낸은행", "지급처", "제3채무자명", "제삼채무자", "은행명", "추심은행"],
    "조정구분": ["약정구분", "조정유형", "약정유형"],
    "약정일": ["약정일자", "조정일", "조정일자"],
    "시작일": ["납입시작일", "시작일자", "첫납입일"],
    "회차": ["회차수", "분납회차", "납입회차", "약정회차", "총회차"],
    "회차당금액": ["월납입액", "회차금액", "분납금액", "월납입금"],
    "약정총액": ["약정금액", "조정금액", "약정액"],
    "상태": ["약정상태", "진행상태", "처리상태"],
    "해제일": ["해제일자"],
    "해제사유원문": ["해제사유", "사유", "해제내용"],
    "해제사유구분": ["사유구분"],
    "요청일": ["요청일자", "추심요청일", "전자추심일"],
    "추심요청액": ["요청금액", "요청액", "추심요청금액"],
    "구분": ["채무조정구분", "제도", "조정제도", "제도구분"],
    "상태일": ["상태변경일", "폐지일", "실효일", "변경일"],
}
# 시트마다 따로 쓰는 비슷한 말 (같은 이름이 시트마다 다른 뜻일 때)
SYN_SHEET = {("08_채무조정", "상태"): ["진행상태", "결과", "상태구분"], ("08_채무조정", "신청일"): ["신청일자", "접수일"]}

# ---------------------------------------------------------------- 값 맞추기 (코드표가 있는 칸)
VALUE_FIELDS = {
    ("02_법조치", "법조치구분"): "법조치구분", ("02_법조치", "법조치세부"): "법조치세부", ("04_입금", "입금구분"): "입금구분",
    ("05_조정", "조정구분"): "조정구분", ("06_해제", "해제사유구분"): "해제사유구분",
    ("08_채무조정", "구분"): "채무조정구분", ("08_채무조정", "상태"): "채무조정상태",
}
CODE_LISTS = dict(RC.CODES, 법조치세부=["예금", "증권", "급여", "보험", "기타채권", "전자소송", "전자독촉", "소송전이",
                                    "부동산강제경매", "부동산임의경매", "동산", "기타"])
VALUE_RULES = {  # 원문 낱말 → 코드 (위에서부터 처음 맞는 것)
    "입금구분": [("추심", "추심금"), ("배당", "배당금"), ("공탁", "공탁금"), ("약정|분납|분할|회차", "약정분납"), ("보증", "보증인"),
              ("제3자|제삼자|대위", "제3자"), ("(?<!가)상계", "상계"), ("본인|가상계좌|무통장|자동이체|계좌이체|입금|수납|변제|현금|카드", "본인변제")],
    "법조치구분": [("가압류", "가압류"), ("지급명령|독촉", "지급명령"), ("압류|추심|전부", "압류추심"), ("경매", "경매"),
              ("명시", "재산명시"), ("재산조회", "재산조회"), ("소송|소장|판결|가소|가단|가합|본안", "소송")],
    "법조치세부": [("예금|은행|금융", "예금"), ("증권|주식", "증권"), ("급여|임금|급료|봉급|퇴직", "급여"), ("보험", "보험"),
              ("전자소송", "전자소송"), ("전자독촉", "전자독촉"), ("소송전이|이의", "소송전이"), ("임의경매", "부동산임의경매"),
              ("강제경매|부동산", "부동산강제경매"), ("동산|유체", "동산")],
    "조정구분": [("분납|분할", "분납"), ("화해", "화해"), ("감면|탕감", "감면"), ("약정", "약정")],
    "해제사유구분": [(p, c) for p, c in RC.REL_RULES],
    "채무조정구분": [("신복|신용회복|워크아웃|채무조정|프리", "신용회복"), ("파산|면책", "파산"), ("회생", "개인회생")],
    "채무조정상태": [("폐지", "폐지"), ("실효|취소", "실효"), ("인가", "인가"), ("면책", "면책"), ("완제|완납|졸업|종결", "완제"),
               ("진행|신청|개시|접수", "진행")],
}
FALLBACK = {"입금구분": "기타", "법조치구분": "기타", "법조치세부": "기타", "조정구분": "기타", "해제사유구분": "모름",
            "채무조정구분": "", "채무조정상태": "진행"}


def _norm(h):
    return re.sub(r"[\s_\-·()\[\]{}/.:]+", "", str(h or "")).lower()


def suggest_value(code_list, raw):
    """원문 값 → (코드, 어떻게) · 어떻게: same(이미 코드) · auto(낱말 규칙) · ''(못 찾음 → 기본값)"""
    v = str(raw or "").strip()
    codes = CODE_LISTS[code_list]
    if v in codes:
        return v, "same"
    if _norm(v) in {_norm(c): c for c in codes}:
        return {_norm(c): c for c in codes}[_norm(v)], "same"
    for pat, code in VALUE_RULES.get(code_list, []):
        if re.search(pat, v, re.I):
            return code, "auto"
    return FALLBACK.get(code_list, ""), ""


# ---------------------------------------------------------------- 파일 읽기

def _cell(v):
    if v is None:
        return ""
    if isinstance(v, dt.datetime):
        return v.strftime("%Y-%m-%d") if (v.hour, v.minute, v.second) == (0, 0, 0) else v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def read_any(path):
    """엑셀(.xlsx .xlsm .xls) · CSV → [(시트 이름, 줄 목록)]"""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            return [(ws.title, [[_cell(v) for v in r] for r in ws.iter_rows(values_only=True)]) for ws in wb.worksheets]
        finally:
            wb.close()
    if ext == ".xls":
        import xlrd
        wb = xlrd.open_workbook(path)
        out = []
        for ws in wb.sheets():
            rows = []
            for i in range(ws.nrows):
                row = []
                for j in range(ws.ncols):
                    c = ws.cell(i, j)
                    row.append(_cell(xlrd.xldate.xldate_as_datetime(c.value, wb.datemode)) if c.ctype == xlrd.XL_CELL_DATE else _cell(c.value))
                rows.append(row)
            out.append((ws.name, rows))
        return out
    if ext in (".csv", ".txt"):
        from . import excel
        name, rows = excel.read_table(path)
        return [(os.path.splitext(os.path.basename(path))[0], rows)]
    raise ValueError("엑셀(.xlsx .xls) 또는 .csv 파일만 읽을 수 있어요")


def header_row(rows):
    """원자료 위쪽 제목 줄을 건너뛰고 머리글 줄 번호를 찾는다 (글자 칸이 가장 많은 줄, 위 15줄 안)"""
    best, bi = -1, 0
    for i, r in enumerate(rows[:15]):
        n = sum(1 for x in r if isinstance(x, str) and x.strip() and not re.fullmatch(r"[\d.,\-\s:]+", x))
        if n > best:
            best, bi = n, i
    return bi


def sig_of(header):
    return "|".join(_norm(h) for h in header if _norm(h))


# ---------------------------------------------------------------- 칸 맞추기

def _field_names(sheet, field):
    return [field] + SYN_SHEET.get((sheet, field), []) + SYN.get(field, [])


def guess_cols(sheet, header):
    """{칸: 머리글 번호} — 똑같은 이름 > 비슷한 말 > 이름이 들어 있음. 한 머리글은 한 칸에만."""
    H = [_norm(h) for h in header]
    used, out = set(), {}
    fields = [f for f, _, _ in RC.SHEETS[sheet]]
    for level in ("exact", "syn", "contains"):
        for f in fields:
            if f in out:
                continue
            names = [_norm(x) for x in _field_names(sheet, f)]
            for i, h in enumerate(H):
                if i in used or not h:
                    continue
                hit = (level == "exact" and h == names[0]) or (level == "syn" and h in names[1:]) or \
                      (level == "contains" and len(h) <= 14 and any(len(n) >= 2 and n in h for n in names))
                if hit:
                    out[f] = i
                    used.add(i)
                    break
    return out


def guess_sheet(name, header):
    """→ (시트 종류, 점수). 시트 이름이 양식과 같으면 그대로, 아니면 꼭 필요한 칸이 많이 맞는 종류."""
    n = _norm(name)
    for sh in RC.SHEETS:
        if n in (_norm(sh), _norm(sh.split("_", 1)[1])):
            return sh, 99
    best, score = "", 0
    for sh, spec in RC.SHEETS.items():
        cols = guess_cols(sh, header)
        s = sum(2 if req else 1 for f, req, _ in spec if f in cols)
        need = [f for f, req, _ in spec if req]
        if all(f in cols for f in need):
            s += 3
        if s > score:
            best, score = sh, s
    return (best, score) if score >= 4 else ("", score)


class Matcher:
    """채권 폴더/recovery/maps.json (맞춘 것 기억) · staged/<시트>.json.gz (담아 둔 자료)"""

    def __init__(self, root):
        self.root = os.path.join(root, "recovery")
        self._files = {}  # (경로, 고친 때) → 읽은 시트들

    def _p(self, *a):
        return os.path.join(self.root, *a)

    # 기억
    def maps(self):
        try:
            with open(self._p("maps.json"), encoding="utf-8") as f:
                m = json.load(f)
        except Exception:
            m = {}
        m.setdefault("cols", {})
        m.setdefault("values", {})
        return m

    def save_maps(self, m):
        os.makedirs(self.root, exist_ok=True)
        tmp = self._p("maps.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self._p("maps.json"))

    # 파일
    def sheets(self, path):
        key = (path, os.path.getmtime(path))
        if key not in self._files:
            self._files = {key: read_any(path)}  # 큰 파일을 여러 개 들고 있지 않게 하나만
        return self._files[key]

    def open(self, path):
        """파일 → 시트마다 머리글 · 예시 줄 · 무슨 자료인지 · 칸 맞추기(기억 > 자동)"""
        if not path or not os.path.isfile(path):
            raise ValueError("파일을 찾을 수 없어요: " + str(path or ""))
        sheets = self.sheets(path)
        names = [n for n, _ in sheets]
        template = any(_norm(n) in (_norm("00_안내"),) for n in names) or sum(1 for n in names if n in RC.SHEETS) >= 2
        m = self.maps()
        out = []
        for name, rows in sheets:
            if name in ("00_안내", "코드표", "99_해제사유_규칙") or not any(any(x not in ("", None) for x in r) for r in rows[:50]):
                continue
            hi = header_row(rows)
            header = [str(h if h is not None else "").strip() for h in rows[hi]] if rows else []
            body = [r for r in rows[hi + 1:] if any(x not in ("", None) for x in r)]
            kind, score = guess_sheet(name, header)
            sig = sig_of(header)
            saved = next((k for k, v in m["cols"].items() if v.get("sig") == sig), None)
            if saved:
                kind = m["cols"][saved]["kind"]
                cols = {f: header.index(h) for f, h in m["cols"][saved]["cols"].items() if h in header}
            else:
                cols = guess_cols(kind, header) if kind else {}
            out.append({"name": name, "header": header, "hi": hi, "rows": len(body), "sample": [[_cell(x) for x in r] for r in body[:6]],
                        "kind": kind, "auto": not saved and bool(kind), "saved": bool(saved), "cols": cols})
        return {"file": os.path.basename(path), "template": template, "sheets": out,
                "kinds": [{"id": k, "name": RC.SHEET_NAMES[k],
                           "fields": [{"f": f, "req": bool(req), "kind": t, "codes": VALUE_FIELDS.get((k, f), "")} for f, req, t in spec]}
                          for k, spec in RC.SHEETS.items()]}

    def values(self, path, sheet, kind, cols):
        """값 맞추기가 필요한 칸의 원문 값 목록 (많은 순 200개) + 기억 · 자동 제안"""
        rows = dict(self.sheets(path))[sheet]
        hi = header_row(rows)
        m = self.maps()
        out = []
        for (k, f), cl in VALUE_FIELDS.items():
            if k != kind or cols.get(f) in (None, -1, ""):
                continue
            i = int(cols[f])
            cnt = {}
            for r in rows[hi + 1:]:
                v = str(r[i]).strip() if i < len(r) and r[i] not in (None, "") else ""
                if v:
                    cnt[v] = cnt.get(v, 0) + 1
            memo = m["values"].get(cl, {})
            vals = []
            for v, n in sorted(cnt.items(), key=lambda x: -x[1])[:200]:
                if v in memo:
                    code, how = memo[v], "saved"
                else:
                    code, how = suggest_value(cl, v)
                vals.append({"raw": v, "n": n, "code": code, "how": how})
            out.append({"field": f, "list": cl, "codes": CODE_LISTS[cl], "values": vals, "more": max(0, len(cnt) - 200)})
        return out

    # 담기
    def stage(self, path, items):
        """items: [{sheet, kind, cols:{칸: 머리글 번호}, values:{칸: {원문: 코드}}}] → 맞춘 것 기억 + 시트별로 담아 둠"""
        sheets = dict(self.sheets(path))
        m = self.maps()
        done = []
        for it in items:
            kind = it.get("kind")
            if kind not in RC.SHEETS:
                continue
            rows = sheets[it["sheet"]]
            hi = header_row(rows)
            header = [str(h if h is not None else "").strip() for h in rows[hi]]
            cols = {f: int(i) for f, i in (it.get("cols") or {}).items() if i not in (None, "", -1, "-1")}
            vmap = it.get("values") or {}
            spec = RC.SHEETS[kind]
            miss = [f for f, req, _ in spec if req and f not in cols]
            if miss:
                raise ValueError(f"「{RC.SHEET_NAMES[kind]}」에 꼭 필요한 칸을 골라 주세요: " + ", ".join(miss))
            # 기억: 머리글 모양 → 칸 맞추기 / 원문 값 → 코드
            sig = sig_of(header)
            m["cols"][f"{kind}:{sig[:120]}"] = {"kind": kind, "sig": sig, "cols": {f: header[i] for f, i in cols.items() if i < len(header)},
                                                "at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "file": os.path.basename(path)}
            for f, mp in vmap.items():
                cl = VALUE_FIELDS.get((kind, f))
                if cl:
                    m["values"].setdefault(cl, {}).update({k: v for k, v in mp.items() if v})
            out_rows = []
            for r in rows[hi + 1:]:
                if not any(x not in ("", None) for x in r):
                    continue
                row = []
                for f, _, _ in spec:
                    i = cols.get(f)
                    v = _cell(r[i]) if i is not None and i < len(r) else ""
                    cl = VALUE_FIELDS.get((kind, f))
                    if cl and v not in ("", None):
                        sv = str(v).strip()
                        v = (vmap.get(f) or {}).get(sv) or m["values"].get(cl, {}).get(sv) or suggest_value(cl, sv)[0]
                    row.append(v)
                out_rows.append(row)
            self._write_staged(kind, {"file": os.path.basename(path), "sheet": it["sheet"], "at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                                      "rows": out_rows})
            done.append({"kind": kind, "name": RC.SHEET_NAMES[kind], "rows": len(out_rows)})
        self.save_maps(m)
        return done

    def _write_staged(self, kind, obj):
        os.makedirs(self._p("staged"), exist_ok=True)
        tmp = self._p("staged", kind + ".json.gz.tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, self._p("staged", kind + ".json.gz"))

    def staged(self, with_rows=False):
        out = {}
        for kind in RC.SHEETS:
            p = self._p("staged", kind + ".json.gz")
            if os.path.isfile(p):
                with gzip.open(p, "rt", encoding="utf-8") as f:
                    o = json.load(f)
                if not with_rows:
                    o = {k: v for k, v in o.items() if k != "rows"} | {"n": len(o.get("rows") or [])}
                out[kind] = o
        return out

    def unstage(self, kind=None):
        for k in ([kind] if kind else list(RC.SHEETS)):
            p = self._p("staged", k + ".json.gz")
            if os.path.isfile(p):
                os.remove(p)

    def raw(self):
        """담아 둔 자료 → parse_raw 에 넣는 {시트: [머리글, 줄...]}"""
        return {k: [[f for f, _, _ in RC.SHEETS[k]]] + o["rows"] for k, o in self.staged(with_rows=True).items()}

    def forget(self, kind=None):
        m = self.maps()
        m["cols"] = {k: v for k, v in m["cols"].items() if kind and v.get("kind") != kind}
        if not kind:
            m["values"] = {}
        self.save_maps(m)
