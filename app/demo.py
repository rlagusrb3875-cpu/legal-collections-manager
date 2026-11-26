# -*- coding: utf-8 -*-
"""화면 점검용: 법원 사이트 대신 꾸며 낸 결과를 돌려준다. (배포본에는 넣지 않음)

숫자 000000 → '숫자 틀림', 당사자 이름에 '없음' → '찾을 수 없음'.
"""
import base64
import datetime as dt
import random

from core import rules
from core.site import SiteError

NAMES = ["홍길동", "윤서아", "문가은", "강민재", "김영", "오하늘", "서지우", "한도윤", "이지훈", "정수빈", "박철수", "최민수",
         "주식회사 대한상사", "장하늘", "임도현", "배수진", "송지민", "권태윤", "조은별", "유하준"]
COURTS = [("서울중앙지방법원", "000210"), ("서울북부지방법원", "000213"), ("인천지방법원", "000240"), ("수원지방법원", "000250"),
          ("부산지방법원", "000410"), ("대전지방법원", "000280"), ("성남지원", "000251")]
KINDS = [("가소", "대여금"), ("가소", "양수금"), ("가단", "구상금"), ("차전", "지급명령"), ("가소", "물품대금")]


def _svg(text):
    s = "".join(f'<text x="{14 + i * 17}" y="{28 + random.randint(-3, 3)}" font-family="Georgia" font-style="italic" '
                f'font-weight="700" font-size="24" fill="#333" transform="rotate({random.randint(-14, 14)} {20 + i * 17} 20)">{d}</text>'
                for i, d in enumerate(text))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="40"><rect width="120" height="40" fill="#f4f4f4"/>{s}'
           f'<path d="M2 {random.randint(14, 26)} C 40 {random.randint(0, 40)}, 80 {random.randint(0, 40)}, 118 {random.randint(14, 26)}" '
           'stroke="#333" stroke-width="1.4" fill="none"/></svg>')
    return base64.b64encode(svg.encode()).decode()


class FakeCourt:
    def __init__(self, meta):
        self.meta = meta

    def captcha(self):
        t = "".join(random.choice("0123456789") for _ in range(6))
        return {"image": _svg(t), "mime": "image/svg+xml", "audio": "", "token": "demo", "at": 0}

    def get_text(self, path):
        raise SiteError("network", "시연 모드에서는 법원 사이트에 접속하지 않아요")

    def resolve(self, case):
        return None, None, "CV"

    def search(self, case, answer, token, party=None):
        if str(answer).strip() == "000000":
            raise SiteError("captcha", "자동입력방지문자가 일치하지 않습니다.")
        name = party if party is not None else case.get("party", "")
        if "없음" in name:
            raise SiteError("notfound", "해당 사건이 존재하지 않습니다.")
        if case.get("dvs") == "타배":
            return fake_dividend(case)
        return fake_result(case, extra=random.random() < 0.3)


