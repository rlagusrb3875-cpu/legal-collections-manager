# -*- coding: utf-8 -*-
"""배당기일 관리 점검: python tests/test_dividend.py"""
import datetime as dt
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))

from core import dividend as DV  # noqa: E402
from core import dividend_out as DO  # noqa: E402

OK = 0
FAIL = []


def check(name, cond, info=""):
    global OK
    if cond:
        OK += 1
    else:
        FAIL.append(f"{name} {info}")


B = dt.date(2026, 11, 9)

# ---------------------------------------------------------------- 값 다듬기
check("법원 줄임", DV.norm_court("서울남부지법") == "서울남부지방법원")
check("법원 공백", DV.norm_court("서울 남부 지방법원") == "서울남부지방법원")
check("지원", DV.norm_court("부산지방법원동부지원") == "부산지방법원 동부지원")
check("사건번호 공백", DV.norm_no("2026 타배 99005") == "2026타배99005")
check("사건번호 전각", DV.norm_no("２０２６타배９９００５") == "2026타배99005")
check("날짜 점", DV.norm_date("2026.12.10") == "2026-12-10")
check("날짜 두 자리", DV.norm_date("26.12.03") == "2026-12-03")
check("날짜 한글", DV.norm_date("2026년 12월 3일") == "2026-12-03")
check("날짜 8자리", DV.norm_date("20261203") == "2026-12-03")
check("금액 쉼표", DV.won("2,050,000") == 2050000)
check("금액 만", DV.won("205만") == 2050000)

# ---------------------------------------------------------------- 붙여넣기 읽기 (사용자 예시: 공백으로 나뉜 줄)
t = DV.read_text("사건번호   법원  채무자      배당기일   배당요구종기     메모\n2026타배99004   부산지방법원     가O나       2026.12.10    공탁\n"
                 "2026타배99005  서울남부지방법원 다O라 26.12.03 동명이인?", DV.CASE_WANT)
check("머리글 알아봄", t["has_head"] and t["map"][:3] == ["no", "court", "debtor"], t["map"])
check("두 줄", len(t["rows"]) == 2 and t["rows"][1]["court"] == "서울남부지방법원")
t2 = DV.read_text("가O나\t부산지방법원\t2026타배99004", DV.CASE_WANT)
check("머리글 없이 값 모양", not t2["has_head"] and t2["rows"][0]["no"] == "2026타배99004" and t2["rows"][0]["debtor"] == "가O나")
t3 = DV.read_text("채무자키\t법조치키\t채무자명\t담당자명\t법원\t사건번호\t제3채무자\t조치종류\nD-1\tL-1\t가O나\t이담당\t부산지법\t2025타채99001\t(주)예시상사\t압류",
                  DV.LAW_WANT)
check("법조치 칸 (제3채무자는 안 읽음)", t3["rows"][0]["dkey"] == "D-1" and "third" not in t3["rows"][0] and t3["rows"][0]["debtor"] == "가O나", t3["rows"][0])

# ---------------------------------------------------------------- 사건검색 결과 읽기 (칸 이름이 달라도)
res = {"checks": [1], "lists": {
    "dlt_rcntDxdyLst": [{"dxdyYmd": "20261117", "dxdyKndNm": "배당기일", "dxdyHm": "1000"}, {"dxdyYmd": "20261001", "dxdyKndNm": "심문기일"}],
    "dlt_reltCsLst": [{"reltCsCortNm": "부산지방법원", "reltCsNo": "2025타채99001", "reltCsDvsNm": "채권압류및추심명령"},
                      {"a": "서울중앙지방법원", "b": "2025 타채 2031", "c": "채권압류및추심명령"}],
    "dlt_btprtCttLst": [{"btprtDvsNm": "공탁자(제3채무자)", "btprtNm": "(주)예시상사"}, {"btprtDvsNm": "채무자", "btprtNm": "가O나"}]},
    "prog": []}
ex = DV.extract(res, "부산지방법원")
check("배당기일", ex["date"] == "2026-11-17" or ex["date"] >= "2026-11-17", ex)
check("관련사건 2", len(ex["rel"]) == 2 and ex["rel"][1][0] == "서울중앙지방법원" and ex["rel"][1][1] == "2025타채2031", ex["rel"])
check("공탁자", ex["third"] == "(주)예시상사", ex["third"])
ex2 = DV.extract({"checks": [1], "lists": {}, "prog": [{"progYmd": "20261020", "progCtt": "배당기일(2026.12.03 14:00) 지정", "progRslt": ""}]})
check("진행내용에서 배당기일", ex2["date"] == "2026-12-03", ex2)

