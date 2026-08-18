// CK Quant Desktop - 渲染进程逻辑
const api = window.ckQuant;

// ============ 工具 ============
function $(sel) { return document.querySelector(sel); }
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3000);
}
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// ============ 登录页 ============
let session = null;
let servers = [];
let currentDeployServerId = null;

// Tab 切换
document.querySelectorAll('.tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((t) => t.classList.remove('active'));
    tab.classList.add('active');
    const isLogin = tab.dataset.tab === 'login';
    $('#loginForm').style.display = isLogin ? 'block' : 'none';
    $('#registerForm').style.display = isLogin ? 'none' : 'block';
    $('#authError').textContent = '';
  });
});

async function doLogin(username, password) {
  const r = await api.login(username, password);
  if (r.ok) {
    session = r;
    $('#userName').textContent = username;
    $('#planBadge').textContent = { free: '免费版', starter: '基础版', pro: '专业版', elite: '旗舰版', whale: '鲸鱼版' }[r.plan] || '免费版';
    $('#loginPage').classList.remove('show');
    $('#mainPage').classList.add('show');
    await loadServers();
  } else {
    $('#authError').textContent = r.error;
  }
}

$('#loginBtn').addEventListener('click', () => doLogin($('#loginUser').value.trim(), $('#loginPass').value));
$('#loginPass').addEventListener('keydown', (e) => { if (e.key === 'Enter') doLogin($('#loginUser').value.trim(), $('#loginPass').value); });

$('#regBtn').addEventListener('click', async () => {
  const u = $('#regUser').value.trim(), p = $('#regPass').value, p2 = $('#regPass2').value;
  if (!u || p.length < 6) { $('#authError').textContent = '用户名不能为空，密码至少6位'; return; }
  if (p !== p2) { $('#authError').textContent = '两次密码不一致'; return; }
  const r = await api.register(u, p);
  if (r.ok) { toast('注册成功，请登录'); $('#authError').textContent = ''; doLogin(u, p); }
  else $('#authError').textContent = r.error;
});

$('#logoutBtn').addEventListener('click', async () => {
  await api.logout();
  session = null;
  $('#mainPage').classList.remove('show');
  $('#loginPage').classList.add('show');
});

// ============ 导航 ============
document.querySelectorAll('.nav-item').forEach((item) => {
  item.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach((n) => n.classList.remove('active'));
    item.classList.add('active');
    document.querySelectorAll('.page').forEach((p) => p.classList.remove('active'));
    $(`#page-${item.dataset.page}`).classList.add('active');
    if (item.dataset.page === 'servers') loadServers();
    if (item.dataset.page === 'deploy') renderDeployWizard();
    if (item.dataset.page === 'plans') renderPlans();
  });
});

// ============ 服务器管理 ============
async function loadServers() {
  servers = await api.listServers();
  const list = $('#serverList');
  if (!servers.length) {
    list.innerHTML = '<div class="card" style="color:var(--muted)">还没有服务器，点击下方按钮添加</div>';
    return;
  }
  list.innerHTML = servers.map((s) => `
    <div class="server-card">
      <div>
        <div class="name">${esc(s.name)}</div>
        <div class="host">${esc(s.host)}:${s.port || 22} · ${esc(s.username)} · ${esc(s.exchange || 'binance')}</div>
      </div>
      <div class="server-actions">
        <span class="status ${s.status === '已部署' ? 'deployed' : 'pending'}">${esc(s.status || '未部署')}</span>
        <button class="btn btn-ghost btn-sm" onclick="editServer('${s.id}')">编辑</button>
        <button class="btn btn-danger btn-sm" onclick="delServer('${s.id}')">删除</button>
      </div>
    </div>`).join('');
}

window.editServer = async (id) => {
  const s = await api.getServer(id);
  if (!s) return;
  openServerForm(s);
};
window.delServer = async (id) => {
  if (!confirm('确定删除该服务器？')) return;
  await api.deleteServer(id);
  toast('已删除');
  loadServers();
};

