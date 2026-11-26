# -*- coding: utf-8 -*-
"""법조치 기능 점검 (법원 사이트에 접속하지 않음).

    python tests/test_legal.py
"""
import datetime as dt
import os
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

from bridge import Bridge  # noqa: E402
from core import legal as L  # noqa: E402
from core import legal_docs as LD  # noqa: E402

ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print("  [정상]", name)
    else:
        fail += 1
        print("  [문제]", name, extra)


def main():
    std = L.default_standards()
    print("기준표 · 비용")
    check("송달료 2026. 7. 1.부터 5,640원", L.value(std, "svc", "2026-11-01") == 5640 and L.value(std, "svc", "2026-01-10") == 5500)
    f = L.pay_order_fee(std, 8350000, 2, True, "2026-11-01")
    check("지급명령 인지 = 소장 인지 1/10 × 9/10, 100원 미만 버림", f["stamp"] == 3700, f)
    check("지급명령 송달료 = 2명 × 6회 × 5,640", f["svc"] == 67680, f)
    check("종이로 내면 감액 없음", L.pay_order_fee(std, 8350000, 2, False, "2026-11-01")["stamp"] == 4100)
    check("인지 1천원 미만은 1천원", L.pay_order_fee(std, 100000, 2, True)["stamp"] == 1000)
    g = L.garnish_fee(std, 3, True, "2026-11-01")
    check("채권압류·추심 인지 2,000 × 2, 송달료 (2+3)명 × 2회", g["stamp"] == 4000 and g["svc"] == 5 * 2 * 5640, g)

    print("압류금지")
    w = L.wage_exempt(std, 2900000, "2026-11-01")
    check("2026. 2. 1.부터 급여 최저 250만", w["ex"] == 2500000 and w["can"] == 400000, w)
    check("그 전에는 185만", L.wage_exempt(std, 2900000, "2025-12-01")["ex"] == 1850000)
    w = L.wage_exempt(std, 7000000, "2026-11-01")
    check("급여 600만 넘으면 300만 + (1/2 − 300만)/2", w["ex"] == 3250000 and w["can"] == 3750000, w)
    check("급여 550만은 1/2", L.wage_exempt(std, 5500000, "2026-11-01")["ex"] == 2750000)
    a = L.assets_calc(std, [{"kind": "예금", "amt": 2400000}, {"kind": "예금", "amt": 1200000}, {"kind": "보험", "amt": 1400000},
                            {"kind": "급여", "amt": 2900000}], 9012000, "2026-11-01")
    check("예금은 여러 곳 합산해서 250만을 뺌", round(a["now"]) == 1100000, a["now"])
    check("보장성 보험 140만은 실익 없음", next(r for r in a["rows"] if r["kind"] == "보험")["verdict"] == "실익 없음")
    check("제3채무자 = 급여 1 + 예금 2", len(a["third"]) == 3)

    print("기한")
    d = L.due_of(std, "2026-10-24", 7)
    check("끝날이 토요일이면 다음 월요일", d["due"] == "2026-11-02" and d["moved"], d)
    check("대체공휴일도 건너뜀", L.due_of(std, "2026-09-21", 7)["due"] == "2026-09-29")
    check("평일이면 그대로", L.due_of(std, "2026-10-27", 7)["due"] == "2026-11-03")

    print("배당")
    st = L.small_tenant(std, "2019-04-15", 0)
    check("근저당 2019. 4.이면 서울 최우선 3,700만", st["amt"] == 37e6 and st["limit"] == 110e6, st)
    v = {"apprl": 320e6, "rate": 78, "cost": 3.2e6, "zone": 0, "mort": "2019-04-15", "mort_amt": 150e6, "depo": 60e6,
         "fix": "2022-02-10", "tax": 1.8e6, "ours": 42e6, "others": 28e6}
    r = L.distribution(std, v)
    check("78%면 우리 몫 2,076만", round(r["ours"]) == 20760000, r["ours"])
    check("1/2 한도", L.distribution(std, dict(v, apprl=60e6, mort="2023-03-01"))["lines"][1]["sub"].endswith("(1/2 한도)"))
    check("확정일자가 근저당보다 빠르면 앞 순위", L.distribution(std, dict(v, fix="2018-01-01"))["lines"][3]["rank"] == 4)

    print("송달 사유 · 조치")
    check("폐문부재 찾기", L.dlv_reason("채무자 김가나 지급명령정본 송달불능(폐문부재)") == "폐문부재")
    check("지급명령 폐문부재 3회 → 소제기 신청", L.recommend("지급명령", "폐문부재", 3) == "소제기 신청 (소송으로)")
    check("지급명령은 공시송달 불가", not L.action_allowed("지급명령", "공시송달 신청")[0])
    check("사건 종류", L.case_kind("차전") == "지급명령" and L.case_kind("타채") == "채권압류" and L.case_kind("가소") == "소송")

    print("원장 · 연결 · 서류")
    tmp = tempfile.mkdtemp(prefix="legal_test_")
    b = Bridge(os.path.join(tmp, "data"))
    b.store.set_setting("save.export_dir", os.path.join(tmp, "out"))
    b.reveal = lambda p: True
    b.store.set_setting("legal.creditor", {"name": "가나자산관리대부 주식회사", "addr": "서울 ○○구", "rep": "○○○", "phone": ""})
    b.lg_info_save({"cause": "양수금", "assignor": "가나캐피탈 주식회사", "assign_date": "2024-08-01", "notice_date": "2024-08-09"})

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["고객명", "주민등록번호", "대출번호", "대출잔액", "미수이자", "주민등록주소", "소멸시효완성일", "기한이익상실일", "연체이율"])
    ws.append(["장나래", "920101-0000000", "110-555-0001", "9,300,000", 760000, "서울 ○○구 ○○로 1", "2027-09-24", "2025-01-15", "15"])
    ws.append(["임다솜", "860202-0000000", "110-555-0002", 6700000, 410000, "서울 ○○구 ○○로 2", dt.date.today() + dt.timedelta(days=40), "2025-02-15", "15"])
    ws.append(["서마루", "750303-0000000", "110-555-0003", 3800000, 220000, "", "2027-11-09", "2025-03-15", "15"])
    xl = os.path.join(tmp, "원장.xlsx")
    wb.save(xl)
    p = b.lg_import_preview(xl)
    check("원장 엑셀 칸 자동 찾기 (고객명·대출번호·대출잔액·주민등록주소)",
          all(k in p["auto"] for k in ("name", "key", "principal", "addr", "sihyo", "birth")), p["auto"])
    check("새로 3명", p["new"] == 3)
    b.lg_import_apply(xl)
    ds = b.lg_debtors()["items"]
    jang = next(x for x in ds if x["name"] == "장나래")
    check("주민번호는 앞 6자리만 저장", jang["birth"] == "920101")
    check("금액 읽기 (쉼표)", jang["principal"] == 9300000)
    check("같은 파일을 다시 넣으면 고침", b.lg_import_preview(xl)["update"] == 3)

    rows = b.lg_doc_rows("지급명령", {"ecfs": True, "basis": "약정"})["rows"]
    st = {r["name"]: r["st"][0] for r in rows}
    check("지급명령 대상: 주소 없음은 제외, 시효 임박은 먼저", st.get("서마루") == "no" and st.get("임다솜") == "warn" and st.get("장나래") == "ok", st)
    todos = b._todos()
    check("시효 임박이 확인할 것에", any(t["kind"] == "시효 임박" and t["party"] == "임다솜" for t in todos))

    rid = b.lg_rehab_register({"did": jang["id"], "doc": "금지명령", "kind": "개인회생", "no": "2026개회 55123", "court": "서울회생법원"})
    check("회생 등록 → 원장 단계 「회생·파산」", b.lg_debtor(jang["id"])["stage_view"] == "회생·파산")
    st = {r["name"]: r["st"][0] for r in b.lg_doc_rows("지급명령", {})["rows"]}
    check("회생 등록하면 서류 대상에서 제외", st.get("장나래") == "no", st)

    prev = b.lg_doc_preview("지급명령", next(x["id"] for x in ds if x["name"] == "임다솜"), {"basis": "약정"})
    check("미리보기 문단 + 붙여넣기 글", prev["paras"][0] == ("title", "지급명령신청서") and "[신청취지]" in prev["paste"], prev["paste"][:80])
    check("약정이율 시작일 = 기한이익 상실일 다음 날", "2025. 2. 16.부터" in prev["paste"])
    res = b.lg_doc_make("지급명령", [r["id"] for r in rows], {"ecfs": True, "basis": "약정"})
    check("가능한 사람만 만듦 (1건)", res["count"] == 1, res)
    files = [f for f in os.listdir(res["folder"]) if f.endswith(".docx")]
    with zipfile.ZipFile(os.path.join(res["folder"], files[0])) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    check("워드 파일 안에 채무자·금액", "임다솜" in xml and "7,110,000" in xml)
    check("목록 엑셀", os.path.isfile(res["list"]))
    check("만들면 단계 「독촉」", b.lg_debtor(next(x["id"] for x in ds if x["name"] == "임다솜"))["stage_view"] == "독촉")

    print("송달·주소보정")
    c = b.store.add_case({"court": "서울중앙지방법원", "court_code": "000210", "year": 2026, "dvs": "차전", "serial": 2468,
                          "party": "서마루", "memo1": "110-555-0003"})
    today = dt.date.today().strftime("%Y%m%d")
    b.store.save_result(c["id"], {"basic": {}, "lists": {}, "checks": [{"at": "2026-10-20 10:00:00"}],
                                  "prog": [{"progYmd": today, "progCtt": "채무자 서마루에게 지급명령정본 송달불능(폐문부재)"},
                                           {"progYmd": today, "progCtt": "지급명령정본 송달불능(폐문부재)"}]})
    c["last_checked"] = "2026-10-20 10:00:00"
    b.store.save_cases()
    dl = b.lg_dlv()
    check("조회 결과의 「폐문부재」가 처리함에", dl["todo"] == 1 and dl["items"][0]["reason"] == "폐문부재", dl["todo"])
    x = dl["items"][0]
    check("원장과 연결 (계좌번호)", x["debtor"] and x["debtor"]["name"] == "서마루")
    v = b.lg_dlv_set(x["key"], "recv", "2026-10-24")
    check("받은 날 넣으면 기한 계산 (주말이면 다음 평일)", v["due"]["due"] == "2026-11-02")
    check("확인할 것에도 기한", b.store.todos[x["key"]]["deadline"] == "2026-11-02")
    try:
        b.lg_dlv_set(x["key"], "act", "공시송달 신청")
        check("지급명령에 공시송달 고르면 막음", False)
    except ValueError:
        check("지급명령에 공시송달 고르면 막음", True)
    b.lg_dlv_set(x["key"], "act", "새 주소로 보정")
    r = b.lg_doc_make("주소보정", [x["key"]], {})
    check("주소보정서 만들면 처리함에서 끝남", r["count"] == 1 and b.lg_dlv()["todo"] == 0)
    check("확인할 것도 처리됨", b.store.todos[x["key"]].get("done"))

    print("보정 관리 대장 (엑셀 · 직접 · 내보내기 · 기일·기한)")
    import openpyxl
    xl = os.path.join(tmp, "보정.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["보정 관리 (공유용)"])
    ws.append(["사건번호", "관할법원", "채무자명", "불능사유", "보정명령일", "보정기간", "조치", "담당자", "비고", "진행상태"])
    ws.append(["2026 가소 777", "수원지방법원", "가상일", "폐문부재 (야간)", "2026-10-23", 7, "야간·휴일 특별송달", "김담당", "집행관 접수", ""])
    ws.append(["2026차전888", "부산지방법원", "가상이", "이사불명", "2026-10-26", 10, "", "이담당", "", "완료"])
    ws.append(["", "", "빈줄", "", "", "", "", "", "", ""])
    wb.save(xl)
    pv = b.lg_dlv_import_preview(xl)
    check("엑셀 머리글을 찾아 칸 자동 짝짓기 (제목 줄 건너뜀)", {"case_no", "court", "party", "reason", "recv", "days", "act", "owner", "memo", "status"} <= set(pv["auto"]), pv["auto"])
    check("사건번호 없는 줄은 뺌 · 새로 2건", pv["rows"] == 2 and pv["new"] == 2)
    r = b.lg_dlv_import_apply(xl, pv["mapping"])
    allx = {y["case_no"]: y for y in b.lg_dlv("all")["items"]}
    g = allx.get("2026가소777")
    check("엑셀로 넣기 (사건번호 띄어쓰기 정리 · 사유 정리)", r["new"] == 2 and g and g["reason"] == "폐문부재" and g["src"] == "xl", g and g["reason"])
    check("보정명령일 + 기간 → 기한 (10.23 + 7 = 10.30 금)", g["due"]["due"] == "2026-10-30")
    check("「진행」이 완료면 끝난 것으로", allx["2026차전888"]["done"])
    ws.cell(row=3, column=9, value="집행관 접수함 (갱신)")
    ws.cell(row=3, column=8, value="")
    wb.save(xl)
    r = b.lg_dlv_import_apply(xl, pv["mapping"])
    g2 = next(y for y in b.lg_dlv("all")["items"] if y["case_no"] == "2026가소777")
    check("같은 사건을 다시 넣으면 새로 만들지 않고 갱신 (빈 칸만 채움)", r == {"new": 0, "update": 2} and g2["memo"] == "집행관 접수" and g2["owner"] == "김담당", r)
    b.lg_dlv_import_apply(xl, pv["mapping"], overwrite=True)
    g2 = next(y for y in b.lg_dlv("all")["items"] if y["case_no"] == "2026가소777")
    check("덮어쓰기를 켜면 엑셀 값으로 바꿈", g2["memo"] == "집행관 접수함 (갱신)")
    k = b.lg_dlv_add({"case_no": "2026가단55", "party": "직접이", "reason": "주소불명", "due_set": "2026-12-01", "owner": "박담당"})
    m = next(y for y in b.lg_dlv("all")["items"] if y["key"] == k)
    check("직접 등록 · 기한 직접 넣기", m["src"] == "manual" and m["due"]["due"] == "2026-12-01" and m["due"].get("set"))
    try:
        b.lg_dlv_add({"case_no": " "})
        check("사건번호 없으면 등록 안 됨", False)
    except ValueError:
        check("사건번호 없으면 등록 안 됨", True)
    b.lg_dlv_set(k, "submit", "2026-11-20")
    check("진행: 제출한 날을 넣으면 「제출함」", b._dlv_status(b.legal.data["dlv"][k]) == "제출함")
    cal = b.calendar(2026, 12)
    check("기일·기한에 보정 기한 (D-day · 완료/지우기용 키)", any(e.get("dlv") and e["key"] == k and e["left"] is not None for e in cal))
    check("확인할 것에도 「보정 기한」", any(i["key"] == k and i["kind"] == "보정 기한" for i in b.home()["items"]))
    ex = b.lg_dlv_export(["case_no", "party", "due", "left", "status", "memo"], tab="all")
    rows = list(openpyxl.load_workbook(ex["path"]).active.iter_rows(values_only=True))
    check("고른 칸만 엑셀로 내보내기 (칸 순서 그대로)", rows[0][:6] == ("사건번호", "당사자", "기한", "남은 날", "진행", "메모") and ex["count"] == len(rows) - 1, rows[0])
    check("내보낸 칸을 기억", b.lg_dlv()["cols_on"] == ["case_no", "party", "due", "left", "status", "memo"])
    b.lg_dlv_done([k])
    check("완료하면 기일·기한에서 빠짐", not any(e.get("key") == k for e in b.calendar(2026, 12)))
    auto = next(y for y in b.lg_dlv("all")["items"] if y["src"] == "auto")
    b.lg_dlv_delete([auto["key"], k])
    check("지우면 대장에서 빠지고, 조회에서 온 건은 다시 들어오지 않음", not any(y["key"] in (auto["key"], k) for y in b.lg_dlv("all")["items"]))

    print("회생·파산 · 집행 · 기준표")
    rv = b.lg_rehab()["items"][0]
    check("회생 단계 · 관리 가부 (받은 문서 기준)", rv["stage_name"] == "금지·중지명령" and rv["m"]["code"] == "stop" and rv["m"]["source"] == "받은 문서")
    b.lg_rehab_set(rid, "due", (dt.date.today() + dt.timedelta(days=5)).isoformat())
    check("회생 기한이 확인할 것에", any(t["kind"] == "회생·파산 기한" for t in b._todos()))
    did = next(x["id"] for x in ds if x["name"] == "임다솜")
    b.lg_asset_save(did, {"kind": "급여", "name": "(주)마바물산", "third": "(주)마바물산", "amt": "2,900,000", "src": "재산명시 목록", "at": "2026-10-05"})
    b.lg_asset_save(did, {"kind": "예금", "name": "가나은행", "third": "주식회사 가나은행", "amt": 3600000})
    a = b.lg_assets(did)
    check("집행 대상 계산", a["calc"]["monthly"] == 400000 and len(a["calc"]["third"]) == 2, a["calc"]["monthly"])
    b.lg_std_set("svc", [{"from": "2025-06-01", "v": 5500}, {"from": "2026-07-01", "v": 5800}])
    check("기준표 바꾸면 계산에 반영", b.lg_doc_rows("지급명령", {})["std"]["svc"] == 5800)
    b.lg_std_undo()
    check("되돌리기", b.lg_doc_rows("지급명령", {})["std"]["svc"] == 5640)
    h = b.lg_home()
    check("법조치 현황 숫자", h["kpi"]["stop"] == 1 and h["kpi"]["debtors"] == 3, h["kpi"])
    i = b.info()
    check("메뉴 숫자", i["legal"]["stop"] >= 0 and i["legal"]["debtors"] == 3)

    print("회생·파산 관리 가부")
    M = lambda dvs, rows, basic=None: L.rehab_status(dvs, [(t, "2026-10-01") for t in rows], basic or {})["code"]  # noqa: E731
    check("신청만 → 주의", M("개회", ["개인회생 신청서 접수"]) == "warn")
    check("금지·중지명령 → 정지", M("개회", ["금지명령", "개인회생 신청서 접수"]) == "stop")
    check("개시결정·인가·파산선고 → 금지", M("개회", ["개시결정"]) == "ban" and M("개회", ["변제계획인가결정", "개시결정"]) == "ban"
          and M("하단", ["파산선고"]) == "ban")
    check("면책결정: 확정 전 금지, 확정 → 회수 불가", M("개회", ["면책결정"]) == "ban" and M("개회", ["면책결정"], {"csCfmtnYmd": "20261020"}) == "end")
    check("폐지·기각·면책불허가 → 회수 가능", M("개회", ["폐지결정", "개시결정"]) == "ok" and M("개회", [], {"csUltmtDvsNm": "기각"}) == "ok"
          and M("하면", ["면책불허가결정"]) == "ok")
    check("근거는 그 절차 조문만", L.rehab_status("개회", [("금지명령", "")])["basis"].startswith("채무자회생법 제593조 —"))
    try:
        b.lg_rehab_search("서울중앙지방법원\t2025가소12345\t홍시험")
        check("회생·파산이 아닌 사건번호는 막음", False)
    except ValueError:
        check("회생·파산이 아닌 사건번호는 막음", True)
    from demo import install as demo_install
    demo_install(b)
    st = b.lg_rehab_search("서울회생법원\t2026개회99901\t임다솜")
    r2 = b.run_submit("123456")
    card = b.result_card(r2["done_list"][0]["cid"])
    check("조회 결과 카드에 관리 가부", card["rehab"] and card["rehab"]["code"] in L.MANAGE and card["status"] in ("가능", "주의", "정지", "금지", "회수 불가")
          or card["rehab"]["label"].startswith(card["status"]), str(card.get("rehab")))
    b.run_stop()
    rh = b.lg_rehab()
    one = next((x for x in rh["items"] if x["no"] == "2026개회99901"), None)
    check("조회한 회생 사건이 추적 목록에 자동으로", one and one["debtor"]["name"] == "임다솜" and one["m"]["source"] == "진행내용", str(one and one["m"]))
    check("상태별 건수", sum(rh["counts"].values()) == rh["total"])
    if one and one["m"]["code"] in L.BLOCKING:
        st = {r["name"]: r["st"][0] for r in b.lg_doc_rows("지급명령", {})["rows"]}
        check("정지·금지면 서류 대상에서 빠짐", st.get("임다솜") in ("no", None), str(st.get("임다솜")))
    print(f"\n정상 {ok} · 문제 {fail}")
    return fail


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