def fake_result(case, extra=False, seed=None):
    rnd = random.Random(seed if seed is not None else hash((case["year"], case["dvs"], case["serial"])))
    today = dt.date.today()
    start = today - dt.timedelta(days=rnd.randint(60, 300))
    steps = [("소장접수", "")]
    if case["dvs"] in ("개회", "개확"):
        steps = [("개인회생 신청서 접수", ""), ("금지명령", ""), ("개시결정", ""), ("개인회생채권자집회기일", "속행"),
                 ("변제계획인가결정", ""), (rnd.choice(["면책결정", "폐지결정"]), "")]
    elif case["dvs"] in ("하단", "하면", "하합"):
        steps = [("파산신청서 접수", ""), ("파산선고", ""), ("면책신청서 접수", ""), ("면책심문기일", "속행"),
                 (rnd.choice(["면책결정", "면책불허가결정"]), "")]
    elif case["dvs"] == "차전":
        steps = [("지급명령신청서 접수", ""), ("지급명령정본 송달", rnd.choice(["도달", "송달불능(폐문부재)"]))]
    else:
        steps += [("소장부본 송달", rnd.choice(["도달", "도달", "송달불능(이사불명)"])), ("변론기일(제201호 법정 10:20)", "속행"),
                  ("판결선고", "원고승"), ("피고 판결정본 송달", "도달")]
    n = rnd.randint(1, len(steps))
    if extra:
        n = min(len(steps), n + 1)
    rows, d = [], start
    for i, (t, r) in enumerate(steps[:n]):
        d = min(today, d + dt.timedelta(days=rnd.randint(10, 50)))
        rows.append({"progYmd": d.strftime("%Y%m%d"), "progCtt": t, "progRslt": r})
    pick = rnd.random()
    if pick < 0.12:
        d = min(today, d + dt.timedelta(days=rnd.randint(1, 8)))
        rows.append({"progYmd": d.strftime("%Y%m%d"), "progCtt": "주소보정명령", "progRslt": ""})
    elif pick < 0.18:
        d = min(today, d + dt.timedelta(days=5))
        rows.append({"progYmd": d.strftime("%Y%m%d"), "progCtt": "확정", "progRslt": ""})
    rows.reverse()
    texts = [r["progCtt"] for r in rows]
    basic = {"csNo": f"{case['year']}{case['dvs']}{case['serial']}", "csNm": dict(KINDS).get(case["dvs"], "대여금"),
             "jdbnNm": f"민사{rnd.randint(1, 40)}단독", "csRcptYmd": start.strftime("%Y%m%d"),
             "rprsClmntNm": "주식회사 ○○캐피탈", "rprsAcsdNm": case.get("party", "")[:1] + "○○",
             "clmntVsml": f"{rnd.randint(2, 30) * 300000:,}", "stmpAtchAmt": f"{rnd.randint(10, 90) * 1000:,}"}
    if "판결선고" in texts:
        jd = next(r for r in rows if r["progCtt"] == "판결선고")["progYmd"]
        basic.update(csUltmtYmd=jd, csUltmtDvsNm="원고승")
        sent = next((r for r in rows if "판결정본" in r["progCtt"]), None)
        if sent:
            basic["lastAdjdocRchYmd"] = sent["progYmd"]
    if "확정" in texts:
        basic["csCfmtnYmd"] = rows[0]["progYmd"]
    lists = {"dlt_btprtCttLst": [{"btprtDvsNm": "원고", "btprtNm": "주식회사 ○○캐피탈"},
                                 {"btprtDvsNm": "피고", "btprtNm": basic["rprsAcsdNm"]}],
             "dlt_agntCttLst": [{"agntDvsNm": "원고 소송대리인", "agntNm": "변호사 김○○"}]}
    if rnd.random() < 0.35 and "확정" not in texts:
        hd = today + dt.timedelta(days=rnd.randint(1, 40))
        lists["dlt_rcntDxdyLst"] = [{"dxdyYmd": hd.strftime("%Y%m%d"), "dxdyHm": rnd.choice(["1000", "1030", "1400", "1520"]),
                                     "dxdyKndNm": rnd.choice(["변론기일", "변론기일", "선고기일"]),
                                     "dxdyPlcNm": f"제{rnd.randint(2, 5)}0{rnd.randint(1, 9)}호 법정", "dxdyRsltNm": ""}]
    return {"task": "CV", "court_code": "", "dvs_code": "", "basic": basic, "lists": lists, "prog": rows, "prog_error": ""}