# ---------------------------------------------------------------- 매칭 (법원+사건번호, 관련사건 전부, 채무자키 여러 개)
law = [
    {"dkey": "D-100231", "lkey": "L-1", "debtor": "가O나", "mgr": "이담당", "court": "부산지방법원", "no": "2025타채99001", "third": "(주)예시상사"},
    {"dkey": "D-100232", "lkey": "L-2", "debtor": "가O나", "mgr": "이담당", "court": "부산지방법원", "no": "2025타채99001", "third": ""},
    {"dkey": "D-9", "lkey": "L-9", "debtor": "마O바", "mgr": "박지훈", "court": "대구지방법원", "no": "2025타채9002", "third": ""},
    {"dkey": "D-7", "lkey": "L-7", "debtor": "가O나", "mgr": "박담당", "court": "인천지방법원", "no": "2024타채1", "third": ""},
]
searched = [
    {"debtor": "가O나", "court": "부산지방법원", "no": "2026타배99004", "ok": True, "date": "2026-11-17", "rel": ex["rel"], "third": "(주)예시상사"},
    {"debtor": "마O바", "court": "대구지방법원", "no": "2026타배99009", "ok": True, "date": "", "rel": [["대구지방법원", "2025타채9001", ""]], "third": ""},
    {"debtor": "버O서", "court": "대전지방법원", "no": "2026타배999", "ok": False, "date": "", "rel": [], "third": ""},
]
M = DV.match(searched, law)
check("키 여러 개", M[0]["status"] == "multi" and M[0]["dkeys"] == ["D-100231", "D-100232"], M[0]["status"])
check("이름만 같은 키는 참고", M[0]["name_note"] == ["D-7"], M[0]["name_note"])
check("못 찾음", M[1]["status"] == "none")
check("실패", M[2]["status"] == "fail")
rows = DV.out_rows(M)
check("법조치키당 한 줄", len(rows) == 3 and rows[0]["lkey"] == "L-1" and rows[2]["dkey"] == "", [r["lkey"] for r in rows])
check("제3채무자 = 공탁자", rows[0]["third"] == "(주)예시상사" and rows[0]["third_src"] == "공탁자(사건검색)")
check("법조치에 없으면 공탁자", rows[1]["third"] == "(주)예시상사" and rows[1]["third_src"] == "공탁자(사건검색)")
check("당사 관련사건", rows[0]["ours"] == "부산지방법원 2025타채99001", rows[0]["ours"])

# 관련사건 번호로 키 붙이기: 법조치 자료에 배당사건 번호가 없고, 법원이 비었거나 달라도 사건번호가 같으면 붙인다
law2 = [{"dkey": "D-A", "lkey": "L-A", "debtor": "다O라", "court": "", "no": "2024타채99002"},
        {"dkey": "D-B", "lkey": "L-B", "debtor": "다O라", "court": "서울동부지방법원", "no": "2025타채2031"},
        {"dkey": "D-C", "lkey": "L-C", "debtor": "박O", "court": "대전지방법원", "no": "2025타채2031"}]
s2 = [{"debtor": "다O라", "court": "서울남부지방법원", "no": "2026타배99005", "ok": True, "date": "", "third": "",
       "rel": [["서울남부지방법원", "2024타채99002", ""], ["서울중앙지방법원", "2025타채2031", ""]]}]
m2 = DV.match(s2, law2)[0]
check("법원 비어도 사건번호로", any(h["lkey"] == "L-A" for h in m2["hits"]), [h["lkey"] for h in m2["hits"]])
check("같은 번호 여러 법원이면 같은 채무자만", [h["lkey"] for h in m2["hits"]] == ["L-A", "L-B"], [h["lkey"] for h in m2["hits"]])
r2 = DV.out_rows([m2])
check("법원 다르면 「법원 확인」", [x["court_check"] for x in r2] == [False, True], [x["court_check"] for x in r2])
check("당사 관련사건 = 법조치 자료 쪽 사건", r2[1]["ours"] == "서울동부지방법원 2025타채2031", r2[1]["ours"])
M2 = DV.match(searched, law, linkmem={"대구지방법원|2026타배99009": "L-9"}, notours={"대전지방법원|2026타배999"})
check("직접 연결 기억", M2[1]["status"] == "ok" and M2[1]["remembered"])
check("우리 사건 아님 기억", M2[2]["status"] == "notours")

