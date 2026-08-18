// CK Quant Desktop - Electron 主进程
const { app, BrowserWindow, ipcMain, safeStorage } = require('electron');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');

// ============ 数据存储（JSON + 加密） ============
const DATA_DIR = path.join(app.getPath('userData'), 'data');
const USERS_FILE = path.join(DATA_DIR, 'users.json');
const SERVERS_FILE = path.join(DATA_DIR, 'servers.json');

function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
}

function readJson(file, fallback) {
  ensureDataDir();
  try {
    if (fs.existsSync(file)) return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (e) { console.error('读取失败:', e); }
  return fallback;
}

function writeJson(file, data) {
  ensureDataDir();
  fs.writeFileSync(file, JSON.stringify(data, null, 2));
}

// 加密存储（用系统级 safeStorage，凭据不落明文）
function encryptSecret(plain) {
  if (!plain) return null;
  const buf = safeStorage.encryptString(String(plain));
  return buf.toString('base64');
}
function decryptSecret(enc) {
  if (!enc) return '';
  try {
    return safeStorage.decryptString(Buffer.from(enc, 'base64'));
  } catch (e) { return ''; }
}

// 密码哈希（PBKDF2 + salt）
function hashPassword(password, salt) {
  return crypto.pbkdf2Sync(password, salt, 100000, 64, 'sha512').toString('hex');
}

// ============ 登录 / 订阅 ============
function registerUser(username, password) {
  const users = readJson(USERS_FILE, {});
  if (users[username]) return { ok: false, error: '用户名已存在' };
  const salt = crypto.randomBytes(16).toString('hex');
  users[username] = {
    salt,
    hash: hashPassword(password, salt),
    // 订阅：free / starter / pro / elite（对应 10U/30U/100U/200U 档）
    plan: 'free',
    planExpires: null,
    createdAt: new Date().toISOString(),
  };
  writeJson(USERS_FILE, users);
  return { ok: true };
}

function loginUser(username, password) {
  const users = readJson(USERS_FILE, {});
  const u = users[username];
  if (!u) return { ok: false, error: '用户名或密码错误' };
  if (u.hash !== hashPassword(password, u.salt)) return { ok: false, error: '用户名或密码错误' };
  return { ok: true, plan: u.plan, planExpires: u.planExpires };
}

// 订阅档位：free 只能模拟盘；付费解锁实盘
const PLANS = {
  free:   { label: '免费版', maxCapital: 0,    monthlyU: 0,    live: false },
  starter:{ label: '基础版', maxCapital: 1000,  monthlyU: 10,   live: true },
  pro:    { label: '专业版', maxCapital: 10000, monthlyU: 30,   live: true },
  elite:  { label: '旗舰版', maxCapital: 100000,monthlyU: 100,  live: true },
  whale:  { label: '鲸鱼版', maxCapital: 500000,monthlyU: 200,  live: true },
};

// ============ SSH 部署引擎（ssh2） ============
const { Client } = require('ssh2');

// 全自动 Docker 安装脚本（无交互，国内源优先，多级回退）
const DOCKER_INSTALL_SCRIPT = `#!/usr/bin/env bash
set -e
log()  { echo "[docker-install] $*"; }
fail() { echo "[docker-install] FAIL $*"; exit 1; }
log "=== CK Quant Docker auto-install ==="
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  log "Docker already installed"; exit 0
fi
if [ -f /etc/os-release ]; then . /etc/os-release; OS_ID="$ID"; else OS_ID="unknown"; fi
log "System: $OS_ID $(uname -m)"
install_deps() {
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq >/dev/null 2>&1 || true
    apt-get install -y -qq curl ca-certificates gnupg lsb-release >/dev/null 2>&1 || true
  elif command -v yum >/dev/null 2>&1; then
    yum install -y -q curl ca-certificates >/dev/null 2>&1 || true
  fi
}
try_official() {
  log "Trying official script (get.docker.com)..."
  if curl -fsSL --connect-timeout 10 https://get.docker.com -o /tmp/get-docker.sh 2>/dev/null; then
    sh /tmp/get-docker.sh >/tmp/docker-install.log 2>&1 && return 0
    log "Official failed, trying mirrors..."
  fi
  return 1
}
try_aliyun() {
  log "Trying Aliyun mirror..."
  local arch="$(uname -m)" docker_arch=""
  case "$arch" in
    x86_64)  docker_arch="amd64" ;;
    aarch64) docker_arch="arm64" ;;
    *)       docker_arch="$arch" ;;
  esac
  if command -v apt-get >/dev/null 2>&1; then
    local distro="$(lsb_release -is 2>/dev/null | tr '[:upper:]' '[:lower:]' || echo "$OS_ID")"
    local codename="$(grep -oP 'VERSION_CODENAME=\\K.*' /etc/os-release 2>/dev/null || echo bookworm)"
    mkdir -p /etc/apt/keyrings
    curl -fsSL --connect-timeout 10 "https://mirrors.aliyun.com/docker-ce/linux/$distro/gpg" -o /etc/apt/keyrings/docker.asc 2>/dev/null || return 1
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$docker_arch signed-by=/etc/apt/keyrings/docker.asc] https://mirrors.aliyun.com/docker-ce/linux/$distro $codename stable" > /etc/apt/sources.list.d/docker.list
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq >/dev/null 2>&1 || true
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null 2>&1 && return 0
  elif command -v yum >/dev/null 2>&1; then
    yum install -y -q yum-utils >/dev/null 2>&1 || true
    yum-config-manager --add-repo "https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo" >/dev/null 2>&1 || return 1
    yum install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null 2>&1 && return 0
  fi
  return 1
}
install_deps
if ! try_official; then
  try_aliyun || fail "Docker install failed"
fi
log "Starting Docker + enable on boot..."
if command -v systemctl >/dev/null 2>&1; then
  systemctl enable docker >/dev/null 2>&1 || true
  systemctl start docker >/dev/null 2>&1 || service docker start || true
elif command -v service >/dev/null 2>&1; then
  service docker start >/dev/null 2>&1 || true
fi
sleep 2
if docker --version >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  log "DOCKER_OK $(docker --version)"
  exit 0
else
  fail "Docker verification failed"
fi
`;

class SSHClient {
  constructor(conn) { this.conn = conn; }

  // 执行命令，返回 stdout/stderr
  exec(cmd, timeout = 120000) {
    return new Promise((resolve, reject) => {
      this.conn.exec(cmd, (err, stream) => {
        if (err) return reject(err);
        let stdout = '', stderr = '';
        stream.on('close', (code) => {
          resolve({ code, stdout, stderr });
        }).on('data', (d) => { stdout += d.toString(); })
          .stderr.on('data', (d) => { stderr += d.toString(); });
        stream.on('error', reject);
        setTimeout(() => { stream.end(); }, timeout);
      });
    });
  }

  // 上传文件内容（写入远程路径）
  writeFile(remotePath, content) {
    return new Promise((resolve, reject) => {
      this.conn.sftp((err, sftp) => {
        if (err) return reject(err);
        sftp.writeFile(remotePath, content, (err2) => {
          if (err2) return reject(err2);
          resolve();
        });
      });
    });
  }

  close() { this.conn.end(); }
}

function sshConnect(cfg) {
  return new Promise((resolve, reject) => {
    const conn = new Client();
    conn.on('ready', () => resolve(new SSHClient(conn)));
    conn.on('error', (e) => reject(new Error(`SSH 连接失败: ${e.message}`)));
    conn.connect({
      host: cfg.host,
      port: cfg.port || 22,
      username: cfg.username,
      password: cfg.password,
      readyTimeout: 15000,
    });
  });
}

// ============ 部署流程 ============
async function deployRobot(ssh, config, onLog) {
  const logs = [];
  const log = (msg) => { logs.push(msg); onLog?.(msg); };

  try {
    log('① 检查 Docker 环境...');
    let r = await ssh.exec('docker --version && docker compose version');
    if (r.code !== 0) {
      if (config.autoInstallDocker !== false) {
        log('⚠️ 未检测到 Docker，开始全自动安装（约 3-10 分钟）...');
        // 上传全自动安装脚本（无交互，国内源优先）
        // 注意：必须转 LF 换行，否则 bash 报 CRLF 错误
                const script = DOCKER_INSTALL_SCRIPT.replace(/\r\n/g, '\n');
        await ssh.writeFile('~/ck-docker-install.sh', script);
        await ssh.exec('chmod +x ~/ck-docker-install.sh');
        r = await ssh.exec('bash ~/ck-docker-install.sh', 900000);
        if (r.code !== 0) {
          log('❌ Docker 自动安装失败: ' + r.stderr.slice(-300));
          return { ok: false, logs };
        }
        // 重新验证
        r = await ssh.exec('docker --version && docker compose version');
        if (r.code !== 0) {
          log('❌ Docker 安装后仍不可用，请手动检查');
          return { ok: false, logs };
        }
        log('✅ Docker 全自动安装成功');
      } else {
        log('❌ 服务器未安装 Docker，请先安装 Docker 或开启自动安装');
        return { ok: false, logs };
      }
    }
    log('✅ Docker 环境正常');

    log('② 创建目录并下载 docker-compose.yml...');
    await ssh.exec(`mkdir -p ~/CK_Quant/user_data/strategies`);
    await ssh.writeFile('~/CK_Quant/docker-compose.yml', `services:
  CK_Quant:
    image: ericchenghz/ck-quant:stable
    container_name: CK_Quant
    restart: unless-stopped
    volumes:
      - "./user_data:/CK_Quant/user_data"
    ports:
      - "8080:8080"
    command: >
      trade
      --userdir /CK_Quant/user_data
      --config /CK_Quant/user_data/config.json
      --strategy ${config.strategy}
`);
    log('✅ docker-compose.yml 已创建');

    log('③ 拉取镜像...');
    r = await ssh.exec('cd ~/CK_Quant && docker compose pull', 600000);
    if (r.code !== 0) { log('❌ 镜像拉取失败: ' + r.stderr.slice(-200)); return { ok: false, logs }; }
    log('✅ 镜像拉取完成');

    if (config.configContent) {
      log('④ 上传用户 config.json...');
      await ssh.writeFile('~/CK_Quant/user_data/config.json', config.configContent);
      log('✅ 用户 config.json 已上传');
    } else {
      log('④ 写入默认 config.json...');
      const cfg = buildFreqtradeConfig(config);
      await ssh.writeFile('~/CK_Quant/user_data/config.json', JSON.stringify(cfg, null, 2));
      log('✅ 默认 config.json 已写入');
    }

    if (config.strategyContent) {
      log('⑤ 上传策略文件...');
      await ssh.writeFile(`~/CK_Quant/user_data/strategies/${config.strategy}.py`, config.strategyContent);
      log('✅ 策略已上传');
    }

    log('⑥ 启动机器人...');
    r = await ssh.exec('cd ~/CK_Quant && docker compose up -d', 120000);
    if (r.code !== 0) { log('❌ 启动失败: ' + r.stderr.slice(-200)); return { ok: false, logs }; }
    log('✅ 机器人已启动！');

    return { ok: true, logs };
  } catch (e) {
    log(`❌ 部署异常: ${e.message}`);
    return { ok: false, logs };
  }
}

function buildFreqtradeConfig(cfg) {
  const dryRun = cfg.dryRun !== false;
  // stake_amount: 支持固定金额（数字）或本金百分比（如 "10%"）
  let stakeAmount = cfg.stakeAmount || 100;
  if (typeof stakeAmount === 'string' && stakeAmount.endsWith('%')) {
    stakeAmount = parseFloat(stakeAmount) / 100; // freqtrade 用 0.1 = 10% 本金
  }
  const conf = {
    trading_mode: cfg.tradingMode || 'futures',
    margin_mode: cfg.marginMode || 'isolated',
    stake_currency: 'USDT',
    stake_amount: stakeAmount,
    max_open_trades: cfg.maxOpenTrades || 10,
    dry_run: dryRun,
    exchange: {
      name: cfg.exchange,
      key: cfg.apiKey || '',
      secret: cfg.apiSecret || '',
      pair_whitelist: cfg.pairWhitelist || ['BTC/USDT:USDT', 'ETH/USDT:USDT'],
      pair_blacklist: [],
    },
    pairlists: cfg.pairlists || [{ method: 'StaticPairList' }],
    telegram: {
      enabled: !!cfg.telegramToken,
      token: cfg.telegramToken || '',
      chat_id: cfg.telegramChatId || '',
    },
    api_server: {
      enabled: true,
      listen_ip_address: '0.0.0.0',
      listen_port: 8080,
      username: cfg.apiUsername || 'ckquant',
      password: cfg.apiPassword || 'ckquant123',
      jwt_secret_key: crypto.randomBytes(32).toString('hex'),
      ws_token: crypto.randomBytes(32).toString('hex'),
    },
  };
  // 模拟盘起始本金（默认 10000）
  if (dryRun) {
    conf.dry_run_wallet = cfg.dryRunWallet || 10000;
  }
  return conf;
}

// ============ 日志流（docker logs -f） ============
async function streamLogs(ssh, onData, onClose) {
  ssh.conn.exec('cd ~/CK_Quant && docker compose logs -f --tail 100', (err, stream) => {
    if (err) { onClose(err.message); return; }
    stream.on('data', (d) => onData(d.toString()));
    stream.stderr.on('data', (d) => onData(d.toString()));
    stream.on('close', () => onClose?.());
  });
  return ssh;
}

// ============ 窗口 ============
let mainWindow;
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 960,
    minHeight: 640,
    title: 'CK Quant Desktop',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  mainWindow.loadFile(path.join(__dirname, '../src/index.html'));
}

