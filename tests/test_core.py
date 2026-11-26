# -*- coding: utf-8 -*-
"""기능 점검 (법원 사이트에는 접속하지 않음 — 시연용 가짜 결과 사용).

    python tests/test_core.py
"""
import os
import sys
import json
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

from bridge import Bridge  # noqa: E402
from core import rules  # noqa: E402
from core.caseno import CourtNames, parse_case_no  # noqa: E402
from demo import install  # noqa: E402

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
    tmp = tempfile.mkdtemp(prefix="court_test_")
    b = Bridge(os.path.join(tmp, "data"))
    install(b)
    b.store.set_setting("save.export_dir", os.path.join(tmp, "out"))
    b.reveal = lambda p: True
    b.store.set_setting("run.delay", 0)

    print("사건번호 · 법원 이름")
    check("2025가소123456", parse_case_no("2025가소123456") == (2025, "가소", "123456"))
    check("두 자리 연도", parse_case_no("25차전 8,812") == (2025, "차전", "8812"))
    check("잘못된 번호", parse_case_no("2025가소12a4") is None)
    cn = CourtNames(b.meta.court_names())
    check("수원지법 → 수원지방법원", cn.match("수원지법")[0] == "수원지방법원")
    check("지원 이름", cn.match("수원지방법원 성남지원")[0] == "성남지원")

    print("상태 규칙")
    s = b.store.settings
    st = lambda rows, basic=None: rules.classify(s, [{"progCtt": r} for r in rows], basic or {})[0]
    check("최근 줄 우선 (선고가 송달불능보다 최근)", st(["판결선고", "소장부본 송달불능"]) == "판결 선고")
    check("송달불능 뒤 도달 → 진행 중", st(["소장부본 송달 도달", "소장부본 송달불능"]) == "진행 중")
    check("판결정본 도달 → 판결 선고", st(["피고 판결정본 송달 도달", "판결선고"]) == "판결 선고")
    check("확정일자 있으면 확정", st(["집행문 부여"], {"csCfmtnYmd": "20261001"}) == "확정")
    check("보정명령", st(["주소보정명령"]) == "보정명령")

    print("조회 흐름")
    p = b.pick_preview({})
    check("조회 대상 고르기", p["count"] > 0 and p["total"] == len(b.store.active_cases()), str(p))
    stt = b.run_start("점검 조회", case_ids=list(b.store.cases)[:4])
    check("조회 시작 · 그림 받기", stt["active"] and stt.get("captcha", {}).get("image"))
    r = b.run_submit("000000")
    check("숫자 틀림 → 같은 사건 · 새 그림", r["message"]["kind"] == "captcha" and r["case"]["no"] == 1)
    r = b.run_submit("123456")
    check("조회 성공 → 다음 사건", r["last"]["kind"] == "ok" and r["case"]["no"] == 2, str(r.get("last")))
    # 찾을 수 없음 + 이름 바꿔 다시
    cid = r["case"]["cid"]
    b.store.cases[cid]["party"] = "㈜없음상사"
    r = b.run_submit("123456")
    check("찾을 수 없음 → 이름 바꿔 다시", r["message"] and r["message"]["kind"] == "retry", str(r.get("message")))
    for _ in range(8):
        if r["case"]["cid"] != cid:
            break
        r = b.run_submit("123456")
    check("이름을 다 바꿔도 없으면 넘어감", r["case"]["cid"] != cid and b.store.cases[cid]["last_result"] == "notfound")
    r = b.run_skip()
    check("건너뛰기 → 다음 사건", r["case"]["no"] == 4)
    r = b.run_submit("123456")
    check("마지막 사건 → 끝", r["finished"])
    rid = r["rid"]
    res = b.run_result(rid)
    check("결과 보기", len(res["rows"]) == 4)
    path = b.export_run(rid)
    check("결과 엑셀", os.path.isfile(path))
    import openpyxl
    wb = openpyxl.load_workbook(path)
    check("엑셀 시트", wb.sheetnames == ["요약", "일반내용", "진행내용", "당사자"], str(wb.sheetnames))

    print("조회 목록 고르기 · 빼기 · 비우기")
    b.run_stop()
    ids6 = list(b.store.cases)[10:16]
    b.run_start("빼기 점검", case_ids=ids6)
    b.run_submit("123456")
    r = b.run_submit("123456")
    done2 = [d["cid"] for d in r["done_list"]]
    r = b.run_remove(cids=[done2[0]])
    check("고른 사건만 목록에서 빠짐", r["removed"] == 1 and [d["cid"] for d in r["done_list"]] == done2[1:] and r["stat"]["total"] == 5)
    check("사건 대장·결과는 그대로", done2[0] in b.store.cases and b.store.result(done2[0]).get("prog"))
    nxt = r["case"]["cid"]
    r = b.run_remove(cids=[nxt])
    check("지금 차례인 사건을 빼면 다음 사건으로", r["case"]["cid"] != nxt and r["stat"]["total"] == 4)
    r = b.run_remove(scope="done")
    check("비우기 → 조회한 것만 빠지고 남은 사건은 계속", not r["done_list"] and r["stat"]["left"] == 3 and r["active"])
    r = b.run_remove(cids=[q["cid"] for q in r["queue"]])
    check("다 빼면 조회가 끝나고 기록도 지움", not r["active"] and not b.sess and not any(x["name"] == "빼기 점검" for x in b.store.runs))

    print("확인할 것 · 달력 · 보고서")
    h = b.home()
    check("확인할 것 목록", len(h["items"]) > 0)
    key = h["items"][0]["key"]
    b.todo_done(key, "처리 메모")
    check("처리함", any(i["key"] == key and i["done"] for i in b.home()["items"]))
    b.deadline_set(h["items"][1]["key"], "2026-12-01")
    check("기한 넣기", b.store.todos[h["items"][1]["key"]]["deadline"] == "2026-12-01")
    import datetime as dt
    t = dt.date.today()
    check("달력", isinstance(b.calendar(t.year, t.month), list))
    rp = b.report_save(t.year, t.month, ["요약 숫자", "상태별 건수", "이번 달 확정 목록", "송달불능·보정명령 목록", "법원별 건수"])
    check("월간 보고서", os.path.isfile(rp))

    print("사건 대장 · 엑셀 넣기")
    xl = os.path.join(tmp, "목록.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["계좌번호", "관할법원", "사건번호", "채무자명", "담당"])
    ws.append(["110-1", "수원지법", "2025가소777001", "홍길동", "김"])
    ws.append(["110-2", "서울중앙지방법원", "2025가소12a4", "박철수", "김"])
    ws.append(["110-3", "대구지방법원", "2023머5521", "이", "김"])
    ws.append(["110-4", "인천지방법원", "2024차전 8812", "김영", "이"])
    wb.save(xl)
    pv = b.import_preview(xl)
    check("칸 자동 찾기", pv["mapping"].get("court") == 1 and pv["mapping"].get("case") == 2 and pv["mapping"].get("party") == 3
          and pv["mapping"].get("memo1") == 0, str(pv["mapping"]))
    check("반영할 줄 · 건너뛸 줄", pv["good_count"] == 2 and len(pv["skips"]) == 2, f"{pv['good_count']} {pv['skips']}")
    n0 = len(b.store.active_cases())
    ap = b.import_apply(xl, gone_action="keep")
    check("대장에 반영", ap["added"] == 2 and len(b.store.active_cases()) == n0 + 2, str(ap))
    ap = b.import_apply(xl, gone_action="keep")
    check("같은 파일 다시 넣으면 중복 없음", ap["added"] == 0 and ap["updated"] == 2)
    cid = b.case_save({"court": "서울북부", "case_no": "2026가소1", "party": "윤서아"})
    check("한 건 넣기", b.store.cases[cid]["court"] == "서울북부지방법원")
    d = b.case_detail(list(b.store.cases)[0])
    check("사건 상세", d["checked"] and d["basic"] and d["rounds"])

    print("직접 입력해서 조회")
    g, bad = b.quick_parse("서울중앙지방법원\t2025가소555001\t홍길동\n수원지법 성남지원, 2024차전8812, 주식회사 대한상사, 110-9\n"
                           "2025가단1 서울북부 윤서아\n인천지방법원 2025가소1 이\n아무말")
    check("탭·쉼표·띄어쓰기·칸 순서", len(g) == 3 and g[1]["court"] == "성남지원" and g[1]["memo1"] == "110-9"
          and g[2]["court"] == "서울북부지방법원", str(g))
    check("못 읽은 줄 알려주기", len(bad) == 2 and "2글자" in bad[0]["problem"], str(bad))
    n0 = len(b.store.active_cases())
    st = b.quick_search("서울남부지방법원 2025가소888001 김영", keep=False)
    check("바로 조회 시작", st["active"] and st["case"]["case_no"] == "2025가소888001")
    r = b.run_submit("123456")
    cid = [c for c in b.store.cases.values() if c["serial"] == "888001"][0]
    check("남기지 않기 → 끝나면 보관함", r["finished"] and cid["archived"] and cid["last_result"] == "ok"
          and len(b.store.active_cases()) == n0)
    st = b.quick_search("서울남부지방법원 2025가소888001 김영", keep=True)
    b.run_submit("123456")
    check("남기기 → 사건 대장으로", not cid["archived"] and len(b.store.active_cases()) == n0 + 1)

    print("엑셀 칸 찾기 (값을 보고) · 대량 조회")
    xl2 = os.path.join(tmp, "머리글없음.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["110-7", "2025가소700001", "수원지방법원", "홍길동", "김"])
    ws.append(["110-8", "2025가소700002", "서울중앙", "박철수", "김"])
    ws.append(["110-9", "2024차전700003", "인천지법", "주식회사 대한상사", "이"])
    wb.save(xl2)
    pv = b.import_preview(xl2)
    check("머리글 없는 파일: 값으로 칸 찾기", pv["mapping"].get("case") == 1 and pv["mapping"].get("court") == 2
          and pv["mapping"].get("party") == 3 and pv["good_count"] == 3, str(pv["mapping"]) + str(pv["auto"]))
    xl3 = os.path.join(tmp, "이상한머리글.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["No", "관할", "번호값", "고객", "비고"])
    ws.append(["1", "대전지방법원", "2025가단800001", "서지우", ""])
    ws.append(["2", "부산지방법원", "2025가소800002", "강민재", ""])
    wb.save(xl3)
    pv = b.import_preview(xl3)
    check("머리글 이름이 달라도 찾기", pv["mapping"].get("case") == 2 and pv["mapping"].get("court") == 1
          and pv["mapping"].get("party") == 3, str(pv["mapping"]))
    pv = b.import_preview(xl3, {"court": 1, "case": 2, "party": 4})
    check("칸을 직접 고르면 그대로", pv["mapping"]["party"] == 4 and pv["good_count"] == 0)
    n0 = len(b.store.active_cases())
    st = b.bulk_search(xl3, {"court": 1, "case": 2, "party": 3}, keep=False)
    check("대량 조회 시작", st["active"] and st["stat"]["total"] == 2)
    r = b.run_submit("123456")
    check("결과 카드 바로 보기", r["last"]["card"]["case_no"] and "prog" in r["last"]["card"] and r["done_list"])
    r = b.run_submit("123456")
    check("남기지 않기 → 끝나면 보관함", r["finished"] and len(b.store.active_cases()) == n0)

    print("채권 나누기")
    first = b.book
    n_first = len(b.store.active_cases())
    b.book_add("두번째 채권")
    check("새 채권은 비어 있음", b.book == "두번째 채권" and not b.store.cases)
    b.case_save({"court": "서울중앙", "case_no": "2026가소2", "party": "김영"})
    b.book_switch(first)
    check("채권 바꾸면 자료도 바뀜", len(b.store.active_cases()) == n_first)
    check("설정은 함께 씀", b.store.settings["run"]["delay"] == 0)
    b.book_rename("두번째 채권", "B채권")
    check("이름 바꾸기", "B채권" in b.book_names())
    b.book_delete("B채권")
    check("지우기 (압축 남김)", "B채권" not in b.book_names() and os.listdir(os.path.join(b.data_dir, "지운 채권")))
    # 예전 판 자료 옮기기
    old = os.path.join(tmp, "old")
    os.makedirs(os.path.join(old, "results"))
    import json as _j
    _j.dump({"x1": {"id": "x1", "court": "서울중앙지방법원", "year": 2025, "dvs": "가소", "serial": "1", "party": "홍길동"}},
            open(os.path.join(old, "cases.json"), "w", encoding="utf-8"))
    b2 = Bridge(old)
    check("예전 자료 → 기본 채권", b2.book == "기본 채권" and "x1" in b2.store.cases
          and not os.path.exists(os.path.join(old, "cases.json")))

    print("경매 (법원경매정보 창)")
    from demo import fake_auction
    r = b.auction_add("서울중앙지방법원\t2024타경4354\t110-1\n수원지법 성남지원, 2025타경12345\n인천지방법원 2025타경7781 계좌 301\n아무 말")
    check("경매 사건 넣기 (탭·쉼표·띄어쓰기)", r["added"] == 3 and len(r["bad"]) == 1, str(r))
    r2 = b.auction_add("서울중앙지방법원 2024타경4354")
    check("같은 사건은 한 번만", r2["added"] == 0 and r2["same"] == 1)
    au = b.auct
    aid = r["ids"][0]
    a0 = au.items[aid]
    check("법원 코드 (B+6자리)", a0["court_code"] == "B000210" and au.items[r["ids"][1]]["court"] == "성남지원")

    class FakeWin:
        """프로그램 안 브라우저 창 대신: 사이트 화면이 받은 자료를 흉내 낸다"""
        def __init__(self, caps):
            self.caps, self.loaded, self.tabs = caps, None, 0
        def load_url(self, u):
            self.n = 0
            if self.loaded:
                self.loaded()
        def evaluate_js(self, js):
            import json as J
            self.log = getattr(self, "log", []) + [js[:40]]
            if "var r={hook" in js:
                return J.dumps({"hook": True, "ready": True})
            if "setSrc(" in js:
                self.backs = getattr(self, "backs", 0) + 1
                self.tabs = 0
                return "back"
            if "window.__csh=[]" in js:
                self.fills = getattr(self, "fills", []) + [js.count("click()")]
                return "filled"
            if js.startswith("JSON.stringify"):
                start = int(js.split("slice(")[1].split(")")[0])
                give = self.caps(self.tabs)
                return J.dumps({"c": len(give), "h": True, "l": give[start:]})
            if "tabs2" in js:
                self.tabs = 1
            return "ok"
    import json as J
    def caps_for(tabs, got):
        out = [{"u": "/pgj/pgj15A/selectAuctnCsSrchRslt.on", "t": J.dumps({"status": 200, "data": got["gnrl"]})}]
        if tabs:
            out += [{"u": "/pgj/pgj15A/selectCsDtlDxdyDts.on", "t": J.dumps({"status": 200, "data": got["dates"]})},
                    {"u": "/pgj/pgj15A/selectDlvrOfdocDtsDtl.on", "t": J.dumps({"status": 200, "data": got["docs"]})}]
        return out
    got = fake_auction(a0, seed=1)
    fw = FakeWin(lambda tabs: caps_for(tabs, got))
    b.awin = fw
    b.store.set_setting("auction.delay", 0)
    st = b.auction_start([aid, r["ids"][1]])
    check("검색 화면으로 돌아가 채우고 「검색」 누르기", st["phase"] == "wait" and fw.fills == [1] and getattr(fw, "backs", 0) == 1,
          str((st["phase"], getattr(fw, "fills", None), getattr(fw, "backs", 0))))
    st = b.auction_state()
    check("사건내역 받으면 탭 열기", st["phase"] in ("tabs", "saved") and st["parts"]["gnrl"], str(st))
    st = b.auction_state()
    check("세 가지 다 받으면 저장 → 다음 사건", st["done"] and st["done"][0]["state"] == "ok" and st["idx"] == 1, str(st))
    st = b.auction_state()
    check("다음 사건도 창을 닫지 않고 바로 (사이트 안에서 돌아가기)", st["idx"] == 1 and fw.backs == 2 and len(fw.fills) == 2 and st["phase"] == "wait",
          str((st["phase"], fw.backs, fw.fills)))
    a0 = au.items[aid]
    check("목록 요약 (사건명·다음 매각기일·최근 문건)", a0["csNm"] and a0["next_sale"].get("date") and a0["last_doc"].get("text"), str(a0))
    # 사이트가 로봇으로 판단한 경우
    fw.caps = lambda tabs: [{"u": "/pgj/pgj15A/selectAuctnCsSrchRslt.on", "t": J.dumps({"status": 200, "message": "비정상 접근", "data": {"ipcheck": False}})}]
    b.asess["read"] = 0
    st = b.auction_state()
    check("로봇 탐지 → 멈추고 안내", st["phase"] == "robot" and "비정상" in st["msg"], str((st["phase"], st["msg"], b.asess.get("caps")[:1])))
    b.auction_stop()
    # 두 번째 조회: 새 문건
    got2 = json.loads(json.dumps(got))
    got2["docs"]["dlt_ofdocDtsLst"].append({"ofdocRcptYmd": "20261029", "rcptDts": "채무자 김OO 매각기일연기신청서 제출", "rcptRslt": ""})
    n = au.record(aid, got2)
    d = b.auction_detail(aid)
    check("새 문건 찾기", n == 1 and any(x["new"] for x in d["docs"]) and au.items[aid]["new_docs"] == 1)
    check("상세: 사건기본·물건·당사자·기일·문건·송달", d["basic"] and d["goods"] and d["parties"] and d["dates"] and d["docs"] and d["dlvr"])
    dup = json.loads(json.dumps(got2))
    dup["docs"]["dlt_ofdocDtsLst"] += [{"ofdocRcptYmd": "20261030", "rcptDts": "채권자 보정서 제출", "rcptRslt": ""}] * 2
    before = len(au.result(aid)["docs"])
    n2 = au.record(aid, dup)
    check("같은 날 같은 문건 두 줄도 모두 저장", n2 == 2 and len(au.result(aid)["docs"]) == before + 2)
    n3 = au.record(aid, dup)
    check("다시 조회해도 늘어나지 않음", n3 == 0 and len(au.result(aid)["docs"]) == before + 2)
    p = b.auction_export([aid])
    wb = openpyxl.load_workbook(p)
    check("경매 엑셀", wb.sheetnames == ["경매 사건", "문건처리내역", "송달내역", "기일내역"], str(wb.sheetnames))
    t = dt.date.fromisoformat(a0["next_sale"]["date"])
    check("달력에 매각기일", any(e.get("aid") == aid for e in b.calendar(t.year, t.month)))
    print("경매 목록 빼기 · 삭제")
    fw.caps = lambda tabs: caps_for(tabs, got)
    st = b.auction_start([aid, r["ids"][1]])
    for _ in range(6):
        if st["done"]:
            break
        st = b.auction_state()
    check("경매 조회 중 「이번 조회」에 쌓임", len(st["done"]) == 1, str(st["done"]))
    try:
        b.auction_delete([r["ids"][2]])
        check("경매 조회 중에는 삭제 막음", False)
    except ValueError:
        check("경매 조회 중에는 삭제 막음", True)
    st = b.auction_run_remove(aids=[st["done"][0]["aid"]])
    check("이번 조회 목록에서 빼기 (사건·결과는 그대로)", st["removed"] == 1 and not st["done"] and aid in au.items and au.result(aid)["docs"])
    b.auction_stop()
    gone = b.auction_add("대전지방법원 2025타경9999")["ids"][0]
    au.record(gone, fake_auction(au.items[gone], seed=3))
    b.store.todos[f"A|{gone}|x"] = {"done": ""}
    n = b.auction_delete([gone])
    check("경매 사건 삭제 → 결과 파일·할 일·조회 기록에서도",
          n == 1 and gone not in au.items and not os.path.exists(os.path.join(au.root, "auction", gone + ".json"))
          and f"A|{gone}|x" not in b.store.todos and not any(gone in x["ids"] for x in au.runs))
    check("삭제 전 자동 백업", b.store.backups())

    print("v1.3 개선")
    g3 = json.loads(json.dumps(got2))
    g3["docs"]["dlt_dlvrDtsLst"].append({"dlvrbkRegYmd": dt.date.today().strftime("%Y%m%d"), "dlvrDts": "임차인 이OO 매각기일통지서 발송", "lastDlvrblRchYmd": "폐문부재"})
    au.record(aid, g3)
    h = b.home()
    au_items = [i for i in h["items"] if i.get("auction")]
    check("경매 할 일이 확인할 것에 (새 문건·송달 안 됨·매각기일)", {"경매 새 문건", "경매 송달 안 됨"} <= {i["kind"] for i in au_items},
          str({i["kind"] for i in au_items}))
    k0 = au_items[0]["key"]
    b.todo_done(k0, "경매 메모")
    check("경매 할 일 처리 → 숨김 + 경매 사건 메모", not any(i["key"] == k0 and not i["done"] for i in b.home()["items"])
          and au.items[k0.split("|")[1]].get("memos"))
    check("처리한 것 보기", any(i["key"] == k0 for i in b.home(show_done=True)["items"]))
    # 소송 연결: 하이픈 무시 + 관련사건 번호
    c1 = list(b.store.active_cases())[0]
    c1["memo1"] = "110-77-1234"
    au.items[aid]["memo1"] = "110 77 1234"
    rel = au.items[r["ids"][1]]
    rel["related_nos"] = [b.store.case_no(c1)]
    links = {x["id"]: x["linked"] for x in b.auction_list()}
    check("소송 연결: 메모 하이픈 무시", any(l["cid"] == c1["id"] for l in links[aid]))
    check("소송 연결: 관련사건 번호", any(l["cid"] == c1["id"] and l["why"] == "관련사건" for l in links[r["ids"][1]]))
    # 경매 조회 기록 · 이어서
    fw.caps = lambda tabs: caps_for(tabs, got)
    st = b.auction_start([aid, r["ids"][1], r["ids"][2]])
    rid = b.asess["rid"]
    b.auction_state(); b.auction_state()
    b.auction_stop()
    runs = b.auction_runs()
    check("경매 조회 기록 남음", runs[0]["id"] == rid and runs[0]["done"] == 1 and not runs[0]["finished"], str(runs[0]))
    st = b.auction_start(rid=rid)
    check("멈춘 경매 조회 이어서 (남은 2건)", st["total"] == 2 and st["done"] and b.asess["rid"] == rid, str((st["total"], len(st["done"]))))
    b.auction_stop()
    # 설정 판 번호
    check("설정 판 번호 (마지막 판까지 올라감 · 첫 화면은 현황 콘솔)", b.store.settings.get("_schema") == b.SETTINGS_SCHEMA[-1][0] and b.store.settings["todo"].get("start") == "console")
    from appbase import lock_check, newer_version
    check("자료 폴더 사용 표시 (같은 PC는 경고 없음)", lock_check(b.data_dir) is None)
    import time as _t
    json.dump({"host": "다른PC", "pid": 1, "at": _t.time()}, open(os.path.join(b.data_dir, "사용중.txt"), "w", encoding="utf-8"))
    check("다른 PC가 쓰는 중이면 알림", (lock_check(b.data_dir) or {}).get("host") == "다른PC")
    os.remove(os.path.join(b.data_dir, "사용중.txt"))
    upd = os.path.join(tmp, "배포")
    os.makedirs(upd)
    open(os.path.join(upd, "사건조회도우미_v9.9.0.zip"), "w").close()
    open(os.path.join(upd, "사건조회도우미_v1.0.0.zip"), "w").close()
    check("새 판 알림", newer_version(upd, "1.3.0")[0] == "9.9.0" and newer_version(upd, "9.9.0") is None)

    b.book_add("경매 채권 2")
    check("채권 바꾸면 경매 목록도 따로", not b.auction_list())
    b.book_switch(first)

    print("설정")
    new = [dict(r) for r in s["rules"]]
    new.insert(0, {"id": "r_t", "words": ["송달"], "status": "시험", "color": "red", "todo": False, "days": 0, "ask": False, "skip": False})
    ch = b.rules_preview(new)
    check("규칙 바꾸기 전 영향 수", len(ch) > 0)
    b.rules_save(new)
    check("규칙 저장", b.store.settings["rules"][0]["id"] == "r_t")
    b.settings_undo(0)
    check("설정 되돌리기", b.store.settings["rules"][0]["id"] != "r_t")
    name = b.backup_now()
    check("백업", name in b.backups())

    print("조회 결과가 법원 화면과 같게 (v1.14.2)")
    st = b.store
    c = st.add_case({"court": "서울중앙지방법원", "court_code": b.meta.court("서울중앙지방법원")["code"], "year": 2025, "dvs": "가소",
                     "serial": "777001", "party": "홍길동"})
    r1 = [{"progYmd": "20250301", "progCtt": "소장접수", "progRslt": ""},
          {"progYmd": "20250310", "progCtt": "피고 소장부본 송달", "progRslt": ""}]
    st.record(c["id"], "t1", {"basic": {"csNo": "x"}, "lists": {"dlt_rcntDxdyLst": [{"dxdyYmd": "20250501"}]}, "prog": r1})
    # 송달 결과가 나중에 채워지고, 법원이 줄 하나를 고침
    r2 = [{"progYmd": "20250301", "progCtt": "소장접수", "progRslt": ""},
          {"progYmd": "20250310", "progCtt": "피고 소장부본 송달", "progRslt": "2025.03.14 도달"},
          {"progYmd": "20250320", "progCtt": "변론기일 지정", "progRslt": ""}]
    new, res = st.record(c["id"], "t2", {"basic": {"csNo": "x"}, "lists": {}, "prog": r2})
    texts = [(r["progCtt"], r["progRslt"]) for r in res["prog"]]
    check("진행 = 법원이 지금 보여 주는 줄 그대로 (송달 결과 채워진 줄이 두 줄로 남지 않음)", len(res["prog"]) == 3 and ("피고 소장부본 송달", "") not in texts, texts)
    check("새로 생기거나 바뀐 줄만 '새 진행'", new == 2, new)
    check("처음 본 때는 같은 줄끼리 이어 감", next(r for r in res["prog"] if r["progCtt"] == "소장접수")["_first"] is True)
    check("기일 목록이 비면 비움", res["lists"] == {})
    new, res = st.record(c["id"], "t3", {"basic": {"csNo": "x"}, "lists": {}, "prog": [], "prog_error": "진행내용을 받지 못했습니다"})
    check("진행을 못 받으면 예전 줄 그대로", len(res["prog"]) == 3 and new == 0)
    # 사건번호를 고치면 예전 사건 결과가 섞이지 않게
    cid2 = b.case_save({"id": c["id"], "court": "서울중앙지방법원", "case_no": "2025가소777002", "party": "홍길동"})
    check("사건번호 고치면 예전 진행 비움", cid2 == c["id"] and st.result(c["id"])["prog"] == [] and not st.cases[c["id"]].get("status"))
    b.case_save({"id": c["id"], "court": "서울중앙지방법원", "case_no": "2025가소777002", "party": "홍길동2"})
    check("이름만 고치면 결과 그대로 둠", st.cases[c["id"]]["party"] == "홍길동2")
    other = st.add_case({"court": "서울중앙지방법원", "court_code": c["court_code"], "year": 2025, "dvs": "가소", "serial": "777003", "party": "김철수"})
    try:
        b.case_save({"id": c["id"], "court": "서울중앙지방법원", "case_no": "2025가소777003", "party": "홍길동"})
        check("다른 사건과 같은 번호로 고치면 막음", False)
    except ValueError:
        check("다른 사건과 같은 번호로 고치면 막음", True)
    st.cases.pop(other["id"], None)
    # 화면의 사건과 조회할 사건이 다르면 조회하지 않음
    sess_ids = [cid for cid, x in list(st.cases.items()) if not x.get("archived")][:2]
    b.run_start(name="t", case_ids=sess_ids)
    s0 = b.run_state(fetch=True)
    wrong = sess_ids[1] if s0["case"]["cid"] == sess_ids[0] else sess_ids[0]
    s1 = b.run_submit("123456", cid=wrong)
    check("화면 사건과 다르면 조회 안 하고 다시 보여 줌", s1["case"]["cid"] == s0["case"]["cid"] and (s1.get("message") or {}).get("kind") == "retry")
    s2 = b.run_submit("123456", cid=s0["case"]["cid"])
    check("같으면 조회함", (s2.get("last") or {}).get("kind") in ("ok", "notfound"))
    b.run_stop()

    print(f"\n정상 {ok} · 문제 {fail}")
    return fail == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
