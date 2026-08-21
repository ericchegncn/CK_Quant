const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const renderer = fs.readFileSync(path.join(__dirname, '..', 'src', 'app.js'), 'utf8');

test('server edit and delete controls comply with the renderer CSP', () => {
  assert.doesNotMatch(renderer, /onclick=["'][^"']*(?:editServer|delServer)/);
  assert.match(renderer, /data-server-action="edit"/);
  assert.match(renderer, /data-server-action="delete"/);
  assert.match(renderer, /#serverList'\)\.addEventListener\('click'/);
});

test('server deletion reports backend failures before changing the list', () => {
  assert.match(renderer, /if \(!result\?\.ok\) \{ toast\(result\?\.error \|\| '删除失败'\); return; \}/);
  assert.match(renderer, /确定删除该服务器？此操作只删除本机保存的服务器记录，不会删除远程机器人。/);
});
