# -*- coding: utf-8 -*-
"""상태 분류 · 확인할 것 · 기일 달력 · 조회 대상 고르기."""
import datetime as dt
import re

from .store import Store

COLORS = {"red": "#e5484d", "orange": "#d97706", "green": "#12a26b", "blue": "#3355ff", "gray": "#9aa1ad",
          "purple": "#7c3aed", "teal": "#0d9488"}


def ymd(s):
    """'20261021' / '2026-10-21' / '2026.10.21' → date 또는 None"""
    d = re.sub(r"[^\d]", "", str(s or ""))[:8]
    if len(d) != 8:
        return None
    try:
        return dt.date(int(d[:4]), int(d[4:6]), int(d[6:8]))
    except ValueError:
        return None


def fmt(d):
    return d.isoformat() if d else ""


def row_text(r):
    parts = [r.get("progCtt") or "", r.get("progCtt1") or "", r.get("progCtt2") or "", r.get("progCtt3") or "",
             r.get("progRslt") or "", r.get("dlvRInf") or ""]
    return " ".join(p.strip() for p in parts if p and str(p).strip())


def _words_match(words, text):
    t = re.sub(r"\s+", "", text)
    return any(w and re.sub(r"\s+", "", w) in t for w in words)


# ---------------------------------------------------------------- 상태

def classify(settings, prog_rows, basic):
    """(상태, 색, 맞은 규칙 id)
    최근 줄부터 차례로 읽어, 처음으로 어떤 규칙에 맞는 줄에서 멈춘다. 한 줄에 여러 규칙이 맞으면 위에 있는 규칙.
    확정일자가 있으면 '확정' 줄이 가장 최근에 있는 것으로 본다."""
    rows = []
    if basic.get("csCfmtnYmd"):
        rows.append(f"확정 {basic['csCfmtnYmd']}")
    rows += [row_text(r) for r in prog_rows[: max(1, int(settings.get("rule_rows") or 5))]]
    for t in rows:
        for rule in settings["rules"]:
            if _words_match(rule["words"], t):
                return rule["status"], rule.get("color", "blue"), rule["id"]
    if basic.get("csUltmtYmd") and basic.get("csUltmtDvsNm"):
        return settings.get("default_status") or "진행 중", "blue", ""
    return settings.get("default_status") or "진행 중", "blue", ""


def hearings(lists):
    """일반내용의 '최근 기일' 목록 → [{date, time, kind, place, result}]"""
    out = []
    for r in (lists or {}).get("dlt_rcntDxdyLst") or []:
        d = ymd(r.get("dxdyYmd"))
        if not d:
            continue
        hm = re.sub(r"[^\d]", "", str(r.get("dxdyHm") or ""))
        out.append({"date": fmt(d), "time": f"{hm[:2]}:{hm[2:4]}" if len(hm) >= 4 else "",
                    "kind": r.get("dxdyKndNm") or "기일", "place": r.get("dxdyPlcNm") or "",
                    "result": r.get("dxdyRsltNm") or ""})
    out.sort(key=lambda h: (h["date"], h["time"]))
    return out


def refresh_case(store, c, res=None):
    """저장된 결과로 사건 대장의 요약 칸(상태·마지막 진행·다음 기일 등)을 다시 계산."""
    res = res or store.result(c["id"])
    basic, prog = res.get("basic") or {}, res.get("prog") or []
    if not res.get("checks"):
        return c
    status, color, rid = classify(store.settings, prog, basic)
    from . import legal
    if legal.rehab_kind(c.get("dvs")):  # 회생·파산 사건은 상태 대신 관리 가부 (회수·집행 가능 / 정지 / 금지 / 불가)
        m = legal.rehab_status(c.get("dvs"), [(row_text(r), fmt(ymd(r.get("progYmd")))) for r in prog], basic)
        c["rehab"] = m
        status, color, rid = m["label"].split(" · ")[0], {"black": "gray"}.get(m["color"], m["color"]), "rehab"
    c["status"], c["color"], c["rule"] = status, color, rid
    c["csNm"] = basic.get("csNm") or c.get("csNm", "")
    c["cfm_date"] = fmt(ymd(basic.get("csCfmtnYmd")))
    c["ultmt"] = " ".join(x for x in (fmt(ymd(basic.get("csUltmtYmd"))), basic.get("csUltmtDvsNm") or "") if x)
    if prog:
        r = prog[0]
        c["last_prog"] = {"date": fmt(ymd(r.get("progYmd"))), "text": row_text(r)}
    today = dt.date.today()
    fut = [h for h in hearings(res.get("lists")) if h["date"] >= fmt(today)]
    c["next_hearing"] = fut[0] if fut else {}
    return c


