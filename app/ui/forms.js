// 회사 양식 서류 — 양식함 · 칸 정하기 · 서류 만들기(대상 → 검수 → 마지막 확인) · 우리 회사 정보
Object.assign(NAV_OF, {fm_edit: 'fm', fm_make: 'fm', fm_company: 'fm', lg_doc: 'fm'});

const FM_TYPES = {text: '글자', long: '긴 글', over: '덮어쓰기', check: '체크', seal: '도장'};
const FMB = {f: 'all', q: ''};
const FM_IMG = {};
const FMST = {ok: '<span class="chip ok">정상</span>', bad: '<span class="chip bad">빈 칸</span>', warn: '<span class="chip warn">확인</span>'};
let FM_CSS = {gothic: '"Malgun Gothic",sans-serif', myeongjo: 'Batang,"AppleMyungjo",serif'};
const fmToday = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);

async function fmImg(fid, p, ver) {
  const k = `${fid}|${p}|${ver || 0}`;
  if (!FM_IMG[k]) FM_IMG[k] = await api('fm_page', {fid, p});
  return FM_IMG[k];
}
function fmTabs(cur) {
  const T = [['fm', '양식함'], ['fm_make', '서류 만들기'], ['fm_company', '우리 회사 정보'], ['lg_doc', '기본 서류']];
  return `<div class="seg">${T.map(([k, n]) => `<button class="${cur === k ? 'on' : ''}" data-go="${k}">${n}</button>`).join('')}</div>`;
}
function fmPaper(pg, img, inner, cls = '', id = '') {
  return `<div class="fm-paper ${cls}" ${id ? `id="${id}"` : ''} style="width:${pg.w}px;height:${pg.h}px"><img src="${img}" draggable="false" alt="">${inner}</div>`;
}
// 서버가 계산한 글자 크기·줄로 칸 위에 값을 그린다 (저장하는 PDF와 같은 크기)
function fmVals(form, lay, p, vals) {
  const css = FM_CSS[form.font] || FM_CSS.myeongjo;
  return (lay || []).map(l => {
    const f = form.fields[l.i];
    if (!f || (f.p || 0) !== p) return '';
    const st = `left:${f.x}px;top:${f.y}px;width:${f.w}px;height:${f.h}px`;
    if (f.type === 'check') return l.check ? `<div class="fm-val ck" data-k="${f.item}" style="${st};font-size:${f.h + 1}px">✓</div>` : '';
    if (f.type === 'seal') return l.seal ? `<div class="fm-val seal" style="${st}">인감</div>` : `<div class="fm-val sealoff" style="${st}">(인감)</div>`;
    if (l.empty) return `<div class="fm-val empty ${f.type === 'over' ? 'over' : ''}" data-k="${f.item}" style="${st}"></div>`;
    if (!l.lines || !l.lines.length) return f.type === 'over' ? `<div class="fm-val over" style="${st}"></div>` : '';
    return `<div class="fm-val ${f.type} ${l.flow ? 'flow' : ''}" data-k="${f.item}" style="${st};font-size:${l.px}px;font-family:${css}">${l.lines.map(esc).join('<br>')}</div>`;
  }).join('');
}

// ================================================================== 양식함
SCREENS.fm = async v => {
  const d = await api('fm_list');
  const q = FMB.q.trim();
  const groups = ['all', 'fav'].concat(d.groups.filter(g => d.forms.some(f => f.grp === g)));
  const list = d.forms.filter(f => (FMB.f === 'all' || (FMB.f === 'fav' ? f.fav : f.grp === FMB.f)) && (!q || f.name.includes(q)));
  const cnt = g => g === 'all' ? d.forms.length : g === 'fav' ? d.forms.filter(f => f.fav).length : d.forms.filter(f => f.grp === g).length;
  v.innerHTML = head(`${esc(INFO.book)} · 회사 양식 PDF를 그대로 쓰고, 바뀌는 칸에만 원장·송달·엑셀 값을 채워요`, '서류 작성', fmTabs('fm')) + `
    <div class="fm-drop" id="fmAdd"><div class="ic">+</div><div style="flex:1"><b>회사 양식 PDF 넣기</b>
      <div class="small muted" style="margin-top:3px">한글·워드에서 저장한 PDF면 낱말 옆 칸과 □ 체크 칸을 자동으로 찾아 줘요. 스캔한 PDF는 칸을 직접 그려요. 양식마다 한 번만 정하면 계속 써요.</div></div>
      <button class="btn" id="fmImp">동료 양식 가져오기</button></div>
    ${d.forms.length ? `<div class="fm-bar"><input class="field" id="fmQ" placeholder="양식 이름 찾기" value="${esc(FMB.q)}" style="width:220px">
      <div class="seg">${groups.map(g => `<button class="${FMB.f === g ? 'on' : ''}" data-f="${g}">${g === 'all' ? '전체' : g === 'fav' ? '★ 즐겨찾기' : esc(g)} <span class="faint">${cnt(g)}</span></button>`).join('')}</div>
      <span style="flex:1"></span><span class="small faint">즐겨찾기 → 최근 쓴 순</span></div>
    <div class="card fm-list">${list.map(f => `<div class="fm-row">
        <button class="fm-star ${f.fav ? 'on' : ''}" data-fav="${f.id}" title="즐겨찾기">${f.fav ? '★' : '☆'}</button>
        <div class="fm-thumb"></div>
        <div style="min-width:0"><div><b>${esc(f.name)}</b> <span class="chip wait">${esc(f.grp)}</span>${f.tasks.map(t => ` <span class="chip ok">${esc(t)} 기본 양식</span>`).join('')}</div>
          <div class="small faint" style="margin-top:3px">${esc(f.file)} · ${f.pages}쪽 · 칸 ${f.n}개 · ${f.uses || 0}건 만듦${f.used ? ' · 마지막 ' + md(f.used) : ''} · ${f.ver}판</div></div>
        <div class="row-gap"><button class="btn sm primary" data-make="${f.id}">서류 만들기</button><button class="btn sm" data-edit="${f.id}">칸 수정</button><button class="btn sm ghost" data-exp="${f.id}">내보내기</button></div>
      </div>`).join('') || '<div class="card-b small faint">맞는 양식이 없어요.</div>'}</div>`
    : empty('아직 등록한 양식이 없어요', '위에서 회사 양식 PDF를 넣어 주세요. 써 보고 싶으면 견본 주소보정서를 넣어 볼 수 있어요.', '<button class="btn" id="fmSample">견본 양식 넣어 보기</button>')}`;
  $('#fmAdd').onclick = e => { if (e.target.closest('#fmImp')) return; safe(async () => {
    let p = null;
    if (MODE === 'browser') p = await modal('PDF 위치', '<label class="lb">양식 PDF의 전체 경로</label><input class="field" id="fp" placeholder="C:\\Users\\...\\주소보정서.pdf">', [{text: '취소'}, {text: '넣기', cls: 'primary', value: bg => $('#fp', bg).value.trim() || false}]);
    const id = await api('fm_add', p ? {path: p} : {});
    if (id) go('fm_edit', {id, fresh: true});
  }); };
  $('#fmImp').onclick = () => safe(async () => {
    let p = null;
    if (MODE === 'browser') p = await modal('양식 파일 위치', '<label class="lb">.양식.zip 파일의 전체 경로</label><input class="field" id="fp">', [{text: '취소'}, {text: '가져오기', cls: 'primary', value: bg => $('#fp', bg).value.trim() || false}]);
    const id = await api('fm_import', p ? {path: p} : {});
    if (id) { toast('양식을 가져왔어요'); go('fm_edit', {id}); }
  });
  if ($('#fmSample')) $('#fmSample').onclick = () => safe(async () => { const id = await api('fm_sample'); go('fm_edit', {id, fresh: true}); });
  if ($('#fmQ')) $('#fmQ').oninput = e => { FMB.q = e.target.value; clearTimeout(FMB.t); FMB.t = setTimeout(async () => { await go('fm'); const i = $('#fmQ'); i.focus(); i.setSelectionRange(99, 99); }, 250); };
  $$('[data-f]', v).forEach(b => b.onclick = () => { FMB.f = b.dataset.f; go('fm'); });
  $$('[data-fav]', v).forEach(b => b.onclick = () => safe(async () => { await api('fm_fav', {fid: b.dataset.fav, on: !b.classList.contains('on')}); go('fm'); }));
  $$('[data-make]', v).forEach(b => b.onclick = () => go('fm_make', {fid: b.dataset.make}));
  $$('[data-edit]', v).forEach(b => b.onclick = () => go('fm_edit', {id: b.dataset.edit}));
  $$('[data-exp]', v).forEach(b => b.onclick = () => safe(async () => { const p = await api('fm_export', {fid: b.dataset.exp}); toast('내보냈어요: ' + p.split(/[\\/]/).pop()); }));
};

