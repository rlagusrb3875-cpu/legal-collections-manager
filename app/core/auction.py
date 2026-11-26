# -*- coding: utf-8 -*-
"""법원경매정보(courtauction.go.kr) 경매사건 — 프로그램 안 브라우저 창 방식.

프로그램이 사이트에 따로 요청하지 않는다. 프로그램 안에 사이트 화면을 그대로 열고,
그 화면이 사이트에서 받은 자료(사건내역 · 기일내역 · 문건/송달내역)를 옆에서 읽어 저장한다.
사이트의 로봇 탐지는 그대로 작동하며, 걸리면 그 안내를 보여주고 멈춘다.
"""
import datetime as dt
import json
import os
import re
import threading
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
COURTS_FILE = os.path.join(os.path.dirname(HERE), "data", "auction_courts.json")
SEARCH_URL = "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ159M00.xml"

# 사이트 화면이 받는 자료를 옆에서 모아 두는 코드 (화면 동작은 바꾸지 않음)
HOOK_JS = r"""(function(){ if(window.__cshHooked) return 'already'; window.__cshHooked=true; window.__csh=[];
 const keep=/selectAuctnCsSrchRslt|selectCsDtlDxdyDts|selectDlvrOfdocDtsDtl/;
 const O=XMLHttpRequest.prototype.open, S=XMLHttpRequest.prototype.send;
 XMLHttpRequest.prototype.open=function(m,u){this.__u=u;return O.apply(this,arguments)};
 XMLHttpRequest.prototype.send=function(b){ if(keep.test(this.__u||'')){ const x=this; x.addEventListener('load',function(){ try{window.__csh.push({u:x.__u,b:String(b||''),s:x.status,t:x.responseText,at:Date.now()})}catch(e){} }); } return S.apply(this,arguments)};
 return 'hooked'; })()"""


def fill_js(court_code, year, serial, press=True):
    """검색칸에 법원·연도·번호를 넣고, press=True 면 「검색」도 누른다. 받은 자료 목록도 비운다."""
    return """(function(){ try { var w=$p.main().wfm_mainFrame.getWindow(); var c=function(i){return w.$p.getComponentById(i)};
  if(!c('ibx_auctnCsSrchCsNo')) return 'notready';
  window.__csh=[]; c('sbx_auctnCsSrchCortOfc').setValue(%s); c('sbx_auctnCsSrchCsYear').setValue(%s); c('ibx_auctnCsSrchCsNo').setValue(%s);
  window.__cshFilled=%s; %s return 'filled'; } catch(e) { return 'err:' + e; } })()""" % (
        json.dumps(court_code), json.dumps(str(year)), json.dumps(str(serial)), json.dumps(f"{year}타경{serial}"),
        "setTimeout(function(){ var b=document.getElementById('mf_wfm_mainFrame_btn_auctnCsSrchBtn'); if(b) b.click(); }, 700);" if press else "")


# 검색칸이 준비됐는지 (사이트 화면이 다 떴는지)
READY_JS = r"""(function(){ var r={hook:!!window.__cshHooked, ready:false, src:''};
 try { var f=$p.main().wfm_mainFrame; r.src=f.getSrc ? f.getSrc() : ''; r.ready=!!f.getWindow().$p.getComponentById('ibx_auctnCsSrchCsNo'); } catch(e) {}
 return JSON.stringify(r); })()"""

# 결과 화면 → 처음 검색 화면으로 (사이트의 「이전」과 같은 방식, 새로 고침 없이)
BACK_JS = r"""(function(){ try { $p.main().wfm_mainFrame.setSrc('/pgj/ui/pgj100/PGJ159M01.xml', {dataObject:{type:'json', name:'param', data:{}}}); return 'back'; }
 catch(e) { return 'err:' + e; } })()"""


TABS_JS = r"""(function(){ var ids=['mf_wfm_mainFrame_tac_srchRsltDvs_tab_tabs2_tabHTML','mf_wfm_mainFrame_tac_srchRsltDvs_tab_tabs3_tabHTML'];
 ids.forEach(function(id,i){ setTimeout(function(){ var a=document.getElementById(id); if(a) a.click(); }, 1200 + i*1800); });
 setTimeout(function(){ var a=document.getElementById('mf_wfm_mainFrame_tac_srchRsltDvs_tab_tabs1_tabHTML'); if(a) a.click(); }, 1200 + 2*1800 + 600);
 return 'ok'; })()"""

