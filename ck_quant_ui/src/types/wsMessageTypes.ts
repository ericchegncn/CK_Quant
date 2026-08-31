export enum FtWsMessageTypes {
  exception = 'exception',

  whitelist = 'whitelist',
  entryFill = 'entry_fill',
  entryCancel = 'entry_cancel',

  exitFill = 'exit_fill',
  exitCancel = 'exit_cancel',
  newCandle = 'new_candle',

  // 4.4 应用层心跳响应（后端 PING/PONG）
  pong = 'pong',
}

export interface FtBaseWsMessage {
  type: FtWsMessageTypes;
}

export interface FtBaseEntryExitFillMessage extends FtBaseWsMessage {
  pair: string;
  open_rate: number;
  amount: number;
  direction: string;
  // ...
}

export interface FtWhitelistMessage extends FtBaseWsMessage {
  type: FtWsMessageTypes.whitelist;
  data: string[];
}

export interface FtEntryFillMessage extends FtBaseEntryExitFillMessage {
  type: FtWsMessageTypes.entryFill;
}

export interface FtExitFillMessage extends FtBaseEntryExitFillMessage {
  type: FtWsMessageTypes.exitFill;
}

export interface FTEntryCancelMessage extends FtBaseEntryExitFillMessage {
  type: FtWsMessageTypes.entryCancel;
  reason: string;
  // ...
}

export interface FTExitCancelMessage extends FtBaseEntryExitFillMessage {
  type: FtWsMessageTypes.exitCancel;
  reason: string;
  // ...
}

export interface FtNewCandleMessage extends FtBaseWsMessage {
  type: FtWsMessageTypes.newCandle;
  /** Pair, timeframe, candletype*/
  data: [string, string, string];
  // ...
}

export interface FtErrorMessage extends FtBaseWsMessage {
  type: FtWsMessageTypes.exception;
  data: string;
}

export interface FtPongMessage extends FtBaseWsMessage {
  type: FtWsMessageTypes.pong;
  data: string;
}

export type FTWsMessage =
  | FtErrorMessage
  | FtPongMessage
  | FtWhitelistMessage
  | FtEntryFillMessage
  | FTEntryCancelMessage
  | FtExitFillMessage
  | FTExitCancelMessage
  | FtNewCandleMessage;
