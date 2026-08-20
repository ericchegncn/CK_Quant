function functionSlice(code, name) {
  const lines = String(code || '').split(/(?<=\n)/);
  const start = lines.findIndex((line) => new RegExp(`^\\s+def\\s+${name}\\s*\\(`).test(line));
  if (start < 0) return null;
  const indent = lines[start].match(/^\s*/)[0].length;
  let end = lines.length;
  for (let index = start + 1; index < lines.length; index += 1) {
    const match = lines[index].match(/^(\s*)def\s+/);
    if (match && match[1].length === indent) { end = index; break; }
  }
  const offset = lines.slice(0, start).join('').length;
  return { text: lines.slice(start, end).join(''), offset };
}

function extractTunables(code) {
  const scope = functionSlice(code, 'populate_entry_trend');
  if (!scope) return [];
  const matches = [];
  const pattern = /([<>]=?\s*)(-?\d+(?:\.\d+)?(?:e-?\d+)?)/gi;
  let match;
  while ((match = pattern.exec(scope.text))) {
    const value = Number(match[2]);
    if (!Number.isFinite(value) || value === 0 || Math.abs(value) === 1) continue;
    matches.push({ start: scope.offset + match.index + match[1].length, end: scope.offset + match.index + match[0].length, value });
  }
  return matches.slice(0, 8);
}

function extractParameterTunables(code) {
  const tunables = [];
  const pattern = /(IntParameter|DecimalParameter|RealParameter)\s*\(([^)]*)\)/g;
  let match;
  while ((match = pattern.exec(String(code || '')))) {
    const args = match[2];
    const low = args.match(/\blow\s*=\s*(-?\d+(?:\.\d+)?)/);
    const high = args.match(/\bhigh\s*=\s*(-?\d+(?:\.\d+)?)/);
    const value = args.match(/\bdefault\s*=\s*(-?\d+(?:\.\d+)?)/);
    if (!low || !high || !value) continue;
    const start = match.index + match[0].indexOf(args) + value.index + value[0].lastIndexOf(value[1]);
    tunables.push({ start, end: start + value[1].length, value: Number(value[1]), low: Number(low[1]), high: Number(high[1]), integer: match[1] === 'IntParameter' });
  }
  return tunables.slice(0, 8);
}

function formatNumber(value, original) {
  const decimals = (String(original).split('.')[1] || '').replace(/e.*/i, '').length;
  if (Math.abs(value) < 0.01) return Number(value.toPrecision(6)).toString();
  return value.toFixed(Math.min(6, Math.max(2, decimals))).replace(/0+$/, '').replace(/\.$/, '');
}

function generateVariants({ name, code, count = 3 }) {
  const parameterTunables = extractParameterTunables(code);
  const tunables = parameterTunables.length ? parameterTunables : extractTunables(code);
  if (!tunables.length) return { variants: [], tunables: [], error: '核心模板的入场函数中没有找到可安全调整的数值阈值' };
  const safeCount = Math.max(1, Math.min(5, Number(count) || 3));
  const factors = [0.9, 1.1, 0.8, 1.2, 0.95];
  const stamp = new Date().toISOString().replace(/\D/g, '').slice(0, 12);
  const variants = [];
  for (let index = 0; index < safeCount; index += 1) {
    const variantName = `AI_${stamp}_v${index + 1}`;
    let next = code;
    for (const tunable of [...tunables].reverse()) {
      const factor = factors[(index + tunables.indexOf(tunable)) % factors.length];
      let nextValue = tunable.low == null ? tunable.value * factor : tunable.value + (tunable.high - tunable.low) * (factor - 1);
      if (tunable.low != null) nextValue = Math.max(tunable.low, Math.min(tunable.high, nextValue));
      if (tunable.integer) nextValue = Math.round(nextValue);
      const replacement = tunable.integer ? String(nextValue) : formatNumber(nextValue, next.slice(tunable.start, tunable.end));
      next = `${next.slice(0, tunable.start)}${replacement}${next.slice(tunable.end)}`;
    }
    const classPattern = new RegExp(`(class\\s+)${name}(\\s*\\()`);
    if (!classPattern.test(next)) return { variants: [], tunables, error: `找不到核心策略类 ${name}` };
    next = next.replace(classPattern, `$1${variantName}$2`);
    variants.push({ name: variantName, code: next, base: name, notes: `本机自动生成的受限参数变体 ${index + 1}；只调整入场阈值，未改动止损、杠杆或 custom_exit。` });
  }
  return { variants, tunables: tunables.map(({ value }) => value) };
}

function generateRandomBaseline({ name, code }) {
  const stamp = new Date().toISOString().replace(/\D/g, '').slice(0, 12);
  const baselineName = `Baseline_${stamp}`;
  const baseName = `_LocalCore_${stamp}`;
  const classPattern = new RegExp(`(class\\s+)${name}(\\s*\\()`);
  if (!classPattern.test(code)) return { error: `找不到核心策略类 ${name}` };
  const renamed = code.replace(classPattern, `$1${baseName}$2`);
  const override = `\n\nclass ${baselineName}(${baseName}):
    """本机确定性随机入场基线；继承相同出场、止损和杠杆规则。"""
    timeframe = '15m'
    def populate_entry_trend(self, dataframe, metadata):
        dataframe['enter_long'] = 0
        dataframe['enter_short'] = 0
        random_key = ((dataframe['date'].astype('int64') // 1000000000) + (dataframe['close'] * 1000000).astype('int64')) % 997
        valid = dataframe['volume'] > 0
        dataframe.loc[valid & (random_key < 16), ['enter_long', 'enter_tag']] = (1, '| 随机基线：做多 |')
        dataframe.loc[valid & (random_key >= 16) & (random_key < 32), ['enter_short', 'enter_tag']] = (1, '| 随机基线：做空 |')
        return dataframe
`;
  return { name: baselineName, code: `${renamed.trimEnd()}${override}`, base: name, notes: '仅用于 G10 信息增益比较的本机随机入场基线；继承核心模板的出场、止损和杠杆。' };
}

module.exports = { functionSlice, extractTunables, extractParameterTunables, generateVariants, generateRandomBaseline };
