# -*- coding: utf-8 -*-
"""회사 양식 PDF — 칸 찾기 · 값 채우기 · 미리보기 그림.

좌표는 모두 「화면에 보이는 쪽(자르기 상자)의 왼쪽 위」를 0으로 한 pt 단위 (1pt = 1/72인치).
양식의 고정 문구는 읽기만 하고 건드리지 않는다. 바뀌는 칸에만 글자를 얹는다.
"""
import base64
import ctypes
import datetime as dt
import io
import os
import re
import sys

# ------------------------------------------------------------------ 항목

ITEMS = [
    {"k": "company", "n": "우리 회사명", "g": "고정값"},
    {"k": "company_addr", "n": "우리 회사 주소", "g": "고정값"},
    {"k": "ceo", "n": "대표자", "g": "고정값"},
    {"k": "phone", "n": "회사 전화", "g": "고정값"},
    {"k": "agent", "n": "담당자·연락처", "g": "고정값"},
    {"k": "creditor", "n": "채권자(원채권사·양도인)", "g": "채권·사건값"},
    {"k": "debtor", "n": "채무자 이름", "g": "채권·사건값"},
    {"k": "debtor_addr", "n": "채무자 주소", "g": "채권·사건값"},
    {"k": "new_addr", "n": "새 주소", "g": "채권·사건값"},
    {"k": "case_no", "n": "사건번호", "g": "채권·사건값", "fmts": [["tight", "2026가소10231"], ["space", "2026 가소 10231"]]},
    {"k": "case_name", "n": "사건명", "g": "채권·사건값"},
    {"k": "court", "n": "법원", "g": "채권·사건값"},
    {"k": "amount", "n": "청구금액", "g": "채권·사건값",
     "fmts": [["num", "금 3,412,000원"], ["kor", "금 삼백사십일만이천원"], ["both", "금 3,412,000원(삼백사십일만이천원)"], ["plain", "3,412,000"]]},
    {"k": "mgmt_no", "n": "관리번호·계좌", "g": "채권·사건값"},
    {"k": "date", "n": "작성일", "g": "그때그때 값", "fmts": [["dot", "2026. 11. 4."], ["kor", "2026년 11월 4일"], ["dash", "2026-11-04"]]},
    {"k": "reason", "n": "송달불능 사유", "g": "그때그때 값", "opts": ["주소불명", "폐문부재", "수취인불명", "이사불명"]},
    {"k": "req", "n": "신청 종류", "g": "그때그때 값", "opts": ["재송달", "특별송달", "공시송달"]},
    {"k": "seal", "n": "법인 인감", "g": "고정값", "image": True},
]
FIXED = {"company", "company_addr", "ceo", "phone", "agent", "date", "seal"}
TYPES = ("text", "long", "over", "check", "seal")


def items(custom=None):
    out = [dict(i) for i in ITEMS]
    for c in custom or []:
        out.append({"k": c["k"], "n": c["n"], "g": "회사에서 더한 항목", "custom": True})
    return out


# ------------------------------------------------------------------ 값 모양

def kor_num(n):
    d, u, big = "영일이삼사오육칠팔구", ["", "십", "백", "천"], ["", "만", "억", "조"]
    n = int(n or 0)
    if n <= 0:
        return "영"
    s, i = "", 0
    while n > 0:
        chunk, c, j = n % 10000, "", 0
        while chunk > 0:
            k = chunk % 10
            if k:
                c = ("" if k == 1 and j > 0 else d[k]) + u[j] + c
            chunk //= 10
            j += 1
        if c:
            s = c + big[i] + s
        n //= 10000
        i += 1
    return s


def to_int(v):
    s = re.sub(r"[^\d]", "", str(v if v is not None else ""))
    return int(s) if s else 0


def fmt_value(item, fmt, v):
    if v is None or v == "":
        return ""
    if item == "date":
        try:
            d = dt.date.fromisoformat(str(v)[:10])
        except ValueError:
            return str(v)
        return f"{d.year}년 {d.month}월 {d.day}일" if fmt == "kor" else d.isoformat() if fmt == "dash" else f"{d.year}. {d.month}. {d.day}."
    if item == "amount":
        n = to_int(v)
        if not n:
            return ""
        a, b = f"금 {n:,}원", f"금 {kor_num(n)}원"
        return b if fmt == "kor" else f"{a}({b[2:]})" if fmt == "both" else f"{n:,}" if fmt == "plain" else a
    if item == "case_no" and fmt == "space":
        return re.sub(r"^(\d{4})(\D+)(\d+)$", r"\1 \2 \3", str(v))
    return str(v)


