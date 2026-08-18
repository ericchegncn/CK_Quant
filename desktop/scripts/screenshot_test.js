// CK Quant Desktop - 截图验证（开发用）
const { app, BrowserWindow } = require('electron');
const path = require('path');
const fs = require('fs');

app.whenReady().then(async () => {
  const win = new BrowserWindow({
    width: 1280,
    height: 820,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, '../electron/preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  await win.loadFile(path.join(__dirname, '../src/index.html'));
  await new Promise((r) => setTimeout(r, 2500));

  // 检查登录页是否显示
  const hasLogin = await win.webContents.executeJavaScript(
    `document.querySelector('#loginPage').classList.contains('show')`
  );
  console.log('登录页显示:', hasLogin);

  // 截图
  const img = await win.webContents.capturePage();
  const out = path.join(process.env.LOCALAPPDATA || 'C:/Users/Eric Cheng/AppData/Local/Temp', 'ckd_login.png');
  fs.writeFileSync(out, img.toPNG());
  console.log('截图保存:', out);

  app.quit();
});
