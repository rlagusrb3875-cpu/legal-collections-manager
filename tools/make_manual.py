# -*- coding: utf-8 -*-
"""사용법(HTML · PDF) 만들기 — 시연 자료로 실제 화면을 찍어 넣는다.

    python tools/make_manual.py                → 화면을 다시 찍고 두 사용법을 만든다
    python tools/make_manual.py --build-only   → 찍어 둔 화면으로 글만 다시 만든다
    python tools/make_manual.py --only g06_pick,g08_run   → 그 화면만 다시 찍는다
    python tools/make_manual.py --only 'r*' --manual=회수분석  → 회수 분석 화면만 찍고 그 사용법만

    dist/종합관리_사용법.html · .pdf   (프로그램 전체)
    dist/배당기일_사용법.html · .pdf   (배당기일만)
    dist/회수분석_사용법.html · .pdf   (회수 분석만)

크롬(헤드리스)으로 화면마다 정해 둔 동작(창 열기 · 칸 고르기 · 빨간 표시)을 한 뒤 찍는다.
"""
import base64
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = next((p for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                           r"C:\Program Files\Google\Chrome\Application\chrome.exe") if os.path.exists(p)), None)
SHOTS = os.path.join(ROOT, "build", "manual", "shots")
# 캡처용 임시 프로필이 macOS 로그인 키체인에 접근하지 않게 한다.
CHROME_KEYCHAIN_ARGS = ["--use-mock-keychain"] if sys.platform == "darwin" else []

# 화면마다: 열고 → 필요한 동작 → 빨간 표시(hl: 선택자, 번호)
HELPERS = r"""
const W = ms => new Promise(r => setTimeout(r, ms));
const MARKS = [];
function hl(sel, n, pad) {
  const el = typeof sel === 'string' ? document.querySelector(sel) : sel;
  if (!el) return;
  const b = document.createElement('div'); b.className = 'm-box'; document.body.appendChild(b);
  let t = null;
  if (n) { t = document.createElement('div'); t.className = 'm-num'; t.textContent = n; document.body.appendChild(t); }
  MARKS.push({el, b, t, p: pad ?? 4});
  place();
}
// 화면이 조금 움직여도(스크롤 · 창 열림) 표시가 대상에 붙어 있게 계속 다시 놓는다
function place() {
  MARKS.forEach(({el, b, t, p, fr}) => { const r0 = el.getBoundingClientRect(), o = fr ? fr.getBoundingClientRect() : {left: 0, top: 0};
    const r = {left: r0.left + o.left, top: r0.top + o.top, width: r0.width, height: r0.height};
    b.style.cssText = `left:${r.left - p}px;top:${r.top - p}px;width:${r.width + p * 2}px;height:${r.height + p * 2}px`;
    if (t) t.style.cssText = `left:${Math.max(2, r.left - p - 13)}px;top:${Math.max(2, r.top - p - 13)}px`; });
}
// 회수 분석: 본문 자리에 겹쳐 띄운 틀(iframe) 안을 다룸
const RF = () => document.querySelector('.rc-frame'), RW = () => RF().contentWindow, RD = () => RW().document, RE = c => RW().eval(c);
async function rgo(id, view) { await go(id);
  for (let i = 0; i < 200; i++) { try { if (RE('APP_ON')) break; } catch (e) {} await W(200); }
  await W(1200);  // 틀이 다 뜬 뒤 종합관리가 보내는 첫 화면 이동이 끝나기를 기다림
  if (view) for (let i = 0; i < 8; i++) { if (RE('ST.view') !== view) RE(`go('${view}')`); await W(400); }
  await W(500);
  const s = RD().createElement('style'); s.textContent = '.toast{display:none!important}*,*::before,*::after{transition:none!important}'; RD().head.appendChild(s); }
function rpk(sel, txt) { const m = [...RD().querySelectorAll(sel)].filter(e => e.getClientRects().length && (!txt || e.textContent.includes(txt)));
  return m.find(e => !m.some(o => o !== e && e.contains(o))) || null; }
function rhl(sel, n, pad) { const el = typeof sel === 'string' ? RD().querySelector(sel) : sel; if (!el) return;
  const b = document.createElement('div'); b.className = 'm-box'; document.body.appendChild(b);
  let t = null; if (n) { t = document.createElement('div'); t.className = 'm-num'; t.textContent = n; document.body.appendChild(t); }
  MARKS.push({el, b, t, p: pad ?? 4, fr: RF()}); place(); }
function rhx(sel, txt, n, pad) { rhl(rpk(sel, txt), n, pad); }
const rcard = t => { const h = [...RD().querySelectorAll('.card .ch h3')].find(x => x.textContent.includes(t)); return h ? h.closest('.card') : null; };
const rscroll = y => { const v = RD().getElementById('view'); v.scrollTop = y; RD().scrollingElement.scrollTop = y; };
setInterval(place, 50);
// 글자로 찾기: sel 중 txt 를 품은 가장 안쪽 요소
function pk(sel, txt) { const m = [...document.querySelectorAll(sel)].filter(e => e.getClientRects().length && (!txt || e.textContent.includes(txt)));
  return m.find(e => !m.some(o => o !== e && e.contains(o))) || null; }
function hx(sel, txt, n, pad) { hl(pk(sel, txt), n, pad); }
const navOpen = () => { document.querySelectorAll('#nav .menu-label.folded').forEach(l => l.click()); };
async function runCase(n) { try { await api('run_stop'); } catch (e) {}
  await api('run_start', {name: '정기 조회', cond: S.conditions}); for (let i = 0; i < n; i++) await api('run_submit', {answer: '123456'});
  await go('run', {state: await api('run_state', {fetch: false})}); }
"""
CSS = """<style>.m-box{position:fixed;border:3px solid #e5484d;border-radius:10px;z-index:9998;pointer-events:none;box-shadow:0 0 0 3px rgba(229,72,77,.18)}
.m-num{position:fixed;width:26px;height:26px;border-radius:50%;background:#e5484d;color:#fff;font:700 14px/26px Pretendard,'Malgun Gothic',sans-serif;text-align:center;z-index:9999;pointer-events:none;box-shadow:0 2px 6px rgba(0,0,0,.25)}
.toast,#toasts,.demo-bar{display:none!important}*,*::before,*::after{transition:none!important;animation:none!important}
html,body{height:768px!important;overflow:hidden!important}.app{height:768px!important}.modal-bg{bottom:auto!important;height:768px!important}.dv-drawer{bottom:auto!important;height:768px!important}.modal{max-height:700px!important}</style>"""

