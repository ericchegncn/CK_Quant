const { spawn } = require('child_process');

const RESEARCH_SCRIPT = String.raw`
import glob, json, math, os, sys
import pandas as pd

root = sys.argv[1]
limit = max(3, min(10, int(sys.argv[2])))
rows = []

def pair_name(filename):
    name = os.path.basename(filename).split('-15m')[0]
    parts = name.split('_')
    if len(parts) >= 3:
        return parts[0] + '/' + parts[1] + ':' + parts[2]
    if len(parts) == 2:
        return parts[0] + '/' + parts[1]
    return name

for filename in glob.glob(root + '/**/*-15m*.feather', recursive=True):
    try:
        frame = pd.read_feather(filename).tail(2200)
        if len(frame) < 192 or not {'open','high','low','close','volume'}.issubset(frame.columns):
            continue
        close = frame['close'].astype(float)
        high = frame['high'].astype(float)
        low = frame['low'].astype(float)
        volume = frame['volume'].astype(float)
        previous = close.shift(1)
        tr = pd.concat([(high-low).abs(), (high-previous).abs(), (low-previous).abs()], axis=1).max(axis=1)
        atr = float(tr.rolling(96).mean().iloc[-1])
        price = float(close.iloc[-1])
        momentum_1h = price / float(close.iloc[-5]) - 1
        momentum_4h = price / float(close.iloc[-17]) - 1
        momentum_1d = price / float(close.iloc[-97]) - 1
        volume_base = float(volume.tail(96).mean())
        volume_ratio = float(volume.tail(16).mean()) / volume_base if volume_base > 0 else 0
        atr_ratio = atr / price if price > 0 else 0
        score = abs(momentum_4h) * 3 + abs(momentum_1d) + atr_ratio * 8 + min(volume_ratio, 5) * 0.01
        values = [momentum_1h, momentum_4h, momentum_1d, volume_ratio, atr_ratio, score]
        if not all(math.isfinite(value) for value in values):
            continue
        rows.append({'pair': pair_name(filename), 'score': score, 'momentum1h': momentum_1h,
                     'momentum4h': momentum_4h, 'momentum1d': momentum_1d,
                     'volumeRatio': volume_ratio, 'atrRatio': atr_ratio, 'candles': len(frame)})
    except Exception:
        continue

rows.sort(key=lambda item: item['score'], reverse=True)
print('CKQ_JSON:' + json.dumps({'candidates': rows[:limit], 'scanned': len(rows)}, ensure_ascii=False))
`;

function runDocker(args) {
  return new Promise((resolve, reject) => {
    const child = spawn('docker', args, { windowsHide: true, shell: false });
    let stdout = ''; let stderr = '';
    child.stdout.on('data', (chunk) => { stdout += chunk.toString(); });
    child.stderr.on('data', (chunk) => { stderr += chunk.toString(); });
    child.on('error', reject);
    child.on('close', (code) => resolve({ code, stdout, stderr }));
  });
}

async function researchMarket({ container = 'CK_Quant', limit = 5, runner = runDocker }) {
  const result = await runner(['exec', container, 'python', '-c', RESEARCH_SCRIPT, '/CK_Quant/user_data/data', String(limit)]);
  if (result.code !== 0) throw new Error(`读取本机行情失败：${(result.stderr || result.stdout).slice(-600)}`);
  const marker = result.stdout.split(/\r?\n/).find((line) => line.startsWith('CKQ_JSON:'));
  if (!marker) throw new Error('行情研究脚本没有返回可识别结果');
  const report = JSON.parse(marker.slice('CKQ_JSON:'.length));
  if (!report.candidates?.length) throw new Error('没有找到可用的 15m Feather 行情；请先在 CK_Quant 中下载历史数据');
  return { ...report, generatedAt: new Date().toISOString(), source: '本机 Docker 历史行情', timeframe: '15m' };
}

module.exports = { RESEARCH_SCRIPT, researchMarket, runDocker };
