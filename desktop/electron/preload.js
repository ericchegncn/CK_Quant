// CK Quant Desktop - 预加载脚本（安全桥接）
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('ckQuant', {
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
});
