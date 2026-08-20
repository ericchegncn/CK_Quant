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

// ============ 终身授权 ============
let session = null;
let servers = [];
let currentDeployServerId = null;

function enterLicensedApp(status) {
  session = { username: status.payload?.customer || '授权用户', plan: 'lifetime' };
  $('#userName').textContent = session.username;
  $('#planBadge').textContent = '终身授权';
  $('#licensedMachineCode').textContent = status.machineCode;
  $('#loginPage').classList.remove('show');
  $('#mainPage').classList.add('show');
  loadServers();
}

$('#copyMachineCode').addEventListener('click', () => {
  api.copyText($('#machineCode').textContent);
  toast('机器码已复制');
});

$('#activateBtn').addEventListener('click', async () => {
  const code = $('#registrationCode').value.trim();
  if (!code) { $('#authError').textContent = '请粘贴注册码'; return; }
  $('#activateBtn').disabled = true;
  $('#activateBtn').textContent = '正在验证…';
  const result = await api.activateLicense(code);
  $('#activateBtn').disabled = false;
  $('#activateBtn').textContent = '激活终身授权';
  if (!result.valid) { $('#authError').textContent = result.error || '激活失败'; return; }
  toast('终身授权激活成功');
  enterLicensedApp(result);
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
    if (item.dataset.page === 'monitor') renderMonitor();
    if (item.dataset.page === 'webui') renderWebUI();
    if (item.dataset.page === 'chat') loadChatHistory();
    if (item.dataset.page === 'settings') loadAISettings();
  });
});

document.querySelectorAll('[data-go]').forEach((button) => {
  button.addEventListener('click', () => document.querySelector(`.nav-item[data-page="${button.dataset.go}"]`)?.click());
});

