# -*- coding: utf-8 -*-
"""배당기일 — 엑셀로 내보내기 · 통계 보고서(HTML 한 파일)"""
import datetime as dt
import html as H

from . import dividend as DV
from .excel import _sheet, _wb

MATCH_COLS = [("채무자키", "dkey"), ("법조치키", "lkey"), ("채무자명", "debtor"), ("담당자명", "mgr"), ("법원", "court"), ("사건번호", "no"),
              ("제3채무자", "third"), ("배당기일", "date"), ("배당관련사건", "rel")]


def match_xlsx(path, rows):
    wb = _wb()
    _sheet(wb, "배당기일", [h for h, _ in MATCH_COLS], [[r.get(k, "") for _, k in MATCH_COLS] for r in rows if r.get("dkey")], first=True)
    _sheet(wb, "못 찾은 것", [h for h, _ in MATCH_COLS], [[r.get(k, "") for _, k in MATCH_COLS] for r in rows if not r.get("dkey")])
    wb.save(path)


def ledger_xlsx(path, rows, all_rows=None):
    """대장 · 진행 중 · 월별 수령 · 변경 기록 (all_rows 가 없으면 근거 목록처럼 한 시트)"""
    wb = _wb()
    head = [h for h, _ in DV.EXPORT_COLS]
    body = lambda L: [[DV.export_value(r, k) for _, k in DV.EXPORT_COLS] for r in L]
    _sheet(wb, "대장" if all_rows is not None else "목록", head, body(rows), first=True)
    if all_rows is not None:
        live = [r for r in all_rows if not r.get("deleted")]
        _sheet(wb, "진행 중", head, body([r for r in live if not DV.is_done(r)]))
        mon = {}
        for r in live:
            if r.get("recv") == "수령" and r.get("recv_at"):
                m = mon.setdefault(r["recv_at"][:7], [0, 0])
                m[0] += 1
                m[1] += int(r.get("amt") or 0)
        _sheet(wb, "월별 수령", ["월", "건수", "수령액"], [[k, v[0], v[1]] for k, v in sorted(mon.items())])
        logs = [[l[0], r.get("no", ""), r.get("lkey", ""), l[1], l[2]] for r in all_rows for l in r.get("log") or []]
        _sheet(wb, "변경 기록", ["때", "배당사건번호", "법조치키", "누가", "내용"], sorted(logs, reverse=True))
    wb.save(path)


def stats_xlsx(path, rows, f, dash, nopay_n):
    D = DV.dashboard(rows, f, dash, nopay_n)
    S = DV.Stats(rows, f)
    T = D["total"]
    wb = _wb()
    pct = lambda v: "" if v is None else round(v * 100, 1)
    _sheet(wb, "요약", ["항목", "값"], [["기간", DV.PERIODS.get(f["period"], f["period"])], ["기준", "수령일" if f["basis"] == "recv" else "배당기일"],
                                       ["배당 건수", T["n"]], ["배당액", T["amt"]], ["회수액", T["got"]], ["회수율(%)", pct(T["rate"])],
                                       ["배당률(%)", pct(T["yld"])], ["미수령 잔액", D["unpaid"]], ["배당 없음", T["none"]],
                                       ["기일→수령 중앙값(일)", T["m_d2r"] or ""]], first=True)
    _sheet(wb, "월별", ["월", "건수", "배당액", "회수액", "아직 안 받음", "배당 없음"], [[g["k"], g["n"], g["amt"], g["got"], g["wait"], g["none"]] for g in D["monthly"]])
    _sheet(wb, "앞으로 들어올 돈", ["구분", "건수", "확정 배당액", "추정액"], [[x["t"], x["n"], x["known"], x["est"]] for x in D["forecast"]["rows"]])
    _sheet(wb, "미수령 경과", ["구분", "건수", "금액"], [[b["t"], b["n"], b["amt"]] for b in D["aging"]["buckets"]])
    for d, t in (("third", "제3채무자별"), ("mgr", "담당자별"), ("court", "법원별")):
        _sheet(wb, t, [t[:-1], "건수", "배당액", "회수액", "회수율(%)", "배당률(%)", "배당 없음", "기일→발송(일)", "기일→수령(일)", "할 일"],
               [[g["k"], g["n"], g["amt"], g["got"], pct(g["rate"]), pct(g["yld"]), g["none"], g["m_d2s"] or "", g["m_d2r"] or "", g["todo"]] for g in D["by"][d]])
    _sheet(wb, "근거 (줄 전체)", [h for h, _ in DV.EXPORT_COLS], [[DV.export_value(r, k) for _, k in DV.EXPORT_COLS] for r in S.rows()])
    wb.save(path)


