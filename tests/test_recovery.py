# -*- coding: utf-8 -*-
"""회수 분석 — 공통 양식 v2 읽기·검사·저장 점검.  python tests/test_recovery.py"""
import datetime as dt
import gzip
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
from core import recovery as RC  # noqa: E402

D = RC.day_of


def book(path, sheets, ver="v2"):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "00_안내"
    ws.append(["공통양식", ver])
    for name, rows in sheets.items():
        s = wb.create_sheet(name)
        s.append([h for h, _, _ in RC.SHEETS[name]] if not isinstance(rows, tuple) else rows[0])
        for r in (rows if not isinstance(rows, tuple) else rows[1]):
            s.append(r)
    wb.save(path)
    return path


BASE = {
    "01_채권": [
        RC.EXAMPLE["01_채권"],  # 2줄 예시 → 건너뜀
        ["D1", "A1", "다O라", "김담당", "99-Z", 3_000_000, 2_000_000, 0, "2027-01-10", "800315-1", "2026-11-01"],
        ["D1", "A2", "다O라", "김담당", "99-Z", "1,500,000", None, None, "2026.12.31", "", "2026-11-01"],
        ["D2", "A3", "너O더", "이담당", "99-Z", 900_000, None, None, None, "020101-4", "2026-11-01"],
        ["D3", "A4", "러O머", "", "", "많음", None, None, None, None, None],  # 잔액 못 읽음 → 오류 줄
    ],
    "02_법조치": [
        ["L1", "D1", "A1", "지급명령", "전자독촉", "", "", "2024-01-05", "2024-03-02", "", "", ""],
        ["L2", "D1", "A1", "압류추심", "예금", "서울중앙지방법원", "2025타채1", 20250304, None, "2025-03-18", "", ""],
        ["L3", "D2", "", "압류추심", "급여", "", "", "2025-05-01", None, None, "", ""],
        ["L4", "D9", "", "소송", "", "", "", "2025-01-01", None, None, "", ""],  # 없는 채무자
        ["L2", "D1", "", "소송", "", "", "", "2025-01-01", None, None, "", ""],  # 겹친 키
    ],
    "03_제3채무자": [
        ["L2", "주식회사 국민은행", 1_000_000], ["L2", "NH농협은행", 1_000_000], ["L2", "하나증권", 500_000], ["L2", "알수없는금융", 300_000],
        ["L9", "신한은행", 100_000],
    ],
    "04_입금": [
        ["D1", "A1", "2025-05-02", 412_000, "추심금", "국민은행", "L2"],
        ["D1", "", "2025-06-02", 100_000, "추심금", "농협", ""],
        ["D2", "", "2025-07-01", 50_000, "본인변제", "", ""],
        ["D2", "", "2025-07-01", 50_000, "현금", "", ""],  # 코드표 밖 → 기타
        ["D7", "", "2025-07-01", 50_000, "본인변제", "", ""],  # 없는 채무자
    ],
    "05_조정": [["D2", "", "분납", "2025-06-01", "2025-06-25", 10, 50_000, 500_000, "진행"]],
    "06_해제": [["L2", "D1", "", "2025-09-10", "분납 약정 체결로 해제", ""], ["L3", "D2", "", "2025-09-10", "팀장 지시", ""]],
    "07_전자추심": [["", "D1", "", "국민은행", "2025-04-02", 1_000_000], ["L2", "", "", "주식회사 농협은행", "2025-04-03", 1_000_000]],
}