$('#addServerBtn').addEventListener('click', () => openServerForm(null));

// 服务器表单（模态简化：直接弹窗 prompt 风格 -> 用内联表单）
function openServerForm(server) {
  const isEdit = !!server;
  const html = `
    <div class="card">
      <h3>${isEdit ? '编辑服务器' : '添加服务器'}</h3>
      <div class="grid-2">
        <div><label>名称</label><input id="f_name" value="${esc(server?.name || '')}" placeholder="如：阿里云实盘"></div>
        <div><label>IP 地址</label><input id="f_host" value="${esc(server?.host || '')}" placeholder="如：47.91.1.141"></div>
        <div><label>SSH 端口</label><input id="f_port" value="${server?.port || 22}"></div>
        <div><label>SSH 用户名</label><input id="f_username" value="${esc(server?.username || 'root')}"></div>
        <div><label>SSH 密码</label><input id="f_password" type="password" placeholder="${isEdit ? '留空则不修改' : '服务器密码'}"></div>
        <div><label>交易所</label>
          <select id="f_exchange"><option value="binance" ${server?.exchange === 'binance' ? 'selected' : ''}>Binance</option><option value="bybit" ${server?.exchange === 'bybit' ? 'selected' : ''}>Bybit</option><option value="okx" ${server?.exchange === 'okx' ? 'selected' : ''}>OKX</option><option value="gate" ${server?.exchange === 'gate' ? 'selected' : ''}>Gate</option></select>
        </div>
      </div>
      <div style="display:flex;gap:10px;margin-top:8px">
        <button class="btn" style="width:auto" id="f_save">保存</button>
        <button class="btn btn-ghost" style="width:auto" id="f_cancel">取消</button>
      </div>
    </div>`;
  const container = $('#deployWizard');
  container.innerHTML = html;
  $('#page-deploy').classList.add('active');
  document.querySelectorAll('.nav-item').forEach((n) => n.classList.remove('active'));
  document.querySelector('.nav-item[data-page="deploy"]').classList.add('active');
  document.querySelectorAll('.page').forEach((p) => p.classList.remove('active'));
  $('#page-deploy').classList.add('active');

  $('#f_save').addEventListener('click', async () => {
    const data = {
      id: server?.id,
      name: $('#f_name').value.trim(),
      host: $('#f_host').value.trim(),
      port: parseInt($('#f_port').value) || 22,
      username: $('#f_username').value.trim(),
      password: $('#f_password').value,
      exchange: $('#f_exchange').value,
    };
    if (!data.name || !data.host || !data.username) { toast('请填写名称/IP/用户名'); return; }
    const r = await api.saveServer(data);
    if (r.ok) { toast(isEdit ? '已更新' : '已添加'); loadServers(); $('#deployWizard').innerHTML = ''; }
    else toast(r.error || '保存失败');
  });
  $('#f_cancel').addEventListener('click', () => { $('#deployWizard').innerHTML = ''; });
}

