# -*- coding: utf-8 -*-
"""배당기일 관리 — 계산과 저장 (화면과 상관없는 부분).

흐름
  ① 조회·매칭 : 배당사건(채무자·법원·사건번호)을 나의사건검색으로 조회 → 배당기일·관련사건·공탁자 뽑기
                → 당사 법조치 자료와 「법원 + 사건번호」로 매칭 (배당사건 자체 + 관련사건 전부)
  ② 현황      : 저장한 배당사건 (다가오는 기일)
  ③ 대장      : 법조치키 하나당 한 줄, 지우지 않고 쌓임 (검수 · 발송 · 수령완료)
  ④ 통계      : 대장으로 계산 (근거 목록 = 숫자마다 그 줄들)

저장: 채권 폴더의 dividend.json 하나.
"""
import copy
import datetime as dt
import json
import os
import re
import statistics
import threading
import uuid

# ---------------------------------------------------------------- 값 다듬기

_CASE_RE = re.compile(r"(?<!\d)(\d{4}|\d{2})\s*[-./]?\s*([가-힣]{1,5})\s*[-./]?\s*(\d{1,7})(?!\d)")
_DATE_RE = re.compile(r"(\d{4})\s*[.\-/년]?\s*(\d{1,2})\s*[.\-/월]?\s*(\d{1,2})")


def today():
    return dt.date.today()


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def norm_court(s):
    """「서울남부지법」「서울 남부 지방법원」→「서울남부지방법원」, 지원은 「부산지방법원 동부지원」"""
    s = re.sub(r"\s+", "", str(s or ""))
    s = s.replace("지법", "지방법원")
    m = re.match(r"^(.+?지방법원)(.+지원)$", s)
    if m:
        s = m.group(1) + " " + m.group(2)
    return s


def norm_no(s):
    """「2026 타배 99005」→「2026타배99005」 (전각 숫자·공백 정리, 일련번호 앞 0 뺌)"""
    t = str(s or "").translate({ord(c): ord("0") + i for i, c in enumerate("０１２３４５６７８９")})
    t = re.sub(r"[\s　]", "", t)
    t = re.sub(r"\(.*?\)", "", t)
    m = _CASE_RE.search(t)
    if m:
        return _fmt_case(m)
    return t


def _fmt_case(m):
    y = m.group(1)
    if len(y) == 2:
        y = str(2000 + int(y))
    return f"{y}{m.group(2)}{int(m.group(3))}"


def key_of(court, no):
    return norm_court(court) + "|" + norm_no(no)


def norm_date(v):
    """2026.12.10 · 26-12-10 · 2026년 12월 10일 · 20261210 · 엑셀 날짜 → 2026-12-10"""
    if v is None or v == "":
        return ""
    if isinstance(v, (dt.date, dt.datetime)):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    m = re.match(r"^(\d{4})(\d{2})(\d{2})", s)
    if m:
        y, mo, d = m.groups()
    else:
        m = re.search(r"(\d{2,4})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})", s)
        if not m:
            return ""
        y, mo, d = m.groups()
        if len(y) == 2:
            y = "20" + y
    try:
        return dt.date(int(y), int(mo), int(d)).isoformat()
    except ValueError:
        return ""


def won(v):
    """'2,050,000' · '205만' · 2050000 → 2050000 (못 읽으면 '')"""
    if v is None or v == "":
        return ""
    if isinstance(v, (int, float)):
        return int(round(v))
    s = str(v).strip().replace(",", "").replace("원", "")
    m = re.match(r"^(-?\d+(?:\.\d+)?)\s*만$", s)
    if m:
        return int(round(float(m.group(1)) * 10000))
    s = re.sub(r"[^\d.\-]", "", s)
    if not s or s in ("-", "."):
        return ""
    try:
        return int(round(float(s)))
    except ValueError:
        return ""


def days_between(a, b):
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def dday(d, base=None):
    if not d:
        return None
    return (dt.date.fromisoformat(d) - (base or today())).days


def median(a):
    a = [x for x in a if x is not None]
    if not a:
        return None
    return int(round(statistics.median(a)))


# ---------------------------------------------------------------- 붙여넣기 · 엑셀 표 읽기

FIELDS = {  # 칸 이름 → 머리글로 알아보는 말 (구체적인 것부터 찾는다)
    "third": r"제\s*3\s*채무자|제삼채무자|공탁자",
    "dkey": r"채무자\s*(키|번호|id|ID|코드)|고객\s*(번호|키|id|ID|코드)|차주\s*(번호|키|id|ID)|회원\s*번호|채무자\s*관리\s*번호",
    "lkey": r"법조치\s*(키|번호|id|ID|코드)|조치\s*(키|번호|id|ID|코드)|법적\s*조치\s*(번호|키)",
    "mgr": r"담당",
    "claim": r"청구\s*액|계산서",
    "court": r"법원|관할",
    "dno": r"배당\s*사건",
    "no": r"^(?!.*배당).*(사건\s*번호|사건)",
    "debtor": r"채무자\s*명|채무자|성명|고객명|이름",
}
FIELD_NAMES = {"dno": "배당사건번호", "third": "제3채무자", "dkey": "채무자키", "lkey": "법조치키", "mgr": "담당자명", "claim": "청구액",
               "court": "법원", "no": "사건번호", "debtor": "채무자명"}


def split_lines(text):
    """탭으로 나뉘면 탭, 아니면 공백으로 나누고 「OO지방법원 OO지원」은 다시 붙인다"""
    out = []
    for line in str(text or "").replace("\r", "").split("\n"):
        if not line.strip():
            continue
        if "\t" in line:
            out.append([c.strip() for c in line.split("\t")])
            continue
        toks, row = line.split(), []
        for w in toks:
            if w.endswith("지원") and row and row[-1].endswith("법원"):
                row[-1] += " " + w
            else:
                row.append(w)
        out.append(row)
    return out


def map_header(head, want):
    """머리글 줄 → 칸마다 이름 (없으면 None). 머리글이 아니면 None 을 돌려준다."""
    def looks_data(h):  # 값처럼 생긴 칸(사건번호·「OO지방법원」·날짜)은 머리글로 치지 않는다
        h = str(h or "").replace(" ", "")
        return bool(_CASE_RE.search(h) or re.search(r"[가-힣]{2,}(지방|고등|가정|행정|회생)법원|지원$", h) or norm_date(h))
    hits = sum(1 for h in head if any(re.search(FIELDS[k], str(h or "")) for k in want) and not looks_data(h))
    if not hits or (hits < 2 and len([h for h in head if str(h or "").strip()]) > 2):
        return None
    used, out = set(), []
    order = [k for k in FIELDS if k in want]
    for h in head:
        h = str(h or "")
        k = next((k for k in order if k not in used and re.search(FIELDS[k], h)), None)
        if k:
            used.add(k)
        out.append(k)
    return out


