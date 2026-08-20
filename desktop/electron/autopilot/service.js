const crypto = require('crypto');
const { generateVariants, generateRandomBaseline } = require('./variants');
const { researchMarket } = require('./research');

const ACTIVE = new Set(['RESEARCHING', 'GENERATING', 'BACKTESTING', 'EVALUATING', 'SIM_DEPLOYING', 'SIM_TRACKING', 'LIVE_TRACKING', 'IMPROVING']);
const TERMINAL = new Set(['COMPLETED', 'FAILED']);
const STAGE_PROGRESS = { RESEARCHING: 0.08, GENERATING: 0.20, BACKTESTING: 0.38, EVALUATING: 0.68, SIM_DEPLOYING: 0.78, SIM_TRACKING: 0.86, AWAITING_USER: 0.94, LIVE_TRACKING: 0.97, COMPLETED: 1 };

function now() { return new Date().toISOString(); }
function safeOptions(input = {}) {
  const count = Math.max(1, Math.min(5, Number(input.variantCount) || 3));
  return {
    template: String(input.template || '').trim(), variantCount: count,
    timerange: String(input.timerange || '20240101-').trim(),
    configPath: String(input.configPath || '/CK_Quant/user_data/config.json').trim(),
    container: String(input.container || 'CK_Quant').trim(),
    paperServerId: /^[A-Za-z0-9_-]{1,128}$/.test(String(input.paperServerId || '')) ? String(input.paperServerId) : '',
    detail1m: Boolean(input.detail1m), fee: Number(input.fee ?? 0.0004), slippage: Number(input.slippage ?? 0.0005),
  };
}

function splitTimerange(timerange, parts = 3, today = new Date()) {
  const match = String(timerange || '').match(/^(\d{8})-(\d{8})?$/);
  if (!match) return [];
  const parse = (value) => new Date(Date.UTC(Number(value.slice(0, 4)), Number(value.slice(4, 6)) - 1, Number(value.slice(6, 8))));
  const format = (date) => `${date.getUTCFullYear()}${String(date.getUTCMonth() + 1).padStart(2, '0')}${String(date.getUTCDate()).padStart(2, '0')}`;
  const start = parse(match[1]);
  const end = match[2] ? parse(match[2]) : new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()));
  const span = end.getTime() - start.getTime();
  if (!(span > parts * 86400000)) return [];
  return Array.from({ length: parts }, (_, index) => {
    const left = new Date(start.getTime() + Math.floor(span * index / parts));
    const right = new Date(start.getTime() + Math.floor(span * (index + 1) / parts));
    return `${format(left)}-${format(right)}`;
  });
}

function marketRegime(change) {
  if (!Number.isFinite(change)) return 'unknown';
  if (change >= 0.10) return 'bull';
  if (change <= -0.10) return 'bear';
  return 'range';
}

class AutopilotService {
  constructor({ store, send, backtests, strategies, research = researchMarket, variants = generateVariants, notify = async () => {}, deployPaper = async () => ({ ok: false, error: '未配置模拟盘部署器' }) }) {
    this.store = store; this.send = send; this.backtests = backtests; this.strategies = strategies;
    this.research = research; this.variants = variants; this.notify = notify; this.deployPaper = deployPaper;
    this.processing = false; this.pauseRequested = false;
    this.recoverInterrupted();
  }

  load() { return this.store.read('autopilot', { _schema: 1, current: null, runs: [] }); }
  current() { return this.load().current; }

  persist(run) {
    this.store.update('autopilot', { _schema: 1, current: null, runs: [] }, (data) => {
      data.current = TERMINAL.has(run.state) ? null : run;
      const index = data.runs.findIndex((item) => item.runId === run.runId);
      if (index >= 0) data.runs[index] = run; else data.runs.push(run);
      data.runs = data.runs.slice(-20);
      return data;
    });
  }

  recoverInterrupted() {
    const run = this.current();
    if (run && ACTIVE.has(run.state)) {
      run.pausedFrom = run.state; run.state = 'PAUSED'; run.updatedAt = now();
      run.current = { ...run.current, detail: '软件上次在流程运行中退出，现场已保留；请点击恢复', lastEvent: '安全暂停' };
      this.persist(run);
    }
  }