// ============ 部署向导 ============
function renderDeployWizard() {
  const list = servers.map((s) => `<option value="${s.id}">${esc(s.name)} (${esc(s.host)})</option>`).join('');
  const w = $('#deployWizard');
  w.innerHTML = `
    <div class="card">
      <h3>1. 选择服务器</h3>
      <select id="d_server">${list || '<option value="">请先在"我的服务器"添加</option>'}</select>
    </div>
    <div class="card">
      <h3>2. 交易所 API</h3>
      <div class="grid-2">
        <div><label>API Key</label><input id="d_apikey" placeholder="交易所 API Key"></div>
        <div><label>API Secret</label><input id="d_apisecret" type="password" placeholder="交易所 API Secret"></div>
      </div>
    </div>
    <div class="card">
      <h3>3. Telegram（可选）</h3>
      <div class="grid-2">
        <div><label>Bot Token</label><input id="d_tgtoken" placeholder="BotFather 获取的 token"></div>
        <div><label>Chat ID</label><input id="d_tgchat" placeholder="你的 Telegram ID"></div>
      </div>
    </div>
    <div class="card">
      <h3>4. 策略与配置</h3>
      <div class="grid-2">
        <div><label>策略名称（类名）</label><input id="d_strategy" value="CK_Trend_15m" placeholder="如：CK_Trend_15m"></div>
        <div><label>每笔金额 (USDT) 或本金百分比（如 10%）</label><input id="d_stake" value="100"></div>
        <div><label>最大同时持仓</label><input id="d_maxopen" value="10"></div>
        <div><label>运行模式</label>
          <select id="d_dryrun"><option value="true" ${session?.plan === 'free' ? 'selected' : ''}>模拟盘 (dry_run)</option><option value="false" ${session?.plan !== 'free' ? 'selected' : ''}>实盘</option></select>
        </div>
        <div id="d_walletRow"><label>模拟盘起始本金 (USDT)</label><input id="d_wallet" value="10000" placeholder="如：10000"></div>
      </div>
      <div style="margin-top:10px">
        <label>config.json（可选）—— 上传后使用你的完整配置，以下选项仅对默认配置生效</label>
        <input type="file" id="d_configfile" accept=".json,.jsonc">
      </div>
      <div style="margin-top:10px"><label>策略文件 (.py) —— 可选，不选则只部署框架</label><input type="file" id="d_strategyfile" accept=".py"></div>
      <div style="margin-top:10px"><label>或粘贴策略代码</label><textarea id="d_strategytext" style="width:100%;height:120px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:10px;font-family:monospace;font-size:12px" placeholder="# 粘贴你的策略代码..."></textarea></div>
      <div style="margin-top:10px">
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
          <input type="checkbox" id="d_autodocker" checked style="width:auto;margin:0">
          服务器未安装 Docker 时自动安装（使用国内镜像一键脚本，约 5-10 分钟）
        </label>
      </div>
    </div>
    <div class="card">
      <h3>5. 部署</h3>
      <button class="btn btn-success" id="d_deployBtn" style="width:auto;padding:12px 32px">🚀 一键部署并启动</button>
      <div style="margin-top:16px">
        <h3 style="margin-bottom:8px">部署日志</h3>
        <div class="log-window" id="deployLog" style="height:200px"></div>
      </div>
    </div>`;
  $('#d_deployBtn').addEventListener('click', deployNow);
}

async function deployNow() {
  const serverId = $('#d_server').value;
  if (!serverId) { toast('请先选择服务器'); return; }

  let strategyContent = $('#d_strategytext').value;
  const file = $('#d_strategyfile').files[0];
  if (file && !strategyContent) {
    strategyContent = await file.text();
  }

  // 可选：上传用户 config.json
  let configContent = null;
  const cfgFile = $('#d_configfile').files[0];
  if (cfgFile) {
    configContent = await cfgFile.text();
  }

  const dryRun = session?.plan === 'free' ? true : $('#d_dryrun').value === 'true';

  const config = {
    strategy: $('#d_strategy').value.trim() || 'MyStrategy',
    apiKey: $('#d_apikey').value.trim(),
    apiSecret: $('#d_apisecret').value.trim(),
    telegramToken: $('#d_tgtoken').value.trim(),
    telegramChatId: $('#d_tgchat').value.trim(),
    stakeAmount: $('#d_stake').value.trim() || 100,
    maxOpenTrades: parseInt($('#d_maxopen').value) || 10,
    dryRun,
    dryRunWallet: parseFloat($('#d_wallet').value) || 10000,
    autoInstallDocker: $('#d_autodocker').checked,
    configContent,
    strategyContent: strategyContent || null,
    tradingMode: 'futures',
    marginMode: 'isolated',
  };

  const logBox = $('#deployLog');
  logBox.innerHTML = '';
  api.onLog(({ serverId: sid, msg }) => {
    if (sid !== serverId) return;
    const cls = msg.includes('✅') ? 'ok' : msg.includes('❌') ? 'err' : 'info';
    const div = document.createElement('div');
    div.className = `log-line ${cls}`;
    div.textContent = msg;
    logBox.appendChild(div);
    logBox.scrollTop = logBox.scrollHeight;
  });

  $('#d_deployBtn').disabled = true;
  $('#d_deployBtn').textContent = '⏳ 部署中...';
  const r = await api.deploy(serverId, config);
  $('#d_deployBtn').disabled = false;
  $('#d_deployBtn').textContent = '🚀 一键部署并启动';
  if (r.ok) { toast('✅ 部署成功！机器人已启动'); loadServers(); }
  else toast('❌ 部署失败，请查看日志');
}