READ_JS = "JSON.stringify({c:(window.__csh||[]).length, h:!!window.__cshHooked, f:window.__cshFilled||'', l:(window.__csh||[]).slice(%d)})"


def load_courts():
    with open(COURTS_FILE, encoding="utf-8") as f:
        return json.load(f)


_CASE = re.compile(r"(\d{4})\s*타\s*경\s*(\d{1,7})")


def parse_auction_no(text):
    m = _CASE.search(str(text or "").replace(",", ""))
    return (int(m.group(1)), str(int(m.group(2)))) if m else None


def ymd(s):
    d = re.sub(r"[^\d]", "", str(s or ""))[:8]
    try:
        return dt.date(int(d[:4]), int(d[4:6]), int(d[6:8])) if len(d) == 8 else None
    except ValueError:
        return None


def won(v):
    d = re.sub(r"[^\d]", "", str(v or ""))
    return f"{int(d):,}원" if d else ""


def who_of(text):
    t = text or ""
    if t.startswith("채권자"):
        return "채권자"
    if t.startswith(("채무자", "소유자")):
        return "채무자·소유자"
    if re.match(r"^(법원|집행관|감정인|등기소|등기관|경매|매각|배당|최고가매수인|매수인)", t):
        return "법원·집행관·감정인"
    return "이해관계인"


# ---------------------------------------------------------------- 화면이 받은 자료 → 저장할 모양

def digest(captures):
    """캡처 목록 → {gnrl, dates, docs, notfound, robot}"""
    out = {"gnrl": None, "dates": None, "docs": None, "notfound": "", "robot": ""}
    for cap in captures:
        try:
            j = json.loads(cap.get("t") or "{}")
        except ValueError:
            continue
        d = j.get("data") or {}
        url = cap.get("u") or ""
        if isinstance(d, dict) and d.get("ipcheck") is False:
            out["robot"] = j.get("message") or "법원경매정보가 자동 접속으로 판단해 막았어요"
            continue
        if "selectAuctnCsSrchRslt" in url:
            if not (d or {}).get("dma_csBasInf"):
                out["notfound"] = j.get("message") or "사건을 찾지 못했어요"
            else:
                out["gnrl"] = d
        elif "selectCsDtlDxdyDts" in url:
            out["dates"] = d
        elif "selectDlvrOfdocDtsDtl" in url:
            out["docs"] = d
    return out


def doc_key(r):
    return "|".join(str(r.get(k) or "").strip() for k in ("ofdocRcptYmd", "rcptDts", "dlvrbkRegYmd", "dlvrDts"))


