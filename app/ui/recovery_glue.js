/* 회수 분석 — recovery.html 을 본문 자리에 띄워 종합관리 메뉴·테마·화면 이동과 이어 줌.
   자료는 「회수 자료 넣기」로 넣은 공통 양식 v2 (bridge_recovery.py 가 읽고 채권 폴더에 저장).
   넣은 자료가 없으면 빈 화면(자료 넣기 안내), 시연 판(--demo)이면 예시 자료. */
'use strict';
(function () {
  const MAP = {rc_home: 'dash', rc_miss: 'miss', rc_judge: 'batch', rc_next: 'plan', rc_anal: 'lact', rc_data: 'data', rc_std: 'std'};
  const BACK = {dash: 'rc_home', owner: 'rc_home', miss: 'rc_miss', batch: 'rc_judge', case: 'rc_judge', track: 'rc_judge', lnext: 'rc_next', plan: 'rc_next', lact: 'rc_anal', lcurve: 'rc_anal', ltime: 'rc_anal', bank: 'rc_anal', cross: 'rc_anal', stats: 'rc_anal', data: 'rc_data', std: 'rc_std'};

  // 메뉴 묶음: 법조치 다음에 「회수 분석」, 자료·설정 묶음에 하나씩
  const gi = MENU_DEFAULT.findIndex(g => g.name === '법조치');
  MENU_DEFAULT.splice(gi < 0 ? MENU_DEFAULT.length - 1 : gi + 1, 0, {name: '회수 분석', items: ['rc_home', 'rc_miss', 'rc_judge', 'rc_next', 'rc_anal']});
  MENU_FOLD_DEFAULT['회수 분석'] = false;
  const add = (name, id) => { const g = MENU_DEFAULT.find(x => x.name === name); if (g) g.items.push(id); };
  add('자료', 'rc_data'); add('설정', 'rc_std');

  const st = document.createElement('style');
  st.textContent = `
  .rc-frame{position:fixed;border:0;z-index:3;display:none;background:var(--bg)}
  .rc-con .card-h .chip{margin-left:auto}
  .rc-con-g{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));padding:14px 0 0}
  .rc-con-g>div{padding:12px 22px 16px;border-left:1px solid var(--line);cursor:pointer}
  .rc-con-g>div:first-child{border-left:0}
  .rc-con-g>div:hover{background:var(--hover)}
  .rc-con-g .l{font-size:13px;color:var(--sub)}
  .rc-con-g .v{font-size:24px;font-weight:700;letter-spacing:-.03em;margin:2px 0}
  .rc-con-g .s{font-size:12px;color:var(--faint)}
  .rc-home{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:10px 14px;margin-bottom:14px}
  .rc-h-t{font-size:13px;font-weight:700;margin-right:6px}
  .rc-h-i{border:1px solid var(--line);background:var(--panel2);border-radius:10px;padding:5px 11px;font-size:13px;color:var(--sub);display:inline-flex;gap:6px;align-items:baseline}
  .rc-h-i b{color:var(--text);font-weight:700}
  .rc-h-i:hover{border-color:var(--text);color:var(--text)}
  @media (max-width:900px){.rc-con-g{grid-template-columns:repeat(2,minmax(0,1fr))}}`;
  document.head.appendChild(st);

  // 회수 분석 화면 파일에도 판 번호를 붙여 예전 판이 캐시에서 나오지 않게 (빌드 때 이 파일 주소에 붙은 ?v= 를 그대로 씀)
  const VER = ((document.currentScript && document.currentScript.src) || '').split('v=')[1] || String(Date.now());
  let fr = null, ready = false, want = null, sumCbs = [];  // 요약을 기다리는 곳(메뉴 숫자·콘솔 카드·확인할 것 줄)이 여럿일 수 있음
  function frame() {
    if (fr) return fr;
    fr = document.createElement('iframe');
    fr.className = 'rc-frame'; fr.title = '회수 분석'; fr.src = 'recovery.html?embed=1&v=' + encodeURIComponent(VER);
    fr.addEventListener('load', () => { ready = true; if (want) send(want); if (sumCbs.length) ask(); });
    document.body.appendChild(fr);
    return fr;
  }
  function place() {
    if (!fr) return;
    const m = $('main').getBoundingClientRect();
    Object.assign(fr.style, {left: m.left + 'px', top: m.top + 'px', width: m.width + 'px', height: m.height + 'px'});
  }
  function send(v) { want = v; if (ready) fr.contentWindow.postMessage({rcGo: v}, '*'); }
  function ask() { if (ready) fr.contentWindow.postMessage({rcAsk: 'summary'}, '*'); }
  function hide() { if (fr) fr.style.display = 'none'; }

  for (const [id, view] of Object.entries(MAP)) {
    SCREENS[id] = async v => { v.innerHTML = ''; frame(); place(); fr.style.display = 'block'; send(view); };
  }
  const goApp = go;
  // 다른 화면으로 가면 회수 분석 틀을 숨김
  go = async function (id, ...rest) { if (!MAP[id]) hide(); return goApp.call(this, id, ...rest); };  // eslint-disable-line no-global-assign
  // 채권을 바꾸면 회수 분석 틀을 버려서, 다음에 열 때 그 채권의 자료를 새로 불러오게 함
  if (typeof afterBook === 'function') {
    const abApp = afterBook;
    afterBook = async function (...a) { if (fr) { fr.remove(); fr = null; ready = false; } return abApp.apply(this, a); };  // eslint-disable-line no-global-assign
  }
  window.addEventListener('resize', place);
  if (window.ResizeObserver) new ResizeObserver(place).observe($('main'));

  // 끌어다 놓기: 회수 분석 틀은 파일 경로를 못 받으니, 끌기 시작하면 잠깐 틀을 비켜 종합관리 창이 받게 함
  let dragT = null;
  const unDrag = () => { if (fr) fr.style.pointerEvents = ''; clearTimeout(dragT); };
  const appEv = window.onAppEvent;
  window.onAppEvent = ev => {
    if (ev && ev.type === 'drop' && fr && fr.style.display === 'block') {
      unDrag();
      if (ev.paths && ev.paths.length) { const was = CUR === 'rc_data'; if (!was) go('rc_data'); setTimeout(() => fr.contentWindow.postMessage({rcDrop: ev.paths[0]}, '*'), was ? 0 : 400); }
      return;
    }
    if (appEv) appEv(ev);
  };
  document.addEventListener('drop', unDrag);
  document.addEventListener('dragleave', e => { if (!e.relatedTarget) unDrag(); });

  window.addEventListener('message', e => {
    const d = e.data || {};
    if (d.rcDrag && fr) { fr.style.pointerEvents = 'none'; clearTimeout(dragT); dragT = setTimeout(unDrag, 8000); }
    if (d.rcView && BACK[d.rcView]) $$('#nav button').forEach(b => b.classList.toggle('on', b.dataset.s === BACK[d.rcView]));
    if (d.rcGoApp && d.rcGoApp.id) go(d.rcGoApp.id, d.rcGoApp.args || {});
    if (d.rcSummary && sumCbs.length) { const l = sumCbs; sumCbs = []; l.forEach(f => f(d.rcSummary)); }
  });

  // 메뉴 알림 숫자 + 현황 콘솔 카드
  function pills(s) {
    const set = (id, n, red) => { const b = $(`#nav button[data-s="${id}"] .pill`); if (b) { b.textContent = n; b.hidden = !n; b.classList.toggle('red', !!red); } };
    set('rc_miss', s.empty ? 0 : s.miss, true); set('rc_judge', s.empty ? 0 : s.ready);
    // 메뉴를 다시 그리기 전(처음 몇 초)에는 묶음 표시가 아직 없으니 건너뜀
    if (typeof markNav === 'function' && !$$('#nav .menu-label').some(l => !l.querySelector('.fdot'))) { try { markNav(); } catch (e) { /* 다음에 다시 */ } }
  }
  const chipTxt = s => s.mode === 'real' ? `자료 기준일 ${s.asof}` : s.mode === 'demo' ? '예시 자료' : '넣은 자료 없음';
  function summary(cb) { sumCbs.push(cb); frame(); ask(); }
  const conApp = SCREENS.console;
  SCREENS.console = async v => {
    await conApp(v);
    const k = $('.con-kpis', v);
    if (!k) return;
    k.insertAdjacentHTML('afterend', `<div class="card rc-con" style="margin-bottom:16px;overflow:hidden"><div class="card-h"><h2>회수 분석</h2><span class="chip" id="rcConChip"></span></div>
      <div class="rc-con-g" id="rcConG"><div class="faint small" style="padding:6px 22px 14px">불러오는 중…</div></div></div>`);
    summary(s => {
      pills(s);
      const g = $('#rcConG');
      if (!g) return;
      const c = $('#rcConChip');
      if (c) { c.textContent = chipTxt(s); c.className = 'chip' + (s.mode === 'real' ? '' : ' warn'); }
      if (s.empty) {
        g.innerHTML = '<div style="grid-column:1/-1;padding:4px 22px 16px;display:flex;align-items:center;gap:12px;cursor:default;border-left:0"><span class="muted">넣은 자료가 없어요. 공통 양식 v2 엑셀을 넣으면 놓친 것·압류 판단·다음 법조치가 여기 바로 보여요.</span><button class="btn sm primary" data-rcgo="rc_data" style="margin-left:auto">회수 자료 넣기</button></div>';
        $$('[data-rcgo]', g).forEach(x => x.onclick = () => go(x.dataset.rcgo));
        return;
      }
      const t = (id, l, val, sub) => `<div data-rcgo="${id}"><div class="l">${l}</div><div class="v num">${val}</div><div class="s">${sub}</div></div>`;
      g.innerHTML = t('rc_miss', '놓친 것·할 것', `${s.miss.toLocaleString()}건`, s.missTxt) + t('rc_judge', '압류 바로 결정', `${s.ready}건`, `확인 필요·막힘 ${s.check}건`) +
        t('rc_next', '다음 법조치 추천', `${s.next.toLocaleString()}명`, '기대 순증분 10만 넘는 채무자') + t('rc_anal', '법조치 순증분', s.netTxt, '최근 12개월 송달 · 비용 뺌');
      $$('[data-rcgo]', g).forEach(x => x.onclick = () => go(x.dataset.rcgo));
    });
  };
  // 확인할 것: 맨 위에 회수 분석에서 볼 것 한 줄
  const homeApp = SCREENS.home;
  SCREENS.home = async (v, a) => {
    await homeApp(v, a);
    const h = $('.head', v);
    if (!h) return;
    h.insertAdjacentHTML('afterend', `<div class="card rc-home" id="rcHome"><span class="rc-h-t">회수 분석</span><span class="faint small">불러오는 중…</span></div>`);
    summary(s => {
      pills(s);
      const b = $('#rcHome');
      if (!b) return;
      const l = (id, n, t) => `<button class="rc-h-i" data-rcgo="${id}"><b>${n}</b>${t}</button>`;
      if (s.empty) {
        b.innerHTML = '<span class="rc-h-t">회수 분석</span><span class="faint small">넣은 자료 없음</span>' + l('rc_data', '', '회수 자료 넣기');
        $$('[data-rcgo]', b).forEach(x => x.onclick = () => go(x.dataset.rcgo));
        return;
      }
      b.innerHTML = `<span class="rc-h-t">회수 분석</span>${l('rc_miss', s.miss.toLocaleString(), '놓친 것·할 것')}${l('rc_judge', s.ready, '압류 바로 결정')}${l('rc_judge', s.check, '압류 확인 필요')}${l('rc_next', s.next.toLocaleString(), '다음 법조치 추천')}<span class="chip${s.mode === 'real' ? '' : ' warn'}" style="margin-left:auto">${chipTxt(s)}</span>`;
      $$('[data-rcgo]', b).forEach(x => x.onclick = () => go(x.dataset.rcgo));
    });
  };
  // 처음 켤 때: 종합관리가 회수 분석보다 먼저 화면을 그렸으면 다시 그려 카드·주소(#rc_…)를 맞춤
  // 메뉴가 다 그려진 뒤(묶음 표시가 생긴 뒤)에만 다시 그림 — 늦으면 0.3초씩 최대 20번 기다림
  let tries = 0;
  const fixStart = () => { try {
    if ($$('#nav .menu-label').some(l => !l.querySelector('.fdot')) || !$('#view').innerHTML) { if (++tries < 20) setTimeout(fixStart, 300); return; }
    const h = (location.hash || '').slice(1).split(/[/?]/)[0];
    if (MAP[h] && CUR !== h) go(h);
    else if ((CUR === 'console' && !$('.rc-con')) || (CUR === 'home' && !$('#rcHome'))) go(CUR, ARGS, {back: true});
  } catch (e) { /* 다음 화면 이동 때 맞춰짐 */ } };
  setTimeout(fixStart, 300);
  // 처음 켤 때 메뉴 숫자
  setTimeout(() => summary(pills), 1500);
})();
