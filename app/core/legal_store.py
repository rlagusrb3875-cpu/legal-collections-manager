# -*- coding: utf-8 -*-
"""법조치 자료 저장 — 채권 폴더의 legal.json 하나.

  debtors  채무자 원장 (모든 법조치 화면이 같이 씀)
  dlv      송달·주소보정 (사건 조회 결과에서 「송달 안 됨」을 찾아 만듦, 키는 확인할 것과 같은 「사건|줄」)
  rehab    회생·파산 (받은 문서 등록 → 채무자에 「멈춤」)
  docs     만든 서류 기록
  info     이 채권의 청구 원인 (양도인·양도일·통지 도달일 등)
  dv       배당 예상에 마지막으로 넣은 값
"""
import copy
import datetime as dt
import json
import os
import threading
import uuid

from .legal import digits

EMPTY = {"debtors": {}, "dlv": {}, "rehab": {}, "docs": [], "info": {}, "dv": {}}
STAGES = ["준비", "독촉", "소송", "확정", "집행", "회생·파산", "종결"]


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class LegalStore:
    def __init__(self, root):
        self.root = root
        self.path = os.path.join(root, "legal.json")
        self.lock = threading.RLock()
        self.rev = 0
        data = {}
        if os.path.isfile(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                os.replace(self.path, self.path + f".broken-{dt.datetime.now():%Y%m%d%H%M%S}")
        self.data = copy.deepcopy(EMPTY)
        self.data.update(data)

    def save(self):
        self.rev += 1
        with self.lock:
            os.makedirs(self.root, exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)

    # ------------------------------------------------------------ 채무자

    @property
    def debtors(self):
        return self.data["debtors"]

    def debtor(self, did):
        return self.data["debtors"].get(did)

    def match_debtor(self, key="", name="", birth="", order=None):
        """같은 채무자 찾기. order: 찾는 순서 (key=관리번호·계좌번호, name_birth=이름+생년월일, name=이름만).
        (채무자, 찾은 방법)을 돌려준다. 이름만으로 찾은 것은 동명이인일 수 있어 화면에 알린다."""
        order = ["key", "name_birth", "name"] if order is None else order
        k = digits(key)
        b6 = str(birth or "")[:6]
        for how in order:
            for d in self.debtors.values():
                if how == "key" and k and digits(d.get("key")) == k:
                    return d, how
                if how == "name_birth" and name and b6 and d.get("name") == name and str(d.get("birth") or "")[:6] == b6:
                    return d, how
                if how == "name" and name and d.get("name") == name and (not b6 or not d.get("birth") or str(d["birth"])[:6] == b6):
                    return d, how
        return None, ""

    def find_debtor(self, key="", name="", birth="", order=None):
        return self.match_debtor(key, name, birth, order)[0]

    def upsert_debtor(self, fields, by="", order=None):
        d = None
        if fields.get("id"):
            d = self.debtor(fields["id"])
        if not d:
            d = self.find_debtor(fields.get("key", ""), fields.get("name", ""), fields.get("birth", ""), order)
        new = d is None
        if new:
            d = {"id": "d" + uuid.uuid4().hex[:10], "stage": "준비", "assets": [], "log": [], "addr_hist": [], "created": now()}
            self.debtors[d["id"]] = d
        old_addr = d.get("addr", "")
        for k, v in fields.items():
            if k == "id" or v is None:
                continue
            d[k] = v
        if old_addr and fields.get("addr") and fields["addr"] != old_addr:
            d.setdefault("addr_hist", []).append({"addr": old_addr, "note": "이전 주소", "at": now()[:10]})
        if new:
            self.log(d, "원장에 추가", by)
        return d, new

    def log(self, d, text, by=""):
        d.setdefault("log", []).insert(0, {"at": now(), "by": by, "text": text})
        del d["log"][60:]

    def active_debtors(self):
        return [d for d in self.debtors.values() if not d.get("archived")]