STEPS = {
    "s01_console": """await go('console'); await W(1500); $('#nav').scrollTop = 99999; await W(200);
      hl('.dv-today', 1, 6); hl('#nav .menu-label[data-g="배당기일"]', 2, 2);""",
    "s02_menu": """await go('dv_run'); await W(1200); $('#nav').scrollTop = 99999; await W(200);
      hl('#nav button[data-s="dv_run"]', 1, 2); hl('#nav button[data-s="dv_board"]', 2, 2); hl('#nav button[data-s="dv_ledger"]', 3, 2); hl('#nav button[data-s="dv_stats"]', 4, 2);""",
    "s03_run_input": """await go('dv_run', {tab: 'search'}); await W(1200);
      $('#dv1').value = '채무자\\t법원\\t사건번호\\n가O나\\t부산지방법원\\t2026타배99004\\n다O라\\t서울남부지법\\t2026 타배 99005\\n차O카\\t인천지방법원\\t2026타배99006'; $('#dv1').oninput(); await W(1500);
      hl('.dv-ins > .dv-icard:first-child .dv-ta', 1); hl('#dvPick', 2); hl('#dvF1', 3); hl('#dvGo1', 4);""",
    "s04_search_result": """await go('dv_run', {tab: 'search'}); await W(800); DVTAB = 'search'; dvRunDraw($('#view')); await W(600);
      hl('.dv-rtabs > button:first-child', 1); hl('#dvTS thead th:nth-child(5)', 2); hl('#dvTS thead th:nth-child(7)', 3); hl('#dvTS thead th:nth-child(6)', 4);""",
    "s05_law_input": """await go('dv_run', {tab: 'search'}); await W(800); DVTAB = 'search'; dvRunDraw($('#view')); await W(400);
      hl('.dv-ins > .dv-icard:last-child .dv-ta', 1); hl('#dvLast', 2); hl('#dvF2', 3); hl('#dvGo2', 4); hl('#dvSum2', 5);""",
    "s06_lawmap": """await go('dv_run'); await W(800);
      dvLawMap({head: ['관할법원', '당사사건', '차주ID', '항목', '비고'], map: ['court', 'no', 'dkey', null, null], has_head: true, missing: ['법조치키'], guessed: false,
        sample: [['부산지방법원', '2025타채99001', 'K-100231', 'LX-05521', ''], ['서울남부지방법원', '2024타채99002', 'K-100877', 'LX-00341', ''], ['인천지방법원', '2024타채99003', 'K-102210', 'LX-03091', '']],
        fields: [['dkey', '채무자키'], ['lkey', '법조치키'], ['debtor', '채무자명'], ['mgr', '담당자명'], ['court', '법원'], ['no', '사건번호'], ['dno', '배당사건번호'], ['claim', '청구액']]});
      await W(700); const s = document.querySelector('[data-lm="3"]'); s.value = 'lkey'; await W(200); hl(s.closest('th'), 1, 3); hl('#lmHead', 2, 6);""",
    "s07_match": """await go('dv_run', {tab: 'match'}); await W(1200); DVTAB = 'match'; dvRunDraw($('#view')); await W(500);
      hl('.dv-rtabs > button:nth-child(2)', 1); hl('#dvTM tbody tr:first-child td:nth-child(2)', 2); hl('#dvTM tbody tr:first-child td:nth-child(3)', 3); hl('#dvSave', 4); hl('#dvDiag', 5);""",
    "s08_pick": """await go('dv_run'); await W(900); dvPick(); await W(900); hl('.dv-pk', 1, 6); hl('.dv-pkout', 2);""",
    "s09_xlsm": """await go('dv_run'); await W(900); hl('#dvData', 1); hl('#dvDataSet', 2); await W(100); dvXlsm(); await W(900);""",
    "s10_board": """await go('dv_board'); await W(1300);
      hl('.dv-stats', 1); hl('.dv-tb .seg', 2); hl('.dv-tb .seg:last-of-type', 3); hl('#dbXl', 4); hl('#dvTB tbody tr:first-child .dv-gc', 5, 2);""",
    "s11_board_cal": """DVB.view = 'cal'; await go('dv_board'); await W(1300); hl('.dv-cal', 1, 6); hl('.dv-calw > .card:last-child', 2, 4); DVB.view = 'table';""",
    "s12_ledger": """await go('dv_ledger', {lf: 'all', q: ''}); await W(1500);
      hl('.dv-stats', 1); hl('#lY', 2); hl('#lM', 3); hl('#lQ', 4); hl('.dv-tb .seg', 5); hl('#lPaste', 6); hl('#lXl', 7);""",
    "s13_ledger_cols": """await go('dv_ledger', {lf: 'all', q: ''}); await W(1500);
      const ci = k => DV_COLS.findIndex(c => c.k === k) + 2;
      hl(`.dv-grid thead th:nth-child(${ci('dkey')})`, 1); hl(`.dv-grid thead th:nth-child(${ci('on')})`, 2); hl(`.dv-grid thead th:nth-child(${ci('third')})`, 3);
      hl(`.dv-grid thead th:nth-child(${ci('stage')})`, 4); hl(`.dv-grid thead th:nth-child(${ci('amt')})`, 5);""",
    "s14_drawer": """await go('dv_ledger', {lf: 'all', q: ''}); await W(1300); const r = DVL.rows.find(x => x.recv !== '수령' && x.dkey) || DVL.rows[0]; await dvRowOpen(r.id); await W(900);
      const db = $('#dvDrawer .dv-db'); db.scrollTop = $('#dvDrawer .dv-chips[data-chip="check"]').offsetTop - 140; await W(300);
      hl('#dvDrawer .dv-chips[data-chip="check"]', 1); hl('#dvDrawer [data-f="amt"]', 2); hl('#dvDrawer .dv-chips[data-chip="recv"]', 3); hl('#dvDs', 4);""",
    "s15_select_copy": """await go('dv_ledger', {lf: 'all', q: ''}); await W(1300);
      const ci = k => DV_COLS.findIndex(c => c.k === k);
      DVG.a = {r: 0, c: ci('dkey')}; DVG.f = {r: 3, c: ci('no')}; dvGPaint(); await W(400); hl('#dvGBar', 1, 4);""",
    "s16_third": """await go('dv_ledger', {lf: 'all', q: ''}); await W(1300);
      const k = DV_COLS.findIndex(c => c.k === 'third'); const tr = document.querySelector('.dv-grid tbody tr[data-lr]'); const td = tr.querySelector(`td[data-ci="${k}"]`);
      dvEditThird(td, tr.dataset.lr); await W(300); td.querySelector('input').value = '(주)한빛건설'; hl(td, 1, 3);""",
    "s17_paste": """await go('dv_ledger', {lf: 'all', q: ''}); await W(1300);
      const L = DVL.data.rows.filter(r => r.lkey && !r.deleted).slice(0, 3);
      dvPaste('배당사건번호\\t법조치키\\t배당액\\t수령 단계\\n' + L.map((r, i) => `${r.no}\\t${r.lkey}\\t${(i + 2) * 1010000}\\t${i ? '발송' : '수령완료'}`).join('\\n') + '\\n2099타배1\\tL-없음\\t300000\\t대기'); await W(1500);""",
    "s18_bulk": """await go('dv_ledger', {lf: 'doing', q: ''}); await W(1300); DVL.rows.slice(0, 3).forEach(r => DVL.sel.add(r.id)); dvLedDraw($('#view')); await W(500);
      hl('.dv-bulk', 1, 3); hl('.dv-grid tbody tr:first-child .dv-ckc', 2, 2); DVL.sel.clear();""",
    "s19_stats": """await go('dv_stats'); await W(1800); hl('.dv-sbar', 1); hl('.dv-kpis', 2, 4); hl('#sSet', 3); hl('#sRep', 4);""",
    "s20_stats_lower": """await go('dv_stats'); await W(1800); const m = document.querySelector('main'); m.scrollTop = 470; await W(500);
      const c = [...document.querySelectorAll('.dv-dcell')]; hl(c[3], 1, 2); hl(c[4], 2, 2);""",
    "s21_stats_panels": """await go('dv_stats'); await W(1800); const m = document.querySelector('main'); m.scrollTop = 99999; await W(500);
      const c = [...document.querySelectorAll('.dv-dcell')]; hl(c[5], 1, 2); hl(c[6], 2, 2); hl(c[7], 3, 2);""",
    "s22_drill": """await go('dv_stats'); await W(1800); await dvDrill('kpi|unpaid'); await W(900);
      hl('#dvDrawer .dv-chk', 1, 4); hl('#dvDrawer .dv-drbar', 2, 2); hl('#dvDrawer tfoot', 3, 2);""",
    "s23_dashset": """await go('dv_stats'); await W(1500); dvDashSet(); await W(1000);""",
    "s24_report": """await go('dv_stats'); await W(1500); dvReport(); await W(2500);""",
    "s25_captcha": """const st = await api('dv_search', {text: '채무자\\t법원\\t사건번호\\n가O나\\t부산지방법원\\t2026타배99004\\n다O라\\t서울남부지방법원\\t2026타배99005'});
      await go('run', {state: st}); await W(1800); hl('.notice.info', 1, 3); const img = document.querySelector('#view img'); if (img) hl(img.closest('.card') || img, 2, 4);""",
    # ---------------------------------------------------------------- 프로그램 전체
    "g01_console": """try { await api('run_stop'); } catch (e) {} await go('console'); await W(1500);
      hl('#bookSel', 1, 3); hl('#navFind', 2, 3); hl('.con-kpis', 3, 5); hl('.con-flow', 4, 4); hl('#conTour', 5, 3);""",
    "g02_console_lower": """await go('console'); await W(1500); const m = document.querySelector('main'); m.scrollTop = 99999; await W(500);
      hx('.card', '오늘 할 것', 1, 3); hx('.card', '작업 기록', 2, 3);""",
    "g03_book": """await go('console'); await W(1200); $('#bookSel').click(); await W(500); hl('.book-menu', 1, 4);""",
    "g04_find": """await go('console'); await W(1200); palette(); await W(300); const i = document.querySelector('.pal input'); i.value = '홍길동'; i.dispatchEvent(new Event('input')); await W(1200);
      hl('.pal .box', 1, 4);""",
    "g05_nav": """await go('home'); await W(1200); navOpen(); await W(300);
      const L = [...document.querySelectorAll('#nav .menu-label')]; L.slice(0, 4).forEach((l, i) => hl(l, i + 1, 2)); hl('#themeSw', 5, 3);""",
    "g06_pick": """try { await api('run_stop'); } catch (e) {} await go('pick'); await W(1500);
      hl('#quick', 1, 4); hl('#bulk', 2, 4); hx('.card', '사건 대장에서 조건으로 조회', 3, 4); hl('#startBtn', 4, 3); hl('#resetAll', 5, 3);""",
    "g07_run": """await runCase(2); await W(1800);
      hl('.cap-box', 1, 4); hl('.cap-tools', 2, 3); hx('.card', '지금까지의 진행', 3, 3); hl('#runSide', 4, 3); hl('#stopRun', 5, 3); hl('#saveRun', 6, 3);""",
    "g08_home": """try { await api('run_stop'); } catch (e) {} await go('home'); await W(1500);
      hl('.todo-cats', 1, 4); hl('.todo-bar', 2, 3); hl('.filters', 3, 3); const t = document.querySelector('.todo'); hl(t, 4, 2); hl('#showDone', 5, 3);""",
    "g09_cal": """await go('cal'); await W(1500); hx('button', '+ 기한 직접 넣기', 1, 3); hx('.card', '2026년', 2, 3); hx('.card', '보정 기한', 3, 3);""",
    "g10_ledger": """await go('ledger'); await W(1500); hl('#q', 1, 3); hx('button', '엑셀로 추가', 2, 3); hx('button', '+ 한 건 넣기', 3, 3); hl('#all', 4, 4);
      const r = document.querySelector('tr[data-cid] td:nth-child(2)'); hl(r, 5, 2);""",
    "g11_ledger_sel": """await go('ledger'); await W(1500); [...document.querySelectorAll('tr[data-cid] input.cbx')].slice(0, 3).forEach(c => c.click()); await W(500); hl('#selBar', 1, 3);""",
    "g12_case": """await go('ledger'); await W(1000); const cid = document.querySelector('tr[data-cid]').dataset.cid; await go('case', {cid}); await W(1500);
      hx('.card', '지금까지의 진행', 1, 3); hx('.card', '일반내용', 2, 3); hx('.card', '메모 · 처리 기록', 3, 3); hl('#now', 4, 3); hl('#edit', 5, 3);""",
    "g13_hist": """await go('hist'); await W(1500); hx('.card', '정기 조회', 1, 3); hx('button', '결과', 2, 3); hx('button', '엑셀', 3, 3);""",
    "g14_result": """await go('result'); await W(1800); hl('#runSel', 1, 3); hl('.filters', 2, 3);""",
    "g15_report": """await go('report'); await W(1800); hx('.card', '넣을 내용', 1, 3); hl('#pdf', 2, 3); hl('#xl', 3, 3);""",
    "g16_auction": """await go('auction'); await W(1500); hx('button', '+ 사건 넣기', 1, 3); hx('button', '전체 조회', 2, 3); const c = document.querySelector('#view .stats, #view .au-stats') || pk('.card', '매각기일 14일 안'); hl(c, 3, 3);
      const t = document.querySelector('tr[data-aid]'); hl(t, 4, 2);""",
    "g17_auction_case": """await go('auction'); await W(1000); const aid = document.querySelector('tr[data-aid]').dataset.aid; await go('auction_case', {aid}); await W(1600);
      hl('.au-tabs', 1, 3); hl('#aNow', 2, 3); hl('#aMemo', 3, 3);""",
    "g18_lg_home": """await go('lg_home'); await W(1600); hx('.card', '진행 중 법조치', 1, 3); hx('.card', '먼저 볼 것', 2, 3); hx('.card', '기한 임박', 3, 3); hx('.card', '법조치 추이', 4, 3);""",
    "g19_debtors": """await go('lg_debtors'); await W(1200); const did = document.querySelector('[data-did]').dataset.did; await go('lg_debtors', {did}); await W(1500);
      hl('#dImp', 1, 3); hl('#dAdd', 2, 3); const f = pk('#view button', '멈춤'); hl(f && f.parentElement, 3, 3); hl(document.querySelector('#pClose') && document.querySelector('#pClose').closest('.card'), 4, 3);""",
    "g20_dlv": """await go('lg_dlv'); await W(1600); hx('button', '엑셀 넣기', 1, 3); hx('button', '+ 직접 등록', 2, 3); const f = pk('#view button', '3일 안'); hl(f && f.parentElement, 3, 3);
      const r = document.querySelector('#view tbody tr'); hl(r, 4, 2); hx('.card', '보정명령 받은 날', 5, 3);""",
    "g21_rehab": """await go('lg_rehab'); await W(1600); hx('.card', '회생·파산 사건 조회', 1, 3); hx('.card', '추적 중인 사건 다시 확인', 2, 3); hx('button', '+ 받은 문서 등록', 3, 3);""",
    "g22_rehab_list": """await go('lg_rehab'); await W(1600); const m = document.querySelector('main'); m.scrollTop = 99999; await W(500); const t = document.querySelector('#view table'); hl(t, 1, 3);""",
    "g23_fm": """await go('fm'); await W(1500); hl(pk('#view .seg', '양식함'), 1, 3); const add = pk('#view *', '회사 양식 PDF 넣기'); hl(add && add.closest('.card'), 2, 3);
      hx('button', '동료 양식 가져오기', 3, 3); const mk = [...document.querySelectorAll('#view button')].filter(b => b.textContent.trim() === '서류 만들기'); hl(mk[mk.length - 1], 4, 3); hx('button', '칸 수정', 5, 3);""",
    "g24_fm_edit": """const fl = await api('fm_list'); await go('fm_edit', {id: fl.forms[0].id}); await W(2200); hl('#edFind', 1, 3); hx('.card', '정한 칸', 2, 3); hl('#edSave', 3, 3);""",
    "g25_fm_make": """const fl = await api('fm_list'); await go('fm_make', {fid: fl.forms[0].id}); await W(2000); hx('.card', '송달 결과', 1, 3); hl('#mk2n', 2, 3);""",
    "g26_fm_check": """const fl = await api('fm_list'); await go('fm_make', {fid: fl.forms[0].id}); await W(1500); await mkCheck(mkTargets()); MK.step = 3; MK.cur = null; await mkDraw($('#view')); await W(1800);""",
    "g27_fm_company": """await go('fm_company'); await W(1500); hx('.card', '고정값', 1, 3); hx('.card', '이 채권의 값', 2, 3); hx('.card', '업무별 기본 양식', 3, 3);""",
    "g28_lg_doc": """await go('lg_doc', {type: '지급명령'}); await W(1800); hl('#docInfo', 1, 3); hx('.seg', '지급명령 신청서', 2, 3); hl('#make', 3, 3); hx('.card', '미리보기', 4, 3);""",
    "g29_xl": """await go('xl'); await W(1300); const a = pk('#view *', '엑셀 파일 고르기'); hl(a && a.closest('.card'), 1, 3); const b = pk('#view *', '조회할 사건 목록'); hl(b && b.parentElement && b.parentElement.parentElement, 2, 3);""",
    "g30_std": """await go('lg_std'); await W(1500); hx('.card', '송달료 1회분', 1, 3); hx('button', '+ 새 시행일', 2, 3);""",
    "g31_set_rule": """await go('settings', {p: 'rule'}); await W(1500); hl('.set-nav', 1, 3); hl(pk('#pane .card', '상태 분류 규칙'), 2, 3);""",
    "g32_set_todo": """await go('settings', {p: 'todo'}); await W(1500);""",
    "g33_set_run": """await go('settings', {p: 'run'}); await W(1500);""",
    "g34_set_menu": """await go('settings', {p: 'menu'}); await W(1500);""",
    "g35_set_link": """await go('settings', {p: 'link'}); await W(1500);""",
    "g36_set_save": """await go('settings', {p: 'save'}); await W(1500);""",
    "g37_set_look": """await go('settings', {p: 'look'}); await W(1500);""",
    # ---------------------------------------------------------------- 회수 분석
    "r01_console": """await go('console'); await W(2500); for (let i = 0; i < 100 && !document.querySelector('[data-rcgo]'); i++) await W(200); await W(400);
      hl('.rc-con', 1, 4); navOpen(); await W(200); const nv = $('#nav'); nv.scrollTop = $('#nav button[data-s="rc_home"]').offsetTop - 120; await W(200);
      hl('#nav button[data-s="rc_home"]', 2, 2); hl('#nav button[data-s="rc_anal"]', 0, 2);""",
    "r02_empty": """await rgo('rc_data'); RE("APP_ON=false;DATA_MODE='empty';renderEmpty()"); await W(500);
      rhl('.steps4', 1, 4); rhx('.card', '새 자료 넣기', 2, 4); rhx('.card', '먼저 둘러보기', 3, 4); rhx('button', '공통 양식 받기', 4, 3);""",
    "r03_data": """await rgo('rc_data', 'data'); await W(400);
      rhl(rcard('새 자료 넣기'), 1, 4); rhl(rcard('담아 둔 자료'), 2, 4); rhl(rcard('지금 쓰는 자료'), 3, 4); rhx('button', '공통 양식 받기', 4, 3);""",
    "r04_map": """await rgo('rc_data', 'data'); RE("impOpen('{{RAW}}')"); for (let i = 0; i < 150 && RE('IMP.busy'); i++) await W(200); await W(500);
      rhl('.isteps', 1, 4); rhl('.itabs', 2, 4); rhl(rpk('.row', '무슨 자료인가요?'), 3, 3); rhl(RD().querySelector('.card table.xl tbody tr:nth-child(2)'), 4, 2);""",
    "r04_values": """await rgo('rc_data', 'data'); RE("impOpen('{{RAW}}')"); for (let i = 0; i < 150 && RE('IMP.busy'); i++) await W(200);
      RE('impToValues()'); for (let i = 0; i < 150 && RE('IMP.busy'); i++) await W(200); await W(500);
      const v = RD().querySelectorAll('.ival')[2]; if (v) { RD().getElementById('view').scrollTop = v.offsetTop - 120; await W(300); rhl(v, 1, 4); rhl(v.querySelector('tbody tr td:nth-child(3)'), 2, 3); }""",
    "r05_staged": """await rgo('rc_data', 'data'); RE("impOpen('{{RAW}}')"); for (let i = 0; i < 150 && RE('IMP.busy'); i++) await W(200);
      RE('impToValues()'); for (let i = 0; i < 150 && RE('IMP.busy'); i++) await W(200); RE('impStage()'); for (let i = 0; i < 200 && RE('IMP.busy'); i++) await W(200); await W(800);
      const c = rcard('담아 둔 자료'); rhl(c.querySelector('table'), 1, 3); rhl(c.querySelector('details'), 2, 3); rhx('button', '이대로 넣기', 3, 3);""",
    "r05_rel": """await rgo('rc_data', 'data'); const c = rpk('.card', '해제 사유 나누기'); RD().getElementById('view').scrollTop = c.offsetTop - 20; await W(400);
      rhl(c, 1, 4); rhl(c.querySelector('tbody tr td:nth-child(4)'), 2, 3);""",
    "r06_dash": """await rgo('rc_home', 'dash'); await W(600); rhl('.today', 1, 4); rhx('.sec', '회수 현황', 2, 3); rhl('.ptabs', 3, 3);""",
    "r07_dash_lower": """await rgo('rc_home', 'dash'); await W(600); rscroll(700); await W(500);""",
    "r08_owner": """await rgo('rc_home', 'owner'); await W(600); rhl('table', 1, 3);""",
    "r09_miss": """await rgo('rc_miss', 'miss'); await W(600);""",
    "r10_miss_sel": """await rgo('rc_miss', 'miss'); await W(400); const tr = RD().querySelector('#view tbody tr'); tr && tr.click(); await W(800);""",
    "r11_batch": """await rgo('rc_judge', 'batch'); await W(600);""",
    "r12_case": """await rgo('rc_judge', 'case'); await W(800);""",
    "r13_case_lower": """await rgo('rc_judge', 'case'); await W(600); rscroll(600); await W(500);""",
    "r14_track": """await rgo('rc_judge', 'track'); await W(600);""",
    "r15_plan": """await rgo('rc_next', 'plan'); await W(800);""",
    "r16_lnext": """await rgo('rc_next', 'lnext'); await W(800);""",
    "r17_lact": """await rgo('rc_anal', 'lact'); await W(800);""",
    "r18_lcurve": """await rgo('rc_anal', 'lcurve'); await W(800);""",
    "r19_bank": """await rgo('rc_anal', 'bank'); await W(800);""",
    "r20_cross": """await rgo('rc_anal', 'cross'); await W(800);""",
    "r21_ltime": """await rgo('rc_anal', 'ltime'); await W(800);""",
    "r22_std": """await rgo('rc_std', 'std'); await W(600);""",
    "r23_help": """await rgo('rc_home', 'dash'); RE('ST.help=true;render()'); await W(700);""",
    "r24_stats_tax": """await rgo('rc_anal', 'stats'); RE("ST.sTab='tax';render()"); await W(700); rhl('.tbar .seg', 1, 3); rhl('.kpis', 2, 4); rhx('.card', '담당자별', 3, 3);""",
    "r25_stats_tax_list": """await rgo('rc_anal', 'stats'); RE("ST.sTab='tax';render()"); await W(500); const c = rpk('.card', '세무서 미압류 목록'); RD().getElementById('view').scrollTop = c.offsetTop - 20; await W(400);
      rhl(c.querySelector('.cb.row'), 1, 3); rhx('button', '목록 엑셀', 2, 3);""",
    "r26_stats_adj": """await rgo('rc_anal', 'stats'); RE("ST.sTab='adj';render()"); await W(700); rhl('.kpis', 1, 4); rhx('.card', '구분별', 2, 3); rhx('.card', '월별 실효·폐지', 3, 3);""",
    "r27_stats_adj_list": """await rgo('rc_anal', 'stats'); RE("ST.sTab='adj';render()"); await W(500); const c = rpk('.card', '급여 압류 후보'); RD().getElementById('view').scrollTop = c.offsetTop - 20; await W(400);
      rhl(c.querySelector('.seg'), 1, 3); rhl(c.querySelector('thead th:nth-child(7)'), 2, 2); rhx('button', '후보 엑셀', 3, 3);""",
    "r28_stats_pay": """await rgo('rc_anal', 'stats'); RE("ST.sTab='pay';ST.sPer='m';render()"); await W(700); rhl(RD().querySelector('#view .tbar:not(.ph .tbar)') || RD().querySelectorAll('.tbar')[1], 1, 3); rhl('.kpis', 2, 4); rhx('.card', '입금유형별 월별', 3, 3);""",
}