class AuctionStore:
    """채권 폴더 안의 auctions.json + auction/<id>.json"""

    def __init__(self, root):
        self.root = root
        self.lock = threading.RLock()
        os.makedirs(os.path.join(root, "auction"), exist_ok=True)
        self.items = self._read(os.path.join(root, "auctions.json"), {})
        self.runs = self._read(os.path.join(root, "auction_runs.json"), [])
        self.rev = 0

    @staticmethod
    def _read(p, default):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def _write(self, p, data):
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, p)

    def save(self):
        self.rev += 1
        with self.lock:
            self._write(os.path.join(self.root, "auctions.json"), self.items)

    def add(self, court, court_code, year, serial, memo1="", owner=""):
        with self.lock:
            for a in self.items.values():
                if a["court_code"] == court_code and a["year"] == year and a["serial"] == serial:
                    if memo1 and not a.get("memo1"):
                        a["memo1"] = memo1
                    a["archived"] = False
                    return a, False
            aid = uuid.uuid4().hex[:10]
            a = {"id": aid, "court": court, "court_code": court_code, "year": year, "serial": serial,
                 "case_no": f"{year}타경{serial}", "memo1": memo1, "owner": owner, "archived": False,
                 "added": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "last_checked": "", "last_result": "",
                 "csNm": "", "claim": "", "status": "", "color": "", "next_sale": {}, "last_doc": {}, "new_docs": 0,
                 "debtor": "", "jdbn": ""}
            self.items[aid] = a
            return a, True

    # ---- 경매 조회 기록 (프로그램을 꺼도 이어서 할 수 있게)
    def new_run(self, ids, name="경매 조회"):
        run = {"id": uuid.uuid4().hex[:8], "name": name, "created": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               "finished": "", "ids": list(ids), "done": []}
        self.runs.insert(0, run)
        self.runs = self.runs[:100]
        self.save_runs()
        return run

    def run(self, rid):
        return next((r for r in self.runs if r["id"] == rid), None)

    def save_runs(self):
        with self.lock:
            self._write(os.path.join(self.root, "auction_runs.json"), self.runs)

    def result(self, aid):
        return self._read(os.path.join(self.root, "auction", aid + ".json"), {"checks": [], "docs": [], "dlvr": []})

    def record(self, aid, got):
        """사건내역·기일·문건/송달 저장. 새 문건/송달 수를 돌려준다."""
        a = self.items[aid]
        res = self.result(aid)
        first = not res["checks"]
        now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new = 0
        if got.get("docs"):
            for kind, rows in (("docs", got["docs"].get("dlt_ofdocDtsLst") or []), ("dlvr", got["docs"].get("dlt_dlvrDtsLst") or [])):
                known = {r.get("_k") or doc_key(r) + "#1" for r in res[kind]}
                seen = {}
                for r in rows:
                    base = doc_key(r)
                    seen[base] = seen.get(base, 0) + 1  # 같은 날 같은 내용이 여러 줄이어도 모두 남긴다
                    k = f"{base}#{seen[base]}"
                    if k in known:
                        continue
                    known.add(k)
                    row = dict(r, _seen=now, _first=first, _k=k)
                    res[kind].append(row)
                    if not first:
                        new += 1
                datekey = "ofdocRcptYmd" if kind == "docs" else "dlvrbkRegYmd"
                res[kind].sort(key=lambda r: (str(r.get(datekey) or ""), r.get("_seen", "")), reverse=True)
        if got.get("gnrl"):
            res["gnrl"] = got["gnrl"]
        if got.get("dates"):
            res["dates"] = got["dates"].get("dlt_dxdyDtsLst") or []
        res["checks"].append({"at": now, "new": new, "parts": [k for k in ("gnrl", "dates", "docs") if got.get(k)]})
        res["checks"] = res["checks"][-60:]
        with self.lock:
            self._write(os.path.join(self.root, "auction", aid + ".json"), res)
        self.rev += 1
        a["last_checked"] = now
        a["last_result"] = "ok"
        a["new_docs"] = new
        summarize(a, res)
        self.save()
        return new


DONE_WORDS = ("매각허가", "대금납부", "배당", "최고가매각", "매각")


def summarize(a, res):
    """목록에 보여줄 요약: 사건명·청구금액·상태·다음 매각기일·최근 문건"""
    g = res.get("gnrl") or {}
    b = g.get("dma_csBasInf") or {}
    a["csNm"] = b.get("csNm", a.get("csNm", ""))
    a["related_nos"] = [r.get("userReltCsNo") for r in (g.get("dlt_rletReltCsLst") or []) if r.get("userReltCsNo")]
    a["claim"] = won(b.get("clmAmt")) or a.get("claim", "")
    a["jdbn"] = b.get("cortAuctnJdbnNm", "")
    debt = [r.get("intrpsNm") for r in (g.get("dlt_rletCsIntrpsLst") or []) if "채무자" in (r.get("auctnIntrpsDvsNm") or "")]
    a["debtor"] = debt[0] if debt else a.get("debtor", "")
    objs = g.get("dlt_rletCsDspslObjctLst") or []
    ultmt = next((o.get("ultmtNm") for o in objs if o.get("ultmtNm") and o.get("ultmtNm") != "미종국"), "")
    today = dt.date.today()
    dates = res.get("dates") or []

    def when(r):
        return ymd(r.get("dxdyTime"))
    past = [r for r in dates if when(r) and when(r) <= today and r.get("dxdyRslt")]
    fut = sorted([r for r in dates if when(r) and when(r) >= today], key=lambda r: when(r))
    flb = sum(1 for r in dates if "유찰" in (r.get("dxdyRslt") or ""))
    if ultmt or (b.get("ultmtDvsCd") not in (None, "", "000")):
        a["status"], a["color"] = (ultmt or "종국"), "gray"
    elif past:
        last = sorted(past, key=lambda r: when(r))[-1]
        rs = last.get("dxdyRslt") or ""
        if "유찰" in rs:
            a["status"], a["color"] = f"{flb}회 유찰", "orange"
        elif any(w in rs for w in DONE_WORDS) or any(w in (last.get("auctnDxdyKndNm") or "") for w in ("배당", "대금")):
            a["status"], a["color"] = (last.get("auctnDxdyKndNm") or "") + (" " + rs if rs else ""), "green"
        else:
            a["status"], a["color"] = rs or "진행", "blue"
    else:
        a["status"], a["color"] = "진행", "blue"
    a["status"] = a["status"].strip()
    if fut:
        r = fut[0]
        a["next_sale"] = {"date": when(r).isoformat(), "time": (re.search(r"\((\d{1,2}:\d{2})\)", r.get("dxdyTime") or "") or [None, ""])[1],
                          "kind": r.get("auctnDxdyKndNm", ""), "price": r.get("tsLwsDspslPrc", ""), "place": r.get("dxdyPlcNm", "")}
    else:
        a["next_sale"] = {}
    docs = sorted([(ymd(r.get("ofdocRcptYmd")), r.get("rcptDts", ""), "문건") for r in res.get("docs") or []] +
                  [(ymd(r.get("dlvrbkRegYmd")), (r.get("dlvrDts", "") + " · " + (r.get("lastDlvrblRchYmd") or "")).strip(" ·"), "송달")
                   for r in res.get("dlvr") or []], key=lambda x: (x[0] or dt.date.min), reverse=True)
    a["last_doc"] = {"date": docs[0][0].isoformat() if docs and docs[0][0] else "", "text": docs[0][1] if docs else "",
                     "kind": docs[0][2] if docs else ""}
    return a


