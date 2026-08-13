export function applyManualPairWhitelist(
  config: Record<string, unknown>,
  whitelist: string[],
): Record<string, unknown> {
  const exchange =
    typeof config.exchange === 'object' &&
    config.exchange !== null &&
    !Array.isArray(config.exchange)
      ? (config.exchange as Record<string, unknown>)
      : {};
  const pairlists = Array.isArray(config.pairlists) ? config.pairlists : [];
  const firstPairlist = pairlists[0];
  const firstMethod =
    typeof firstPairlist === 'object' && firstPairlist !== null && !Array.isArray(firstPairlist)
      ? (firstPairlist as Record<string, unknown>).method
      : undefined;

  const staticPairlists =
    firstMethod === 'StaticPairList'
      ? pairlists
      : [
          { method: 'StaticPairList' },
          ...pairlists.slice(1).filter((pairlist) => {
            if (typeof pairlist !== 'object' || pairlist === null || Array.isArray(pairlist)) {
              return true;
            }
            return (pairlist as Record<string, unknown>).method !== 'StaticPairList';
          }),
        ];

  return {
    ...config,
    exchange: {
      ...exchange,
      pair_whitelist: whitelist,
    },
    pairlists: staticPairlists,
  };
}

export function normalizeAdminConfigSource(source: string): string {
  try {
    const config = JSON.parse(source) as Record<string, unknown>;
    const stakeAmount = config.stake_amount;

    if (typeof stakeAmount === 'string') {
      const trimmed = stakeAmount.trim();
      const numericStakeAmount = Number(trimmed);

      if (trimmed !== '' && Number.isFinite(numericStakeAmount)) {
        config.stake_amount = numericStakeAmount;
        return JSON.stringify(config, null, 2);
      }
    }
  } catch {
    // Leave invalid JSON unchanged so the server can return its normal validation message.
  }

  return source;
}
