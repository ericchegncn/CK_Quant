// CK Quant Desktop - 预加载脚本（安全桥接）
const { contextBridge, ipcRenderer } = require('electron');
const { clipboard } = require('electron');

contextBridge.exposeInMainWorld('ckQuant', {
  // 终身授权
  getLicenseStatus: () => ipcRenderer.invoke('license:status'),
  getMachineCode: () => ipcRenderer.invoke('license:machineCode'),
  activateLicense: (code) => ipcRenderer.invoke('license:activate', { code }),
  removeLicense: () => ipcRenderer.invoke('license:remove'),
  copyText: (text) => clipboard.writeText(String(text || '')),

  // 认证
  register: (username, password) => ipcRenderer.invoke('auth:register', { username, password }),
  login: (username, password) => ipcRenderer.invoke('auth:login', { username, password }),
  logout: () => ipcRenderer.invoke('auth:logout'),
  getSession: () => ipcRenderer.invoke('auth:session'),
  getPlans: () => ipcRenderer.invoke('plans:list'),

  // 服务器管理
  listServers: () => ipcRenderer.invoke('server:list'),
  saveServer: (data) => ipcRenderer.invoke('server:save', data),
  deleteServer: (id) => ipcRenderer.invoke('server:delete', id),
  getServer: (id) => ipcRenderer.invoke('server:get', id),

  // 部署
  deploy: (serverId, config) => ipcRenderer.invoke('deploy:run', { serverId, config }),
  disconnect: (serverId) => ipcRenderer.invoke('deploy:disconnect', serverId),

  // 机器人操作
  robotAction: (serverId, action) => ipcRenderer.invoke('robot:action', { serverId, action }),
  readConfig: (serverId) => ipcRenderer.invoke('config:read', serverId),
  saveConfig: (serverId, content) => ipcRenderer.invoke('config:save', { serverId, content }),

  // 策略编辑
  listStrategies: (serverId) => ipcRenderer.invoke('strategy:list', serverId),
  readStrategy: (serverId, filename) => ipcRenderer.invoke('strategy:read', { serverId, filename }),
  saveStrategy: (serverId, filename, content) => ipcRenderer.invoke('strategy:save', { serverId, filename, content }),

  // 日志
  startLogs: (serverId) => ipcRenderer.invoke('logs:start', serverId),
  onLog: (cb) => ipcRenderer.on('deploy:log', (e, d) => cb(d)),
  onLogData: (cb) => ipcRenderer.on('logs:data', (e, d) => cb(d)),

  // 隧道（WebUI 内嵌）
  startTunnel: (serverId) => ipcRenderer.invoke('tunnel:start', serverId),
  stopTunnel: (serverId) => ipcRenderer.invoke('tunnel:stop', serverId),
  getCredentials: (serverId) => ipcRenderer.invoke('webui:getCredentials', serverId),
  onTunnelError: (cb) => ipcRenderer.on('tunnel:error', (e, d) => cb(d)),

  // AI 助手与 BYOK 设置
  getAISettings: () => ipcRenderer.invoke('ai:getSettings'),
  saveAISettings: (settings) => ipcRenderer.invoke('ai:saveSettings', settings),
  testAIConnection: () => ipcRenderer.invoke('ai:testConnection'),
  listAIModels: () => ipcRenderer.invoke('ai:listModels'),
  chat: (message, sessionId) => ipcRenderer.invoke('ai:chat', { message, sessionId }),
  getChatHistory: (sessionId) => ipcRenderer.invoke('ai:history', { sessionId }),
  clearChat: (sessionId) => ipcRenderer.invoke('ai:clear', { sessionId }),
  confirmAIAction: (confirmationId, approved) => ipcRenderer.invoke('ai:confirm', { confirmationId, approved }),
  onAIStream: (cb) => subscribe('ai:stream', cb),
  onAITool: (cb) => subscribe('ai:tool', cb),
  onAIDone: (cb) => subscribe('ai:done', cb),
  onAIError: (cb) => subscribe('ai:error', cb),
  onAIConfirmation: (cb) => subscribe('ai:requireConfirm', cb),

  // 回测中心
  submitBacktest: (input) => ipcRenderer.invoke('backtest:submit', input),
  listBacktests: (limit) => ipcRenderer.invoke('backtest:list', { limit }),
  getBacktest: (jobId) => ipcRenderer.invoke('backtest:get', { jobId }),
  cancelBacktest: (jobId) => ipcRenderer.invoke('backtest:cancel', { jobId }),
  compareBacktests: (jobIds) => ipcRenderer.invoke('backtest:compare', { jobIds }),
  onBacktestProgress: (cb) => subscribe('backtest:progress', cb),
  onBacktestDone: (cb) => subscribe('backtest:done', cb),
  onBacktestFailed: (cb) => subscribe('backtest:failed', cb),

  // 本地策略库（私有代码仅保存在本机应用数据目录）
  listLocalStrategies: () => ipcRenderer.invoke('strategy:localList'),
  readLocalStrategy: (name) => ipcRenderer.invoke('strategy:localRead', { name }),
  saveLocalStrategy: (input) => ipcRenderer.invoke('strategy:localSave', input),
  deleteLocalStrategy: (name) => ipcRenderer.invoke('strategy:localDelete', { name }),
  importLocalStrategy: (locked) => ipcRenderer.invoke('strategy:localImport', { locked }),
  validateLocalStrategy: (name, code, strictTemplate) => ipcRenderer.invoke('strategy:validate', { name, code, strictTemplate }),
  setLocalStrategyStatus: (name, status) => ipcRenderer.invoke('strategy:setStatus', { name, status }),

  // 监控巡检、诊断和受控自愈
  getMonitorOverview: () => ipcRenderer.invoke('monitor:overview'),
  inspectRobots: () => ipcRenderer.invoke('monitor:inspect'),
  diagnoseRobot: (serverId) => ipcRenderer.invoke('ops:diag', { serverId }),
  getOpsReport: () => ipcRenderer.invoke('ops:report'),
  getOpsSettings: () => ipcRenderer.invoke('ops:getSettings'),
  saveOpsSettings: (input) => ipcRenderer.invoke('ops:saveSettings', input),
  onMonitorUpdate: (cb) => subscribe('monitor:update', cb),
  onMonitorAlert: (cb) => subscribe('monitor:alert', cb),
});

function subscribe(channel, callback) {
  const listener = (_event, payload) => callback(payload);
  ipcRenderer.on(channel, listener);
  return () => ipcRenderer.removeListener(channel, listener);
}
