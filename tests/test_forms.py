# -*- coding: utf-8 -*-
"""회사 양식 서류 점검 (법원 사이트에 접속하지 않음).

    python tests/test_forms.py
"""
import os
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

from bridge import Bridge  # noqa: E402
from core import forms as FM  # noqa: E402
from form_sample import make  # noqa: E402

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
    tmp = tempfile.mkdtemp(prefix="court_forms_")
    pdf = make(os.path.join(tmp, "주소보정서_회사양식.pdf"))

    print("값 모양")
    check("금액 한글: 3,412,000 → 삼백사십일만이천", FM.kor_num(3412000) == "삼백사십일만이천")
    check("금액 한글: 10,000 → 일만, 110,000 → 십일만", FM.kor_num(10000) == "일만" and FM.kor_num(110000) == "십일만")
    check("금액 둘 다", FM.fmt_value("amount", "both", "3412000") == "금 3,412,000원(삼백사십일만이천원)")
    check("날짜 두 모양", FM.fmt_value("date", "dot", "2026-11-04") == "2026. 11. 4." and FM.fmt_value("date", "kor", "2026-11-04") == "2026년 11월 4일")
    check("사건번호 띄어 쓰기", FM.fmt_value("case_no", "space", "2026가소10231") == "2026 가소 10231")
    check("사건번호 정리 (띄어쓰기·전각 숫자)", FM.clean_case_no("２０２６ 가소 20877") == "2026가소20877")

    print("칸 자동 찾기")
    r = FM.detect(pdf)
    F = r["fields"]
    by = lambda k: [f for f in F if f.get("item") == k]  # noqa: E731
    check("스캔 PDF 아님", not r["scanned"])
    check("표의 「사　　건」 옆 칸 → 사건번호", len(by("case_no")) == 1 and by("case_no")[0]["x"] > 150)
    check("「원　　고」 두 곳(표·서명줄) → 우리 회사명", len(by("company")) == 2)
    check("「피　　고」 → 채무자 이름", len(by("debtor")) == 1)
    ck = [f for f in F if f["type"] == "check"]
    check("□ 체크 6곳을 찾음", len(ck) == 6, len(ck))
    check("□ 옆 글자로 선택지 짝짓기", {(f["item"], f.get("opt")) for f in ck} ==
          {("reason", "주소불명"), ("reason", "폐문부재"), ("reason", "수취인불명"), ("reason", "이사불명"), ("req", "재송달"), ("req", "특별송달")})
    na = by("new_addr")
    check("「2. 보정할 주소」 아래 상자 → 새 주소 (긴 글)", na and na[0]["type"] == "long" and na[0]["h"] > 30 and na[0]["y"] > 340, na)
    check("「○○법원 귀중」 → 법원 덮어쓰기", by("court") and by("court")[0]["type"] == "over" and by("court")[0]["suffix"] == " 귀중")
    check("「20 . . .」 → 작성일 덮어쓰기", by("date") and by("date")[0]["type"] == "over")
    check("본문 문장의 「원고」「피고」는 칸으로 안 잡음", len(by("debtor")) == 1)

    print("점검 · 채우기")
    names = {i["k"]: i["n"] for i in FM.ITEMS}
    v = {"company": "가상신용정보 주식회사", "debtor": "이예시", "case_no": "2026차전5512", "court": "수원지방법원", "reason": "이사불명",
         "new_addr": "경기도 수원시 팔달구 예시로 45, 3층", "date": "2026-11-04", "agent": "담당 ○○○"}
    check("값이 다 있으면 정상", FM.check(F, v, names, full=False)["status"] == "ok")
    c = FM.check(F, dict(v, court=""), names, full=False)
    check("법원이 비면 빈 칸", c["status"] == "bad" and c["issues"][0]["k"] == "court")
    c = FM.check(F, dict(v, debtor="이예시 외 3명 (연대보증인 김예시 · 박예시 · 최예시 · 그리고 아주 긴 이름의 공동피고 주식회사 예시상사)"), names, full=False)
    check("칸보다 긴 글자는 넘침(확인)", c["status"] == "warn")
    c = FM.check(F, v, names, ref={"court": "수원지방법원 안산지원"}, full=False)
    check("사건 대장의 법원과 다르면 확인 + 대장 값으로 고치기", c["status"] == "warn" and c["issues"][0]["fix"]["v"] == "수원지방법원 안산지원")
    check("새 주소는 비어도 됨 (특별송달 등)", FM.check(F, dict(v, new_addr=""), names, full=False)["status"] == "ok")
    out = FM.build(pdf, r["pages"], F, [v, dict(v, debtor="김가상", reason="폐문부재", req="특별송달", new_addr="")], os.path.join(tmp, "out.pdf"))
    from pypdf import PdfReader
    rd = PdfReader(out)
    t0, t1 = rd.pages[0].extract_text(), rd.pages[1].extract_text()
    check("두 사람 → 두 쪽", len(rd.pages) == 2)
    check("고정 문구는 그대로", "위 사건에 관하여 원고는 피고의 주소를" in t0)
    check("1쪽에 이예시 · 수원지방법원 귀중", "이예시" in t0 and "수원지방법원 귀중" in t0)
    check("2쪽은 김가상 (쪽이 섞이지 않음)", "김가상" in t1 and "이예시" not in t1)
    check("파일이 작음 (글꼴은 쓴 글자만)", os.path.getsize(out) < 400_000, os.path.getsize(out))

    print("양식함 · 대상 · 저장")
    b = Bridge(os.path.join(tmp, "data"))
    b.reveal = lambda p: True
    b.store.set_setting("save.export_dir", os.path.join(tmp, "out"))
    b.store.set_setting("legal.creditor", {"name": "가상신용정보 주식회사", "addr": "서울 ○○구", "rep": "○○○", "phone": ""})
    fid = b.fm_add(pdf)
    check("PDF 넣기 → 칸 정하기 전(초안)", b._form(fid)["draft"] and not b.fm_list()["forms"])
    check("이름은 파일 이름에서 「회사양식」 떼고", b._form(fid)["name"] == "주소보정서")
    try:
        b.fm_save(fid, {"fields": [dict(F[0], item="")]})
        check("항목 없는 칸은 저장 안 됨", False)
    except ValueError:
        check("항목 없는 칸은 저장 안 됨", True)
    b.fm_save(fid, {"fields": [f for f in b.fm_detect(fid)["fields"] if f.get("item")]})
    check("저장하면 양식함에", b.fm_list()["forms"][0]["n"] == 14)
    b.fm_save(fid, {"fields": [f for f in b._form(fid)["fields"] if f["item"] != "agent"]})
    check("칸을 바꾸면 판이 올라가고 예전 칸은 보관", b._form(fid)["ver"] == 2 and os.path.isfile(os.path.join(b._fdir(fid), "versions", "v1.json")))
    d1, _ = b.legal.upsert_debtor({"name": "이예시", "key": "110-1", "addr": "서울 ○○구 ○○로 1", "principal": 1000000})
    d2, _ = b.legal.upsert_debtor({"name": "김회생", "key": "110-2", "addr": "부산 ○○구"})
    import datetime as dt
    b.lg_rehab_register({"did": d2["id"], "doc": "개시결정", "kind": "개인회생", "no": "2026개회13579", "court": "서울회생법원", "got": dt.date.today().isoformat()})
    xl = os.path.join(tmp, "대상.xlsx")
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["성명", "사건번호", "관할법원", "신주소", "불능사유"])
    ws.append([" 이예시 ", "2026 가소 777", "", "경기 ○○시 새길 1", "이사불명"])
    ws.append(["김회생", "2026가소888", "부산지방법원", "", "폐문부재"])
    wb.save(xl)
    t = b.fm_targets(fid, "xl", path=xl)
    T = {x["name"]: x for x in t["targets"]}
    check("엑셀 열 이름 자동 짝짓기 (성명·사건번호·관할법원·신주소·불능사유)", set(t["excel"]["auto"]) == {"debtor", "case_no", "court", "new_addr", "reason"}, t["excel"]["auto"])
    check("이름 앞뒤 빈칸 · 사건번호 띄어쓰기 정리", T["이예시"]["vals"]["case_no"] == "2026가소777" and any("정리" in n["m"] for n in T["이예시"]["notes"]))
    check("회생 금지인 채무자는 고를 수 없음", T["김회생"]["block"] is not None and T["이예시"]["block"] is None)
    check("고정값(우리 회사명·작성일)이 들어감", T["이예시"]["vals"]["company"] == "가상신용정보 주식회사" and T["이예시"]["vals"]["date"])
    tl = b.fm_targets(fid, "ledger")
    check("원장에서 고르기", len(tl["targets"]) == 2)
    items = [{"tid": T["이예시"]["tid"], "did": d1["id"], "name": "이예시", "vals": dict(T["이예시"]["vals"], court="수원지방법원")}]
    res = b.fm_make(fid, items, "each", {})
    files = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(tmp, "out")) for f in fs if f.endswith(".pdf")]
    check("한 명당 PDF 하나 저장", res["count"] == 1 and len(files) == 1 and "이예시" in os.path.basename(files[0]), files)
    check("원장 기록에 남김", any("주소보정서 작성" in x["text"] for x in b.legal.debtor(d1["id"])["log"]))
    check("30일 안에 같은 서류 → 중복으로 알려 줌", b.fm_precheck(fid, items)["dups"])
    try:
        b.fm_make(fid, [dict(items[0], vals=dict(items[0]["vals"], court=""))], "one", {})
        check("빈 칸이 남으면 저장 안 됨", False)
    except ValueError:
        check("빈 칸이 남으면 저장 안 됨", True)
    late = [{"tid": "x", "did": d2["id"], "name": "김회생", "vals": dict(T["김회생"]["vals"])}]
    try:
        b.fm_make(fid, late, "one", {})
        check("저장 직전 회생 금지면 빼고, 남는 게 없으면 안 만듦", False)
    except ValueError as e:
        check("저장 직전 회생 금지면 빼고, 남는 게 없으면 안 만듦", "회생" in str(e))
    p = b.fm_export(fid)
    with zipfile.ZipFile(p) as z:
        check("양식 내보내기 (.양식.zip: PDF + 칸)", set(z.namelist()) == {"form.pdf", "form.json"})
    nid = b.fm_import(p)
    check("동료 양식 가져오기 → 칸까지 그대로", len(b._form(nid)["fields"]) == 13 and not b._form(nid)["draft"])
    b.fm_task("송달불능", nid)
    b.fm_delete(nid)
    check("양식을 지우면 업무별 기본 양식에서도 빠짐", "송달불능" not in b._fset()["tasks"])
    b.fm_item_add("담당 부서", "법조치1팀")
    k = b._fset()["items"][0]["k"]
    check("회사에서 더한 항목 (고정값)", b._base_vals().get(k) == "법조치1팀" and any(i["k"] == k for i in b.fm_list()["items"]))

    print("엑셀 열 기억 · 연결 기준 (키)")
    from core import xlmap as XM
    from core import printing
    check("인쇄기 목록은 실패해도 빈 목록", isinstance(printing.list_printers(), list))
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["차주 성함", "여신 키", "사건 No", "관할 법정", "남은 돈"])
    ws.append(["이예시", "110-1", "2026가소777", "수원지방법원", "1,000,000"])
    ws.append(["김새로", "220-9", "2026가소999", "부산지방법원", "500,000"])
    xl2 = os.path.join(tmp, "낯선머리글.xlsx")
    wb.save(xl2)
    o = b.xl_open(xl2, "debtor")
    check("낯선 머리글(여신 키)은 처음엔 키로 못 짝지음", "key" not in o["mapping"], o["mapping"])
    b.xl_apply(xl2, "debtor", {"name": 0, "key": 1, "principal": 4, "court": 3})
    o2 = b.xl_open(xl2, "form")
    check("원장에서 짝지은 열을 회사 양식 화면도 기억 (차주 성함·여신 키·관할 법정)", o2["mapping"].get("debtor") == 0 and o2["mapping"].get("mgmt_no") == 1
          and o2["mapping"].get("court") == 3 and o2["src"].get("mgmt_no") == "mem", o2["mapping"])
    o3 = b.xl_open(xl2, "case")
    check("사건 대장 화면도 기억 (여신 키 → 메모 1)", o3["mapping"].get("memo1") == 1 and o3["mapping"].get("party") == 0, o3["mapping"])
    d, how = b.legal.match_debtor("", "이예시", "", ["key", "name"])
    check("찾는 순서: 키가 없으면 이름으로 (찾은 방법을 알려 줌)", d and how == "name")
    check("이름만 끄면 이름으로 안 찾음", b.legal.match_debtor("", "이예시", "", ["key"])[0] is None)
    b.link_set("debtor", {"by": ["key"]})
    o4 = b.xl_open(xl2, "debtor")
    check("연결 기준을 「키만」으로 바꾸면 미리보기도 바뀜", "갱신 2명" in o4["summary"], o4["summary"])
    b.link_set("debtor", {"by": [], "key_col": "남은 돈"})
    o5 = b.xl_open(xl2, "debtor")
    check("모두 끄면 늘 새로 · 키로 쓸 열을 정하면 그 열이 키", "새로 2명" in o5["summary"] and o5["mapping"].get("key") == 4, (o5["summary"], o5["mapping"]))
    b.link_set("debtor", {"by": ["key", "name_birth", "name"], "key_col": ""})
    b.link_set("case_debtor", {"by": ["key"]})
    cc = b.store.add_case({"court": "수원지방법원", "court_code": "000250", "year": 2026, "dvs": "가소", "serial": 31, "party": "이예시", "memo1": ""})
    check("사건↔채무자를 「키만」으로 하면 이름이 같아도 안 이음", b._debtor_of_case(cc["id"]) is None)
    b.link_set("case_debtor", {"by": ["key", "name"]})
    check("「이름」을 켜면 이음", b._debtor_of_case(cc["id"]) is not None)
    b.link_set("dlv", {"by": "none"})
    check("보정 관리: 「찾지 않음」이면 같은 사건도 새로", b._dlv_match({"case_no": "2026가소777"}) is None)
    check("기억은 지울 수 있음", b.xl_forget() and not b._xlmem())
    check("모르는 기능은 막음", _raises(lambda: b.link_set("x", {})))

    print("PC 켤 때 자동 실행")
    from core import autostart as AS
    st = AS.status()
    check("Windows가 아니거나 exe로 실행하지 않으면 「회사 PC에서」", not st["supported"] or AS.WIN)
    if not AS.WIN:
        check("쓸 수 없는 곳에서 켜면 막음", _raises(lambda: AS.set_on(True)))
    # 가짜 레지스트리로 켜고 끄기 확인
    import types
    reg = {}
    fake = types.SimpleNamespace(HKEY_CURRENT_USER=1, KEY_SET_VALUE=2, REG_SZ=1)

    class K:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    fake.OpenKey = lambda *a: K()
    fake.QueryValueEx = lambda k, n: (reg[n], 1) if n in reg else (_ for _ in ()).throw(OSError())
    fake.SetValueEx = lambda k, n, z, t, v: reg.__setitem__(n, v)
    fake.DeleteValue = lambda k, n: reg.pop(n) if n in reg else (_ for _ in ()).throw(FileNotFoundError())
    exe = os.path.join(tmp, "종합관리.exe")
    open(exe, "w").close()
    old = (AS.WIN, os.environ.get("CSH_LAUNCHER"), sys.modules.get("winreg"))
    AS.WIN, os.environ["CSH_LAUNCHER"], sys.modules["winreg"] = True, exe, fake
    try:
        check("켜면 시작 프로그램에 이 exe를 넣음", AS.set_on(True)["on"] and reg[AS.NAME] == f'"{exe}" --autostart')
        check("끄면 뺌 (없어도 오류 없음)", not AS.set_on(False)["on"] and AS.NAME not in reg and not AS.set_on(False)["on"])
        reg[AS.NAME] = '"C:\\예전\\위치.exe"'
        check("다른 위치가 등록돼 있으면 알려 줌", AS.status()["other"] and not AS.status()["on"])
        reg[AS.NAME] = r'"C:\Users\a\AppData\Local\CourtSearch\사건조회도우미.exe" --autostart'
        check("예전 이름(사건조회도우미.exe)을 가리키면 새 이름으로 옮김", AS.migrate()["on"] and exe in reg[AS.NAME])
        reg.pop(AS.NAME)
        check("켠 적이 없으면 옮기지 않음", not AS.migrate()["on"] and AS.NAME not in reg)
    finally:
        AS.WIN = old[0]
        if old[1] is None:
            os.environ.pop("CSH_LAUNCHER", None)
        else:
            os.environ["CSH_LAUNCHER"] = old[1]
        if old[2] is None:
            sys.modules.pop("winreg", None)
        else:
            sys.modules["winreg"] = old[2]
    print("현황 콘솔 · 작업 기록 · 찾기")
    n0 = len(b.activity())
    b.lg_dlv_add({"case_no": "2026가소4321", "party": "기록이", "reason": "폐문부재", "recv": "2026-11-02"})
    acts = b.activity()
    check("한 일이 작업 기록에 남음 (보정 직접 등록)", len(acts) == n0 + 1 and "2026가소4321" in acts[0]["text"] and acts[0]["go"] == "lg_dlv", acts[:1])
    check("작업 기록은 최근 것부터", acts[0]["at"] >= acts[-1]["at"])
    con = b.console()
    check("현황 콘솔: 숫자 네 칸 · 업무 흐름 · 오늘 할 것 · 기록", {"todo", "hot", "dlv", "soon", "stop", "docs", "forms"} <= set(con["kpi"]) and con["flow"]["dlv"] == con["kpi"]["dlv"]
          and isinstance(con["today"], list) and con["log"], con["kpi"])
    check("이번 주 만든 서류 수", con["kpi"]["docs"] >= 1, con["kpi"])
    pr = b.palette("이예시")
    check("찾기: 사건·채무자 이름으로", any("이예시" in x["t"] for x in pr["cases"]) and any("이예시" in x["t"] for x in pr["debtors"]), pr)
    check("찾기: 사건번호로", b.palette("2026가소31")["cases"])
    check("찾기: 빈 말은 빈 결과", b.palette("") == {"cases": [], "debtors": []})
    print(f"\n정상 {ok} · 문제 {fail}")
    return fail == 0


def _raises(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