def guess_by_value(row, rows=None, want=None):
    """머리글이 없을 때 값 모양으로 칸 짐작. 법조치 자료면 키처럼 생긴 칸을 순서대로 채무자키 · 법조치키로."""
    sample = (rows or [row])[:30]
    ncol = max(len(r) for r in sample)
    col = lambda i: [str(r[i]).strip() for r in sample if i < len(r) and str(r[i] or "").strip()]
    out, names, keys = [], [], []
    for i in range(ncol):
        vs = col(i)
        if not vs:
            out.append(None)
            continue
        share = lambda f: sum(1 for v in vs if f(v)) / len(vs)
        if share(lambda v: bool(_CASE_RE.fullmatch(re.sub(r"\s", "", v)))) >= .6:
            out.append("dno" if want and "dno" in want and share(lambda v: "타배" in v or "타경" in v) >= .6 else "no")
        elif share(lambda v: bool(re.search(r"(법원|지원|지법)$", v))) >= .6:
            out.append("court")
        elif share(lambda v: bool(re.fullmatch(r"[가-힣O○*]{2,6}", v))) >= .6:
            names.append(i)
            out.append("_name")
        elif share(lambda v: bool(re.fullmatch(r"[\d,]{5,}", v)) and "," in v) >= .6:
            out.append("claim")
        elif share(lambda v: bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\-_./]{2,}", v))) >= .6 and not share(lambda v: bool(norm_date(v))) >= .6:
            keys.append(i)
            out.append("_key")
        else:
            out.append(None)
    for n, i in enumerate(names):
        out[i] = ("debtor", "mgr")[n] if n < 2 else None
    for n, i in enumerate(keys):
        out[i] = ("dkey", "lkey")[n] if n < 2 else None
    if want:
        out = [k if k in want else None for k in out]
    return out


def head_sig(head, has_head):
    return "|".join(str(h).strip() for h in head) if has_head else f"(머리글 없음 · {len(head)}칸)"


def read_rows(rows, want, mapping=None, has_head=None):
    """표(줄 목록) → {map, head, rows:[{칸: 값}], has_head, guessed}
    mapping 을 주면 그 칸 짝을 그대로 쓴다 (사람이 「칸 맞추기」에서 고른 것)."""
    rows = [list(r) for r in rows if any(str(c or "").strip() for c in r)]
    if not rows:
        return {"map": [], "head": [], "rows": [], "has_head": False, "guessed": False, "missing": []}
    m = map_header(rows[0], want)
    if has_head is None:
        has_head = m is not None
    elif has_head and m is None:
        m = [None] * len(rows[0])
    guessed = False
    if not has_head:
        m = guess_by_value(rows[0], rows, want)
        guessed = True
    if mapping is not None:
        m = [k if k in want else None for k in mapping] + [None] * max(0, len(rows[0]) - len(mapping))
        guessed = False
    body = rows[1:] if has_head else rows
    out = []
    for r in body:
        o = {}
        for i, k in enumerate(m):
            if k and k in want:
                o[k] = str(r[i]).strip() if i < len(r) and r[i] is not None else ""
        if any(o.values()):
            out.append(o)
    head = [str(h or "") for h in rows[0]] if has_head else [f"칸 {i + 1}" for i in range(max(len(r) for r in rows[:30]))]
    return {"map": m, "head": head, "rows": out, "has_head": has_head, "guessed": guessed,
            "sample": [[str(c or "") for c in r] for r in body[:5]],
            "missing": [FIELD_NAMES[k] for k in want if k not in m]}


def read_text(text, want):
    return read_rows(split_lines(text), want)


LAW_WANT = ["dkey", "lkey", "debtor", "mgr", "court", "no", "dno", "claim"]
CASE_WANT = ["debtor", "court", "no"]


# ---------------------------------------------------------------- 나의사건검색 결과 읽기

def _vals(row):
    return [str(v).strip() for v in (row or {}).values() if v not in (None, "") and str(v).strip()]


def _case_in(text):
    m = _CASE_RE.search(re.sub(r"\s", "", str(text or "")))
    return _fmt_case(m) if m else ""


def _cases_all(text):
    """글 속의 사건번호 모두 (진행내용 등)"""
    return [_fmt_case(m) for m in _CASE_RE.finditer(str(text or ""))]


def _row_case(r):
    """한 줄(사이트 자료)에서 사건번호: 한 칸에 통째로 있거나, 연도·구분·번호가 나뉘어 있어도"""
    vs = _vals(r)
    no = next((_case_in(v) for v in vs if _case_in(v)), "")
    if no:
        return no
    y = next((v for v in vs if re.fullmatch(r"(19|20)\d{2}", v)), "")
    d = next((v for v in vs if re.fullmatch(r"[가-힣]{1,5}", v) and not re.search(r"법원|지원|명령|신청|결정", v)), "")
    n = next((v for v in vs if re.fullmatch(r"\d{1,7}", v) and v != y), "")
    return f"{y}{d}{int(n)}" if y and d and n else ""