// ============ IPC ============
// 当前会话状态
let session = null;
let sshCache = new Map(); // serverId -> SSHClient

ipcMain.handle('auth:register', (e, { username, password }) => registerUser(username, password));
ipcMain.handle('auth:login', (e, { username, password }) => {
  const r = loginUser(username, password);
  if (r.ok) session = { username, ...r };
  return r;
});
ipcMain.handle('auth:logout', () => { session = null; return { ok: true }; });
ipcMain.handle('auth:session', () => session);
ipcMain.handle('plans:list', () => PLANS);

// 服务器管理
ipcMain.handle('server:list', () => {
  const servers = readJson(SERVERS_FILE, {});
  // 解密返回（脱敏）
  return Object.entries(servers).map(([id, s]) => ({
    id, name: s.name, host: s.host, port: s.port, username: s.username,
    exchange: s.exchange, status: s.status || '未部署',
  }));
});
ipcMain.handle('server:save', (e, data) => {
  if (!session) return { ok: false, error: '未登录' };
  const servers = readJson(SERVERS_FILE, {});
  const id = data.id || crypto.randomBytes(8).toString('hex');
  servers[id] = {
    ...data,
    id,
    password: data.password ? encryptSecret(data.password) : (servers[id]?.password || null),
    apiSecret: data.apiSecret ? encryptSecret(data.apiSecret) : (servers[id]?.apiSecret || null),
    telegramToken: data.telegramToken ? encryptSecret(data.telegramToken) : (servers[id]?.telegramToken || null),
  };
  writeJson(SERVERS_FILE, servers);
  return { ok: true, id };
});
ipcMain.handle('server:delete', (e, id) => {
  const servers = readJson(SERVERS_FILE, {});
  delete servers[id];
  writeJson(SERVERS_FILE, servers);
  return { ok: true };
});
ipcMain.handle('server:get', (e, id) => {
  const servers = readJson(SERVERS_FILE, {});
  const s = servers[id];
  if (!s) return null;
  return { ...s, password: decryptSecret(s.password), apiSecret: decryptSecret(s.apiSecret), telegramToken: decryptSecret(s.telegramToken) };
});

