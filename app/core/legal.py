# -*- coding: utf-8 -*-
"""법조치 계산: 기준표(법령 값) · 비용 · 압류금지 · 기한 · 배당 · 송달 사유.

법령 값은 코드에 박지 않고 기준표(STANDARDS)에 「시행일별 값」으로 둔다.
사용자가 바꾼 값은 자료 폴더의 standards.json 에 저장되고 여기 기본값 위에 덮어쓴다.
계산 결과는 모두 「예상」이다 — 화면에서도 그렇게 표시한다.
"""
import copy
import datetime as dt
import re

# ---------------------------------------------------------------- 기준표 기본값 (2026-11-01 웹 확인)
# check: 확인한 날·출처. 비어 있으면 「확인 필요」로 표시한다.

_SRC_SVC = "korea.legal 「법원 송달료 1회분 5,640원으로 인상(2026.7.1)」 조견표"
_SRC_MJ = "korea.legal 민사집행법 시행령 제3·4·6·7조 (2026.1.27 개정, 2026.2.1 시행)"
_SRC_STAMP = "korea.legal 민사소송 등 인지법 제7·9·16조"

STANDARDS = {
    "svc": {"name": "송달료 1회분", "unit": "원", "basis": "송달료규칙 · 업무처리요령 (e-Post 적용 사건)",
            "rows": [{"from": "2025-06-01", "v": 5500, "check": "2026-11-01 · " + _SRC_SVC},
                     {"from": "2026-07-01", "v": 5640, "check": "2026-11-01 · " + _SRC_SVC}]},
    "pay_times": {"name": "독촉(지급명령) 송달료", "unit": "회분 × 당사자", "basis": "송달료 업무처리요령 별표 (독촉 「차」)",
                  "rows": [{"from": "2000-01-01", "v": 6, "check": "2026-11-01 · " + _SRC_SVC}]},
    "garn_times": {"name": "채권압류·추심 송달료", "unit": "회분 × 당사자", "basis": "송달료 업무처리요령 별표 (기타집행)",
                   "rows": [{"from": "2000-01-01", "v": 2, "check": "2026-11-01 · 법원 송달료표 「기타집행 당사자수×2회분」"}]},
    "ecfs": {"name": "전자소송 인지 비율", "unit": "배", "basis": "민사소송 등 인지법 제16조 (전자문서 제출 시 10분의 9)",
             "rows": [{"from": "2011-05-02", "v": 0.9, "check": "2026-11-01 · " + _SRC_STAMP}]},
    "garn_stamp": {"name": "강제집행 신청 인지 (압류·추심 각각)", "unit": "원", "basis": "민사소송 등 인지법 제9조 제1항",
                   "rows": [{"from": "2000-01-01", "v": 2000, "check": "2026-11-01 · " + _SRC_STAMP}]},
    "wage_floor": {"name": "급여 압류금지 최저금액 (월)", "unit": "원", "basis": "민사집행법 시행령 제3조 · 압류명령 신청 접수일 기준",
                   "rows": [{"from": "2019-04-01", "v": 1850000, "check": ""},
                            {"from": "2026-02-01", "v": 2500000, "check": "2026-11-01 · " + _SRC_MJ}]},
    "wage_high": {"name": "급여 압류금지 최고금액 기준 (월)", "unit": "원", "basis": "민사집행법 시행령 제4조: 기준 + (급여의 1/2 − 기준) × 1/2",
                  "rows": [{"from": "2011-07-06", "v": 3000000, "check": "2026-11-01 · " + _SRC_MJ}]},
    "dep_floor": {"name": "예금 압류금지 (개인별 합산)", "unit": "원", "basis": "민사집행법 시행령 제7조",
                  "rows": [{"from": "2019-04-01", "v": 1850000, "check": ""},
                           {"from": "2026-02-01", "v": 2500000, "check": "2026-11-01 · " + _SRC_MJ}]},
    "ins_floor": {"name": "보장성 보험 해약·만기환급금 압류금지", "unit": "원", "basis": "민사집행법 시행령 제6조 (계약 합산)",
                  "rows": [{"from": "2011-07-06", "v": 1500000, "check": ""},
                           {"from": "2026-02-01", "v": 2500000, "check": "2026-11-01 · " + _SRC_MJ}]},
}