// ================================================================== 칸 정하기
let ED = null;
const FM_SAMPLE = () => ({company: (S.legal && S.legal.creditor && S.legal.creditor.name) || '우리 회사 주식회사', company_addr: (S.legal && S.legal.creditor && S.legal.creditor.addr) || '서울 ○○구 ○○로 00',
  ceo: (S.legal && S.legal.creditor && S.legal.creditor.rep) || '○○○', agent: (S.legal && S.legal.agent) || '담당 ○○○', phone: '02-000-0000', creditor: '○○캐피탈 주식회사',
  debtor: '홍길동', debtor_addr: '서울 ○○구 ○○로 12', new_addr: '경기도 ○○시 ○○구 예시로 45, 3층', case_no: '2026가소12345', case_name: '양수금', court: '수원지방법원',
  amount: 3412000, mgmt_no: '110-123-456789', date: fmToday(), reason: '이사불명', req: '재송달', __seal: true});
SCREENS.fm_edit = async (v, a) => {
  if (!ED || ED.id !== a.id || a.fresh) {
    const d = await api('fm_get', {fid: a.id});
    FM_CSS = d.css || FM_CSS;
    ED = {id: a.id, form: d.form, items: d.items, groups: d.groups, fields: JSON.parse(JSON.stringify(d.form.fields)), sel: -1, page: 0, preview: false, lay: null,
      name: d.form.name, grp: d.form.grp, font: d.form.font || 'myeongjo', scanned: false};
    if (!ED.fields.length) {
      const r = await api('fm_detect', {fid: a.id});
      ED.scanned = r.scanned;
      ED.fields = r.fields;
      setTimeout(() => toast(r.scanned ? '스캔한 PDF라 글자를 읽지 못했어요. 칸을 직접 그려 주세요.' : `칸 ${r.fields.length}곳을 찾아 제안했어요. 맞는지 확인해 주세요.`), 200);
    }
  }
  await fmEditDraw(v);
};
async function fmEditDraw(v) {
  v = v || $('#view');
  const E = ED, F = E.fields, pg = E.form.pages[E.page];
  const img = await fmImg(E.id, E.page, E.form.ver);
  const IT = Object.fromEntries(E.items.map(i => [i.k, i]));
  if (E.preview && !E.lay) {
    const r = await api('fm_check', {fid: E.id, items: [{tid: 's', vals: FM_SAMPLE()}], full: true, fields: F.filter(f => f.item && !f.sug), font: E.font});
    const real = F.filter(f => f.item && !f.sug);
    E.lay = r.s.layout.map(l => Object.assign({}, l, {i: F.indexOf(real[l.i])}));
  }
  const nSug = F.filter(f => f.sug).length;
  const lab = f => f.item ? (IT[f.item] || {n: f.item}).n + (f.type === 'check' ? ' = ' + (f.opt || '?') : '') : '항목 고르기';
  const boxes = F.map((f, i) => (f.p || 0) !== E.page ? '' : `<div class="fm-fd ${f.sug ? 'sug' : ''} ${!f.item ? 'none' : ''} ${f.type === 'check' ? 'ck' : ''} ${E.sel === i ? 'sel' : ''}" data-i="${i}"
      style="left:${f.x}px;top:${f.y}px;width:${f.w}px;height:${f.h}px"><span class="no">${i + 1}</span><span class="tag">${i + 1}. ${esc(lab(f))}${f.sug ? ' · 제안' : ''}</span><span class="rs" data-rs="${i}"></span></div>`).join('');
  const pv = E.preview && E.lay ? fmVals({fields: F, font: E.font}, E.lay, E.page) : '';
  v.innerHTML = head(`<a data-go="fm">양식함</a> · 칸 정하기`, `${esc(E.name)} — 바뀌는 칸 정하기`,
    `<button class="btn danger" id="edDel">양식 지우기</button>`) +
    `<div class="fm-ed"><div>
      <div class="fm-tool"><button class="btn sm primary" id="edFind">🔍 칸 자동 찾기</button>
        ${E.form.pages.length > 1 ? `<div class="seg">${E.form.pages.map((_, i) => `<button class="${E.page === i ? 'on' : ''}" data-pg="${i}">${i + 1}쪽</button>`).join('')}</div>` : ''}
        <span class="small faint">빈 곳을 끌면 새 칸 · 칸을 끌면 이동 · 모서리로 크기 · Delete로 지우기</span><span style="flex:1"></span>
        <label class="small" style="display:flex;gap:6px;align-items:center"><input type="checkbox" class="cbx" id="edPv" ${E.preview ? 'checked' : ''}>견본 값 넣어 보기</label></div>
      ${E.scanned ? '<div class="notice" style="margin:0 0 10px">스캔한 PDF라 글자를 읽지 못했어요. 값이 들어갈 자리를 끌어서 직접 그려 주세요.</div>' : ''}
      ${fmPaper(pg, img, pv + boxes, 'edit' + (E.preview ? ' hl' : ''), 'edPaper')}
    </div>
    <div class="fm-side">
      <div class="card"><div class="card-b fm-meta">
        <div><label class="lb">양식 이름</label><input class="field" id="edName" value="${esc(E.name)}"></div>
        <div class="form" style="margin-top:8px"><div><label class="lb">묶음</label><select class="field" id="edGrp">${E.groups.map(g => `<option ${E.grp === g ? 'selected' : ''}>${g}</option>`).join('')}</select></div>
        <div><label class="lb">채울 글꼴</label><select class="field" id="edFont"><option value="myeongjo" ${E.font === 'myeongjo' ? 'selected' : ''}>바탕 (명조)</option><option value="gothic" ${E.font === 'gothic' ? 'selected' : ''}>맑은 고딕</option></select></div></div>
      </div></div>
      ${E.sel >= 0 && F[E.sel] ? fmFieldCard(F[E.sel], E.sel, IT) : `<div class="card"><div class="card-b small muted" style="line-height:1.65"><b style="color:var(--text)">칸을 고르거나 새로 그려 주세요</b><br>
        「칸 자동 찾기」는 낱말 옆 빈칸·밑줄, <b>□ 체크 칸</b>(옆 글자로 선택지까지), 「○○법원 귀중」·「20 . . .」 같은 덮어쓸 글자를 찾아요.<br>
        · 글자: 한 줄 값 · 긴 글: 주소처럼 줄 바꿈 · 덮어쓰기: 인쇄된 글자를 가리고 새로 씀 · 체크: □에 ✓ · 도장: 인감 그림</div></div>`}
      <div class="card"><div class="card-h" style="padding-bottom:12px"><h2>정한 칸 ${F.length}개</h2>${nSug ? `<button class="btn sm primary" id="edAll">제안 ${nSug}개 모두 확인</button>` : ''}</div>
        <div class="fm-flist">${F.map((f, i) => `<div class="fm-fr ${E.sel === i ? 'on' : ''}" data-sel="${i}"><span class="n">${i + 1}</span>
          <span style="flex:1;min-width:0">${f.item ? esc((IT[f.item] || {n: f.item}).n) : '<span style="color:var(--bad)">항목 고르기</span>'}${f.type === 'check' && f.opt ? ` <span class="faint">= ${esc(f.opt)}</span>` : ''}${E.form.pages.length > 1 ? ` <span class="faint">${(f.p || 0) + 1}쪽</span>` : ''}</span>
          ${f.sug ? '<span class="chip now">제안</span>' : ''}<span class="chip wait">${FM_TYPES[f.type]}</span></div>`).join('') || '<div class="card-b small faint">아직 없어요.</div>'}</div></div>
      <div class="row-gap"><button class="btn" id="edCancel" style="flex:1;justify-content:center">취소</button><button class="btn primary" id="edSave" style="flex:2;justify-content:center">양식 저장</button></div>
    </div></div>`;
  fmEditBind(IT);
}
function fmFieldCard(f, i, IT) {
  const isCk = f.type === 'check', isSeal = f.type === 'seal';
  const list = ED.items.filter(it => isSeal ? it.image : isCk ? it.opts : !it.opts && !it.image);
  const groups = [...new Set(list.map(it => it.g))];
  const same = f.item && !isCk ? ED.fields.map((g, j) => [g, j]).filter(([g, j]) => j !== i && g.item === f.item).map(([, j]) => j + 1) : [];
  const it = IT[f.item] || {};
  return `<div class="card"><div class="card-h" style="padding-bottom:12px"><h2>${i + 1}번 칸</h2>
    ${f.sug ? `<span class="row-gap"><button class="btn sm" data-drop="${i}">버리기</button><button class="btn sm primary" data-okf="${i}">맞아요</button></span>` : `<button class="btn sm danger" data-drop="${i}">칸 지우기</button>`}</div>
    <div class="card-b" style="padding-top:0">
      ${f.sug ? `<div class="notice info" style="margin:0 0 10px">양식의 「<b>${esc(f.found)}</b>」${isCk ? ' 글자를 보고 체크 칸과 선택지를 짝지었어요.' : ' 옆이라 이 칸으로 제안했어요.'}</div>` : ''}
      <label class="lb">칸 종류</label><div class="seg fm-seg">${Object.entries(FM_TYPES).map(([k, n]) => `<button class="${f.type === k ? 'on' : ''}" data-ty="${k}">${n}</button>`).join('')}</div>
      <label class="lb" style="margin-top:10px">들어갈 항목</label>
      <select class="field" id="fItem"><option value="">— 고르기 —</option>${groups.map(g => `<optgroup label="${g}">${list.filter(x => x.g === g).map(x => `<option value="${x.k}" ${f.item === x.k ? 'selected' : ''}>${esc(x.n)}</option>`).join('')}</optgroup>`).join('')}</select>
      ${isCk && f.item ? `<label class="lb" style="margin-top:10px">이 값일 때 ✓</label><select class="field" id="fOpt">${(it.opts || []).map(o => `<option ${f.opt === o ? 'selected' : ''}>${o}</option>`).join('')}</select>` : ''}
      ${it.fmts ? `<label class="lb" style="margin-top:10px">쓰는 모양</label><select class="field" id="fFmt">${it.fmts.map(([k, n]) => `<option value="${k}" ${(f.fmt || it.fmts[0][0]) === k ? 'selected' : ''}>${n}</option>`).join('')}</select>
        <div class="small faint" style="margin-top:4px">원장 값은 그대로 두고, 이 양식에서 쓰는 모양만 바꿔요.</div>` : ''}
      ${f.type === 'over' ? `<label class="lb" style="margin-top:10px">가릴 원래 글자</label><input class="field" value="${esc(f.orig || '(양식에 인쇄된 글자)')}" readonly>
        <label class="lb" style="margin-top:10px">뒤에 붙일 글자</label><input class="field" id="fSuf" value="${esc(f.suffix || '')}" placeholder="예: 귀중">` : ''}
      ${!isCk && !isSeal ? `<div class="form" style="margin-top:10px"><div><label class="lb">가장 큰 글자 (pt)</label><input class="field" id="fSize" type="number" min="6" max="30" step="0.5" value="${esc(f.size || '')}" placeholder="자동"></div>
        <label class="small" style="display:flex;gap:6px;align-items:center;align-self:end;padding-bottom:10px"><input type="checkbox" class="cbx" id="fOptn" ${f.optional ? 'checked' : ''}>비어 있어도 됨</label></div>` : ''}
      ${same.length ? `<div class="notice info" style="margin:10px 0 0">같은 항목이 <b>${same.join(', ')}번 칸</b>에도 있어요. 같은 값이 들어가요.</div>` : ''}
      ${it.g === '고정값' ? '<div class="small faint" style="margin-top:8px">「우리 회사 정보」 값이 자동으로 들어가요.</div>' : ''}
      ${!isCk && !isSeal ? '<div style="text-align:right;margin-top:6px"><a class="small" data-go="fm_company">+ 회사 항목 새로 만들기</a></div>' : ''}
    </div></div>`;
}
function fmEditBind(IT) {
  const E = ED, F = E.fields;
  const redraw = (lay) => { if (lay) E.lay = null; fmEditDraw(); };
  $('#edFind').onclick = () => safe(async () => {
    const r = await api('fm_detect', {fid: E.id});
    const ov = (a, b) => { const x = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)), y = Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y)); return x * y / (Math.min(a.w * a.h, b.w * b.h) || 1); };
    const add = r.fields.filter(s => !F.some(f => (f.p || 0) === s.p && ov(f, s) > 0.4));
    F.push(...add);
    E.sel = -1; redraw(true);
    const ck = add.filter(f => f.type === 'check').length;
    toast(add.length ? `낱말 옆 칸 ${add.length - ck}곳, □ 체크 ${ck}곳을 더 찾았어요. 확인해 주세요.` : r.scanned ? '스캔한 PDF라 글자를 읽지 못했어요' : '더 찾을 칸이 없어요');
  });
  $$('[data-pg]').forEach(b => b.onclick = () => { E.page = +b.dataset.pg; E.sel = -1; redraw(); });
  $('#edPv').onchange = e => { E.preview = e.target.checked; redraw(true); };
  $('#edName').onchange = e => { E.name = e.target.value; };
  $('#edGrp').onchange = e => { E.grp = e.target.value; };
  $('#edFont').onchange = e => { E.font = e.target.value; redraw(true); };
  $$('[data-sel]').forEach(r => r.onclick = () => { E.sel = +r.dataset.sel; const f = F[E.sel]; if ((f.p || 0) !== E.page) E.page = f.p || 0; redraw(); });
  if ($('#edAll')) $('#edAll').onclick = () => { F.forEach(f => delete f.sug); E.sel = -1; redraw(true); toast('제안한 칸을 모두 확인했어요'); };
  $$('[data-okf]').forEach(b => b.onclick = () => { delete F[+b.dataset.okf].sug; E.sel = -1; redraw(true); });
  $$('[data-drop]').forEach(b => b.onclick = () => { F.splice(+b.dataset.drop, 1); E.sel = -1; redraw(true); });
  const f = F[E.sel];
  if (f) {
    $$('[data-ty]').forEach(b => b.onclick = () => {
      const t = b.dataset.ty; f.type = t;
      const it = IT[f.item] || {};
      if ((t === 'check') !== !!it.opts || (t === 'seal') !== !!it.image) { f.item = t === 'seal' ? 'seal' : ''; delete f.opt; }
      if (t === 'over' && !f.orig) f.orig = '(양식에 인쇄된 글자)';
      redraw(true);
    });
    $('#fItem').onchange = e => { f.item = e.target.value; const it = IT[f.item] || {}; if (f.type === 'check' && it.opts) f.opt = it.opts[0]; f.fmt = it.fmts ? it.fmts[0][0] : undefined; redraw(true); };
    if ($('#fOpt')) $('#fOpt').onchange = e => { f.opt = e.target.value; redraw(true); };
    if ($('#fFmt')) $('#fFmt').onchange = e => { f.fmt = e.target.value; redraw(true); };
    if ($('#fSuf')) $('#fSuf').onchange = e => { f.suffix = e.target.value; redraw(true); };
    if ($('#fSize')) $('#fSize').onchange = e => { f.size = +e.target.value || undefined; redraw(true); };
    if ($('#fOptn')) $('#fOptn').onchange = e => { f.optional = e.target.checked; redraw(true); };
  }
  $('#edCancel').onclick = () => safe(async () => {
    if (E.form.draft) { if (!await confirmBox('양식 넣기 취소', '아직 저장하지 않은 새 양식이에요. 넣은 PDF를 양식함에서 뺄까요?', '빼기')) return; await api('fm_delete', {fid: E.id}); }
    ED = null; go('fm');
  });
  $('#edDel').onclick = () => safe(async () => { if (!await confirmBox('양식 지우기', `「${esc(E.name)}」 양식과 정한 칸을 지워요. 이미 만든 서류 파일은 그대로 남아요.`, '지우기')) return; await api('fm_delete', {fid: E.id}); ED = null; toast('양식을 지웠어요'); go('fm'); });
  $('#edSave').onclick = () => safe(async () => {
    if (F.some(x => x.sug)) return toast('확인하지 않은 제안 칸이 있어요. 「맞아요」나 「버리기」를 눌러 주세요.', true);
    const none = F.findIndex(x => !x.item);
    if (none >= 0) { E.sel = none; E.page = F[none].p || 0; redraw(); return toast(`${none + 1}번 칸의 항목을 골라 주세요`, true); }
    const r = await api('fm_save', {fid: E.id, data: {fields: F, name: E.name, grp: E.grp, font: E.font}});
    Object.keys(FM_IMG).forEach(k => k.startsWith(E.id) && delete FM_IMG[k]);
    ED = null; toast(`저장했어요 — 칸 ${r.n}개. 이제 「서류 만들기」에서 바로 써요.`); go('fm');
  });
  // 마우스: 새 칸 그리기 · 옮기기 · 크기
  const pp = $('#edPaper');
  pp.onmousedown = e => {
    if (e.button) return;
    const r0 = pp.getBoundingClientRect(), sx = e.clientX - r0.left, sy = e.clientY - r0.top;
    const rs = e.target.closest('[data-rs]'), fd = e.target.closest('.fm-fd');
    let mode = rs ? 'rs' : fd ? 'mv' : 'new', i0 = rs ? +rs.dataset.rs : fd ? +fd.dataset.i : -1, tmp, moved = false;
    const f0 = i0 >= 0 ? Object.assign({}, F[i0]) : null;
    if (mode === 'new') { tmp = document.createElement('div'); tmp.className = 'fm-drawing'; pp.appendChild(tmp); }
    else if (E.sel !== i0) { E.sel = i0; $$('.fm-fd', pp).forEach(x => x.classList.toggle('sel', +x.dataset.i === i0)); }
    e.preventDefault();
    const mv = ev => {
      const r = pp.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top;
      if (Math.abs(x - sx) + Math.abs(y - sy) > 2) moved = true;
      if (mode === 'new') { Object.assign(tmp.style, {left: Math.min(x, sx) + 'px', top: Math.min(y, sy) + 'px', width: Math.abs(x - sx) + 'px', height: Math.abs(y - sy) + 'px'}); return; }
      const g = F[i0], el = pp.querySelector(`.fm-fd[data-i="${i0}"]`);
      if (mode === 'mv') { g.x = Math.round((f0.x + x - sx) * 2) / 2; g.y = Math.round((f0.y + y - sy) * 2) / 2; }
      else { g.w = Math.max(8, Math.round(f0.w + x - sx)); g.h = Math.max(8, Math.round(f0.h + y - sy)); }
      Object.assign(el.style, {left: g.x + 'px', top: g.y + 'px', width: g.w + 'px', height: g.h + 'px'});
    };
    const up = ev => {
      document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up);
      if (mode === 'new') {
        const r = pp.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top, w = Math.abs(x - sx), h = Math.abs(y - sy);
        tmp.remove();
        if (w < 7 || h < 7) { if (E.sel >= 0) { E.sel = -1; redraw(); } return; }
        const small = w < 24 && h < 24;
        F.push({p: E.page, item: '', type: small ? 'check' : h > 30 ? 'long' : 'text', x: Math.round(Math.min(x, sx)), y: Math.round(Math.min(y, sy)), w: Math.round(w), h: Math.round(h)});
        E.sel = F.length - 1;
        redraw(true);
      } else redraw(moved);
    };
    document.addEventListener('mousemove', mv); document.addEventListener('mouseup', up);
  };
}
document.addEventListener('keydown', e => {
  if (CUR !== 'fm_edit' || !ED || ED.sel < 0 || /INPUT|SELECT|TEXTAREA/.test(e.target.tagName)) return;
  const f = ED.fields[ED.sel];
  if (e.key === 'Delete' || e.key === 'Backspace') { ED.fields.splice(ED.sel, 1); ED.sel = -1; ED.lay = null; fmEditDraw(); e.preventDefault(); }
  const step = e.shiftKey ? 5 : 0.5;
  const mvk = {ArrowLeft: ['x', -step], ArrowRight: ['x', step], ArrowUp: ['y', -step], ArrowDown: ['y', step]}[e.key];
  if (mvk && f) { f[mvk[0]] += mvk[1]; ED.lay = null; fmEditDraw(); e.preventDefault(); }
});

