# -*- coding: utf-8 -*-
"""법조치 서류 만들기 — 문단 목록을 만들고, 워드(.docx)로 저장한다. (한글 2014 이상은 .docx 를 열 수 있음)

문단: ("title", 글) ("center", 글) ("p", 글) ("party", 이름표, 글) ("li", 번호, 글) ("right", 글) ("gap",)
화면 미리보기도 같은 문단 목록을 그린다.
"""
import datetime as dt
import os
import zipfile
from xml.sax.saxutils import escape

from . import legal as L

BASIS = {
    "약정": "약정 연체이율",
    "소촉": "소송촉진 등에 관한 특례법 연 12%",
    "상사": "상사 법정이율 연 6%",
    "민사": "민사 법정이율 연 5%",
}


def won(n):
    return f"{int(round(float(n or 0))):,}"


def kdate(s):
    if not s:
        return "    .   .   ."
    d = dt.date.fromisoformat(s[:10])
    return f"{d.year}. {d.month}. {d.day}."


def _creditor(cr):
    lines = [cr.get("name") or "(채권자 이름 — 설정에서 넣기)"]
    if cr.get("addr"):
        lines.append(cr["addr"])
    if cr.get("rep"):
        lines.append(f"대표이사 {cr['rep']}")
    if cr.get("phone"):
        lines.append(f"(전화 {cr['phone']})")
    return " / ".join(lines)


def delay_text(d, basis):
    """지연손해금 시작과 이율"""
    if basis == "약정":
        rate = d.get("rate") or ""
        start = d.get("default_date")
        frm = f"{kdate((dt.date.fromisoformat(start) + dt.timedelta(days=1)).isoformat())}부터" if start else "(기한이익 상실일 다음 날)부터"
        return frm, f"{rate}%" if rate else "(약정 연체이율)%"
    if basis == "소촉":
        return "이 사건 지급명령 정본 송달 다음 날부터", "12%"
    return "이 사건 지급명령 정본 송달 다음 날부터", "6%" if basis == "상사" else "5%"


def warnings_for(kind, d, info, cr, basis="약정"):
    w = []
    if not cr.get("name"):
        w.append("채권자(우리 회사) 정보가 비어 있어요 — 법조치 설정")
    if kind in ("지급명령", "채권압류") and not d.get("addr"):
        w.append("채무자 주소가 없어요")
    if kind == "지급명령":
        if basis == "약정" and not d.get("rate"):
            w.append("약정 연체이율이 없어요")
        if basis == "약정" and not d.get("default_date"):
            w.append("기한이익 상실일이 없어요")
        if (info.get("cause") or "양수금") == "양수금" and not (info.get("assignor") and info.get("notice_date")):
            w.append("양도인·양도 통지 도달일이 비어 있어요 — 채권 정보")
    return w


def pay_order(d, info, cr, fee, basis, court=""):
    claim = float(d.get("principal") or 0) + float(d.get("interest") or 0)
    cause = info.get("cause") or "양수금"
    frm, rate = delay_text(d, basis)
    assignor = info.get("assignor") or "(양도인)"
    p = [("title", "지급명령신청서"), ("party", "채 권 자", _creditor(cr)),
         ("party", "채 무 자", f"{d.get('name', '')} / {d.get('addr') or '(주소)'}"), ("gap",),
         ("center", f"{cause} 청구의 독촉사건"), ("center", f"청구금액: 금 {won(claim)}원"),
         ("h", "신 청 취 지"), ("p", "채무자는 채권자에게 아래 청구금액 및 독촉절차비용을 지급하라는 명령을 구합니다."),
         ("li", "1.", f"금 {won(claim)}원 및 그중 금 {won(d.get('principal'))}원에 대하여 {frm} 다 갚는 날까지 연 {rate}의 비율로 계산한 돈"),
         ("li", "2.", f"독촉절차비용 {won(fee['stamp'] + fee['svc'])}원 (인지대 {won(fee['stamp'])}원, 송달료 {won(fee['svc'])}원)"),
         ("h", "신 청 원 인")]
    if cause == "양수금":
        p += [("li", "1.", f"채무자는 {kdate(d.get('contract_date') or info.get('contract_date'))} {assignor}와(과) 대출계약을 맺고 돈을 빌렸으나, "
                            f"현재 원금 {won(d.get('principal'))}원과 이자 {won(d.get('interest'))}원을 갚지 않고 있습니다."),
              ("li", "2.", f"{assignor}는 {kdate(info.get('assign_date'))} 채권자에게 위 채권을 양도하였고, 그 양도 통지는 "
                            f"{kdate(info.get('notice_date'))} 채무자에게 도달하였습니다."),
              ("li", "3.", "따라서 채권자는 채무자에게 위 신청취지 기재 금액의 지급을 구하기 위하여 이 신청에 이르렀습니다.")]
    else:
        p += [("li", "1.", f"채무자는 {kdate(d.get('contract_date') or info.get('contract_date'))} 채권자와 대출계약을 맺고 돈을 빌렸으나, "
                            f"현재 원금 {won(d.get('principal'))}원과 이자 {won(d.get('interest'))}원을 갚지 않고 있습니다."),
              ("li", "2.", "따라서 채권자는 채무자에게 위 신청취지 기재 금액의 지급을 구하기 위하여 이 신청에 이르렀습니다.")]
    att = ["대출거래약정서 사본"] + (["채권양도계약서 사본", "채권양도 통지서 및 도달 증명"] if cause == "양수금" else []) + ["법인 등기사항증명서"]
    p += [("h", "첨 부 서 류")] + [("li", f"{i}.", a) for i, a in enumerate(att, 1)]
    p += [("gap",), ("right", kdate(L.today())), ("right", f"위 채권자 {cr.get('name') or ''} (인)"), ("gap",), ("center", f"{court or '○○지방법원'} 귀중")]
    return p