def clean_case_no(s):
    s = str(s or "").translate({0xFF10 + i: 0x30 + i for i in range(10)})
    return re.sub(r"\s+", "", s)


# ------------------------------------------------------------------ 글꼴

FONT_FILES = {
    "gothic": [r"C:\Windows\Fonts\malgun.ttf", "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
               "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"],
    "gothic_b": [r"C:\Windows\Fonts\malgunbd.ttf"],
    "myeongjo": [r"C:\Windows\Fonts\batang.ttc", "/System/Library/Fonts/Supplemental/AppleMyungjo.ttf",
                 "/usr/share/fonts/truetype/nanum/NanumMyeongjo.ttf"],
}
FONT_CSS = {"gothic": '"Malgun Gothic","Apple SD Gothic Neo",sans-serif', "myeongjo": 'Batang,"AppleMyungjo","Nanum Myeongjo",serif'}
_REG = {}


def font_name(kind="myeongjo", bold=False):
    """reportlab에 한글 글꼴을 올리고 이름을 돌려준다. 회사 PC(Windows)에 있는 맑은 고딕·바탕을 쓴다."""
    key = (kind, bold)
    if key in _REG:
        return _REG[key]
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    paths = (FONT_FILES["gothic_b"] if bold and kind == "gothic" else []) + FONT_FILES.get(kind, []) + FONT_FILES["gothic"]
    windir = os.environ.get("WINDIR")
    if windir:
        paths = [p.replace(r"C:\Windows", windir) for p in paths]
    for p in paths:
        if os.path.isfile(p):
            name = f"KR_{kind}_{int(bold)}"
            try:
                pdfmetrics.registerFont(TTFont(name, p, subfontIndex=0) if p.lower().endswith(".ttc") else TTFont(name, p))
            except Exception:
                continue
            _REG[key] = name
            return name
    raise ValueError("한글 글꼴(맑은 고딕·바탕)을 찾지 못했어요")


def text_width(s, size, kind="myeongjo", bold=False):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    return stringWidth(s, font_name(kind, bold), size)


def _wrap(s, size, w, kind):
    lines, cur = [], ""
    for word in s.split(" "):
        t = f"{cur} {word}" if cur else word
        if text_width(t, size, kind) <= w:
            cur = t
            continue
        if cur:
            lines.append(cur)
        cur = ""
        for ch in word:  # 낱말 하나가 줄보다 길면 글자 단위로 자른다
            if text_width(cur + ch, size, kind) <= w:
                cur += ch
            else:
                lines.append(cur)
                cur = ch
    if cur:
        lines.append(cur)
    return lines


def layout(f, text, kind="myeongjo"):
    """칸에 맞는 글자 크기를 정한다. flow=True면 가장 작게 해도 넘친다."""
    w, h = f["w"] - 4, f["h"]
    top = float(f.get("size") or 0)
    if f["type"] == "long":
        hi = top or 12
        size = hi
        while size >= 9.5:
            lines = _wrap(text, size, w, kind)
            if len(lines) * size * 1.3 <= h + 0.5:
                return {"px": size, "lines": lines, "flow": False}
            size -= 0.5
        return {"px": 9.5, "lines": _wrap(text, 9.5, w, kind), "flow": True}
    bold = f["type"] == "over"
    hi = top or (min(16, h * 0.76) if bold else min(12.5, h * 0.72))
    size = hi
    while size >= 8.5:
        if text_width(text, size, kind, bold) <= w:
            return {"px": size, "lines": [text], "flow": False}
        size -= 0.5
    return {"px": 8.5, "lines": [text], "flow": True}


# ------------------------------------------------------------------ 점검