  event(run, state, detail, progress = STAGE_PROGRESS[state] ?? run.current?.progress ?? 0, artifact = null) {
    run.state = state; run.updatedAt = now();
    run.current = { stage: state.toLowerCase(), detail, progress, lastEvent: detail };
    run.history.push({ ts: run.updatedAt, state, detail });
    if (artifact) Object.assign(run.artifacts, artifact);
    this.persist(run);
    this.send('autopilot:event', { runId: run.runId, stage: run.current.stage, detail, progress, artifact, ts: run.updatedAt });
  }

  async checkpoint(run) {
    if (!this.pauseRequested) return false;
    run.pausedFrom = run.state; this.pauseRequested = false;
    this.event(run, 'PAUSED', '已在安全检查点暂停，回测结果和策略变体均已保留', run.current.progress);
    return true;
  }

  start(input = {}) {
    const existing = this.current();
    if (existing) return { ok: false, error: `已有流程处于 ${existing.state}，请先继续或结束它` };
    const options = safeOptions(input);
    const template = options.template ? this.strategies.read(options.template) : this.strategies.list().map((item) => this.strategies.read(item.name)).find((item) => item?.meta?.source === 'official');
    if (!template || template.meta.source !== 'official') return { ok: false, error: '一键研究只能使用内置的 Freqtrade 官方公开模板' };
    options.template = template.meta.name;
    const run = {
      runId: `auto_${Date.now()}_${crypto.randomBytes(2).toString('hex')}`, state: 'RESEARCHING', startedAt: now(), updatedAt: now(), endedAt: null,
      options, current: { stage: 'researching', detail: '准备读取本机行情', progress: 0.02, lastEvent: '流程已创建' },
      artifacts: { researchReport: null, strategies: [], backtestJobs: [], evalReport: null, paperRobotId: null, liveRobotId: null },
      history: [], awaitingUser: null, outcome: null,
    };
    this.persist(run); this.store.appendAudit({ actor: 'user', action: 'autopilot.start', params: { template: options.template, variantCount: options.variantCount }, result: 'ok', runId: run.runId });
    queueMicrotask(() => this.execute(run.runId));
    return { ok: true, runId: run.runId };
  }

  status() { return { ok: true, run: this.current() }; }
  history(limit = 20) { return { ok: true, runs: this.load().runs.slice(-Math.max(1, Math.min(20, Number(limit) || 20))).reverse() }; }

  pause() {
    const run = this.current();
    if (!run || !ACTIVE.has(run.state)) return { ok: false, error: '当前没有可暂停的运行流程' };
    this.pauseRequested = true;
    this.event(run, run.state, '已请求暂停；将完成当前原子步骤后安全暂停', run.current.progress);
    return { ok: true };
  }

  resume() {
    const run = this.current();
    if (!run || run.state !== 'PAUSED') return { ok: false, error: '当前流程不在暂停状态' };
    run.state = run.pausedFrom || 'RESEARCHING'; run.pausedFrom = null;
    this.event(run, run.state, `从 ${run.state} 阶段恢复`, run.current.progress);
    queueMicrotask(() => this.execute(run.runId));
    return { ok: true };
  }

