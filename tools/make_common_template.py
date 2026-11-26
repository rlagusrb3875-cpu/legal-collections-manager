# 공통 양식 v2 엑셀 만들기: python tools/make_common_template.py 법조치회수분석_공통양식_v2.xlsx  (openpyxl 필요)
import sys
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.comments import Comment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

OUT = sys.argv[1]
F = "맑은 고딕"
fb = Font(name=F, size=10); fbb = Font(name=F, size=10, bold=True)
fh = Font(name=F, size=10, bold=True, color="FFFFFF"); ft = Font(name=F, size=14, bold=True)
fex = Font(name=F, size=10, italic=True, color="808080"); fsm = Font(name=F, size=9, color="808080")
REQ = PatternFill("solid", fgColor="141414"); OPT = PatternFill("solid", fgColor="6B6B70")
CODE = PatternFill("solid", fgColor="365ABD"); NOTE = PatternFill("solid", fgColor="F4F4F3")
th = Side(style="thin", color="D6D6D3"); BD = Border(top=th, bottom=th, left=th, right=th)
WR = Alignment(wrap_text=True, vertical="top")

CODES = {
 "법조치구분": ["지급명령", "소송", "압류추심", "경매", "가압류", "재산명시", "재산조회", "기타"],
 "법조치세부": ["예금", "증권", "급여", "보험", "기타채권", "전자소송", "전자독촉", "소송전이", "부동산강제경매", "부동산임의경매", "동산", "기타"],
 "입금구분": ["추심금", "배당금", "공탁금", "본인변제", "약정분납", "보증인", "제3자", "상계", "기타"],
 "조정구분": ["분납", "약정", "화해", "감면", "기타"],
 "해제사유구분": ["변제완납", "약정·분납", "회생·파산·면책", "오류·중복", "취하·기타", "모름"],
 "채무조정구분": ["개인회생", "파산", "신용회복"],
 "채무조정상태": ["진행", "인가", "폐지", "실효", "면책", "완제"],
}
RULES = [  # 해제 사유 원문에 이 말이 있으면 → 구분 (위에서부터 처음 맞는 것)
 ("분납|분할|약정|화해", "약정·분납"),
 ("완납|완제|변제|상환|일시납", "변제완납"),
 ("회생|파산|면책|신복|채무조정", "회생·파산·면책"),
 ("오류|착오|중복|잘못|오기|오입력", "오류·중복"),
 ("취하|철회|기타", "취하·기타"),
]
# (머리글, 필수, 예시, 설명, 코드표 이름)
SHEETS = [
 ("01_채권", "계좌 1개 = 1줄 — 법조치 안 한 채무자도 모두 (비교 집단)", [
  ("채무자키", 1, "D900482", "", None), ("계좌키", 1, "A2099-00871", "계좌별 시효를 따로 셈", None), ("채무자명", 0, "사O아", "", None),
  ("담당자", 0, "김담당", "현재 담당자", None), ("포트폴리오", 0, "99-Z 저축은행", "채권명", None),
  ("채권잔액", 1, 6930000, "원 · 아래 기준일 잔액", None), ("원금", 0, 5200000, "", None), ("법비용", 0, 186000, "지금까지 쓴 법비용 합(원)", None),
  ("시효도래일", 0, "2029-03-02", "", None), ("주민번호앞7", 0, "780512-1", "생년월일 6자리 + 뒷자리 첫 숫자만 (예: 780512-1) — 연령대·성별로 바꾸고 원래 값은 저장 안 함", None),
  ("기준일", 0, "2026-11-01", "잔액 기준일", None)]),
 ("02_법조치", "법조치 1건 = 1줄 (모든 구분)", [
  ("법조치키", 1, "L25-10016", "", None), ("채무자키", 1, "D900482", "", None), ("계좌키", 0, "A2099-00871", "", None),
  ("법조치구분", 1, "압류추심", "코드표에서 고르기", "법조치구분"), ("법조치세부", 0, "예금", "코드표에서 고르기", "법조치세부"),
  ("법원", 0, "서울중앙지방법원", "", None), ("사건번호", 0, "2025타채12345", "종합관리 사건 조회와 이어 송달·진행을 가져옴", None),
  ("신청일", 0, "2025-03-04", "", None), ("확정일자", 0, "", "집행권원(지급명령·판결 등) 확정일", None),
  ("인용일자", 0, "2025-03-18", "압류추심 등 결정(인용)일", None), ("담당자", 0, "김담당", "", None),
  ("송달일", 0, "", "있으면 적기 — 비우면 인용일·신청일 + 기준 날수로 추정", None),
  ("제3채무자유형", 0, "예금+세무서", "전산 분류값 그대로 (예금 · 예금+세무서 · 세무서 · 보험+세무서 …) — 통계 「세무서 미압류」에 씀", None)]),
 ("03_제3채무자", "법조치 × 제3채무자 1줄", [
  ("법조치키", 1, "L25-10016", "", None), ("제3채무자명", 1, "주식회사 국민은행", "이름이 달라도 됨 — 처음 한 번 은행 이름 맞추기", None),
  ("결정금액", 1, 1610000, "그 제3채무자에 정한 압류 금액(원)", None)]),
 ("04_입금", "입금 1건 = 1줄", [
  ("채무자키", 1, "D900482", "", None), ("계좌키", 0, "A2099-00871", "어느 계좌에 들어갔는지", None),
  ("입금일", 1, "2025-05-02", "", None), ("입금액", 1, 412000, "원 · 취소·반환은 음수", None),
  ("입금구분", 1, "추심금", "전산 값을 코드표 값으로 바꿔 넣기", "입금구분"),
  ("제3채무자", 0, "국민은행", "추심금이면 어느 은행 돈인지 — 은행별 성과에 씀", None), ("법조치키", 0, "L25-10016", "알면 적기", None)]),
 ("05_조정", "약정 1건 = 1줄", [
  ("채무자키", 1, "D900482", "", None), ("계좌키", 0, "A2099-00871", "", None), ("조정구분", 1, "분납", "", "조정구분"),
  ("약정일", 1, "2025-04-03", "", None), ("시작일", 0, "2025-04-25", "첫 납부 예정일", None), ("회차", 0, 10, "", None),
  ("회차당금액", 0, 100000, "원", None), ("약정총액", 0, 1000000, "원", None), ("상태", 0, "진행", "진행·완료·파기 등 (있으면)", None)]),
 ("06_해제", "해제 완료 1건 = 1줄", [
  ("법조치키", 1, "L25-10016", "", None), ("채무자키", 0, "D900482", "", None), ("제3채무자명", 0, "", "일부 은행만 해제했으면", None),
  ("해제일", 1, "2025-09-10", "", None), ("해제사유원문", 0, "분납 약정 체결로 해제", "수기로 적은 그대로", None),
  ("해제사유구분", 0, "", "비워 두면 원문으로 자동 분류 (99_해제사유_규칙) — 못 나눈 것은 프로그램에서 고름", "해제사유구분")]),
 ("07_전자추심", "추심 요청 1건 = 1줄", [
  ("법조치키", 0, "L25-10016", "법조치키나 채무자키 중 하나는 꼭", None), ("채무자키", 0, "D900482", "", None), ("채무자명", 0, "사O아", "", None),
  ("제3채무자", 1, "국민은행", "", None), ("요청일", 1, "2025-04-02", "", None), ("추심요청액", 1, 412000, "원", None)]),
 ("08_채무조정", "채무조정 1건 = 1줄 (개인회생·파산·신용회복)", [
  ("채무자키", 1, "D900482", "", None), ("구분", 1, "개인회생", "개인회생 · 파산 · 신용회복", "채무조정구분"),
  ("신청일", 0, "2024-02-01", "", None), ("상태", 1, "폐지", "진행 · 인가 · 폐지 · 실효 · 면책 · 완제", "채무조정상태"),
  ("상태일", 0, "2025-06-10", "그 상태가 된 날 (폐지·실효일 등)", None)]),
]