def extract(res, court="", debtor="", own_no=""):
    """사건 조회 결과(store.result) → 배당기일 · 관련사건 · 공탁자(제3채무자).
    사이트의 칸 이름이 바뀌어도 읽히도록 값의 모양으로 찾는다."""
    lists = (res or {}).get("lists") or {}
    out = {"date": "", "rel": [], "third": "", "found": bool((res or {}).get("checks"))}
    # 배당기일: 최근 기일 목록에서 「배당」이 들어간 줄
    dates = []
    for r in lists.get("dlt_rcntDxdyLst") or []:
        vs = _vals(r)
        if any("배당" in v for v in vs):
            for v in vs:
                d = norm_date(v) if re.fullmatch(r"\d{8}|\d{4}[.\-]\d{1,2}[.\-]\d{1,2}", v) else ""
                if d:
                    dates.append(d)
    # 진행내용에 「배당기일 지정」·「배당기일(2026.11.17 10:00)」 등
    if not dates:
        for p in (res or {}).get("prog") or []:
            t = f"{p.get('progCtt', '')} {p.get('progRslt', '')}"
            if "배당기일" in t:
                m = re.search(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})", t)
                if m:
                    dates.append(norm_date(m.group(0)))
    if dates:
        fut = sorted(d for d in dates if d >= today().isoformat())
        out["date"] = fut[0] if fut else max(dates)
    # 관련사건: ① 관련사건 목록 ② 다른 목록(당사자 등) ③ 진행내용 글 속 사건번호 — 배당사건 자신은 뺀다
    own = norm_no(own_no) if own_no else ""
    seen = set()

    def add(ct, no, kind, src):
        if not no or no == own:
            return
        k = no
        if k in seen:
            return
        seen.add(k)
        out["rel"].append([ct or norm_court(court), no, kind, src])

    for r in lists.get("dlt_reltCsLst") or []:
        vs = _vals(r)
        no = _row_case(r)
        ct = next((norm_court(v) for v in vs if re.search(r"(법원|지원)$", v.replace(" ", ""))), "")
        kind = next((v for v in vs if re.search(r"명령|신청|결정|신고|가압류|압류|추심|전부|공탁", v) and not _case_in(v)), "")
        add(ct, no, kind, "관련사건")
    for name, rows in lists.items():
        if name == "dlt_reltCsLst" or not isinstance(rows, list):
            continue
        for r in rows:
            if not isinstance(r, dict):
                continue
            vs = _vals(r)
            ct = next((norm_court(v) for v in vs if re.search(r"(법원|지원)$", v.replace(" ", ""))), "")
            for v in vs:
                for no in _cases_all(v):
                    add(ct, no, "", "사건 정보")
    for p in (res or {}).get("prog") or []:
        t = f"{p.get('progCtt', '')} {p.get('progRslt', '')}"
        for no in _cases_all(t):
            add("", no, "", "진행내용")
    # 공탁자(= 보통 제3채무자): 당사자 목록에서 구분이 공탁자·제3채무자인 줄의 이름
    for r in lists.get("dlt_btprtCttLst") or []:
        vs = _vals(r)
        role = next((v for v in vs if re.search(r"공탁자|제3채무자|제삼채무자", v)), "")
        if role:
            name = next((v for v in vs if v != role and not re.fullmatch(r"[\d\-.]+", v) and len(v) >= 2), "")
            if name:
                out["third"] = re.sub(r"^\d+\.\s*", "", name)
                break
    return out


# ---------------------------------------------------------------- 매칭

def match(searched, law_rows, linkmem=None, notours=None):
    """searched: [{debtor,court,no,ok,date,rel,third}] · law_rows: 법조치 자료 줄
    배당사건 자체와 관련사건마다 법조치 자료에서 같은 사건을 찾아 그 줄의 채무자키·법조치키를 붙인다.
      1) 법원 + 사건번호가 같으면 그대로
      2) 법원이 다르거나 비어 있어도 사건번호가 같으면 붙이고 「법원 확인」 표시
         (같은 번호가 여러 법원에 있으면 채무자 이름이 같은 줄만)
    → 사건마다 hits(맞은 법조치 줄) · 상태(ok·multi·none·fail·notours)"""
    linkmem, notours = linkmem or {}, set(notours or [])
    full, by_no, by_dno = {}, {}, {}
    for r in law_rows:
        if r.get("dno"):
            by_dno.setdefault(norm_no(r["dno"]), []).append(r)
        if not r.get("no"):
            continue
        n = norm_no(r["no"])
        by_no.setdefault(n, []).append(r)
        if r.get("court"):
            full.setdefault(key_of(r["court"], n), []).append(r)
    out = []
    for s in searched:
        k = key_of(s["court"], s["no"])
        if k in notours:
            out.append(dict(s, hits=[], dkeys=[], rel_out=[], name_note=[], status="notours"))
            continue
        keys = [[s["court"], s["no"], "배당사건 자체"]] + [list(x) for x in s.get("rel") or []]
        hits, rel_out = [], []
        # 법조치 자료에 배당사건번호 칸이 있으면 그것으로 먼저
        for f in by_dno.get(norm_no(s["no"]), []):
            oc = norm_court(f.get("court") or s["court"])
            hits.append(dict(f, via=f"배당사건번호 {norm_no(s['no'])}", ours=f"{oc} {norm_no(f.get('no', ''))}".strip(), court_check=False))
        for j, x in enumerate(keys):
            c, n, kind = x[0], x[1], (x[2] if len(x) > 2 else "")
            src = x[3] if len(x) > 3 else ""
            n = norm_no(n)
            found = full.get(key_of(c, n), [])
            check = False
            if not found and by_no.get(n):
                cand = by_no[n]
                same = [r for r in cand if s.get("debtor") and r.get("debtor") == s.get("debtor")]
                found = same if (same and len({norm_court(r.get("court", "")) for r in cand}) > 1) else cand
                check = any(r.get("court") for r in found)  # 법원이 적혀 있는데 달랐으면 확인 표시
            if j > 0:
                rel_out.append({"court": norm_court(c), "no": n, "kind": kind, "src": src, "hit": bool(found)})
            for f in found:
                if not any(h.get("lkey") == f.get("lkey") and h.get("dkey") == f.get("dkey") for h in hits):
                    oc = norm_court(f.get("court") or c)
                    hits.append(dict(f, via=f"{oc} {n}" + (" · 법원 확인" if check else ""), ours=f"{oc} {n}", court_check=check))
        remembered = False
        if not hits and linkmem.get(k):
            f = [r for r in law_rows if r.get("lkey") == linkmem[k]]
            if f:
                hits = [dict(x, via="직접 연결 (기억)", ours=f"{norm_court(x.get('court') or s['court'])} {norm_no(x.get('no', ''))}") for x in f]
                remembered = True
        dkeys = list(dict.fromkeys(h.get("dkey") for h in hits if h.get("dkey")))
        name_note = list(dict.fromkeys(r.get("dkey") for r in law_rows
                                       if s.get("debtor") and r.get("debtor") == s.get("debtor") and r.get("dkey") not in dkeys
                                       and not any(h.get("lkey") == r.get("lkey") for h in hits) and r.get("dkey")))
        st = "fail" if not s.get("ok") else ("multi" if len(dkeys) > 1 else "ok") if hits else "none"
        out.append(dict(s, hits=hits, dkeys=dkeys, rel_out=rel_out, name_note=name_note, status=st, remembered=remembered))
    return out


