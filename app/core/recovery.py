# -*- coding: utf-8 -*-
"""회수 분석 — 공통 양식 v2 읽기 · 검사 · 저장.

계산은 화면(recovery.html)이 한다. 여기서는
  ① 엑셀(공통 양식 v2)을 읽어 줄마다 검사하고 (점검표)
  ② 화면이 바로 조립할 수 있는 짧은 모양으로 바꿔
  ③ 채권 폴더/recovery/ 에 압축 저장한다.
주민번호는 앞 7자리만 읽어 연령대·성별로 바꾸고 원래 값은 어디에도 남기지 않는다.
"""
import datetime as dt
import gzip
import json
import os
import re
import shutil
import threading

EPOCH = dt.date(1970, 1, 1)
VERSION = 1

# ---------------------------------------------------------------- 양식 정의 (tools/make_common_template.py 와 같음)
# (머리글, 필수, 종류)  종류: key · text · date · amt · int
SHEETS = {
    "01_채권": [("채무자키", 1, "key"), ("계좌키", 1, "key"), ("채무자명", 0, "text"), ("담당자", 0, "text"), ("포트폴리오", 0, "text"),
              ("채권잔액", 1, "amt"), ("원금", 0, "amt"), ("법비용", 0, "amt"), ("시효도래일", 0, "date"), ("주민번호앞7", 0, "text"),
              ("기준일", 0, "date")],
    "02_법조치": [("법조치키", 1, "key"), ("채무자키", 1, "key"), ("계좌키", 0, "key"), ("법조치구분", 1, "text"), ("법조치세부", 0, "text"),
               ("법원", 0, "text"), ("사건번호", 0, "text"), ("신청일", 0, "date"), ("확정일자", 0, "date"), ("인용일자", 0, "date"),
               ("담당자", 0, "text"), ("송달일", 0, "date"), ("제3채무자유형", 0, "text")],
    "03_제3채무자": [("법조치키", 1, "key"), ("제3채무자명", 1, "text"), ("결정금액", 1, "amt")],
    "04_입금": [("채무자키", 1, "key"), ("계좌키", 0, "key"), ("입금일", 1, "date"), ("입금액", 1, "amt"), ("입금구분", 1, "text"),
              ("제3채무자", 0, "text"), ("법조치키", 0, "key")],
    "05_조정": [("채무자키", 1, "key"), ("계좌키", 0, "key"), ("조정구분", 1, "text"), ("약정일", 1, "date"), ("시작일", 0, "date"),
              ("회차", 0, "int"), ("회차당금액", 0, "amt"), ("약정총액", 0, "amt"), ("상태", 0, "text")],
    "06_해제": [("법조치키", 1, "key"), ("채무자키", 0, "key"), ("제3채무자명", 0, "text"), ("해제일", 1, "date"), ("해제사유원문", 0, "text"),
              ("해제사유구분", 0, "text")],
    "07_전자추심": [("법조치키", 0, "key"), ("채무자키", 0, "key"), ("채무자명", 0, "text"), ("제3채무자", 1, "text"), ("요청일", 1, "date"),
                ("추심요청액", 1, "amt")],
    "08_채무조정": [("채무자키", 1, "key"), ("구분", 1, "text"), ("신청일", 0, "date"), ("상태", 1, "text"), ("상태일", 0, "date")],
}
SHEET_NAMES = {"01_채권": "채권 목록 (계좌)", "02_법조치": "법조치", "03_제3채무자": "제3채무자 · 결정금액", "04_입금": "입금 내역",
               "05_조정": "조정 (분납·약정)", "06_해제": "해제", "07_전자추심": "전자추심 요청", "08_채무조정": "채무조정 (개인회생·파산·신용회복)"}
