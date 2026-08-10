export interface AdminCapabilities {
  enabled: boolean;
  config_edit: boolean;
  strategy_edit: boolean;
  apply_reload: boolean;
  audit_log: boolean;
  automatic_backups: boolean;
}

export type AdminDocumentKind = 'config' | 'strategy';

export interface EditableAdminDocument {
  kind: AdminDocumentKind;
  name: string;
  source: string;
  revision: string;
  redacted: boolean;
  updated_at: string;
}

export interface SaveAdminDocumentPayload {
  source: string;
  revision: string;
  apply: boolean;
}

export interface SaveAdminDocumentResult {
  status: string;
  revision: string;
  backup_id: string;
  reload_requested: boolean;
}

export interface AdminValidationResult {
  valid: boolean;
  message: string;
}

export interface AdminBackupInfo {
  backup_id: string;
  kind: AdminDocumentKind;
  created_at: string;
  size: number;
}

export interface RestoreAdminBackupPayload {
  backup_id: string;
  revision: string;
  apply: boolean;
}

export interface AdminMarketSummary {
  pair: string;
  base: string;
  quote: string;
  last: number | null;
  quote_volume: number | null;
  percentage: number | null;
}

export interface AdminMarketsResponse {
  exchange: string;
  stake_currency: string;
  updated_at: string;
  markets: AdminMarketSummary[];
}