def check(fields, vals, names, kind="myeongjo", ref=None, full=True):
    """한 사람의 값을 양식 칸에 맞춰 보고 문제를 찾는다."""
    issues, lay = [], []
    seen = set()
    for i, f in enumerate(fields):
        k = f.get("item")
        if not k:
            continue
        if f["type"] == "check":
            lay.append({"i": i, "check": vals.get(k) == f.get("opt")})
            continue
        if f["type"] == "seal":
            lay.append({"i": i, "seal": bool(vals.get("__seal"))})
            continue
        text = fmt_value(k, f.get("fmt"), vals.get(k))
        if not text:
            if not f.get("optional") and k not in seen:
                issues.append({"t": "bad", "k": k, "m": f"「{names.get(k, k)}」 칸이 비어 있어요."})
                seen.add(k)
            lay.append({"i": i, "empty": not f.get("optional"), "lines": [], "px": 0})
            continue
        if f.get("suffix"):
            text += f["suffix"]
        r = layout(f, text, kind)
        if r["flow"] and k not in seen:
            issues.append({"t": "warn", "k": k, "m": f"「{names.get(k, k)}」 글자가 칸보다 길어요. 줄여 쓰거나 양식의 칸을 키워 주세요."})
            seen.add(k)
        lay.append(dict(r, i=i))
    ref = ref or {}
    if ref.get("court") and vals.get("court") and ref["court"] != vals["court"]:
        issues.append({"t": "warn", "k": "court", "m": f"사건 대장에는 법원이 「{ref['court']}」예요.", "fix": {"v": ref["court"], "label": "대장 값으로"}})
    status = "bad" if any(x["t"] == "bad" for x in issues) else "warn" if issues else "ok"
    out = {"status": status, "issues": issues}
    if full:
        out["layout"] = lay
    return out


# ------------------------------------------------------------------ PDF 읽기 · 그림

def _pdfium():
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw
    return pdfium, raw


def page_info(path):
    pdfium, _ = _pdfium()
    doc = pdfium.PdfDocument(path)
    out = []
    for pg in doc:
        l, b, r, t = pg.get_cropbox()
        out.append({"w": round(r - l, 2), "h": round(t - b, 2), "cl": l, "ct": t})
    doc.close()
    return out


def render_png(path, index=0, scale=2.0):
    pdfium, _ = _pdfium()
    doc = pdfium.PdfDocument(path)
    try:
        img = doc[index].render(scale=scale).to_pil()
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    finally:
        doc.close()


def normalize(src, dst):
    """돌려 놓은 쪽(/Rotate)을 내용에 반영해 저장한다 — 칸 좌표가 어긋나지 않게."""
    from pypdf import PdfReader, PdfWriter
    rd = PdfReader(src)
    if rd.is_encrypted:
        try:
            rd.decrypt("")
        except Exception:
            raise ValueError("암호가 걸린 PDF예요. 암호를 푼 PDF를 넣어 주세요.")
    w = PdfWriter()
    for p in rd.pages:
        if p.get("/Rotate", 0) % 360:
            p.transfer_rotation_to_content()
        w.add_page(p)
    with open(dst, "wb") as f:
        w.write(f)


# ------------------------------------------------------------------ 칸 찾기

def _norm(s):
    s = re.sub(r"[\s\u3000]+", "", s or "")
    s = re.sub(r"^(\d{1,2}|[가-하])[.)](?=[^.\d])", "", s)
    return s.strip(":：·.")


LABELS = {}
for _k, _ws in {
    "case_no": ["사건", "사건번호", "사건번호(사건명)"], "case_name": ["사건명"],
    "company": ["원고", "신청인", "채권자", "신청인(채권자)", "원고(채권자)", "채권자(신청인)", "채권자겸신청인"],
    "debtor": ["피고", "채무자", "피신청인", "상대방", "피고(채무자)", "채무자(피고)", "채무자(피신청인)"],
    "creditor": ["양도인", "원채권자", "채권양도인"],
    "debtor_addr": ["주소", "채무자주소", "피고주소", "송달주소"],
    "new_addr": ["보정할주소", "새주소", "신주소", "송달장소", "송달할장소", "변경된주소", "보정주소", "새로운주소"],
    "amount": ["청구금액", "청구액", "소가", "청구금", "금액", "청구채권", "집행채권"],
    "ceo": ["대표이사", "대표자"], "agent": ["대리인", "담당자", "신청대리인", "소송대리인"], "phone": ["연락처", "전화", "전화번호"],
    "mgmt_no": ["관리번호", "계좌번호"], "date": ["작성일", "신청일", "신청일자", "일자", "날짜", "작성일자", "제출일"],
}.items():
    for _w in _ws:
        LABELS[_w] = _k