THIRD_TEXT = {
    "급여": "채무자가 제3채무자로부터 지급받는 매월의 급여(본봉 및 제수당)와 퇴직금 중 민사집행법 제246조 제1항 제4호·제5호와 같은 법 시행령에 따른 압류금지 금액을 뺀 나머지 금액으로서, 위 청구금액에 이르기까지의 금액",
    "예금": "채무자가 제3채무자에 대하여 가지는 예금채권 중 민사집행법 제246조 제1항 제8호·제9호와 같은 법 시행령에 따른 압류금지 금액을 뺀 나머지 금액으로서, 위 청구금액에 이르기까지의 금액",
    "보험": "채무자가 제3채무자와 맺은 보험계약에 따른 해약환급금 채권 중 민사집행법 제246조 제1항 제7호와 같은 법 시행령에 따른 압류금지 금액을 뺀 나머지 금액으로서, 위 청구금액에 이르기까지의 금액",
    "임차보증금": "채무자가 제3채무자에 대하여 가지는 임대차보증금 반환채권 중 주택임대차보호법상 우선변제를 받을 수 있는 금액을 뺀 나머지 금액으로서, 위 청구금액에 이르기까지의 금액",
}


def garnish(d, info, cr, fee, thirds, title_no="", court=""):
    claim = float(d.get("principal") or 0) + float(d.get("interest") or 0)
    p = [("title", "채권압류 및 추심명령 신청서"), ("party", "채 권 자", _creditor(cr)),
         ("party", "채 무 자", f"{d.get('name', '')} / {d.get('addr') or '(주소)'}")]
    for i, t in enumerate(thirds, 1):
        p.append(("party", f"제3채무자 {i}", t.get("third") or t.get("name") or "(제3채무자)"))
    p += [("gap",), ("center", f"청구채권: 금 {won(claim)}원"),
          ("p", f"집행권원: {title_no or '(집행권원 — 사건번호)'} 사건의 집행력 있는 정본"),
          ("h", "압류할 채권의 표시")]
    for i, t in enumerate(thirds, 1):
        p.append(("li", f"{i}.", f"[제3채무자 {i}] " + THIRD_TEXT.get(t.get("kind"), "채무자가 제3채무자에 대하여 가지는 채권")))
    p += [("h", "신 청 취 지"),
          ("li", "1.", "채무자의 제3채무자에 대한 위 압류할 채권을 압류한다."),
          ("li", "2.", "제3채무자는 채무자에게 위 압류된 채권을 지급하여서는 아니 된다."),
          ("li", "3.", "채무자는 위 채권을 처분하거나 영수하여서는 아니 된다."),
          ("li", "4.", "위 압류된 채권은 채권자가 추심할 수 있다."),
          ("p", "라는 재판을 구합니다."),
          ("h", "신 청 이 유"),
          ("p", "채권자는 채무자에 대하여 위 집행권원을 가지고 있으나 채무자가 이를 갚지 않으므로, 채무자의 제3채무자에 대한 위 채권을 압류하고 추심하기 위하여 이 신청을 합니다."),
          ("h", "첨 부 서 류"), ("li", "1.", "집행력 있는 정본"), ("li", "2.", "송달증명원"), ("li", "3.", "법인 등기사항증명서"),
          ("gap",), ("right", kdate(L.today())), ("right", f"위 채권자 {cr.get('name') or ''} (인)"), ("gap",),
          ("center", f"{court or '○○지방법원'} 귀중"),
          ("p", f"(비용 예상: 인지 {won(fee['stamp'])}원, 송달료 {won(fee['svc'])}원)")]
    return p