// ============ 服务器管理 ============
async function loadServers() {
  servers = await api.listServers();
  $('#dashboardServerCount').textContent = servers.length;
  const list = $('#serverList');
  if (!servers.length) {
    list.innerHTML = '<div class="card" style="color:var(--muted)">还没有服务器，点击下方按钮添加</div>';
    return;
  }
  list.innerHTML = servers.map((s) => {
    const time = s.lastDeployAt ? new Date(s.lastDeployAt).toLocaleString('zh-CN') : '';
    const statusClass = s.status === '已部署' ? 'deployed' : s.status === '部署失败' ? 'error' : 'pending';
    return `
    <div class="server-card">
      <div>
        <div class="name">${esc(s.name)}</div>
        <div class="host">${esc(s.host)}:${s.port || 22} · ${esc(s.username)} · ${esc(s.exchange || 'binance')}${time ? ' · 部署于 ' + time : ''}</div>
      </div>
      <div class="server-actions">
        <span class="status ${statusClass}">${esc(s.status || '未部署')}</span>
        <button class="btn btn-ghost btn-sm" onclick="editServer('${s.id}')">编辑</button>
        <button class="btn btn-danger btn-sm" onclick="delServer('${s.id}')">删除</button>
      </div>
    </div>`;
  }).join('');
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
      <h3>3. WebUI 登录账号（用于软件内嵌 WebUI 登录）</h3>
      <div class="grid-2">
        <div><label>用户名</label><input id="d_apiuser" value="ckquant" placeholder="WebUI 登录用户名"></div>
        <div><label>密码</label><input id="d_apipass" type="password" placeholder="留空将自动生成高强度密码"></div>
      </div>
      <p style="color:var(--muted);font-size:12px;margin-top:4px">💡 这些将写入 config.json 的 api_server 配置，内嵌 WebUI 时自动登录，无需手动输入</p>
    </div>
    <div class="card">
      <h3>4. Telegram（可选）</h3>
      <div class="grid-2">
        <div><label>Bot Token</label><input id="d_tgtoken" placeholder="BotFather 获取的 token"></div>
        <div><label>Chat ID</label><input id="d_tgchat" placeholder="你的 Telegram ID"></div>
      </div>
    </div>
    <div class="card">
      <h3>5. 策略与配置</h3>
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
      <h3>6. 部署</h3>
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
    apiUsername: $('#d_apiuser').value.trim() || 'ckquant',
    apiPassword: $('#d_apipass').value.trim(),
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
  const sel = $('#m_server');
  sel.innerHTML = deployed.length
    ? deployed.map((s) => `<option value="${s.id}">${esc(s.name)}</option>`).join('')
    : '<option value="">暂无已部署的服务器（请先部署）</option>';

  $('#m_start').onclick = async () => {
    const sid = sel.value;
    if (!sid) { toast('请选择服务器'); return; }
    $('#logWindow').innerHTML = '<div class="log-line info">连接日志中...</div>';
    api.onLogData(({ serverId, data }) => {
      if (serverId !== sid) return;
      const div = document.createElement('div');
      div.className = 'log-line info';
      div.textContent = data;
      $('#logWindow').appendChild(div);
      $('#logWindow').scrollTop = $('#logWindow').scrollHeight;
    });
    const r = await api.startLogs(sid);
    if (!r.ok) { $('#logWindow').innerHTML = `<div class="log-line err">${esc(r.error)}</div>`; }
  };

  // 操作按钮
  const bindAction = (id, action, label) => {
    const btn = $(id);
    btn.onclick = async () => {
      const sid = sel.value;
      if (!sid) { toast('请选择服务器'); return; }
      btn.disabled = true;
      btn.textContent = label + '...';
      const r = await api.robotAction(sid, action);
      btn.disabled = false;
      btn.textContent = label;
      toast(r.ok ? `✅ ${label}成功` : `❌ ${r.error || '操作失败'}`);
    };
  };
  bindAction('#m_restart', 'restart', '🔄 重启机器人');
  bindAction('#m_stop', 'stop', '⏹ 停止机器人');
  bindAction('#m_startbot', 'start', '▶ 启动机器人');
  bindAction('#m_reload', 'reload', '♻️ 重载配置');

  // 配置编辑器
  $('#m_editcfg').onclick = async () => {
    const sid = sel.value;
    if (!sid) { toast('请选择服务器'); return; }
    const r = await api.readConfig(sid);
    if (!r.ok) { toast('❌ ' + (r.error || '读取失败')); return; }
    $('#cfgEditor').value = r.content;
    $('#cfgEditorWrap').style.display = 'block';
  };
  $('#cfgSave').onclick = async () => {
    const sid = sel.value;
    const content = $('#cfgEditor').value;
    try { JSON.parse(content); } catch (e) { toast('❌ 配置不是合法 JSON: ' + e.message); return; }
    const r = await api.saveConfig(sid, content);
    toast(r.ok ? '✅ 配置已保存并重载' : '❌ ' + (r.error || '保存失败'));
    if (r.ok) $('#cfgEditorWrap').style.display = 'none';
  };
  $('#cfgCancel').onclick = () => { $('#cfgEditorWrap').style.display = 'none'; };

  // 策略编辑器
  let currentStrategyFile = null;
  $('#m_editstrategy').onclick = async () => {
    const sid = sel.value;
    if (!sid) { toast('请选择服务器'); return; }
    const r = await api.listStrategies(sid);
    if (!r.ok) { toast('❌ ' + (r.error || '读取失败')); return; }
    const files = r.files || [];
    const opt = files.map((f) => `<option value="${esc(f)}">${esc(f)}</option>`).join('');
    $('#strategySelect').innerHTML = opt || '<option value="">（无策略文件）</option>';
    $('#strategyEditor').value = '';
    currentStrategyFile = null;
    $('#strategyEditorWrap').style.display = 'block';
  };
  $('#strategyLoad').onclick = async () => {
    const sid = sel.value;
    const fname = $('#strategySelect').value;
    if (!sid || !fname) { toast('请选择服务器和策略'); return; }
    const r = await api.readStrategy(sid, fname);
    if (!r.ok) { toast('❌ ' + (r.error || '读取失败')); return; }
    $('#strategyEditor').value = r.content;
    currentStrategyFile = fname;
    toast(`✅ 已加载 ${fname}`);
  };
  $('#strategySave').onclick = async () => {
    const sid = sel.value;
    const fname = currentStrategyFile || $('#strategySelect').value;
    const content = $('#strategyEditor').value;
    if (!sid || !fname) { toast('请先选择策略'); return; }
    if (!content.trim()) { toast('❌ 策略内容不能为空'); return; }
    const r = await api.saveStrategy(sid, fname, content);
    toast(r.ok ? '✅ 策略已保存并重载' : '❌ ' + (r.error || '保存失败'));
    if (r.ok) $('#strategyEditorWrap').style.display = 'none';
  };
  $('#strategyCancel').onclick = () => { $('#strategyEditorWrap').style.display = 'none'; };
}