OPT_WORDS = {"재송달": ["재송달", "종전주소", "주소변동없음", "주소변경없음"], "특별송달": ["특별송달", "집행관", "야간", "휴일"],
             "공시송달": ["공시송달"]}
COURT_RE = re.compile(r"^(\S+(지방)?법원(\S+지원)?|\S+지원)귀중$")
DATE_RE = re.compile(r"^(20\d{0,2})?\.{2,3}$|^(20\d{0,2})?년월일$")
BOX_BELOW = {"new_addr", "debtor_addr", "company_addr"}
BOXES = set("□☐❑▢")


def _lines_and_chars(page, info):
    pdfium, raw = _pdfium()
    cl, ct = info["cl"], info["ct"]
    hs, vs = [], []
    for obj in page.get_objects(filter=(raw.FPDF_PAGEOBJ_PATH,), max_depth=3):
        try:
            m = obj.get_matrix()
            n = raw.FPDFPath_CountSegments(obj.raw)
        except Exception:
            continue
        start = prev = None
        x, y = ctypes.c_float(), ctypes.c_float()
        for i in range(n):
            seg = raw.FPDFPath_GetPathSegment(obj.raw, i)
            raw.FPDFPathSegment_GetPoint(seg, x, y)
            X = m.a * x.value + m.c * y.value + m.e - cl
            Y = ct - (m.b * x.value + m.d * y.value + m.f)
            t = raw.FPDFPathSegment_GetType(seg)
            pts = []
            if t == raw.FPDF_SEGMENT_MOVETO:
                start = prev = (X, Y)
            else:
                if t == raw.FPDF_SEGMENT_LINETO and prev:
                    pts.append((prev, (X, Y)))
                prev = (X, Y)
            if raw.FPDFPathSegment_GetClose(seg) and start and prev:
                pts.append((prev, start))
                prev = start
            for (x0, y0), (x1, y1) in pts:
                if abs(y1 - y0) < 0.9 and abs(x1 - x0) > 4:
                    hs.append((min(x0, x1), max(x0, x1), (y0 + y1) / 2))
                elif abs(x1 - x0) < 0.9 and abs(y1 - y0) > 4:
                    vs.append(((x0 + x1) / 2, min(y0, y1), max(y0, y1)))
    boxes = []
    for obj in page.get_objects(filter=(raw.FPDF_PAGEOBJ_PATH,), max_depth=3):
        try:
            l, b, r, t = obj.get_bounds()
        except Exception:
            continue
        if 6 <= r - l <= 16 and 6 <= t - b <= 16 and abs((r - l) - (t - b)) < 2.5:
            boxes.append((l - cl, ct - t, r - cl, ct - b))
    tp = page.get_textpage()
    chars = []
    for i in range(tp.count_chars()):
        ch = tp.get_text_range(i, 1)
        l, b, r, t = tp.get_charbox(i)
        chars.append((ch, l - cl, ct - t, r - cl, ct - b))
    tp.close()
    return hs, vs, boxes, chars


def _segments(chars, vs):
    """글자를 줄·덩어리로 묶는다 (표의 세로줄이나 넓은 빈칸에서 끊음)."""
    segs, cur = [], None
    for ch, l, t, r, b in chars:
        if ch in "\r\n" or (r - l) <= 0.01:
            if ch in "\r\n" and cur:
                segs.append(cur)
                cur = None
            elif cur and ch == " ":
                cur["text"] += " "
            continue
        h = b - t
        if cur:
            same_line = abs((cur["t"] + cur["b"]) / 2 - (t + b) / 2) < max(h, cur["b"] - cur["t"]) * 0.55
            gap = l - cur["r"]
            wall = any(cur["r"] - 1 <= v[0] <= l + 1 and v[1] <= (t + b) / 2 <= v[2] for v in vs)
            if not same_line or gap < -h or wall or gap > max(3 * h, 30):
                segs.append(cur)
                cur = None
        if cur is None:
            cur = {"text": "", "l": l, "t": t, "r": r, "b": b}
        cur["text"] += ch
        cur["l"], cur["t"], cur["r"], cur["b"] = min(cur["l"], l), min(cur["t"], t), max(cur["r"], r), max(cur["b"], b)
    if cur:
        segs.append(cur)
    for s in segs:
        s["n"] = _norm(s["text"])
    return [s for s in segs if s["n"] or BOXES.intersection(s["text"])]