ZONES = ["서울", "과밀억제권역 등", "광역시 등", "그 밖의 지역"]
_SRC_HOUSE = "korea.legal 주택임대차보호법 시행령 제11조 · 찾기쉬운생활법령 2016 개정 안내"
# 소액임차인: 선순위 담보물권 설정일이 속한 줄. v = [[보증금 한도, 최우선 금액] × ZONES]
SMALL_TENANT = [
    {"from": "2010-07-26", "v": [[75e6, 25e6], [65e6, 22e6], [55e6, 19e6], [40e6, 14e6]], "check": ""},
    {"from": "2014-01-01", "v": [[95e6, 32e6], [80e6, 27e6], [60e6, 20e6], [45e6, 15e6]], "check": "서울·광역시·그 밖 확인 / 과밀 확인 필요 · " + _SRC_HOUSE},
    {"from": "2016-03-31", "v": [[100e6, 34e6], [80e6, 27e6], [60e6, 20e6], [50e6, 17e6]], "check": "서울·광역시·그 밖 확인 / 과밀 확인 필요 · " + _SRC_HOUSE},
    {"from": "2018-09-18", "v": [[110e6, 37e6], [100e6, 34e6], [60e6, 20e6], [50e6, 17e6]], "check": ""},
    {"from": "2021-05-11", "v": [[150e6, 50e6], [130e6, 43e6], [70e6, 23e6], [60e6, 20e6]], "check": ""},
    {"from": "2023-02-21", "v": [[165e6, 55e6], [145e6, 48e6], [85e6, 28e6], [75e6, 25e6]], "check": "보증금 한도 확인 / 최우선 금액은 2차 자료 · " + _SRC_HOUSE},
]

# 기한 계산용 쉬는 날 (토·일은 자동). 대체공휴일 포함 — 해마다 확인해 더한다.
HOLIDAYS = [
    "2026-01-01", "2026-02-16", "2026-02-17", "2026-02-18", "2026-03-02", "2026-05-05", "2026-05-25", "2026-06-03",
    "2026-08-17", "2026-09-24", "2026-09-25", "2026-09-28", "2026-10-05", "2026-10-09", "2026-12-25",
    "2027-01-01", "2027-02-08", "2027-02-09", "2027-03-01", "2027-05-05", "2027-05-13", "2027-08-16", "2027-09-14",
    "2027-09-15", "2027-09-16", "2027-10-04", "2027-10-11", "2027-12-27",
]


def default_standards():
    return {"items": copy.deepcopy(STANDARDS), "small": copy.deepcopy(SMALL_TENANT), "holidays": list(HOLIDAYS)}


def merge_standards(saved):
    """저장된 기준표(사용자가 고친 것)를 기본값 위에. 새 판에서 생긴 항목은 기본값으로 채운다."""
    out = default_standards()
    if not saved:
        return out
    for k, it in (saved.get("items") or {}).items():
        if k in out["items"] and it.get("rows"):
            out["items"][k]["rows"] = it["rows"]
    if saved.get("small"):
        out["small"] = saved["small"]
    if saved.get("holidays") is not None:
        out["holidays"] = saved["holidays"]
    return out


def today():
    return dt.date.today().isoformat()


def value(std, key, date=None):
    """date(YYYY-MM-DD)에 맞는 값. date 가 없으면 오늘."""
    date = date or today()
    rows = sorted(std["items"][key]["rows"], key=lambda r: r["from"])
    cur = rows[0]
    for r in rows:
        if r["from"] <= date:
            cur = r
    return cur["v"]


def row_at(std, key, date=None):
    date = date or today()
    rows = sorted(std["items"][key]["rows"], key=lambda r: r["from"])
    cur = rows[0]
    for r in rows:
        if r["from"] <= date:
            cur = r
    return cur


# ---------------------------------------------------------------- 인지·송달료

