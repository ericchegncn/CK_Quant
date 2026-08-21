type Translate = (key: string, values?: Record<string, string | number>) => string;

const jobCategoryKeys: Record<string, string> = {
  backtest: 'backgroundJobBacktest',
  pairlist: 'backgroundJobPairlist',
  download_data: 'backgroundJobDownloadData',
  lookahead_analysis: 'backgroundJobLookaheadAnalysis',
  recursive_analysis: 'backgroundJobRecursiveAnalysis',
};

const jobStatusKeys: Record<string, string> = {
  success: 'backgroundJobStatusSuccess',
  failed: 'backgroundJobStatusFailed',
  running: 'backgroundJobStatusRunning',
  pending: 'backgroundJobStatusPending',
  queued: 'backgroundJobStatusQueued',
};

const exactProgressKeys: Record<string, string> = {
  backtest: 'progressBacktest',
  backtesting: 'progressBacktesting',
  'startup candles': 'progressStartupCandles',
  'analyzing trades': 'progressAnalyzingTrades',
  'recursive analysis': 'progressRecursiveAnalysis',
  'lookahead analysis': 'progressLookaheadAnalysis',
  'downloading data...': 'progressDownloadingData',
  timeframe: 'progressTimeframe',
  dataload: 'progressDataLoad',
  analyze: 'progressAnalyze',
  convert: 'progressConvert',
};

export function localizeJobCategory(category: string, t: Translate): string {
  const key = jobCategoryKeys[category.toLowerCase()];
  return key ? t(`research.${key}`) : category;
}

export function localizeJobStatus(status: string, t: Translate): string {
  const key = jobStatusKeys[status.toLowerCase()];
  return key ? t(`research.${key}`) : status;
}

export function localizeJobDescription(description: string, t: Translate): string {
  const normalized = description.trim();
  const exactKey = exactProgressKeys[normalized.toLowerCase()];
  if (exactKey) return t(`research.${exactKey}`);

  let match = normalized.match(/^Startup candle\s+(\d+)$/i);
  if (match) return t('research.progressStartupCandle', { count: match[1] });

  match = normalized.match(/^Analyzing\s+(.+)$/i);
  if (match) return t('research.progressAnalyzingStrategy', { strategy: match[1] });

  match = normalized.match(/^Downloading trades\s+\[(.+)]$/i);
  if (match) return t('research.progressDownloadingTrades', { pair: match[1] });

  match = normalized.match(/^Downloading\s+(.+)$/i);
  if (match) return t('research.progressDownloadingPair', { pair: match[1] });

  match = normalized.match(/^Timeframe\s+(.+)$/i);
  if (match) return t('research.progressTimeframeValue', { timeframe: match[1] });

  return description;
}
