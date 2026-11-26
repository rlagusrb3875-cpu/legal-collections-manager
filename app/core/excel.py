# -*- coding: utf-8 -*-
"""엑셀 읽기(사건 목록) · 엑셀 쓰기(조회 결과, 월간 보고서, 시효 앱 보내기, 양식)."""
import csv
import datetime as dt
import os
import re

from .caseno import CourtNames, parse_case_no
from .rules import hearings, row_text, ymd

FIELDS = [  # (키, 화면 이름, 머리글에서 찾을 말)
    ("court", "법원", ["관할법원", "법원명", "법원", "관할"]),
    ("case", "사건번호", ["사건번호", "사건 번호", "사건"]),
    ("year", "연도", ["사건연도", "연도", "년도"]),
    ("dvs", "사건구분", ["사건구분", "사건부호", "구분"]),
    ("serial", "번호", ["일련번호", "사건일련번호", "번호"]),
    ("party", "당사자 이름", ["당사자명", "당사자", "채무자명", "채무자", "피고", "성명", "이름", "상대방"]),
    ("owner", "담당", ["담당자", "담당"]),
    ("memo1", "메모 1", ["계좌번호", "계좌", "고객번호", "관리번호", "메모1", "메모 1", "메모"]),
    ("memo2", "메모 2", ["메모2", "메모 2", "비고"]),
]


# ---------------------------------------------------------------- 읽기

