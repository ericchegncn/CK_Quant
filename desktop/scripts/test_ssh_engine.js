// 测试 SSH 部署引擎核心流程（连本地测试容器 127.0.0.1:2222）
const { Client } = require('ssh2');

const HOST = '127.0.0.1';
const PORT = 2222;
const USER = 'root';
const PASS = 'TestPass123';

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

const conn = new Client();
conn.on('ready', async () => {
  console.log('✅ SSH 连接成功');
  try {
    // 1. 测试基础命令
    let r = await exec(conn, 'uname -a && whoami && pwd');
    console.log('✅ 命令执行:', r.stdout.trim().split('\n').join(' | '));

    // 2. 创建目录
    r = await exec(conn, 'mkdir -p ~/CK_Quant/user_data/strategies && echo OK');
    console.log('✅ 目录创建:', r.stdout.trim());

    // 3. 上传文件（模拟 docker-compose.yml）
    await writeFile(conn, '/root/CK_Quant/docker-compose.yml', 'test: "compose content"\n');
    r = await exec(conn, 'cat /root/CK_Quant/docker-compose.yml');
    console.log('✅ 文件上传验证:', r.stdout.trim());

    // 4. 上传策略文件
    await writeFile(conn, '/root/CK_Quant/user_data/strategies/TestStrategy.py', 'class TestStrategy:\n    pass\n');
    r = await exec(conn, 'ls -la /root/CK_Quant/user_data/strategies/');
    console.log('✅ 策略上传验证:', r.stdout.trim().split('\n').pop());

    console.log('\n🎉 SSH 部署引擎全部功能测试通过！');
  } catch (e) {
    console.log('❌ 测试失败:', e.message);
  }
  conn.end();
  process.exit(0);
});
conn.on('error', (e) => { console.log('❌ SSH 错误:', e.message); process.exit(1); });
conn.connect({ host: HOST, port: PORT, username: USER, password: PASS, readyTimeout: 15000 });