def label_status_counts(cases):
    out = {}
    for c in cases:
        s = c.get("status") or "조회 전"
        out[s] = out.get(s, 0) + 1
    return out


# ---------------------------------------------------------------- 확인할 것

def todos(store, show_done=False):
    """확인할 것 목록. 자료가 바뀌지 않았으면 지난번 계산을 다시 쓴다 (사건이 많아도 화면 전환이 빠르게)."""
    import copy
    key = (store.rev, dt.date.today(), dt.datetime.now().strftime("%Y%m%d%H"))
    hit = getattr(store, "_todo_cache", None)
    if hit and hit[0] == key:
        return finish(copy.deepcopy(hit[1]), store.settings["todo"], show_done)
    items = _todos(store)
    store._todo_cache = (key, items)
    return finish(copy.deepcopy(items), store.settings["todo"], show_done)


def _todos(store):
    s = store.settings
    ts = s["todo"]
    today = dt.date.today()
    look = today - dt.timedelta(days=int(ts.get("lookback_days") or 60))
    rules = {r["id"]: r for r in s["rules"]}
    items = []
    for c in store.active_cases():
        if not c.get("last_checked"):
            continue
        res = store.result(c["id"])
        seen_rules = set()
        for r in res.get("prog") or []:  # 최근 줄부터
            d = ymd(r.get("progYmd"))
            if not d or d < look:
                continue
            text = row_text(r)
            for rule in s["rules"]:
                if not _words_match(rule["words"], text):
                    continue
                if not rule.get("todo") or rule["id"] in seen_rules:
                    break  # 한 사건에서 같은 종류는 가장 최근 것 하나만
                seen_rules.add(rule["id"])
                key = f"{c['id']}|{Store.row_key(r)}"
                st = store.todos.get(key, {})
                due = st.get("deadline") or (fmt(d + dt.timedelta(days=int(rule["days"]))) if rule.get("days") else "")
                items.append({"key": key, "cid": c["id"], "kind": rule["status"], "color": rule.get("color", "blue"),
                              "date": fmt(d), "text": text, "due": due, "due_manual": bool(st.get("deadline")),
                              "ask": bool(rule.get("ask")) and not st.get("deadline"), "done": st.get("done", ""),
                              "done_note": st.get("note", ""), "done_by": st.get("by", ""), "new": not r.get("_first")})
                break
        # 기일 미리 알림
        for h in hearings(res.get("lists")):
            hd = ymd(h["date"])
            if hd and today <= hd <= today + dt.timedelta(days=int(ts.get("hearing_days") or 14)):
                key = f"{c['id']}|hearing|{h['date']}|{h['time']}"
                st = store.todos.get(key, {})
                items.append({"key": key, "cid": c["id"], "kind": "기일", "color": "blue", "date": h["date"],
                              "text": " ".join(x for x in (h["kind"], h["time"], h["place"]) if x), "due": h["date"],
                              "due_manual": False, "ask": False, "done": st.get("done", ""), "done_note": st.get("note", ""),
                              "done_by": st.get("by", ""), "new": False})
        # 확정 예상 (판결 송달일 + 항소기간)
        b = res.get("basic") or {}
        sent = ymd(b.get("lastAdjdocRchYmd"))
        if sent and not b.get("csCfmtnYmd") and sent >= look:
            exp = sent + dt.timedelta(days=int(ts.get("confirm_days") or 14))
            key = f"{c['id']}|confirm|{fmt(sent)}"
            st = store.todos.get(key, {})
            items.append({"key": key, "cid": c["id"], "kind": "확정 예상", "color": "green", "date": fmt(sent),
                          "text": f"판결 송달 {fmt(sent)} → {fmt(exp)} 확정 예상", "due": fmt(exp), "due_manual": False,
                          "ask": False, "done": st.get("done", ""), "done_note": st.get("note", ""),
                          "done_by": st.get("by", ""), "new": False})
    return finish(items, ts)