wb = Workbook(); ws = wb.active; ws.title = "00_안내"; ws.sheet_view.showGridLines = False
ws["A1"] = "공통양식"; ws["B1"] = "v2"; ws["A1"].font = fbb; ws["B1"].font = fbb
ws["C1"] = "← 프로그램이 이 두 칸으로 양식과 판을 알아봅니다. 지우거나 바꾸지 마세요."; ws["C1"].font = fsm
ws.column_dimensions["A"].width = 24; ws.column_dimensions["B"].width = 10; ws.column_dimensions["C"].width = 92
ws["A3"] = "법조치 회수 분석 — 공통 양식 v2"; ws["A3"].font = ft
G = [
 ("쓰는 법", "전산에서 뽑은 원자료를 VBA 등으로 이 양식의 시트·머리글에 맞춰 옮겨 넣고 프로그램에 끌어다 놓으면, 설정 없이 바로 읽습니다. 시트 이름과 1줄 머리글은 바꾸지 마세요. 칸 순서는 바뀌어도 되고, 없는 칸은 비워 둬도 됩니다."),
 ("칸 색", "검정 = 꼭 있어야 하는 칸 · 회색 = 있으면 좋은 칸 · 파랑 = 코드표 값 중에서 고르는 칸. 2줄은 형식 예시 — 지우고 넣어도, 그대로 둬도 됩니다(예시로 알아보고 건너뜀)."),
 ("열쇠", "채무자키 = 모든 시트 공통 · 계좌키 = 채권·입금·조정 (계좌별 시효) · 법조치키 = 법조치·제3채무자·해제·전자추심."),
 ("가장 중요한 것", "01_채권에는 법조치를 안 한 채무자도 모두 넣어 주세요. 「법조치가 없었으면 얼마나 들어왔을지」를 비슷한 채무자로 비교해야 진짜 효과(증분 회수)를 셉니다."),
 ("주민번호", "앞 7자리(생년월일 + 뒷자리 첫 숫자)만 넣어 주세요. 프로그램은 연령대·성별로 바꾸고 원래 값은 저장하지 않습니다. 13자리 전체가 보이면 읽지 않고 알려 줍니다."),
 ("입금구분", "추심금·배당금·공탁금 = 법조치가 직접 만든 돈, 본인변제·약정분납 = 법조치 뒤 반응한 돈(연계)으로 나눠 셉니다. 전산 값이 다르면 코드표 값으로 바꿔 넣어 주세요."),
 ("해제 사유", "수기로 적은 원문을 그대로 「해제사유원문」에 넣으면 99_해제사유_규칙의 낱말로 자동 분류합니다. 규칙은 고쳐 쓸 수 있고, 못 나눈 것은 프로그램에서 한 번 골라 주면 다음부터 기억합니다."),
 ("날짜 · 금액", "날짜는 2026-03-15 / 2026.3.15 / 20260315 모두 됩니다. 금액은 원 단위 숫자."),
 ("빈칸", "빈칸 = 모름(계산에서 뺌) · 0 = 확인된 0."),
]
r = 5
for k, v in G:
    a = ws.cell(r, 1, k); a.font = fbb; a.fill = NOTE; a.border = BD; a.alignment = WR
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
    b = ws.cell(r, 2, v); b.font = fb; b.alignment = WR; b.border = BD
    ws.row_dimensions[r].height = max(30, 15 * (len(v) // 80 + 1) + 6); r += 1

cs = wb.create_sheet("코드표")
for i, (name, vals) in enumerate(CODES.items(), start=1):
    c = cs.cell(1, i, name); c.font = fh; c.fill = CODE; c.border = BD
    for j, v in enumerate(vals, start=2):
        x = cs.cell(j, i, v); x.font = fb; x.border = BD
    cs.column_dimensions[get_column_letter(i)].width = 16
CODECOL = {name: (get_column_letter(i), len(vals)) for i, (name, vals) in enumerate(CODES.items(), start=1)}

for name, desc, cols in SHEETS:
    s = wb.create_sheet(name, index=len(wb.sheetnames) - 1)
    s.freeze_panes = "A2"
    for i, (h, req, ex, note, code) in enumerate(cols, start=1):
        c = s.cell(1, i, h); c.font = fh; c.border = BD
        c.fill = CODE if code else (REQ if req else OPT)
        c.alignment = Alignment(horizontal="center", vertical="center")
        tip = ("[꼭 필요] " if req else "") + (note or "")
        if tip.strip(): c.comment = Comment(tip, "공통양식")
        e = s.cell(2, i, ex); e.font = fex; e.border = BD
        if isinstance(ex, int) and ex >= 1000: e.number_format = "#,##0"
        s.column_dimensions[get_column_letter(i)].width = max(12, min(22, len(h) * 2 + 4))
        if code:
            col, n = CODECOL[code]
            dv = DataValidation(type="list", formula1=f"='코드표'!${col}$2:${col}${n+1}", allow_blank=True,
                                showErrorMessage=True, errorTitle="코드표 값", error="코드표에 있는 값 중에서 고르세요.")
            s.add_data_validation(dv); dv.add(f"{get_column_letter(i)}2:{get_column_letter(i)}50000")
    s.row_dimensions[1].height = 24
    n = len(cols) + 2
    s.cell(1, n, desc).font = fsm; s.cell(2, n, "← 2줄은 예시 · 머리글에 마우스를 올리면 설명").font = fsm
    s.column_dimensions[get_column_letter(n)].width = 50

rs = wb.create_sheet("99_해제사유_규칙")
for i, h in enumerate(["원문에 이 말이 있으면 (| = 또는)", "해제사유구분"], start=1):
    c = rs.cell(1, i, h); c.font = fh; c.fill = CODE; c.border = BD
for j, (k, v) in enumerate(RULES, start=2):
    rs.cell(j, 1, k).font = fb; rs.cell(j, 2, v).font = fb
    rs.cell(j, 1).border = BD; rs.cell(j, 2).border = BD
rs.cell(len(RULES) + 3, 1, "위에서부터 처음 맞는 줄로 나눕니다. 어디에도 안 맞으면 「모름」 → 프로그램에서 직접 고르면 다음부터 기억합니다.").font = fsm
rs.column_dimensions["A"].width = 44; rs.column_dimensions["B"].width = 18
wb.move_sheet("코드표", offset=len(wb.sheetnames))
wb.save(OUT); print("saved", OUT, wb.sheetnames)
