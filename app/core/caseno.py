# -*- coding: utf-8 -*-
"""엑셀에 적힌 법원 이름·사건번호·당사자 이름을 사이트에 넣을 수 있는 모양으로 읽기."""
import re

_CASE = re.compile(r"^\s*(\d{2}|\d{4})\s*([가-힣]{1,5})\s*([\d,\s-]{1,12})\s*$")


def parse_case_no(text):
    """'2025가소123456' → (2025, '가소', '123456'). 못 읽으면 None."""
    s = str(text or "").strip().replace("（", "(").replace("）", ")")
    s = re.sub(r"\(.*?\)", "", s)  # '2025가소123456(병합)' 같은 꼬리 정리
    m = _CASE.match(s)
    if not m:
        return None
    year, dvs, serial = m.group(1), m.group(2), re.sub(r"[^\d]", "", m.group(3))
    if not serial or len(serial) > 7:
        return None
    y = int(year)
    if len(year) == 2:
        y += 2000 if y < 80 else 1900
    if not 1950 <= y <= 2100:
        return None
    return y, dvs, str(int(serial))


def format_case_no(year, dvs, serial):
    return f"{year}{dvs}{serial}"


def _squash(s):
    return re.sub(r"\s+", "", str(s or ""))


def _expand(s):
    s = _squash(s)
    for a, b in (("지법", "지방법원"), ("고법", "고등법원"), ("가법", "가정법원"), ("행법", "행정법원")):
        if s.endswith(a) or a + "(" in s or re.search(a + r"(?=[가-힣]+지원)", s):
            s = s.replace(a, b)
    return s


class CourtNames:
    """법원 이름 맞추기. 정확히 같으면 그대로, 줄임말·지원 표기는 고쳐서 알려준다."""

    def __init__(self, names, aliases=None):
        self.names = list(names)
        self.exact = {_squash(n): n for n in self.names}
        self.aliases = {_squash(k): v for k, v in (aliases or {}).items()}

    def match(self, text):
        """(법원 이름 또는 None, 고친 경우 설명 또는 '', 후보 목록)"""
        raw = str(text or "").strip()
        if not raw:
            return None, "", []
        key = _squash(raw)
        if key in self.exact:
            return self.exact[key], "", []
        if key in self.aliases:
            return self.aliases[key], f"「{raw}」→ {self.aliases[key]} (직접 정한 이름)", []
        exp = _expand(raw)
        if exp in self.exact:
            return self.exact[exp], f"「{raw}」→ {self.exact[exp]}", []
        # '수원지방법원 성남지원' → '성남지원' 처럼 지원 이름만 쓰는 경우
        if exp.endswith("지원"):
            branch = exp.rsplit("법원", 1)[-1]
            parent = exp[:-len(branch)]
            cands = [n for n in self.names if _squash(n).rsplit("법원", 1)[-1] == branch]
            if parent:
                kind = "가정법원" if "가정" in parent else ""
                narrowed = [n for n in cands if (kind in n) if kind] or [n for n in cands if "가정" not in n]
                cands = narrowed or cands
            if len(cands) == 1:
                return cands[0], f"「{raw}」→ {cands[0]}", []
            if cands:
                return None, "", cands
        # '서울중앙' → '서울중앙지방법원'
        for suffix in ("지방법원", "법원"):
            if exp + suffix in self.exact:
                n = self.exact[exp + suffix]
                return n, f"「{raw}」→ {n}", []
        cands = [n for n in self.names if exp and (exp in _squash(n))]
        if len(cands) == 1:
            return cands[0], f"「{raw}」→ {cands[0]}", []
        return None, "", cands[:6]


def name_variants(name, patterns=None):
    """찾을 수 없을 때 다시 시도할 이름 표기들 (원래 이름 제외)."""
    n = str(name or "").strip()
    out = []
    core = re.sub(r"^(주식회사|\(주\)|㈜)\s*|\s*(주식회사|\(주\)|㈜)$", "", n).strip()
    if core and core != n:
        for form in (patterns or ["㈜{}", "주식회사 {}", "{}(주)", "(주){}", "{}주식회사", "{}"]):
            out.append(form.format(core))
    if " " in n:
        out.append(n.replace(" ", ""))
    seen, res = {n}, []
    for v in out:
        if v not in seen and len(v) >= 2:
            seen.add(v)
            res.append(v)
    return res