def _label_of(n):
    if n in LABELS:
        return LABELS[n]
    m = re.match(r"^(.+?)\(.+\)$", n)
    if m and n in LABELS:
        return LABELS[n]
    if m and m[1] in LABELS:
        return LABELS[m[1]]
    return None


def _same_line(a, b):
    return abs((a["t"] + a["b"]) / 2 - (b["t"] + b["b"]) / 2) < (a["b"] - a["t"]) * 0.6


def _box_below(lab, hs):
    tops = sorted((y, a, b_) for a, b_, y in hs if lab["b"] < y <= lab["b"] + 30 and a <= lab["l"] + 40 and b_ - a > 150)
    for y, a, b_ in tops:
        bot = [y2 for a2, b2, y2 in hs if abs(a2 - a) < 3 and abs(b2 - b_) < 3 and y + 12 < y2 < y + 150]
        if bot:
            return {"x": a + 5, "y": y + 4, "w": b_ - a - 10, "h": min(bot) - y - 8}
    return None


def _region(lab, segs, hs, vs, pw, item=""):
    cy, h = (lab["t"] + lab["b"]) / 2, lab["b"] - lab["t"]
    walls = sorted(v[0] for v in vs if v[1] - 1 <= cy <= v[2] + 1)
    right = [x for x in walls if lab["r"] - 1 <= x <= lab["r"] + 120]
    if not right and (item in BOX_BELOW or re.match(r"^\s*(\d{1,2}|[가-하])[.)]", lab["text"])):
        bb = _box_below(lab, hs)
        if bb:
            return bb
    later = [s for s in segs if s is not lab and _same_line(lab, s) and s["l"] > lab["r"] + 2]
    if right:
        x0 = right[0] + 4
        nxt = [x for x in walls if x > right[0] + 15]
        x1 = (nxt[0] if nxt else pw - 40) - 4
        inside = [s for s in later if x0 - 2 <= s["l"] < x1]
        above = [y for x_a, x_b, y in hs if x_a <= x0 + 2 and x_b >= x0 + 10 and y <= lab["t"] + 1 and lab["t"] - y < 30]
        below = [y for x_a, x_b, y in hs if x_a <= x0 + 2 and x_b >= x0 + 10 and y >= lab["b"] - 1 and y - lab["b"] < 40]
        y0 = (max(above) + 3) if above else lab["t"] - 3
        y1 = (min(below) - 3) if below else lab["b"] + 3
        if inside:  # 칸 안에 이미 글자(○○○ 등)가 있으면 덮어쓰기 칸으로
            if all(not _label_of(s["n"]) for s in inside):
                x1b = max(s["r"] for s in inside) + 3
                return {"x": x0, "y": y0, "w": max(x1b, x0 + 40) - x0, "h": y1 - y0, "over": " ".join(s["text"].strip() for s in inside)}
            x1 = min(s["l"] for s in inside) - 6
        return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}
    ul = [(a, b_, y) for a, b_, y in hs if lab["b"] - 4 <= y <= lab["b"] + 9 and b_ > lab["r"] + 20 and a <= lab["r"] + 40]
    if ul:
        a, b_, y = min(ul, key=lambda u: u[0])
        x0 = max(a, lab["r"] + 3) + 2
        hh = max(h + 5, 14)
        return {"x": x0, "y": y - hh - 0.5, "w": b_ - x0 - 1, "h": hh}
    end = min([s["l"] for s in later] + [pw - 40]) - 6
    if end - lab["r"] > 40:
        return {"x": lab["r"] + 6, "y": lab["t"] - 3, "w": end - lab["r"] - 6, "h": h + 6}
    return None