// ================================================================== 서류 만들기
let MK = null;
const mkVals = t => Object.assign({}, t.vals, MK.ov[t.tid] || {});
const mkItems = ts => ts.map(t => ({tid: t.tid, vals: mkVals(t), ref: t.ref}));
async function mkCheck(ts, full) {
  if (!ts.length) return;
  const r = await api('fm_check', {fid: MK.fid, items: mkItems(ts), full: !!full});
  Object.entries(r).forEach(([k, x]) => { MK.chk[k] = x; if (x.layout) MK.lay[k] = x.layout; });
}
SCREENS.fm_make = async (v, a) => {
  if (a.fid || a.src || a.reset || !MK) {
    const lst = await api('fm_list');
    let fid = a.fid || (a.reset ? '' : (MK && MK.fid)) || '';
    if (!fid && a.src === 'dlv') fid = (lst.tasks.find(t => t[0] === '송달불능') || [])[2] || '';
    if (fid && !lst.forms.some(f => f.id === fid)) fid = '';
    MK = {fid, forms: lst.forms, src: a.src || 'dlv', keys: a.keys || null, from: a.from || '', step: fid ? 2 : 1, targets: [], sel: new Set(), ov: {}, ok: new Set(),
      chk: {}, lay: {}, flt: 'issue', view: 'one', cur: null, out: 'each', dupKeep: new Set(), xl: a.path ? {path: a.path, mapping: a.mapping || null} : null, pre: null, opts: {log: true, dlv_done: true, seal: false}, loaded: false};
    if (fid) await mkLoad();
    if (MK.from === 'dlv' && MK.targets.length) { MK.step = 3; await mkCheck(mkTargets()); }
  }
  await mkDraw(v);
};
async function mkLoad() {
  const d = await api('fm_get', {fid: MK.fid});
  FM_CSS = d.css || FM_CSS;
  MK.form = d.form; MK.items = d.items;
  MK.IT = Object.fromEntries(d.items.map(i => [i.k, i]));
  if (MK.src === 'xl' && !MK.xl) { MK.targets = []; MK.loaded = true; return; }
  const r = await api('fm_targets', MK.src === 'xl' ? {fid: MK.fid, src: 'xl', path: MK.xl.path, mapping: MK.xl.mapping} : {fid: MK.fid, src: MK.src, keys: MK.keys});
  MK.targets = r.targets;
  if (r.excel) MK.xl = Object.assign(MK.xl || {}, r.excel);
  MK.sel = new Set(r.targets.filter(t => !t.block).map(t => t.tid));
  MK.chk = {}; MK.lay = {}; MK.ok = new Set(); MK.loaded = true;
}
const mkTargets = () => MK.targets.filter(t => MK.sel.has(t.tid) && !t.block);
const mkStatus = t => (MK.chk[t.tid] || {}).status || 'ok';
function mkSteps() {
  const names = ['양식 고르기', '대상 고르기', '검수', '마지막 확인 · 저장'];
  return `<div class="fm-steps">${names.map((n, i) => {
    const skip = MK.from === 'dlv' && i < 2;
    const cls = MK.step === i + 1 ? 'on' : skip ? 'skip' : MK.step > i + 1 ? 'done' : '';
    return `<div class="${cls}" ${!skip && MK.step > i + 1 ? `data-step="${i + 1}"` : ''}><i>${MK.step > i + 1 || skip ? '✓' : i + 1}</i>${skip ? (i ? '송달에서 고름' : '기본 양식') : n}</div>`;
  }).join('')}</div>`;
}
async function mkDraw(v) {
  v = v || $('#view');
  const title = MK.form ? esc(MK.form.name) : '서류 만들기';
  let body = '';
  if (MK.step === 1) body = mk1();
  else if (MK.step === 2) body = mk2();
  else if (MK.step === 3) body = await mk3();
  else body = mk4();
  v.innerHTML = head(`${esc(INFO.book)} · 서류 작성`, title, fmTabs('fm_make')) + mkSteps() +
    (MK.from === 'dlv' && MK.step === 3 ? `<div class="fm-from">↩ 송달 화면에서 바로 왔어요 · 송달불능 → 기본 양식 「${title}」 · ${mkTargets().length}명<span style="flex:1"></span><button class="btn sm" data-go="lg_dlv">송달로 돌아가기</button></div>` : '') + body;
  $$('[data-step]', v).forEach(b => b.onclick = () => { MK.step = +b.dataset.step; mkDraw(); });
  [null, mk1Bind, mk2Bind, mk3Bind, mk4Bind][MK.step](v);
}
function mk1() {
  if (!MK.forms.length) return empty('등록한 양식이 없어요', '양식함에서 회사 양식 PDF를 먼저 넣어 주세요.', '<button class="btn primary" data-go="fm">양식함으로</button>');
  return `<div class="fm-pick">${MK.forms.map(f => `<div class="fm-pk ${MK.fid === f.id ? 'on' : ''}" data-pk="${f.id}"><div class="fm-thumb"></div>
    <div><b>${f.fav ? '★ ' : ''}${esc(f.name)}</b><div class="small faint">${esc(f.grp)} · 칸 ${f.n}개${f.tasks.length ? ' · ' + f.tasks.map(esc).join(', ') + ' 기본' : ''}</div></div></div>`).join('')}</div>
    <div style="display:flex;justify-content:flex-end;margin-top:14px"><button class="btn primary" id="mk1n" ${MK.fid ? '' : 'disabled'}>다음 — 대상 고르기</button></div>`;
}
function mk1Bind(v) {
  $$('[data-pk]', v).forEach(c => c.onclick = () => { MK.fid = c.dataset.pk; mkDraw(); });
  if ($('#mk1n')) $('#mk1n').onclick = () => safe(async () => { await mkLoad(); MK.step = 2; mkDraw(); });
}
function mk2() {
  const srcs = [['dlv', '송달 결과', '처리할 송달불능 건'], ['ledger', '채무자 원장', '원장의 채무자 전체'], ['xl', '엑셀 넣기', '열 이름을 자동으로 짝지어요']];
  const L = MK.targets, sel = mkTargets(), can = L.filter(t => !t.block);
  const notes = sel.flatMap(t => t.notes.map(n => [t, n]));
  const v = t => mkVals(t);
  const skipK = ['company', 'company_addr', 'ceo', 'phone', 'agent', 'date', 'seal', 'debtor', 'creditor', 'case_name'];
  const cols = [...new Set(MK.form.fields.map(f => f.item))].filter(k => !skipK.includes(k)).slice(0, 5).map(k => [k, (MK.IT[k] || {n: k}).n]);
  return `<div class="card" style="overflow:hidden">
    <div class="card-h" style="padding-bottom:14px"><div class="fm-src">${srcs.map(([k, n, d]) => `<button class="${MK.src === k ? 'on' : ''}" data-src="${k}">${n}<small>${d}</small></button>`).join('')}</div>
      <button class="btn sm" data-go="fm_make" data-arg='{"reset":1}'>양식 바꾸기</button></div>
    ${MK.src === 'xl' ? `<div class="card-b fm-xl">${MK.xl ? `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><b>${esc(MK.xl.name)} · ${MK.xl.rows}줄</b>
        <span><span class="chip ok">열 ${MK.xl.header.length}개 중 ${Object.keys(MK.xl.auto).length}개 자동으로 짝지음</span> <button class="btn sm" id="xlPick">다른 엑셀</button></span></div>
      <div class="fm-map">${MK.xl.header.map((h, j) => { const k = Object.keys(MK.xl.mapping).find(x => +MK.xl.mapping[x] === j) || '';
        return `<div><b title="${esc(h)}">${esc(h || excelCol(j))}</b>→<select class="field" data-map="${j}"><option value="">안 씀</option>${MK.items.filter(i => !i.image && i.k !== 'date').map(i => `<option value="${i.k}" ${i.k === k ? 'selected' : ''}>${esc(i.n)}</option>`).join('')}</select>${k && MK.xl.auto[k] === j ? '<span class="chip ok">자동</span>' : ''}</div>`; }).join('')}</div>`
      : `<button class="btn primary" id="xlPick">엑셀 파일 고르기</button> <span class="small muted">채무자 이름·사건번호·법원·새 주소 같은 열이 있으면 자동으로 짝지어요. 원장에 있는 채무자면 빠진 값을 원장에서 채워요.</span>`}</div>` : ''}
    ${notes.length ? `<div class="card-b fm-notes"><div style="display:flex;justify-content:space-between;margin-bottom:8px"><b class="small">자동으로 정리하고 채운 값 ${notes.length}곳</b><span class="small faint">검수 화면에도 표시돼요</span></div>
      ${notes.slice(0, 8).map(([t, n]) => `<div><span class="chip ${n.filled ? 'now' : 'wait'}">${n.filled ? '원장에서 채움' : '값 정리'}</span><b>${esc(t.name)}</b><span class="muted">${esc(n.m)}</span></div>`).join('')}${notes.length > 8 ? `<div class="faint">… ${notes.length - 8}곳 더</div>` : ''}</div>` : ''}
    ${L.length ? `<div style="max-height:480px;overflow:auto"><table class="tbl lg-tbl"><thead><tr><th style="width:36px"><input type="checkbox" class="cbx" id="mkAll" ${sel.length && sel.length === can.length ? 'checked' : ''}></th><th>채무자</th>${cols.map(c => `<th>${c[1]}</th>`).join('')}<th>관리 가부</th><th>최근 작성</th></tr></thead><tbody>
      ${L.map(t => `<tr class="${t.block ? 'off' : ''}"><td><input type="checkbox" class="cbx" data-ck="${esc(t.tid)}" ${t.block ? 'disabled' : ''} ${MK.sel.has(t.tid) && !t.block ? 'checked' : ''}></td>
        <td><b>${esc(t.name || '(이름 없음)')}</b>${t.did ? '' : ' <span class="chip wait" title="원장에 없는 사람">원장 없음</span>'}</td>
        ${cols.map(([k]) => { const x = v(t)[k]; return `<td class="small ${k === 'new_addr' || k === 'debtor_addr' ? 'fm-ell' : ''}">${x ? esc(k === 'amount' ? won(x) : x) : '<span class="faint">—</span>'}</td>`; }).join('')}
        <td>${t.block ? `<span class="chip bad">${esc(t.block.label)}</span>` : '<span class="chip ok">가능</span>'}</td>
        <td>${t.dup ? `<span class="chip warn">${esc(t.dup)} 같은 서류</span>` : '<span class="faint">—</span>'}</td></tr>`).join('')}</tbody></table></div>`
      : MK.src === 'xl' && !MK.xl ? '' : empty('대상이 없어요', MK.src === 'dlv' ? '「송달·주소보정」에 처리할 송달불능 건이 없어요.' : '원장에 채무자가 없어요.')}
    <div class="lg-foot"><span class="small muted">회생·파산으로 정지·금지·불가인 채무자는 고를 수 없어요.</span><span style="flex:1"></span><b>${sel.length}명 고름</b>
      <button class="btn primary" id="mk2n" ${sel.length ? '' : 'disabled'}>다음 — 검수</button></div></div>`;
}
function mk2Bind(v) {
  $$('[data-src]', v).forEach(b => b.onclick = () => safe(async () => { MK.src = b.dataset.src; MK.from = ''; MK.keys = null; MK.xl = MK.src === 'xl' ? MK.xl : null; MK.ov = {}; await mkLoad(); mkDraw(); }));
  if ($('#xlPick')) $('#xlPick').onclick = () => safe(async () => { const p = await chooseExcel(); if (!p) return; MK.xl = {path: p, mapping: null}; await mkLoad(); mkDraw(); });
  $$('[data-map]', v).forEach(s => s.onchange = () => safe(async () => {
    const j = +s.dataset.map, m = Object.assign({}, MK.xl.mapping);
    Object.keys(m).forEach(k => { if (+m[k] === j) delete m[k]; });
    if (s.value) m[s.value] = j;
    MK.xl.mapping = m; await mkLoad(); mkDraw();
  }));
  $$('[data-ck]', v).forEach(c => c.onclick = () => { c.checked ? MK.sel.add(c.dataset.ck) : MK.sel.delete(c.dataset.ck); mkDraw(); });
  if ($('#mkAll')) $('#mkAll').onclick = e => { MK.targets.forEach(t => { if (!t.block) e.target.checked ? MK.sel.add(t.tid) : MK.sel.delete(t.tid); }); mkDraw(); };
  $('#mk2n').onclick = () => safe(async () => { await mkCheck(mkTargets()); MK.step = 3; MK.cur = null; mkDraw(); });
}
function mkList() { const T = mkTargets(); return MK.flt === 'issue' ? T.filter(t => mkStatus(t) !== 'ok') : T; }
async function mk3() {
  const T = mkTargets(), L = mkList();
  const nBad = T.filter(t => mkStatus(t) === 'bad').length, nWarn = T.filter(t => mkStatus(t) === 'warn').length;
  const okWait = T.filter(t => mkStatus(t) === 'ok' && !MK.ok.has(t.tid)).length, done = T.filter(t => MK.ok.has(t.tid)).length;
  if (!L.some(t => t.tid === MK.cur)) MK.cur = L.length ? L[0].tid : null;
  const bar = `<div class="fm-sum"><div class="seg"><button class="${MK.flt === 'issue' ? 'on' : ''}" data-flt="issue">고칠 것만 <b>${nBad + nWarn}</b></button><button class="${MK.flt === 'all' ? 'on' : ''}" data-flt="all">전체 <b>${T.length}</b></button></div>
    <span class="chip bad">빈 칸 ${nBad}</span><span class="chip warn">확인 ${nWarn}</span><span class="chip ok">정상 ${T.length - nBad - nWarn}</span>
    <div class="seg">${[['one', '한 장씩'], ['table', '표로 고치기'], ['grid', '훑어보기']].map(([k, n]) => `<button class="${MK.view === k ? 'on' : ''}" data-view="${k}">${n}</button>`).join('')}</div>
    <span style="flex:1"></span><span class="small muted">검수 ${done}/${T.length}</span><div class="fm-prog"><i style="width:${T.length ? done / T.length * 100 : 0}%"></i></div>
    <button class="btn sm ${okWait ? 'primary' : ''}" id="okAll" ${okWait ? '' : 'disabled'}>정상 ${okWait}건 한꺼번에 검수 끝</button><button class="btn sm" id="toOut">마지막 확인 ›</button></div>`;
  if (MK.view === 'table') return bar + mkTable(T);
  const pg = MK.form.pages[0];
  if (MK.view === 'grid') {
    const G = MK.flt === 'issue' ? L : T;
    const need = G.filter(t => !MK.lay[t.tid]);
    if (need.length) await mkCheck(need, true);
    const img = await fmImg(MK.fid, 0, MK.form.ver);
    return bar + `<div class="fm-thumbs">${G.map(t => `<div class="fm-th ${mkStatus(t)}" data-th="${esc(t.tid)}">${fmPaper(pg, img, fmVals(MK.form, MK.lay[t.tid], 0), 'hl')}
      <div class="cap"><b>${MK.ok.has(t.tid) ? '✓ ' : ''}${esc(t.name)}</b>${FMST[mkStatus(t)]}</div></div>`).join('') || '<div class="small faint">고칠 것이 없어요.</div>'}</div>`;
  }
  if (!L.length) return bar + `<div class="card"><div class="card-b" style="text-align:center;padding:44px"><div style="font-size:30px">✓</div><b style="font-size:16px">고칠 것이 없어요</b>
    <div class="small muted" style="margin-top:6px">${okWait ? `정상 ${okWait}건은 「한꺼번에 검수 끝」을 누르거나 「훑어보기」로 빠르게 넘겨 보세요.` : '모두 검수했어요. 「마지막 확인」으로 넘어가세요.'}</div></div></div>`;
  const t = T.find(x => x.tid === MK.cur);
  if (!MK.lay[t.tid]) await mkCheck([t], true);
  MK.page = Math.min(MK.page || 0, MK.form.pages.length - 1);
  const img = await fmImg(MK.fid, MK.page, MK.form.ver);
  const vals = mkVals(t), ch = MK.chk[t.tid] || {issues: []};
  const used = [...new Set(MK.form.fields.map(f => f.item))];
  const bad = new Set(ch.issues.map(x => x.k)), noted = new Set(t.notes.map(n => n.k));
  const fixedK = new Set(['company', 'company_addr', 'ceo', 'phone', 'agent', 'date', 'seal']);
  const edit = used.filter(k => !fixedK.has(k)).sort((a, b) => bad.has(b) - bad.has(a)), fixed = used.filter(k => fixedK.has(k) && k !== 'seal');
  const inp = k => {
    const it = MK.IT[k] || {n: k}, x = vals[k];
    if (it.opts) return `<div class="fm-vr"><label>${esc(it.n)}</label><select class="field" data-k="${k}"><option value="">— 없음 —</option>${it.opts.map(o => `<option ${x === o ? 'selected' : ''}>${o}</option>`).join('')}</select></div>`;
    const is = ch.issues.find(y => y.k === k);
    return `<div class="fm-vr"><label>${esc(it.n)}${noted.has(k) ? '<span style="color:var(--accent)">자동으로 정리함</span>' : fixedK.has(k) ? '<span class="faint">우리 회사 정보</span>' : ''}</label>
      <input class="field ${is ? is.t : ''}" data-k="${k}" value="${esc(x == null ? '' : x)}" ${fixedK.has(k) ? 'readonly' : ''}></div>`;
  };
  return bar + `<div class="fm-rv">
    <div class="card fm-pl">${L.map(x => `<div class="pi ${x.tid === MK.cur ? 'on' : ''}" data-pi="${esc(x.tid)}"><span class="ck ${MK.ok.has(x.tid) ? 'y' : ''}">${MK.ok.has(x.tid) ? '✓' : ''}</span>
      <span style="flex:1;min-width:0"><b>${esc(x.name)}</b><br><span class="small faint">${esc((mkVals(x).court || '법원 없음').replace('지방법원', '지법'))}</span></span>${FMST[mkStatus(x)]}</div>`).join('')}</div>
    <div class="fm-rvp">${MK.form.pages.length > 1 ? `<div class="seg" style="margin-bottom:8px">${MK.form.pages.map((_, i) => `<button class="${MK.page === i ? 'on' : ''}" data-rpg="${i}">${i + 1}쪽</button>`).join('')}</div>` : ''}
      ${fmPaper(MK.form.pages[MK.page], img, fmVals(MK.form, MK.lay[t.tid], MK.page), 'hl', 'rvPaper')}
      <div class="small faint" style="margin-top:8px;text-align:center">파란 바탕 = 채운 값 (저장할 땐 안 보여요) · 값을 누르면 오른쪽 입력칸으로 · <b>Enter</b> 검수 끝 → 다음 · ↑↓ 이동</div></div>
    <div class="fm-side">
      <div class="card"><div class="card-h" style="padding-bottom:12px"><h2>${esc(t.name)} · ${esc(vals.case_no || '사건번호 없음')}</h2>${FMST[mkStatus(t)]}</div>
        <div class="card-b" style="padding-top:0">
          ${ch.issues.map(x => `<div class="fm-iss ${x.t}">${x.t === 'bad' ? '●' : '▲'} <span>${esc(x.m)}</span>${x.fix ? `<button class="btn sm" data-fix="${esc(x.k)}" data-fv="${esc(x.fix.v)}">${esc(x.fix.label)}</button>` : ''}</div>`).join('')}
          ${t.notes.map(n => `<div class="fm-iss info">ⓘ <span>${esc(n.m)}</span></div>`).join('')}
          ${t.dup ? `<div class="fm-iss warn">▲ <span>${esc(t.dup)}에 같은 서류를 만들었어요.</span></div>` : ''}
          ${!ch.issues.length ? '<div class="fm-iss ok">✓ 빈 칸이나 넘치는 글자가 없어요.</div>' : ''}
          <div style="margin-top:10px">${edit.map(inp).join('')}</div>
          ${fixed.length ? `<details class="fm-fix"><summary>고정값 ${fixed.length}개 — 우리 회사 정보 · 오늘 날짜</summary><div style="margin-top:8px">${fixed.map(inp).join('')}</div></details>` : ''}
          <div class="small faint" style="margin-top:8px">여기서 고친 값은 이 서류에만 써요.</div>
        </div></div>
      <button class="btn primary" id="okOne" style="justify-content:center">${MK.ok.has(t.tid) ? '검수 끝 ✓ · 다음' : mkStatus(t) === 'warn' ? '확인함 · 다음 ⏎' : '검수 끝 · 다음 ⏎'}</button>
    </div></div>`;
}
function mkTable(T) {
  const ord = {bad: 0, warn: 1, ok: 2};
  const rows = [...T].sort((a, b) => ord[mkStatus(a)] - ord[mkStatus(b)]);
  const used = [...new Set(MK.form.fields.map(f => f.item))].filter(k => !['company', 'company_addr', 'ceo', 'phone', 'agent', 'date', 'seal'].includes(k));
  return `<div class="card" style="overflow:hidden"><div class="card-h" style="padding-bottom:12px"><h2>표로 고치기</h2><span class="small muted">문제 있는 줄이 위로 와요 · 고친 칸은 파랗게</span></div>
    <div style="max-height:560px;overflow:auto"><table class="tbl fm-tbl"><thead><tr><th>상태</th><th>검수</th>${used.map(k => `<th>${esc((MK.IT[k] || {n: k}).n)}</th>`).join('')}</tr></thead><tbody>
    ${rows.map(t => { const v = mkVals(t), o = MK.ov[t.tid] || {}; return `<tr class="${mkStatus(t)}"><td>${FMST[mkStatus(t)]}</td><td style="text-align:center">${MK.ok.has(t.tid) ? '✓' : ''}</td>
      ${used.map(k => { const it = MK.IT[k] || {}; return it.opts ? `<td><select class="field" data-tk="${k}" data-tt="${esc(t.tid)}"><option value="">—</option>${it.opts.map(x => `<option ${v[k] === x ? 'selected' : ''}>${x}</option>`).join('')}</select></td>`
        : `<td><input class="field ${k in o ? 'chg' : ''}" data-tk="${k}" data-tt="${esc(t.tid)}" value="${esc(v[k] == null ? '' : v[k])}"></td>`; }).join('')}</tr>`; }).join('')}</tbody></table></div></div>`;
}
async function mkSet(tid, k, val) {
  (MK.ov[tid] = MK.ov[tid] || {})[k] = val;
  MK.ok.delete(tid);
  delete MK.lay[tid];
  await mkCheck([MK.targets.find(t => t.tid === tid)], MK.view !== 'table');
  mkDraw();
}
function mkOkOne() {
  const L = mkList(), t = mkTargets().find(x => x.tid === MK.cur);
  if (!t) return;
  if (mkStatus(t) === 'bad') return toast('빈 칸이 남아 있어요. 값을 채운 뒤 눌러 주세요.', true);
  MK.ok.add(t.tid);
  const i = L.findIndex(x => x.tid === t.tid), next = L.slice(i + 1).concat(L.slice(0, i)).find(x => !MK.ok.has(x.tid));
  if (next) MK.cur = next.tid;
  mkDraw();
  if (!next) toast('이 목록은 모두 검수했어요.');
}
function mk3Bind(v) {
  $$('[data-flt]', v).forEach(b => b.onclick = () => { MK.flt = b.dataset.flt; mkDraw(); });
  $$('[data-view]', v).forEach(b => b.onclick = () => { MK.view = b.dataset.view; mkDraw(); });
  $$('[data-rpg]', v).forEach(b => b.onclick = () => { MK.page = +b.dataset.rpg; mkDraw(); });
  $('#okAll').onclick = () => { const T = mkTargets().filter(t => mkStatus(t) === 'ok' && !MK.ok.has(t.tid)); T.forEach(t => MK.ok.add(t.tid)); toast(`정상 ${T.length}건을 검수 끝으로 했어요. 고칠 것만 남았어요.`); mkDraw(); };
  $('#toOut').onclick = () => safe(async () => {
    const T = mkTargets(), left = T.filter(t => !MK.ok.has(t.tid));
    if (!T.some(t => MK.ok.has(t.tid))) return toast('검수 끝으로 한 서류가 없어요', true);
    if (left.length && !await confirmBox('검수하지 않은 서류', `아직 검수하지 않은 서류가 ${left.length}건 있어요. 검수한 ${T.length - left.length}건만 저장할까요?`, '검수한 것만')) return;
    const ok = T.filter(t => MK.ok.has(t.tid));
    MK.pre = await api('fm_precheck', {fid: MK.fid, items: ok.map(t => ({tid: t.tid, did: t.did, name: t.name, vals: mkVals(t)}))});
    MK.dupKeep = new Set();
    MK.step = 4; mkDraw();
  });
  $$('[data-pi]', v).forEach(r => r.onclick = () => { MK.cur = r.dataset.pi; mkDraw(); });
  $$('[data-th]', v).forEach(r => r.onclick = () => { MK.view = 'one'; MK.flt = 'all'; MK.cur = r.dataset.th; mkDraw(); });
  $$('.fm-side [data-k]', v).forEach(i => {
    i.onchange = () => safe(() => mkSet(MK.cur, i.dataset.k, i.value));
    i.onfocus = () => $$('#rvPaper .fm-val').forEach(e => e.classList.toggle('glow', e.dataset.k === i.dataset.k));
  });
  $$('[data-fix]', v).forEach(b => b.onclick = () => safe(() => mkSet(MK.cur, b.dataset.fix, b.dataset.fv)));
  $$('[data-tk]', v).forEach(i => i.onchange = () => safe(() => mkSet(i.dataset.tt, i.dataset.tk, i.value)));
  if ($('#okOne')) $('#okOne').onclick = mkOkOne;
  const pp = $('#rvPaper');
  if (pp) pp.onclick = e => { const x = e.target.closest('.fm-val[data-k]'); if (!x) return; const d = $('details.fm-fix'); const inp = $(`.fm-side [data-k="${x.dataset.k}"]`);
    if (inp && d && d.contains(inp)) d.open = true; if (inp) { inp.focus(); if (inp.select) inp.select(); } };
}
document.addEventListener('keydown', e => {
  if (CUR !== 'fm_make' || !MK || MK.step !== 3 || MK.view !== 'one' || /INPUT|SELECT|TEXTAREA/.test(e.target.tagName) || $('.modal-bg')) return;
  const L = mkList(), i = L.findIndex(x => x.tid === MK.cur);
  if (e.key === 'Enter') { mkOkOne(); e.preventDefault(); }
  if (e.key === 'ArrowDown' && i < L.length - 1) { MK.cur = L[i + 1].tid; mkDraw(); e.preventDefault(); }
  if (e.key === 'ArrowUp' && i > 0) { MK.cur = L[i - 1].tid; mkDraw(); e.preventDefault(); }
});
function mkFinal() {
  const late = new Set(MK.pre.late.map(x => x.tid)), dup = new Set(MK.pre.dups.map(x => x.tid));
  return mkTargets().filter(t => MK.ok.has(t.tid) && !late.has(t.tid) && (!dup.has(t.tid) || MK.dupKeep.has(t.tid)));
}
function mk4() {
  const P = MK.pre, F = mkFinal(), ok = mkTargets().filter(t => MK.ok.has(t.tid)), name = MK.form.name;
  const flows = F.filter(t => mkStatus(t) === 'warn');
  const hasSeal = MK.form.fields.some(f => f.type === 'seal');
  const ex = F[0] ? mkVals(F[0]) : {};
  const opts = [['each', '한 명당 PDF 하나', `파일 이름: ${name}_${ex.debtor || '이름'}_${ex.case_no || '사건번호'}.pdf`],
    ['one', '한 파일로 묶기', `${name}_묶음_${F.length}건.pdf — 인쇄해서 한꺼번에 낼 때`], ['print', '인쇄기로 바로 보내기', '고른 인쇄기로 실제 크기(100%)로 인쇄해요 · 묶은 PDF 파일도 남겨요']];
  const PR = MK.printers;
  const prBox = MK.out !== 'print' ? '' : !PR ? '<div class="small faint" style="margin:6px 0 4px 28px">인쇄기 목록을 읽는 중…</div>'
    : `<div class="fm-pr"><div><label class="lb">인쇄기</label><select class="field" id="mkPr">${PR.printers.length ? PR.printers.map(p => `<option value="${esc(p.name)}" ${p.name === (MK.printer || PR.pick) ? 'selected' : ''}>${esc(p.name)}${p.default ? ' (기본)' : ''}</option>`).join('') : '<option value="">(찾은 인쇄기가 없어요 — 기본 PDF 프로그램으로)</option>'}</select></div>
      <div><label class="lb">부수</label><input class="field" id="mkCp" type="number" min="1" max="20" value="${MK.copies || 1}"></div>
      <button class="btn sm" id="mkPrR" style="align-self:end">새로 읽기</button></div>
      <div class="small faint" style="margin:4px 0 0 28px">「Microsoft Print to PDF」를 고르면 PDF 파일로 저장돼요. 고른 인쇄기는 다음에도 기억해요.${PR.win ? '' : ' (이 PC는 Windows가 아니라 인쇄기로 바로 보내기는 회사 PC에서 돼요)'}</div>`;
  const ic = (c, s) => `<span class="ic ${c}">${s}</span>`;
  return `<div class="fm-out"><div style="display:flex;flex-direction:column;gap:14px">
    <div class="card fm-chk"><div class="card-h" style="padding-bottom:12px"><h2>저장 직전 다시 확인했어요</h2><span class="small faint">${esc(P.at)} 기준</span></div>
      <div class="row">${ic(P.late.length ? 'bad' : 'ok', P.late.length ? '!' : '✓')}<div><b>회생·파산 관리 가부</b><div class="d">${P.late.length ? P.late.map(x => `<b style="color:var(--bad)">${esc(x.name)}</b> — 지금 「${esc(x.label)}」예요. 자동으로 뺐어요.`).join('<br>') : '고른 사람 모두 회수·집행이 가능한 상태예요.'}</div></div></div>
      <div class="row">${ic(P.dups.length ? 'warn' : 'ok', P.dups.length ? '▲' : '✓')}<div style="flex:1"><b>같은 서류 중복 (30일)</b><div class="d">${P.dups.length ? P.dups.map(x => `<div style="display:flex;gap:8px;align-items:center;margin-top:4px"><span><b>${esc(x.name)}</b> — ${esc(x.date)}에 같은 「${esc(name)}」를 만들었어요.</span><span style="flex:1"></span>
          <button class="btn sm ${MK.dupKeep.has(x.tid) ? 'primary' : ''}" data-dk="${esc(x.tid)}">${MK.dupKeep.has(x.tid) ? '그래도 만들기 ✓' : '빼 둠 · 그래도 만들기'}</button></div>`).join('') : '최근 30일 안에 같은 서류를 만든 사람이 없어요.'}</div></div></div>
      <div class="row">${ic(flows.length ? 'warn' : 'ok', flows.length ? '▲' : '✓')}<div><b>빈 칸 · 넘침 · 대장과 다른 값</b><div class="d">빈 칸 0건${flows.length ? ` · 확인하고 넘긴 것 ${flows.length}건 (${flows.slice(0, 6).map(t => esc(t.name)).join(', ')})` : ''}</div></div></div></div>
    <div class="card"><div class="card-h" style="padding-bottom:12px"><h2>어떻게 저장할까요?</h2></div><div class="card-b" style="padding-top:0">
      ${opts.map(([k, n, d]) => `<div class="lg-opt ${MK.out === k ? 'on' : ''}" data-out="${k}"><span class="rd"></span><div><b>${n}</b><small>${esc(d)}</small></div></div>`).join('')}
      ${prBox}
      <div class="small muted" style="margin:10px 0 4px">저장 위치: 내보내기 폴더 › 법조치 서류 › 날짜 시간 ${esc(name)}</div>
      <label class="fm-cb"><input type="checkbox" class="cbx" data-op="log" ${MK.opts.log ? 'checked' : ''}>채무자 원장 기록에 「${esc(name)} 작성」 남기기</label>
      ${F.some(t => t.dlv) ? `<label class="fm-cb"><input type="checkbox" class="cbx" data-op="dlv_done" ${MK.opts.dlv_done ? 'checked' : ''}>송달·주소보정에서 이 건들을 「처리함」으로 바꾸기</label>` : ''}
      ${hasSeal ? `<label class="fm-cb"><input type="checkbox" class="cbx" data-op="seal" ${MK.opts.seal ? 'checked' : ''}>법인 인감 찍기 <span class="faint">— 누가 언제 찍었는지 서류 기록에 남아요</span></label>` : ''}
    </div></div></div>
    <div class="card" style="overflow:hidden"><div class="card-h" style="padding-bottom:12px"><h2>저장할 서류 ${F.length}건</h2><span class="small faint">검수 ${ok.length} · 뺌 ${ok.length - F.length}</span></div>
      <div style="max-height:460px;overflow:auto"><table class="tbl">${F.map(t => `<tr><td><b>${esc(t.name)}</b></td><td class="small muted">${esc(mkVals(t).case_no || '')}</td><td>${mkStatus(t) === 'ok' ? FMST.ok : '<span class="chip warn">확인함</span>'}</td></tr>`).join('')}</table></div>
      <div class="card-b"><button class="btn primary" id="mkGo" style="width:100%;justify-content:center" ${F.length ? '' : 'disabled'}>${MK.out === 'print' ? `${F.length}건 인쇄하기` : `${F.length}건 PDF 저장하기`}</button></div></div></div>`;
}
function mk4Bind(v) {
  $$('[data-dk]', v).forEach(b => b.onclick = () => { const k = b.dataset.dk; MK.dupKeep.has(k) ? MK.dupKeep.delete(k) : MK.dupKeep.add(k); mkDraw(); });
  $$('[data-out]', v).forEach(b => b.onclick = () => safe(async () => { MK.out = b.dataset.out; if (MK.out === 'print' && !MK.printers) { mkDraw(); MK.printers = await api('fm_printers'); } mkDraw(); }));
  if ($('#mkPr')) $('#mkPr').onchange = e => { MK.printer = e.target.value; };
  if ($('#mkCp')) $('#mkCp').onchange = e => { MK.copies = Math.max(1, +e.target.value || 1); };
  if ($('#mkPrR')) $('#mkPrR').onclick = () => safe(async () => { MK.printers = await api('fm_printers'); mkDraw(); });
  $$('[data-op]', v).forEach(c => c.onchange = () => safe(async () => {
    if (c.dataset.op === 'seal' && c.checked && !await confirmBox('법인 인감 찍기', '이번에 저장하는 서류에 법인 인감 그림을 찍어요. 찍은 사람과 시간이 서류 기록에 남아요. 찍을까요?', '찍기')) { c.checked = false; return; }
    MK.opts[c.dataset.op] = c.checked; mkDraw();
  }));
  $('#mkGo').onclick = () => safe(async () => {
    const F = mkFinal();
    const pr = MK.out === 'print' ? (($('#mkPr') || {}).value || '') : '';
    const r = await api('fm_make', {fid: MK.fid, items: F.map(t => ({tid: t.tid, did: t.did, dlv: t.dlv, name: t.name, vals: mkVals(t)})), mode: MK.out,
      opts: Object.assign({}, MK.opts, {printer: pr, copies: MK.copies || 1})});
    toast(`${r.count}건을 ${r.sim ? '만들었어요 (시뮬레이션이라 PDF 대신 값 목록을 내려받아요)' : r.printed ? `「${r.printed}」로 인쇄를 보냈어요` : 'PDF로 저장했어요'}${r.skipped.length ? ` · 회생·파산으로 ${r.skipped.length}건 뺌` : ''} — ${r.folder.split(/[\\/]/).pop()}`);
    const back = MK.from === 'dlv';
    MK = null;
    go(back ? 'lg_dlv' : 'fm');
  });
}
// 송달 화면에서 바로: 「송달불능」 기본 양식으로 검수부터
async function fmFromDlv(keys) {
  const lst = await api('fm_list');
  const fid = (lst.tasks.find(t => t[0] === '송달불능') || [])[2] || (lst.forms.find(f => f.grp === '송달') || {}).id;
  if (!fid) { toast('양식함에 회사 양식을 먼저 넣어 주세요', true); return go('fm'); }
  go('fm_make', {fid, src: 'dlv', keys, from: 'dlv'});
}