def suit_stamp(v):
    """소장 인지 (민사소송 등 인지법 제2조), 반올림 전"""
    v = max(0, float(v))
    if v < 1e7:
        return v * 0.005
    if v < 1e8:
        return v * 0.0045 + 5000
    if v < 1e9:
        return v * 0.004 + 55000
    return v * 0.0035 + 555000


def round_stamp(x):
    """1천원 미만이면 1천원, 그 위는 100원 미만 버림"""
    return 1000 if x < 1000 else int(x // 100 * 100)


def pay_order_fee(std, claim, parties=2, ecfs=True, date=None):
    stamp = suit_stamp(claim) / 10
    if ecfs:
        stamp *= value(std, "ecfs", date)
    unit, times = value(std, "svc", date), value(std, "pay_times", date)
    return {"stamp": round_stamp(stamp), "svc": int(parties * times * unit), "unit": unit, "times": times, "parties": parties}


def garnish_fee(std, third, collect=True, date=None):
    """채권압류(및 추심)명령. 인지는 신청마다 — 압류+추심이면 두 번."""
    st = value(std, "garn_stamp", date) * (2 if collect else 1)
    unit, times = value(std, "svc", date), value(std, "garn_times", date)
    parties = 2 + max(0, int(third))
    return {"stamp": int(st), "svc": int(parties * times * unit), "unit": unit, "times": times, "parties": parties}


# ---------------------------------------------------------------- 압류금지

def man(n):
    v = round(n / 10000)
    if v >= 10000:
        return f"{v // 10000}억" + (f" {v % 10000:,}만" if v % 10000 else "")
    return f"{v:,}만"


def wage_exempt(std, wage, date=None):
    """월 급여(세금 등 뺀 금액) → 압류금지 금액·이유"""
    w = max(0, float(wage))
    floor, high = value(std, "wage_floor", date), value(std, "wage_high", date)
    half = w / 2
    if w <= floor:
        return {"ex": w, "can": 0, "why": f"월 {man(floor)} 이하 → 전부 압류금지"}
    if half <= floor:
        ex, why = floor, f"급여의 1/2({man(half)})이 최저 {man(floor)}보다 적음 → {man(floor)}"
    elif half <= high:
        ex, why = half, "급여의 1/2"
    else:
        ex = high + (half - high) / 2
        why = f"1/2이 {man(high)} 넘음 → {man(high)} + (1/2 − {man(high)}) × 1/2"
    return {"ex": ex, "can": max(0, w - ex), "why": why}


ASSET_KINDS = ["급여", "예금", "보험", "부동산", "자동차", "임차보증금", "그 밖"]


def assets_calc(std, assets, debt, date=None):
    """재산 목록 → 재산별 회수 가능 금액과 결론. 예금은 개인별 합산으로 압류금지를 뺀다."""
    out, deps, insr = [], [a for a in assets if a.get("kind") == "예금"], [a for a in assets if a.get("kind") == "보험"]
    dep_floor, ins_floor = value(std, "dep_floor", date), value(std, "ins_floor", date)
    dep_total = sum(float(a.get("amt") or 0) for a in deps)
    ins_total = sum(float(a.get("amt") or 0) for a in insr)
    dep_can = max(0, dep_total - dep_floor)
    ins_can = max(0, ins_total - ins_floor)
    monthly = 0
    for a in assets:
        amt, amt2 = float(a.get("amt") or 0), float(a.get("amt2") or 0)
        r = {"id": a.get("id"), "kind": a.get("kind"), "name": a.get("name", ""), "src": a.get("src", ""), "at": a.get("at", ""),
             "amt": amt, "amt2": amt2, "third": a.get("third", "")}
        if a.get("kind") == "급여":
            w = wage_exempt(std, amt, date)
            monthly += w["can"]
            r.update(ex=w["ex"], why=w["why"], can=w["can"], can_text=f"월 {man(w['can'])}", verdict="추천" if w["can"] > 0 else "실익 없음")
        elif a.get("kind") == "예금":
            share = dep_can * (amt / dep_total) if dep_total else 0
            r.update(ex=None, why=f"예금 {len(deps)}곳 합산 {man(dep_total)}에서 {man(dep_floor)}를 뺌 · 송달되는 날 잔액 기준",
                     can=share, can_text=man(share), verdict="추천" if share > 0 else "실익 없음")
        elif a.get("kind") == "보험":
            share = ins_can * (amt / ins_total) if ins_total else 0
            r.update(ex=None, why=f"보장성 보험 해약환급금 합산 {man(ins_total)}에서 {man(ins_floor)}를 뺌",
                     can=share, can_text=man(share), verdict="검토" if share > 0 else "실익 없음")
        elif a.get("kind") in ("부동산",):
            can = max(0, amt - amt2)
            r.update(ex=None, why="시세에서 선순위(근저당 등)를 뺀 값 · 배당 예상에서 자세히", can=can, can_text=f"약 {man(can)}",
                     verdict="검토" if can > 0 else "실익 없음")
        elif a.get("kind") == "자동차":
            can = max(0, amt - amt2)
            r.update(ex=None, why="시세에서 경매 비용을 뺀 값", can=can, can_text=man(can), verdict="검토" if can >= 2_000_000 else "보류")
        else:
            r.update(ex=None, why="직접 판단", can=amt, can_text=man(amt) if amt else "—", verdict="검토" if amt else "조사 필요")
        out.append(r)
    now_can = sum(r["can"] for r in out if r["kind"] in ("예금",))
    months = None
    if monthly > 0:
        months = max(0, -(-(debt - now_can) // monthly))
    third = [r for r in out if r["kind"] in ("급여", "예금", "보험", "임차보증금") and r["verdict"] in ("추천", "검토") and r["can"] > 0]
    return {"rows": out, "now": now_can, "monthly": monthly, "months": months, "third": third,
            "floors": {"dep": dep_floor, "ins": ins_floor, "wage": value(std, "wage_floor", date)}}


# ---------------------------------------------------------------- 기한 (민법 제157조 초일 불산입, 제161조 말일이 토·공휴일이면 다음 날)

def is_off(std, d):
    return d.weekday() >= 5 or d.isoformat() in (std.get("holidays") or [])


def due_of(std, start, days):
    """start: 받은 날. 다음 날부터 days 일째, 쉬는 날이면 다음 평일."""
    d0 = dt.date.fromisoformat(start)
    raw = d0 + dt.timedelta(days=int(days))
    d = raw
    while is_off(std, d):
        d += dt.timedelta(days=1)
    return {"due": d.isoformat(), "raw": raw.isoformat(), "moved": d != raw}


# ---------------------------------------------------------------- 배당 (판단 보조)

def small_tenant(std, date, zone):
    cur = None
    for r in sorted(std["small"], key=lambda r: r["from"]):
        if r["from"] <= date:
            cur = r
    if not cur:
        return None
    lim, amt = cur["v"][int(zone)]
    return {"from": cur["from"], "limit": lim, "amt": amt, "check": cur.get("check", "")}


def distribution(std, v):
    """v: apprl, rate, cost, zone, mort(설정일), mort_amt, depo, fix(확정일자), tax, ours, others"""
    f = lambda k: float(v.get(k) or 0)  # noqa: E731
    sale = f("apprl") * f("rate") / 100
    left = sale
    lines = []

    def take(rank, name, sub, want):
        nonlocal left
        got = min(want, max(left, 0))
        left -= got
        lines.append({"rank": rank, "name": name, "sub": sub, "want": want, "got": got})

    take(0, "집행비용", "경매 신청비·감정료 등", f("cost"))
    st = small_tenant(std, v.get("mort") or today(), int(v.get("zone") or 0))
    pri, cap = 0.0, False
    if st and f("depo") and f("depo") <= st["limit"]:
        pri = min(st["amt"], f("depo"))
        half = (sale - f("cost")) / 2  # 주택가액의 1/2 한도
        if pri > half:
            pri, cap = max(half, 0), True
        sub = f"{st['from']}~ 기준 · {ZONES[int(v.get('zone') or 0)]} {man(st['limit'])} 이하 → {man(st['amt'])}" + (" (1/2 한도)" if cap else "")
    elif st:
        sub = f"보증금 {man(f('depo'))} > 한도 {man(st['limit'])} → 해당 없음" if f("depo") else "임차인 없음"
    else:
        sub = "기준표에 그 날짜가 없음"
    take(1, "소액임차인 최우선변제", sub, pri)
    take(2, "당해세", "그 부동산에 매긴 세금", f("tax"))
    mort = lambda: take(3, f"근저당 ({v['mort']})" if v.get("mort") else "근저당", "실제 채권액", f("mort_amt"))  # noqa: E731
    fix = lambda: take(4, f"확정일자 임차인 ({v['fix']})" if v.get("fix") else "확정일자 임차인", "남은 보증금", max(0, f("depo") - pri))  # noqa: E731
    if v.get("fix") and v.get("mort") and v["fix"] < v["mort"]:
        fix(), mort()
    else:
        mort(), fix()
    rest = max(left, 0)
    tot = f("ours") + f("others")
    ours = min(f("ours"), rest * f("ours") / tot) if tot else 0
    others = min(f("others"), rest * f("others") / tot) if tot else 0
    return {"sale": sale, "lines": lines, "rest": rest, "ours": ours, "others": others, "surplus": max(0, rest - ours - others),
            "small": st}


def break_even(std, v, cost):
    for r in range(40, 101):
        if distribution(std, dict(v, rate=r))["ours"] >= cost:
            return r
    return None


# ---------------------------------------------------------------- 송달 안 됨

DLV_WORDS = ["폐문부재", "수취인불명", "이사불명", "주소불명", "수취인부재", "송달불능"]


def dlv_reason(text):
    for w in DLV_WORDS:
        if w in (text or "").replace(" ", ""):
            return w
    return ""


def case_kind(dvs):
    dvs = dvs or ""
    if dvs in ("차", "차전"):
        return "지급명령"
    if dvs.startswith("타채"):
        return "채권압류"
    if dvs.startswith("타경"):
        return "경매"
    if dvs.startswith("가") or dvs in ("나", "다"):
        return "소송"
    return "기타"


ACTIONS = ["새 주소로 보정", "재송달", "야간·휴일 특별송달", "공시송달 신청", "소제기 신청 (소송으로)", "초본 발급 요청"]


def recommend(kind, reason, cnt, new_addr=False):
    if kind == "채권압류":
        return "재송달"
    if reason in ("이사불명", "수취인불명", "주소불명"):
        return "새 주소로 보정" if new_addr else "초본 발급 요청"
    if reason in ("폐문부재", "수취인부재"):
        if kind == "지급명령" and cnt >= 3:
            return "소제기 신청 (소송으로)"
        return "야간·휴일 특별송달"
    return "재송달"


def action_allowed(kind, act):
    """지급명령은 공시송달 불가(민사소송법 제462조 단서) → 소제기 신청 뒤 소송에서. 소제기 신청은 지급명령만."""
    if act == "공시송달 신청" and kind == "지급명령":
        return False, "지급명령은 공시송달을 할 수 없어요 — 소제기 신청 뒤 소송에서 가능"
    if act == "소제기 신청 (소송으로)" and kind != "지급명령":
        return False, "지급명령 사건에서만 해요"
    return True, ""


# ---------------------------------------------------------------- 회생·파산

FLOW = {
    "개인회생": ["신청", "금지·중지명령", "개시결정", "채권자목록 이의", "변제계획 인가", "변제", "면책"],
    "파산·면책": ["신청", "파산선고", "채권신고 (관재인 선임 시)", "면책 심리 · 이의", "면책 결정"],
    "법인회생": ["신청", "보전처분·중지명령", "개시결정", "채권신고", "관계인집회", "인가"],
}
DOC_STAGE = {"금지명령": ("개인회생", 1), "중지명령": ("개인회생", 1), "개시결정": ("개인회생", 2), "채권자목록 송달": ("개인회생", 3),
             "파산선고": ("파산·면책", 1), "면책 심리 통지": ("파산·면책", 3), "보전처분": ("법인회생", 1), "공공정보 등재": (None, 0)}


def rehab_action(kind, stage):
    s = FLOW[kind][min(stage, len(FLOW[kind]) - 1)]
    if s == "채권자목록 이의":
        return ["이의신청서 만들기", "이의 안 함 · 사유 기록"]
    if s.startswith("채권신고"):
        return ["채권신고서 만들기", "신고 안 함 · 사유 기록"]
    if s.startswith("면책 심리"):
        return ["면책 이의신청서 만들기", "이의 안 함 · 사유 기록"]
    return ["다음 단계로"]


# ---------------------------------------------------------------- 회생·파산 사건의 관리 가부 (회수·집행 가능 / 정지 / 금지 / 불가)
# 진행내용(최근 줄부터)과 종국결과로 판단한다. 판단 근거 줄을 함께 보여주고, 확정 여부는 담당자가 확인한다.

REHAB_DVS = {"개회": "개인회생", "개확": "개인회생", "하단": "파산", "하합": "파산", "하면": "면책", "회단": "회생", "회합": "회생", "간회단": "회생", "간회합": "회생"}

MANAGE = {  # 코드: (크게 보일 말, 색, 한 줄 설명)
    "ok": ("회수·집행 가능", "green", "회생·파산 절차가 멈추게 하는 효력이 없어요. 회수·집행을 다시 검토할 수 있어요."),
    "warn": ("주의 · 신청만 접수", "orange", "아직 금지·중지명령이나 개시결정이 없어요. 집행은 가능하지만 곧 멈출 수 있어 진행을 지켜봐야 해요."),
    "stop": ("정지 · 금지·중지명령", "orange", "법원 명령으로 강제집행·가압류 등이 멈춘 상태예요. 새 집행·추심을 하지 마세요."),
    "ban": ("금지 · 절차 진행 중", "red", "절차가 열려 개별 회수·집행이 금지된 상태예요. 절차(변제계획·배당) 안에서만 받아요."),
    "end": ("회수 불가 · 면책", "black", "면책으로 책임이 사라졌어요. 추심·집행을 하면 안 되고 관리 종결 대상이에요."),
}

_EV = [  # (정규식, 코드, 무엇, 근거) — 한 줄에 여럿이 맞으면 위에 있는 것
    (r"면책\s*불허가", "ok", "면책 불허가", "확정되면 다시 회수 가능 (파산이면 파산 절차 종결 여부도 확인)"),
    (r"면책\s*(결정|허가)", "end", "면책결정", "채무자회생법 제566조(파산)·제625조(개인회생) — 면책의 효력"),
    (r"(인가\s*전\s*)?폐지\s*결정|절차\s*폐지", "ok", "폐지결정", "폐지 확정 뒤에는 금지 효력이 없어요 (확정 여부 확인)"),
    (r"(신청\s*)?기각\s*결정|신청\s*기각|각하\s*결정", "ok", "기각·각하", "기각·각하 확정 뒤에는 금지 효력이 없어요 (확정 여부 확인)"),
    (r"신청\s*취하|취하\s*(서|간주)?", "ok", "취하", "취하되면 금지 효력이 없어요"),
    (r"(변제|회생)\s*계획\s*인가|인가\s*결정", "ban", "계획 인가", "채무자회생법 제615조(개인회생)·제252조(회생) — 계획대로만 변제, 개별 집행 금지"),
    (r"파산\s*선고", "ban", "파산선고", "채무자회생법 제424조(파산채권은 파산절차로만)·제348조(선고 전 집행 실효)"),
    (r"개시\s*결정", "ban", "개시결정", "채무자회생법 제600조(개인회생)·제58조(회생) — 강제집행·가압류 중지·금지"),
    (r"면책\s*신청", "ban", "면책신청", "채무자회생법 제557조 — 파산선고 뒤 면책신청이 있으면 강제집행 금지·중지"),
    (r"(포괄적\s*)?금지\s*명령|중지\s*명령|보전\s*처분", "stop", "금지·중지명령", "채무자회생법 제593조(개인회생)·제43~45조(회생) — 집행 중지·금지"),
]


def rehab_kind(dvs):
    return REHAB_DVS.get(dvs or "", "")


def rehab_status(dvs, prog_texts, basic=None, doc=""):
    """prog_texts: 진행내용 글(최근 줄부터). basic: 일반내용(종국결과·확정일). doc: 조회 전이면 등록한 문서 이름.
    → {code, label, color, desc, event, basis, row, confirmed, source}"""
    basic = basic or {}
    rows = []
    ult = (basic.get("csUltmtDvsNm") or "").strip()
    if ult:  # 종국결과 칸은 짧게 오므로 진행내용 말투로 바꿔 맨 앞에
        for w, as_text in (("불허가", "면책불허가"), ("면책", "면책결정"), ("인가", "인가결정"), ("폐지", "폐지결정"),
                           ("기각", "기각결정"), ("각하", "각하결정"), ("취하", "신청취하"), ("파산", "파산선고")):
            if w in ult:
                rows.append((f"종국결과: {ult} ({as_text})", basic.get("csUltmtYmd") or ""))
                break
    rows += [(t, d) for t, d in prog_texts]
    confirmed = bool(basic.get("csCfmtnYmd"))
    for text, date in rows:
        t = re.sub(r"\s+", "", text)
        for pat, code, what, basis in _EV:
            if re.search(pat.replace(r"\s*", ""), t):
                if code == "end" and not (confirmed or "확정" in t):
                    code, label_note = "ban", "면책결정 (확정 전 — 확정되면 회수 불가)"
                else:
                    label_note = ""
                out = dict(code=code, event=what, basis=basis, row=text, date=date, confirmed=confirmed, source="진행내용")
                break
        else:
            continue
        break
    else:
        if doc:  # 아직 조회 전: 받은 문서로
            code = {"금지명령": "stop", "중지명령": "stop", "보전처분": "stop", "개시결정": "ban", "파산선고": "ban",
                    "채권자목록 송달": "ban", "면책 심리 통지": "ban", "공공정보 등재": "warn"}.get(doc, "warn")
            out = dict(code=code, event=doc, basis="받은 문서 기준 — 사건 조회로 확인해 주세요", row="", date="", confirmed=False, source="받은 문서")
            label_note = ""
        else:
            code = "ban" if rehab_kind(dvs) == "면책" else "warn"
            out = dict(code=code, event="신청" if code == "warn" else "면책 심리 중", row=rows[0][0] if rows else "", date=rows[0][1] if rows else "",
                       basis="채무자회생법 제557조 — 면책신청 중 강제집행 금지" if code == "ban" else "결정이 나오기 전이에요",
                       confirmed=False, source="진행내용" if rows else "조회 전")
            label_note = ""
    label, color, desc = MANAGE[out["code"]]
    kind = rehab_kind(dvs)
    out.update(label=label, color=color, desc=desc, note=label_note, kind=kind, basis=_basis_for(out["basis"], kind))
    return out


def _basis_for(text, kind):
    """「제593조(개인회생)·제43~45조(회생)」처럼 여러 절차가 섞인 근거에서 이 사건 절차 것만 남긴다."""
    if not kind or " — " not in text:
        return text
    head, tail = text.split(" — ", 1) if text.startswith("채무자회생법") else (text, "")
    tag = {"면책": "파산"}.get(kind, kind)
    parts = head.replace("채무자회생법 ", "").split("·")
    keep = [p for p in parts if "(" not in p or f"({tag})" in p or (tag == "파산" and "(파산" in p)]
    if not keep:
        return text
    return "채무자회생법 " + "·".join(re.sub(r"\((개인회생|회생|파산)\)", "", p) for p in keep) + (" — " + tail if tail else "")


BLOCKING = ("stop", "ban", "end")  # 우리 법조치를 멈춰야 하는 상태


def digits(s):
    return re.sub(r"\D", "", str(s or ""))