# 실제 사이트 대비: 사건번호 모양 · 관련사건이 칸마다 나뉜 경우 · 진행내용에만 있는 경우 · 배당사건번호 칸
check("하이픈", DV.norm_no("2025-타채-99001") == "2025타채99001")
check("두 자리 연도", DV.norm_no("25타채99001") == "2025타채99001")
res3 = {"checks": [1], "lists": {"dlt_reltCsLst": [{"cortNm": "서울중앙지방법원", "csYr": "2025", "csDvsNm": "타채", "csSerial": "2031"}]},
        "prog": [{"progYmd": "20261001", "progCtt": "2025-타채-99001 채권자 배당요구신청", "progRslt": ""}, {"progYmd": "20261002", "progCtt": "2026타배99005 배당기일 지정"}]}
ex3 = DV.extract(res3, "서울남부지방법원", "다O라", "2026타배99005")
check("나뉜 칸 · 진행내용에서 관련사건", [x[1] for x in ex3["rel"]] == ["2025타채2031", "2025타채99001"], ex3["rel"])
t4 = DV.read_text("배당사건번호\t채무자키\t법조치키\t채무자명\t법원\t법조치 사건번호\n2026타배99005\tD-1\tL-1\t김\t서울\t2025타채1", DV.LAW_WANT)
check("배당사건번호 칸은 따로", t4["map"][0] == "dno" and t4["map"][5] == "no", t4["map"])
m4 = DV.match([{"debtor": "김", "court": "서울남부지방법원", "no": "2026타배99005", "ok": True, "date": "", "third": "", "rel": []}],
              [{"dkey": "D-1", "lkey": "L-1", "debtor": "김", "court": "", "no": "2025타채1", "dno": "2026타배99005"}])[0]
check("배당사건번호로도 붙음", [h["lkey"] for h in m4["hits"]] == ["L-1"])

# 법조치 자료 칸 읽기: 머리글이 없거나 이름이 달라도 채무자키 · 법조치키를 놓치지 않기
t5 = DV.read_text("서울중앙지방법원\t2025타채2031\t다O라\t123456789\tLA-2025-0042\t이담당\n부산지방법원\t2025타채1\t가O나\t223456789\tLA-2025-0043\t김담당", DV.LAW_WANT)
check("머리글 없이: 키 칸 짐작", t5["map"] == ["court", "no", "debtor", "dkey", "lkey", "mgr"] and t5["guessed"] and len(t5["rows"]) == 2, t5["map"])
t6 = DV.read_text("관할\t사건\t성명\t고객ID\t조치ID\t담당\n서울중앙지방법원\t2025타채2031\t다O라\t123456789\tLA-1\t이담당", DV.LAW_WANT)
check("머리글 이름이 달라도 키", t6["rows"][0].get("dkey") == "123456789" and t6["rows"][0].get("lkey") == "LA-1", t6["map"])
t7 = DV.read_rows(DV.split_lines("가\t나\t다\t라\n서울중앙지방법원\t2025타채1\tK1\tL1"), DV.LAW_WANT, ["court", "no", "dkey", "lkey"], True)
check("칸 직접 고르기 (모르는 머리글)", t7["rows"] == [{"court": "서울중앙지방법원", "no": "2025타채1", "dkey": "K1", "lkey": "L1"}], t7["rows"])
m7 = DV.match([{"debtor": "김", "court": "서울남부지방법원", "no": "2026타배99005", "ok": True, "date": "", "third": "", "rel": [["서울중앙지방법원", "2025타채1", ""]]}],
              t7["rows"])
check("고른 칸으로 매칭 → 키 붙음", [(h["dkey"], h["lkey"]) for h in m7[0]["hits"]] == [("K1", "L1")])