// ============ WebUI（软件内嵌） ============
async function renderWebUI() {
  const deployed = servers.filter((s) => s.status === '已部署');
  const sel = $('#w_server');
  sel.innerHTML = deployed.length
    ? deployed.map((s) => `<option value="${s.id}">${esc(s.name)}</option>`).join('')
    : '<option value="">暂无已部署的服务器</option>';

  api.onTunnelError(({ serverId, error }) => {
    toast('❌ WebUI 隧道错误: ' + error);
    $('#webuiFrameWrap').style.display = 'none';
  });

  const btn = $('#webuiOpenBtn');
  btn.onclick = async () => {
    const sid = sel.value;
    if (!sid) { toast('请选择服务器'); return; }
    btn.disabled = true;
    btn.textContent = '⏳ 连接中...';
    const r = await api.startTunnel(sid);
    if (!r.ok) {
      btn.disabled = false;
      btn.textContent = '🔗 连接 WebUI';
      toast('❌ ' + (r.error || '连接失败'));
      return;
    }
    // 获取自动登录凭据
    const cred = await api.getCredentials(sid);
    if (!cred.ok) {
      btn.disabled = false;
      btn.textContent = '🔗 连接 WebUI';
      toast('❌ ' + (cred.error || '无法读取 WebUI 登录凭据'));
      return;
    }
    $('#webuiFrameWrap').style.display = 'block';
    const view = document.getElementById('webuiView');
    const url = `http://127.0.0.1:${r.localPort}`;
    const loginUrl = JSON.stringify(url);
    const loginUser = JSON.stringify(cred.apiUsername);
    const loginPassword = JSON.stringify(cred.apiPassword);

    // 加载 WebUI
    view.src = url;
    toast('✅ WebUI 已连接，正在自动登录...');

    // dom-ready 后注入自动登录脚本（用部署时保存的凭据）
    const doAutoLogin = () => {
      try {
        view.executeJavaScript(`
          (() => {
            const tryFill = () => {
              // 找登录弹窗输入框（id: url-input / username / password）
              const urlInput = document.querySelector('#url-input');
              const userInput = document.querySelector('input[type="text"]:not(#url-input)') ||
                                document.querySelectorAll('input')[1];
              const passInput = document.querySelector('input[type="password"]');
              const loginBtn = [...document.querySelectorAll('button')].find(b =>
                /登录|login|connect/i.test(b.textContent || ''));
              if (urlInput && passInput) {
                const setVal = (el, v) => {
                  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                  setter.call(el, v);
                  el.dispatchEvent(new Event('input', { bubbles: true }));
                };
                setVal(urlInput, ${loginUrl});
                if (userInput) setVal(userInput, ${loginUser});
                setVal(passInput, ${loginPassword});
                if (loginBtn) loginBtn.click();
                return true;
              }
              return false;
            };
            // 轮询直到表单出现（最多 30 秒）
            let tries = 0;
            const timer = setInterval(() => {
              tries++;
              if (tryFill() || tries > 60) clearInterval(timer);
            }, 500);
          })();
        `);
      } catch (e) { console.log('自动登录注入失败:', e.message); }
    };
    view.addEventListener('dom-ready', doAutoLogin, { once: true });

    btn.disabled = false;
    btn.textContent = '🔗 连接 WebUI';
  };
}

// ============ AI 助手 ============
let currentChatSessionId = null;
let currentAIReply = null;
let pendingAIConfirmation = null;
let chatHistoryLoaded = false;

function scrollChatToBottom() {
  const box = $('#chatMessages');
  box.scrollTop = box.scrollHeight;
}

function setChatBusy(busy) {
  $('#chatSendBtn').disabled = busy;
  $('#chatSendBtn').textContent = busy ? '回答中…' : '发送';
  $('#chatInput').disabled = busy;
}