def read_table(path):
    """파일 → (시트 이름, 행 목록[list[str]])"""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = [[_cell(v) for v in r] for r in ws.iter_rows(values_only=True)]
        name = ws.title
        wb.close()
        return name, rows
    if ext == ".xls":
        import xlrd
        wb = xlrd.open_workbook(path)
        ws = wb.sheet_by_index(0)
        rows = []
        for i in range(ws.nrows):
            row = []
            for j in range(ws.ncols):
                cell = ws.cell(i, j)
                if cell.ctype == xlrd.XL_CELL_DATE:
                    row.append(_cell(xlrd.xldate.xldate_as_datetime(cell.value, wb.datemode)))
                else:
                    row.append(_cell(cell.value))
            rows.append(row)
        return ws.name, rows
    if ext in (".csv", ".txt"):
        raw = open(path, "rb").read()
        for enc in ("utf-8-sig", "cp949", "euc-kr"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = raw.decode("utf-8", "replace")
        delim = "\t" if text.count("\t") > text.count(",") else ","
        return "CSV", [[_cell(v) for v in r] for r in csv.reader(text.splitlines(), delimiter=delim)]
    raise ValueError("엑셀(.xlsx .xls) 또는 .csv 파일만 읽을 수 있어요")


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime("%Y-%m-%d")
    return str(v).strip()


def find_header(rows):
    for i, r in enumerate(rows[:30]):
        filled = [x for x in r if x]
        if len(filled) >= 2 and sum(1 for x in filled if not re.fullmatch(r"[\d.,\-\s]+", x)) >= 2:
            return i
    return 0


def guess_columns(header):
    used, out = set(), {}
    for key, _, words in FIELDS:
        for w in words:
            for j, h in enumerate(header):
                hn = re.sub(r"\s+", "", h)
                if j in used or not hn:
                    continue
                if hn == re.sub(r"\s+", "", w) or (len(w) >= 2 and w in hn and key not in ("serial", "dvs")):
                    out[key] = j
                    used.add(j)
                    break
            if key in out:
                break
    # 사건번호 칸이 있으면 연도/구분/번호 칸은 쓰지 않는다
    if "case" in out:
        for k in ("year", "dvs", "serial"):
            out.pop(k, None)
    return out


def guess_by_content(header, body, mapping, court_names):
    """머리글로 못 찾은 법원·사건번호·당사자 칸을 칸 안의 값을 보고 찾는다. 찾은 키 목록을 돌려준다."""
    sample = body[:60]
    ncol = max([len(header)] + [len(r) for r in sample]) if sample else len(header)
    used = set(mapping.values())
    found = []

    def values(j):
        return [r[j].strip() for r in sample if j < len(r) and r[j].strip()]

    def score(j, test):
        vals = values(j)
        return (sum(1 for v in vals if test(v)) / len(vals)) if len(vals) >= 1 else 0

    def best(test, prefer=()):
        cands = []
        for j in range(ncol):
            if j in used:
                continue
            s = score(j, test)
            if any(w in (header[j] if j < len(header) else "") for w in prefer):
                s += 0.15
            cands.append((s, -j, j))
        cands.sort(reverse=True)
        return cands[0][2] if cands and cands[0][0] >= 0.6 else None

    if "case" not in mapping and not {"year", "dvs", "serial"} <= set(mapping):
        j = best(lambda v: bool(parse_case_no(v)))
        if j is not None:
            mapping["case"] = j
            used.add(j)
            found.append("case")
    if "court" not in mapping:
        j = best(lambda v: bool(court_names.match(v)[0]), ("법원",))
        if j is not None:
            mapping["court"] = j
            used.add(j)
            found.append("court")
    if "party" not in mapping:
        def namelike(v):
            v2 = v.replace(" ", "")
            return (2 <= len(v2) <= 40 and re.search(r"[가-힣A-Za-z]", v2) and not parse_case_no(v)
                    and not re.fullmatch(r"[\d\-.,/()]+", v2) and not court_names.match(v)[0])
        j = best(namelike, ("명", "이름", "성명", "채무자", "당사자", "피고", "고객", "상대방"))
        if j is not None:
            mapping["party"] = j
            used.add(j)
            found.append("party")
    return found


def col_letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def preview(path, meta, store, mapping=None, prefer_fn=None):
    sheet, rows = read_table(path)
    names = CourtNames(meta.court_names(), store.settings.get("aliases"))
    hi = find_header(rows)
    first = rows[hi] if rows else []
    if any(parse_case_no(x) for x in first):
        # 머리글 없이 바로 자료가 있는 파일: 칸 이름을 A열, B열… 로
        width = max(len(r) for r in rows[hi:hi + 50])
        header = [f"{col_letter(j)}열" for j in range(width)]
        body = [r for r in rows[hi:] if any(x for x in r)]
        hi -= 1
    else:
        header = first
        body = [r for r in rows[hi + 1:] if any(x for x in r)]
    auto, src = [], {}
    if not mapping:
        mapping = guess_columns(header)
        pref = prefer_fn(header) if prefer_fn else {}
        if pref:  # 다른 화면에서 짝지어 둔 열 이름이 먼저
            used = set(pref.values())
            mapping = {k: v for k, v in mapping.items() if v not in used and k not in pref}
            mapping.update(pref)
            if "case" in mapping:
                for k in ("year", "dvs", "serial"):
                    mapping.pop(k, None)
            src = {k: "mem" for k in pref}
        auto = guess_by_content(header, body, mapping, names)
    width = max([len(header)] + [len(r) for r in body[:50]]) if body else len(header)
    header = header + [f"{col_letter(j)}열" for j in range(len(header), width)]
    dvs_names = meta.all_dvs_names()
    good, fixes, skips = [], [], []
    for n, r in enumerate(body):
        line = hi + 2 + n

        def get(k):
            j = mapping.get(k)
            return r[j].strip() if j is not None and j < len(r) else ""
        raw_court = get("court")
        court, fix, cands = names.match(raw_court)
        if "case" in mapping:
            p = parse_case_no(get("case"))
            raw_case = get("case")
        else:
            raw_case = f"{get('year')}{get('dvs')}{get('serial')}"
            p = parse_case_no(raw_case)
        party = get("party")
        problem = ""
        if not raw_court:
            problem = "법원 칸이 비어 있어요"
        elif not court:
            problem = f"법원 이름을 알 수 없어요" + (f" (혹시: {', '.join(cands[:3])})" if cands else "")
        elif not p:
            problem = "사건번호를 읽지 못했어요 (예: 2025가소123456)"
        elif p[1] not in dvs_names:
            problem = f"「{p[1]}」은 나의사건검색에 없는 사건구분이에요"
        elif len(party.replace(" ", "")) < 2:
            problem = "당사자 이름은 2글자 이상이어야 조회돼요"
        item = {"line": line, "court_raw": raw_court, "case_raw": raw_case, "party": party}
        if problem:
            item["problem"] = problem
            skips.append(item)
            continue
        if raw_case.replace(" ", "") != f"{p[0]}{p[1]}{p[2]}":
            fix = (fix + " · " if fix else "") + f"사건번호를 {p[0]}{p[1]}{p[2]}로 읽었어요"
        rec = {"court": court, "court_code": meta.court(court)["code"], "year": p[0], "dvs": p[1], "serial": p[2],
               "party": party, "owner": get("owner"), "memo1": get("memo1"), "memo2": get("memo2"),
               "extra": {header[j] or col_letter(j): r[j] for j in range(min(len(header), len(r)))
                         if j not in mapping.values() and r[j]}}
        if fix:
            fixes.append(dict(item, fix=fix))
        good.append(rec)
    # 사건 대장과 비교
    keys_now = {store.key_of(g["court"], g["year"], g["dvs"], g["serial"]) for g in good}
    keys_old = {store.key_of(c["court"], c["year"], c["dvs"], c["serial"]): c for c in store.active_cases()}
    new = [g for g in good if store.key_of(g["court"], g["year"], g["dvs"], g["serial"]) not in keys_old]
    gone = [c["id"] for k, c in keys_old.items() if k not in keys_now]
    sample = {k: (body[0][j] if body and j < len(body[0]) else "") for k, j in mapping.items()}
    # 칸마다 값 몇 개 (칸 고르기 목록에 보여줌)
    peek = [[r[j] for r in body[:4] if j < len(r) and r[j]][:3] for j in range(len(header))]
    rowsview = [{"court": g["court"], "case_no": f"{g['year']}{g['dvs']}{g['serial']}", "party": g["party"],
                 "memo1": g["memo1"]} for g in good[:8]]
    return {"sheet": sheet, "header": header, "letters": [col_letter(j) for j in range(len(header))], "peek": peek,
            "auto": auto, "rowsview": rowsview, "src": src,
            "mapping": mapping, "sample": sample, "rows": len(body), "good": good, "fixes": fixes, "skips": skips,
            "new": len(new), "same": len(good) - len(new), "gone": gone,
            "fields": [{"key": k, "name": n} for k, n, _ in FIELDS]}


# ---------------------------------------------------------------- 쓰기 공통

def _wb():
    import openpyxl
    return openpyxl.Workbook()


def _sheet(wb, title, header, rows, widths=None, first=False):
    from openpyxl.styles import Alignment, Font, PatternFill
    ws = wb.active if first else wb.create_sheet()
    ws.title = title[:31]
    ws.append(header)
    for r in rows:
        ws.append(r)
    fill = PatternFill("solid", fgColor="1F2A44")
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = fill
        c.alignment = Alignment(vertical="center")
    ws.freeze_panes = "A2"
    if rows:
        ws.auto_filter.ref = ws.dimensions
    for j, h in enumerate(header):
        w = (widths or {}).get(h)
        if not w:
            vals = [len(str(h))] + [len(str(r[j])) for r in rows[:300] if j < len(r)]
            w = min(60, max(8, int(max(vals) * 1.3) + 2))
        ws.column_dimensions[col_letter(j)].width = w
    return ws


def safe_name(s):
    return re.sub(r'[\\/:*?"<>|]+', "_", s).strip() or "결과"


def unique_path(folder, name, ext=".xlsx"):
    os.makedirs(folder, exist_ok=True)
    p = os.path.join(folder, safe_name(name) + ext)
    n = 2
    while os.path.exists(p):
        p = os.path.join(folder, f"{safe_name(name)} ({n}){ext}")
        n += 1
    return p


def summary_row(store, c, res, col):
    b = res.get("basic") or {}
    nh = c.get("next_hearing") or {}
    memos = " / ".join(m["text"] for m in c.get("memos") or [])
    v = {
        "사건번호": store.case_no(c), "법원": c["court"], "당사자": c.get("party", ""), "사건명": c.get("csNm", ""),
        "상태": c.get("status") or ("찾을 수 없음" if c.get("last_result") == "notfound" else "조회 전"),
        "마지막 진행": (c.get("last_prog") or {}).get("text", ""), "마지막 진행일": (c.get("last_prog") or {}).get("date", ""),
        "종국결과": c.get("ultmt", ""), "확정일": c.get("cfm_date", ""), "재판부": b.get("jdbnNm", ""),
        "접수일": str(ymd(b.get("csRcptYmd")) or ""), "원고소가": b.get("clmntVsml", ""), "인지액": b.get("stmpAtchAmt", ""),
        "다음 기일": " ".join(x for x in (nh.get("date"), nh.get("time"), nh.get("kind")) if x),
        "마지막 조회": c.get("last_checked", ""), "담당": c.get("owner", ""), "메모 1": c.get("memo1", ""),
        "메모 2": c.get("memo2", ""), "처리 메모": memos,
    }
    return v.get(col, "")


def export_results(store, meta, case_ids, folder, name, changed_ids=None):
    s = store.settings["excel"]
    cols = s.get("cols") or []
    sheets = s.get("sheets") or ["요약"]
    if s.get("only_changed") and changed_ids is not None:
        case_ids = [i for i in case_ids if i in changed_ids]
    cases = [store.cases[i] for i in case_ids if i in store.cases]
    results = {c["id"]: store.result(c["id"]) for c in cases}
    wb = _wb()
    first = True
    if "요약" in sheets:
        _sheet(wb, "요약", cols, [[summary_row(store, c, results[c["id"]], k) for k in cols] for c in cases], first=first)
        first = False
    if "일반내용" in sheets:
        keys = []
        for c in cases:
            for k in (results[c["id"]].get("basic") or {}):
                if k not in keys and not k.startswith("enc") and not k.endswith("Yn"):
                    keys.append(k)
        head = ["사건번호", "당사자", "메모 1"] + [meta.label(k) for k in keys]
        rows = [[store.case_no(c), c.get("party", ""), c.get("memo1", "")] +
                [_fmt_value(k, (results[c["id"]].get("basic") or {}).get(k, "")) for k in keys] for c in cases]
        _sheet(wb, "일반내용", head, rows, first=first)
        first = False
    if "진행내용" in sheets:
        rows = []
        for c in cases:
            for r in results[c["id"]].get("prog") or []:
                rows.append([store.case_no(c), c.get("party", ""), c.get("memo1", ""), str(ymd(r.get("progYmd")) or ""),
                             row_text(r), r.get("progRslt", ""), "새로" if r.get("_seen", "")[:10] == dt.date.today().isoformat() and not r.get("_first") else ""])
        _sheet(wb, "진행내용", ["사건번호", "당사자", "메모 1", "일자", "내용", "결과", "이번에 새로"], rows,
               widths={"내용": 60}, first=first)
        first = False
    if "당사자" in sheets:
        rows = []
        for c in cases:
            lists = results[c["id"]].get("lists") or {}
            for r in lists.get("dlt_btprtCttLst") or []:
                rows.append([store.case_no(c), r.get("btprtDvsNm", ""), r.get("btprtNm", ""),
                             str(ymd(r.get("btprtCfmtnYmd") or r.get("indvdCfmtnYmd")) or ""), r.get("adjdocRchYmd", "")])
            for r in lists.get("dlt_agntCttLst") or []:
                rows.append([store.case_no(c), r.get("agntDvsNm", "대리인"), r.get("agntNm", ""), "", ""])
        _sheet(wb, "당사자", ["사건번호", "구분", "이름", "확정일", "판결도달일"], rows, first=first)
        first = False
    if "기일" in sheets:
        rows = []
        for c in cases:
            for h in hearings(results[c["id"]].get("lists")):
                rows.append([store.case_no(c), c.get("party", ""), h["date"], h["time"], h["kind"], h["place"], h["result"]])
        _sheet(wb, "기일", ["사건번호", "당사자", "기일", "시각", "종류", "장소", "결과"], rows, first=first)
        first = False
    if first:
        _sheet(wb, "요약", cols, [], first=True)
    path = unique_path(folder, name)
    wb.save(path)
    return path


def _fmt_value(k, v):
    if isinstance(v, (list, dict)):
        return ""
    if k.endswith("Ymd"):
        d = ymd(v)
        return d.isoformat() if d else v
    return v


# ---------------------------------------------------------------- 월간 보고서

def monthly_report(store, year, month, parts, folder, author=""):
    from openpyxl.styles import Font
    first = dt.date(year, month, 1)
    last = (first + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)
    cases = store.active_cases()
    wb = _wb()
    ws = wb.active
    ws.title = "현황"
    ws.append([f"{os.path.basename(store.root)} · {year}년 {month}월 소송 사건 현황"])
    ws["A1"].font = Font(bold=True, size=15)
    ws.append([f"기준 {dt.date.today():%Y.%m.%d} · 사건 대장 {len(cases)}건" + (f" · 작성 {author}" if author else "")])
    ws.append([])
    counts = {}
    for c in cases:
        k = c.get("status") or "조회 전"
        counts[k] = counts.get(k, 0) + 1
    cfm = [c for c in cases if c.get("cfm_date") and first.isoformat() <= c["cfm_date"] <= last.isoformat()]
    act = [c for c in cases if c.get("color") in ("red", "orange")]
    if "요약 숫자" in parts:
        ws.append(["전체", "진행 중", "이번 달 확정", "조치 필요"])
        ws.append([len(cases), counts.get(store.settings.get("default_status") or "진행 중", 0), len(cfm), len(act)])
        for c in ws[ws.max_row - 1]:
            c.font = Font(bold=True)
        ws.append([])
    if "상태별 건수" in parts:
        ws.append(["상태", "건수"])
        ws[ws.max_row][0].font = ws[ws.max_row][1].font = Font(bold=True)
        for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
            ws.append([k, v])
        ws.append([])
    if "담당자별 건수" in parts:
        by = {}
        for c in cases:
            by[c.get("owner") or "(없음)"] = by.get(c.get("owner") or "(없음)", 0) + 1
        ws.append(["담당", "건수"])
        for k, v in sorted(by.items()):
            ws.append([k, v])
        ws.append([])
    if "법원별 건수" in parts:
        by = {}
        for c in cases:
            by[c["court"]] = by.get(c["court"], 0) + 1
        ws.append(["법원", "건수"])
        for k, v in sorted(by.items(), key=lambda kv: -kv[1]):
            ws.append([k, v])
    ws.column_dimensions["A"].width = 26
    for col in "BCD":
        ws.column_dimensions[col].width = 14
    head = ["사건번호", "법원", "당사자", "상태", "확정일", "마지막 진행", "담당", "메모 1"]

    def row(c):
        return [store.case_no(c), c["court"], c.get("party", ""), c.get("status", ""), c.get("cfm_date", ""),
                (c.get("last_prog") or {}).get("text", ""), c.get("owner", ""), c.get("memo1", "")]
    if "이번 달 확정 목록" in parts:
        _sheet(wb, "이번 달 확정", head, [row(c) for c in cfm])
    if "송달불능·보정명령 목록" in parts:
        _sheet(wb, "조치 필요", head, [row(c) for c in act])
    path = unique_path(folder, f"{os.path.basename(store.root)} 사건현황_{year}년{month:02d}월")
    wb.save(path)
    return path, {"total": len(cases), "counts": counts, "confirmed": len(cfm), "action": len(act)}


# ---------------------------------------------------------------- 시효관리 앱 보내기 · 양식

def export_sihyo(store, case_ids, folder):
    key = store.settings["sihyo"].get("key", "memo1")
    rows = []
    for cid in case_ids:
        c = store.cases.get(cid)
        if not c or not c.get("cfm_date"):
            continue
        rows.append([c.get(key, ""), store.case_no(c), c["court"], c.get("party", ""), c.get("csNm", ""),
                     c.get("ultmt", ""), c["cfm_date"], "판결 확정"])
    wb = _wb()
    _sheet(wb, "확정 사건", ["계좌번호", "사건번호", "법원", "당사자", "사건명", "종국결과", "확정일", "사건 종류"], rows, first=True)
    path = unique_path(folder, f"{os.path.basename(store.root)} 사건조회_확정사건_{dt.date.today():%y%m%d}")
    wb.save(path)
    return path, len(rows)


def template(folder):
    wb = _wb()
    _sheet(wb, "사건 목록", ["법원", "사건번호", "당사자", "담당", "계좌번호", "비고"],
           [["서울중앙지방법원", "2025가소123456", "홍길동", "김담당", "110-23-5521", ""],
            ["수원지방법원 성남지원", "2024차전8812", "주식회사 ○○", "이담당", "110-55-1029", "예시 줄 — 지우고 쓰세요"]],
           first=True)
    path = unique_path(folder, "사건목록_양식")
    wb.save(path)
    return path