  async decide(input = {}) {
    const run = this.current();
    if (!run || run.state !== 'AWAITING_USER') return { ok: false, error: '当前没有等待确认的事项' };
    const decision = String(input.decision || '');
    if (!['confirm', 'reject'].includes(decision)) return { ok: false, error: '决策值不合法' };
    this.store.appendAudit({ actor: 'user', action: 'autopilot.decide', params: { decision, type: run.awaitingUser?.type }, result: 'ok', runId: run.runId });
    if (decision === 'reject') {
      run.awaitingUser = null; run.outcome = '用户拒绝建议'; run.endedAt = now();
      this.event(run, 'COMPLETED', '本轮已按你的决定结束；全部研究产物仍保存在本机', 1);
      return { ok: true };
    }
    if (run.awaitingUser?.type === 'improve_confirm') {
      run.awaitingUser = null; run.endedAt = now(); run.outcome = '未通过完整门禁，已保留证据供下一轮改进';
      this.event(run, 'COMPLETED', '本轮没有策略通过完整 G1-G10，未部署模拟盘', 1);
      return { ok: true };
    }
    if (run.awaitingUser?.type === 'paper_confirm') {
      const strategy = run.awaitingUser.payload?.candidates?.[0];
      if (!run.options.paperServerId) {
        run.awaitingUser = null; run.outcome = '完整门禁通过；本轮未选择模拟盘服务器，结果已保存'; run.endedAt = now();
        this.strategies.setStatus(strategy, 'passed');
        this.event(run, 'COMPLETED', '候选策略已通过完整门禁并保存在本机；未执行服务器部署', 1);
        return { ok: true, deployed: false };
      }
      const local = this.strategies.read(strategy);
      if (!local?.code) return { ok: false, error: '候选策略文件不存在' };
      run.awaitingUser = null;
      this.event(run, 'SIM_DEPLOYING', `正在把 ${strategy} 部署到所选模拟盘服务器`, STAGE_PROGRESS.SIM_DEPLOYING);
      const deployed = await this.deployPaper({ serverId: run.options.paperServerId, strategy, code: local.code });
      if (!deployed.ok) {
        run.pausedFrom = 'SIM_DEPLOYING'; this.event(run, 'PAUSED', `模拟盘部署失败：${deployed.error || '未知错误'}`, STAGE_PROGRESS.SIM_DEPLOYING);
        return { ok: false, error: deployed.error || '模拟盘部署失败' };
      }
      this.strategies.setStatus(strategy, 'paper');
      run.tracking = { strategy, startedAt: now(), snapshots: [] };
      this.event(run, 'SIM_TRACKING', '模拟盘已启动；将按巡检结果累计至少 14 天或 50 笔交易', STAGE_PROGRESS.SIM_TRACKING, { paperRobotId: run.options.paperServerId });
      return { ok: true };
    }
    if (run.awaitingUser?.type === 'live_confirm') {
      run.awaitingUser = null; run.outcome = '模拟验证通过，用户已确认实盘建议；需在部署向导再次核对资金和交易所权限'; run.endedAt = now();
      this.event(run, 'COMPLETED', '已记录实盘意向。为防误操作，请在部署向导核对资金后手动开启实盘', 1);
      return { ok: true, requiresDeploymentWizard: true };
    }
    return { ok: false, error: '无法识别该确认类型' };
  }

  async observe(payload = {}) {
    const run = this.current();
    const robot = payload.robot;
    if (!run || run.state !== 'SIM_TRACKING' || !robot || robot.serverId !== run.artifacts.paperRobotId) return;
    run.tracking = run.tracking || { startedAt: now(), snapshots: [] };
    const previous = run.tracking.snapshots.at(-1);
    if (previous && Date.now() - new Date(previous.ts).getTime() < 5 * 60 * 1000) return;
    const snapshot = { ts: payload.ts || now(), state: robot.state, api: robot.api?.state, ...robot.profit };
    run.tracking.snapshots.push(snapshot); run.tracking.snapshots = run.tracking.snapshots.slice(-5000); this.persist(run);
    const days = (Date.now() - new Date(run.tracking.startedAt).getTime()) / 86400000;
    if (days < 14 && Number(snapshot.closedTrades || 0) < 50) return;
    const primary = (run.artifacts.evalReport?.rows || []).find((row) => row.strategy === run.tracking.strategy);
    const expected = Number(primary?.metrics?.expectedValue);
    const actual = Number(snapshot.totalProfitRatio) / Math.max(1, Number(snapshot.closedTrades));
    const deviation = Number.isFinite(expected) && expected !== 0 ? Math.abs(actual - expected) / Math.abs(expected) : Infinity;
    const healthy = deviation <= 0.30 && Number(snapshot.maxDrawdown || 0) < 0.30;
    run.awaitingUser = { type: healthy ? 'live_confirm' : 'improve_confirm', payload: { strategy: run.tracking.strategy, days, closedTrades: snapshot.closedTrades, deviation, maxDrawdown: snapshot.maxDrawdown } };
    this.event(run, 'AWAITING_USER', healthy ? '模拟盘达到观察门槛且偏差可接受，等待你决定是否进入实盘' : '模拟盘达到观察门槛，但与回测偏差过大，建议停止并改进', STAGE_PROGRESS.AWAITING_USER);
    this.send('autopilot:awaitingUser', { runId: run.runId, ...run.awaitingUser });
    await this.notify({ title: 'CK Quant · 模拟验证完成', message: run.current.detail, level: healthy ? 'info' : 'warn' });
  }