def out_rows(matched):
    """매칭 결과 → 법조치키 하나당 한 줄 (엑셀·저장 모양)"""
    rows = []
    for m in matched:
        if m.get("status") in ("fail", "notours"):
            continue
        rel = ", ".join(f"{x['court']} {x['no']}" + (f"({x['kind']})" if x.get("kind") else "") for x in m.get("rel_out") or [])
        base = {"court": m["court"], "no": m["no"], "date": m.get("date", ""), "rel": rel, "rel_nos": ", ".join(x["no"] for x in m.get("rel_out") or []),
                "case_status": m["status"], "debtor": m.get("debtor", ""), "multi": len(m.get("dkeys") or []) > 1,
                "name_note": m.get("name_note") or [], "rel_out": m.get("rel_out") or [], "remembered": m.get("remembered", False)}
        if not m.get("hits"):
            rows.append(dict(base, dkey="", lkey="", mgr="", third=m.get("third", ""), third_src="공탁자(사건검색)" if m.get("third") else "",
                             via="", ours="", claim=""))
        for h in m.get("hits") or []:
            st = m.get("third") or ""  # 제3채무자는 사건검색의 공탁자로만 (법조치 자료에는 없음)
            rows.append(dict(base, dkey=h.get("dkey", ""), lkey=h.get("lkey", ""), debtor=h.get("debtor") or m.get("debtor", ""),
                             mgr=h.get("mgr", ""), third=st, third_src="공탁자(사건검색)" if st else "",
                             via=h.get("via", ""),
                             ours=h.get("ours", ""), court_check=h.get("court_check", False),
                             claim=won(h.get("claim", ""))))
    return rows


def row_key(r):
    return f"{norm_court(r['court'])}|{norm_no(r['no'])}|{r.get('lkey') or r.get('debtor', '')}"


# ---------------------------------------------------------------- 대장 줄

RECV_LABEL = {"대기": "대기", "발송": "발송", "수령": "수령완료"}


def is_none(r):
    return r.get("recv") == "수령" and r.get("amt") not in ("", None) and int(r.get("amt") or 0) == 0


def is_done(r):
    return r.get("check") == "완료" and r.get("recv") == "수령"


def need_send(r, base=None):
    return bool(r.get("date")) and dday(r["date"], base) < 0 and r.get("recv") == "대기"


def stage(r, base=None):
    if r.get("check") not in ("완료", "보류"):
        return "검수 대기", "warn"
    if r.get("check") == "보류":
        return "검수 보류", "bad"
    if r.get("recv") == "수령":
        return ("끝 · 배당 없음", "wait") if is_none(r) else ("수령완료", "ok")
    if r.get("recv") == "발송":
        return "발송 · 입금 대기", "now"
    if not r.get("date") or dday(r["date"], base) >= 0:
        return "기일 대기", "wait"
    return "발송 필요", "bad"


def ours_court(r):
    a = (r.get("ours") or "").split(" ")
    return " ".join(a[:-1]) if len(a) > 1 else ""


def ours_no(r):
    a = (r.get("ours") or "").split(" ")
    return a[-1] if a and a[-1] else ""


EXPORT_COLS = [("채무자키", "dkey"), ("법조치키", "lkey"), ("채무자명", "debtor"), ("담당자명", "mgr"), ("배당법원", "court"),
               ("배당사건번호", "no"), ("배당기일", "date"), ("당사 법원", "_oc"), ("당사 사건번호", "_on"), ("제3채무자", "third"),
               ("배당관련사건", "rel"), ("청구액", "claim"), ("검수", "check"), ("배당액", "amt"),
               ("수령 단계", "_recv"), ("발송일", "send_at"), ("수령일", "recv_at"), ("메모", "memo")]


def export_value(r, k):
    if k == "_oc":
        return ours_court(r)
    if k == "_on":
        return ours_no(r)
    if k == "_recv":
        return RECV_LABEL.get(r.get("recv"), r.get("recv", ""))
    v = r.get(k, "")
    return "" if v is None else v


# 붙여넣어 고치기: 바꿀 수 있는 칸 (머리글 → 칸, 값 바꾸는 법)
PASTE_FIELDS = [
    ("amt", r"배당\s*액|배당금", "배당액", won), ("claim", r"청구\s*액|계산서", "청구액", won),
    ("third", r"제\s*3\s*채무자|공탁자", "제3채무자", None), ("mgr", r"담당", "담당자", None),
    ("recv", r"수령\s*단계|^수령$|^단계$", "수령 단계",
     lambda v: "수령" if re.search(r"완료|수령", v) else "발송" if "발송" in v else "대기" if "대기" in v else ""),
    ("send_at", r"발송\s*일", "발송일", norm_date), ("recv_at", r"수령\s*일|입금\s*일", "수령일", norm_date),
    ("date", r"배당\s*기일", "배당기일", norm_date), ("memo", r"메모|비고", "메모", None),
    ("check", r"^검수$", "검수", lambda v: "완료" if re.search(r"완료|^[OoYy○]$|^예$", v.strip()) else "보류" if "보류" in v else "대기"),
]


# ---------------------------------------------------------------- 저장

EMPTY = {"ledger": [], "board": [], "search": {}, "law": {"text": "", "rows": [], "src": "", "at": ""}, "linkmem": {},
         "notours": [], "diffs": [], "dash": {}, "xlsm": {"path": "", "recent": []}, "nopay_n": None, "board_order": [],
         "board_sort": "date", "ledger_sort": "date"}

DASH_DEFAULT = {"order": ["kpi", "month", "forecast", "aging", "oldest", "third", "mgr", "court"], "hide": [],
                "kpis": ["amt", "got", "yield", "unpaid", "none", "d2r"], "top": 8, "lateD": 31, "oldN": 6,
                "period": "12m", "basis": "date"}


