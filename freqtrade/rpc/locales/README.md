# Bot message catalogues / 机器人消息语言包

One JSON fragment per area and language: `<area>.<locale>.json`.

| Area | Used by | Owner |
| ---- | ------- | ----- |
| `tg` | `freqtrade/rpc/telegram.py` (all Telegram output) | Telegram handler |
| `rpc` | `freqtrade/rpc/rpc.py` (errors shown in the chat) | RPC layer |

The English fragments (`*.en.json`) are the **source of truth**: every value is
the literal string the code used to contain. Keys are flat, dot separated and
prefixed with the area (`tg.entry.new_trade`, `rpc.no_active_trade`).

Locales mirror the WebUI picker (`ck_quant_ui/src/i18n/index.ts`):
`en`, `zh-CN`, `zh-TW`, `de`, `ja`, `fr`, `ko`.

## Rules

1. **Never change a value in `*.en.json`** when the goal is to translate - the
   English output must stay byte identical (the upstream test suite pins it).
2. Placeholders are named (`{pair}`, `{amount}`) and must be kept verbatim in
   translated values, same names, same count. The values are formatted with
   `str.format`, so a literal brace has to be doubled (`{{`).
3. Markdown (`*bold*`, `` `code` ``, escaped characters) and emojis are part of
   the message and must be preserved - they are what Telegram renders.
4. Keep line breaks (`\n`) and trailing whitespace exactly where the English
   value has them.
5. A translation must never leave a key untranslated: `tests/rpc/test_i18n.py`
   asserts that every shipped locale covers the full English catalogue and uses
   the same placeholders.

## Glossary (keep terminology consistent)

| English | zh-CN | zh-TW | de | ja | fr | ko |
| ------- | ----- | ----- | -- | -- | -- | -- |
| Pair | 交易对 | 交易對 | Paar | 通貨ペア | Paire | 페어 |
| Amount | 数量 | 數量 | Menge | 数量 | Montant | 수량 |
| Open Rate | 开仓价 | 開倉價 | Einstiegskurs | エントリー価格 | Prix d'entrée | 진입가 |
| Current Rate | 当前价 | 當前價 | Aktueller Kurs | 現在価格 | Prix actuel | 현재가 |
| Exit Rate | 平仓价 | 平倉價 | Ausstiegskurs | 決済価格 | Prix de sortie | 청산가 |
| Profit | 盈亏 | 盈虧 | Gewinn | 損益 | Profit | 손익 |
| Direction | 方向 | 方向 | Richtung | 方向 | Sens | 방향 |
| Leverage | 杠杆 | 槓桿 | Hebel | レバレッジ | Levier | 레버리지 |
| Duration | 持仓时长 | 持倉時長 | Dauer | 保有時間 | Durée | 보유 기간 |
| Enter Tag | 入场标签 | 入場標籤 | Einstiegs-Tag | エントリータグ | Tag d'entrée | 진입 태그 |
| Exit Reason | 出场原因 | 出場原因 | Ausstiegsgrund | 決済理由 | Raison de sortie | 청산 사유 |
| Balance | 余额 | 餘額 | Guthaben | 残高 | Solde | 잔고 |
| Trade / Trades | 交易 / 持仓 | 交易 / 持倉 | Trade(s) | トレード | Trade(s) | 트레이드 |
| Whitelist | 白名单 | 白名單 | Whitelist | ホワイトリスト | Liste blanche | 화이트리스트 |
| Blacklist | 黑名单 | 黑名單 | Blacklist | ブラックリスト | Liste noire | 블랙리스트 |
| Win rate | 胜率 | 勝率 | Trefferquote | 勝率 | Taux de réussite | 승률 |
| Profit factor | 利润因子 | 利潤因子 | Profitfaktor | プロフィットファクター | Facteur de profit | 수익 계수 |
| Drawdown | 回撤 | 回撤 | Drawdown | ドローダウン | Drawdown | 낙폭 |
| Stake | 仓位 | 倉位 | Einsatz | ステーク | Mise | 스테이크 |
| Open trades | 未平仓交易 | 未平倉交易 | Offene Trades | 未決済トレード | Trades ouverts | 미체결 트레이드 |
| Force exit | 强制平仓 | 強制平倉 | Zwangsausstieg | 強制決済 | Sortie forcée | 강제 청산 |
