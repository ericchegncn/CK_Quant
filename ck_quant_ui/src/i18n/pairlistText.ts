import { de } from './pairlist.de';
import { fr } from './pairlist.fr';
import { ja } from './pairlist.ja';
import { ko } from './pairlist.ko';
import { zhTW } from './pairlist.zh-TW';

const zhCN: Record<string, string> = {
  'Use pairlist as configured in config.': '使用配置文件中设置的交易对列表。',
  'Provides dynamic pair list based on trade volumes.': '根据交易成交量动态生成交易对列表。',
  'Filter pairs by age (days listed).': '按照交易对上线天数进行筛选。',
  'Filter pairs by performance.': '按照交易对表现进行筛选。',
  'Filter pairs by price.': '按照交易对价格进行筛选。',
  'Filter pairs by their recent volatility.': '按照交易对近期波动率进行筛选。',
  'Filters low-value coins which would not allow setting stoplosses.':
    '过滤因价值过低而无法正确设置止损的币种。',
  'Filters pairs by their rate of change.': '按照价格变化率筛选交易对。',
  'Filter by bid/ask difference.': '按照买卖价差筛选交易对。',
  'Get a pairlist from an upstream bot.': '从上游机器人获取交易对列表。',
  'Retrieve pairs from a remote API.': '从远程 API 获取交易对列表。',
  'Randomize pairlist order.': '随机打乱交易对列表顺序。',
  'Offset pair list filter.': '按照偏移位置截取交易对列表。',
  'Allow inactive pairs': '允许非活跃交易对',
  'Allow inactive pairs to be in the whitelist.': '允许非活跃交易对保留在白名单中。',
  'Bearer token': 'Bearer 令牌',
  'Bearer token - used for auth against the upstream service.':
    '用于访问上游服务的 Bearer 身份验证令牌。',
  'Consider trades from the last X minutes. 0 means all trades.':
    '统计最近 X 分钟的交易；0 表示全部交易。',
  'Keep last pairlist on failure': '失败时保留上一次交易对列表',
  'Lookback Days': '回看天数',
  'Lookback Period': '回看周期数',
  'Lookback Timeframe': '回看时间框架',
  'Low price ratio': '低价比例',
  'Max spread ratio': '最大价差比例',
  'Max spread ratio for a pair to be considered.': '交易对允许的最大买卖价差比例。',
  'Maximum Days Listed': '最大上线天数',
  'Maximum number of days a pair must have been listed on the exchange.':
    '交易对在交易所上线天数的最大值。',
  'Maximum price': '最高价格',
  'Maximum Rate of Change': '最大变化率',
  'Maximum rate of change to filter pairs.': '用于筛选交易对的最大价格变化率。',
  'Maximum value': '最大价值',
  'Maximum Volatility': '最大波动率',
  'Maximum volatility a pair must have to be considered.': '交易对允许的最大波动率。',
  'Minimum Days Listed': '最小上线天数',
  'Minimum number of days a pair must have been listed on the exchange.':
    '交易对在交易所上线天数的最小值。',
  'Minimum price': '最低价格',
  'Minimum profit': '最低收益',
  'Minimum profit in percent. Pairs with less profit are removed.':
    '最低收益率，低于此收益率的交易对将被移除。',
  'Minimum Rate of Change': '最小变化率',
  'Minimum rate of change to filter pairs.': '用于筛选交易对的最小价格变化率。',
  'Minimum value': '最小价值',
  'Minimum value to use for filtering the pairlist.': '筛选交易对列表时使用的最小价值。',
  'Minimum Volatility': '最小波动率',
  'Minimum volatility a pair must have to be considered.': '交易对需要达到的最小波动率。',
  Minutes: '分钟数',
  'Name of the producer to use. Requires additional external_message_consumer configuration.':
    '要使用的生产者名称；需要额外配置 external_message_consumer。',
  'Number of assets': '交易对数量',
  'Number of assets to use from the pairlist': '从列表中选用的交易对数量。',
  'Number of assets to use from the pairlist, starting from offset.':
    '从偏移位置开始选用的交易对数量。',
  'Number of assets to use from the pairlist.': '从列表中选用的交易对数量。',
  'Number of days to look back at.': '需要回看的天数。',
  'Number of periods to look back at.': '需要回看的周期数。',
  Offset: '偏移位置',
  'Offset of the pairlist.': '交易对列表的起始偏移位置。',
  'Producer name': '生产者名称',
  'Random Seed': '随机种子',
  'Read timeout': '读取超时',
  'Refresh period': '刷新周期',
  'Refresh period in seconds': '刷新周期（秒）',
  'Remove pairs where a price move of 1 price unit (pip) is above this ratio.':
    '移除一个最小价格单位的变动比例高于该值的交易对。',
  'Remove pairs with a price above this value.': '移除价格高于该值的交易对。',
  'Remove pairs with a price below this value.': '移除价格低于该值的交易对。',
  'Remove pairs with a value (price * amount) above this value.':
    '移除价值（价格 × 数量）高于该值的交易对。',
  'Request timeout for remote pairlist': '远程交易对列表请求超时时间。',
  'Seed for random number generator. Not used in live mode.': '随机数生成器种子；实盘模式不使用。',
  'Shuffle frequency': '随机排序频率',
  "Shuffle frequency. Can be either 'candle' or 'iteration'.":
    "随机排序频率，可选 'candle' 或 'iteration'。",
  'Sort key': '排序字段',
  'Sort key to use for sorting the pairlist.': '交易对列表使用的排序字段。',
  'Timeframe to use for lookback.': '回看所使用的时间框架。',
  'URL to fetch pairlist from': '获取交易对列表的 URL',
};

export function localizePairlistText(text: string | undefined, locale: string): string {
  if (!text) return '';
  const catalogs: Record<string, Record<string, string>> = {
    'zh-CN': zhCN,
    'zh-TW': zhTW,
    de,
    fr,
    ja,
    ko,
  };
  return catalogs[locale]?.[text] ?? text;
}