class TestValues(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(RC.parse_date("2026-03-15"), D(dt.date(2026, 3, 15)))
        self.assertEqual(RC.parse_date("2026.3.5"), D(dt.date(2026, 3, 5)))
        self.assertEqual(RC.parse_date(20260315), D(dt.date(2026, 3, 15)))
        self.assertEqual(RC.parse_date("2026년 3월 5일"), D(dt.date(2026, 3, 5)))
        self.assertEqual(RC.parse_date(46096), D(dt.date(2026, 3, 15)))  # 엑셀 날짜 숫자
        self.assertIsNone(RC.parse_date(""))
        self.assertIs(RC.parse_date("어제"), False)
        self.assertIs(RC.parse_date("2026-02-30"), False)

    def test_amounts(self):
        self.assertEqual(RC.parse_amt("1,234,000원"), 1234000)
        self.assertEqual(RC.parse_amt("(5,000)"), -5000)
        self.assertEqual(RC.parse_amt(-300.4), -300)
        self.assertIs(RC.parse_amt("많음"), False)

    def test_rrn(self):
        asof = dt.date(2026, 11, 1)
        self.assertEqual(RC.age_sex("800315-1", asof), ("40대", "남"))
        self.assertEqual(RC.age_sex("0201014", asof), ("20대", "여"))
        self.assertEqual(RC.age_sex("601231-2", asof), ("60대 이상", "여"))
        self.assertEqual(RC.age_sex("abc", asof), ("모름", "모름"))

    def test_banks(self):
        self.assertEqual(RC.bank_name("주식회사 국민은행")[0], "국민은행")
        self.assertEqual(RC.bank_name("KB국민")[0], "국민은행")
        self.assertEqual(RC.bank_name("NH농협")[0], "농협은행")
        self.assertEqual(RC.bank_name("(주)하나증권"), ("하나증권", True))  # 증권은 은행 규칙에 넣지 않음
        self.assertEqual(RC.bank_name("중소기업은행")[0], "IBK기업은행")
        self.assertFalse(RC.bank_name("알수없는금융")[1])

    def test_types(self):
        self.assertEqual(RC.act_type("압류추심", "예금"), "예금 압류추심")
        self.assertEqual(RC.act_type("압류추심", "보험"), "기타 압류추심")
        self.assertEqual(RC.act_type("경매", "부동산임의경매"), "부동산 경매")
        self.assertEqual(RC.act_type("무엇", ""), "기타")


class TestParse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def parse(self, sheets, **kw):
        return RC.parse(book(os.path.join(self.tmp, "t.xlsx"), sheets, **kw), today=dt.date(2026, 11, 21))

    def find(self, rep, level, sheet, text):
        return [x for x in rep["items"] if x["level"] == level and x["sheet"] == sheet and text in x["what"]]

    def test_full(self):
        data, rep = self.parse(BASE)
        self.assertTrue(rep["ok"])
        self.assertEqual(rep["asof"], "2026-11-01")
        self.assertEqual([d[0] for d in data["D"]], ["D1", "D2"])  # 예시·오류 줄 빠짐
        self.assertEqual(len(data["A"]), 3)
        self.assertEqual(data["A"][1][2], 1_500_000)
        self.assertEqual(data["D"][0][4:], ["40대", "남"])
        self.assertTrue(self.find(rep, "정보", "01_채권", "2줄 예시"))
        self.assertTrue(self.find(rep, "오류", "01_채권", "채권잔액"))
        # 법조치: 없는 채무자·겹친 키 빠짐, 날짜 숫자 읽음, 인용일 없는 압류추심 표시
        self.assertEqual([x[0] for x in data["L"]], ["L1", "L2", "L3"])
        self.assertEqual(data["L"][1][3], "예금 압류추심")
        self.assertEqual(data["L"][1][6], D(dt.date(2025, 3, 4)))
        self.assertEqual(data["L"][2][11], 1)
        self.assertTrue(self.find(rep, "주의", "02_법조치", "없는 채무자키"))
        self.assertTrue(self.find(rep, "주의", "02_법조치", "겹침"))
        # 제3채무자: 이름 맞춤, 없는 법조치 빠짐, 모르는 이름 알림
        self.assertEqual([b[1] for b in data["B"]], ["국민은행", "농협은행", "하나증권", "알수없는금융"])
        self.assertTrue(self.find(rep, "정보", "03_제3채무자", "알수없는금융"))
        # 입금: 코드 밖 → 기타, 은행 이름 맞춤
        kinds = [data["PK"][p[3]] for p in data["P"]]
        self.assertEqual(kinds, ["추심금", "추심금", "본인변제", "기타"])
        self.assertEqual(data["PB"][data["P"][1][4]], "농협은행")
        self.assertEqual(data["P"][0][5], 1)  # L2
        # 해제: 규칙으로 나눔 + 모름
        self.assertEqual([r[4] for r in data["R"]], ["약정·분납", "모름"])
        # 전자추심: 채무자키만 있어도 됨, 이름 맞춤
        self.assertEqual([(e[0], e[2]) for e in data["E"]], [(-1, "국민은행"), (1, "농협은행")])
        self.assertEqual(rep["counts"]["채무자"], 2)

    def test_full_rrn_dropped(self):
        sh = dict(BASE)
        sh["01_채권"] = [["D1", "A1", "", "", "", 1000, None, None, None, "800315-1234567", None]]
        sh["02_법조치"] = [["L1", "D1", "", "지급명령", "", "", "", "2025-01-01", None, None, "", ""]]
        data, rep = self.parse({k: sh[k] for k in ("01_채권", "02_법조치")})
        self.assertTrue(self.find(rep, "오류", "01_채권", "13자리"))
        self.assertEqual(data["D"][0][4:], ["모름", "모름"])
        self.assertNotIn("1234567", json.dumps(data, ensure_ascii=False))

    def test_missing_required(self):
        _, rep = self.parse({"01_채권": (["채무자키", "채권잔액"], [["D1", 100]]), "02_법조치": BASE["02_법조치"]})
        self.assertFalse(rep["ok"])
        self.assertTrue(self.find(rep, "오류", "01_채권", "계좌키"))

    def test_no_marker_and_short_names(self):
        from openpyxl import Workbook
        wb = Workbook()
        wb.active.title = "채권"
        wb.active.append([h for h, _, _ in RC.SHEETS["01_채권"]])
        wb.active.append(["D1", "A1", "", "", "", 1000])
        s = wb.create_sheet("법조치")
        s.append([h for h, _, _ in RC.SHEETS["02_법조치"]])
        s.append(["L1", "D1", "", "소송", "", "", "", "2025-01-01"])
        p = os.path.join(self.tmp, "n.xlsx")
        wb.save(p)
        data, rep = RC.parse(p, today=dt.date(2026, 11, 21))
        self.assertTrue(rep["ok"])
        self.assertTrue(self.find(rep, "주의", "00_안내", "v2"))
        self.assertEqual(data["asof"], D(dt.date(2025, 1, 1)))  # 기준일 없으면 가장 늦은 날짜

    def test_store_roundtrip(self):
        data, rep = self.parse(BASE)
        st = RC.RecoveryStore(self.tmp)
        self.assertFalse(st.has())
        st.save_data(data, {"at": "x", "file": "t.xlsx", "counts": rep["counts"]})
        st.save_data(data, {"at": "y", "file": "t2.xlsx", "counts": rep["counts"]})
        st2 = RC.RecoveryStore(self.tmp)
        self.assertEqual(json.loads(st2.blob())["D"], data["D"])
        self.assertEqual([h["file"] for h in st2.history()], ["t2.xlsx", "t.xlsx"])
        self.assertTrue(any(f.startswith("data_") for f in os.listdir(os.path.join(self.tmp, "recovery", "backup"))))
        with gzip.open(os.path.join(self.tmp, "recovery", "data.json.gz"), "rt", encoding="utf-8") as f:
            self.assertEqual(json.load(f)["v"], RC.VERSION)
        st2.save_state({"decisions": [1]})
        st2.save_state({"decisions": [2]}, demo=True)
        self.assertEqual(st2.state()["decisions"], [1])
        self.assertEqual(st2.state(demo=True)["decisions"], [2])
        st2.clear()
        self.assertFalse(st2.has())
        self.assertIsNone(st2.blob())

    def test_report_and_sample(self):
        data, rep = self.parse(BASE)
        out = RC.write_report(os.path.join(self.tmp, "r.xlsx"), rep, "t.xlsx")
        from openpyxl import load_workbook
        ws = load_workbook(out)["점검표"]
        self.assertEqual(ws["A5"].value, "구분")
        # 예시 파일 → 다시 읽으면 같은 건수
        p = RC.write_template_rows(os.path.join(self.tmp, "s.xlsx"), {k: v for k, v in BASE.items()})
        data2, rep2 = RC.parse(p, today=dt.date(2026, 11, 21))
        self.assertEqual(rep2["counts"], rep["counts"])


class TestRawMap(unittest.TestCase):
    """채권마다 다른 원자료 → 칸·값 맞추기 → 담아 두기 → 넣기"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def raw_book(self, name, sheets):
        from openpyxl import Workbook
        wb = Workbook()
        wb.remove(wb.active)
        for sh, rows in sheets.items():
            ws = wb.create_sheet(sh)
            for r in rows:
                ws.append(r)
        p = os.path.join(self.tmp, name)
        wb.save(p)
        return p

    def test_guess_and_values(self):
        from core import rawmap as RM
        self.assertEqual(RM.guess_cols("04_입금", ["차주번호", "수납일자", "수납액", "수납구분", "비고"]),
                         {"채무자키": 0, "입금일": 1, "입금액": 2, "입금구분": 3})
        self.assertEqual(RM.guess_sheet("입금내역", ["차주번호", "수납일자", "수납액", "수납구분"])[0], "04_입금")
        self.assertEqual(RM.guess_sheet("법적조치", ["조치번호", "차주번호", "조치구분", "신청일자", "결정일자", "제3채무자구분"])[0], "02_법조치")
        self.assertEqual(RM.suggest_value("입금구분", "가상계좌입금"), ("본인변제", "auto"))
        self.assertEqual(RM.suggest_value("입금구분", "추심입금"), ("추심금", "auto"))
        self.assertEqual(RM.suggest_value("법조치구분", "채권가압류"), ("가압류", "auto"))
        self.assertEqual(RM.suggest_value("법조치구분", "채권압류및추심명령"), ("압류추심", "auto"))
        self.assertEqual(RM.suggest_value("법조치구분", "지급명령"), ("지급명령", "same"))
        self.assertEqual(RM.suggest_value("채무조정상태", "개시결정"), ("진행", "auto"))
        self.assertEqual(RM.suggest_value("입금구분", "???")[1], "")
        self.assertEqual(RM.header_row([["입금 내역 (2026.11)", None], [None, None], ["차주번호", "수납일자", "수납액"], ["D1", "2026-01-01", 100]]), 2)

    def test_stage_apply_and_remember(self):
        from bridge import Bridge
        b = Bridge(os.path.join(self.tmp, "data"))
        b.store.settings["save"]["export_dir"] = os.path.join(self.tmp, "out")
        f1 = self.raw_book("채권A_원자료.xlsx", {
            "채권목록": [["채권 목록 (추출 2026-11-01)"], [], ["차주번호", "대출번호", "고객명", "총잔액", "시효만료일", "기준일자"],
                     ["D1", "A1", "다O라", 3000000, "2027-01-10", "2026-11-01"], ["D2", "A2", "너O더", 900000, "", "2026-11-01"]],
            "법적조치": [["조치번호", "차주번호", "조치구분", "세부구분", "신청일자", "결정일자", "확정일", "제3채무자구분"],
                     ["L1", "D1", "지급명령", "전자독촉", "2024-01-05", "", "2024-03-02", ""],
                     ["L2", "D1", "채권압류및추심명령", "예금", "2025-03-04", "2025-03-18", "", "예금+세무서"],
                     ["L3", "D2", "채권압류및추심명령", "예금채권", "2025-05-01", "2025-05-10", "", "예금"]],
            "수납": [["차주번호", "수납일자", "수납액", "수납구분", "추심은행"],
                   ["D1", "2025-05-02", 412000, "추심입금", "국민"], ["D2", "2025-07-01", 50000, "가상계좌입금", ""], ["D2", "2025-08-01", 50000, "특이입금", ""]],
        })
        o = b.rc_raw_open(f1)
        self.assertFalse(o["template"])
        kinds = {x["name"]: x["kind"] for x in o["sheets"]}
        self.assertEqual(kinds, {"채권목록": "01_채권", "법적조치": "02_법조치", "수납": "04_입금"})
        sh = {x["name"]: x for x in o["sheets"]}
        self.assertEqual(sh["채권목록"]["hi"], 2)
        vals = b.rc_raw_values(f1, "수납", "04_입금", sh["수납"]["cols"])
        v = {x["raw"]: (x["code"], x["how"]) for x in vals[0]["values"]}
        self.assertEqual(v["추심입금"], ("추심금", "auto"))
        self.assertEqual(v["특이입금"][0], "본인변제")  # 「입금」 낱말
        items = [{"sheet": n, "kind": sh[n]["kind"], "cols": sh[n]["cols"], "values": {}} for n in sh]
        items[2]["values"] = {"입금구분": {"특이입금": "제3자"}}
        st = b.rc_raw_stage(f1, items)
        self.assertEqual([k["kind"] for k in st["kinds"] if k.get("n")], ["01_채권", "02_법조치", "04_입금"])
        rep = st["report"]
        self.assertTrue(rep["ok"], rep["items"])
        self.assertEqual(rep["counts"]["법조치"], 3)
        info = b.rc_apply_staged()
        data = json.loads(b.rc_load(0)["s"])
        self.assertEqual([x[3] for x in data["L"]], ["지급명령", "예금 압류추심", "예금 압류추심"])  # 「예금채권」 → 예금
        self.assertEqual(data["L"][1][12], "예금+세무서")
        self.assertEqual([data["PK"][p[3]] for p in data["P"]], ["추심금", "본인변제", "제3자"])
        self.assertEqual(info["counts"]["채무자"], 2)
        # 기억: 같은 머리글의 다음 달 파일은 그대로 채워짐
        f2 = self.raw_book("채권A_12월.xlsx", {"수납": [["차주번호", "수납일자", "수납액", "수납구분", "추심은행"], ["D1", "2025-12-02", 1000, "특이입금", ""]]})
        o2 = b.rc_raw_open(f2)
        self.assertTrue(o2["sheets"][0]["saved"])
        v2 = b.rc_raw_values(f2, "수납", "04_입금", o2["sheets"][0]["cols"])
        self.assertEqual(v2[0]["values"][0]["how"], "saved")
        self.assertEqual(v2[0]["values"][0]["code"], "제3자")
        self.assertEqual(b.rc_maps()["values"]["입금구분"], 1)
        b.rc_unstage("04_입금")
        self.assertNotIn("n", [k for k in b.rc_staged()["kinds"] if k["kind"] == "04_입금"][0])

    def test_template_and_adjust(self):
        from bridge import Bridge
        b = Bridge(os.path.join(self.tmp, "d2"))
        sh = dict(BASE)
        sh["08_채무조정"] = [["D1", "개인회생", "2024-01-01", "폐지", "2025-06-10"], ["D2", "신복", "2024-01-01", "실효", "2025-07-01"]]
        p = book(os.path.join(self.tmp, "t.xlsx"), sh)
        o = b.rc_raw_open(p)
        self.assertTrue(o["template"])
        items = [{"sheet": x["name"], "kind": x["kind"], "cols": x["cols"], "values": {}} for x in o["sheets"]]
        st = b.rc_raw_stage(p, items)
        self.assertTrue(st["report"]["ok"])
        b.rc_apply_staged()
        data = json.loads(b.rc_load(0)["s"])
        self.assertEqual([(x[1], x[3]) for x in data["X"]], [("개인회생", "폐지"), ("신용회복", "실효")])


class TestBridge(unittest.TestCase):
    def test_bridge_calls(self):
        os.environ.setdefault("LOCALAPPDATA", tempfile.mkdtemp())
        from bridge import Bridge
        tmp = tempfile.mkdtemp()
        b = Bridge(tmp)
        b.store.settings["save"]["export_dir"] = os.path.join(tmp, "out")
        self.assertFalse(b.rc_info()["has"])
        self.assertIsNone(b.rc_load())
        p = book(os.path.join(tmp, "in.xlsx"), BASE)
        rep = b.rc_check(p)
        self.assertTrue(rep["ok"])
        info = b.rc_apply(p)
        self.assertEqual(info["counts"]["법조치"], 3)
        i = b.rc_info()
        self.assertTrue(i["has"])
        self.assertEqual(i["last"]["file"], "in.xlsx")
        part = b.rc_load(0)
        self.assertEqual(part["n"], 1)
        self.assertEqual(json.loads(part["s"])["asof"], RC.day_of(dt.date(2026, 11, 1)))
        out = b.rc_save_table("다음 법조치_261121.csv", ["가", "나"], [[1, "x"], [2, None]])
        self.assertTrue(out.endswith(".xlsx") and os.path.isfile(out))
        self.assertTrue(os.path.isfile(b.rc_report(p)))
        b.rc_state_save({"relMap": {"a": "모름"}})
        self.assertEqual(b.rc_state()["relMap"], {"a": "모름"})
        with self.assertRaises(ValueError):
            b.rc_check(os.path.join(tmp, "없음.xlsx"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