NEED_SHEETS = ("01_채권", "02_법조치")
# 양식 2줄 예시 (이 값과 거의 같으면 예시 줄로 보고 건너뜀)
EXAMPLE = {
    "01_채권": ["D900482", "A2099-00871", "사O아", "김담당", "99-Z 저축은행", 6930000, 5200000, 186000, "2029-03-02", "780512-1", "2026-11-01"],
    "02_법조치": ["L25-10016", "D900482", "A2099-00871", "압류추심", "예금", "서울중앙지방법원", "2025타채12345", "2025-03-04", "", "2025-03-18", "김담당", "", "예금+세무서"],
    "03_제3채무자": ["L25-10016", "주식회사 국민은행", 1610000],
    "04_입금": ["D900482", "A2099-00871", "2025-05-02", 412000, "추심금", "국민은행", "L25-10016"],
    "05_조정": ["D900482", "A2099-00871", "분납", "2025-04-03", "2025-04-25", 10, 100000, 1000000, "진행"],
    "06_해제": ["L25-10016", "D900482", "", "2025-09-10", "분납 약정 체결로 해제", ""],
    "07_전자추심": ["L25-10016", "D900482", "사O아", "국민은행", "2025-04-02", 412000],
    "08_채무조정": ["D900482", "개인회생", "2024-02-01", "폐지", "2025-06-10"],
}
CODES = {
    "법조치구분": ["지급명령", "소송", "압류추심", "경매", "가압류", "재산명시", "재산조회", "기타"],
    "입금구분": ["추심금", "배당금", "공탁금", "본인변제", "약정분납", "보증인", "제3자", "상계", "기타"],
    "조정구분": ["분납", "약정", "화해", "감면", "기타"],
    "해제사유구분": ["변제완납", "약정·분납", "회생·파산·면책", "오류·중복", "취하·기타", "모름"],
    "채무조정구분": ["개인회생", "파산", "신용회복"],
    "채무조정상태": ["진행", "인가", "폐지", "실효", "면책", "완제"],
}
REL_RULES = [("분납|분할|약정|화해", "약정·분납"), ("완납|완제|변제|상환|일시납", "변제완납"),
             ("회생|파산|면책|신복|채무조정", "회생·파산·면책"), ("오류|착오|중복|잘못|오기|오입력", "오류·중복"), ("취하|철회|기타", "취하·기타")]
PAY_KIND = CODES["입금구분"]
# 법조치 구분 + 세부 → 화면에서 쓰는 이름
TYPE_ORDER = ["지급명령", "소송", "예금 압류추심", "증권 압류추심", "급여 압류추심", "기타 압류추심", "부동산 경매", "기타 경매",
              "가압류", "재산명시", "재산조회", "기타"]


def act_type(g, s):
    g, s = (g or "").strip(), (s or "").strip()
    if g == "압류추심":
        return {"예금": "예금 압류추심", "증권": "증권 압류추심", "급여": "급여 압류추심"}.get(s, "기타 압류추심")
    if g == "경매":
        return "부동산 경매" if (not s or "부동산" in s) else "기타 경매"
    if g in ("지급명령", "소송", "가압류", "재산명시", "재산조회"):
        return g
    return "기타"


# ---------------------------------------------------------------- 은행 이름 맞추기
BANK_RULES = [
    (r"KB|국민", "국민은행"), (r"신한", "신한은행"), (r"우리", "우리은행"), (r"KEB|하나|외환", "하나은행"), (r"NH|농협|농축협|단위농협", "농협은행"),
    (r"IBK|기업", "IBK기업은행"), (r"우체국|우정사업", "우체국"), (r"새마을", "새마을금고"), (r"신협|신용협동", "신협"),
    (r"카카오", "카카오뱅크"), (r"토스", "토스뱅크"), (r"케이뱅크|K뱅크|K-?BANK", "케이뱅크"), (r"SC|제일", "SC제일은행"),
    (r"수협", "수협은행"), (r"씨티|CITI", "씨티은행"), (r"부산", "부산은행"), (r"iM|대구", "iM뱅크"), (r"경남", "경남은행"),
    (r"광주", "광주은행"), (r"전북", "전북은행"), (r"제주", "제주은행"), (r"KDB|산업", "산업은행"), (r"산림조합", "산림조합"),
]
NOT_BANK = re.compile(r"증권|투자|생명|화재|손해|보험|캐피탈|카드|저축은행|종합금융|자산운용|선물")


def clean_name(s):
    s = re.sub(r"주식회사|\(주\)|㈜|\(株\)", "", str(s or ""))
    return re.sub(r"\s+", "", s).strip()