def install(bridge):
    """시연용 자료를 채우고 법원 사이트 대신 FakeCourt 를 쓰게 한다."""
    bridge.court = FakeCourt(bridge.meta)
    bridge.demo = True  # 회수 분석: 넣은 자료가 없으면 예시 자료로
    s = bridge.store
    if s.cases:
        install_auction(bridge)
        install_legal(bridge)
        install_forms(bridge)
        install_dividend(bridge)
        return
    rnd = random.Random(7)
    for i in range(40):
        court, code = COURTS[i % len(COURTS)]
        dvs, _ = KINDS[i % len(KINDS)]
        c = s.add_case({"court": court, "court_code": code, "year": rnd.choice([2024, 2025, 2026]), "dvs": dvs,
                        "serial": str(rnd.randint(1000, 399999)), "party": NAMES[i % len(NAMES)],
                        "owner": rnd.choice(["김담당", "이담당"]), "memo1": f"{rnd.choice([110, 220, 301])}-{rnd.randint(10, 99)}-{rnd.randint(1000, 9999)}"})
        if i < 34:
            past = (dt.datetime.now() - dt.timedelta(days=rnd.randint(8, 20))).strftime("%Y-%m-%d %H:%M:%S")
            got = fake_result(c, seed=i)
            old = dict(got, prog=got["prog"][1:])
            s.record(c["id"], "seed", old)
            new, res = s.record(c["id"], "seed", got)
            c["last_checked"] = past
            c["last_result"] = "ok"
            c["new_count"] = new
            rules.refresh_case(s, c, res)
    s.cases[list(s.cases)[-1]]["last_result"] = "notfound"
    s.save_cases()
    run = s.new_run("정기 조회", [c for c in list(s.cases)[:34]])
    for it in run["items"]:
        it.update(state="done", sec=round(rnd.uniform(3, 6), 1), new=rnd.choice([0, 0, 1]))
    run["finished"] = (dt.datetime.now() - dt.timedelta(days=9)).strftime("%Y-%m-%d %H:%M:%S")
    run["elapsed"] = 512
    s.save_runs()
    install_auction(bridge)
    install_legal(bridge)
    install_forms(bridge)
    install_dividend(bridge)