// 部署
ipcMain.handle('deploy:run', async (e, { serverId, config }) => {
  if (!session) return { ok: false, error: '未登录' };
  const servers = readJson(SERVERS_FILE, {});
  const s = servers[serverId];
  if (!s) return { ok: false, error: '服务器不存在' };

  const ssh = await sshConnect({
    host: s.host, port: s.port, username: s.username,
    password: decryptSecret(s.password),
  });
  sshCache.set(serverId, ssh);

  const merged = { ...s, ...config, apiKey: config.apiKey || s.apiKey, apiSecret: config.apiSecret || decryptSecret(s.apiSecret), telegramToken: config.telegramToken || decryptSecret(s.telegramToken) };
  const result = await deployRobot(ssh, merged, (msg) => {
    mainWindow.webContents.send('deploy:log', { serverId, msg });
  });
  return result;
});
ipcMain.handle('deploy:disconnect', (e, serverId) => {
  const ssh = sshCache.get(serverId);
  if (ssh) { ssh.close(); sshCache.delete(serverId); }
  return { ok: true };
});

// 日志流
ipcMain.handle('logs:start', (e, serverId) => {
  const ssh = sshCache.get(serverId);
  if (!ssh) return { ok: false, error: '未连接' };
  streamLogs(ssh, (data) => {
    mainWindow.webContents.send('logs:data', { serverId, data });
  }, () => {});
  return { ok: true };
});

// 端口转发（WebUI 内嵌）
ipcMain.handle('tunnel:start', (e, serverId) => {
  const ssh = sshCache.get(serverId);
  if (!ssh) return { ok: false, error: '未连接' };
  // 动态分配本地端口，转发到远程 8080
  const localPort = 18080 + Math.floor(Math.random() * 1000);
  ssh.conn.forwardOut('127.0.0.1', 8080, '127.0.0.1', localPort, (err) => {
    if (err) return { ok: false, error: err.message };
  });
  return { ok: true, localPort };
});

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
