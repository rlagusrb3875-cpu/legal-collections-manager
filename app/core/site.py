# -*- coding: utf-8 -*-
"""나의사건검색(ssgo.scourt.go.kr)과 주고받기.

사람이 사이트에서 하는 것과 같은 순서로 요청한다.
  1) 자동입력방지 그림 받기  (그림 + 사이트가 준 암호 답)
  2) 사람이 입력한 숫자 + 암호 답으로 일반내용 조회
  3) 같은 값으로 진행내용 조회
자동입력방지 문자는 프로그램이 풀지 않는다. 사람이 입력한 값을 그대로 보낸다.
"""
import http.cookiejar
import json
import re
import ssl
import time
import urllib.error
import urllib.request


def _log(kind, detail):
    try:
        from appbase import log_event
        log_event(kind, detail)
    except Exception:
        pass

BASE = "https://ssgo.scourt.go.kr"
ENTRY = BASE + "/ssgo/index.on?cortId=www"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0")

LIST_NAMES = {
    "dlt_btprtCttLst": "당사자", "dlt_agntCttLst": "대리인", "dlt_rcntDxdyLst": "최근 기일",
    "dlt_inscrtDtsLst": "심급", "dlt_reltCsLst": "관련 사건", "dlt_rcntSbmsnDocmtLst": "최근 제출서류",
    "dlt_lwstRltnrCttLst": "소송관계인", "dlt_hrngProgCurst": "심리 진행 현황", "dlt_aplntCttLst": "참가인",
}


class SiteError(Exception):
    """kind: captcha(숫자 틀림) / notfound(사건 없음) / blocked(접속 막힘) / network / site(그 밖)"""

    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


def _ssl_context():
    # 회사 PC 의 보안 인증서까지 믿도록 운영체제 인증서 저장소를 쓴다
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:
        return ssl.create_default_context()


def classify(message):
    m = message or ""
    if re.search(r"자동\s*입력|방지\s*문자|보안\s*문자|캡차|캡챠|captcha", m, re.I):
        return "captcha"
    if re.search(r"없습니다|존재하지|조회된?\s*(결과|내용|사건)이?\s*없|일치하는|확인하(여|시)", m):
        return "notfound"
    if re.search(r"차단|과도|접근이 제한|비정상", m):
        return "blocked"
    return "site"


