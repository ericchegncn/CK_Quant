const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { parseResultFile } = require('./parser');
const { evaluate } = require('./eval');

const TIMEFRAMES = new Set(['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '1d']);

function now() { return new Date().toISOString(); }

function validateSubmit(input = {}) {
  const strategy = String(input.strategy || '').trim();
  if (!/^[A-Za-z_][A-Za-z0-9_]{0,127}$/.test(strategy)) throw new Error('策略名称只能包含字母、数字和下划线，且不能以数字开头');
  const timeframe = String(input.timeframe || '15m');
  if (!TIMEFRAMES.has(timeframe)) throw new Error('不支持该时间周期');
  const timerange = String(input.timerange || '').trim();
  if (timerange && !/^\d{8}(?:-\d{0,8})?$/.test(timerange)) throw new Error('回测区间格式应为 20240101-20260101');
  const configPath = String(input.configPath || '/CK_Quant/user_data/config.json').trim();
  if (!/^\/CK_Quant\/user_data\/[A-Za-z0-9_.\/-]+\.json$/.test(configPath) || configPath.includes('..')) throw new Error('配置文件必须位于容器 /CK_Quant/user_data 下');
  const container = String(input.container || 'CK_Quant').trim();
  if (!/^[A-Za-z0-9_.-]{1,128}$/.test(container)) throw new Error('Docker 容器名称不合法');
  const pairs = [...new Set((Array.isArray(input.pairs) ? input.pairs : []).map((pair) => String(pair || '').trim()).filter(Boolean))];
  if (pairs.length > 100 || pairs.some((pair) => !/^[A-Z0-9._-]+\/[A-Z0-9._-]+(?::[A-Z0-9._-]+)?$/.test(pair))) {
    throw new Error('交易对列表不合法');
  }
  return {
    strategy, timeframe, timerange, configPath, container,
    fee: Math.max(0, Math.min(0.01, Number(input.fee ?? 0.0004))),
    slippage: Math.max(0, Math.min(0.02, Number(input.slippage ?? 0.0005))),
    detail1m: Boolean(input.detail1m), pairs,
  };
}

function runDocker(args, onLine = () => {}, childRef = () => {}) {
  return new Promise((resolve, reject) => {
    const child = spawn('docker', args, { windowsHide: true, shell: false });
    childRef(child);
    let stdout = '';
    let stderr = '';
    const consume = (kind) => (chunk) => {
      const text = chunk.toString();
      if (kind === 'stdout') stdout += text; else stderr += text;
      for (const line of text.split(/\r?\n/).filter(Boolean)) onLine(line, kind);
    };
    child.stdout.on('data', consume('stdout'));
    child.stderr.on('data', consume('stderr'));
    child.on('error', (error) => reject(Object.assign(error, { stdout, stderr })));
    child.on('close', (code, signal) => resolve({ code, signal, stdout, stderr }));
  });
}

class BacktestService {
  constructor({ store, dataDir, send, runner = runDocker, strategyResolver = () => null }) {
    this.store = store;
    this.dataDir = dataDir;
    this.send = send;
    this.runner = runner;
    this.strategyResolver = strategyResolver;
    this.running = null;
    this.pumping = false;
    this.waiters = new Map();
    fs.mkdirSync(path.join(dataDir, 'results'), { recursive: true });
    this.recoverInterrupted();
  }

  load() { return this.store.read('jobs', { _schema: 1, jobs: [] }); }

  update(jobId, patch) {
    let updated;
    this.store.update('jobs', { _schema: 1, jobs: [] }, (data) => {
      const job = data.jobs.find((item) => item.jobId === jobId);
      if (!job) return data;
      Object.assign(job, typeof patch === 'function' ? patch(job) : patch);
      updated = { ...job };
      return data;
    });
    return updated;
  }

  recoverInterrupted() {
    this.store.update('jobs', { _schema: 1, jobs: [] }, (data) => {
      for (const job of data.jobs) {
        if (job.status === 'running') {
          job.status = 'failed';
          job.endedAt = now();
          job.error = '软件在回测期间退出，任务已安全终止；请重新提交。';
        }
      }
      return data;
    });
  }

  submit(input) {
    let options;
    try { options = validateSubmit(input); }
    catch (error) { return { ok: false, error: error.message, code: 'BACKTEST_INVALID' }; }
    const jobId = `job_${Date.now()}_${crypto.randomBytes(3).toString('hex')}`;
    const job = {
      jobId, strategy: options.strategy, status: 'queued', createdAt: now(),
      timeframe: options.timeframe, timerange: options.timerange, configPath: options.configPath,
      container: options.container, fee: options.fee, slippage: options.slippage, detail1m: options.detail1m,
      pairs: options.pairs,
      stages: { download: 0, run: 0, parse: 0, eval: 0 }, resultRef: null, evalResult: null, error: null,
    };
    this.store.update('jobs', { _schema: 1, jobs: [] }, (data) => { data.jobs.push(job); return data; });
    this.store.appendAudit({ actor: 'user', action: 'backtest.submit', params: { strategy: job.strategy, timerange: job.timerange, timeframe: job.timeframe }, result: 'queued', jobId });
    queueMicrotask(() => this.pump());
    return { ok: true, jobId };
  }

  list(limit = 50) {
    const jobs = this.load().jobs || [];
    return jobs.slice(-Math.max(1, Math.min(200, Number(limit) || 50))).reverse();
  }

  get(jobId) {
    const job = this.load().jobs.find((item) => item.jobId === jobId);
    if (!job) return null;
    if (job.resultRef) {
      try { return { ...job, result: JSON.parse(fs.readFileSync(path.join(this.dataDir, job.resultRef), 'utf8')) }; }
      catch (_) { return job; }
    }
    return job;
  }

  cancel(jobId) {
    const job = this.load().jobs.find((item) => item.jobId === jobId);
    if (!job) return { ok: false, error: '回测任务不存在' };
    if (!['queued', 'running'].includes(job.status)) return { ok: false, error: '该任务已经结束，不能取消' };
    if (this.running?.jobId === jobId && this.running.child) this.running.child.kill();
    this.update(jobId, { status: 'cancelled', endedAt: now(), error: null });
    this.resolveWaiters(jobId);
    this.store.appendAudit({ actor: 'user', action: 'backtest.cancel', params: {}, result: 'ok', jobId });
    return { ok: true };
  }

  wait(jobId) {
    const current = this.get(jobId);
    if (!current) return Promise.reject(new Error('回测任务不存在'));
    if (['done', 'failed', 'cancelled'].includes(current.status)) return Promise.resolve(current);
    return new Promise((resolve) => {
      const list = this.waiters.get(jobId) || [];
      list.push(resolve); this.waiters.set(jobId, list);
    });
  }

  resolveWaiters(jobId) {
    const job = this.get(jobId);
    for (const resolve of this.waiters.get(jobId) || []) resolve(job);
    this.waiters.delete(jobId);
  }

  progress(job, stage, progress, message) {
    this.update(job.jobId, (current) => ({ stages: { ...current.stages, [stage]: progress } }));
    this.send('backtest:progress', { jobId: job.jobId, strategy: job.strategy, stage, progress, message, ts: now() });
  }

  async pump() {
    if (this.pumping) return;
    this.pumping = true;
    try {
      while (true) {
        const job = this.load().jobs.find((item) => item.status === 'queued');
        if (!job) break;
        await this.run(job);
      }
    } finally { this.pumping = false; }
  }

  async run(job) {
    this.update(job.jobId, { status: 'running', startedAt: now(), error: null });
    this.running = { jobId: job.jobId, child: null };
    try {
      this.progress(job, 'download', 1, '使用容器中已有历史数据；缺少数据时 Freqtrade 会明确报错');
      const localStrategy = this.strategyResolver(job.strategy);
      if (localStrategy?.code) {
        const runtimeDirectory = path.join(this.dataDir, 'runtime');
        fs.mkdirSync(runtimeDirectory, { recursive: true });
        const localFile = path.join(runtimeDirectory, `${job.strategy}.py`);
        fs.writeFileSync(localFile, localStrategy.code, { encoding: 'utf8', mode: 0o600 });
        const copiedStrategy = await this.runner(['cp', localFile, `${job.container}:/CK_Quant/user_data/strategies/${job.strategy}.py`]);
        if (copiedStrategy.code !== 0) throw new Error(`无法把本机私有策略同步到回测容器：${copiedStrategy.stderr.slice(-500)}`);
      }
      const outputBase = `/CK_Quant/user_data/backtest_results/desktop_${job.jobId}`;
      const args = ['exec', job.container, 'freqtrade', 'backtesting', '--config', job.configPath, '--strategy', job.strategy,
        '--timeframe', job.timeframe, '--fee', String(job.fee), '--export', 'trades', '--export-filename', outputBase];
      if (job.timerange) args.push('--timerange', job.timerange);
      if (job.detail1m && job.timeframe !== '1m') args.push('--timeframe-detail', '1m');
      if (job.pairs?.length) args.push('--pairs', ...job.pairs);
      let lineCount = 0;
      const executed = await this.runner(args, (line) => {
        lineCount += 1;
        this.progress(job, 'run', Math.min(0.95, 0.08 + lineCount / 350), line.slice(0, 300));
      }, (child) => { if (this.running?.jobId === job.jobId) this.running.child = child; });
      if (this.get(job.jobId)?.status === 'cancelled') return;
      if (executed.code !== 0) throw new Error((executed.stderr || executed.stdout || 'Freqtrade 回测失败').slice(-1500));
      this.progress(job, 'run', 1, 'Freqtrade 回测完成');

      const locate = await this.runner(['exec', job.container, 'sh', '-lc', `ls -1t ${outputBase}* 2>/dev/null | head -1`]);
      const remoteResult = locate.stdout.trim();
      if (!remoteResult) throw new Error('回测完成但没有找到导出结果');
      const extension = path.posix.extname(remoteResult) || '.zip';
      const localRaw = path.join(this.dataDir, 'results', `${job.jobId}.raw${extension}`);
      const copied = await this.runner(['cp', `${job.container}:${remoteResult}`, localRaw]);
      if (copied.code !== 0) throw new Error(`无法复制回测结果：${copied.stderr.slice(-500)}`);

      this.progress(job, 'parse', 0.3, '正在重新计算关键统计指标');
      const result = parseResultFile(localRaw, { ...job, jobId: job.jobId });
      this.progress(job, 'parse', 1, '统计指标解析完成');
      this.progress(job, 'eval', 0.4, '正在执行 G1-G10 确定性门禁');
      const resultRef = path.join('results', `${job.jobId}.json`);
      fs.writeFileSync(path.join(this.dataDir, resultRef), `${JSON.stringify(result, null, 2)}\n`, 'utf8');
      this.update(job.jobId, { status: 'done', endedAt: now(), resultRef, evalResult: result.evalResult, stages: { download: 1, run: 1, parse: 1, eval: 1 } });
      this.store.appendAudit({ actor: 'system', action: 'backtest.done', params: { strategy: job.strategy }, result: 'ok', jobId: job.jobId });
      this.send('backtest:done', { jobId: job.jobId, resultRef, evalResult: result.evalResult, ts: now() });
      this.resolveWaiters(job.jobId);
    } catch (error) {
      if (this.get(job.jobId)?.status !== 'cancelled') {
        this.update(job.jobId, { status: 'failed', endedAt: now(), error: error.message });
        this.store.appendAudit({ actor: 'system', action: 'backtest.failed', params: { strategy: job.strategy }, result: 'error', jobId: job.jobId });
        this.send('backtest:failed', { jobId: job.jobId, error: error.message, ts: now() });
        this.resolveWaiters(job.jobId);
      }
    } finally { this.running = null; }
  }

  compare(jobIds) {
    const jobs = [...new Set(jobIds || [])].slice(0, 10).map((id) => this.get(id)).filter((job) => job?.result);
    const metrics = [
      ['交易数', 'trades'], ['胜率', 'winRate'], ['每笔期望', 'expectedValue'], ['利润因子', 'profitFactor'],
      ['年化收益', 'annualReturn'], ['最大回撤', 'maxDrawdown'], ['Sharpe', 'sharpe'], ['门禁通过', 'evalResult.passed'],
    ];
    const valueAt = (object, key) => key.split('.').reduce((value, part) => value?.[part], object);
    return metrics.map(([label, key]) => ({ metric: label, values: Object.fromEntries(jobs.map((job) => [job.jobId, valueAt(job.result, key)])) }));
  }

  reevaluate(jobId, evidence = {}) {
    const job = this.get(jobId);
    if (!job?.result || !job.resultRef) return { ok: false, error: '回测结果不存在' };
    const evalResult = evaluate(job.result, evidence);
    const result = { ...job.result, evalResult };
    fs.writeFileSync(path.join(this.dataDir, job.resultRef), `${JSON.stringify(result, null, 2)}\n`, 'utf8');
    this.update(jobId, { evalResult });
    this.store.appendAudit({ actor: 'system', action: 'backtest.reevaluate', params: { evidence: Object.keys(evidence) }, result: evalResult.passed ? 'passed' : 'failed', jobId });
    return { ok: true, evalResult, result };
  }
}

module.exports = { BacktestService, validateSubmit, runDocker };
