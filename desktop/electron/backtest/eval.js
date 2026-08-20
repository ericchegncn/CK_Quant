function finite(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function mean(values) {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
}

function seededRandom(seed = 20260820) {
  let state = seed >>> 0;
  return () => ((state = (1664525 * state + 1013904223) >>> 0) / 4294967296);
}

function bootstrapMeanCi(values, samples = 1000, seed = 20260820) {
  if (!values.length) return [0, 0];
  const random = seededRandom(seed);
  const means = [];
  for (let sample = 0; sample < samples; sample += 1) {
    let sum = 0;
    for (let index = 0; index < values.length; index += 1) sum += values[Math.floor(random() * values.length)];
    means.push(sum / values.length);
  }
  means.sort((a, b) => a - b);
  return [means[Math.floor(samples * 0.025)], means[Math.floor(samples * 0.975)]];
}

function gate(pass, value, threshold, detail, status = pass ? 'passed' : 'failed') {
  return { pass: Boolean(pass), value, threshold, detail, status };
}

function evaluate(result, evidence = {}) {
  const derivedBuyHold = Number.isFinite(result.marketChange) && finite(result.backtestDays) > 0
    ? Math.pow(Math.max(0.000001, 1 + result.marketChange), 365 / result.backtestDays) - 1
    : null;
  const buyHoldAnnualReturn = evidence.buyHoldAnnualReturn ?? derivedBuyHold;
  const regimes = Array.isArray(evidence.regimes) ? evidence.regimes : [];
  const periodCounts = regimes.map((period) => finite(period.trades));
  const regimeKinds = new Set(regimes.map((period) => period.regime));
  const hasThreeRegimes = periodCounts.length >= 3 && periodCounts.every((count) => count >= 30) && ['bull', 'bear', 'range'].every((kind) => regimeKinds.has(kind));
  const spanOk = finite(result.backtestDays) >= 730;
  const g2Ready = regimes.length >= 3;
  const gates = {
    G1: gate(result.trades >= 300, result.trades, '>= 300', `共 ${result.trades} 笔交易`),
    G2: g2Ready
      ? gate(spanOk && hasThreeRegimes, `${result.backtestDays} 天`, '>= 2 年且三种市场各 >= 30 笔', '历史跨度和市场状态覆盖')
      : gate(false, `${result.backtestDays} 天`, '>= 2 年且覆盖牛熊震荡', '缺少可验证的牛市、熊市和震荡样本证据', 'not_evaluated'),
    G3: gate(result.expectedValue > 0 && result.evCi95[0] > 0, result.expectedValue, '均值 > 0 且 95%CI 下界 > 0', `95%CI [${result.evCi95.map((v) => v.toFixed(6)).join(', ')}]`),
    G4: buyHoldAnnualReturn == null
      ? gate(false, result.annualReturn, '> 同池买入持有基准', '尚未计算买入持有基准', 'not_evaluated')
      : gate(result.annualReturn > 0 && result.annualReturn > buyHoldAnnualReturn, result.annualReturn, `> ${buyHoldAnnualReturn}`, '与同池买入持有年化比较'),
    G5: gate(result.maxDrawdown < 0.30, result.maxDrawdown, '< 0.30', `最大回撤 ${(result.maxDrawdown * 100).toFixed(2)}%`),
    G6: gate(result.profitFactor >= 1, result.profitFactor, '>= 1.0', `利润因子 ${result.profitFactor.toFixed(3)}`),
    G7: evidence.walkForward?.pass == null
      ? gate(false, '未执行', '样本外验证通过', '需要独立留出集回测', 'not_evaluated')
      : gate(evidence.walkForward.pass, evidence.walkForward.summary, '样本外验证通过', evidence.walkForward.detail || ''),
    G8: evidence.robustness?.positiveShare == null
      ? gate(false, '未执行', '>= 80% 邻域期望为正', '需要参数邻域回测', 'not_evaluated')
      : gate(evidence.robustness.positiveShare >= 0.8, evidence.robustness.positiveShare, '>= 0.80', evidence.robustness.detail || ''),
    G9: gate(result.topPairShare < 0.5 && result.topMonthShare < 0.5, { topPairShare: result.topPairShare, topMonthShare: result.topMonthShare }, '< 0.50 / < 0.50', '单币和单月收益集中度'),
    G10: evidence.randomBaselineEv == null
      ? gate(false, '未执行', '策略期望 >= 2x 随机基线', '需要随机入场基线回测', 'not_evaluated')
      : gate(result.expectedValue >= 2 * evidence.randomBaselineEv, result.expectedValue, `>= ${2 * evidence.randomBaselineEv}`, `随机基线 ${evidence.randomBaselineEv}`),
  };
  const required = Object.values(gates);
  const passed = required.every((item) => item.pass);
  const evaluated = required.filter((item) => item.status !== 'not_evaluated').length;
  return {
    passed,
    complete: evaluated === required.length,
    summary: passed ? 'G1-G10 全部通过' : `已评估 ${evaluated}/${required.length} 项强制门禁；未全部通过`,
    gates,
    evidence: Object.keys(evidence),
  };
}

module.exports = { finite, mean, bootstrapMeanCi, evaluate };