# ---------------------------------------------------------------- 대장: 새 줄 · 다시 매칭 · 다른 값
tmp = tempfile.mkdtemp()
st = DV.DividendStore(tmp)
n = st.to_ledger(rows)
check("대장 새 줄", n["add"] == 3 and len(st.ledger) == 3)
rows2 = [dict(r) for r in rows]
rows2[0]["date"] = "2026-11-20"
rows2[0]["mgr"] = "박지훈"
n2 = st.to_ledger(rows2)
check("다시 매칭: 새 줄 없음", n2["add"] == 0 and n2["upd"] == 1 and len(st.ledger) == 3, n2)
check("기일 바뀜 기록", st.ledger[0]["date"] == "2026-11-20" and st.ledger[0]["changed"] and "배당기일" in st.ledger[0]["log"][0][2])
check("다른 값은 고르게", any(d["f"] == "mgr" and d["to"] == "박지훈" for d in st.data["diffs"]) and st.ledger[0]["mgr"] == "이담당")
st.save()
st2 = DV.DividendStore(tmp)
check("저장 · 다시 읽기", len(st2.ledger) == 3 and st2.data["dash"]["lateD"] == 31)
# 예전에 키 없이 저장된 줄은 다시 매칭하면 그 줄에 키가 채워진다 (새 줄을 만들지 않음)
st3 = DV.DividendStore(tempfile.mkdtemp())
st3.to_ledger([{"court": "대구지방법원", "no": "2026타배99009", "debtor": "마O바", "dkey": "", "lkey": "", "date": "", "rel_nos": ""}])
n3 = st3.to_ledger([{"court": "대구지방법원", "no": "2026타배99009", "debtor": "마O바", "dkey": "D-9", "lkey": "L-9", "via": "대구지방법원 2025타채9002",
                     "ours": "대구지방법원 2025타채9002", "date": "", "rel_nos": ""}])
check("키 없던 줄에 키 채움", len(st3.ledger) == 1 and st3.ledger[0]["dkey"] == "D-9" and st3.ledger[0]["lkey"] == "L-9" and n3["add"] == 0, st3.ledger)

# ---------------------------------------------------------------- 단계 · 오늘 할 일
r = {"check": "완료", "recv": "대기", "date": "2026-11-01"}
check("발송 필요", DV.stage(r, B)[0] == "발송 필요")
check("배당 없음", DV.stage({"check": "완료", "recv": "수령", "amt": 0}, B)[0] == "끝 · 배당 없음")
L = [
    {"id": "1", "no": "1", "court": "a", "mgr": "이담당", "check": "완료", "recv": "대기", "date": "2026-11-12"},
    {"id": "2", "no": "2", "court": "a", "mgr": "이담당", "check": "완료", "recv": "대기", "date": "2026-10-01"},
    {"id": "3", "no": "3", "court": "a", "mgr": "이담당", "check": "완료", "recv": "발송", "date": "2026-09-01", "send_at": "2026-09-20"},
    {"id": "4", "no": "4", "court": "a", "mgr": "박지훈", "check": "대기", "recv": "대기", "date": ""},
]
G = {g["k"]: g["ids"] for g in DV.today_groups(L, "이담당", True, 10, [], B)}
check("오늘 할 일: 7일 안", G["soon"] == ["1"], G)
check("오늘 할 일: 발송 전", G["send"] == ["2"])
check("오늘 할 일: 입금 없음", G["pay"] == ["3"])
check("내 것만", G["check"] == [])
G2 = {g["k"]: g["ids"] for g in DV.today_groups(L, "이담당", False, 10, [], B)}
check("전체", G2["check"] == ["4"])

# ---------------------------------------------------------------- 다시 조회할 건 고르기
P = DV.pick_candidates([
    {"court": "서울중앙지방법원", "no": "2026타배720", "date": "", "recv": "대기"},
    {"court": "수원지방법원", "no": "2026타배655", "date": "2026-11-13", "recv": "대기"},
    {"court": "인천지방법원", "no": "2026타배812", "date": "2027-01-20", "recv": "대기"},
    {"court": "인천지방법원", "no": "2026타배1", "date": "2026-05-01", "recv": "수령"},
    {"court": "인천지방법원", "no": "2026타배2", "date": "2026-10-01", "recv": "발송"},
], [], [{"court": "대전지방법원", "no": "2026타배999"}], set(), B)
whys = sorted(x["why"] for x in P["in"])
check("고르기", whys == ["30일 안 기일", "기일 미정", "지난 조회 실패"], whys)
check("뺀 것", sorted(x["why"] for x in P["out"]) == ["기일 지남 (대장에서 처리)", "기일 확정 · 30일 넘게 남음", "수령완료"])

