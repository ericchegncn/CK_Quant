// 通过 Electron 解密凭据并读取远程 config 的 api_server（诊断用）
const { app, safeStorage } = require('electron');
const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

app.whenReady().then(async () => {
  const serversFile = 'C:/Users/Eric Cheng/AppData/Roaming/ck-quant-desktop/data/servers.json';
  const servers = JSON.parse(fs.readFileSync(serversFile, 'utf8'));
  const s = Object.values(servers)[0];
  if (!s) { console.log('无服务器记录'); app.exit(1); return; }

  const password = safeStorage.decryptString(Buffer.from(s.password, 'base64'));
  console.log('服务器:', s.name, s.host, s.username, '| 状态:', s.status);

  const conn = new Client();
  conn.on('ready', async () => {
    console.log('✅ SSH 连接成功');
    const r = await exec(conn, `cat ~/CK_Quant/user_data/config.json 2>/dev/null | grep -A8 '"api_server"' | head -12`);
    console.log('=== 服务器 config.json 的 api_server ===');
    console.log(r.stdout || '(未找到 api_server 或文件不存在)');
    conn.end();
    app.exit(0);
  });
  conn.on('error', (e) => { console.log('❌ SSH 错误:', e.message); app.exit(1); });
  conn.connect({ host: s.host, port: s.port || 22, username: s.username, password, readyTimeout: 15000 });
});

function exec(conn, cmd, timeout = 30000) {
  return new Promise((resolve, reject) => {
    conn.exec(cmd, (err, stream) => {
      if (err) return reject(err);
      let stdout = '', stderr = '';
      stream.on('close', (code) => resolve({ code, stdout, stderr }))
        .on('data', (d) => { stdout += d.toString(); })
        .stderr.on('data', (d) => { stderr += d.toString(); });
      stream.on('error', reject);
      setTimeout(() => stream.end(), timeout);
    });
  });
}
