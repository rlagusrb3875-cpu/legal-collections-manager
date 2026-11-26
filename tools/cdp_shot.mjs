// 사용법 화면 찍기 (회수 분석처럼 오래 계산하는 화면용):
//   node tools/cdp_shot.mjs <크롬 경로> <주소> <저장할 png> [최대 기다림 ms]
// 헤드리스 크롬을 DevTools 로 열고, 화면이 window.__done = true 를 세울 때까지 실제 시간으로 기다렸다가 1366×768(2배)로 찍는다.
import {spawn} from 'node:child_process';
import {mkdtempSync, writeFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

const [chrome, url, out, maxWait = '90000'] = process.argv.slice(2);
const dir = mkdtempSync(join(tmpdir(), 'cdp_shot_'));
const keychainArgs = process.platform === 'darwin' ? ['--use-mock-keychain'] : [];
const ch = spawn(chrome, ['--headless=new', '--disable-gpu', ...keychainArgs, '--hide-scrollbars', '--remote-debugging-port=0', `--user-data-dir=${dir}`,
  '--window-size=1366,768', 'about:blank'], {stdio: ['ignore', 'ignore', 'pipe']});
const quit = code => { try { ch.kill(); } catch (e) {} setTimeout(() => { try { rmSync(dir, {recursive: true, force: true}); } catch (e) {} process.exit(code); }, 300); };
setTimeout(() => { console.error('시간 넘음'); quit(2); }, +maxWait + 30000);

const port = await new Promise((res, rej) => {
  let buf = '';
  ch.stderr.on('data', d => { buf += d; const m = buf.match(/DevTools listening on ws:\/\/[^:]+:(\d+)\//); if (m) res(m[1]); });
  ch.on('exit', () => rej(new Error('크롬이 꺼짐')));
});
const pages = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const ws = new WebSocket(pages.find(p => p.type === 'page').webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener('open', r));
let id = 0;
const wait = new Map();
ws.addEventListener('message', e => { const m = JSON.parse(e.data); if (m.id && wait.has(m.id)) { wait.get(m.id)(m); wait.delete(m.id); } });
const send = (method, params = {}) => new Promise(r => { const i = ++id; wait.set(i, r); ws.send(JSON.stringify({id: i, method, params})); });
const sleep = ms => new Promise(r => setTimeout(r, ms));

await send('Emulation.setDeviceMetricsOverride', {width: 1366, height: 768, deviceScaleFactor: 2, mobile: false});
await send('Page.enable');
await send('Page.navigate', {url});
const t0 = Date.now();
let done = false;
while (Date.now() - t0 < +maxWait) {
  await sleep(500);
  const r = await send('Runtime.evaluate', {expression: 'window.__done === true', returnByValue: true});
  if (r.result && r.result.result && r.result.result.value) { done = true; break; }
}
await sleep(400);
const shot = await send('Page.captureScreenshot', {format: 'png'});
writeFileSync(out, Buffer.from(shot.result.data, 'base64'));
const title = await send('Runtime.evaluate', {expression: 'document.title', returnByValue: true});
console.log(done ? '준비됨' : '기다림 끝(준비 신호 없음)', ((title.result || {}).result || {}).value || '');
quit(0);