class DividendStore:
    def __init__(self, root):
        self.root = root
        self.path = os.path.join(root, "dividend.json")
        self.lock = threading.RLock()
        data = {}
        if os.path.isfile(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                os.replace(self.path, self.path + f".broken-{dt.datetime.now():%Y%m%d%H%M%S}")
        self.data = copy.deepcopy(EMPTY)
        self.data.update(data)
        self.data["dash"] = dict(DASH_DEFAULT, **(self.data.get("dash") or {}))

    def save(self):
        with self.lock:
            os.makedirs(self.root, exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)

    def backup(self, keep=30):
        """하루 한 번 dividend 백업 (채권 폴더/backup/dividend_YYYYMMDD.json)"""
        if not os.path.isfile(self.path):
            return
        d = os.path.join(self.root, "backup")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, f"dividend_{dt.date.today():%Y%m%d}.json")
        if not os.path.exists(p):
            import shutil
            shutil.copy2(self.path, p)
            olds = sorted(f for f in os.listdir(d) if f.startswith("dividend_"))
            for f in olds[:-keep]:
                try:
                    os.remove(os.path.join(d, f))
                except OSError:
                    pass

    # ------------------------------------------------------------ 대장

    @property
    def ledger(self):
        return self.data["ledger"]

    def row(self, rid):
        return next((r for r in self.ledger if r["id"] == rid), None)

    @staticmethod
    def log(r, text, by=""):
        r.setdefault("log", []).insert(0, [now()[:16], by, text])
        del r["log"][80:]

    def new_row(self, fields, src, by=""):
        r = {"id": uuid.uuid4().hex[:10], "dkey": "", "lkey": "", "debtor": "", "mgr": "", "court": "", "no": "", "date": "",
             "rel": "", "via": "", "ours": "", "third": "", "third_src": "", "claim": "", "check": "대기", "check_by": "",
             "amt": "", "recv": "대기", "send_at": "", "recv_at": "", "memo": "", "src": src, "fresh": True, "changed": False,
             "deleted": False, "added": now(), "log": []}
        r.update({k: v for k, v in fields.items() if k in r and v is not None})
        r["court"] = norm_court(r["court"])
        r["no"] = norm_no(r["no"])
        self.ledger.append(r)
        return r

    def find(self, court, no, lkey="", debtor=""):
        k = key_of(court, no)
        for r in self.ledger:
            if key_of(r["court"], r["no"]) == k and ((lkey and r.get("lkey") == lkey) or (not lkey and r.get("debtor") == debtor and not r.get("lkey"))):
                return r
        return None

    def find_keyless(self, court, no):
        """같은 배당사건인데 키 없이 들어간 줄 (예전에 매칭이 안 됐던 줄)"""
        k = key_of(court, no)
        return next((r for r in self.ledger if key_of(r["court"], r["no"]) == k and not r.get("lkey") and not r.get("dkey") and not r.get("deleted")), None)

    def to_ledger(self, rows, by=""):
        """매칭 결과 줄을 대장에 넣는다. 같은 사건+법조치키면 새 줄 없이 기일·관련사건만 고치고,
        담당자·제3채무자·채무자키가 다르면 「다른 값」으로 모아 사람이 고르게 한다."""
        add = upd = 0
        for o in rows:
            ex = self.find(o["court"], o["no"], o.get("lkey", ""), o.get("debtor", ""))
            if not ex and o.get("lkey"):
                kl = self.find_keyless(o["court"], o["no"])
                if kl:  # 키 없던 줄에 이번에 찾은 채무자키 · 법조치키를 채운다
                    kl.update(dkey=o.get("dkey", ""), lkey=o["lkey"], debtor=o.get("debtor") or kl.get("debtor", ""), mgr=o.get("mgr") or kl.get("mgr", ""),
                              ours=o.get("ours") or kl.get("ours", ""), via=o.get("via", ""), claim=o.get("claim") or kl.get("claim", ""), changed=True)
                    if kl.get("memo", "").startswith("우리 사건 못 찾음"):
                        kl["memo"] = ""
                    self.log(kl, f"매칭으로 키 붙음 · {o.get('dkey', '')} / {o['lkey']} ({o.get('via', '')})", "조회·매칭")
                    upd += 1
                    continue
            if ex:
                ch = []
                if o.get("date") and ex.get("date") != o["date"]:
                    ch.append(f"배당기일 {ex.get('date') or '—'} → {o['date']}")
                    ex["date"] = o["date"]
                if o.get("rel_nos") is not None and ex.get("rel") != o.get("rel_nos"):
                    ex["rel"] = o.get("rel_nos")
                    ch.append("관련사건 바뀜")
                if ch:
                    ex["changed"] = True
                    ex["deleted"] = False
                    self.log(ex, " · ".join(ch), "조회·매칭")
                    upd += 1
                for f in ("mgr", "dkey"):
                    to = o.get(f) or ""
                    if to and (ex.get(f) or "") != to and not any(d["id"] == ex["id"] and d["f"] == f for d in self.data["diffs"]):
                        self.data["diffs"].append({"id": ex["id"], "f": f, "from": ex.get(f) or "", "to": to})
                continue
            r = self.new_row({"dkey": o.get("dkey", ""), "lkey": o.get("lkey", ""), "debtor": o.get("debtor", ""), "mgr": o.get("mgr", ""),
                              "court": o["court"], "no": o["no"], "date": o.get("date", ""), "rel": o.get("rel_nos", ""),
                              "via": o.get("via", ""), "ours": o.get("ours", ""), "third": o.get("third", ""),
                              "third_src": o.get("third_src", ""), "claim": o.get("claim", ""),
                              "memo": "" if o.get("dkey") else "우리 사건 못 찾음 — 키 직접 넣기"},
                             f"조회·매칭 {now()[2:10].replace('-', '.')}", by)
            self.log(r, "사건검색으로 들어옴" + (f" · {o['via']}로 매칭" if o.get("via") else ""), "조회·매칭")
            add += 1
        return {"add": add, "upd": upd}


# ---------------------------------------------------------------- 통계

PERIODS = {"12m": "최근 12개월", "this": "올해", "last": "작년", "all": "전체"}


def months_of(period, base=None):
    b = base or today()
    out = []
    if period == "12m":
        y, m = b.year, b.month
        for i in range(11, -1, -1):
            mm = m - i
            yy = y + (mm - 1) // 12
            mm = (mm - 1) % 12 + 1
            out.append(f"{yy}-{mm:02d}")
    elif period in ("this", "last") or re.fullmatch(r"\d{4}", str(period)):
        y = b.year if period == "this" else b.year - 1 if period == "last" else int(period)
        out = [f"{y}-{m:02d}" for m in range(1, 13)]
    else:  # all: 대장에 있는 가장 이른 달부터
        return None
    return out