def fake_auction(a, seed=0):
    """시연용 경매 결과 (화면이 받는 자료와 같은 모양)"""
    rnd = random.Random(seed)
    today = dt.date.today()
    rcpt = today - dt.timedelta(days=rnd.randint(200, 500))
    ev = rnd.randint(1, 6) * 50_000_000
    names = ["김OO", "이OO", "박OO", "주식회사 OO"]
    gnrl = {"ipcheck": True,
            "dma_csBasInf": {"cortOfcNm": a["court"], "userCsNo": a["case_no"], "csNm": rnd.choice(["부동산강제경매", "부동산임의경매"]),
                             "csRcptYmd": rcpt.strftime("%Y%m%d"), "csCmdcYmd": (rcpt + dt.timedelta(days=9)).strftime("%Y%m%d"),
                             "clmAmt": str(rnd.randint(10, 300) * 1_000_000), "cortAuctnJdbnNm": f"경매{rnd.randint(1, 12)}계",
                             "jdbnTelno": "530-1815", "execrCsTelno": "02-533-6852", "ultmtDvsCd": "000"},
            "dlt_dstrtDemnLstprdDts": [{"dspslObjctSeq": "1", "userSt": "서울특별시 관악구 관악로 227-6", "bldNm": "OO파크", "bldDtlDts": "1층101호",
                                        "dstrtDemnLstprdYmd": (rcpt + dt.timedelta(days=80)).strftime("%Y%m%d")}],
            "dlt_dspslGdsDspslObjctLst": [{"dspslGdsSeq": "1", "userSt": "서울특별시 관악구 관악로 227-6", "bldNm": "OO파크", "bldDtlDts": "1층101호",
                                           "aeeEvlAmt": str(ev), "fstPbancLwsDspslPrc": str(int(ev * 0.8)),
                                           "dspslDxdyYmd": (today + dt.timedelta(days=rnd.randint(3, 40))).strftime("%Y%m%d"), "fstDspslHm": "1000",
                                           "dspslGdsRmk": "일괄매각"}],
            "dlt_rletCsIntrpsLst": [{"auctnIntrpsDvsNm": "채권자", "intrpsNm": names[3]}, {"auctnIntrpsDvsNm": "채무자겸소유자", "intrpsNm": names[0]},
                                    {"auctnIntrpsDvsNm": "근저당권자", "intrpsNm": "OO은행"}, {"auctnIntrpsDvsNm": "임차인", "intrpsNm": names[1]},
                                    {"auctnIntrpsDvsNm": "교부권자", "intrpsNm": "서울특별시 관악구"}],
            "dlt_rletReltCsLst": [{"cortOfcNm": a["court"], "userReltCsNo": f"{a['year']}타경{int(a['serial']) + 7}", "reltCsDvsNm": "중복"}],
            "dlt_rletCsDspslObjctLst": [{"ultmtNm": "미종국"}]}
    d1 = today - dt.timedelta(days=rnd.randint(20, 60))
    d2 = today + dt.timedelta(days=rnd.randint(3, 40))
    fl = rnd.random() < 0.6
    dates = {"ipcheck": True, "dlt_dxdyDtsLst": [
        {"dspslGdsSeq": "1", "aeeEvlAmt": str(ev), "dxdyTime": d1.strftime("%Y.%m.%d") + "(10:00)", "auctnDxdyKndNm": "매각기일",
         "dxdyPlcNm": "제4별관 2층 211호 법정", "tsLwsDspslPrc": f"{ev:,}원", "dxdyRslt": "유찰" if fl else "변경"},
        {"dspslGdsSeq": "1", "aeeEvlAmt": str(ev), "dxdyTime": d2.strftime("%Y.%m.%d") + "(10:00)", "auctnDxdyKndNm": "매각기일",
         "dxdyPlcNm": "제4별관 2층 211호 법정", "tsLwsDspslPrc": f"{int(ev * (0.8 if fl else 1)):,}원", "dxdyRslt": ""}]}
    docs_txt = [(0, "채권자 주식회사 OO 경매신청서 제출"), (8, "등기소 OO등기소 등기필증 제출"), (25, "집행관 OOO 현황조사보고서 제출"),
                (40, "감정인 OO감정평가법인 감정평가서 제출"), (70, "근저당권자 OO은행 채권계산서 제출"), (75, "교부권자 서울특별시 관악구 교부청구서 제출"),
                (90, "임차인 이OO 권리신고 및 배당요구신청서 제출")]
    docs = [{"ofdocRcptYmd": (rcpt + dt.timedelta(days=k)).strftime("%Y%m%d"), "rcptDts": t, "rcptRslt": ""} for k, t in docs_txt]
    dlvr = [{"dlvrbkRegYmd": (rcpt + dt.timedelta(days=12)).strftime("%Y%m%d"), "dlvrDts": "채무자겸소유자 김OO 개시결정정본 발송",
             "lastDlvrblRchYmd": (rcpt + dt.timedelta(days=15)).strftime("%Y.%m.%d") + " 도달"},
            {"dlvrbkRegYmd": (rcpt + dt.timedelta(days=30)).strftime("%Y%m%d"), "dlvrDts": "임차인 이OO 배당요구종기 최고서 발송",
             "lastDlvrblRchYmd": "폐문부재"}]
    return {"gnrl": gnrl, "dates": dates, "docs": {"ipcheck": True, "dlt_ofdocDtsLst": docs, "dlt_dlvrDtsLst": dlvr}}


def install_auction(bridge):
    au = bridge.auct
    if au.items:
        return
    rnd = random.Random(3)
    picks = [("서울중앙지방법원", "B000210"), ("인천지방법원", "B000240"), ("수원지방법원", "B000250"), ("대전지방법원", "B000280"),
             ("부산지방법원", "B000410"), ("성남지원", "B000251")]
    memos = [c.get("memo1", "") for c in bridge.store.active_cases()][:6]
    for i, (court, code) in enumerate(picks):
        a, _ = au.add(court, code, rnd.choice([2024, 2025]), str(rnd.randint(1000, 99999)), memos[i] if i % 2 == 0 and i < len(memos) else "")
        got = fake_auction(a, seed=i)
        au.record(a["id"], got)
        if i < 2:  # 두 번째 조회에서 새 문건이 생긴 것처럼
            today = dt.date.today()
            got["docs"]["dlt_ofdocDtsLst"].append({"ofdocRcptYmd": (today - dt.timedelta(days=3)).strftime("%Y%m%d"),
                                                    "rcptDts": "채무자겸소유자 김OO 매각기일연기신청서 제출", "rcptRslt": ""})
            got["docs"]["dlt_dlvrDtsLst"].append({"dlvrbkRegYmd": (today - dt.timedelta(days=6)).strftime("%Y%m%d"),
                                                  "dlvrDts": "채무자겸소유자 김OO 매각및매각결정기일통지서 발송",
                                                  "lastDlvrblRchYmd": (today - dt.timedelta(days=4)).strftime("%Y.%m.%d") + " 도달"})
            au.record(a["id"], got)