def detect(path):
    """양식에서 바뀔 칸을 찾아 제안한다. 제안만 할 뿐, 사람이 확인해서 저장한다."""
    pdfium, _ = _pdfium()
    infos = page_info(path)
    doc = pdfium.PdfDocument(path)
    out, nchars = [], 0
    try:
        for pi, pg in enumerate(doc):
            info = infos[pi]
            hs, vs, boxes, chars = _lines_and_chars(pg, info)
            nchars += len(chars)
            segs = _segments(chars, vs)
            used = set()
            # 1) □ 체크 칸 (글자 □ 또는 작은 네모)
            cks = []
            for s in segs:
                for ch, l, t, r, b in chars:
                    if ch in BOXES and s["l"] - 0.5 <= l and r <= s["r"] + 0.5 and s["t"] - 0.5 <= t and b <= s["b"] + 0.5:
                        cks.append((l, t, r, b))
            cks += boxes
            for (l, t, r, b) in cks:
                lab = min((s for s in segs if s["l"] >= r - 1 and abs((s["t"] + s["b"]) / 2 - (t + b) / 2) < (b - t) and s["l"] - r < 30),
                          key=lambda s: s["l"], default=None)
                text = re.sub("[□☐❑▢]", "", lab["text"]).strip() if lab else ""
                nn = _norm(text)
                item = opt = ""
                for it in ITEMS:
                    for o in it.get("opts") or []:
                        if any(w in nn for w in OPT_WORDS.get(o, [o])):
                            item, opt = it["k"], o
                            break
                    if item:
                        break
                out.append({"p": pi, "type": "check", "item": item, "opt": opt, "x": l - 1.5, "y": t - 1.5, "w": r - l + 3, "h": b - t + 3,
                            "sug": True, "found": "□ " + (text[:24] or "(옆 글자 없음)")})
            # 2) 「○○법원 귀중」, 「20 . . .」 같은 덮어쓰기
            for s in segs:
                if COURT_RE.match(s["n"]):
                    out.append({"p": pi, "type": "over", "item": "court", "suffix": " 귀중", "orig": s["text"].strip(),
                                "x": s["l"] - 2, "y": s["t"] - 3, "w": max(s["r"] - s["l"] + 60, 160), "h": s["b"] - s["t"] + 6,
                                "sug": True, "found": s["text"].strip()})
                    used.add(id(s))
                elif DATE_RE.match(re.sub(r"\s", "", s["text"])) and len(s["text"].strip()) >= 4:
                    out.append({"p": pi, "type": "over", "item": "date", "fmt": "kor" if "년" in s["text"] else "dot", "orig": s["text"].strip(),
                                "x": s["l"] - 2, "y": s["t"] - 3, "w": max(s["r"] - s["l"] + 20, 110), "h": s["b"] - s["t"] + 6,
                                "sug": True, "found": s["text"].strip()})
                    used.add(id(s))
            # 3) 낱말 옆 빈칸 · 밑줄 (끊어진 낱말 「원　　고」도 이어 붙여 본다)
            k = 0
            while k < len(segs):
                s = segs[k]
                if id(s) in used or BOXES.intersection(s["text"]):
                    k += 1
                    continue
                lab, item, span = s, _label_of(s["n"]), 1
                if not item:
                    for j in (2, 3):
                        grp = segs[k:k + j]
                        if len(grp) < j or not all(_same_line(grp[0], g) for g in grp):
                            break
                        n = "".join(g["n"] for g in grp)
                        if _label_of(n) and not any(grp[a]["r"] - 1 <= v[0] <= grp[a + 1]["l"] + 1 and v[1] <= (s["t"] + s["b"]) / 2 <= v[2]
                                                    for a in range(j - 1) for v in vs):
                            item, span = _label_of(n), j
                            lab = {"text": " ".join(g["text"] for g in grp), "n": n, "l": grp[0]["l"], "r": grp[-1]["r"],
                                   "t": min(g["t"] for g in grp), "b": max(g["b"] for g in grp)}
                            break
                if item:
                    reg = _region(lab, segs, hs, vs, info["w"], item)
                    if reg and reg["w"] >= 20 and reg["h"] >= 8:
                        if item == "debtor_addr":  # 위쪽 가까운 낱말이 원고·채권자면 우리 회사 주소
                            near = [x for x in out if x["p"] == pi and x.get("item") in ("company", "debtor") and 0 < lab["t"] - x["y"] < 45]
                            if near and near[-1]["item"] == "company":
                                item = "company_addr"
                        f = {"p": pi, "type": "over" if reg.get("over") else "long" if reg["h"] > max(2.3 * (lab["b"] - lab["t"]), 26) else "text",
                             "item": item, "x": reg["x"], "y": reg["y"], "w": reg["w"], "h": reg["h"], "sug": True, "found": lab["text"].strip()}
                        if reg.get("over"):
                            f["orig"] = reg["over"]
                        if item == "date":
                            f["fmt"] = "dot"
                        if item == "amount":
                            f["fmt"] = "num"
                        if item == "case_no":
                            f["fmt"] = "tight"
                        if item == "new_addr":
                            f["optional"] = True
                        out.append(f)
                k += span
    finally:
        doc.close()
    # 겹치는 제안은 앞의 것만
    keep = []
    for f in out:
        if any(g["p"] == f["p"] and _overlap(f, g) > 0.5 for g in keep):
            continue
        keep.append({k: (round(v, 1) if isinstance(v, float) else v) for k, v in f.items()})
    keep.sort(key=lambda f: (f["p"], round(f["y"] / 6), f["x"]))
    return {"fields": keep, "scanned": nchars == 0, "pages": infos}