def bank_name(s):
    """→ (맞춘 이름, 규칙으로 맞췄는지)"""
    c = clean_name(s)
    if not c:
        return "", True
    if NOT_BANK.search(c):  # 하나증권·KB손해보험 같은 것은 은행 규칙에 넣지 않음
        return c, True
    for pat, name in BANK_RULES:
        if re.search(pat, c, re.I):
            return name, True
    return c, bool(re.search(r"은행|금고|조합|뱅크", c))


# ---------------------------------------------------------------- 값 읽기

def day_of(d):
    return (d - EPOCH).days


def date_of(n):
    return EPOCH + dt.timedelta(days=int(n))


def parse_date(v):
    """→ 날 번호(1970-01-01 = 0) · None(빈칸) · False(못 읽음)"""
    if v is None or v == "":
        return None
    if isinstance(v, dt.datetime):
        return day_of(v.date())
    if isinstance(v, dt.date):
        return day_of(v)
    if isinstance(v, (int, float)):
        n = int(v)
        if 19000101 <= n <= 21001231:
            return parse_date(str(n))
        if 1 <= n < 80000:  # 엑셀 날짜 숫자
            return day_of(dt.date(1899, 12, 30) + dt.timedelta(days=n))
        return False
    s = str(v).strip()
    if not s:
        return None
    m = re.match(r"^(\d{4})\s*[-./년]\s*(\d{1,2})\s*[-./월]\s*(\d{1,2})", s) or re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
    if not m:
        return False
    try:
        return day_of(dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
    except ValueError:
        return False


def parse_amt(v):
    """→ 정수(원) · None(빈칸) · False(못 읽음)"""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return int(round(v))
    s = re.sub(r"[,\s원₩]", "", str(v))
    if not s:
        return None
    if re.fullmatch(r"\(?-?\d+(\.\d+)?\)?", s):
        neg = s.startswith("(") or s.startswith("-")
        n = int(round(float(s.strip("()-"))))
        return -n if neg else n
    return False


def key_of(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def text_of(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime("%Y-%m-%d")
    return str(v).strip()


FULL_RRN = re.compile(r"\d{6}\s*-?\s*\d{7}")


def age_sex(v, asof):
    """주민번호 앞 7자리 → (연령대, 성별). 못 읽으면 ('모름', '모름')"""
    s = re.sub(r"\D", "", text_of(v))
    if len(s) < 7:
        return "모름", "모름"
    g = s[6]
    cent = {"1": 1900, "2": 1900, "5": 1900, "6": 1900, "3": 2000, "4": 2000, "7": 2000, "8": 2000, "9": 1800, "0": 1800}[g]
    try:
        b = dt.date(cent + int(s[0:2]), int(s[2:4]), int(s[4:6]))
    except ValueError:
        return "모름", "모름"
    a = asof.year - b.year - ((asof.month, asof.day) < (b.month, b.day))
    band = "20대" if a < 30 else "30대" if a < 40 else "40대" if a < 50 else "50대" if a < 60 else "60대 이상"
    return band, ("남" if int(g) % 2 == 1 else "여")


# ---------------------------------------------------------------- 점검표

class Report:
    """오류 = 그 줄을 넣지 않음 · 주의 = 넣지만 확인 필요 · 정보 = 알려 둘 것"""
    LEVELS = ("오류", "주의", "정보")

    def __init__(self):
        self.items = {}  # (level, sheet, what) → {n, rows[]}

    def add(self, level, sheet, what, row=None, sample=""):
        k = (level, sheet, what)
        it = self.items.setdefault(k, {"n": 0, "rows": [], "sample": []})
        it["n"] += 1
        if row is not None and len(it["rows"]) < 12:
            it["rows"].append(row)
            if sample and len(it["sample"]) < 3:
                it["sample"].append(str(sample)[:60])

    def count(self, level):
        return sum(v["n"] for (lv, _, _), v in self.items.items() if lv == level)

    def rows(self):
        order = {lv: i for i, lv in enumerate(self.LEVELS)}
        out = [{"level": lv, "sheet": sh, "what": w, "n": v["n"], "rows": v["rows"], "sample": v["sample"]}
               for (lv, sh, w), v in self.items.items()]
        return sorted(out, key=lambda x: (order[x["level"]], x["sheet"], -x["n"]))


# ---------------------------------------------------------------- 읽기

def read_book(path):
    """엑셀 → {시트 이름: [줄(list)]}, 판 표시"""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        out, ver = {}, ""
        names = {re.sub(r"\s", "", n): n for n in wb.sheetnames}
        if "00_안내" in names:
            ws = wb[names["00_안내"]]
            for r in ws.iter_rows(min_row=1, max_row=1, max_col=2, values_only=True):
                if text_of(r[0]) == "공통양식":
                    ver = text_of(r[1]) if len(r) > 1 else ""
        for want in SHEETS:
            hit = names.get(want) or names.get(want.split("_", 1)[1])
            if hit:
                out[want] = [list(r) for r in wb[hit].iter_rows(values_only=True)]
        return out, ver
    finally:
        wb.close()


def _is_example(sheet, row):
    ex = EXAMPLE.get(sheet) or []
    if not ex or not row or text_of(row[0]) != text_of(ex[0]):  # 첫 칸(열쇠)까지 예시와 같아야 예시 줄
        return False
    hit = tot = 0
    for a, b in zip(row, ex):
        if b in ("", None):
            continue
        tot += 1
        if text_of(a) == text_of(b) or (parse_date(a) is not None and parse_date(a) == parse_date(b) and parse_date(a) is not False):
            hit += 1
    return tot and hit / tot >= .6


def _rows(sheet, raw, rep):
    """시트 줄 → [(엑셀 줄 번호, {칸: 값})] (필수·형식 검사 포함)"""
    spec = SHEETS[sheet]
    if not raw:
        return []
    head = [re.sub(r"\s", "", text_of(h)) for h in raw[0]]
    pos = {}
    for i, h in enumerate(head):
        if h and h not in pos:
            pos[h] = i
    miss = [h for h, req, _ in spec if req and h not in pos]
    for h in miss:
        rep.add("오류", sheet, f"꼭 있어야 하는 칸 「{h}」이 없음 — 시트 전체를 넣지 않음")
    if miss:
        return []
    for h, req, _ in spec:
        if not req and h not in pos:
            rep.add("정보", sheet, f"「{h}」 칸 없음 (없어도 됨)")
    if "주민번호앞7" in pos:  # 13자리가 하나라도 보이면 그 칸은 모두 버림
        i = pos["주민번호앞7"]
        if any(len(r) > i and FULL_RRN.search(text_of(r[i])) for r in raw[1:]):
            rep.add("오류", sheet, "주민번호 13자리가 보여 「주민번호앞7」 칸을 모두 버림 — 앞 7자리만 넣어 주세요")
            del pos["주민번호앞7"]
    out = []
    for n, r in enumerate(raw[1:], start=2):
        if not any(v not in (None, "") for v in r):
            continue
        ordered = [r[pos[h]] if h in pos and pos[h] < len(r) else None for h, _, _ in spec]
        if n == 2 and _is_example(sheet, ordered):
            rep.add("정보", sheet, "2줄 예시를 건너뜀", n)
            continue
        rec, bad = {}, False
        for (h, req, kind), v in zip(spec, ordered):
            if kind == "date":
                x = parse_date(v)
                if x is False:
                    rep.add("오류" if req else "주의", sheet, f"「{h}」 날짜를 못 읽음" + ("" if req else " — 빈칸으로 둠"), n, v)
                    x = None
                    bad = bad or bool(req)
            elif kind in ("amt", "int"):
                x = parse_amt(v)
                if x is False:
                    rep.add("오류" if req else "주의", sheet, f"「{h}」 숫자를 못 읽음" + ("" if req else " — 빈칸으로 둠"), n, v)
                    x = None
                    bad = bad or bool(req)
            elif kind == "key":
                x = key_of(v)
            else:
                x = text_of(v)
            if req and x in (None, ""):
                rep.add("오류", sheet, f"「{h}」이 비어 있음", n)
                bad = True
            rec[h] = x
        if not bad:
            out.append((n, rec))
    return out


def parse(path, rel_rules=None, today=None):
    """공통 양식 v2 파일 → (data, report)"""
    raw, ver = read_book(path)
    return parse_raw(raw, ver, rel_rules, today)


def parse_raw(raw, ver="v2", rel_rules=None, today=None):
    """{시트: [머리글, 줄...]} → (data, report). data 는 화면이 조립하는 짧은 모양. 오류 줄은 빼고 넣는다."""
    rep = Report()
    if ver != "v2":
        rep.add("주의" if raw else "오류", "00_안내", "공통 양식 v2 표시(A1 「공통양식」 · B1 「v2」)가 없음 — 시트 이름으로 읽음" if raw else
                "공통 양식 시트를 찾지 못함 (01_채권 · 02_법조치 …)")
    for sh in NEED_SHEETS:
        if sh not in raw:
            rep.add("오류", sh, "꼭 있어야 하는 시트가 없음")
    for sh in SHEETS:
        if sh not in raw and sh not in NEED_SHEETS:
            rep.add("정보", sh, "시트 없음 — 이 자료를 쓰는 분석은 비어 보임")
    rows = {sh: _rows(sh, raw.get(sh) or [], rep) for sh in SHEETS}
    today = today or dt.date.today()

    # 자료 기준일: 01_채권 기준일 중 가장 늦은 날, 없으면 입금·법조치 날짜 중 가장 늦은 날 (오늘을 넘지 않음)
    t = day_of(today)
    bases = [r["기준일"] for _, r in rows["01_채권"] if r.get("기준일") is not None]
    later = [r["입금일"] for _, r in rows["04_입금"]] + [r[k] for _, r in rows["02_법조치"] for k in ("신청일", "인용일자", "확정일자") if r.get(k) is not None]
    asof = min(t, max(bases) if bases else (max(later) if later else t))
    asof_d = date_of(asof)

    # 채무자 · 계좌
    D, A, di, ai = [], [], {}, {}
    for n, r in rows["01_채권"]:
        k = r["채무자키"]
        if k not in di:
            age, sex = age_sex(r.get("주민번호앞7"), asof_d) if r.get("주민번호앞7") else ("모름", "모름")
            di[k] = len(D)
            D.append([k, r.get("채무자명") or "", r.get("담당자") or "", r.get("포트폴리오") or "", age, sex])
        if r["계좌키"] in ai:
            rep.add("주의", "01_채권", "계좌키가 겹침 — 처음 줄만 씀", n, r["계좌키"])
            continue
        if r["채권잔액"] < 0:
            rep.add("주의", "01_채권", "채권잔액이 음수", n, r["채권잔액"])
        ai[r["계좌키"]] = len(A)
        A.append([r["계좌키"], di[k], r["채권잔액"], r.get("원금"), r.get("법비용"), r.get("시효도래일")])
    no_age = sum(1 for d in D if d[4] == "모름")
    if D and no_age:
        rep.add("정보", "01_채권", f"연령대를 모르는 채무자 {no_age:,}명 (주민번호앞7 비었거나 못 읽음)")

    def acct(sheet, n, r):
        k = r.get("계좌키") or ""
        if not k:
            return -1
        if k not in ai:
            rep.add("주의", sheet, "01_채권에 없는 계좌키 — 계좌 연결만 뺌", n, k)
            return -1
        return ai[k]

    # 법조치
    L, li = [], {}
    owner_less = 0
    for n, r in rows["02_법조치"]:
        k, dk = r["법조치키"], r["채무자키"]
        if k in li:
            rep.add("주의", "02_법조치", "법조치키가 겹침 — 처음 줄만 씀", n, k)
            continue
        if dk not in di:
            rep.add("주의", "02_법조치", "01_채권에 없는 채무자키 — 넣지 않음", n, dk)
            continue
        g = r["법조치구분"]
        if g not in CODES["법조치구분"]:
            rep.add("주의", "02_법조치", "코드표에 없는 법조치구분 — 「기타」로 셈", n, g)
        typ = act_type(g, r.get("법조치세부"))
        ap, cite, conf, sv = r.get("신청일"), r.get("인용일자"), r.get("확정일자"), r.get("송달일")
        if ap is None:
            ap = cite if cite is not None else conf
            if ap is None:
                rep.add("오류", "02_법조치", "신청일 · 인용일자 · 확정일자가 모두 비어 있음", n, k)
                continue
            rep.add("주의", "02_법조치", "신청일 없음 — 인용일자·확정일자로 대신함", n, k)
        if cite is not None and cite < ap:
            rep.add("주의", "02_법조치", "인용일자가 신청일보다 빠름", n, k)
        if conf is not None and conf < ap:
            rep.add("주의", "02_법조치", "확정일자가 신청일보다 빠름", n, k)
        if ap > asof:
            rep.add("주의", "02_법조치", "신청일이 자료 기준일보다 늦음", n, k)
        own = r.get("담당자") or D[di[dk]][2]
        owner_less += 0 if own else 1
        li[k] = len(L)
        L.append([k, di[dk], acct("02_법조치", n, r), typ, r.get("법원") or "", r.get("사건번호") or "", ap, conf, cite, sv, own,
                  1 if (typ.endswith("압류추심") and cite is None) else 0, r.get("제3채무자유형") or ""])
    est = sum(1 for x in L if x[11])
    if est:
        rep.add("정보", "02_법조치", f"압류추심 인용일자 없음 {est:,}건 — 신청일 + 기준 날수로 추정")
    if L and not any(x[9] is not None for x in L):
        rep.add("정보", "02_법조치", "송달일 칸이 없거나 비어 있음 — 인용일·신청일 + 기준 날수로 추정 (회수 분석 기준에서 바꿈)")

    def act(sheet, n, k, need=True):
        if not k:
            return -1
        if k not in li:
            rep.add("주의", sheet, "02_법조치에 없는 법조치키" + (" — 넣지 않음" if need else " — 법조치 연결만 뺌"), n, k)
            return None if need else -1
        return li[k]

    # 제3채무자
    B, unmatched = [], {}
    for n, r in rows["03_제3채무자"]:
        x = act("03_제3채무자", n, r["법조치키"])
        if x is None:
            continue
        nm, ok = bank_name(r["제3채무자명"])
        if not ok and L[x][3] in ("예금 압류추심", "증권 압류추심"):
            unmatched[nm] = unmatched.get(nm, 0) + 1
        if r["결정금액"] <= 0:
            rep.add("주의", "03_제3채무자", "결정금액이 0 이하", n, r["결정금액"])
        B.append([x, nm, r["결정금액"]])
    for nm, c in sorted(unmatched.items(), key=lambda kv: -kv[1])[:30]:
        rep.add("정보", "03_제3채무자", f"은행 이름 규칙에 없는 이름 「{nm}」 {c}건 — 그대로 씀")

    # 입금
    P, banks, bidx = [], [], {}

    def bank_i(s):
        nm = bank_name(s)[0]
        if not nm:
            return -1
        if nm not in bidx:
            bidx[nm] = len(banks)
            banks.append(nm)
        return bidx[nm]
    for n, r in rows["04_입금"]:
        dk = r["채무자키"]
        if dk not in di:
            rep.add("주의", "04_입금", "01_채권에 없는 채무자키 — 넣지 않음", n, dk)
            continue
        kind = r["입금구분"]
        if kind not in PAY_KIND:
            rep.add("주의", "04_입금", "코드표에 없는 입금구분 — 「기타」로 셈", n, kind)
            kind = "기타"
        if r["입금일"] > asof:
            rep.add("주의", "04_입금", "입금일이 자료 기준일보다 늦음 — 계산에서 빠질 수 있음", n, date_of(r["입금일"]))
        if kind == "추심금" and not r.get("제3채무자") and not r.get("법조치키"):
            rep.add("주의", "04_입금", "추심금인데 제3채무자·법조치키가 모두 비어 있음 — 은행별 성과에서 빠질 수 있음", n)
        P.append([di[dk], r["입금일"], r["입금액"], PAY_KIND.index(kind), bank_i(r.get("제3채무자")), act("04_입금", n, r.get("법조치키"), need=False),
                  acct("04_입금", n, r)])

    # 조정(약정)
    C = []
    for n, r in rows["05_조정"]:
        dk = r["채무자키"]
        if dk not in di:
            rep.add("주의", "05_조정", "01_채권에 없는 채무자키 — 넣지 않음", n, dk)
            continue
        cat = r["조정구분"] if r["조정구분"] in CODES["조정구분"] else "기타"
        C.append([di[dk], cat, r["약정일"], r.get("시작일"), r.get("회차"), r.get("회차당금액"), r.get("약정총액"), r.get("상태") or "", acct("05_조정", n, r)])

    # 해제
    rules = [(re.compile(p), c) for p, c in (rel_rules or REL_RULES)]
    R, unk = [], 0
    for n, r in rows["06_해제"]:
        x = act("06_해제", n, r["법조치키"])
        if x is None:
            continue
        cat = r.get("해제사유구분") or ""
        if cat and cat not in CODES["해제사유구분"]:
            rep.add("주의", "06_해제", "코드표에 없는 해제사유구분 — 원문으로 다시 나눔", n, cat)
            cat = ""
        txt = r.get("해제사유원문") or ""
        if not cat:
            cat = next((c for p, c in rules if p.search(txt)), "모름")
        unk += cat == "모름"
        if r["해제일"] < L[x][6]:
            rep.add("주의", "06_해제", "해제일이 신청일보다 빠름", n, r["법조치키"])
        R.append([x, L[x][1], r["해제일"], txt, cat, clean_name(r.get("제3채무자명"))])
    if unk:
        rep.add("정보", "06_해제", f"사유를 나누지 못한 해제 {unk:,}건 — 「회수 자료 넣기」 해제 사유 나누기에서 골라 주세요")

    # 전자추심
    E = []
    for n, r in rows["07_전자추심"]:
        x = act("07_전자추심", n, r.get("법조치키"), need=False) if r.get("법조치키") else -1
        dk = r.get("채무자키") or (D[L[x][1]][0] if x >= 0 else "")
        if x < 0 and not dk:
            rep.add("오류", "07_전자추심", "법조치키 · 채무자키가 모두 비어 있음", n)
            continue
        if dk not in di:
            rep.add("주의", "07_전자추심", "01_채권에 없는 채무자키 — 넣지 않음", n, dk)
            continue
        E.append([x, di[dk], bank_name(r["제3채무자"])[0], r["요청일"], r["추심요청액"]])

    # 채무조정 (개인회생·파산·신용회복 상태)
    X = []
    for n, r in rows["08_채무조정"]:
        dk = r["채무자키"]
        if dk not in di:
            rep.add("주의", "08_채무조정", "01_채권에 없는 채무자키 — 넣지 않음", n, dk)
            continue
        kind, st = r["구분"], r["상태"]
        if kind not in CODES["채무조정구분"]:
            rep.add("주의", "08_채무조정", "구분은 개인회생·파산·신용회복 중 하나 — 넣지 않음", n, kind)
            continue
        if st not in CODES["채무조정상태"]:
            rep.add("주의", "08_채무조정", "상태는 진행·인가·폐지·실효·면책·완제 중 하나 — 「진행」으로 셈", n, st)
            st = "진행"
        day = r.get("상태일") if r.get("상태일") is not None else r.get("신청일")
        if day is None:
            rep.add("주의", "08_채무조정", "상태일·신청일이 모두 비어 있음 — 넣지 않음", n, dk)
            continue
        X.append([di[dk], kind, r.get("신청일"), st, day])
    if L and not any(x[12] for x in L):
        rep.add("정보", "02_법조치", "제3채무자유형 칸이 없거나 비어 있음 — 통계 「세무서 미압류」를 셀 수 없음")

    no_act = len(D) - len({x[1] for x in L})
    if D:
        rep.add("정보", "01_채권", f"법조치 없는 채무자 {no_act:,}명 — 비교 집단으로 씀")
    counts = {"채무자": len(D), "계좌": len(A), "법조치": len(L), "제3채무자": len(B), "입금": len(P), "약정": len(C), "해제": len(R), "전자추심": len(E),
              "채무조정": len(X)}
    data = {"v": VERSION, "asof": asof, "D": D, "A": A, "L": L, "B": B, "P": P, "PK": PAY_KIND, "PB": banks, "C": C, "R": R, "E": E, "X": X}
    return data, {"ver": ver, "asof": date_of(asof).isoformat(), "counts": counts, "items": rep.rows(),
                  "errors": rep.count("오류"), "warns": rep.count("주의"), "ok": bool(D) and bool(L) and not any(
                      it["level"] == "오류" and it["sheet"] in NEED_SHEETS and "시트" in it["what"] for it in rep.rows())}


# ---------------------------------------------------------------- 저장

class RecoveryStore:
    """채권 폴더/recovery/ — data.json.gz(자료) · state.json(판단·처리 기록) · history.json(넣은 이력) · backup/"""

    def __init__(self, root):
        self.root = os.path.join(root, "recovery")
        self.lock = threading.RLock()
        self._blob = None  # 화면으로 넘길 JSON 글자 (한 번 만들어 둠)

    def _p(self, name):
        return os.path.join(self.root, name)

    def has(self):
        return os.path.isfile(self._p("data.json.gz"))

    def history(self):
        try:
            with open(self._p("history.json"), encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def blob(self):
        with self.lock:
            if self._blob is None and self.has():
                with gzip.open(self._p("data.json.gz"), "rt", encoding="utf-8") as f:
                    self._blob = f.read()
            return self._blob

    def save_data(self, data, info):
        with self.lock:
            os.makedirs(self.root, exist_ok=True)
            if self.has():
                self._backup("data.json.gz", "data")
            s = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            tmp = self._p("data.json.gz.tmp")
            with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as f:
                f.write(s)
            os.replace(tmp, self._p("data.json.gz"))
            self._blob = s
            h = [info] + self.history()
            self._write("history.json", h[:60])

    def clear(self):
        with self.lock:
            if self.has():
                self._backup("data.json.gz", "data")
                os.remove(self._p("data.json.gz"))
            self._blob = None

    def state(self, demo=False):
        try:
            with open(self._p("state_demo.json" if demo else "state.json"), encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def save_state(self, st, demo=False):
        with self.lock:
            os.makedirs(self.root, exist_ok=True)
            name = "state_demo.json" if demo else "state.json"
            if not demo:
                self._backup(name, "state", daily=True)
            self._write(name, st)

    def _write(self, name, obj):
        tmp = self._p(name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        os.replace(tmp, self._p(name))

    def _backup(self, name, prefix, daily=False, keep=20):
        src = self._p(name)
        if not os.path.isfile(src):
            return
        d = self._p("backup")
        os.makedirs(d, exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y%m%d" if daily else "%Y%m%d_%H%M%S")
        dst = os.path.join(d, f"{prefix}_{stamp}" + (".json.gz" if name.endswith(".gz") else ".json"))
        if daily and os.path.exists(dst):
            return
        shutil.copy2(src, dst)
        olds = sorted(f for f in os.listdir(d) if f.startswith(prefix + "_"))
        for f in olds[:-keep]:
            try:
                os.remove(os.path.join(d, f))
            except OSError:
                pass


# ---------------------------------------------------------------- 엑셀로 내보내기

def write_report(path, rep, src=""):
    """점검표 → 엑셀 (VBA 고칠 곳 찾기용)"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "점검표"
    ws.append(["파일", src])
    ws.append(["자료 기준일", rep.get("asof", "")])
    ws.append(["오류", rep.get("errors", 0), "주의", rep.get("warns", 0)])
    ws.append([])
    ws.append(["구분", "시트", "내용", "건수", "엑셀 줄 번호 (앞 12개)", "값 예시"])
    for c in ws[5]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="141414")
    for it in rep.get("items", []):
        ws.append([it["level"], it["sheet"], it["what"], it["n"], ", ".join(map(str, it["rows"])), " / ".join(it.get("sample") or [])])
    ws.freeze_panes = "A6"
    for col, w in zip("ABCDEF", (8, 14, 70, 8, 30, 40)):
        ws.column_dimensions[col].width = w
    cs = wb.create_sheet("건수")
    cs.append(["자료", "건수"])
    for k, v in (rep.get("counts") or {}).items():
        cs.append([k, v])
    wb.save(path)
    return path


def write_template_rows(path, sheets):
    """{시트: [줄]} → 공통 양식 v2 모양 엑셀 (예시 파일 만들기)"""
    from openpyxl import Workbook
    wb = Workbook(write_only=True)
    g = wb.create_sheet("00_안내")
    g.append(["공통양식", "v2", "← 예시 자료로 만든 파일 (가짜 채무자)"])
    for sh, spec in SHEETS.items():
        ws = wb.create_sheet(sh)
        ws.append([h for h, _, _ in spec])
        for r in sheets.get(sh) or []:
            ws.append(r)
    wb.save(path)
    return path