def install_legal(bridge):
    """법조치 화면 점검용 가짜 원장 · 회생 · 서류 기록"""
    lg = bridge.legal
    if lg.debtors:
        return
    rnd = random.Random(11)
    today = dt.date.today()
    for c in list(bridge.store.cases.values())[:20]:
        if c["party"].startswith("주식회사"):
            continue
        lg.upsert_debtor({"name": c["party"], "key": c["memo1"], "birth": f"{rnd.randint(70, 99)}0{rnd.randint(1, 9)}1{rnd.randint(0, 9)}",
                          "principal": rnd.randint(30, 200) * 100000, "interest": rnd.randint(1, 30) * 10000, "rate": "15",
                          "addr": f"서울 ○○구 ○○로 {rnd.randint(1, 99)}", "default_date": "2025-03-15",
                          "sihyo": (today + dt.timedelta(days=rnd.randint(200, 900))).isoformat()})
    for i, n in enumerate(["구슬기", "남바다", "배하늘", "류하준", "신도윤", "장나래"]):
        lg.upsert_debtor({"name": n, "key": f"110-555-{i:04d}", "birth": f"8{i}0101", "principal": rnd.randint(30, 200) * 100000,
                          "interest": rnd.randint(1, 30) * 10000, "rate": "15", "default_date": "2025-02-15",
                          "addr": "" if n == "류하준" else f"경기 ○○시 ○○길 {i + 3}",
                          "sihyo": (today + dt.timedelta(days=40 if n == "구슬기" else 400 + i * 30)).isoformat()})
    ds = list(lg.debtors.values())
    d = ds[2]
    d["title_no"] = "서울중앙지방법원 2025차전 4411"
    d["assets"] = [{"id": "a1", "kind": "급여", "name": "(주)마바물산", "third": "주식회사 마바물산", "amt": 2900000, "amt2": 0, "src": "재산명시 목록", "at": "2026-10-05"},
                   {"id": "a2", "kind": "예금", "name": "가나은행", "third": "주식회사 가나은행", "amt": 2400000, "amt2": 0, "src": "재산조회 (금융기관)", "at": "2026-10-12"},
                   {"id": "a3", "kind": "예금", "name": "다라저축은행", "third": "다라저축은행", "amt": 1200000, "amt2": 0, "src": "재산조회 (금융기관)", "at": "2026-10-12"},
                   {"id": "a4", "kind": "보험", "name": "사사생명 보장성", "third": "사사생명보험 주식회사", "amt": 1400000, "amt2": 0, "src": "재산조회 (보험)", "at": "2026-10-12"},
                   {"id": "a5", "kind": "자동차", "name": "2014년식 승용차", "third": "", "amt": 2500000, "amt2": 1500000, "src": "재산조회 (자동차)", "at": "2026-10-12"}]
    d["stage"] = "확정"
    for x in range(14):
        lg.data["docs"].append({"at": (dt.datetime.now() - dt.timedelta(days=rnd.randint(0, 65))).strftime("%Y-%m-%d %H:%M:%S"),
                                "type": "지급명령", "did": "", "name": "", "file": ""})
    lg.save()
    bridge.store.set_setting("legal.creditor", {"name": "가나자산관리대부 주식회사", "addr": "서울 ○○구 ○○대로 100", "rep": "○○○", "phone": ""})
    bridge.lg_info_save({"cause": "양수금", "assignor": "가나캐피탈 주식회사", "assign_date": "2024-08-01", "notice_date": "2024-08-09", "contract_date": "2019-03-14"})
    bridge.lg_rehab_register({"did": ds[0]["id"], "doc": "개시결정", "kind": "개인회생", "no": "2026개회13579", "court": "서울회생법원",
                              "got": (today - dt.timedelta(days=4)).isoformat()})
    r = bridge.lg_rehab_register({"did": ds[4]["id"], "doc": "채권자목록 송달", "kind": "개인회생", "no": "2026개회3344", "court": "수원회생법원",
                                  "got": (today - dt.timedelta(days=20)).isoformat(), "due": (today + dt.timedelta(days=8)).isoformat(),
                                  "list_amt": 1000000})
    lg.data["rehab"][r]["stop_ok"] = "2026-10-20 10:00:00"
    r = bridge.lg_rehab_register({"did": ds[6]["id"], "doc": "개시결정", "kind": "개인회생", "no": "2025개회24680", "court": "서울회생법원",
                                  "got": "2025-11-03"})
    lg.data["rehab"][r].update(stage=5, paid=9, total=60, missed=2, stop_ok="2025-11-05 10:00:00")
    lg.save()
    # 회생·파산 사건: 사건 대장에 들어간 것에 시연 결과를 넣고, 몇 건 더
    from core import legal as L
    s = bridge.store
    for n, (court, code, no, who) in enumerate([("서울회생법원", "000221", "2026개회7781", ds[8]), ("수원회생법원", "000251", "2025하단4410", ds[9]),
                                                 ("부산회생법원", "000411", "2024개회30915", ds[10]), ("서울회생법원", "000221", "2025개회118", ds[11])]):
        try:
            bridge.case_save({"court": court, "case_no": no, "party": who["name"], "memo1": who.get("key", "")})
        except ValueError:
            pass
    for i, c in enumerate([c for c in s.active_cases() if L.rehab_kind(c.get("dvs"))]):
        if c.get("last_checked"):
            continue
        got = fake_result(c, seed=100 + i)
        _, res = s.record(c["id"], "seed", got)
        c["last_checked"] = (dt.datetime.now() - dt.timedelta(days=3 + i * 9)).strftime("%Y-%m-%d %H:%M:%S")
        c["last_result"] = "ok"
        rules.refresh_case(s, c, res)
    s.save_cases()
    bridge._rehab_sync()
    bridge._dlv_sync()
    for i, x in enumerate(list(lg.data["dlv"].values())[:3]):
        x["recv"] = (today - dt.timedelta(days=3 + i * 2)).isoformat()
    lg.save()


