function now() { return new Date().toISOString(); }

const DEFAULT_SETTINGS = {
  _schema: 1,
  intervalMinutes: 5,
  autoHeal: false,
  dailyLossLimit: 0.10,
  drawdownLimit: 0.30,
  desktopNotifications: true,
};

function clamp(value, fallback, min, max) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.min(max, Math.max(min, number)) : fallback;
}

function safeJson(text, fallback = null) {
  try { return JSON.parse(String(text || '').trim()); } catch (_) { return fallback; }
}

function ratio(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  return Math.abs(number) > 1 ? number / 100 : number;
}

function redact(text) {
  return String(text || '')
    .replace(/(api[_ -]?key|secret|token|password)(["' :=]+)[^\s,"']+/gi, '$1$2[已隐藏]')
    .replace(/\b[A-Za-z0-9_-]{32,}\b/g, '[敏感内容已隐藏]')
    .slice(-30000);
}

function errorLines(logs) {
  const lines = redact(logs).split(/\r?\n/).filter((line) => /ERROR|CRITICAL|APIError|Timeout|InvalidKey|Invalid API-key/i.test(line));
  return lines.slice(-20);
}

function parseStats(text) {
  const data = safeJson(text, {});
  return { cpu: data.CPUPerc || data.CPU || null, memory: data.MemUsage || data.Mem || null };
}

function parseDisk(text) {
  const parts = String(text || '').trim().split(/\s+/);
  const percent = parts.find((part) => /^\d+%$/.test(part));
  return percent ? Number(percent.replace('%', '')) : null;
}

function extractProfit(profit, daily, openTrades) {
  const lastDaily = Array.isArray(daily?.data) ? daily.data.at(-1) : Array.isArray(daily) ? daily.at(-1) : null;
  return {
    totalProfit: Number(profit?.profit_all_coin ?? profit?.profit_closed_coin ?? 0) || 0,
    totalProfitRatio: ratio(profit?.profit_all_ratio ?? profit?.profit_all_percent),
    closedTrades: Number(profit?.closed_trade_count ?? profit?.trade_count ?? 0) || 0,
    openTrades: Array.isArray(openTrades) ? openTrades.length : 0,
    maxDrawdown: ratio(profit?.max_drawdown ?? profit?.max_drawdown_account),
    dailyProfit: Number(lastDaily?.abs_profit ?? lastDaily?.profit_abs ?? 0) || 0,
    dailyProfitRatio: ratio(lastDaily?.rel_profit ?? lastDaily?.profit_ratio),
  };
}

class OpsService {
  constructor({ store, getServers, ensureConnection, robotAction, send, notify = () => {}, wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms)) }) {
    this.store = store;
    this.getServers = getServers;
    this.ensureConnection = ensureConnection;
    this.robotAction = robotAction;
    this.send = send;
    this.notify = notify;
    this.wait = wait;
    this.timer = null;
    this.inspecting = null;
  }

  settings() { return { ...DEFAULT_SETTINGS, ...this.store.read('ops_settings', DEFAULT_SETTINGS) }; }

  saveSettings(input = {}) {
    const current = this.settings();
    const next = {
      ...current,
      intervalMinutes: Math.round(clamp(input.intervalMinutes, current.intervalMinutes, 1, 60)),
      autoHeal: Boolean(input.autoHeal),
      dailyLossLimit: clamp(input.dailyLossLimit, current.dailyLossLimit, 0.01, 0.50),
      drawdownLimit: clamp(input.drawdownLimit, current.drawdownLimit, 0.05, 0.80),
      desktopNotifications: input.desktopNotifications !== false,
      updatedAt: now(),
    };
    this.store.write('ops_settings', next);
    this.restartTimer();
    return next;
  }

  start() { this.restartTimer(); }
  stop() { if (this.timer) clearInterval(this.timer); this.timer = null; }

  restartTimer() {
    this.stop();
    const milliseconds = this.settings().intervalMinutes * 60 * 1000;
    this.timer = setInterval(() => this.inspectAll({ source: 'scheduled' }), milliseconds);
    this.timer.unref?.();
  }

  latest() { return this.store.read('ops_snapshot', { _schema: 1, generatedAt: null, robots: [] }); }

  async connect(serverId) {
    for (let attempt = 1; attempt <= 3; attempt += 1) {
      const ssh = await this.ensureConnection(serverId);
      if (ssh) return ssh;
      if (attempt < 3) await this.wait(10000);
    }
    return null;
  }

  async inspectServer(server) {
    const result = {
      robotId: `robot_${server.id}`, serverId: server.id, serverName: server.name, host: server.host,
      desiredState: server.desiredState || 'running', state: 'unknown', restartCount: 0,
      api: { state: 'unknown' }, errors: [], resources: {}, diskPercent: null, database: {}, profit: {}, inspectedAt: now(),
    };
    const ssh = await this.connect(server.id);
    if (!ssh) { result.error = 'SSH 连续三次无法连接；未执行任何自动操作'; return result; }
    const state = await ssh.exec("docker inspect -f '{{.State.Status}}|{{.RestartCount}}' CK_Quant 2>/dev/null", 20000);
    if (state.code === 0) {
      const [status, restarts] = state.stdout.trim().split('|');
      result.state = status || 'unknown'; result.restartCount = Number(restarts) || 0;
    } else result.state = 'not_found';

    const [logs, stats, disk, database] = await Promise.all([
      ssh.exec('docker logs --tail 200 CK_Quant 2>&1', 30000),
      ssh.exec("docker stats --no-stream --format '{{json .}}' CK_Quant 2>/dev/null", 20000),
      ssh.exec("df -P / | tail -1", 20000),
      ssh.exec("stat -c '%s|%Y' /root/CK_Quant/user_data/tradesv3.sqlite 2>/dev/null", 20000),
    ]);
    result.errors = errorLines(`${logs.stdout}\n${logs.stderr}`);
    result.resources = parseStats(stats.stdout);
    result.diskPercent = parseDisk(disk.stdout);
    const [bytes, modified] = database.stdout.trim().split('|');
    result.database = { sizeMB: Number(bytes) ? Number((Number(bytes) / 1048576).toFixed(2)) : null, modifiedAt: Number(modified) ? new Date(Number(modified) * 1000).toISOString() : null };

    if (server.apiUsername && server.apiPassword) {
      const port = Math.min(65535, Math.max(1, Number(server.apiPort) || 8080));
      const auth = Buffer.from(`${server.apiUsername}:${server.apiPassword}`).toString('base64');
      const header = `'Authorization: Basic ${auth}'`;
      const [ping, profit, openTrades, daily] = await Promise.all([
        ssh.exec(`curl -fsS -H ${header} http://127.0.0.1:${port}/api/v1/ping`, 15000),
        ssh.exec(`curl -fsS -H ${header} http://127.0.0.1:${port}/api/v1/profit`, 20000),
        ssh.exec(`curl -fsS -H ${header} http://127.0.0.1:${port}/api/v1/status`, 20000),
        ssh.exec(`curl -fsS -H ${header} 'http://127.0.0.1:${port}/api/v1/daily?timescale=1'`, 20000),
      ]);
      result.api = ping.code === 0 ? { state: 'ok' } : { state: 'error', error: redact(ping.stderr).slice(-300) };
      result.profit = extractProfit(safeJson(profit.stdout, {}), safeJson(daily.stdout, {}), safeJson(openTrades.stdout, []));
    } else result.api = { state: 'not_configured', error: '未保存 WebUI API 凭据' };
    return result;
  }

  async inspectAll({ source = 'manual' } = {}) {
    if (this.inspecting) return this.inspecting;
    this.inspecting = this.runInspection(source).finally(() => { this.inspecting = null; });
    return this.inspecting;
  }

  async runInspection(source) {
    const robots = [];
    for (const server of this.getServers()) {
      const snapshot = await this.inspectServer(server);
      robots.push(snapshot);
      this.send('monitor:update', { robot: snapshot, source, ts: now() });
    }
    const result = { _schema: 1, generatedAt: now(), source, robots };
    this.store.write('ops_snapshot', result);
    if (this.settings().autoHeal) await this.applyRules(result);
    return result;
  }

  runtimeState() { return this.store.read('ops_runtime', { _schema: 1, robots: {} }); }

  async applyRules(snapshot) {
    const settings = this.settings();
    const runtime = this.runtimeState();
    for (const robot of snapshot.robots) {
      const state = runtime.robots[robot.robotId] || { apiFailures: 0, lastRestartAt: null, alerts: {} };
      const minutesSinceRestart = state.lastRestartAt ? (Date.now() - Date.parse(state.lastRestartAt)) / 60000 : Infinity;
      let action = null;
      let rule = null;
      let reason = null;
      const invalidKey = robot.errors.some((line) => /InvalidKey|Invalid API-key|authentication/i.test(line));
      if (invalidKey && robot.desiredState !== 'stopped') { action = 'stop'; rule = 'H8'; reason = '检测到交易所 API Key 失效'; }
      else if (robot.profit.dailyProfitRatio != null && robot.profit.dailyProfitRatio < -settings.dailyLossLimit && robot.desiredState !== 'stopped') { action = 'stop'; rule = 'H4'; reason = `单日亏损超过 ${(settings.dailyLossLimit * 100).toFixed(1)}%`; }
      else if (robot.profit.maxDrawdown != null && robot.profit.maxDrawdown > settings.drawdownLimit && robot.desiredState !== 'stopped') { action = 'stop'; rule = 'H5'; reason = `最大回撤超过 ${(settings.drawdownLimit * 100).toFixed(1)}%`; }
      else if (['exited', 'restarting', 'not_found'].includes(robot.state) && robot.desiredState !== 'stopped' && minutesSinceRestart >= 10) { action = 'restart'; rule = 'H1'; reason = `容器状态 ${robot.state}`; }
      state.apiFailures = robot.api.state === 'error' ? state.apiFailures + 1 : 0;
      if (!action && robot.state === 'running' && state.apiFailures >= 3 && robot.desiredState !== 'stopped' && minutesSinceRestart >= 30) { action = 'restart'; rule = 'H2'; reason = 'API 连续三次无响应'; }
      if (robot.diskPercent != null && robot.diskPercent > 85) this.alert(robot, 'H6', `磁盘占用 ${robot.diskPercent}%`, 'warn', state);
      if (robot.errors.length >= 5) this.alert(robot, 'H3', `最近日志发现 ${robot.errors.length} 条错误`, 'warn', state);
      if (action) {
        this.store.appendAudit({ actor: 'system', action: `ops.${rule}.${action}`, params: { serverId: robot.serverId, reason }, result: 'started' });
        const result = await this.robotAction(robot.serverId, action);
        if (action === 'restart' && result.ok) state.lastRestartAt = now();
        this.alert(robot, rule, `${reason}；${result.ok ? `已自动${action === 'stop' ? '暂停' : '重启'}` : `处置失败：${result.error || '未知错误'}`}`, result.ok ? 'warn' : 'critical', state, true);
      }
      runtime.robots[robot.robotId] = state;
    }
    this.store.write('ops_runtime', runtime);
  }

  alert(robot, rule, message, level, state, force = false) {
    const previous = state.alerts[rule] ? Date.parse(state.alerts[rule]) : 0;
    const cooldown = rule === 'H3' ? 3600000 : 86400000;
    if (!force && Date.now() - previous < cooldown) return;
    state.alerts[rule] = now();
    const alert = { robotId: robot.robotId, serverId: robot.serverId, serverName: robot.serverName, rule, message, level, ts: now() };
    this.store.update('alerts', { _schema: 1, alerts: [] }, (data) => { data.alerts.push(alert); data.alerts = data.alerts.slice(-500); return data; });
    this.send('monitor:alert', alert);
    this.notify(alert);
  }

  diagnostic(serverId) {
    const robot = this.latest().robots.find((item) => item.serverId === serverId);
    if (!robot) return null;
    const facts = { containerState: robot.state, restartCount: robot.restartCount, apiState: robot.api.state, logTail: robot.errors, resources: robot.resources, diskPercent: robot.diskPercent, database: robot.database, profit: robot.profit };
    const summary = robot.error || (robot.state !== 'running' ? `机器人容器状态为 ${robot.state}` : robot.api.state !== 'ok' ? `机器人运行但 API 状态为 ${robot.api.state}` : robot.errors.length ? `机器人运行中，最近日志有 ${robot.errors.length} 条错误` : '机器人状态正常');
    const report = { robotId: robot.robotId, serverId, generatedAt: now(), summary, facts, suggestedActions: [] };
    if (robot.state !== 'running' && robot.desiredState !== 'stopped') report.suggestedActions.push({ action: 'restart', reason: '容器未运行', requiresConfirm: true });
    if (robot.api.state !== 'ok') report.suggestedActions.push({ action: 'checkCredentials', reason: 'API 无法验证', requiresConfirm: false });
    return report;
  }

  report() {
    const snapshot = this.latest();
    const running = snapshot.robots.filter((robot) => robot.state === 'running').length;
    const stopped = snapshot.robots.filter((robot) => robot.desiredState === 'stopped' || robot.state === 'exited').length;
    const totalProfit = snapshot.robots.reduce((sum, robot) => sum + (Number(robot.profit.totalProfit) || 0), 0);
    const dailyProfit = snapshot.robots.reduce((sum, robot) => sum + (Number(robot.profit.dailyProfit) || 0), 0);
    return { generatedAt: now(), robots: snapshot.robots.length, running, stopped, totalProfit, dailyProfit, items: snapshot.robots.map((robot) => ({ robotId: robot.robotId, serverName: robot.serverName, state: robot.state, profit: robot.profit })) };
  }
}

module.exports = { OpsService, DEFAULT_SETTINGS, safeJson, ratio, redact, errorLines, parseStats, parseDisk, extractProfit };
