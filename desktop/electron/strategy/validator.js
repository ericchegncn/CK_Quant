const { spawn } = require('child_process');

const INSPECT_SCRIPT = String.raw`
import ast, json, sys
source = sys.stdin.read()
try:
    tree = ast.parse(source)
except SyntaxError as exc:
    print(json.dumps({"ok": False, "error": str(exc), "line": exc.lineno}))
    raise SystemExit(2)

classes, imports, attributes, methods, calls = [], [], {}, {}, []
for node in ast.walk(tree):
    if isinstance(node, ast.Import): imports.extend(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom): imports.append(node.module or "")
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name): calls.append(node.func.id)
        elif isinstance(node.func, ast.Attribute): calls.append(node.func.attr)
for node in tree.body:
    if isinstance(node, ast.ClassDef):
        classes.append(node.name)
        class_methods = []
        class_attrs = {}
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                class_methods.append(item.name)
            if isinstance(item, (ast.Assign, ast.AnnAssign)):
                targets = item.targets if isinstance(item, ast.Assign) else [item.target]
                value = item.value
                if isinstance(value, ast.Constant) and isinstance(value.value, (str, int, float, bool)):
                    for target in targets:
                        if isinstance(target, ast.Name): class_attrs[target.id] = value.value
        methods[node.name] = class_methods
        attributes[node.name] = class_attrs
print(json.dumps({"ok": True, "classes": classes, "imports": sorted(set(imports)), "attributes": attributes, "methods": methods, "calls": sorted(set(calls)), "lines": len(source.splitlines())}))
`;

function spawnInspect(command, args, source, timeoutMs = 20000) {
  return new Promise((resolve) => {
    let settled = false;
    const child = spawn(command, args, { windowsHide: true, shell: false });
    let stdout = '';
    let stderr = '';
    const timer = setTimeout(() => { child.kill(); finish({ ok: false, unavailable: false, error: 'Python 语法检查超时' }); }, timeoutMs);
    function finish(result) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(result);
    }
    child.stdout.on('data', (chunk) => { stdout += chunk.toString(); });
    child.stderr.on('data', (chunk) => { stderr += chunk.toString(); });
    child.on('error', (error) => finish({ ok: false, unavailable: error.code === 'ENOENT', error: error.message }));
    child.on('close', () => {
      try { finish({ ...JSON.parse(stdout.trim()), stderr }); }
      catch (_) { finish({ ok: false, unavailable: false, error: (stderr || stdout || 'Python 检查没有返回结果').slice(-800) }); }
    });
    child.stdin.on('error', () => {});
    child.stdin.end(source);
  });
}

async function inspectPython(source, inspectImpl) {
  if (inspectImpl) return inspectImpl(source);
  const local = await spawnInspect('python', ['-c', INSPECT_SCRIPT], source);
  if (local.ok || local.line) return local;
  return spawnInspect('docker', ['exec', '-i', 'CK_Quant', 'python', '-c', INSPECT_SCRIPT], source, 30000);
}