def install_forms(bridge, force=False):
    """회사 양식 화면 점검용: 견본 주소보정서 양식 (칸까지 정해 둠) + 검수에서 고칠 것이 보이는 송달 건"""
    if bridge._forms():
        return
    if not force:
        try:
            import pypdfium2  # noqa: F401  (PDF 부품이 없으면 건너뜀 — 시뮬레이션은 force로 따로 넣음)
            import reportlab  # noqa: F401
        except ImportError:
            return
    fid = bridge.fm_sample()
    bridge.fm_save(fid, {"fields": [f for f in bridge.fm_detect(fid)["fields"] if f.get("item")]})
    bridge.fm_fav(fid, True)
    bridge.fm_task("송달불능", fid)
    bridge.store.set_setting("legal.agent", "담당 김담당 (02-000-0000)")
    lg = bridge.legal
    by = {d["name"]: d for d in lg.debtors.values()}
    cases = [c for c in bridge.store.active_cases() if not c["dvs"].startswith(("개", "하", "회"))]
    other = next((c for c in cases if c.get("court") and c["court"] != "서울남부지방법원"), None)
    add = []
    if "구슬기" in by and other:  # 사건 대장과 법원이 다름 → 확인
        by["구슬기"]["court"] = "서울남부지방법원"
        add.append({"case_no": bridge.store.case_no(other), "did": by["구슬기"]["id"], "party": "구슬기", "reason": "이사불명"})
    if "남바다" in by:  # 법원을 모름 → 빈 칸
        add.append({"case_no": "2026가소40112", "did": by["남바다"]["id"], "party": "남바다", "reason": "폐문부재"})
    if "배하늘" in by:  # 사건번호 띄어쓰기 → 정리 + 이틀 전에 같은 서류 → 중복
        by["배하늘"]["court"] = "대전지방법원"
        add.append({"case_no": "2026 가소 5512", "did": by["배하늘"]["id"], "party": "배하늘", "reason": "수취인불명"})
        lg.data["docs"].insert(0, {"at": (dt.datetime.now() - dt.timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"), "type": "양식:주소보정서 (견본)",
                                   "form": fid, "ver": 1, "did": by["배하늘"]["id"], "name": "배하늘", "key": "2026가소5512", "file": ""})
    lg.save()
    for x in add:
        bridge.lg_dlv_add(x)


# ---------------------------------------------------------------- 배당기일 시연 자료

DV_SITE = {
    "부산지방법원|2026타배99004": ("(주)예시상사", [("부산지방법원", "2025타채99001"), ("부산지방법원", "2025타채13377")], 8),
    "서울남부지방법원|2026타배99005": ("(주)서진테크", [("서울남부지방법원", "2024타채99002"), ("서울중앙지방법원", "2025타채2031")], 24),
    "인천지방법원|2026타배99006": ("(주)대성물류", [("인천지방법원", "2024타채99003"), ("인천지방법원", "2024타채41020")], 10),
    "수원지방법원|2026타배99007": ("(주)한빛건설", [("수원지방법원", "2025타채1188")], 17),
    "의정부지방법원|2026타배99008": ("국민은행", [("의정부지방법원", "2025타채2234"), ("의정부지방법원", "2025타채2290")], 3),
    "대구지방법원|2026타배99009": ("(주)대경정밀", [("대구지방법원", "2025타채9001")], 36),
    "광주지방법원|2026타배99010": ("광주은행", [("광주지방법원", "2025타채4410")], None),
}
DV_CASES = "채무자\t법원\t사건번호\n가O나\t부산지방법원\t2026타배99004\n다O라\t서울남부지법\t2026 타배 99005\n차O카\t인천지방법원\t2026타배99006\n" \
           "다O라\t수원지방법원\t2026타배99007\n타O파\t의정부지방법원\t2026타배99008\n마O바\t대구지방법원\t2026타배99009\n하O거\t광주지방법원\t2026타배99010"
DV_LAW = """채무자키\t법조치키\t채무자명\t담당자명\t법원\t사건번호\t청구액
D-100231\tL-24-05521\t가O나\t김담당\t부산지방법원\t2025타채99001\t5200000
D-100232\tL-24-05522\t가O나\t김담당\t부산지방법원\t2025타채99001\t3100000
D-100877\tL-25-00341\t다O라\t이담당\t서울남부지방법원\t2024타채99002\t4400000
D-100877\tL-25-00342\t다O라\t이담당\t서울중앙지방법원\t2025타채2031\t
D-101540\tL-25-00660\t다O라\t이담당\t서울중앙지방법원\t2025타채2031\t2800000
D-102210\tL-24-03091\t차O카\t김담당\t인천지방법원\t2024타채99003\t6100000
D-102211\tL-24-04102\t차O카\t김담당\t인천지방법원\t2024타채41020\t
D-103300\tL-25-01188\t다O라\t김담당\t수원지방법원\t2025타채1188\t3900000
D-104455\tL-25-02234\t타O파\t이담당\t의정부지방법원\t2025타채2234\t2500000
D-104455\tL-25-02290\t타O파\t이담당\t의정부지방법원\t2025타채2290\t
D-105010\tL-25-09001\t마O바\t이담당\t대구지방법원\t2025타채9002\t1800000
D-106000\tL-25-04410\t하O거\t김담당\t광주지방법원\t2025타채4410\t2200000"""


def fake_dividend(case):
    key = f"{case['court']}|{case['year']}{case['dvs']}{case['serial']}"
    third, rel, days = DV_SITE.get(key, ("(주)○○상사", [(case["court"], f"{case['year'] - 1}타채{case['serial']}0")], 20))
    today = dt.date.today()
    lists = {"dlt_btprtCttLst": [{"btprtDvsNm": "공탁자(제3채무자)", "btprtNm": third}, {"btprtDvsNm": "채무자", "btprtNm": case.get("party", "")}],
             "dlt_reltCsLst": [{"cortNm": c, "reltCsNo": n, "reltCsDvsNm": "채권압류및추심명령"} for c, n in rel]}
    if days is not None:
        lists["dlt_rcntDxdyLst"] = [{"dxdyYmd": (today + dt.timedelta(days=days)).strftime("%Y%m%d"), "dxdyHm": "1000", "dxdyKndNm": "배당기일", "dxdyPlcNm": "제2호 법정"}]
    prog = [{"progYmd": (today - dt.timedelta(days=40)).strftime("%Y%m%d"), "progCtt": "공탁사유신고서 접수", "progRslt": ""}]
    return {"task": "CV", "court_code": "", "dvs_code": "", "basic": {"csNo": f"{case['year']}타배{case['serial']}", "csNm": "배당절차"},
            "lists": lists, "prog": prog, "prog_error": ""}


def install_dividend(bridge):
    """대장 과거 자료(2025-01~지난달)와 붙여넣기 예시를 채운다. 이미 있으면 그대로."""
    from core import dividend as DV
    st = bridge.dv
    if st.ledger:
        return
    rnd = random.Random(11)
    TH = ["국민은행", "신한은행", "농협은행", "우리은행", "하나은행", "기업은행", "(주)대성물류", "(주)한빛건설", "(주)서진테크", "(주)예시상사"]
    MG = ["김담당", "이담당", "박담당"]
    CT = ["서울중앙지방법원", "서울남부지방법원", "수원지방법원", "인천지방법원", "의정부지방법원", "부산지방법원", "대전지방법원"]
    today = dt.date.today()
    for i in range(110):
        d = today - dt.timedelta(days=rnd.randint(12, 650))
        claim = rnd.randint(10, 120) * 100000
        rate = rnd.uniform(.1, .9)
        none = rnd.random() < .1
        amt = 0 if none else int(round(claim * rate / 10000)) * 10000
        send = d + dt.timedelta(days=rnd.randint(2, 12))
        recv_d = send + dt.timedelta(days=rnd.randint(3, 18))
        pending = (today - d).days < 90 and rnd.random() < .3
        recv = "수령" if not pending or none else rnd.choice(["대기", "발송"])
        court = rnd.choice(CT)
        r = st.new_row({"dkey": f"D-{90000 + i * 7}", "lkey": f"L-{d.year % 100 - 1:02d}-{10000 + i}", "debtor": rnd.choice("김이박최정강조윤장임") + "O" + rnd.choice("민수영지현우진호"),
                        "mgr": rnd.choice(MG), "court": court, "no": f"{d.year}타배{100 + i * 13}", "date": d.isoformat(),
                        "ours": f"{court} {d.year - 1}타채{2000 + i * 31}", "third": rnd.choice(TH), "claim": claim, "check": "완료",
                        "amt": amt, "recv": recv, "send_at": send.isoformat() if recv != "대기" else "",
                        "recv_at": (d.isoformat() if none else recv_d.isoformat()) if recv == "수령" else ""}, "엑셀 가져옴 (배당관리.xlsx · 시연)")
        r["fresh"] = False
        r["check_by"] = r["mgr"]
        DV.DividendStore.log(r, "엑셀에서 가져옴 (시연)", "시연")
    st.data["search"] = {"text": DV_CASES, "items": [], "rid": "", "del": [], "order": [], "matched": None, "mdel": [], "morder": []}
    st.data["law"] = {"text": DV_LAW, "rows": [], "src": "", "at": ""}
    st.save()
    bridge.dv_law_text(DV_LAW)