class Stats:
    """대장 줄 → 숫자. 화면·보고서·근거 목록이 모두 같은 함수를 쓴다."""

    def __init__(self, rows, f=None, base=None):
        self.base = base or today()
        self.f = dict(period="12m", basis="date", third="", mgr="", court="")
        self.f.update(f or {})
        self.all = [r for r in rows if not r.get("deleted") and r.get("no")]
        self.lateD = int(self.f.get("lateD") or 31)

    @property
    def today_s(self):
        return self.base.isoformat()

    def months(self):
        ms = months_of(self.f["period"], self.base)
        if ms is None:
            ds = sorted(self.base_date(r)[:7] for r in self.all if self.base_date(r))
            if not ds:
                return [self.today_s[:7]]
            y0, m0 = map(int, ds[0].split("-"))
            ms, y, m = [], y0, m0
            while f"{y}-{m:02d}" <= self.today_s[:7]:
                ms.append(f"{y}-{m:02d}")
                m += 1
                if m > 12:
                    y, m = y + 1, 1
        return ms

    def base_date(self, r):
        if self.f["basis"] == "recv":
            return r.get("recv_at", "") if r.get("recv") == "수령" else ""
        return r.get("date", "")

    def filtered(self, ignore=""):
        return [r for r in self.all if all(ignore == k or not self.f.get(k) or r.get(k) == self.f[k] for k in ("third", "mgr", "court"))]

    def rows(self, ignore="", months=None):
        ms = set(months or self.months())
        return [r for r in self.filtered(ignore) if self.base_date(r) and self.base_date(r)[:7] in ms]

    def nopay(self, r, n):
        return r.get("recv") == "발송" and r.get("send_at") and days_between(r["send_at"], self.today_s) > n

    def agg(self, rows, keyf=None, nopay_n=10):
        G = {}
        for r in rows:
            k = (keyf(r) if keyf else "all") or "(없음)"
            g = G.setdefault(k, {"k": k, "n": 0, "amt": 0, "got": 0, "wait": 0, "n_got": 0, "n_wait": 0, "none": 0, "claim": 0,
                                 "claim_amt": 0, "d2s": [], "s2r": [], "d2r": [], "todo": 0})
            g["n"] += 1
            a = int(r.get("amt") or 0) if r.get("amt") not in ("", None) else 0
            g["amt"] += a
            if r.get("claim") and r.get("amt") not in ("", None):
                g["claim"] += int(r["claim"])
                g["claim_amt"] += a
            if is_none(r):
                g["none"] += 1
            if r.get("recv") == "수령":
                g["got"] += a
                g["n_got"] += 1
                if r.get("recv_at") and a and r.get("date"):
                    g["d2r"].append(days_between(r["date"], r["recv_at"]))
                    if r.get("send_at"):
                        g["s2r"].append(days_between(r["send_at"], r["recv_at"]))
            else:
                g["wait"] += a
                g["n_wait"] += 1
            if r.get("send_at") and r.get("date"):
                g["d2s"].append(days_between(r["date"], r["send_at"]))
            if r.get("check") != "완료" or need_send(r, self.base) or self.nopay(r, nopay_n):
                g["todo"] += 1
        out = []
        for g in G.values():
            g.update(m_d2s=median(g["d2s"]), m_s2r=median(g["s2r"]), m_d2r=median(g["d2r"]),
                     rate=g["got"] / g["amt"] if g["amt"] else 0, yld=g["claim_amt"] / g["claim"] if g["claim"] else None,
                     zero=g["none"] / g["n"] if g["n"] else 0)
            out.append(g)
        return out

    def total(self, rows, nopay_n=10):
        a = self.agg(rows, None, nopay_n)
        if a:
            return a[0]
        return {"k": "all", "n": 0, "amt": 0, "got": 0, "wait": 0, "n_got": 0, "n_wait": 0, "none": 0, "claim": 0, "claim_amt": 0,
                "d2s": [], "s2r": [], "d2r": [], "todo": 0, "m_d2s": None, "m_s2r": None, "m_d2r": None, "rate": 0, "yld": None, "zero": 0}

    def aging(self):
        L = [r for r in self.filtered() if r.get("recv") != "수령" and r.get("date") and dday(r["date"], self.base) < 0]
        def sent_days(r):
            return days_between(r["send_at"], self.today_s) if r.get("send_at") else 0
        B = [("발송 전", -1, lambda r: r.get("recv") == "대기"),
             ("발송 0~14일", 0, lambda r: r.get("recv") == "발송" and sent_days(r) <= 14),
             ("15~30일", 15, lambda r: r.get("recv") == "발송" and 14 < sent_days(r) <= 30),
             ("31~60일", 31, lambda r: r.get("recv") == "발송" and 30 < sent_days(r) <= 60),
             ("61일 넘음", 61, lambda r: r.get("recv") == "발송" and sent_days(r) > 60)]
        buckets = []
        for t, frm, fn in B:
            x = [r for r in L if fn(r)]
            buckets.append({"t": t, "from": frm, "n": len(x), "amt": sum(int(r.get("amt") or 0) for r in x), "ids": [r["id"] for r in x]})
        old = sorted(({"id": r["id"], "days": sent_days(r) if r.get("recv") == "발송" else -dday(r["date"], self.base),
                       "b": next((i for i, (_, _, fn) in enumerate(B) if fn(r)), 0)} for r in L), key=lambda x: -x["days"])
        return {"buckets": buckets, "old": old}

    def avg_yield(self):
        g = self.agg([r for r in self.all if r.get("recv") == "수령" and r.get("claim") and r.get("amt") not in ("", None)])
        return g[0]["yld"] if g and g[0]["yld"] else 0.45

    def forecast(self):
        avg = self.avg_yield()
        fut = [r for r in self.filtered() if r.get("recv") != "수령"]
        B = [("기일 지남 · 받을 돈", lambda r: r.get("date") and dday(r["date"], self.base) < 0),
             ("30일 안", lambda r: r.get("date") and 0 <= dday(r["date"], self.base) <= 30),
             ("31~60일", lambda r: r.get("date") and 30 < dday(r["date"], self.base) <= 60),
             ("61~90일", lambda r: r.get("date") and 60 < dday(r["date"], self.base) <= 90),
             ("기일 미정", lambda r: not r.get("date"))]
        out = []
        for t, fn in B:
            x = [r for r in fut if fn(r)]
            known = sum(int(r["amt"]) for r in x if r.get("amt") not in ("", None))
            est = sum(int(r.get("claim") or 0) * avg for r in x if r.get("amt") in ("", None))
            out.append({"t": t, "n": len(x), "known": known, "est": int(round(est)), "ids": [r["id"] for r in x]})
        return {"avg": avg, "rows": out}

    def monthly(self, nopay_n=10):
        ms = self.months()
        G = {g["k"]: g for g in self.agg(self.rows(), lambda r: self.base_date(r)[:7], nopay_n)}
        empty = self.total([], nopay_n)
        return [dict(G.get(m) or dict(empty, k=m), k=m) for m in ms]

    def by(self, dim, nopay_n=10):
        g = self.agg(self.rows(dim), lambda r: r.get(dim), nopay_n)
        return sorted(g, key=lambda x: -x["amt"])


