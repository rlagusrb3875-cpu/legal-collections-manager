# -*- coding: utf-8 -*-
"""채권 나누기 (자료를 채권별 폴더에 따로 보관)"""
import datetime as dt
import json
import os
import subprocess
import sys
import threading
import time

from appbase import DEFAULT_BOOK, LOCAL, _desktop, _save_pointer
from core import auction as AU
from core import excel, rules
from core.caseno import CourtNames, name_variants, parse_case_no
from core.meta import Meta
from core.site import Court, SiteError
from core.store import SUMMARY_COLS, Store, now


class BooksMixin:
    # ------------------------------------------------------------ 채권 (자료를 채권별로 나눠 보관)

    def _books_dir(self):
        return os.path.join(self.data_dir, "채권")

    def _books_info(self):
        try:
            with open(os.path.join(self.data_dir, "books.json"), encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_books_info(self, current, order=None):
        info = self._books_info()
        info["current"] = current
        if order is not None:
            info["order"] = order
        with open(os.path.join(self.data_dir, "books.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False)

    def _migrate(self):
        """예전 판(채권 구분 없음)의 자료를 「기본 채권」으로 옮긴다."""
        old = os.path.join(self.data_dir, "cases.json")
        if not os.path.isfile(old):
            if not self.book_names():  # 처음 실행
                os.makedirs(os.path.join(self._books_dir(), DEFAULT_BOOK), exist_ok=True)
            return
        import shutil
        dst = os.path.join(self._books_dir(), DEFAULT_BOOK)
        os.makedirs(dst, exist_ok=True)
        for name in ("cases.json", "runs.json", "todos.json", "results", "backups"):
            src = os.path.join(self.data_dir, name)
            if os.path.exists(src) and not os.path.exists(os.path.join(dst, name)):
                shutil.move(src, os.path.join(dst, name))
        self._save_books_info(DEFAULT_BOOK)

    def book_names(self):
        d = self._books_dir()
        names = [n for n in os.listdir(d) if os.path.isdir(os.path.join(d, n))] if os.path.isdir(d) else []
        order = self._books_info().get("order") or []
        return sorted(names, key=lambda n: (order.index(n) if n in order else 999, n))

    def _open_book(self, name):
        return Store(os.path.join(self._books_dir(), name), settings_root=self.data_dir)

    @staticmethod
    def _check_book_name(name):
        import re
        name = (name or "").strip()
        if not name:
            raise ValueError("채권 이름을 넣어 주세요")
        if re.search(r'[\\/:*?"<>|]', name) or name in (".", ".."):
            raise ValueError('채권 이름에는 \\ / : * ? " < > | 를 쓸 수 없어요')
        return name

    def books(self):
        out = []
        for n in self.book_names():
            p = os.path.join(self._books_dir(), n, "cases.json")
            cnt = 0
            try:
                with open(p, encoding="utf-8") as f:
                    cnt = sum(1 for c in json.load(f).values() if not c.get("archived"))
            except Exception:
                pass
            out.append({"name": n, "cases": cnt, "current": n == self.book})
        return out

    def book_switch(self, name):
        if name not in self.book_names():
            raise ValueError("그런 채권이 없어요")
        if self.sess:
            self.run_stop()
        self.asess = None
        self.book = name
        self.store = self._open_book(name)
        self._save_books_info(name)
        return self.info()

    def book_add(self, name):
        name = self._check_book_name(name)
        if name in self.book_names():
            raise ValueError("같은 이름의 채권이 있어요")
        os.makedirs(os.path.join(self._books_dir(), name), exist_ok=True)
        self._save_books_info(self.book, self.book_names())
        return self.book_switch(name)

    def book_rename(self, old, new):
        new = self._check_book_name(new)
        if new in self.book_names():
            raise ValueError("같은 이름의 채권이 있어요")
        if self.sess:
            self.run_stop()
        os.rename(os.path.join(self._books_dir(), old), os.path.join(self._books_dir(), new))
        order = [new if n == old else n for n in (self._books_info().get("order") or self.book_names())]
        if self.book == old:
            self.book = new
        self._save_books_info(self.book, order)
        self.store = self._open_book(self.book)
        return self.books()

    def book_delete(self, name):
        names = self.book_names()
        if name not in names:
            raise ValueError("그런 채권이 없어요")
        if len(names) == 1:
            raise ValueError("채권이 하나뿐이라 지울 수 없어요")
        import shutil
        # 지우기 전에 통째로 압축해 남겨 둔다
        keep = os.path.join(self.data_dir, "지운 채권")
        os.makedirs(keep, exist_ok=True)
        shutil.make_archive(os.path.join(keep, f"{name}_{dt.datetime.now():%Y%m%d_%H%M%S}"), "zip",
                            os.path.join(self._books_dir(), name))
        if self.book == name and self.sess:
            self.run_stop()
        shutil.rmtree(os.path.join(self._books_dir(), name))
        if self.book == name:
            self.book_switch(self.book_names()[0])
        return self.books()

    def book_clear(self):
        """지금 채권의 사건·결과·기록을 모두 비운다 (먼저 백업)."""
        if self.sess:
            self.run_stop()
        backup = self.store.backup()
        import shutil
        root = self.store.root
        for name in ("cases.json", "runs.json", "todos.json"):
            p = os.path.join(root, name)
            if os.path.exists(p):
                os.remove(p)
        shutil.rmtree(os.path.join(root, "results"), ignore_errors=True)
        self.store = self._open_book(self.book)
        return os.path.basename(backup)