def address_fix(item, d, cr, new_addr=""):
    act = item.get("act") or ""
    chk = lambda on: "☑" if on else "☐"  # noqa: E731
    if act.startswith("소제기"):
        return [("title", "소제기신청서"), ("party", "사　　건", item.get("case_no", "")), ("party", "채 권 자", _creditor(cr)),
                ("party", "채 무 자", d.get("name", "") if d else item.get("party", "")), ("gap",),
                ("p", "위 독촉사건에 관하여 채무자에게 지급명령을 송달할 수 없으므로, 민사소송법 제466조 제1항에 따라 소제기 신청을 합니다."),
                ("gap",), ("right", kdate(L.today())), ("right", f"위 채권자 {cr.get('name') or ''} (인)")]
    na = new_addr or (d or {}).get("addr", "")
    return [("title", "주소보정서"), ("party", "사　　건", item.get("case_no", "")),
            ("party", "채 권 자", cr.get("name") or ""), ("party", "채 무 자", (d or {}).get("name") or item.get("party", "")), ("gap",),
            ("p", "위 사건에 관하여 아래와 같이 채무자의 주소를 보정합니다."),
            ("li", chk(act == "새 주소로 보정"), f"주소변동 있음 — 새 주소: {na if act == '새 주소로 보정' else ''}"),
            ("li", chk(act == "재송달"), "주소변동 없음 — 같은 주소로 재송달 신청"),
            ("li", chk(act.startswith("야간")), "특별송달 신청 (야간·휴일)"),
            ("li", chk(act == "공시송달 신청"), "공시송달 신청 (소명자료 붙임)"),
            ("gap",), ("right", kdate(L.today())), ("right", f"위 채권자 {cr.get('name') or ''} (인)")]


def rehab_doc(kind, r, d, cr, amount=0):
    title = {"이의신청서": "개인회생채권자목록 이의신청서", "채권신고서": "채권신고서", "면책 이의신청서": "면책 이의신청서"}[kind]
    body = {
        "이의신청서": f"채권자는 채무자가 낸 개인회생채권자목록 중 채권자의 채권 금액에 대하여 이의합니다. 채권자의 채권은 금 {won(amount)}원(원금·이자 포함)입니다.",
        "채권신고서": f"채권자는 위 사건에 관하여 아래 채권을 신고합니다. 신고 금액: 금 {won(amount)}원(원금·이자 포함).",
        "면책 이의신청서": "채권자는 위 사건의 면책신청에 대하여 이의합니다. (면책 불허가 사유를 구체적으로 적으세요)",
    }[kind]
    return [("title", title), ("party", "사　　건", r.get("no", "")), ("party", "채 권 자", _creditor(cr)),
            ("party", "채 무 자", (d or {}).get("name", "")), ("gap",), ("p", body), ("gap",),
            ("right", kdate(L.today())), ("right", f"위 채권자 {cr.get('name') or ''} (인)"), ("gap",),
            ("center", f"{r.get('court') or '○○법원'} 귀중")]


def paste_text(paras):
    """전자소송 입력칸에 붙여 넣을 신청취지·신청원인 글"""
    out, take = [], False
    for p in paras:
        if p[0] == "h":
            take = p[1].replace(" ", "") in ("신청취지", "신청원인", "신청이유", "압류할채권의표시")
            out.append("\n[" + p[1].replace(" ", "") + "]")
            continue
        if not take:
            continue
        if p[0] == "li":
            out.append(f"{p[1]} {p[2]}")
        elif p[0] == "p":
            out.append(p[1])
    return "\n".join(out).strip()


# ---------------------------------------------------------------- 워드 파일 (직접 XML 로)

_CT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>"""
_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>"""
_DOCRELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>"""
_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Batang" w:hAnsi="Batang" w:eastAsia="바탕" w:cs="Batang"/><w:sz w:val="23"/><w:szCs w:val="23"/><w:lang w:val="en-US" w:eastAsia="ko-KR"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="80" w:line="384" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style></w:styles>"""
_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _run(text, bold=False, size=None):
    rpr = ("<w:b/>" if bold else "") + (f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>' if size else "")
    return f'<w:r>{f"<w:rPr>{rpr}</w:rPr>" if rpr else ""}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def _para(p):
    k = p[0]
    if k == "title":
        return f'<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="200" w:after="400"/></w:pPr>{_run(" ".join(p[1]) if len(p[1]) <= 12 else p[1], True, 36)}</w:p>'
    if k == "h":
        return f'<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="240" w:after="120"/></w:pPr>{_run(p[1], True, 25)}</w:p>'
    if k == "center":
        return f'<w:p><w:pPr><w:jc w:val="center"/></w:pPr>{_run(p[1], True)}</w:p>'
    if k == "right":
        return f'<w:p><w:pPr><w:jc w:val="right"/></w:pPr>{_run(p[1])}</w:p>'
    if k == "party":
        return f'<w:p><w:pPr><w:ind w:left="1700" w:hanging="1700"/></w:pPr>{_run(p[1], True)}<w:r><w:tab/></w:r>{_run(p[2])}</w:p>'
    if k == "li":
        return f'<w:p><w:pPr><w:ind w:left="500" w:hanging="400"/></w:pPr>{_run(p[1] + " ")}{_run(p[2])}</w:p>'
    if k == "gap":
        return "<w:p/>"
    return f'<w:p><w:pPr><w:ind w:firstLine="200"/></w:pPr>{_run(p[1])}</w:p>'


def write_docx(paras, path):
    body = "".join(_para(p) for p in paras)
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {_NS}><w:body>{body}'
           '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1700" w:right="1440" w:bottom="1440" w:left="1700" '
           'w:header="851" w:footer="992" w:gutter="0"/></w:sectPr></w:body></w:document>')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CT)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/_rels/document.xml.rels", _DOCRELS)
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", _STYLES)
    return path