def _strip(g):
    return {k: v for k, v in g.items() if k not in ("d2s", "s2r", "d2r")}


def dashboard(rows, f, dash, nopay_n=10, base=None):
    """④ 통계 화면에 필요한 숫자 한 번에"""
    S = Stats(rows, dict(f, lateD=dash.get("lateD", 31)), base)
    ms = S.months()
    A = S.total(S.rows(), nopay_n)
    prev_ms = [f"{int(m[:4]) - 1}-{m[5:]}" for m in ms]
    P = S.total(S.rows("", prev_ms), nopay_n) if S.rows("", prev_ms) else None
    AG = S.aging()
    late = sum(b["amt"] for b in AG["buckets"] if b["from"] >= int(dash.get("lateD", 31)))
    unpaid = sum(b["amt"] for b in AG["buckets"])
    return {"months": ms, "total": _strip(A), "prev": _strip(P) if P else None, "monthly": [_strip(g) for g in S.monthly(nopay_n)],
            "forecast": S.forecast(), "aging": AG, "unpaid": unpaid, "late": late,
            "by": {d: [_strip(g) for g in S.by(d, nopay_n)] for d in ("third", "mgr", "court")}}


def drill(rows, f, dash, key, nopay_n=10, base=None):
    """숫자 하나 → 그 숫자를 만든 줄 목록과 검수용 값"""
    S = Stats(rows, dict(f, lateD=dash.get("lateD", 31)), base)
    kind, _, rest = key.partition("|")
    a, _, b = rest.partition("|")
    byid = {r["id"]: r for r in S.all}
    R = S.rows()
    A = S.total(R, nopay_n)
    amt = lambda L: sum(int(r.get("amt") or 0) for r in L if r.get("amt") not in ("", None))
    if kind == "kpi":
        AG = S.aging()
        K = {
            "amt": (R, "amt", A["amt"], "배당액 = 이 기간 줄의 배당액 합계", ""),
            "n": (R, "n", A["n"], "배당 건수 = 이 기간 줄 수", ""),
            "avg": (R, "amt", A["amt"], "건당 배당액 = 배당액 합계 ÷ 건수", ""),
            "got": ([r for r in R if r.get("recv") == "수령"], "amt", A["got"], "회수액 = 수령완료 줄의 배당액 합계", ""),
            "rate": ([r for r in R if r.get("recv") == "수령"], "amt", A["got"], "회수율 = 회수액 ÷ 배당액", ""),
            "yield": ([r for r in R if r.get("claim") and r.get("amt") not in ("", None)], "amt", A["claim_amt"],
                      "배당률 = 배당액 합계 ÷ 청구액 합계 (청구액 있는 줄만)", "claim"),
            "unpaid": ([byid[x["id"]] for x in AG["old"]], "amt", sum(x["amt"] for x in AG["buckets"]),
                       "미수령 잔액 = 배당기일 지났는데 수령완료가 아닌 줄의 배당액 (기간과 상관없이 지금 기준)", "age"),
            "none": ([r for r in R if is_none(r)], "n", A["none"], "배당 없음 = 배당액 0원으로 수령완료된 줄", ""),
            "d2r": ([r for r in R if r.get("recv") == "수령" and r.get("recv_at") and int(r.get("amt") or 0) and r.get("date")], "n",
                    len(A["d2r"]), "기일 → 수령 = 배당기일부터 수령일까지 날 수의 중앙값 (0원 배당 뺌)", "d2r"),
        }[a]
        L, sm, show, why, ctx = K
        title = {"amt": "배당액", "n": "배당 건수", "avg": "건당 배당액", "got": "회수액 (수령)", "rate": "회수율", "yield": "배당률",
                 "unpaid": "미수령 잔액", "none": "배당 없음", "d2r": "기일 → 수령"}[a]
        act = ""
    elif kind == "month":
        L = [r for r in R if S.base_date(r)[:7] == a]
        title, sm, show, ctx, act = f"{a[:4]}년 {int(a[5:])}월", "amt", amt(L), "", ""
        why = f"{'수령일' if S.f['basis'] == 'recv' else '배당기일'}이 {a.replace('-', '.')}인 줄"
    elif kind == "fc":
        FC = S.forecast()
        x = FC["rows"][int(a)]
        L = [byid[i] for i in x["ids"]]
        title, sm, show, ctx, act = f"앞으로 들어올 돈 · {x['t']}", "amt", x["known"], "est", ""
        why = f"수령완료 전 줄 · 배당액 모르는 줄은 청구액 × 평균 배당률 {FC['avg'] * 100:.0f}%로 추정"
    elif kind == "ag":
        AG = S.aging()
        x = AG["buckets"][int(a)]
        L = [byid[i] for i in x["ids"]]
        title, sm, show, ctx = f"미수령 · {x['t']}", "amt", x["amt"], "age"
        act = "send" if int(a) == 0 else "recv"
        why = "배당기일 지났는데 아직 교부신청서를 보내지 않은 줄" if int(a) == 0 else "발송한 뒤 지난 날로 나눈 줄"
    elif kind == "old":
        AG = S.aging()
        L = [byid[x["id"]] for x in AG["old"]]
        title, sm, show, ctx, act, why = "오래된 미수령 전체", "amt", sum(x["amt"] for x in AG["buckets"]), "age", "", "지난 날 많은 순"
    elif kind == "dim":
        L = [r for r in S.rows(a) if (r.get(a) or "(없음)") == b]
        title = {"third": "제3채무자", "mgr": "담당자", "court": "법원"}[a] + " · " + b
        sm, show, ctx, act, why = "amt", amt(L), ("d2r" if a == "court" else "claim" if a == "third" else ""), "", f"이 기간 {b} 줄"
    else:
        raise ValueError("알 수 없는 목록이에요")
    L = sorted(L, key=lambda r: r.get("date") or "9999")
    total = amt(L)
    ok = (len(L) == show) if sm == "n" else (round(total) == round(show))
    return {"title": title, "why": why, "ctx": ctx, "act": act, "sum": sm, "show": show, "count": len(L), "total": total, "ok": ok,
            "ids": [r["id"] for r in L], "dim": [a, b] if kind == "dim" else None, "avg_yield": S.avg_yield()}


