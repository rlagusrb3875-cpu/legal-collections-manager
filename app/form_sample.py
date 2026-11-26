# -*- coding: utf-8 -*-
"""시연·점검용 「주소보정서」 양식 PDF를 만든다 (회사 양식을 흉내 낸 것, 배포본 시연 자료에도 씀)."""
from core.forms import font_name


def make(path):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    W, H = A4
    F, FB = font_name("myeongjo"), font_name("myeongjo", True)
    c = canvas.Canvas(path, pagesize=A4)
    top = lambda y: H - y  # noqa: E731  (위에서 잰 값 → PDF 좌표)

    def t(x, y, s, txt, font=F, center=False):
        c.setFont(font, s)
        (c.drawCentredString if center else c.drawString)(x, top(y + s * 0.85), txt)

    def box(x, y, w, h):
        c.rect(x, top(y + h), w, h)

    def cb(x, y, txt):
        c.rect(x, top(y + 11), 11, 11)
        t(x + 16, y, 12, txt)

    c.setTitle("주소보정서 (시연용 회사 양식)")
    t(W / 2, 58, 22, "주  소  보  정  서", center=True)
    for lab, y in (("사　　건", 120), ("원　　고", 148), ("피　　고", 176)):
        box(60, y, 90, 28)
        box(150, y, 385, 28)
        t(76, y + 7, 12, lab)
    t(60, 224, 12.5, "위 사건에 관하여 원고는 피고의 주소를 아래와 같이 보정합니다.")
    t(60, 258, 13, "1. 송달불능 사유", FB)
    cb(80, 285, "주소불명")
    cb(175, 285, "폐문부재")
    cb(270, 285, "수취인불명")
    cb(380, 285, "이사불명")
    t(60, 322, 13, "2. 보정할 주소", FB)
    box(80, 345, 455, 50)
    t(60, 410, 13, "3. 신청", FB)
    cb(80, 437, "주소 변동 없음 — 종전 주소로 재송달을 신청합니다.")
    cb(80, 461, "특별송달(집행관 송달)을 신청합니다. (주간 · 야간 · 휴일)")
    t(60, 498, 11.5, "※ 첨부: 주민등록표 초본 1통")
    t(232, 536, 12.5, "20    .    .    .")
    t(296, 588, 12.5, "원　고")
    c.line(338, top(603), 494, top(603))
    t(498, 588, 12.5, "(인)")
    t(296, 614, 12.5, "대리인")
    c.line(338, top(629), 494, top(629))
    t(60, 690, 16, "서울중앙지방법원 귀중", FB)
    c.showPage()
    c.save()
    return path