# ---------------------------------------------------------------- 붙여넣어 고치기
for x, a in zip(st.ledger, ("2200000", "", "")):
    x["amt"] = int(a) if a else ""
pp = DV.paste_parse(f"배당사건번호\t법조치키\t배당액\n2026타배99004\tL-1\t2,050,000\n2026타배99004\tL-2\t1,000,000\n2026타배999\tL-x\t3", st.ledger)
check("붙여넣기 바뀜", len(pp["ch"]) == 2 and pp["ch"][0]["to"] == 2050000, pp)
check("붙여넣기 못 찾음", len(pp["miss"]) == 1)
check("붙여넣기 오류", "err" in DV.paste_parse("배당액\n1", st.ledger))

# ---------------------------------------------------------------- 통계: 근거 목록 합계 = 대시보드 값
import random  # noqa: E402
rnd = random.Random(3)
LL = []
for i in range(120):
    d = B - dt.timedelta(days=rnd.randint(-60, 400))
    amt = rnd.randint(0, 50) * 100000
    recv = "수령" if d < B - dt.timedelta(days=20) and rnd.random() < .85 else rnd.choice(["대기", "발송"])
    send = (d + dt.timedelta(days=rnd.randint(2, 10))).isoformat() if recv != "대기" else ""
    LL.append({"id": str(i), "no": f"2026타배{i}", "court": rnd.choice(["서울중앙지방법원", "수원지방법원"]), "mgr": rnd.choice(["갑", "을"]),
               "third": rnd.choice(["국민은행", "신한은행", "(주)가"]), "date": d.isoformat(), "amt": amt, "claim": amt * 2 or 1000000,
               "check": "완료", "recv": recv, "send_at": send,
               "recv_at": (dt.date.fromisoformat(send) + dt.timedelta(days=rnd.randint(3, 20))).isoformat() if recv == "수령" else ""})
F = {"period": "12m", "basis": "date", "third": "", "mgr": "", "court": ""}
dash = dict(DV.DASH_DEFAULT)
D = DV.dashboard(LL, F, dash, 10, B)
check("월 12개", len(D["months"]) == 12 and D["months"][-1] == "2026-11")
keys = ["kpi|amt", "kpi|got", "kpi|yield", "kpi|unpaid", "kpi|none", "kpi|d2r", "kpi|n", "fc|0", "fc|1", "ag|0", "ag|1", "ag|4", "old|0",
        f"month|{D['months'][3]}", "dim|third|국민은행", "dim|mgr|갑", "dim|court|수원지방법원"]
bad = [k for k in keys if not DV.drill(LL, F, dash, k, 10, B)["ok"]]
check("근거 목록 합계 = 대시보드", not bad, bad)
mon = sum(g["amt"] for g in D["monthly"])
check("월별 합 = 배당액", mon == D["total"]["amt"])
F2 = dict(F, basis="recv")
D2 = DV.dashboard(LL, F2, dash, 10, B)
check("수령일 기준 = 받은 돈만", D2["total"]["amt"] == D2["total"]["got"])

# ---------------------------------------------------------------- 내보내기 · 보고서
p = os.path.join(tmp, "a.xlsx")
DO.ledger_xlsx(p, LL[:10], LL)
import openpyxl  # noqa: E402
wb = openpyxl.load_workbook(p)
check("엑셀 시트", wb.sheetnames == ["대장", "진행 중", "월별 수령", "변경 기록"], wb.sheetnames)
check("엑셀 칸 나눔", [c.value for c in wb["대장"][1]][4:6] == ["배당법원", "배당사건번호"])
DO.stats_xlsx(os.path.join(tmp, "s.xlsx"), LL, F, dash, 10)
html = DO.report_html(LL, F, dash, 10, "OO캐피탈", "이담당", "최근 12개월")
check("보고서", "한눈에 보기" in html and "<svg" in html and "채무자명" not in html.split("<footer>")[0].split("</header>")[1][:200])
DO.match_xlsx(os.path.join(tmp, "m.xlsx"), rows)

print(f"통과 {OK}개" + (f" · 실패 {len(FAIL)}개" if FAIL else ""))
for f in FAIL:
    print("  ✕", f)
sys.exit(1 if FAIL else 0)