// ============ 监控 ============
async function renderMonitor() {
  const deployed = servers.filter((s) => s.status === '已部署');
  $('#monitorServerSelect').innerHTML = deployed.length
    ? `<select id="m_server">${deployed.map((s) => `<option value="${s.id}">${esc(s.name)}</option>`).join('')}</select>
       <button class="btn btn-sm" style="margin-top:8px" id="m_start">▶ 连接日志</button>`
    : '<p style="color:var(--muted)">暂无已部署的服务器</p>';
  const startBtn = $('#m_start');
  if (startBtn) startBtn.addEventListener('click', async () => {
    const sid = $('#m_server').value;
    $('#logWindow').innerHTML = '';
    api.onLogData(({ serverId, data }) => {
      if (serverId !== sid) return;
      const div = document.createElement('div');
      div.className = 'log-line info';
      div.textContent = data;
      $('#logWindow').appendChild(div);
      $('#logWindow').scrollTop = $('#logWindow').scrollHeight;
    });
    await api.startLogs(sid);
  });
}

// ============ WebUI ============
async function renderWebUI() {
  const deployed = servers.filter((s) => s.status === '已部署');
  $('#webuiServerSelect').innerHTML = deployed.length
    ? `<select id="w_server">${deployed.map((s) => `<option value="${s.id}">${esc(s.name)}</option>`).join('')}</select>`
    : '<p style="color:var(--muted)">暂无已部署的服务器</p>';
  const btn = $('#webuiOpenBtn');
  btn.onclick = async () => {
    const sid = $('#w_server').value;
    if (!sid) { toast('请选择服务器'); return; }
    const r = await api.startTunnel(sid);
    if (r.ok) {
      $('#webuiFrameWrap').style.display = 'block';
      $('#webuiFrame').src = `http://127.0.0.1:${r.localPort}`;
      toast(`WebUI 隧道已建立 (端口 ${r.localPort})`);
    } else toast(r.error || '隧道建立失败');
  };
}

// ============ 订阅 ============
async function renderPlans() {
  const plans = await api.getPlans();
  const cards = Object.entries(plans).map(([key, p]) => `
    <div class="plan-card ${p.monthlyU ? '' : 'highlight'}">
      <h3>${p.label}</h3>
      <div class="price">${p.monthlyU === 0 ? '免费' : p.monthlyU + ' U'}<span>/月</span></div>
      <div class="desc">${p.maxCapital === 0 ? '模拟盘体验' : `管理资金 ≤ ${p.maxCapital} USDT`}${p.live ? '<br>✅ 实盘交易' : '<br>🚫 仅模拟盘'}</div>
      <button class="btn ${p.monthlyU ? '' : 'btn-ghost'}" onclick="toast('订阅功能即将上线，敬请期待')">${session?.plan === key ? '当前方案' : '选择'}</button>
    </div>`).join('');
  $('#planCards').innerHTML = cards;
}

// ============ 初始化 ============
(async () => {
  // 检查是否已有会话
  const s = await api.getSession();
  if (s) {
    session = s;
    $('#userName').textContent = s.username;
    $('#planBadge').textContent = { free: '免费版', starter: '基础版', pro: '专业版', elite: '旗舰版', whale: '鲸鱼版' }[s.plan] || '免费版';
    $('#mainPage').classList.add('show');
    await loadServers();
  } else {
    $('#loginPage').classList.add('show');
  }
})();