# ---------------------------------------------------------------- 보고서 (A4 인쇄용 HTML 한 파일)

def _man(v):
    return f"{int(round((v or 0) / 10000)):,}"


def _pct(v):
    return "—" if v is None else f"{v * 100:.0f}%"


def report_html(rows, f, dash, nopay_n, book, me, cond):
    e = H.escape
    D = DV.dashboard(rows, f, dash, nopay_n)
    S = DV.Stats(rows, f)
    A, P = D["total"], D["prev"]
    ms = D["months"]
    M = lambda v: _man(v) + "만"

    def dl(a, b):
        if not b:
            return '<span class="d">전년 자료 없음</span>'
        d = (a - b) / b * 100
        return f'<span class="d {"up" if d >= 0 else "dn"}">{"▲" if d >= 0 else "▼"} {abs(d):.0f}% 전년 같은 기간</span>'

    AG, FC = D["aging"], D["forecast"]
    by = {r["id"]: r for r in S.all}
    unpaid, late_d = D["unpaid"], int(dash.get("lateD", 31))
    late = sum(b["amt"] for b in AG["buckets"] if b["from"] >= late_d)
    late_n = sum(b["n"] for b in AG["buckets"] if b["from"] >= late_d)
    fc90 = sum(x["known"] + x["est"] for x in FC["rows"][1:4])
    fc90n = sum(x["n"] for x in FC["rows"][1:4])
    data = D["monthly"]
    mx = DV_nice(max([g["got"] + g["wait"] for g in data] + [0]) * 1.12)
    W, Hh, L, B, T = 680, 210, 54, 28, 14
    pw, ph = W - L - 8, Hh - B - T
    bw = min(22, pw / max(1, len(data)) * .6)
    svg = [f'<svg viewBox="0 0 {W} {Hh}" width="100%" role="img" aria-label="월별 배당액">']
    for fr in (0, .25, .5, .75, 1):
        y = T + ph - ph * fr
        svg.append(f'<line x1="{L}" x2="{W - 8}" y1="{y}" y2="{y}" stroke="{"#e6e6e4" if fr else "#c9c9c6"}"/>'
                   f'<text x="{L - 8}" y="{y + 4}" text-anchor="end" font-size="10" fill="#8a8a90">{M(mx * fr) if fr else "0"}</text>')
    best = max(data, key=lambda g: g["got"] + g["wait"]) if data else None
    for i, g in enumerate(data):
        cx = L + pw / len(data) * (i + .5)
        x = cx - bw / 2
        hg, hw, y0 = g["got"] / mx * ph, g["wait"] / mx * ph, T + ph
        if hg > 0:
            svg.append(_col(x, y0, hg, bw, "#256abf", not hw))
        if hw > 0:
            svg.append(_col(x, y0 - hg - (2 if hg else 0), hw, bw, "#86b6ef", True))
        if best is g and g["got"] + g["wait"] > 0:
            svg.append(f'<text x="{cx}" y="{y0 - hg - hw - 6}" text-anchor="middle" font-size="10.5" font-weight="700" fill="#141414">{M(g["got"] + g["wait"])}</text>')
        svg.append(f'<text x="{cx}" y="{Hh - 10}" text-anchor="middle" font-size="10" fill="#66666b">{int(g["k"][5:])}월</text>')
    svg.append("</svg>")

    def bar(v, mx_, cls=""):
        return f'<span class="b"><i class="{cls}" style="width:{(v / mx_ * 100) if mx_ else 0:.1f}%"></i></span>'

    def dim_table(dim, title):
        G = sorted(DV.Stats(rows, f).agg(S.rows(dim), lambda r: r.get(dim), nopay_n), key=lambda g: -g["amt"])
        tot = sum(g["amt"] for g in G) or 1
        mxx = max([g["amt"] for g in G] + [1])
        show, rest = G[:10], G[10:]
        h = [f'<table><thead><tr><th>{title}</th><th class="n">건수</th><th>배당액</th><th class="n">비율</th><th class="n">회수율</th><th class="n">배당률</th>'
             f'<th class="n">0원</th><th class="n">기일→수령</th>{"<th class=n>할 일</th>" if dim == "mgr" else ""}</tr></thead><tbody>']
        for g in show:
            todo_cell = f'<td class="n">{g["todo"]}</td>' if dim == "mgr" else ""
            d2r = g["m_d2r"] if g["m_d2r"] is not None else "—"
            h.append(f'<tr class="{"hl" if f.get(dim) == g["k"] else ""}"><td>{e(g["k"])}</td><td class="n">{g["n"]}</td><td class="bar">{bar(g["amt"], mxx)}<b>{M(g["amt"])}</b></td>'
                     f'<td class="n">{g["amt"] / tot * 100:.0f}%</td><td class="n">{_pct(g["rate"])}</td><td class="n">{_pct(g["yld"])}</td><td class="n">{g["none"]}</td>'
                     f'<td class="n">{d2r}일</td>{todo_cell}</tr>')
        if rest:
            ra = sum(g["amt"] for g in rest)
            h.append(f'<tr class="rest"><td>그 외 {len(rest)}곳</td><td class="n">{sum(g["n"] for g in rest)}</td><td class="bar"><b>{M(ra)}</b></td>'
                     f'<td class="n">{ra / tot * 100:.0f}%</td><td></td><td></td><td class="n">{sum(g["none"] for g in rest)}</td><td></td>{"<td></td>" if dim == "mgr" else ""}</tr>')
        h.append("</tbody></table>")
        return "".join(h)

    third = [g for g in D["by"]["third"] if g["n"] >= 3]
    best_y = max(third, key=lambda g: g["yld"] or 0) if third else None
    worst_z = max(third, key=lambda g: g["zero"]) if third else None
    courts = sorted([g for g in D["by"]["court"] if g["m_d2r"] is not None and g["n"] >= 3], key=lambda g: -g["m_d2r"])
    mg = sorted(DV.Stats(rows, f).agg(S.filtered(), lambda r: r.get("mgr"), nopay_n), key=lambda g: -g["todo"])
    fc_mx = max([x["known"] + x["est"] for x in FC["rows"]] + [1])
    ag_mx = max([b["amt"] for b in AG["buckets"]] + [1])
    basis = "수령일" if f["basis"] == "recv" else "배당기일"
    title = f"{book} 배당 통계 보고서"
    concl = [f'<li>회수: {DV.PERIODS.get(f["period"], "")} 배당 <b>{A["n"]}건 · {M(A["amt"])}</b> 중 <b>{M(A["got"])} ({_pct(A["rate"])})</b> 회수'
             + (f' · 전년 같은 기간보다 <b>{"늘었어요" if A["got"] >= P["got"] else "줄었어요"} ({(A["got"] - P["got"]) / P["got"] * 100:.0f}%)</b>' if P and P["got"] else "") + ".</li>",
             f'<li>미수령: 받을 돈 <b>{M(unpaid)}</b> 중 <b>발송 후 {late_d}일 넘은 {late_n}건 · {M(late)}</b>은 입금 확인이 필요해요.</li>',
             f'<li>전망: 앞으로 90일 안 배당기일 <b>{fc90n}건 · 약 {M(fc90)}</b> 들어올 예정이에요 (일부 추정).</li>']
    if best_y:
        concl.append(f'<li>제3채무자: 배당률이 가장 높은 곳은 <b>{e(best_y["k"])} ({_pct(best_y["yld"])})</b>'
                     + (f', 0원 배당이 가장 잦은 곳은 <b>{e(worst_z["k"])} ({_pct(worst_z["zero"])})</b>' if worst_z and worst_z["zero"] > 0 else "") + ".</li>")
    if courts:
        concl.append(f'<li>처리 속도: 기일→수령 중앙값 <b>{A["m_d2r"] if A["m_d2r"] is not None else "—"}일</b> · 가장 오래 걸리는 법원 '
                     f'<b>{e(courts[0]["k"])} {courts[0]["m_d2r"]}일</b>' + (f' · 할 일이 가장 많은 담당자 <b>{e(mg[0]["k"])} {mg[0]["todo"]}건</b>' if mg and mg[0]["todo"] else "") + ".</li>")
    old_rows = "".join(
        f'<tr><td>{e(by[x["id"]]["court"])}</td><td>{e(by[x["id"]]["no"])}</td><td>{e(by[x["id"]].get("dkey", ""))}</td><td>{e(by[x["id"]].get("third", ""))}</td>'
        f'<td>{e(by[x["id"]].get("mgr", ""))}</td><td>{"발송 · 입금 대기" if by[x["id"]].get("recv") == "발송" else "발송 전"}</td><td class="n"><b>{x["days"]}일</b></td>'
        f'<td class="n">{(format(int(by[x["id"]]["amt"]), ",") if by[x["id"]].get("amt") not in ("", None) else "—")}</td></tr>'
        for x in AG["old"][:12]) or '<tr><td colspan="8" class="sub">없어요</td></tr>'
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} · {DV.PERIODS.get(f["period"], "")}</title>
<style>{_CSS}</style></head><body>
<div class="tool"><button onclick="window.print()">인쇄 · PDF로 저장</button></div>
<div class="page">
<header><div><h1>{e(title)}</h1><div class="sub">{e(cond)}</div></div>
<div class="meta">기준일 {dt.date.today():%Y.%m.%d}<br>만든 사람 {e(me or "")}<br>자료: 배당 관리 대장 {len(S.rows())}줄</div></header>
<div class="concl"><h3>한눈에 보기</h3><ol>{"".join(concl)}</ol></div>
<div class="kpis">
 <div class="kpi"><span>배당액</span><b>{_man(A["amt"])}<small>만원</small></b>{dl(A["amt"], P and P["amt"])}</div>
 <div class="kpi"><span>회수액 (수령)</span><b>{_man(A["got"])}<small>만원</small></b>{dl(A["got"], P and P["got"])}</div>
 <div class="kpi"><span>배당률 (배당액 ÷ 청구액)</span><b>{"—" if A["yld"] is None else f'{A["yld"] * 100:.0f}'}<small>%</small></b><span class="d">{"전년 " + _pct(P["yld"]) if P and P["yld"] is not None else ""}</span></div>
 <div class="kpi"><span>미수령 잔액</span><b>{_man(unpaid)}<small>만원</small></b><span class="d {"bad" if late else ""}">{late_d}일 넘음 {M(late)}</span></div>
 <div class="kpi"><span>배당 없음 (0원)</span><b>{A["none"]}<small>건</small></b><span class="d">전체의 {_pct(A["zero"])}</span></div>
 <div class="kpi"><span>기일 → 수령 (중앙값)</span><b>{A["m_d2r"] if A["m_d2r"] is not None else "—"}<small>일</small></b><span class="d">발송까지 {A["m_d2s"] if A["m_d2s"] is not None else "—"}일 · 입금 {A["m_s2r"] if A["m_s2r"] is not None else "—"}일</span></div>