def detail(a, res, today=None):
    """상세 화면용: 사건기본내역·배당요구종기·물건·당사자·관련사건·항고·기일·문건·송달"""
    g = res.get("gnrl") or {}
    b = g.get("dma_csBasInf") or {}

    def d(v):
        x = ymd(v)
        return x.isoformat() if x else ""
    basic = [("사건번호", b.get("userCsNo") or a["case_no"]), ("사건명", b.get("csNm", "")), ("법원", b.get("cortOfcNm") or a["court"]),
             ("접수일자", d(b.get("csRcptYmd"))), ("개시결정일자", d(b.get("csCmdcYmd"))), ("청구금액", won(b.get("clmAmt"))),
             ("담당계", " ".join(x for x in (b.get("cortAuctnJdbnNm"), b.get("jdbnTelno")) if x)),
             ("집행관사무소", b.get("execrCsTelno") or b.get("execrOfcTelno") or ""), ("사건진행정지사유", b.get("csProgSuspRsn") or ""),
             ("종국일자", d(b.get("csUltmtYmd")))]
    basic = [{"label": k, "value": v} for k, v in basic if v]

    def addr(r):
        return " ".join(x for x in (r.get("userSt") or " ".join(x for x in (r.get("adongSdNm"), r.get("adongSggNm"), r.get("adongEmdNm"), r.get("rprsLtnoAddr")) if x),
                                    r.get("bldNm") or "", (r.get("bldDtlDts") or "").strip()) if x)
    demand = [{"seq": r.get("dspslObjctSeq", ""), "addr": addr(r), "date": d(r.get("dstrtDemnLstprdYmd"))} for r in g.get("dlt_dstrtDemnLstprdDts") or []]
    goods = []
    for r in g.get("dlt_dspslGdsDspslObjctLst") or []:
        goods.append({"seq": r.get("dspslGdsSeq", ""), "addr": addr(r), "eval": won(r.get("aeeEvlAmt")),
                      "min": won(r.get("fothPbancLwsDspslPrc") or r.get("thrdPbancLwsDspslPrc") or r.get("scndPbancLwsDspslPrc") or r.get("fstPbancLwsDspslPrc")),
                      "sale": d(r.get("dspslDxdyYmd")), "time": (r.get("fstDspslHm") or "")[:2] + ":" + (r.get("fstDspslHm") or "")[2:] if r.get("fstDspslHm") else "",
                      "amount": won(r.get("dspslAmt")), "rmk": r.get("dspslGdsRmk", "")})
    parties = [{"kind": r.get("auctnIntrpsDvsNm", ""), "name": r.get("intrpsNm", "")} for r in g.get("dlt_rletCsIntrpsLst") or []]
    related = [{"court": r.get("cortOfcNm", ""), "no": r.get("userReltCsNo", ""), "kind": r.get("reltCsDvsNm", "")} for r in g.get("dlt_rletReltCsLst") or []]
    related += [{"court": r.get("cortOfcNm", "") or "", "no": r.get("userCsNo") or r.get("userDpcnMrgCsNo") or "", "kind": "중복/병합/이송"}
                for r in g.get("dlt_dpcnMrgTrnscsCsRlet") or []]
    appeal = [{"text": " ".join(str(v) for k, v in r.items() if v and not k.endswith("Cd") and k not in ("cortOfcCd", "csNo"))} for r in g.get("dlt_csApalRaplDts") or []]
    dates = [{"seq": r.get("dspslGdsSeq", ""), "time": r.get("dxdyTime", ""), "kind": r.get("auctnDxdyKndNm", ""), "place": r.get("dxdyPlcNm", ""),
              "eval": won(r.get("aeeEvlAmt")), "min": r.get("tsLwsDspslPrc", ""), "result": r.get("dxdyRslt", "")} for r in res.get("dates") or []]
    last_at = (res.get("checks") or [{}])[-1].get("at", "")[:19]
    docs = [{"date": d(r.get("ofdocRcptYmd")), "text": r.get("rcptDts", ""), "result": r.get("rcptRslt", ""), "who": who_of(r.get("rcptDts")),
             "new": (not r.get("_first")) and r.get("_seen", "")[:19] == last_at} for r in res.get("docs") or []]
    dlvr = [{"date": d(r.get("dlvrbkRegYmd")), "text": r.get("dlvrDts", ""), "result": r.get("lastDlvrblRchYmd", ""), "who": who_of(r.get("dlvrDts")),
             "new": (not r.get("_first")) and r.get("_seen", "")[:19] == last_at} for r in res.get("dlvr") or []]
    return {"case": a, "basic": basic, "demand": demand, "goods": goods, "parties": parties, "related": related,
            "appeal": appeal, "dates": dates, "docs": docs, "dlvr": dlvr, "checked": bool(res.get("checks")),
            "checks": len(res.get("checks") or [])}