function addChatMessage(role, content, options = {}) {
  $('#chatEmpty')?.remove();
  const row = document.createElement('div');
  row.className = `message ${role === 'user' ? 'user' : 'assistant'}`;
  if (options.replyId) row.dataset.replyId = options.replyId;
  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.textContent = role === 'user' ? '我' : 'K';
  const body = document.createElement('div');
  body.className = 'message-body';
  body.textContent = content || (options.streaming ? '正在思考…' : '');
  row.append(avatar, body);
  $('#chatMessages').appendChild(row);
  scrollChatToBottom();
  return body;
}

function addToolCard(payload) {
  let card = [...document.querySelectorAll('.tool-card')].reverse().find((node) =>
    node.dataset.replyId === payload.replyId && node.dataset.tool === payload.tool && !node.dataset.finished);
  if (!card) {
    card = document.createElement('div');
    card.className = 'tool-card';
    card.dataset.replyId = payload.replyId || '';
    card.dataset.tool = payload.tool || '';
    $('#chatMessages').appendChild(card);
  }
  const labels = { robot_status: '查询机器人状态', robot_logs: '读取机器人日志', backtest_list: '读取回测记录', robot_action: '执行机器人操作' };
  const status = payload.status === 'start' ? '处理中…' : payload.status === 'done' ? '已完成' : '失败';
  card.textContent = `${labels[payload.tool] || payload.tool} · ${status}`;
  card.classList.toggle('done', payload.status === 'done');
  card.classList.toggle('error', payload.status === 'error');
  if (payload.status !== 'start') card.dataset.finished = 'true';
  scrollChatToBottom();
}

async function loadChatHistory(force = false) {
  if (chatHistoryLoaded && !force) return;
  chatHistoryLoaded = true;
  const sessions = await api.getChatHistory();
  if (!sessions.ok || !sessions.messages?.length) return;
  const latest = [...sessions.messages].sort((a, b) => String(b.updatedAt).localeCompare(String(a.updatedAt)))[0];
  currentChatSessionId = latest.sessionId;
  const result = await api.getChatHistory(currentChatSessionId);
  if (!result.ok) return;
  $('#chatMessages').innerHTML = '';
  for (const message of result.messages || []) addChatMessage(message.role, message.content);
}

async function sendChatMessage(text) {
  const message = String(text ?? $('#chatInput').value).trim();
  if (!message || currentAIReply) return;
  addChatMessage('user', message);
  $('#chatInput').value = '';
  setChatBusy(true);
  const body = addChatMessage('assistant', '', { streaming: true });
  const result = await api.chat(message, currentChatSessionId);
  if (!result.ok) {
    body.textContent = `无法发送：${result.error || '未知错误'}`;
    setChatBusy(false);
    return;
  }
  currentChatSessionId = result.sessionId;
  currentAIReply = { replyId: result.replyId, body, content: '' };
  body.parentElement.dataset.replyId = result.replyId;
}

$('#chatSendBtn').addEventListener('click', () => sendChatMessage());
$('#chatInput').addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendChatMessage(); }
});
document.querySelectorAll('.quick-prompt').forEach((button) => button.addEventListener('click', () => sendChatMessage(button.textContent)));
$('#clearChatBtn').addEventListener('click', async () => {
  if (currentAIReply) { toast('请等待当前回答完成'); return; }
  await api.clearChat(currentChatSessionId);
  currentChatSessionId = null;
  chatHistoryLoaded = true;
  $('#chatMessages').innerHTML = '<div class="chat-empty" id="chatEmpty"><div style="font-size:34px">💬</div><h3 style="color:var(--text);margin-top:10px">对话已清空</h3><p>可以开始一个新问题。</p></div>';
});