def finish(items, ts, show_done=False):
    """급한 정도로 나누고 정렬. 처리한 것은 설정대로 숨긴다 (show_done 이면 모두)."""
    today = dt.date.today()
    hot = int(ts.get("hot_days") or 3)
    for it in items:
        due = ymd(it["due"])
        it["left"] = (due - today).days if due else None
        it["estimated"] = bool(it["due"]) and not it.get("due_manual") and it["kind"] not in ("기일", "매각기일")
        if it["done"]:
            it["group"] = "처리함"
        elif it["ask"] or (it["left"] is not None and it["left"] <= hot):
            it["group"] = "급한 것"
        elif it["left"] is not None and it["left"] <= 7:
            it["group"] = "이번 주 안에"
        else:
            it["group"] = "나중에"
    order = {"급한 것": 0, "이번 주 안에": 1, "나중에": 2, "처리함": 3}
    items.sort(key=lambda i: (order[i["group"]], i["left"] if i["left"] is not None else 999, i["date"]))
    hide = ts.get("hide_done", "day")
    if hide != "never" and not show_done:
        limit = dt.datetime.now() - dt.timedelta(days=1 if hide == "day" else 0)
        items = [i for i in items if not i["done"] or dt.datetime.strptime(i["done"], "%Y-%m-%d %H:%M:%S") > limit]
    return items


# ---------------------------------------------------------------- 달력

def calendar(store, year, month):
    first = dt.date(year, month, 1)
    last = (first + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)
    ev = []
    for c in store.active_cases():
        res = store.result(c["id"])
        for h in hearings(res.get("lists")):
            d = ymd(h["date"])
            if d and first <= d <= last:
                ev.append({"date": h["date"], "cid": c["id"], "type": "선고" if "선고" in h["kind"] else "기일",
                           "text": " ".join(x for x in (h["kind"], h["time"], h["place"]) if x)})
    for t in todos(store):
        d = ymd(t["due"])
        if t["kind"] == "기일" or not d or not first <= d <= last:
            continue
        ev.append({"date": t["due"], "cid": t["cid"], "key": t["key"], "type": "확정 예상" if t["kind"] == "확정 예상" else "기한",
                   "text": f"{t['kind']} 기한" + (" (직접 넣음)" if t["due_manual"] else "")})
    for key, st in store.todos.items():
        if key.startswith("manual|") and st.get("deadline"):
            d = ymd(st["deadline"])
            if d and first <= d <= last:
                ev.append({"date": st["deadline"], "cid": st.get("cid", ""), "type": "기한", "text": st.get("note", "직접 넣은 기한")})
    ev.sort(key=lambda e: e["date"])
    return ev


# ---------------------------------------------------------------- 조회 대상 고르기

def pick(store, cond, notfound_ids=None):
    """조건에 맞는 사건 목록과 조건별로 빠진 수."""
    s = dict(store.settings["conditions"])
    s.update(cond or {})
    today = dt.date.today()
    rules = {r["id"]: r for r in store.settings["rules"]}
    skip_status = {r["status"] for r in store.settings["rules"] if r.get("skip")}
    cases = store.active_cases()
    removed = {}
    out = []

    def drop(name):
        removed[name] = removed.get(name, 0) + 1

    for c in cases:
        if s.get("only_notfound") and c.get("last_result") != "notfound":
            drop("only_notfound"); continue
        nh = (c.get("next_hearing") or {}).get("date")
        if s.get("only_hearing") and not (nh and ymd(nh) <= today + dt.timedelta(days=int(s.get("hearing_days") or 14))):
            drop("only_hearing"); continue
        if s.get("owner") and s.get("owner_value") and (c.get("owner") or "") != s["owner_value"]:
            drop("owner"); continue
        if s.get("court") and s.get("court_value") and c.get("court") != s["court_value"]:
            drop("court"); continue
        if s.get("closed") and c.get("status") in skip_status:
            drop("closed"); continue
        last = c.get("last_checked") or ""
        if s.get("recent") and last:
            if (today - dt.date.fromisoformat(last[:10])).days < int(s.get("recent_days") or 7):
                drop("recent"); continue
        if s.get("stale") and last and (c.get("last_prog") or {}).get("date"):
            lp = ymd(c["last_prog"]["date"])
            if lp and (today - lp).days > int(s.get("stale_months") or 6) * 30:
                if (today - dt.date.fromisoformat(last[:10])).days < int(s.get("stale_every") or 30):
                    drop("stale"); continue
        out.append(c)
    if s.get("hearing_first"):
        lim = today + dt.timedelta(days=int(s.get("hearing_days") or 14))

        def soon(c):
            d = ymd((c.get("next_hearing") or {}).get("date"))
            return 0 if d and d <= lim else 1
        out.sort(key=soon)
    return out, removed