# ---------------------------------------------------------------- 확인할 것 (경매)

BAD_DLVR = re.compile(r"폐문|부재|불명|불능|거절|이사|미거주|주소")


def norm_memo(s):
    """계좌번호 등 메모 맞추기용: 숫자·글자만 남김 (하이픈·띄어쓰기 무시)"""
    return re.sub(r"[^0-9A-Za-z가-힣]", "", str(s or ""))


def todos(au, settings, todo_state):
    """경매 결과에서 할 일: 새 문건·송달, 송달 안 됨(폐문부재 등), 매각기일 임박."""
    ts = settings.get("todo", {})
    today = dt.date.today()
    look = today - dt.timedelta(days=int(ts.get("lookback_days") or 60))
    near = today + dt.timedelta(days=int(ts.get("hearing_days") or 14))
    out = []

    def item(key, a, kind, color, date, text, due=""):
        st = todo_state.get(key, {})
        out.append({"key": key, "aid": a["id"], "cid": "", "kind": kind, "color": color, "date": date, "text": text,
                    "due": st.get("deadline") or due, "due_manual": bool(st.get("deadline")), "ask": False,
                    "done": st.get("done", ""), "done_note": st.get("note", ""), "done_by": st.get("by", ""), "new": True,
                    "auction": True, "case_no": a["case_no"], "party": a.get("debtor", ""), "court": a.get("court", ""),
                    "memo1": a.get("memo1", "")})
    for a in au.items.values():
        if a.get("archived") or not a.get("last_checked"):
            continue
        res = au.result(a["id"])
        newest = {}
        for kind, rows, dk, tk in (("경매 새 문건", res.get("docs") or [], "ofdocRcptYmd", "rcptDts"),
                                   ("경매 새 송달", res.get("dlvr") or [], "dlvrbkRegYmd", "dlvrDts")):
            for r in rows:
                d = ymd(r.get(dk))
                if r.get("_first") or not d or d < look:
                    continue
                if kind not in newest:
                    newest[kind] = 1
                    item(f"A|{a['id']}|{r.get('_k') or doc_key(r)}", a, kind, "orange", d.isoformat(), r.get(tk, ""))
        for r in res.get("dlvr") or []:
            d = ymd(r.get("dlvrbkRegYmd"))
            rs = r.get("lastDlvrblRchYmd") or ""
            if d and d >= look and rs and "도달" not in rs and BAD_DLVR.search(rs):
                item(f"A|{a['id']}|dlvbad|{r.get('_k') or doc_key(r)}", a, "경매 송달 안 됨", "red", d.isoformat(),
                     f"{r.get('dlvrDts', '')} · {rs}", (d + dt.timedelta(days=7)).isoformat())
                break
        s = a.get("next_sale") or {}
        sd = ymd(s.get("date"))
        if sd and today <= sd <= near:
            item(f"A|{a['id']}|sale|{s['date']}", a, "매각기일", "blue", s["date"],
                 " ".join(x for x in (s.get("kind") or "매각기일", s.get("time"), "최저 " + s["price"] if s.get("price") else "") if x), s["date"])
    return out
