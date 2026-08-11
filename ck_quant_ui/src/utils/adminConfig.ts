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