class Court:
    def __init__(self, meta, timeout=20):
        self.meta = meta
        self.timeout = timeout
        self._new_session()

    def _new_session(self):
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar), urllib.request.HTTPSHandler(context=_ssl_context()))
        self.started = False

    # ------------------------------------------------------------ 기본 통신

    def _open(self, req):
        try:
            return self.op.open(req, timeout=self.timeout)
        except urllib.error.HTTPError as ex:
            if ex.code in (403, 429):
                raise SiteError("blocked", f"법원 사이트가 접속을 막았습니다 (HTTP {ex.code}). 잠시 뒤 다시 해 주세요.")
            # 사이트는 업무 오류(숫자 틀림, 사건 없음 등)도 오류 번호와 함께 JSON 안내문으로 보낸다
            msg = ""
            try:
                msg = _message(json.loads(ex.read().decode("utf-8", "replace")))
            except Exception:
                pass
            if msg:
                raise SiteError(classify(msg), msg)
            _log(f"나의사건검색 HTTP {ex.code}", req.full_url)
            raise SiteError("site", f"법원 사이트 응답 오류 (HTTP {ex.code})")
        except (urllib.error.URLError, TimeoutError, OSError) as ex:
            reason = getattr(ex, "reason", ex)
            raise SiteError("network", f"법원 사이트에 연결하지 못했습니다: {reason}")

    def start(self):
        if self.started:
            return
        self._open(urllib.request.Request(ENTRY, headers={"User-Agent": UA})).read()
        self.started = True

    def get_text(self, path):
        return self._open(urllib.request.Request(BASE + path, headers={"User-Agent": UA})).read().decode("utf-8", "replace")

    def post(self, path, body):
        self.start()
        req = urllib.request.Request(BASE + path, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers={
            "User-Agent": UA, "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json, text/plain, */*", "Origin": BASE, "Referer": ENTRY,
            "X-Requested-With": "XMLHttpRequest"})
        raw = self._open(req).read().decode("utf-8", "replace")
        try:
            return json.loads(raw)
        except ValueError:
            _log("나의사건검색 응답이 JSON 아님", path + "\n" + raw[:2000])
            if "<html" in raw[:500].lower():
                raise SiteError("site", "법원 사이트가 데이터 대신 화면을 보냈습니다 (점검 중이거나 접속이 끊김)")
            raise SiteError("site", "법원 사이트 응답을 읽지 못했습니다")

    # ------------------------------------------------------------ 자동입력방지 그림

    def captcha(self):
        """{"image": PNG base64, "audio": WAV base64, "token": 사이트가 준 암호 답}"""
        res = self.post("/ssgo/ssgo10l/getCaptchaInf.on", {})
        info = (res.get("data") or {}).get("dma_captchaInf") or {}
        if not info.get("image") or not info.get("answer"):
            raise SiteError("site", _message(res) or "자동입력방지 그림을 받지 못했습니다")
        return {"image": info["image"], "audio": info.get("audio", ""), "token": info["answer"], "at": time.time()}

    # ------------------------------------------------------------ 사건 조회

    def resolve(self, case):
        """사건 대장의 한 줄 → 사이트에 넣을 값. 문제가 있으면 SiteError('input')"""
        court = self.meta.court(case.get("court_code") or "") or self.meta.court(case.get("court") or "")
        if not court:
            raise SiteError("input", f"법원 이름을 알 수 없습니다: {case.get('court')}")
        dvs = case.get("dvs") or ""
        code = self.meta.case_type_code(court["code"], dvs)
        if not code:
            raise SiteError("input", f"사건구분을 알 수 없습니다: {dvs}")
        task = self.meta.task_of(code, dvs)
        if not task:
            raise SiteError("input", f"이 사건구분({dvs})은 나의사건검색에서 조회할 수 없습니다")
        return court, code, task

    def search(self, case, answer, token, party=None):
        """숫자(answer)와 사이트 암호 답(token)으로 일반내용·진행내용을 함께 가져온다."""
        court, code, task = self.resolve(case)
        t = self.meta.task(task)
        name = (party if party is not None else case.get("party") or "").strip()
        base = {
            "cortCd": court["code"], "csYear": str(case["year"]), "csDvsCd": code, "csDvsNm": case["dvs"],
            "csSerial": str(case["serial"]), "btprtNm": name, "captchaAnswer": str(answer).strip() + token,
            "csNo": "", "encCsNo": "",
        }
        g_action = (t.get("gnrl") or {}).get("action")
        if not g_action:
            raise SiteError("input", "이 사건 종류의 조회 주소를 찾지 못했습니다")
        res = self.post(g_action, {"dma_search": dict(base)})
        gdata = res.get("data") or {}
        bas = gdata.get("dma_csBasCtt") or {}
        if not bas.get("csNo") and not bas.get("csNm"):
            if not _message(res):  # 안내문도 없이 자료가 비어 있음 → 응답 모양이 바뀌었을 수 있음
                _log("나의사건검색 일반내용 모양이 다름", json.dumps(res, ensure_ascii=False)[:3000])
            msg = _message(res) or "사건을 찾지 못했습니다"
            raise SiteError(classify(msg) if classify(msg) != "site" else "notfound", msg)

        out = {"task": task, "court_code": court["code"], "dvs_code": code,
               "basic": bas, "lists": {k: v for k, v in gdata.items() if isinstance(v, list)},
               "prog": [], "prog_error": ""}
        p = t.get("prog") or {}
        if p.get("action"):
            try:
                out["prog"] = self._prog(p, base, bas)
            except SiteError as ex:
                out["prog_error"] = str(ex)
        return out

    def _prog(self, p, base, bas):
        rows, page = [], 1
        while True:
            q = dict(base, progCttDvs="0", pageNo=page, totalYn="Y" if page == 1 else "N", inqScop="01")
            if bas.get("encCsNo"):
                q["encCsNo"] = bas["encCsNo"]
            body = {"dma_search": q}
            if "dma_pageInfo" in (p.get("ref") or []):
                body["dma_pageInfo"] = {"pageNo": str(page), "pageSize": "", "bfPageNo": "", "startRowNo": "",
                                        "totalCnt": "", "totalYn": q["totalYn"], "maxPageSize": ""}
            res = self.post(p["action"], body)
            data = res.get("data") or {}
            got = data.get("dlt_csProgCtt")
            if got is None:
                if page == 1:
                    raise SiteError(classify(_message(res)), _message(res) or "진행내용을 받지 못했습니다")
                break
            new = [r for r in got if r not in rows]
            rows += new
            total = int(str((data.get("dma_pageInfo") or {}).get("totalCnt") or 0) or 0)
            if not new or not total or len(rows) >= total or page >= 50:
                break
            page += 1
        return rows


def _message(res):
    if not isinstance(res, dict):
        return ""
    errs = res.get("errors")
    if isinstance(errs, list) and errs:
        e = errs[0]
        return (e.get("message") or e.get("msg") or str(e)) if isinstance(e, dict) else str(e)
    if isinstance(errs, dict):
        return errs.get("message") or ""
    msg = (res.get("message") or "").strip()
    if res.get("status") not in (None, 200, "200") or "완료" not in msg:
        return msg
    return ""
