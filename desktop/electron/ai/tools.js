const READ_TOOLS = [
  {
    type: 'function',
    function: {
      name: 'robot_status',
      description: '查询所有量化服务器和机器人当前真实状态。用户询问运行状态时必须调用。',
      parameters: { type: 'object', properties: {}, additionalProperties: false },
    },
  },
  {
    type: 'function',
    function: {
      name: 'robot_logs',
      description: '读取指定服务器机器人最近日志。',
      parameters: {
        type: 'object', required: ['serverId'], additionalProperties: false,
        properties: { serverId: { type: 'string' }, lines: { type: 'integer', minimum: 10, maximum: 500 } },
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'backtest_list',
      description: '列出最近的真实回测任务和状态。',
      parameters: { type: 'object', properties: { limit: { type: 'integer', minimum: 1, maximum: 50 } }, additionalProperties: false },
    },
  },
  {
    type: 'function',
    function: {
      name: 'robot_action',
      description: '重启、启动或停止机器人。该工具属于写操作，执行前软件会要求用户确认。',
      parameters: {
        type: 'object', required: ['serverId', 'action'], additionalProperties: false,
        properties: { serverId: { type: 'string' }, action: { type: 'string', enum: ['restart', 'start', 'stop', 'reload'] } },
      },
    },
  },
];

const WRITE_TOOLS = new Set(['robot_action']);

function clampLines(value) {
  return Math.max(10, Math.min(500, Number(value) || 100));
}

function createToolExecutor(ctx) {
  return async function execute(name, args) {
    if (name === 'robot_status') {
      const servers = ctx.getServers();
      const results = [];
      for (const server of servers) {
        const item = { id: server.id, name: server.name, host: server.host, savedStatus: server.status || '未知', state: 'unknown' };
        try {
          const ssh = await ctx.ensureConnection(server.id);
          if (!ssh) throw new Error('SSH 无法连接');
          const result = await ssh.exec("docker inspect -f '{{.State.Status}}|{{.RestartCount}}' CK_Quant 2>/dev/null", 20000);
          const [state, restartCount] = result.stdout.trim().split('|');
          item.state = state || 'not_found';
          item.restartCount = Number(restartCount) || 0;
        } catch (error) { item.error = error.message; }
        results.push(item);
      }
      return { ok: true, source: '实时 SSH + 本地服务器记录', robots: results };
    }
    if (name === 'robot_logs') {
      const serverId = String(args.serverId || '');
      if (!ctx.getServers().some((server) => server.id === serverId)) return { ok: false, error: '服务器不存在' };
      const ssh = await ctx.ensureConnection(serverId);
      if (!ssh) return { ok: false, error: 'SSH 无法连接' };
      const result = await ssh.exec(`docker logs --tail ${clampLines(args.lines)} CK_Quant 2>&1`, 30000);
      return { ok: result.code === 0, serverId, lines: result.stdout.slice(-30000), error: result.code ? result.stderr.slice(-500) : undefined };
    }
    if (name === 'backtest_list') {
      const jobs = ctx.store.read('jobs', { _schema: 1, jobs: [] }).jobs || [];
      return { ok: true, source: '本地 jobs.json', jobs: jobs.slice(-(Number(args.limit) || 10)).reverse() };
    }
    if (name === 'robot_action') return ctx.robotAction(String(args.serverId || ''), String(args.action || ''));
    return { ok: false, error: `未知工具: ${name}` };
  };
}

module.exports = { READ_TOOLS, WRITE_TOOLS, createToolExecutor };
