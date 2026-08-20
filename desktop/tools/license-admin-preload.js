const { contextBridge, ipcRenderer, clipboard } = require('electron');

contextBridge.exposeInMainWorld('licenseAdmin', {
  status: () => ipcRenderer.invoke('admin:status'),
  issue: (machineCode, customer) => ipcRenderer.invoke('admin:issue', { machineCode, customer }),
  copy: (text) => clipboard.writeText(String(text || '')),
});
