# -*- coding: utf-8 -*-
"""월간 보고서 · 설정 · 백업"""
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


class SettingsMixin:
    # ------------------------------------------------------------ 월간 보고서

    def report_preview(self, year, month):
        cases = self.store.active_cases()
        y, m = int(year), int(month)
        start, end = f"{y}-{m:02d}-01", f"{y}-{m:02d}-31"
        cfm = [c for c in cases if c.get("cfm_date") and start <= c["cfm_date"] <= end]
        act = [c for c in cases if c.get("color") in ("red", "orange")]
        counts = rules.label_status_counts(cases)
        colors = {}
        for c in cases:
            colors[c.get("status") or "조회 전"] = c.get("color") or "gray"
        return {"total": len(cases), "counts": counts, "colors": colors, "running": counts.get(self.store.settings.get("default_status") or "진행 중", 0),
                "confirmed": [dict(case_no=self.store.case_no(c), court=c["court"], party=c.get("party", ""),
                                   date=c["cfm_date"], memo1=c.get("memo1", "")) for c in cfm],
                "action": [dict(case_no=self.store.case_no(c), court=c["court"], party=c.get("party", ""),
                                status=c.get("status", ""), memo1=c.get("memo1", "")) for c in act],
                "me": self.store.settings.get("me") or os.environ.get("USERNAME", "")}

    def report_save(self, year, month, parts):
        path, _ = excel.monthly_report(self.store, int(year), int(month), parts, self.export_dir(),
                                       self.store.settings.get("me") or os.environ.get("USERNAME", ""))
        self.reveal(path)
        return path

    # ------------------------------------------------------------ 설정

    def setting_set(self, path, value, note=""):
        self.store.set_setting(path, value, note)
        return self.store.settings

    def rules_preview(self, new_rules):
        """규칙을 바꾸면 상태가 바뀌는 사건 수"""
        cur = self.store.settings
        test = dict(cur, rules=new_rules)
        changed = []
        for c in self.store.active_cases():
            if not c.get("last_checked"):
                continue
            res = self.store.result(c["id"])
            a = rules.classify(cur, res.get("prog") or [], res.get("basic") or {})[0]
            b = rules.classify(test, res.get("prog") or [], res.get("basic") or {})[0]
            if a != b:
                changed.append({"case_no": self.store.case_no(c), "party": c.get("party", ""), "from": a, "to": b})
        return changed

    def rules_save(self, new_rules, note="상태 규칙 바꿈"):
        changed = self.rules_preview(new_rules)
        self.store.set_setting("rules", new_rules, f"{note} · {len(changed)}건 상태 바뀜")
        for c in self.store.active_cases():
            rules.refresh_case(self.store, c)
        self.store.save_cases()
        return {"changed": len(changed), "settings": self.store.settings}

    def settings_log(self):
        return self.store.settings_log[:100]

    def settings_undo(self, idx):
        self.store.undo_setting(int(idx))
        if self.store.settings_log and self.store.settings_log[0]["path"] == "rules":
            for c in self.store.active_cases():
                rules.refresh_case(self.store, c)
            self.store.save_cases()
        return self.store.settings

    def settings_export(self):
        path = excel.unique_path(self.export_dir(), f"종합관리_설정_{dt.date.today():%y%m%d}", ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.store.settings, f, ensure_ascii=False, indent=1)
        self.reveal(path)
        return path

    def settings_import(self):
        p = self.choose_file()
        if not p:
            return None
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if k in self.store.settings:
                self.store.set_setting(k, v, "설정 파일 불러오기")
        return self.store.settings

    def pick_folder_setting(self, path):
        d = self.choose_folder()
        if d:
            self.store.set_setting(path, d)
        return self.store.settings

    def data_dir_change(self):
        d = self.choose_folder()
        if not d:
            return None
        import shutil
        target = os.path.join(d, "사건조회도우미") if os.path.basename(d) != "사건조회도우미" else d
        if not os.path.isfile(os.path.join(target, "cases.json")):
            shutil.copytree(self.data_dir, target, dirs_exist_ok=True)
        _save_pointer({"data_dir": target})
        self.__init__(target)
        return target

    def autostart_get(self):
        from core import autostart
        return autostart.status()

    def autostart_set(self, on):
        from core import autostart
        st = autostart.set_on(bool(on))
        self.store.set_setting("save.autostart", bool(on), "PC 켤 때 자동 실행 " + ("켬" if on else "끔"))
        return st

    def backup_now(self):
        return os.path.basename(self.store.backup())

    def backups(self):
        return self.store.backups()

    def backup_restore(self, name):
        self.store.restore(name)
        return True

    def meta_refresh(self):
        from core import meta as M
        data = M.build(self.court.get_text)
        path = os.path.join(self.data_dir, "court_meta.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        self.meta = Meta(data)
        self.court.meta = self.meta
        return {"courts": len(data["courts"]), "tasks": len(data["tasks"])}