</div>
<h2>1. 월별 {"회수액" if f["basis"] == "recv" else "배당액"}</h2>
<div class="legend"><span><i style="background:#256abf"></i>수령</span>{"" if f["basis"] == "recv" else '<span><i style="background:#86b6ef"></i>아직 안 받음</span>'}<span>{basis} 기준</span></div>
{"".join(svg)}
<table class="mt"><thead><tr><th></th>{"".join(f'<th class="n">{int(g["k"][5:])}월</th>' for g in data)}<th class="n">합계</th></tr></thead><tbody>
<tr><td>건수</td>{"".join(f'<td class="n">{g["n"] or ""}</td>' for g in data)}<td class="n"><b>{A["n"]}</b></td></tr>
<tr><td>배당액(만)</td>{"".join(f'<td class="n">{_man(g["amt"]) if g["amt"] else ""}</td>' for g in data)}<td class="n"><b>{_man(A["amt"])}</b></td></tr>
<tr><td>회수액(만)</td>{"".join(f'<td class="n">{_man(g["got"]) if g["got"] else ""}</td>' for g in data)}<td class="n"><b>{_man(A["got"])}</b></td></tr>
</tbody></table>
<h2>2. 앞으로 들어올 돈 · 미수령 경과</h2>
<div class="two"><div><h3>앞으로 들어올 돈</h3><table><thead><tr><th>구분</th><th class="n">건수</th><th>금액</th></tr></thead><tbody>
{"".join(f'<tr><td>{x["t"]}</td><td class="n">{x["n"]}</td><td class="bar"><span class="b" style="display:inline-flex;background:none;gap:2px">' + (f'<i style="width:{x["known"] / fc_mx * 100:.1f}%"></i>' if x["known"] else "") + (f'<i class="e" style="width:{x["est"] / fc_mx * 100:.1f}%"></i>' if x["est"] else "") + f'</span><b>{M(x["known"] + x["est"])}</b></td></tr>' for x in FC["rows"])}
</tbody></table><div class="note">빗금 = 추정 (배당액을 아직 모르는 건: 청구액 × 평균 배당률 {_pct(FC["avg"])})</div></div>
<div><h3>미수령 경과 (배당기일 지난 건)</h3><table><thead><tr><th>구분</th><th class="n">건수</th><th>금액</th></tr></thead><tbody>
{"".join(f'<tr><td>{b["t"]}</td><td class="n">{b["n"]}</td><td class="bar">{bar(b["amt"], ag_mx, "r" if b["from"] >= late_d else "w")}<b>{M(b["amt"])}</b></td></tr>' for b in AG["buckets"])}
</tbody></table><div class="note">빨강 = 발송 후 {late_d}일 넘게 입금 없음 → 법원·제3채무자 확인 필요</div></div></div>
<h2>3. 조치가 필요한 건 (오래된 미수령)</h2>
<table><thead><tr><th>배당법원</th><th>배당사건번호</th><th>채무자키</th><th>제3채무자</th><th>담당</th><th>단계</th><th class="n">지난 날</th><th class="n">배당액</th></tr></thead><tbody>{old_rows}</tbody></table>
<h2 class="pb">4. 제3채무자별 — 어디서 회수가 되나</h2>{dim_table("third", "제3채무자")}
<div class="note">배당률이 높고 0원이 적은 제3채무자는 압류 대상 고를 때 우선 고려 · 0원이 잦은 곳은 선순위·공탁 사유 확인</div>
<h2>5. 법원별 — 처리 속도</h2>{dim_table("court", "법원")}
<h2>6. 담당자별 — 운영</h2>{dim_table("mgr", "담당자")}
<div class="note">할 일 = 검수 대기 + 기일 지남·발송 전 + 발송 후 {nopay_n}일 넘게 입금 없음 (기준일 현재)</div>
<footer>용어 · 배당액 = 배당표 금액 · 회수율 = 회수액 ÷ 배당액 · 배당률 = 배당액 ÷ 청구액(채권계산서 금액) · 0원 = 배당 없음 · 걸린 날은 중앙값<br>
종합관리 · 배당 통계 · {dt.date.today():%Y.%m.%d} 만듦 · 개인정보(채무자명)는 넣지 않고 채무자키만 표시</footer>
</div></body></html>"""


def DV_nice(v):
    if v <= 0:
        return 1
    import math
    p = 10 ** math.floor(math.log10(v))
    f = v / p
    for s in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if f <= s:
            return s * p
    return 10 * p


def _col(x, y0, h, bw, fill, top):
    if h <= 0:
        return ""
    if not top:
        return f'<rect x="{x:.1f}" y="{y0 - h:.1f}" width="{bw:.1f}" height="{h:.1f}" fill="{fill}"/>'
    r = min(4, h)
    return (f'<path d="M{x:.1f},{y0:.1f} V{y0 - h + r:.1f} Q{x:.1f},{y0 - h:.1f} {x + r:.1f},{y0 - h:.1f} H{x + bw - r:.1f} '
            f'Q{x + bw:.1f},{y0 - h:.1f} {x + bw:.1f},{y0 - h + r:.1f} V{y0:.1f} Z" fill="{fill}"/>')


_CSS = """@page{size:A4;margin:13mm 12mm}
*{box-sizing:border-box}
body{margin:0;background:#f5f5f4;color:#141414;font-family:Pretendard,"Malgun Gothic","Apple SD Gothic Neo",sans-serif;font-size:12.5px;letter-spacing:-.01em;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.page{max-width:794px;margin:20px auto;background:#fff;padding:34px 40px;border:1px solid #e6e6e4;border-radius:6px}
.tool{max-width:794px;margin:16px auto 0;display:flex;justify-content:flex-end;gap:8px}
.tool button{border:1px solid #141414;background:#141414;color:#fff;border-radius:8px;padding:7px 14px;font:inherit;cursor:pointer}
header{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:2px solid #141414;padding-bottom:12px;margin-bottom:16px;gap:16px}
h1{font-size:21px;margin:0 0 4px;letter-spacing:-.03em}
.meta{color:#66666b;font-size:11px;line-height:1.6;text-align:right;white-space:nowrap}
.sub{color:#66666b}
h2{font-size:14px;margin:24px 0 8px;padding-left:8px;border-left:3px solid #141414;break-after:avoid}
h3{font-size:12.5px;margin:14px 0 6px}
.concl{border:1.5px solid #141414;border-radius:8px;padding:12px 16px}
.concl h3{margin:0 0 6px;font-size:13px}
.concl ol{margin:0;padding-left:18px;line-height:1.8}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid #e6e6e4;border-radius:8px;margin-top:12px}
.kpi{padding:10px 12px;border-left:1px solid #e6e6e4;border-top:1px solid #e6e6e4}
.kpi:nth-child(3n+1){border-left:0}.kpi:nth-child(-n+3){border-top:0}
.kpi span{display:block;font-size:11px;color:#66666b}
.kpi b{display:block;font-size:19px;letter-spacing:-.03em;margin:2px 0}
.kpi b small{font-size:11px;color:#66666b;font-weight:500;margin-left:2px}
.d{font-size:10.5px;color:#8a8a90}.d.up{color:#1b8a4e}.d.dn{color:#cf3f3f}.d.bad{color:#cf3f3f}
.legend{display:flex;gap:14px;font-size:11px;color:#66666b;margin:4px 0 2px;flex-wrap:wrap}
.legend i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
table{width:100%;border-collapse:collapse;font-size:11.5px}
tr{break-inside:avoid}
th{text-align:left;font-weight:600;color:#66666b;border-bottom:1.5px solid #141414;padding:6px 6px;font-size:11px;white-space:nowrap}
td{padding:6px 6px;border-bottom:1px solid #ececea;vertical-align:middle}
.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
td.bar{min-width:150px}td.bar b{font-weight:600;margin-left:6px;white-space:nowrap}
.b{display:inline-block;width:55%;height:9px;vertical-align:middle;background:#f0f0ee;border-radius:0 3px 3px 0}
.b i{display:block;height:100%;background:#256abf;border-radius:0 3px 3px 0}.b i.w{background:#86b6ef}.b i.e{background:repeating-linear-gradient(135deg,#86b6ef 0 3px,#cfe0f8 3px 6px)}.b i.r{background:#cf3f3f}
tr.hl td{background:rgba(54,90,189,.07)}tr.rest td{color:#66666b}
.mt{margin-top:6px}
.note{font-size:11px;color:#66666b;line-height:1.6;margin-top:6px}
.pb{break-before:page}
footer{margin-top:26px;padding-top:10px;border-top:1px solid #e6e6e4;color:#8a8a90;font-size:10.5px;line-height:1.6}
@media print{body{background:#fff}.page{margin:0;max-width:none;border:0;padding:0}.tool{display:none}}"""