def make_raw_sample(path, n=300):
    """회수 분석 그림용: 채권마다 다른 원자료 모양 (제목 줄 · 다른 칸 이름 · 다른 값)"""
    import datetime as dt
    import random
    from openpyxl import Workbook
    R = random.Random(5)
    wb = Workbook()
    wb.remove(wb.active)
    d0 = dt.date(2026, 11, 1)
    c = wb.create_sheet("채권목록")
    c.append(["채권 목록 (B캐피탈 · 2026.11 추출)"])
    c.append([])
    c.append(["차주번호", "대출번호", "고객명", "관리담당", "총잔액", "시효만료일", "주민등록번호", "기준일자"])
    L = wb.create_sheet("법적조치")
    L.append(["조치번호", "차주번호", "대출번호", "조치구분", "세부구분", "관할법원", "사건번호", "접수일자", "확정일", "결정일자", "제3채무자구분"])
    P = wb.create_sheet("수납내역")
    P.append(["차주번호", "수납일자", "수납액", "수납구분", "추심은행", "조치번호"])
    X = wb.create_sheet("채무조정")
    X.append(["차주번호", "제도", "신청일자", "진행상태", "상태변경일"])
    for i in range(n):
        k = f"B{10000 + i}"
        c.append([k, f"N{20000 + i}", f"김O{i % 10}", R.choice(["최과장", "박대리", "이주임"]), R.randint(5, 300) * 10000,
                  (d0 + dt.timedelta(days=R.randint(-30, 1500))).isoformat(), f"{R.randint(60, 99)}0101-{R.choice([1, 2])}", "2026-11-01"])
        if R.random() < .6:
            ap = d0 - dt.timedelta(days=R.randint(400, 900))
            L.append([f"J{i}a", k, f"N{20000 + i}", "지급명령신청", "전자독촉", "서울중앙지방법원", f"{ap.year}차전{R.randint(1000, 99999)}", ap.isoformat(),
                      (ap + dt.timedelta(days=60)).isoformat(), "", ""])
            if R.random() < .7:
                ap2 = ap + dt.timedelta(days=R.randint(90, 300))
                L.append([f"J{i}b", k, f"N{20000 + i}", "채권압류 및 추심명령", R.choice(["예금채권", "예금", "급여채권"]), "서울중앙지방법원",
                          f"{ap2.year}타채{R.randint(1000, 99999)}", ap2.isoformat(), "", (ap2 + dt.timedelta(days=14)).isoformat(),
                          R.choice(["예금", "예금+세무서", "보험+세무서", "예금"])])
                if R.random() < .4:
                    P.append([k, (ap2 + dt.timedelta(days=60)).isoformat(), R.randint(5, 50) * 10000, "추심입금", R.choice(["국민", "신한은행", "NH농협"]), f"J{i}b"])
        for _ in range(R.randint(0, 3)):
            P.append([k, (d0 - dt.timedelta(days=R.randint(1, 700))).isoformat(), R.randint(1, 30) * 10000,
                      R.choice(["가상계좌입금", "무통장입금", "분납입금", "CMS자동이체", "대위변제"]), "", ""])
        if R.random() < .08:
            X.append([k, R.choice(["개인회생", "신용회복지원", "파산면책"]), "2024-03-01", R.choice(["폐지", "실효", "인가결정", "면책확정"]), "2025-08-01"])
    wb.save(path)
    return path


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def shoot():
    tmp = tempfile.mkdtemp(prefix="dv_manual_")
    port = free_port()
    env = dict(os.environ, LOCALAPPDATA=os.path.join(tmp, "la"))
    srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "app", "main.py"), "--serve", "--port", str(port), "--demo", os.path.join(tmp, "demo")],
                           env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    ui = os.path.join(ROOT, "app", "ui")
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/index.html", timeout=1)
                break
            except Exception:
                time.sleep(0.3)

        def api(name, args=None):
            req = urllib.request.Request(base + "/api", data=json.dumps({"name": name, "args": args or {}}).encode(), headers={"Content-Type": "application/json"})
            return json.loads(urllib.request.urlopen(req).read())["data"]
        # 시연 자료 준비: 내 이름 · 배당사건 조회 · 법조치 자료 · 매칭 · 저장
        api("setting_set", {"path": "me", "value": "김담당"})
        api("setting_set", {"path": "save.export_dir", "value": os.path.join(tmp, "out")})  # 예시 파일 등은 임시 폴더에
        only = next((a.split("=", 1)[1] if "=" in a else sys.argv[sys.argv.index(a) + 1] for a in sys.argv if a.startswith("--only")), "")
        only = set(x for x in only.split(",") if x)
        if not only or not all(o.startswith("r") for o in only):  # 배당기일 화면용 시연 자료 (회수 분석만 찍을 때는 건너뜀)
            from demo import DV_CASES, DV_LAW  # noqa
            st = api("dv_search", {"text": DV_CASES})
            for _ in range(30):
                if not (st or {}).get("case"):
                    break
                st = api("run_submit", {"answer": "123456"})
            api("dv_law_text", {"text": DV_LAW})
            api("dv_match")
            api("dv_save")
            api("dv_match")  # 매칭 결과 탭이 보이게 다시
        raw = make_raw_sample(os.path.join(tmp, "B캐피탈_원자료_2611.xlsx"))
        os.makedirs(SHOTS, exist_ok=True)
        with open(os.path.join(ui, "index.html"), encoding="utf-8") as f:
            html = f.read()
        for name, js in STEPS.items():
            if only and name not in only and not any(o.endswith('*') and name.startswith(o[:-1]) for o in only):
                continue
            page = html.replace("</body>", CSS + "<script>" + HELPERS +
                                "setTimeout(async () => { try { " + js.replace("{{RAW}}", raw.replace("\\", "/")) + " } catch (e) { document.title = 'ERR ' + e.message; } window.__done = true; }, 1800);</script></body>")
            with open(os.path.join(ui, "_shot.html"), "w", encoding="utf-8") as f:
                f.write(page)
            png = os.path.join(SHOTS, name + ".png")
            if name.startswith("r"):  # 회수 분석: 실제 시간으로 준비 신호를 기다렸다 찍음 (가상 시간으로는 안 끝남)
                r = subprocess.run(["node", os.path.join(ROOT, "tools", "cdp_shot.mjs"), CHROME, f"{base}/_shot.html?mode=browser", png, "90000"],
                                   capture_output=True, text=True, timeout=200)
                print("  찍음", name, r.stdout.strip() or r.stderr.strip()[-200:])
                continue
            subprocess.run([CHROME, "--headless=new", "--disable-gpu", *CHROME_KEYCHAIN_ARGS, "--hide-scrollbars", f"--user-data-dir={tmp}/chrome",
                            "--window-size=1366,855", "--force-device-scale-factor=2", "--virtual-time-budget=14000",
                            f"--screenshot={png}", f"{base}/_shot.html?mode=browser"], capture_output=True, timeout=120)
            if os.path.exists(png):  # 헤드리스 창은 위 87px 를 빼고 화면을 그리므로, 화면(1366×768) 부분만 남긴다
                from PIL import Image
                im = Image.open(png)
                im.crop((0, 0, 1366 * 2, 768 * 2)).save(png)
            print("  찍음", name, "✓" if os.path.exists(png) else "✕")
    finally:
        srv.terminate()
        try:
            os.remove(os.path.join(ui, "_shot.html"))
        except OSError:
            pass


