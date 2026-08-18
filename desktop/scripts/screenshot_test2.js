// 直接加载真实 main.js 逻辑的截图验证
const { app } = require('electron');
const path = require('path');
const fs = require('fs');

// 复用 main.js 的窗口创建
process.env.CKD_SCREENSHOT = '1';
require('../electron/main.js');

app.whenReady().then(async () => {
  await new Promise(r => setTimeout(r, 3500));
  const wins = require('electron').BrowserWindow.getAllWindows();
  if (!wins.length) { console.log('❌ 无窗口'); app.exit(1); return; }
  const win = wins[0];
  const hasLogin = await win.webContents.executeJavaScript(
    `document.querySelector('#loginPage').classList.contains('show')`
  );
  console.log('登录页显示:', hasLogin);
  const img = await win.webContents.capturePage();
  const out = path.join(process.env.LOCALAPPDATA, 'ckd_login2.png');
  fs.writeFileSync(out, img.toPNG());
  console.log('截图:', out);
  app.exit(0);
});