api.onAIStream((payload) => {
  if (!currentAIReply || payload.replyId !== currentAIReply.replyId) return;
  currentAIReply.content += payload.delta || '';
  currentAIReply.body.textContent = currentAIReply.content;
  scrollChatToBottom();
});
api.onAITool((payload) => addToolCard(payload));
api.onAIDone((payload) => {
  if (!currentAIReply || payload.replyId !== currentAIReply.replyId) return;
  currentAIReply.body.textContent = payload.final || currentAIReply.content || '操作已处理。';
  currentAIReply = null;
  setChatBusy(false);
  scrollChatToBottom();
});
api.onAIError((payload) => {
  if (!currentAIReply || payload.replyId !== currentAIReply.replyId) return;
  currentAIReply.body.textContent = `无法完成：${payload.error || '未知错误'}`;
  currentAIReply = null;
  setChatBusy(false);
  scrollChatToBottom();
});
api.onAIConfirmation((payload) => {
  pendingAIConfirmation = payload;
  $('#aiConfirmSummary').textContent = `${payload.action?.summary || 'AI 请求执行操作'}（30 秒内确认）`;
  $('#aiConfirmBar').classList.add('show');
});

async function answerAIConfirmation(approved) {
  if (!pendingAIConfirmation) return;
  await api.confirmAIAction(pendingAIConfirmation.confirmationId, approved);
  pendingAIConfirmation = null;
  $('#aiConfirmBar').classList.remove('show');
}
$('#aiApproveBtn').addEventListener('click', () => answerAIConfirmation(true));
$('#aiRejectBtn').addEventListener('click', () => answerAIConfirmation(false));

// ============ AI 设置 ============
async function loadAISettings() {
  const result = await api.getAISettings();
  if (!result.ok) { $('#aiConnectionStatus').textContent = result.error || '读取设置失败'; return; }
  const settings = result.settings;
  $('#aiBaseUrl').value = settings.baseUrl || '';
  $('#aiModel').value = settings.model || '';
  $('#aiTemperature').value = settings.temperature ?? 0.3;
  $('#aiMaxTokens').value = settings.maxTokens ?? 4096;
  $('#aiApiKey').value = '';
  $('#aiKeyStatus').textContent = settings.hasKey ? 'API Key 已使用 Windows 系统加密保存；留空不会修改。' : 'API Key 尚未配置';
  $('#aiConnectionStatus').textContent = settings.testedAt ? `上次连接成功：${new Date(settings.testedAt).toLocaleString('zh-CN')} · ${settings.lastLatencyMs || '-'} ms` : '';
}

$('#saveAISettingsBtn').addEventListener('click', async () => {
  const button = $('#saveAISettingsBtn');
  button.disabled = true;
  const result = await api.saveAISettings({
    baseUrl: $('#aiBaseUrl').value.trim(), model: $('#aiModel').value.trim(), apiKey: $('#aiApiKey').value.trim(),
    temperature: Number($('#aiTemperature').value), maxTokens: Number($('#aiMaxTokens').value),
  });
  button.disabled = false;
  if (!result.ok) { $('#aiConnectionStatus').textContent = `保存失败：${result.error}`; return; }
  toast('AI 设置已保存');
  await loadAISettings();
});

$('#testAIConnectionBtn').addEventListener('click', async () => {
  const button = $('#testAIConnectionBtn');
  button.disabled = true;
  $('#aiConnectionStatus').textContent = '正在测试模型连接…';
  const result = await api.testAIConnection();
  button.disabled = false;
  $('#aiConnectionStatus').textContent = result.ok ? `连接成功 · ${result.model} · ${result.latencyMs} ms` : `连接失败：${result.error || '未知错误'}`;
});

$('#loadAIModelsBtn').addEventListener('click', async () => {
  const button = $('#loadAIModelsBtn');
  button.disabled = true;
  const result = await api.listAIModels();
  button.disabled = false;
  if (!result.ok || !result.models?.length) { $('#aiConnectionStatus').textContent = result.error || '服务商未提供模型列表，请手动填写模型名称。'; return; }
  $('#aiModelList').innerHTML = '';
  for (const model of result.models) {
    const option = document.createElement('option');
    option.value = model;
    $('#aiModelList').appendChild(option);
  }
  $('#aiConnectionStatus').textContent = `已获取 ${result.models.length} 个模型，可在模型名称中选择。`;
});

// ============ 初始化 ============
(async () => {
  const status = await api.getLicenseStatus();
  $('#machineCode').textContent = status.machineCode;
  if (status.valid) enterLicensedApp(status);
  else $('#loginPage').classList.add('show');
})();