_IMG = {}


def img_data(name, fmt="WEBP"):
    """PNG → 화면용 WebP(가볍게) · PDF용 JPEG(PDF 안에서 다시 커지지 않게) base64"""
    if (name, fmt) in _IMG:
        return _IMG[(name, fmt)]
    from PIL import Image
    im = Image.open(os.path.join(SHOTS, name + ".png")).convert("RGB")
    w = 2200 if fmt == "WEBP" else 1800
    if im.width > w:
        im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    if fmt == "WEBP":
        im.save(buf, "WEBP", quality=80, method=6)
    else:
        im.save(buf, "JPEG", quality=74, optimize=True, progressive=True)
    _IMG[(name, fmt)] = f"data:image/{fmt.lower()};base64," + base64.b64encode(buf.getvalue()).decode()
    return _IMG[(name, fmt)]


def include(src_name, secs, start, pre="dv-", label="배당"):
    """다른 사용법의 장(section id=cN)을 가져와 번호를 이어 붙인다: cN → {pre}cN, 「1-2.」 → 「13-2.」"""
    with open(os.path.join(ROOT, "packaging", "manual", src_name), encoding="utf-8") as f:
        src = f.read()
    nmap = {sec[1:]: str(start + i) for i, sec in enumerate(secs)}
    out = []
    for sec in secs:
        m = re.search(r'<section class="ch" id="%s">.*?</section>' % re.escape(sec), src, re.S)
        if m:
            out.append(m.group(0))
    html = "\n".join(out)
    k = lambda x: nmap.get(x, x)
    html = re.sub(r'<a href="#c(\d)-(\d+)">\1-\2</a>', lambda m: f'<a href="#{pre}c{m.group(1)}-{m.group(2)}">{k(m.group(1))}-{m.group(2)}</a>', html)
    html = re.sub(r'(id|href)="#?c(\d)((?:-\d+)?)"', lambda m: f'{m.group(1)}="{"#" if m.group(1) == "href" else ""}{pre}c{m.group(2)}{m.group(3)}"', html)
    html = re.sub(r'(<h3 id="%sc(\d)-\d+">)\2-' % re.escape(pre), lambda m: m.group(1) + k(m.group(2)) + "-", html)
    html = re.sub(r'<span class="no">(\d)</span> ', lambda m: f'<span class="no">{k(m.group(1))}</span> {label} · ', html)
    return html


