// 测试完整部署流程（对测试容器执行 deployRobot 逻辑）
const { Client } = require('ssh2');

const conn = new Client();
const HOST = '127.0.0.1', PORT = 2222, USER = 'root', PASS = 'TestPass123';

function exec(conn, cmd, timeout = 60000) {
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
function writeFile(conn, remotePath, content) {
  return new Promise((resolve, reject) => {
    conn.sftp((err, sftp) => {
      if (err) return reject(err);
      sftp.writeFile(remotePath, content, (e) => e ? reject(e) : resolve());
    });
  });
}

conn.on('ready', async () => {
  const logs = [];
  const log = (m) => { logs.push(m); console.log(m); };
  try {
    log('① 检查 Docker 环境...');
    const r = await exec(conn, 'docker --version && docker compose version');
    if (r.code !== 0) {
      log('❌ 服务器未安装 Docker，请先安装 Docker 或改用本地部署');
      log('   stderr: ' + r.stderr.trim().slice(0, 150));
    }
  } catch (e) {
    log('❌ 部署异常: ' + e.message);
  }
  conn.end();
  process.exit(0);
});
conn.on('error', (e) => { console.log('❌ SSH 错误:', e.message); process.exit(1); });
conn.connect({ host: HOST, port: PORT, username: USER, password: PASS, readyTimeout: 15000 });