def _overlap(a, b):
    x = max(0, min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]))
    y = max(0, min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]))
    small = min(a["w"] * a["h"], b["w"] * b["h"]) or 1
    return x * y / small


# ------------------------------------------------------------------ 채우기

def _overlay(pages, fields, vals, kind, seal):
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    first = pages[0]
    c = canvas.Canvas(buf, pagesize=(first["w"] + first["cl"], first["ct"]))
    for pi, info in enumerate(pages):
        c.setPageSize((info["w"] + info["cl"], info["ct"]))
        cl, ct = info["cl"], info["ct"]
        for f in fields:
            if f.get("p", 0) != pi or not f.get("item"):
                continue
            X, top = cl + f["x"], ct - f["y"]
            k = f["item"]
            if f["type"] == "check":
                if vals.get(k) == f.get("opt"):
                    w, h = f["w"], f["h"]
                    c.setLineWidth(max(1, w * 0.12))
                    p = c.beginPath()
                    p.moveTo(X + 0.18 * w, top - 0.55 * h)
                    p.lineTo(X + 0.42 * w, top - 0.82 * h)
                    p.lineTo(X + 0.88 * w, top - 0.15 * h)
                    c.drawPath(p, stroke=1, fill=0)
                continue
            if f["type"] == "seal":
                if vals.get("__seal") and seal and os.path.isfile(seal):
                    c.drawImage(seal, X, top - f["h"], f["w"], f["h"], mask="auto", preserveAspectRatio=True, anchor="c")
                continue
            text = fmt_value(k, f.get("fmt"), vals.get(k))
            if f["type"] == "over":  # 원래 글자를 하얗게 가린다
                c.setFillColorRGB(1, 1, 1)
                c.rect(X, top - f["h"], f["w"], f["h"], stroke=0, fill=1)
                c.setFillColorRGB(0, 0, 0)
            if not text:
                continue
            if f.get("suffix"):
                text += f["suffix"]
            r = layout(f, text, kind)
            bold = f["type"] == "over"
            c.setFont(font_name(kind, bold), r["px"])
            if f["type"] == "long":
                y = top - r["px"] * 1.05 - 1
                for line in r["lines"]:
                    c.drawString(X + 2, y, line)
                    y -= r["px"] * 1.3
            else:
                c.drawString(X + 2, top - f["h"] / 2 - r["px"] * 0.35, text)
        c.showPage()
    c.save()
    return buf.getvalue()


def build(src, pages, fields, value_sets, out, kind="myeongjo", seal=None):
    """원본 양식 위에 값을 얹어 PDF 하나로 저장한다 (value_sets 하나당 양식 한 벌)."""
    from pypdf import PdfReader, PdfWriter
    with open(src, "rb") as f:
        data = f.read()
    w = PdfWriter()
    for vals in value_sets:
        base = PdfReader(io.BytesIO(data))  # 사람마다 새로 읽어 쪽이 섞이지 않게
        ov = PdfReader(io.BytesIO(_overlay(pages, fields, vals, kind, seal)))
        for i, pg in enumerate(base.pages):
            if i < len(ov.pages):
                pg.merge_page(ov.pages[i])
            w.add_page(pg)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "wb") as f:
        w.write(f)
    return out


def print_file(path):
    """기본 PDF 프로그램으로 인쇄 (Windows)."""
    if sys.platform == "win32":
        os.startfile(path, "print")  # noqa
        return True
    return False