  async execute(runId) {
    if (this.processing) return;
    this.processing = true;
    try {
      let run = this.current();
      if (!run || run.runId !== runId) return;
      if (run.state === 'RESEARCHING') {
        this.event(run, 'RESEARCHING', '正在读取本机 15m 历史数据并按动量、波动和量能排序');
        const report = await this.research({ container: run.options.container, limit: 5 });
        run.research = report;
        this.event(run, 'GENERATING', `研究完成：扫描 ${report.scanned} 个交易对，选出 ${report.candidates.length} 个候选`, STAGE_PROGRESS.GENERATING, { researchReport: report });
        if (await this.checkpoint(run)) return;
      }
      run = this.current();
      if (run.state === 'GENERATING') {
        const template = this.strategies.read(run.options.template);
        if (!template?.meta?.locked || template.meta.source !== 'official') throw new Error('官方公开模板不存在或已损坏，流程已停止');
        const generated = this.variants({ name: template.meta.name, code: template.code, count: run.options.variantCount });
        if (generated.error) throw new Error(generated.error);
        const saved = [];
        for (const variant of generated.variants) {
          const result = await this.strategies.save({ ...variant, source: 'variant' });
          if (result.ok) saved.push(result.strategy.name);
        }
        if (!saved.length) throw new Error('自动变体均未通过本机静态校验；核心模板没有被修改');
        run.generatedTunables = generated.tunables;
        this.event(run, 'BACKTESTING', `已在本机生成并校验 ${saved.length} 个受限参数变体`, STAGE_PROGRESS.BACKTESTING, { strategies: saved });
        if (await this.checkpoint(run)) return;
      }
      run = this.current();
      if (run.state === 'BACKTESTING') {
        const pairs = (run.research?.candidates || []).map((item) => item.pair);
        for (let index = run.artifacts.backtestJobs.length; index < run.artifacts.strategies.length; index += 1) {
          const strategy = run.artifacts.strategies[index];
          this.event(run, 'BACKTESTING', `串行回测 ${index + 1}/${run.artifacts.strategies.length}：${strategy}`, 0.38 + (0.26 * index / run.artifacts.strategies.length));
          this.strategies.setStatus(strategy, 'backtesting');
          const submitted = this.backtests.submit({ ...run.options, strategy, timeframe: '15m', pairs });
          if (!submitted.ok) throw new Error(`无法提交 ${strategy}：${submitted.error}`);
          run.artifacts.backtestJobs.push(submitted.jobId); this.persist(run);
          this.strategies.linkBacktest(strategy, submitted.jobId, 'backtesting');
          const job = await this.backtests.wait(submitted.jobId);
          this.strategies.setStatus(strategy, job.status === 'done' ? 'draft' : 'rejected');
          if (await this.checkpoint(run)) return;
        }
        this.event(run, 'EVALUATING', '全部回测结束，正在执行确定性统计门禁');
      }
      run = this.current();
      if (run.state === 'EVALUATING') {
        const primaryJobs = run.artifacts.backtestJobs.map((jobId) => this.backtests.get(jobId)).filter(Boolean);
        const positiveShare = primaryJobs.length ? primaryJobs.filter((job) => job.status === 'done' && job.result?.expectedValue > 0).length / primaryJobs.length : 0;
        run.artifacts.evidenceJobs = run.artifacts.evidenceJobs || {};

        if (!run.artifacts.evidenceJobs.baseline) {
          const template = this.strategies.read(run.options.template);
          const baseline = generateRandomBaseline({ name: template.meta.name, code: template.code });
          if (!baseline.error) {
            const saved = await this.strategies.save({ ...baseline, source: 'variant' });
            if (saved.ok) {
              this.strategies.setStatus(baseline.name, 'backtesting');
              this.event(run, 'EVALUATING', '正在运行相同止损与出场规则的随机入场基线', 0.70);
              const submitted = this.backtests.submit({ ...run.options, strategy: baseline.name, timeframe: '15m', pairs: (run.research?.candidates || []).map((item) => item.pair) });
              if (submitted.ok) {
                run.artifacts.evidenceJobs.baseline = submitted.jobId; run.artifacts.baselineStrategy = baseline.name; this.persist(run);
                await this.backtests.wait(submitted.jobId);
              }
              this.strategies.setStatus(baseline.name, 'banned');
            }
          }
          if (await this.checkpoint(run)) return;
        }

        const ranges = splitTimerange(run.options.timerange);
        const ranked = primaryJobs.filter((job) => job.status === 'done' && job.result).sort((a, b) => b.result.expectedValue - a.result.expectedValue).slice(0, 2);
        run.artifacts.evidenceJobs.walkForward = run.artifacts.evidenceJobs.walkForward || {};
        for (const candidate of ranked) {
          const ids = run.artifacts.evidenceJobs.walkForward[candidate.strategy] || [];
          for (let index = ids.length; index < ranges.length; index += 1) {
            this.event(run, 'EVALUATING', `样本外分段 ${index + 1}/${ranges.length}：${candidate.strategy}`, 0.72 + (0.12 * index / Math.max(1, ranges.length)));
            const submitted = this.backtests.submit({ ...run.options, strategy: candidate.strategy, timeframe: '15m', timerange: ranges[index], pairs: (run.research?.candidates || []).map((item) => item.pair) });
            if (!submitted.ok) break;
            ids.push(submitted.jobId); run.artifacts.evidenceJobs.walkForward[candidate.strategy] = ids; this.persist(run);
            await this.backtests.wait(submitted.jobId);
            if (await this.checkpoint(run)) return;
          }
        }

        const baselineJob = run.artifacts.evidenceJobs.baseline ? this.backtests.get(run.artifacts.evidenceJobs.baseline) : null;
        const baselineEv = baselineJob?.status === 'done' ? baselineJob.result?.expectedValue : null;
        for (const candidate of primaryJobs) {
          const segmentJobs = (run.artifacts.evidenceJobs.walkForward[candidate.strategy] || []).map((jobId) => this.backtests.get(jobId)).filter(Boolean);
          const segmentPasses = segmentJobs.map((job) => job.status === 'done' && job.result?.trades >= 100 && job.result?.evalResult?.gates?.G3?.pass && job.result?.evalResult?.gates?.G4?.pass && job.result?.evalResult?.gates?.G5?.pass && job.result?.evalResult?.gates?.G6?.pass);
          const evidence = {
            robustness: { positiveShare, detail: `${primaryJobs.filter((job) => job.result?.expectedValue > 0).length}/${primaryJobs.length} 个邻域变体期望为正` },
            walkForward: { pass: segmentJobs.length === 3 && segmentPasses.every(Boolean), summary: `${segmentPasses.filter(Boolean).length}/${segmentJobs.length} 段通过`, detail: '各留出段要求 >=100 笔且 G3-G6 通过' },
            regimes: segmentJobs.map((job) => ({ timerange: job.timerange, trades: job.result?.trades || 0, marketChange: job.result?.marketChange, regime: marketRegime(job.result?.marketChange) })),
          };
          if (baselineEv != null) evidence.randomBaselineEv = baselineEv;
          this.backtests.reevaluate(candidate.jobId, evidence);
        }

        const rows = run.artifacts.backtestJobs.map((jobId) => this.backtests.get(jobId)).map((job) => ({
          jobId: job.jobId, strategy: job.strategy, status: job.status, evalResult: job.evalResult || null,
          metrics: job.result ? { trades: job.result.trades, expectedValue: job.result.expectedValue, totalProfitRatio: job.result.totalProfitRatio, annualReturn: job.result.annualReturn, maxDrawdown: job.result.maxDrawdown, profitFactor: job.result.profitFactor } : null,
          error: job.error || null,
        }));
        const passed = rows.filter((row) => row.status === 'done' && row.evalResult?.complete && row.evalResult?.passed);
        for (const row of rows) this.strategies.setStatus(row.strategy, passed.includes(row) ? 'passed' : 'rejected');
        const report = { evaluatedAt: now(), passed: passed.map((row) => row.strategy), rows, conclusion: passed.length ? `${passed.length} 个策略通过完整 G1-G10` : '没有策略通过完整 G1-G10；不会自动部署' };
        run.awaitingUser = { type: passed.length ? 'paper_confirm' : 'improve_confirm', payload: { report, candidates: passed.map((row) => row.strategy) } };
        this.event(run, 'AWAITING_USER', report.conclusion, STAGE_PROGRESS.AWAITING_USER, { evalReport: report });
        this.send('autopilot:awaitingUser', { runId: run.runId, ...run.awaitingUser });
        await this.notify({ title: 'CK Quant · 一键运行等待确认', message: report.conclusion, level: passed.length ? 'info' : 'warn' });
      }
    } catch (error) {
      const run = this.current();
      if (run?.runId === runId) {
        run.pausedFrom = run.state;
        this.event(run, 'PAUSED', `流程已安全暂停：${error.message}`, run.current?.progress || 0);
        await this.notify({ title: 'CK Quant · 一键运行已暂停', message: error.message, level: 'warn' });
      }
    } finally { this.processing = false; }
  }
}

module.exports = { AutopilotService, ACTIVE, TERMINAL, safeOptions, splitTimerange, marketRegime };
