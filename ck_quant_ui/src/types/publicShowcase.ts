/**
 * Guest-visible showcase configuration for a single bot.
 *
 * Served by the authenticated endpoint `/api/v1/ck_quant/public_showcase`.
 * `label` is the public heading shown on the showcase page; it must never be
 * derived from internal strategy or container names.
 */
export interface PublicShowcaseConfig {
  enabled: boolean;
  label: string;
  show_absolute: boolean;
}

/** Partial update sent to the public-showcase endpoint. */
export interface PublicShowcasePayload {
  enabled?: boolean;
  label?: string;
  show_absolute?: boolean;
}