// ================================================================== 우리 회사 정보
SCREENS.fm_company = async v => {
  const d = await api('fm_company');
  const cr = d.creditor || {}, info = d.info || {};
  const f = (id, t, val, ph = '') => `<div><label class="lb">${t}</label><input class="field" id="${id}" value="${esc(val || '')}" placeholder="${esc(ph)}"></div>`;
  v.innerHTML = head(`${esc(INFO.book)} · 모든 양식에 자동으로 들어가는 값`, '우리 회사 정보', fmTabs('fm_company')) + `<div class="fm-co">
    <div style="display:flex;flex-direction:column;gap:14px">
      <div class="card"><div class="card-h"><h2>고정값 — 한 번만 넣기</h2><span class="chip wait">모든 채권·양식 공통</span></div><div class="card-b"><div class="form">
        ${f('cName', '우리 회사명 (원고·신청인·채권자)', cr.name)}${f('cRep', '대표자', cr.rep, '예: 대표이사 ○○○')}<div class="full">${f('cAddr', '우리 회사 주소', cr.addr)}</div>
        ${f('cPhone', '회사 전화', cr.phone)}${f('cAgent', '담당자·연락처', d.agent, '예: 담당 ○○○ (02-000-0000)')}${f('cCourt', '기본 관할 법원', d.court)}
        <div><label class="lb">채울 글꼴 (새 양식)</label><select class="field" id="cFont"><option value="myeongjo" ${d.font === 'myeongjo' ? 'selected' : ''}>바탕 (명조)</option><option value="gothic" ${d.font === 'gothic' ? 'selected' : ''}>맑은 고딕</option></select></div></div>
        <div class="row-gap mt16"><button class="btn primary" id="cSave">저장</button></div></div></div>
      <div class="card"><div class="card-h"><h2>법인 인감 그림</h2>${d.seal ? '<span class="chip ok">넣어 둠</span>' : '<span class="chip wait">없음</span>'}</div><div class="card-b">
        <div class="small muted" style="line-height:1.6">양식에 「도장」 칸을 만들면 저장할 때마다 찍을지 물어요. 찍은 사람과 시간이 서류 기록에 남아요. 그림은 이 PC의 자료 폴더에만 보관돼요.</div>
        <div class="row-gap mt16"><button class="btn" id="sealSet">${d.seal ? '그림 바꾸기' : '그림 넣기'}</button>${d.seal ? '<button class="btn danger" id="sealDel">지우기</button>' : ''}</div></div></div>
    </div>
    <div style="display:flex;flex-direction:column;gap:14px">
      <div class="card"><div class="card-h"><h2>이 채권의 값</h2><span class="chip now">${esc(INFO.book)}</span></div><div class="card-b"><div class="form">
        ${f('iAssignor', '채권자 (원채권사·양도인)', info.assignor)}${f('iCause', '사건명·청구 원인 (기본)', info.cause, '예: 양수금')}</div>
        <div class="small faint" style="margin-top:8px">채권을 바꾸면 그 채권의 값이 들어가요. 사건 조회 결과에 사건명이 있으면 그 값을 먼저 써요.</div>
        <div class="row-gap mt16"><button class="btn primary" id="iSave">저장</button></div></div></div>
      <div class="card"><div class="card-h"><h2>업무별 기본 양식</h2><span class="small faint">그 화면에서 바로 만들 때 쓰는 양식</span></div><div class="card-b">
        ${d.tasks.map(([t, s, fid]) => `<div class="fm-task"><div><b>${esc(t)}</b><div class="small faint">${esc(s)}</div></div><select class="field" data-task="${esc(t)}"><option value="">— 정하지 않음 —</option>${d.forms.map(x => `<option value="${x.id}" ${fid === x.id ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select></div>`).join('')}</div></div>
      <div class="card"><div class="card-h"><h2>회사에서 더한 항목</h2><button class="btn sm" id="itAdd">+ 항목 만들기</button></div><div class="card-b">
        ${d.items.length ? `<table class="tbl"><thead><tr><th>항목</th><th>값 (비우면 엑셀의 같은 이름 열에서)</th><th></th></tr></thead><tbody>${d.items.map(i => `<tr><td><b>${esc(i.n)}</b></td><td><input class="field" data-iv="${i.k}" value="${esc(i.value || '')}" placeholder="엑셀에서"></td><td><button class="btn sm ghost" data-idel="${i.k}">지우기</button></td></tr>`).join('')}</tbody></table>`
          : '<div class="small faint">예: 「담당 부서」(고정값), 「관리번호」(엑셀 열). 만든 항목은 칸 정하기에서 고를 수 있어요.</div>'}</div></div>
    </div></div>`;
  $('#cSave').onclick = () => safe(async () => {
    await setSetting('legal.creditor', {name: $('#cName').value.trim(), rep: $('#cRep').value.trim(), addr: $('#cAddr').value.trim(), phone: $('#cPhone').value.trim()}, '우리 회사 정보');
    await setSetting('legal.agent', $('#cAgent').value.trim(), '담당자·연락처');
    await setSetting('legal.court', $('#cCourt').value.trim());
    await setSetting('legal.form_font', $('#cFont').value);
    toast('저장했어요. 모든 양식에 바로 반영돼요.');
  });
  $('#iSave').onclick = () => safe(async () => { await api('lg_info_save', {info: Object.assign({}, info, {assignor: $('#iAssignor').value.trim(), cause: $('#iCause').value.trim()})}); toast('이 채권의 값을 저장했어요'); });
  $('#sealSet').onclick = () => safe(async () => {
    let p = null;
    if (MODE === 'browser') p = await modal('그림 위치', '<label class="lb">인감 그림 파일(PNG·JPG)의 전체 경로</label><input class="field" id="fp">', [{text: '취소'}, {text: '넣기', cls: 'primary', value: bg => $('#fp', bg).value.trim() || false}]);
    if (await api('fm_seal_set', p ? {path: p} : {})) { toast('인감 그림을 넣었어요'); go('fm_company'); }
  });
  if ($('#sealDel')) $('#sealDel').onclick = () => safe(async () => { if (await confirmBox('인감 그림 지우기', '보관한 인감 그림을 지울까요?', '지우기')) { await api('fm_seal_set', {remove: true}); go('fm_company'); } });
  $$('[data-task]', v).forEach(s => s.onchange = () => safe(async () => { await api('fm_task', {task: s.dataset.task, fid: s.value}); toast('기본 양식을 정했어요'); }));
  $('#itAdd').onclick = () => safe(async () => {
    const r = await modal('항목 만들기', '<label class="lb">항목 이름</label><input class="field" id="inN" placeholder="예: 담당 부서"><label class="lb" style="margin-top:10px">값 (모든 서류에 같은 값이면 넣기 · 비우면 엑셀 열에서)</label><input class="field" id="inV">',
      [{text: '취소'}, {text: '만들기', cls: 'primary', value: bg => ({n: $('#inN', bg).value, v: $('#inV', bg).value})}]);
    if (!r) return;
    await api('fm_item_add', {name: r.n, value: r.v}); go('fm_company');
  });
  $$('[data-iv]', v).forEach(i => i.onchange = () => safe(async () => { await api('fm_item_set', {k: i.dataset.iv, value: i.value}); toast('저장했어요'); }));
  $$('[data-idel]', v).forEach(b => b.onclick = () => safe(async () => { await api('fm_item_set', {k: b.dataset.idel, delete: true}); go('fm_company'); }));
};