function stripComments(source) {
  return String(source).split(/\r?\n/).map((line) => line.replace(/#.*$/, '')).join('\n');
}

async function validateStrategy({ name, code, strictTemplate = false, inspectImpl } = {}) {
  const errors = [];
  const warnings = [];
  const strategyName = String(name || '').trim();
  const source = String(code || '');
  if (!/^[A-Za-z_][A-Za-z0-9_]{0,127}$/.test(strategyName)) errors.push({ rule: 'V2', message: '策略名称只能包含字母、数字和下划线，且不能以数字开头' });
  if (!source.trim()) errors.push({ rule: 'V1', message: '策略代码不能为空' });
  if (errors.length) return { ok: false, errors, warnings, facts: null };

  const facts = await inspectPython(source, inspectImpl);
  if (!facts.ok) {
    errors.push({ rule: 'V1', message: `Python 语法检查失败${facts.line ? `（第 ${facts.line} 行）` : ''}：${facts.error || facts.stderr || '未知错误'}` });
    return { ok: false, errors, warnings, facts };
  }
  if (!facts.classes.includes(strategyName)) errors.push({ rule: 'V2', message: `代码中没有与文件名一致的类 ${strategyName}` });
  const attributes = facts.attributes[strategyName] || {};
  const methods = new Set(facts.methods[strategyName] || []);
  if (attributes.timeframe !== '15m') errors.push({ rule: 'V3', message: `timeframe 必须是 15m，当前为 ${String(attributes.timeframe ?? '未定义')}` });

  const missingCore = ['leverage', 'custom_exit'].filter((method) => !methods.has(method));
  if (missingCore.length) {
    const item = { rule: 'V4', message: `缺少核心方法：${missingCore.join('、')}` };
    if (strictTemplate) errors.push(item); else warnings.push(item);
  }
  if (!methods.has('custom_stoploss') && attributes.use_custom_stoploss !== false) {
    warnings.push({ rule: 'V4', message: '未检测到 custom_stoploss，请确认止损由固定 stoploss 或其他机制负责' });
  }

  const cleaned = stripComments(source).toLowerCase();
  for (const pattern of ['shift(-', 'lookahead', 'future_']) {
    if (cleaned.includes(pattern)) errors.push({ rule: 'V5', message: `检测到可能使用未来数据的模式：${pattern}` });
  }

  const safeRoots = new Set(['datetime', 'logging', 'typing', 'math', 'decimal', 'collections', 'functools', 'numpy', 'pandas', 'talib', 'freqtrade', 'technical']);
  const dangerousRoots = new Set(['os', 'subprocess', 'socket', 'requests', 'urllib', 'http', 'ftplib', 'shutil', 'pathlib']);
  for (const imported of facts.imports || []) {
    const root = imported.split('.')[0];
    if (dangerousRoots.has(root)) errors.push({ rule: 'V8', message: `禁止策略导入高风险模块：${imported}` });
    else if (!safeRoots.has(root)) warnings.push({ rule: 'V8', message: `非常用模块 ${imported}，部署前请人工确认用途` });
  }
  for (const call of facts.calls || []) {
    if (['eval', 'exec', '__import__', 'open', 'compile'].includes(call)) errors.push({ rule: 'V8', message: `禁止策略调用高风险函数：${call}()` });
  }

  for (const indicator of ['mfi', 'adx', 'macd', 'obv']) {
    if (new RegExp(`\\b${indicator}\\b`, 'i').test(cleaned)) warnings.push({ rule: 'V7', message: `检测到非基础特征 ${indicator.toUpperCase()}，需证明它带来样本外提升` });
  }
  if (facts.lines > 600) warnings.push({ rule: 'V9', message: `代码共 ${facts.lines} 行，超过 600 行，维护和审查成本较高` });

  for (const [key, raw] of Object.entries(attributes)) {
    const value = Number(raw);
    if (!Number.isFinite(value)) continue;
    const lower = key.toLowerCase();
    if (lower.includes('atr') && lower.includes('multiplier') && (value < 1 || value > 6)) warnings.push({ rule: 'V10', message: `${key}=${value} 超出建议 ATR 倍数 1~6` });
    if (lower.includes('near') && (lower.includes('window') || lower.includes('period')) && (value < 24 || value > 192)) warnings.push({ rule: 'V10', message: `${key}=${value} 超出建议窗口 24~192` });
    if (/(^|_)rsi($|_)/.test(lower) && (value < 20 || value > 80)) warnings.push({ rule: 'V10', message: `${key}=${value} 超出建议 RSI 阈值 20~80` });
  }
  return { ok: errors.length === 0, errors, warnings, facts: { classes: facts.classes, imports: facts.imports, attributes, methods: [...methods], lines: facts.lines } };
}

module.exports = { validateStrategy, inspectPython, spawnInspect, stripComments, INSPECT_SCRIPT };
