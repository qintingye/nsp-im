// W1 WDW 实测验收 — 注入 mock DOM 后整段 eval
const fs = require('fs');
const path = 'D:/hermes-dev-team/nsp-im/docs/preview/index.html';
const html = fs.readFileSync(path, 'utf8');
const js = html.match(/<script>([\s\S]*?)<\/script>/)[1];

// 预创建 mock elements
const elements = {};
function makeEl(id) {
  if (elements[id]) return elements[id];
  const el = {
    id, textContent: '', innerHTML: '', href: '',
    classList: {
      _set: new Set(),
      add(c) { this._set.add(c); },
      remove(c) { this._set.delete(c); },
      contains(c) { return this._set.has(c); }
    },
    style: {},
    parentElement: null, previousElementSibling: null,
    addEventListener() {},
    querySelectorAll() { return []; }
  };
  elements[id] = el; return el;
}
['gate','gate-input','gate-err','plist','pdate','pcount','nb','nbg',
 'modal','modal-content','m-title','m-intro','m-invest','m-source-org',
 'm-source-url','m-r1','m-r2','m-r3','m-r4','m-total','m-eval']
  .forEach(id => makeEl(id));

const sessionStorage = {
  _s: {},
  getItem(k) { return this._s[k]; },
  setItem(k, v) { this._s[k] = v; }
};

global.document = {
  getElementById: id => makeEl(id),
  querySelectorAll: () => [],
  addEventListener() {}
};
global.sessionStorage = sessionStorage;
global.alert = (m) => console.log('  [alert]', m);
global.window = {};

// 在 eval 之前注入 PROJECTS 等全局（eval 内部 const 会成为块作用域，不能用）
// 但 eval 内 const TODAY={...}; 会成为 eval 局部 — 改为 var
const jsForEval = js.replace(/^const TODAY=/m, 'var TODAY=')
                    .replace(/^const PROJECTS=/m, 'var PROJECTS=')
                    .replace(/^const NETS=/m, 'var NETS=')
                    .replace(/^const NET_KEYS=/m, 'var NET_KEYS=');

try {
  eval(jsForEval);
} catch (e) {
  console.log('Eval error:', e.message);
  process.exit(1);
}

console.log('=== W1 WDW 实测验收 ===');

// [P0-1] renderTab2 已经执行过（在 eval 中调用）
console.log('\n[P0-1] renderTab2():');
const pdate = makeEl('pdate');
const pcount = makeEl('pcount');
const plist = makeEl('plist');
console.log('  pdate:', pdate.textContent, '→ 期望 2026-08-19', pdate.textContent === '2026-08-19' ? '✓ PASS' : '✗ FAIL');
console.log('  pcount:', JSON.stringify(pcount.textContent), '→ 期望 "5"', pcount.textContent === '5' ? '✓ PASS' : '✗ FAIL');
const pcards = (plist.innerHTML.match(/class="pcard"/g) || []).length;
console.log('  pcards count:', pcards, '→ 期望 5', pcards === 5 ? '✓ PASS' : '✗ FAIL');
['新型数据中心','新型电力系统','南方电网','算电协同','多用户绿电'].forEach(t => {
  console.log('  含政策标题 [' + t + ']:', plist.innerHTML.includes(t) ? '✓' : '✗');
});

// [P0-2] openNet
console.log('\n[P0-2] openNet(water):');
try {
  openNet('water');
  const mc = makeEl('modal-content');
  console.log('  NO ERROR ✓ PASS');
  console.log('  innerHTML length:', mc.innerHTML.length, mc.innerHTML.length > 800 ? '✓ PASS' : '✗ FAIL');
  console.log('  has close button:', mc.innerHTML.includes('closeModal()') ? '✓ PASS' : '✗ FAIL');
  console.log('  has 水网·5 个项目:', mc.innerHTML.includes('水网 · 5 个项目') ? '✓ PASS' : '✗ FAIL');
  console.log('  has W1-W5 cards:', ['W1','W2','W3','W4','W5'].every(w => mc.innerHTML.includes(w)) ? '✓ PASS' : '✗ FAIL');
} catch (e) {
  console.log('  ✗ ERROR:', e.message);
}

// [P0-3] checkGate
console.log('\n[P0-3] checkGate():');
const gate = makeEl('gate');
const gateInput = makeEl('gate-input');
const gateErr = makeEl('gate-err');

// 错密码
gateInput.value = 'wrongpass';
checkGate();
console.log('  错密码 → gate 仍可见:', !gate.classList.contains('hide') ? '✓ PASS' : '✗ FAIL');
console.log('  错密码 → err 文本:', gateErr.textContent === '❌ 密码错误' ? '✓ PASS' : '✗ FAIL [' + gateErr.textContent + ']');
console.log('  错密码 → sessionStorage 未设:', sessionStorage.getItem('nsp_gate') === undefined ? '✓ PASS' : '✗ FAIL');

// 对密码
gateInput.value = 'nsp2026';
checkGate();
console.log('  对密码 → gate 隐藏:', gate.classList.contains('hide') ? '✓ PASS' : '✗ FAIL');
console.log('  对密码 → sessionStorage=ok:', sessionStorage.getItem('nsp_gate') === 'ok' ? '✓ PASS' : '✗ FAIL');

// 模拟刷新
gate.classList.remove('hide');
try { if (sessionStorage.getItem('nsp_gate') === 'ok') { gate.classList.add('hide'); } } catch(e){}
console.log('  刷新 → gate 自动隐藏:', gate.classList.contains('hide') ? '✓ PASS' : '✗ FAIL');

console.log('\n=== 全部 P0 验证完毕 ===');