def today_groups(rows, me="", mine=True, nopay_n=10, diffs=None, base=None):
    b = base or today()
    ts = b.isoformat()
    L = [r for r in rows if not r.get("deleted") and r.get("no") and (not mine or not me or r.get("mgr") == me)]
    dif = {d["id"] for d in diffs or []}
    sent = lambda r: days_between(r["send_at"], ts) if r.get("send_at") else 0
    G = [
        ("soon", "7일 안 배당기일", "출석·계산서 확인", "bad", [r for r in L if r.get("date") and 0 <= dday(r["date"], b) <= 7 and r.get("recv") != "수령"],
         lambda r: r["date"]),
        ("send", "기일 지남 · 발송 전", "배당금교부신청서 보내기", "bad", [r for r in L if need_send(r, b)], lambda r: r["date"]),
        ("pay", f"발송 후 {nopay_n}일 넘게 입금 없음", "입금 확인 · 법원·제3채무자 연락", "warn",
         [r for r in L if r.get("recv") == "발송" and r.get("send_at") and sent(r) > nopay_n], lambda r: r["send_at"]),
        ("check", "검수 대기", "키·사건·배당표 금액 확인", "warn", [r for r in L if r.get("check") in ("대기", "보류")], lambda r: r.get("date") or "9999"),
        ("chg", "기일·값 바뀐 건", "다시 조회 · 법조치 자료 반영", "now", [r for r in L if r.get("changed") or r["id"] in dif], lambda r: r.get("date") or "9999"),
    ]
    return [{"k": k, "t": t, "sub": s, "c": c, "ids": [r["id"] for r in sorted(x, key=key)]} for k, t, s, c, x, key in G]


def pay_lag_median(rows):
    return median([days_between(r["send_at"], r["recv_at"]) for r in rows
                   if r.get("recv") == "수령" and r.get("send_at") and r.get("recv_at") and int(r.get("amt") or 0)]) or 10


def pick_candidates(rows, board, last_fail, notours, base=None):
    """다시 조회할 건: 기일 미정 · 30일 안 · 지난 조회 실패 · 새로 들어옴 (나머지는 이유와 함께 뺌)"""
    b = base or today()
    cases = {}
    for r in list(rows) + [dict(x, fresh=True, recv="대기") for x in board]:
        if not r.get("no") or r.get("deleted"):
            continue
        k = key_of(r["court"], r["no"])
        if k in notours:
            continue
        c = cases.setdefault(k, {"k": k, "court": norm_court(r["court"]), "no": norm_no(r["no"]), "debtor": r.get("debtor", ""),
                                 "date": r.get("date", ""), "done": True, "fresh": False})
        if r.get("recv") != "수령":
            c["done"] = False
        if r.get("fresh"):
            c["fresh"] = True
        if not c["date"] and r.get("date"):
            c["date"] = r["date"]
    for f in last_fail or []:
        k = key_of(f["court"], f["no"])
        cases[k] = {"k": k, "court": norm_court(f["court"]), "no": norm_no(f["no"]), "debtor": f.get("debtor", ""), "date": "",
                    "done": False, "fail": True}
    IN, OUT = [], []
    for c in cases.values():
        if c.get("fail"):
            IN.append(dict(c, why="지난 조회 실패"))
        elif c["done"]:
            OUT.append(dict(c, why="수령완료"))
        elif not c["date"]:
            IN.append(dict(c, why="기일 미정"))
        elif dday(c["date"], b) < 0:
            OUT.append(dict(c, why="기일 지남 (대장에서 처리)"))
        elif dday(c["date"], b) <= 30:
            IN.append(dict(c, why="30일 안 기일"))
        elif c["fresh"]:
            IN.append(dict(c, why="새로 들어옴"))
        else:
            OUT.append(dict(c, why="기일 확정 · 30일 넘게 남음"))
    return {"in": IN, "out": OUT}


def paste_parse(text, rows):
    """엑셀에서 붙여넣은 표 → 바뀔 칸 목록. 줄은 법조치키 / 배당사건번호 / 채무자키로 찾는다."""
    lines = [l.split("\t") for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
    if len(lines) < 2:
        return {"err": "머리글 줄과 값 줄이 필요해요"}
    h = [c.strip() for c in lines[0]]
    ki = {"lkey": next((i for i, x in enumerate(h) if re.search(r"법조치\s*키", x)), -1),
          "no": next((i for i, x in enumerate(h) if re.search(r"사건\s*번호", x) and "당사" not in x), -1),
          "dkey": next((i for i, x in enumerate(h) if re.search(r"채무자\s*키", x)), -1)}
    if ki["lkey"] < 0 and ki["no"] < 0:
        return {"err": "「법조치키」나 「배당사건번호」 칸이 있어야 어느 줄인지 찾을 수 있어요"}
    fi = [(f, n, cv, next((i for i, x in enumerate(h) if re.search(rx, x) and not re.search(r"키|번호", x)), -1))
          for f, rx, n, cv in PASTE_FIELDS]
    fi = [x for x in fi if x[3] >= 0]
    if not fi:
        return {"err": "바꿀 칸(배당액·제3채무자·수령 단계 등)을 못 찾았어요"}
    live = [r for r in rows if not r.get("deleted")]
    ch, miss, same = [], [], 0
    for c in lines[1:]:
        c = [x.strip() for x in c] + [""] * len(h)
        L = [r for r in live if (ki["lkey"] < 0 or r.get("lkey") == c[ki["lkey"]]) and (ki["no"] < 0 or norm_no(r.get("no")) == norm_no(c[ki["no"]]))
             and (ki["dkey"] < 0 or r.get("dkey") == c[ki["dkey"]])]
        if not L:
            miss.append(" · ".join(x for x in c if x))
            continue
        if len(L) > 1 and ki["lkey"] < 0:
            miss.append(" · ".join(x for x in c if x) + " (여러 줄 — 법조치키를 같이 넣어 주세요)")
            continue
        r = L[0]
        for f, n, cv, i in fi:
            raw = c[i]
            if raw == "":
                continue
            v = cv(raw) if cv else raw
            if v == "":
                continue
            if str(r.get(f, "") if r.get(f) is not None else "") == str(v):
                same += 1
                continue
            ch.append({"id": r["id"], "f": f, "n": n, "from": r.get(f, ""), "to": v, "no": r["no"], "lkey": r.get("lkey", "")})
    keys = [{"lkey": "법조치키", "no": "배당사건번호", "dkey": "채무자키"}[k] for k, i in ki.items() if i >= 0]
    return {"keys": keys, "fields": [n for _, n, _, _ in fi], "ch": ch, "miss": miss, "same": same}