MANUALS = [("종합관리_사용법.src.html", "종합관리_사용법"), ("배당기일_사용법.src.html", "배당기일_사용법"), ("회수분석_사용법.src.html", "회수분석_사용법")]


def build():
    sys.path.insert(0, os.path.join(ROOT, "app"))
    from bridge import VERSION
    out_dir = os.path.join(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)
    pick = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--manual=")), "")  # --manual=회수분석 → 그 사용법만
    for src_name, out_name in MANUALS:
        src = os.path.join(ROOT, "packaging", "manual", src_name)
        if not os.path.exists(src) or (pick and not out_name.startswith(pick)):
            continue
        with open(src, encoding="utf-8") as f:
            html = f.read()
        meta = dict(x.split("=", 1) for x in (re.search(r"<!--meta (.*?)-->", html) or [None, ""])[1].split("|") if "=" in x)
        html = re.sub(r"<!--meta .*?-->\n?", "", html)
        if "{{HEAD}}" in html:
            rd = lambda n: open(os.path.join(ROOT, "packaging", "manual", n), encoding="utf-8").read()
            html = html.replace("{{HEAD}}", rd("_shell_head.html")).replace("{{FOOT}}", rd("_shell_foot.html"))
            html = html.replace("{{TITLE}}", meta.get("title", "사용법")).replace("{{LOGO}}", meta.get("logo", "종")).replace("{{HINT}}", meta.get("hint", ""))
            html = html.replace("{{CHIPS}}", "".join(f"<button>{c}</button>" for c in meta.get("chips", "").split(",") if c))
        html = re.sub(r"\{\{include:([^|}]+)\|([^|}]+)\|(\d+)(?:\|([^|}]+)\|([^|}]+))?\}\}",
                      lambda m: include(m.group(1), m.group(2).split(","), int(m.group(3)), *(m.group(4, 5) if m.group(4) else ())), html)
        html = html.replace("{{VERSION}}", VERSION).replace("{{DATE}}", time.strftime("%Y.%m.%d"))
        out_html = os.path.join(out_dir, out_name + ".html")
        with open(out_html, "w", encoding="utf-8") as f:
            f.write(re.sub(r"\{\{img:([a-z0-9_]+)\}\}", lambda m: img_data(m.group(1)), html))
        pdf_html = os.path.join(tempfile.mkdtemp(prefix="dv_ph_"), out_name + ".html")
        with open(pdf_html, "w", encoding="utf-8") as f:
            f.write(re.sub(r"\{\{img:([a-z0-9_]+)\}\}", lambda m: img_data(m.group(1), "JPEG"), html))
        out_pdf = os.path.join(out_dir, out_name + ".pdf")
        tmp = tempfile.mkdtemp(prefix="dv_pdf_")
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", *CHROME_KEYCHAIN_ARGS, f"--user-data-dir={tmp}", "--no-pdf-header-footer",
                        "--generate-pdf-document-outline", "--virtual-time-budget=6000", f"--print-to-pdf={out_pdf}",
                        "file://" + pdf_html + "?print=1"], capture_output=True, timeout=300)
        shutil.rmtree(tmp, ignore_errors=True)
        print("만듦:", out_html, f"({os.path.getsize(out_html) // 1024}KB)")
        print("만듦:", out_pdf, f"({os.path.getsize(out_pdf) // 1024}KB)" if os.path.exists(out_pdf) else "✕ PDF 실패")


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(ROOT, "app"))
    if "--build-only" not in sys.argv:
        shoot()
    build()
