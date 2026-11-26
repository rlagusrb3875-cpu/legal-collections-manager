# -*- coding: utf-8 -*-
"""엑셀 열 짝짓기 기억 · 연결 기준(키).

- 한 번 짝지은 열 이름은 어느 화면에서 넣든 기억한다 (자료 폴더 xlmem.json = {열 이름: 공통 항목}).
  화면마다 항목 이름이 달라서(사건 대장 party, 원장 name …) 「공통 항목」으로 바꿔 저장한다.
- 연결 기준(settings["link"]): 기능마다 같은 사람·같은 건을 무엇으로 찾을지와, 키로 쓸 엑셀 열 이름.
"""
import re

# 화면(넣을 곳)별 항목 → 공통 항목
CANON = {
    "case": {"court": "court", "case": "case_no", "party": "name", "owner": "owner", "memo1": "key", "memo2": "memo",
             "year": "year", "dvs": "dvs", "serial": "serial"},
    "debtor": {"name": "name", "birth": "birth", "key": "key", "principal": "principal", "interest": "interest", "addr": "addr",
               "sihyo": "sihyo", "default_date": "default_date", "rate": "rate", "contract_date": "contract_date", "court": "court"},
    "dlv": {"case_no": "case_no", "court": "court", "party": "name", "doc": "doc", "reason": "reason", "date": "dlv_date", "recv": "recv",
            "days": "days", "due": "due", "act": "act", "new_addr": "new_addr", "owner": "owner", "memo": "memo", "submit": "submit", "status": "status"},
    "rehab": {"name": "name", "birth": "birth", "kind": "rehab_kind", "date": "rehab_date", "no": "case_no"},
    "form": {"debtor": "name", "case_no": "case_no", "court": "court", "debtor_addr": "addr", "new_addr": "new_addr", "amount": "amount",
             "mgmt_no": "key", "reason": "reason", "req": "act", "case_name": "case_name", "creditor": "creditor"},
}
# 키(관리번호·계좌번호)가 들어가는 항목
KEY_FIELD = {"case": "memo1", "debtor": "key", "form": "mgmt_no"}

LINK_DEFAULT = {
    "debtor": {"by": ["key", "name_birth", "name"], "key_col": ""},       # 채무자 원장 엑셀: 같은 채무자 찾기
    "case_debtor": {"by": ["key", "name"]},                                # 사건 대장 ↔ 채무자 원장
    "case": {"key_col": ""},                                               # 사건 대장 엑셀: 키(메모 1)로 쓸 열
    "dlv": {"by": "case_recv"},                                            # 보정 관리 엑셀: 같은 건 찾기
    "rehab": {"by": ["name_birth", "name"]},                               # 회생·파산 공공정보 → 원장
    "form": {"by": ["key", "name"], "key_col": ""},                         # 회사 양식 엑셀 → 원장
}
METHODS = {"key": "관리번호·계좌번호(키)", "name_birth": "이름 + 생년월일", "name": "이름만"}


def norm(h):
    return re.sub(r"[\s_\-()（）\[\].:]+", "", str(h or "")).lower()


def link(settings, what):
    cur = dict(LINK_DEFAULT[what])
    cur.update((settings.get("link") or {}).get(what) or {})
    return cur


def prefer(mem, settings, dest, header):
    """기억해 둔 열 이름으로 이 화면의 항목 → 열 번호를 만든다. 키 열을 정해 두었으면 그것이 먼저."""
    mem = mem or {}
    rev = {v: k for k, v in CANON.get(dest, {}).items()}
    out = {}
    for j, h in enumerate(header):
        c = mem.get(norm(h))
        f = rev.get(c)
        if f and f not in out:
            out[f] = j
    kf = KEY_FIELD.get(dest)
    kc = norm((link(settings, dest) if dest in LINK_DEFAULT else {}).get("key_col", ""))
    if kf and kc:
        j = next((j for j, h in enumerate(header) if norm(h) == kc), None)
        if j is not None:
            out = {k: v for k, v in out.items() if v != j}
            out[kf] = j
    return out


def merge(auto, pref):
    """자동으로 찾은 것 위에 기억한 것을 얹는다 (같은 열을 두 항목이 쓰지 않게). 어디서 왔는지도 돌려준다."""
    used = set(pref.values())
    out = {k: v for k, v in auto.items() if v not in used and k not in pref}
    out.update(pref)
    src = {k: ("mem" if k in pref else "auto") for k in out}
    return out, src


def remember(mem, dest, header, mapping):
    """넣기를 누르면: 이 짝짓기를 기억 (다른 화면도 같이 씀). 바뀌었으면 새 기억을, 아니면 None."""
    canon = CANON.get(dest, {})
    mem = dict(mem or {})
    changed = False
    for f, j in (mapping or {}).items():
        try:
            j = int(j)
        except (TypeError, ValueError):
            continue
        if f in canon and 0 <= j < len(header) and norm(header[j]):
            if mem.get(norm(header[j])) != canon[f]:
                mem.pop(norm(header[j]), None)
                mem[norm(header[j])] = canon[f]
                changed = True
    if not changed:
        return None
    return dict(list(mem.items())[-400:])
