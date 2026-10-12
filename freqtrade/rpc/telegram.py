# pragma pylint: disable=unused-argument, unused-variable, protected-access, invalid-name

"""
This module manage Telegram communication
"""

import asyncio
import json
import logging
import re
from collections.abc import Callable, Coroutine
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial, wraps
from html import escape
from itertools import chain
from math import isnan
from threading import Thread
from typing import Any, Literal

from tabulate import tabulate
from telegram import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import MessageLimit, ParseMode
from telegram.error import BadRequest, NetworkError, TelegramError
from telegram.ext import Application, CallbackContext, CallbackQueryHandler, CommandHandler
from telegram.helpers import escape_markdown

from freqtrade.__init__ import __version__
from freqtrade.constants import DUST_PER_COIN, Config
from freqtrade.enums import MarketDirection, RPCMessageType, SignalDirection, TradingMode
from freqtrade.exceptions import OperationalException
from freqtrade.misc import chunks, plural
from freqtrade.persistence import Trade
from freqtrade.rpc import RPC, RPCException, RPCHandler
from freqtrade.rpc.i18n import SUPPORTED_LOCALES, I18n
from freqtrade.rpc.rpc_types import (
    RPCEntryMsg,
    RPCExitMsg,
    RPCLiquidationWarningMsg,
    RPCOrderMsg,
    RPCSendMsg,
)
from freqtrade.util import (
    dt_from_ts,
    dt_humanize_delta,
    fmt_coin,
    fmt_coin2,
    format_date,
    format_pct,
    round_value,
)
from freqtrade.util.datetime_helpers import dt_now


MAX_MESSAGE_LENGTH = MessageLimit.MAX_TEXT_LENGTH


logger = logging.getLogger(__name__)

logger.debug("Included module rpc.telegram ...")


def safe_async_db(func: Callable[..., Any]):
    """
    Decorator to safely handle sessions when switching async context
    :param func: function to decorate
    :return: decorated function
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        """Decorator logic"""
        try:
            return func(*args, **kwargs)
        finally:
            Trade.session.remove()

    return wrapper


@dataclass
class TimeunitMappings:
    header: str
    message: str
    message2: str
    callback: str
    default: int
    dateformat: str


def authorized_only(command_handler: Callable[..., Coroutine[Any, Any, None]]):
    """
    Decorator to check if the message comes from the correct chat_id
    can only be used with Telegram Class to decorate instance methods.
    :param command_handler: Telegram CommandHandler
    :return: decorated function
    """

    @wraps(command_handler)
    async def wrapper(self, *args, **kwargs) -> None:
        """Decorator logic"""
        update = kwargs.get("update") or args[0]

        # Reject unauthorized messages
        message: Message = (
            update.message if update.callback_query is None else update.callback_query.message
        )
        cchat_id: int = int(message.chat_id)
        ctopic_id: int | None = message.message_thread_id
        from_user_id: str = str(update.effective_user.id if update.effective_user else "")

        chat_id = int(self._config["telegram"]["chat_id"])
        if cchat_id != chat_id:
            logger.info(f"Rejected unauthorized message from: {cchat_id}")
            return None
        topic_id = self._config["telegram"].get("topic_id")
        if topic_id is not None and str(ctopic_id) != topic_id:
            # This can be quite common in multi-topic environments.
            logger.debug(f"Rejected message from wrong channel: {cchat_id}, {ctopic_id}")
            return None

        authorized = self._config["telegram"].get("authorized_users", None)
        if authorized is not None and from_user_id not in authorized:
            logger.info(f"Unauthorized user tried to control the bot: {from_user_id}")
            return None
        # Rollback session to avoid getting data stored in a transaction.
        Trade.rollback()
        logger.debug("Executing handler: %s for chat_id: %s", command_handler.__name__, chat_id)
        try:
            return await command_handler(self, *args, **kwargs)
        except RPCException as e:
            await self._send_msg(str(e))
        except BaseException:
            logger.exception("Exception occurred within Telegram module")
        finally:
            Trade.session.remove()

    return wrapper


class Telegram(RPCHandler):
    """This class handles all telegram communication"""

    def __init__(self, rpc: RPC, config: Config) -> None:
        """
        Init the Telegram call, and init the super class RPCHandler
        :param rpc: instance of RPC Helper class
        :param config: Configuration object
        :return: None
        """
        super().__init__(rpc, config)

        self._app: Application
        self._loop: asyncio.AbstractEventLoop
        # All user facing strings (notifications and commands) are
        # translated through this catalogue.  Locale 'en' reproduces the
        # historic output byte for byte.
        self._i18n = I18n(config)
        self._init_keyboard()
        self._start_thread()

    def _start_thread(self):
        """
        Creates and starts the polling thread
        """
        self._thread = Thread(target=self._init, name="FTTelegram")
        self._thread.start()

    def _t(self, key: str, chat_id: int | str | None = None, **kwargs: Any) -> str:
        """Translate a user facing message key for ``chat_id``."""
        return self._i18n.t(key, chat_id=chat_id, **kwargs)

    @property
    def _chat_id(self) -> int | str | None:
        """Chat notifications are sent to (locale source for messages)."""
        return self._config["telegram"]["chat_id"]

    @staticmethod
    def _update_chat_id(update: Update) -> int | str | None:
        """Chat id of an incoming command (locale source for commands)."""
        return update.effective_chat.id if getattr(update, "effective_chat", None) else None

    def _init_keyboard(self) -> None:
        """
        Validates the keyboard configuration from telegram config
        section.
        """
        self._keyboard: list[list[str | KeyboardButton]] = [
            ["/daily", "/profit", "/balance"],
            ["/status", "/status table", "/performance"],
            ["/count", "/start", "/stop", "/help"],
        ]
        # do not allow commands with mandatory arguments and critical cmds
        # TODO: DRY! - its not good to list all valid cmds here. But otherwise
        #       this needs refactoring of the whole telegram module (same
        #       problem in _help()).
        valid_keys: list[str] = [
            r"/start$",
            r"/pause$",
            r"/stop$",
            r"/status$",
            r"/status table$",
            r"/trades$",
            r"/performance$",
            r"/buys",
            r"/entries",
            r"/sells",
            r"/exits",
            r"/mix_tags",
            r"/daily$",
            r"/daily \d+$",
            r"/profit([_ ]long|[_ ]short)?$",
            r"/profit([_ ]long|[_ ]short)? \d+$",
            r"/stats$",
            r"/count$",
            r"/locks$",
            r"/balance$",
            r"/stopbuy$",
            r"/stopentry$",
            r"/reload_config$",
            r"/show_config$",
            r"/logs$",
            r"/whitelist$",
            r"/whitelist(\ssorted|\sbaseonly)+$",
            r"/blacklist$",
            r"/bl_delete$",
            r"/weekly$",
            r"/weekly \d+$",
            r"/monthly$",
            r"/monthly \d+$",
            r"/forcebuy$",
            r"/forcelong$",
            r"/forceshort$",
            r"/forcesell$",
            r"/forceexit$",
            r"/health$",
            r"/help$",
            r"/version$",
            r"/language$",
            r"/language .+$",
            r"/lang$",
            r"/lang .+$",
            r"/marketdir (long|short|even|none)$",
            r"/marketdir$",
        ]
        # Create keys for generation
        valid_keys_print = [k.replace("$", "") for k in valid_keys]

        # custom keyboard specified in config.json
        cust_keyboard = self._config["telegram"].get("keyboard", [])
        if cust_keyboard:
            combined = "(" + ")|(".join(valid_keys) + ")"
            # check for valid shortcuts
            invalid_keys = [
                b for b in chain.from_iterable(cust_keyboard) if not re.match(combined, b)
            ]
            if len(invalid_keys):
                err_msg = (
                    "config.telegram.keyboard: Invalid commands for "
                    f"custom Telegram keyboard: {invalid_keys}"
                    f"\nvalid commands are: {valid_keys_print}"
                )
                raise OperationalException(err_msg)
            else:
                self._keyboard = cust_keyboard
                logger.info(f"using custom keyboard from config.json: {self._keyboard}")

    def _init_telegram_app(self):
        return Application.builder().token(self._config["telegram"]["token"]).build()

    def _init(self) -> None:
        """
        Initializes this module with the given config,
        registers all known command handlers
        and starts polling for message updates
        Runs in a separate thread.
        """
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

        self._app = self._init_telegram_app()

        # Register command handler and start telegram message polling
        handles = [
            CommandHandler("status", self._status),
            CommandHandler("profit", self._profit),
            CommandHandler("balance", self._balance),
            CommandHandler("start", self._start),
            CommandHandler("stop", self._stop),
            CommandHandler(["forcesell", "forceexit", "fx"], self._force_exit),
            CommandHandler(
                ["forcebuy", "forcelong"],
                partial(self._force_enter, order_side=SignalDirection.LONG),
            ),
            CommandHandler(
                "forceshort", partial(self._force_enter, order_side=SignalDirection.SHORT)
            ),
            CommandHandler("reload_trade", self._reload_trade_from_exchange),
            CommandHandler("trades", self._trades),
            CommandHandler("delete", self._delete_trade),
            CommandHandler(["coo", "cancel_open_order"], self._cancel_open_order),
            CommandHandler("performance", self._performance),
            CommandHandler(["buys", "entries"], self._enter_tag_performance),
            CommandHandler(["sells", "exits"], self._exit_reason_performance),
            CommandHandler("mix_tags", self._mix_tag_performance),
            CommandHandler("stats", self._stats),
            CommandHandler("daily", self._daily),
            CommandHandler("weekly", self._weekly),
            CommandHandler("monthly", self._monthly),
            CommandHandler("count", self._count),
            CommandHandler("locks", self._locks),
            CommandHandler(["unlock", "delete_locks"], self._delete_locks),
            CommandHandler(["reload_config", "reload_conf"], self._reload_config),
            CommandHandler(["show_config", "show_conf"], self._show_config),
            CommandHandler(["stopbuy", "stopentry", "pause"], self._pause),
            CommandHandler("whitelist", self._whitelist),
            CommandHandler("blacklist", self._blacklist),
            CommandHandler(["blacklist_delete", "bl_delete"], self._blacklist_delete),
            CommandHandler("logs", self._logs),
            CommandHandler("health", self._health),
            CommandHandler("help", self._help),
            CommandHandler("version", self._version),
            CommandHandler(["language", "lang"], self._language),
            CommandHandler("marketdir", self._changemarketdir),
            CommandHandler("order", self._order),
            CommandHandler("list_custom_data", self._list_custom_data),
            CommandHandler("tg_info", self._tg_info),
            CommandHandler("profit_long", self._profit_long),
            CommandHandler("profit_short", self._profit_short),
        ]
        callbacks = [
            CallbackQueryHandler(self._status_table, pattern="update_status_table"),
            CallbackQueryHandler(self._daily, pattern="update_daily"),
            CallbackQueryHandler(self._weekly, pattern="update_weekly"),
            CallbackQueryHandler(self._monthly, pattern="update_monthly"),
            CallbackQueryHandler(self._profit_long, pattern="update_profit_long"),
            CallbackQueryHandler(self._profit_short, pattern="update_profit_short"),
            CallbackQueryHandler(self._profit, pattern=r"update_profit$"),
            CallbackQueryHandler(self._balance, pattern="update_balance"),
            CallbackQueryHandler(self._performance, pattern="update_performance"),
            CallbackQueryHandler(
                self._enter_tag_performance, pattern="update_enter_tag_performance"
            ),
            CallbackQueryHandler(
                self._exit_reason_performance, pattern="update_exit_reason_performance"
            ),
            CallbackQueryHandler(self._mix_tag_performance, pattern="update_mix_tag_performance"),
            CallbackQueryHandler(self._count, pattern="update_count"),
            CallbackQueryHandler(self._force_exit_inline, pattern=r"force_exit__\S+"),
            CallbackQueryHandler(self._force_enter_inline, pattern=r"force_enter__\S+"),
        ]
        for handle in handles:
            self._app.add_handler(handle)

        for callback in callbacks:
            self._app.add_handler(callback)

        logger.info(
            "rpc.telegram is listening for following commands: %s",
            [[x for x in sorted(h.commands)] for h in handles],
        )
        self._loop.run_until_complete(self._startup_telegram())

    async def _startup_telegram(self) -> None:
        retries = 3
        attempt = 0
        while attempt < retries:
            try:
                await self._app.initialize()
                await self._app.start()
                break
            except Exception as ex:
                logger.error(
                    "Error starting Telegram bot (attempt %d/%d): %s", attempt + 1, retries, ex
                )
                attempt += 1
                if attempt == retries:
                    logger.warning("Telegram init failed.")
                    return
                await asyncio.sleep(2)
        if self._app.updater:
            await self._app.updater.start_polling(
                bootstrap_retries=10,
                timeout=20,
                drop_pending_updates=True,
            )
            while True:
                await asyncio.sleep(10)
                if not self._app.updater.running:
                    break

    async def _cleanup_telegram(self) -> None:
        if self._app.updater:
            await self._app.updater.stop()
        await self._app.stop()
        await self._app.shutdown()

    def cleanup(self) -> None:
        """
        Stops all running telegram threads.
        :return: None
        """
        # This can take up to `timeout` from the call to `start_polling`.
        asyncio.run_coroutine_threadsafe(self._cleanup_telegram(), self._loop)
        self._thread.join()

    def _exchange_from_msg(self, msg: RPCOrderMsg | RPCLiquidationWarningMsg) -> str:
        """
        Extracts the exchange name from the given message.
        :param msg: The message to extract the exchange name from.
        :return: The exchange name.
        """
        dry_suffix = (
            self._t("tg.common.dry_suffix", chat_id=self._chat_id)
            if self._config["dry_run"]
            else ""
        )
        return self._t(
            "tg.common.exchange",
            chat_id=self._chat_id,
            exchange=msg["exchange"],
            dry=dry_suffix,
        )

    def _add_analyzed_candle(self, pair: str) -> str:
        candle_val = (
            self._config["telegram"].get("notification_settings", {}).get("show_candle", "off")
        )
        if candle_val != "off" and candle_val == "ohlc":
            analyzed_df, _ = self._rpc._freqtrade.dataprovider.get_analyzed_dataframe(
                pair, self._config["timeframe"]
            )
            candle = analyzed_df.iloc[-1].squeeze() if len(analyzed_df) > 0 else None
            if candle is not None:
                ohlc = f"{candle['open']}, {candle['high']}, "
                ohlc += f"{candle['low']}, {candle['close']}"
                return self._t("tg.common.candle_ohlc", chat_id=self._chat_id, ohlc=ohlc)

        return ""

    def _format_entry_msg(self, msg: RPCEntryMsg) -> str:
        is_fill = msg["type"] in [RPCMessageType.ENTRY_FILL]
        emoji = "\N{CHECK MARK}" if is_fill else "\N{LARGE BLUE CIRCLE}"

        terminology = {
            "1_enter": "tg.entry.new_trade",
            "1_entered": "tg.entry.new_trade_filled",
            "x_enter": "tg.entry.increasing_position",
            "x_entered": "tg.entry.position_increase_filled",
        }

        key = f"{'x' if msg['sub_trade'] else '1'}_{'entered' if is_fill else 'enter'}"
        wording = self._t(terminology[key], chat_id=self._chat_id)

        message = self._t(
            "tg.entry.header",
            chat_id=self._chat_id,
            emoji=emoji,
            exchange=self._exchange_from_msg(msg),
            wording=wording,
            trade_id=msg["trade_id"],
        )
        message += self._t("tg.common.pair", chat_id=self._chat_id, pair=msg["pair"])
        message += self._add_analyzed_candle(msg["pair"])
        if msg.get("enter_tag"):
            message += self._t(
                "tg.common.enter_tag", chat_id=self._chat_id, enter_tag=msg["enter_tag"]
            )
        message += self._t(
            "tg.common.amount", chat_id=self._chat_id, amount=round_value(msg["amount"], 8)
        )
        leverage = (
            f" ({msg['leverage']:.3g}x)"
            if msg.get("leverage") and msg.get("leverage", 1.0) != 1.0
            else ""
        )
        message += self._t(
            "tg.common.direction",
            chat_id=self._chat_id,
            direction=msg["direction"],
            leverage=leverage,
        )
        message += self._t(
            "tg.common.open_rate",
            chat_id=self._chat_id,
            rate=fmt_coin2(msg["open_rate"], msg["quote_currency"]),
        )
        if msg["type"] == RPCMessageType.ENTRY and msg["current_rate"]:
            message += self._t(
                "tg.common.current_rate",
                chat_id=self._chat_id,
                rate=fmt_coin2(msg["current_rate"], msg["quote_currency"]),
            )

        profit_fiat_extra = self.__format_profit_fiat(msg, "stake_amount")  # type: ignore
        total = fmt_coin(msg["stake_amount"], msg["quote_currency"])

        message += self._t(
            "tg.entry.new_total" if msg["sub_trade"] else "tg.entry.total",
            chat_id=self._chat_id,
            total=total,
            fiat=profit_fiat_extra,
        )

        return message

    def _format_exit_msg(self, msg: RPCExitMsg) -> str:
        duration = msg["close_date"].replace(microsecond=0) - msg["open_date"].replace(
            microsecond=0
        )
        duration_min = duration.total_seconds() / 60

        leverage_text = (
            f" ({msg['leverage']:.3g}x)"
            if msg.get("leverage") and msg.get("leverage", 1.0) != 1.0
            else ""
        )

        profit_fiat_extra = self.__format_profit_fiat(msg, "profit_amount")

        profit_extra = self._t(
            "tg.common.profit_extra",
            chat_id=self._chat_id,
            gain=msg["gain"],
            amount=fmt_coin(msg["profit_amount"], msg["quote_currency"]),
            fiat=profit_fiat_extra,
        )

        is_fill = msg["type"] == RPCMessageType.EXIT_FILL
        is_sub_trade = msg.get("sub_trade")
        is_sub_profit = msg["profit_amount"] != msg.get("cumulative_profit")
        is_final_exit = msg.get("is_final_exit", False) and is_sub_profit
        profit_prefix = "Sub " if is_sub_trade else ""
        cp_extra = ""
        exit_wording = (
            self._t("tg.exit.exited", chat_id=self._chat_id)
            if is_fill
            else self._t("tg.exit.exiting", chat_id=self._chat_id)
        )
        if is_sub_trade or is_final_exit:
            cp_fiat = self.__format_profit_fiat(msg, "cumulative_profit")

            if is_final_exit:
                profit_prefix = "Sub "
                cp_extra = self._t(
                    "tg.exit.final_profit",
                    chat_id=self._chat_id,
                    ratio=format_pct(msg["final_profit_ratio"]),
                    amount=fmt_coin(msg["cumulative_profit"], msg["stake_currency"]),
                    fiat=cp_fiat,
                )
            else:
                exit_wording = (
                    self._t("tg.exit.partially_exited", chat_id=self._chat_id)
                    if is_fill
                    else self._t("tg.exit.partially_exiting", chat_id=self._chat_id)
                )
                if msg["cumulative_profit"]:
                    cp_extra = self._t(
                        "tg.exit.cumulative_profit",
                        chat_id=self._chat_id,
                        amount=fmt_coin(msg["cumulative_profit"], msg["stake_currency"]),
                        fiat=cp_fiat,
                    )
        enter_tag = (
            self._t("tg.common.enter_tag", chat_id=self._chat_id, enter_tag=msg["enter_tag"])
            if msg.get("enter_tag")
            else ""
        )
        if is_fill:
            profit_label = "tg.exit.sub_profit" if profit_prefix else "tg.exit.profit"
        else:
            profit_label = (
                "tg.exit.unrealized_sub_profit" if profit_prefix else "tg.exit.unrealized_profit"
            )
        message = (
            self._t(
                "tg.exit.header",
                chat_id=self._chat_id,
                emoji=self._get_exit_emoji(msg),
                exchange=self._exchange_from_msg(msg),
                wording=exit_wording,
                pair=msg["pair"],
                trade_id=msg["trade_id"],
            )
            + self._add_analyzed_candle(msg["pair"])
            + self._t(
                "tg.exit.profit_line",
                chat_id=self._chat_id,
                label=self._t(profit_label, chat_id=self._chat_id),
                ratio=format_pct(msg["profit_ratio"]),
                extra=profit_extra,
            )
            + f"{cp_extra}"
            + f"{enter_tag}"
            + self._t("tg.exit.exit_reason", chat_id=self._chat_id, reason=msg["exit_reason"])
            + self._t(
                "tg.common.direction",
                chat_id=self._chat_id,
                direction=msg["direction"],
                leverage=leverage_text,
            )
            + self._t(
                "tg.common.amount", chat_id=self._chat_id, amount=round_value(msg["amount"], 8)
            )
            + self._t(
                "tg.common.open_rate",
                chat_id=self._chat_id,
                rate=fmt_coin2(msg["open_rate"], msg["quote_currency"]),
            )
        )
        if msg["type"] == RPCMessageType.EXIT and msg["current_rate"]:
            message += self._t(
                "tg.common.current_rate",
                chat_id=self._chat_id,
                rate=fmt_coin2(msg["current_rate"], msg["quote_currency"]),
            )
            if msg["order_rate"]:
                message += self._t(
                    "tg.exit.exit_rate",
                    chat_id=self._chat_id,
                    rate=fmt_coin2(msg["order_rate"], msg["quote_currency"]),
                )
        elif msg["type"] == RPCMessageType.EXIT_FILL:
            message += self._t(
                "tg.exit.exit_rate",
                chat_id=self._chat_id,
                rate=fmt_coin2(msg["close_rate"], msg["quote_currency"]),
            )

        if is_sub_trade:
            stake_amount_fiat = self.__format_profit_fiat(msg, "stake_amount")

            rem = fmt_coin(msg["stake_amount"], msg["quote_currency"])
            message += self._t(
                "tg.exit.remaining",
                chat_id=self._chat_id,
                amount=rem,
                fiat=stake_amount_fiat,
            )
        else:
            message += self._t(
                "tg.exit.duration",
                chat_id=self._chat_id,
                duration=duration,
                minutes=f"{duration_min:.1f}",
            )
        return message

    def __format_profit_fiat(
        self, msg: RPCExitMsg, key: Literal["stake_amount", "profit_amount", "cumulative_profit"]
    ) -> str:
        """
        Format Fiat currency to append to regular profit output
        """
        profit_fiat_extra = ""
        if self._rpc._fiat_converter and (fiat_currency := msg.get("fiat_currency")):
            profit_fiat = self._rpc._fiat_converter.convert_amount(
                msg[key], msg["stake_currency"], fiat_currency
            )
            profit_fiat_extra = self._t(
                "tg.common.fiat_extra",
                chat_id=self._chat_id,
                amount=f"{profit_fiat:.3f}",
                currency=fiat_currency,
            )
        return profit_fiat_extra

    def _format_liquidation_warning_msg(self, msg: RPCLiquidationWarningMsg) -> str:
        direction = msg["direction"]
        if msg.get("leverage") and msg.get("leverage", 1.0) != 1.0:
            direction += f" ({msg['leverage']:.3g}x)"

        if msg["margin_mode"] == "cross":
            single = msg["positions_at_risk"] == 1
            headline = self._t(
                "tg.liquidation.headline_cross",
                chat_id=self._chat_id,
                emoji="\N{WARNING SIGN}",
                exchange=self._exchange_from_msg(msg),
                positions_at_risk=msg["positions_at_risk"],
                open_positions=msg["open_positions"],
                verb=self._t(
                    "tg.liquidation.verb_is" if single else "tg.liquidation.verb_are",
                    chat_id=self._chat_id,
                ),
                possessive=self._t(
                    "tg.liquidation.poss_its" if single else "tg.liquidation.poss_their",
                    chat_id=self._chat_id,
                ),
                pair=msg["pair"],
                trade_id=msg["trade_id"],
            )
            advice = self._t("tg.liquidation.advice_cross", chat_id=self._chat_id)
        else:
            headline = self._t(
                "tg.liquidation.headline_isolated",
                chat_id=self._chat_id,
                emoji="\N{WARNING SIGN}",
                exchange=self._exchange_from_msg(msg),
                pair=msg["pair"],
                trade_id=msg["trade_id"],
            )
            advice = self._t("tg.liquidation.advice_isolated", chat_id=self._chat_id)

        return (
            headline
            + self._t(
                "tg.common.direction",
                chat_id=self._chat_id,
                direction=direction,
                leverage="",
            )
            + self._t(
                "tg.common.current_rate",
                chat_id=self._chat_id,
                rate=fmt_coin2(msg["current_rate"], msg["quote_currency"]),
            )
            + self._t(
                "tg.liquidation.liquidation_stop",
                chat_id=self._chat_id,
                price=fmt_coin2(msg["liquidation_price"], msg["quote_currency"]),
            )
            + self._t(
                "tg.liquidation.remaining",
                chat_id=self._chat_id,
                ratio=f"{msg['remaining_ratio']:.2%}",
            )
            + self._t("tg.liquidation.footer", chat_id=self._chat_id, advice=advice)
        )

    def compose_message(self, msg: RPCSendMsg) -> str | None:
        if msg["type"] == RPCMessageType.ENTRY or msg["type"] == RPCMessageType.ENTRY_FILL:
            message = self._format_entry_msg(msg)

        elif msg["type"] == RPCMessageType.EXIT or msg["type"] == RPCMessageType.EXIT_FILL:
            message = self._format_exit_msg(msg)

        elif (
            msg["type"] == RPCMessageType.ENTRY_CANCEL or msg["type"] == RPCMessageType.EXIT_CANCEL
        ):
            message_side = (
                self._t("tg.common.enter_order", chat_id=self._chat_id)
                if msg["type"] == RPCMessageType.ENTRY_CANCEL
                else self._t("tg.common.exit_order", chat_id=self._chat_id)
            )
            partial = (
                self._t("tg.common.partial_prefix", chat_id=self._chat_id)
                if msg.get("sub_trade")
                else ""
            )
            message = self._t(
                "tg.cancel.order",
                chat_id=self._chat_id,
                emoji="\N{WARNING SIGN}",
                exchange=self._exchange_from_msg(msg),
                partial=partial,
                side=message_side,
                pair=msg["pair"],
                trade_id=msg["trade_id"],
                reason=msg["reason"],
            )

        elif msg["type"] == RPCMessageType.PROTECTION_TRIGGER:
            message = self._t(
                "tg.protection.trigger",
                chat_id=self._chat_id,
                reason=msg["reason"],
                pair=msg["pair"],
                lock_end_time=msg["lock_end_time"],
            )

        elif msg["type"] == RPCMessageType.PROTECTION_TRIGGER_GLOBAL:
            message = self._t(
                "tg.protection.trigger_global",
                chat_id=self._chat_id,
                reason=msg["reason"],
                lock_end_time=msg["lock_end_time"],
            )

        elif msg["type"] == RPCMessageType.LIQUIDATION_WARNING:
            message = self._format_liquidation_warning_msg(msg)

        elif msg["type"] == RPCMessageType.STATUS:
            message = self._t("tg.common.status_msg", chat_id=self._chat_id, status=msg["status"])

        elif msg["type"] == RPCMessageType.WARNING:
            message = self._t(
                "tg.common.warning",
                chat_id=self._chat_id,
                emoji="\N{WARNING SIGN}",
                status=msg["status"],
            )
        elif msg["type"] == RPCMessageType.EXCEPTION:
            # Errors will contain exceptions, which are wrapped in triple ticks.
            message = self._t(
                "tg.common.error",
                chat_id=self._chat_id,
                emoji="\N{WARNING SIGN}",
                status=msg["status"],
            )

        elif msg["type"] == RPCMessageType.STARTUP:
            message = f"{msg['status']}"
        elif msg["type"] == RPCMessageType.STRATEGY_MSG:
            message = f"{msg['msg']}"
        else:
            logger.debug("Unknown message type: %s", msg["type"])
            return None
        return message

    def _message_loudness(self, msg: RPCSendMsg) -> str:
        """Determine the loudness of the message - on, off or silent"""
        default_noti = "on"

        msg_type = msg["type"]
        noti = ""
        if msg["type"] == RPCMessageType.EXIT or msg["type"] == RPCMessageType.EXIT_FILL:
            sell_noti = (
                self._config["telegram"].get("notification_settings", {}).get(str(msg_type), {})
            )

            # For backward compatibility sell still can be string
            if isinstance(sell_noti, str):
                noti = sell_noti
            else:
                default_noti = sell_noti.get("*", default_noti)
                noti = sell_noti.get(str(msg["exit_reason"]), default_noti)
        else:
            noti = (
                self._config["telegram"]
                .get("notification_settings", {})
                .get(str(msg_type), default_noti)
            )

        return noti

    def send_msg(self, msg: RPCSendMsg) -> None:
        """Send a message to telegram channel"""
        noti = self._message_loudness(msg)

        if noti == "off":
            logger.info(f"Notification '{msg['type']}' not sent.")
            # Notification disabled
            return

        message = self.compose_message(deepcopy(msg))
        if message:
            asyncio.run_coroutine_threadsafe(
                self._send_msg(message, disable_notification=(noti == "silent")), self._loop
            )

    def _get_exit_emoji(self, msg):
        """
        Get emoji for exit-messages
        """

        if float(msg["profit_ratio"]) >= 0.05:
            return "\N{ROCKET}"
        elif float(msg["profit_ratio"]) >= 0.0:
            return "\N{EIGHT SPOKED ASTERISK}"
        elif msg["exit_reason"] == "stop_loss":
            return "\N{WARNING SIGN}"
        else:
            return "\N{CROSS MARK}"

    def _prepare_order_details(self, filled_orders: list, quote_currency: str, is_open: bool):
        """
        Prepare details of trade with entry adjustment enabled
        """
        lines_detail: list[str] = []
        if len(filled_orders) > 0:
            first_avg = filled_orders[0]["safe_price"]
        order_nr = 0
        for order in filled_orders:
            lines: list[str] = []
            if order["is_open"] is True:
                continue
            order_nr += 1
            wording = (
                self._t("tg.order.entry", chat_id=self._chat_id)
                if order["ft_is_entry"]
                else self._t("tg.order.exit", chat_id=self._chat_id)
            )

            cur_entry_amount = order["filled"] or order["amount"]
            cur_entry_average = order["safe_price"]
            lines.append("  ")
            lines.append(
                self._t(
                    "tg.order.header",
                    chat_id=self._chat_id,
                    wording=wording,
                    nr=order_nr,
                )
            )
            if order_nr == 1:
                lines.append(
                    self._t(
                        "tg.order.amount",
                        chat_id=self._chat_id,
                        amount=round_value(cur_entry_amount, 8),
                        cost=fmt_coin(order["cost"], quote_currency),
                    )
                )
                lines.append(
                    self._t(
                        "tg.order.average_price",
                        chat_id=self._chat_id,
                        price=round_value(cur_entry_average, 8),
                    )
                )
            else:
                # TODO: This calculation ignores fees.
                price_to_1st_entry = (cur_entry_average - first_avg) / first_avg
                if is_open:
                    lines.append(f"({dt_humanize_delta(order['order_filled_date'])})")
                lines.append(
                    self._t(
                        "tg.order.amount",
                        chat_id=self._chat_id,
                        amount=round_value(cur_entry_amount, 8),
                        cost=fmt_coin(order["cost"], quote_currency),
                    )
                )
                lines.append(
                    self._t(
                        "tg.order.average_entry_price",
                        chat_id=self._chat_id,
                        wording=wording,
                        price=round_value(cur_entry_average, 8),
                        ratio=format_pct(price_to_1st_entry),
                    )
                )
                lines.append(
                    self._t(
                        "tg.order.order_filled",
                        chat_id=self._chat_id,
                        date=order["order_filled_date"],
                    )
                )

            lines_detail.append("\n".join(lines))

        return lines_detail

    @authorized_only
    async def _order(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /order.
        Returns the orders of the trade
        :param bot: telegram bot
        :param update: message update
        :return: None
        """

        trade_ids = []
        if context.args and len(context.args) > 0:
            trade_ids = [int(i) for i in context.args if i.isnumeric()]

        results = self._rpc._rpc_trade_status(trade_ids=trade_ids)
        for r in results:
            lines = [
                self._t(
                    "tg.order.list_header",
                    chat_id=self._update_chat_id(update),
                    trade_id=r["trade_id"],
                )
            ]

            lines_detail = self._prepare_order_details(
                r["orders"], r["quote_currency"], r["is_open"]
            )
            lines.extend(lines_detail if lines_detail else "")
            await self.__send_order_msg(lines, r, self._update_chat_id(update))

    async def __send_order_msg(
        self,
        lines: list[str],
        r: dict[str, Any],
        chat_id: int | str | None = None,
    ) -> None:
        """
        Send status message.
        """
        msg = ""

        for line in lines:
            if line:
                if (len(msg) + len(line) + 1) < MAX_MESSAGE_LENGTH:
                    msg += line + "\n"
                else:
                    await self._send_msg(msg)
                    msg = (
                        self._t(
                            "tg.order.list_header_continued",
                            chat_id=chat_id,
                            trade_id=r["trade_id"],
                        )
                        + line
                        + "\n"
                    )

        await self._send_msg(msg)

    @authorized_only
    async def _status(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /status.
        Returns the current TradeThread status
        :param bot: telegram bot
        :param update: message update
        :return: None
        """

        if context.args and "table" in context.args:
            await self._status_table(update, context)
            return
        else:
            await self._status_msg(update, context)

    async def _status_msg(self, update: Update, context: CallbackContext) -> None:
        """
        handler for `/status` and `/status <id>`.

        """
        # Check if there's at least one numerical ID provided.
        # If so, try to get only these trades.
        trade_ids = []
        if context.args and len(context.args) > 0:
            trade_ids = [int(i) for i in context.args if i.isnumeric()]

        results = self._rpc._rpc_trade_status(trade_ids=trade_ids)
        position_adjust = self._config.get("position_adjustment_enable", False)
        max_entries = self._config.get("max_entry_position_adjustment", -1)
        chat_id = self._update_chat_id(update)
        for r in results:
            r["open_date_hum"] = dt_humanize_delta(r["open_date"])

            r["stake_amount_r"] = fmt_coin(r["stake_amount"], r["quote_currency"])
            r["max_stake_amount_r"] = fmt_coin(
                r["max_stake_amount"] or r["stake_amount"], r["quote_currency"]
            )
            r["profit_abs_r"] = fmt_coin(r["profit_abs"], r["quote_currency"])
            r["realized_profit_r"] = fmt_coin(r["realized_profit"], r["quote_currency"])
            r["total_profit_abs_r"] = fmt_coin(r["total_profit_abs"], r["quote_currency"])
            direction_word = self._t(
                "tg.common.short" if r.get("is_short") else "tg.common.long", chat_id=chat_id
            )
            lines = [
                self._t("tg.status.trade_id", chat_id=chat_id, trade_id=r["trade_id"])
                + (
                    self._t(
                        "tg.status.trade_id_since",
                        chat_id=chat_id,
                        time=r["open_date_hum"],
                    )
                    if r["is_open"]
                    else ""
                ),
                self._t("tg.status.current_pair", chat_id=chat_id, pair=r["pair"]),
                self._t(
                    "tg.status.direction",
                    chat_id=chat_id,
                    direction=f"`{direction_word}`",
                    leverage=(f" ` ({r['leverage']}x)`" if r.get("leverage") else ""),
                ),
                self._t(
                    "tg.status.amount",
                    chat_id=chat_id,
                    amount=r["amount"],
                    stake=r["stake_amount_r"],
                ),
                (
                    self._t(
                        "tg.status.total_invested",
                        chat_id=chat_id,
                        amount=r["max_stake_amount_r"],
                    )
                    if position_adjust
                    else ""
                ),
                (
                    self._t("tg.status.enter_tag", chat_id=chat_id, enter_tag=r["enter_tag"])
                    if r["enter_tag"]
                    else ""
                ),
                (
                    self._t("tg.status.exit_reason", chat_id=chat_id, reason=r["exit_reason"])
                    if r.get("exit_reason")
                    else ""
                ),
            ]

            if position_adjust:
                max_buy_str = f"/{max_entries + 1}" if (max_entries > 0) else ""
                lines.extend(
                    [
                        self._t(
                            "tg.status.number_of_entries",
                            chat_id=chat_id,
                            count=r["nr_of_successful_entries"],
                            max_entries=max_buy_str,
                        ),
                        self._t(
                            "tg.status.number_of_exits",
                            chat_id=chat_id,
                            count=r["nr_of_successful_exits"],
                        ),
                    ]
                )

            lines.extend(
                [
                    self._t(
                        "tg.status.open_rate",
                        chat_id=chat_id,
                        rate=round_value(r["open_rate"], 8),
                    ),
                    (
                        self._t(
                            "tg.status.close_rate",
                            chat_id=chat_id,
                            rate=round_value(r["close_rate"], 8),
                        )
                        if r["close_rate"]
                        else ""
                    ),
                    self._t("tg.status.open_date", chat_id=chat_id, date=r["open_date"]),
                    (
                        self._t("tg.status.close_date", chat_id=chat_id, date=r["close_date"])
                        if r["close_date"]
                        else ""
                    ),
                    (
                        self._t(
                            "tg.status.current_rate",
                            chat_id=chat_id,
                            rate=round_value(r["current_rate"], 8),
                        )
                        if r["is_open"]
                        else ""
                    ),
                    self._t(
                        "tg.status.profit_open" if r["is_open"] else "tg.status.profit_closed",
                        chat_id=chat_id,
                        ratio=format_pct(r["profit_ratio"]),
                        amount=r["profit_abs_r"],
                    ),
                ]
            )

            if r["is_open"]:
                if (
                    r.get("realized_profit") is not None
                    and r.get("realized_profit_ratio") is not None
                ):
                    lines.append(
                        self._t(
                            "tg.status.realized_profit",
                            chat_id=chat_id,
                            ratio=format_pct(r["realized_profit_ratio"]),
                            amount=r["realized_profit_r"],
                        )
                    )
                if r.get("total_profit_ratio") is not None:
                    lines.append(
                        self._t(
                            "tg.status.total_profit",
                            chat_id=chat_id,
                            ratio=format_pct(r["total_profit_ratio"]),
                            amount=r["total_profit_abs_r"],
                        )
                    )

                # Append empty line to improve readability
                lines.append(" ")
                # Adding liquidation only if it is not None
                if liquidation := r.get("liquidation_price"):
                    lines.append(
                        self._t(
                            "tg.status.liquidation",
                            chat_id=chat_id,
                            price=round_value(liquidation, 8),
                        )
                    )

                if (
                    r["stop_loss_abs"] != r["initial_stop_loss_abs"]
                    and r["initial_stop_loss_ratio"] is not None
                ):
                    # Adding initial stoploss only if it is different from stoploss
                    lines.append(
                        self._t(
                            "tg.status.initial_stoploss",
                            chat_id=chat_id,
                            price=round_value(r["initial_stop_loss_abs"], 8),
                            ratio=format_pct(r["initial_stop_loss_ratio"]),
                        )
                    )

                # Adding stoploss and stoploss percentage only if it is not None
                lines.append(
                    self._t(
                        "tg.status.stoploss",
                        chat_id=chat_id,
                        price=round_value(r["stop_loss_abs"], 8),
                        ratio=(
                            f"`({format_pct(r['stop_loss_ratio'])})`"
                            if r["stop_loss_ratio"]
                            else ""
                        ),
                    )
                )
                lines.append(
                    self._t(
                        "tg.status.stoploss_distance",
                        chat_id=chat_id,
                        price=round_value(r["stoploss_current_dist"], 8),
                        ratio=format_pct(r["stoploss_current_dist_ratio"]),
                    )
                )
                if open_orders := r.get("open_orders"):
                    lines.append(
                        self._t(
                            "tg.status.open_order",
                            chat_id=chat_id,
                            orders=open_orders,
                            status=(
                                f"- `{r['exit_order_status']}`" if r["exit_order_status"] else ""
                            ),
                        )
                    )

            await self.__send_status_msg(lines, r, self._update_chat_id(update))

    async def __send_status_msg(
        self,
        lines: list[str],
        r: dict[str, Any],
        chat_id: int | str | None = None,
    ) -> None:
        """
        Send status message.
        """
        msg = ""

        for line in lines:
            if line:
                if (len(msg) + len(line) + 1) < MAX_MESSAGE_LENGTH:
                    msg += line + "\n"
                else:
                    await self._send_msg(msg)
                    msg = (
                        self._t(
                            "tg.status.trade_id_continued",
                            chat_id=chat_id,
                            trade_id=r["trade_id"],
                        )
                        + line
                        + "\n"
                    )

        await self._send_msg(msg)

    @authorized_only
    async def _status_table(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /status table.
        Returns the current TradeThread status in table format
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        fiat_currency = self._config.get("fiat_display_currency", "")
        statlist, head, fiat_profit_sum, fiat_total_profit_sum = self._rpc._rpc_status_table(
            self._config["stake_currency"], fiat_currency
        )

        chat_id = self._update_chat_id(update)
        show_total = not isnan(fiat_profit_sum) and len(statlist) > 1
        show_total_realized = (
            not isnan(fiat_total_profit_sum) and len(statlist) > 1 and fiat_profit_sum
        ) != fiat_total_profit_sum
        max_trades_per_msg = 50
        """
        Calculate the number of messages of 50 trades per message
        0.99 is used to make sure that there are no extra (empty) messages
        As an example with 50 trades, there will be int(50/50 + 0.99) = 1 message
        """
        messages_count = max(int(len(statlist) / max_trades_per_msg + 0.99), 1)
        for i in range(messages_count):
            trades = statlist[i * max_trades_per_msg : (i + 1) * max_trades_per_msg]
            if show_total and i == messages_count - 1:
                # append total line
                trades.append(
                    [
                        self._t("tg.status_table.total", chat_id=chat_id),
                        "",
                        "",
                        f"{fiat_profit_sum:.2f} {fiat_currency}",
                    ]
                )
                if show_total_realized:
                    trades.append(
                        [
                            self._t("tg.status_table.total", chat_id=chat_id),
                            self._t("tg.status_table.incl_realized", chat_id=chat_id),
                            "",
                            f"{fiat_total_profit_sum:.2f} {fiat_currency}",
                        ]
                    )

            message = tabulate(trades, headers=head, tablefmt="simple")
            if show_total and i == messages_count - 1:
                # insert separators line between Total
                lines = message.split("\n")
                offset = 2 if show_total_realized else 1
                message = "\n".join(lines[:-offset] + [lines[1]] + lines[-offset:])
            await self._send_msg(
                f"<pre>{message}</pre>",
                parse_mode=ParseMode.HTML,
                reload_able=True,
                callback_path="update_status_table",
                query=update.callback_query,
            )

    async def _timeunit_stats(self, update: Update, context: CallbackContext, unit: str) -> None:
        """
        Handler for /daily <n>
        Returns a daily profit (in BTC) over the last n days.
        :param bot: telegram bot
        :param update: message update
        :return: None
        """

        chat_id = self._update_chat_id(update)
        vals = {
            "days": TimeunitMappings(
                self._t("tg.timeunit.day", chat_id=chat_id),
                self._t("tg.timeunit.daily", chat_id=chat_id),
                self._t("tg.timeunit.days", chat_id=chat_id),
                "update_daily",
                7,
                "%Y-%m-%d",
            ),
            "weeks": TimeunitMappings(
                self._t("tg.timeunit.monday", chat_id=chat_id),
                self._t("tg.timeunit.weekly", chat_id=chat_id),
                self._t("tg.timeunit.weeks_monday", chat_id=chat_id),
                "update_weekly",
                8,
                "%Y-%m-%d",
            ),
            "months": TimeunitMappings(
                self._t("tg.timeunit.month", chat_id=chat_id),
                self._t("tg.timeunit.monthly", chat_id=chat_id),
                self._t("tg.timeunit.months", chat_id=chat_id),
                "update_monthly",
                6,
                "%Y-%m",
            ),
        }
        val = vals[unit]

        stake_cur = self._config["stake_currency"]
        fiat_disp_cur = self._config.get("fiat_display_currency", "")
        try:
            timescale = int(context.args[0]) if context.args else val.default
        except (TypeError, ValueError, IndexError):
            timescale = val.default
        stats = self._rpc._rpc_timeunit_profit(timescale, stake_cur, fiat_disp_cur, unit)
        stats_tab = tabulate(
            [
                [
                    f"{period['date']:{val.dateformat}} ({period['trade_count']})",
                    f"{fmt_coin(period['abs_profit'], stats['stake_currency'])}",
                    f"{period['fiat_value']:.2f} {stats['fiat_display_currency']}",
                    f"{format_pct(period['rel_profit'])}",
                ]
                for period in stats["data"]
            ],
            headers=[
                self._t("tg.timeunit.header_count", chat_id=chat_id, header=val.header),
                f"{stake_cur}",
                f"{fiat_disp_cur}",
                self._t("tg.timeunit.profit_pct", chat_id=chat_id),
                self._t("tg.timeunit.trades", chat_id=chat_id),
            ],
            tablefmt="simple",
        )
        message = (
            self._t(
                "tg.timeunit.title",
                chat_id=chat_id,
                message=val.message,
                timescale=timescale,
                unit=val.message2,
            )
            + f"<pre>{stats_tab}</pre>"
        )
        await self._send_msg(
            message,
            parse_mode=ParseMode.HTML,
            reload_able=True,
            callback_path=val.callback,
            query=update.callback_query,
        )

    @authorized_only
    async def _daily(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /daily <n>
        Returns a daily profit (in BTC) over the last n days.
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        await self._timeunit_stats(update, context, "days")

    @authorized_only
    async def _weekly(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /weekly <n>
        Returns a weekly profit (in BTC) over the last n weeks.
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        await self._timeunit_stats(update, context, "weeks")

    @authorized_only
    async def _monthly(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /monthly <n>
        Returns a monthly profit (in BTC) over the last n months.
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        await self._timeunit_stats(update, context, "months")

    def _format_profit_message(
        self,
        stats: dict,
        stake_cur: str,
        fiat_disp_cur: str,
        timescale: int | None = None,
        direction: str | None = None,
        chat_id: int | str | None = None,
    ) -> str:
        """
        Format profit statistics message for telegram.

        :param stats: Trade statistics dictionary
        :param stake_cur: Stake currency
        :param fiat_disp_cur: Fiat display currency
        :param timescale: Optional timescale filter
        :param direction: Optional direction filter ('long', 'short', or None for all)
        :return: Formatted markdown message
        """
        # Extract common variables
        profit_closed_coin = stats["profit_closed_coin"]
        profit_closed_ratio_mean = stats["profit_closed_ratio_mean"]
        profit_closed_percent = stats["profit_closed_percent"]
        profit_closed_fiat = stats["profit_closed_fiat"]
        profit_all_coin = stats["profit_all_coin"]
        profit_all_ratio_mean = stats["profit_all_ratio_mean"]
        profit_all_percent = stats["profit_all_percent"]
        profit_all_fiat = stats["profit_all_fiat"]
        trade_count = stats["trade_count"]
        first_trade_date = f"{stats['first_trade_humanized']} ({stats['first_trade_date']})"
        latest_trade_date = f"{stats['latest_trade_humanized']} ({stats['latest_trade_date']})"
        avg_duration = stats["avg_duration"]
        best_pair = stats["best_pair"]
        best_pair_profit_ratio = stats["best_pair_profit_ratio"]
        best_pair_profit_abs = fmt_coin(stats["best_pair_profit_abs"], stake_cur)
        winrate = stats["winrate"]
        expectancy = stats["expectancy"]
        expectancy_ratio = stats["expectancy_ratio"]

        # Direction-specific labels
        direction_label = f" {direction}" if direction else ""
        no_trades_msg = self._t(
            "tg.profit.no_trades",
            chat_id=chat_id,
            direction=direction_label,
            bot_start_date=stats["bot_start_date"],
        )
        no_closed_msg = self._t(
            "tg.profit.no_closed_trade", chat_id=chat_id, direction=direction_label
        )
        closed_roi_label = self._t(
            "tg.profit.closed_roi", chat_id=chat_id, direction=direction_label
        )
        all_roi_label = self._t("tg.profit.all_roi", chat_id=chat_id, direction=direction_label)

        if stats["trade_count"] == 0:
            return no_trades_msg

        # Build message
        if stats["closed_trade_count"] > 0:
            fiat_closed_trades = (
                f"∙ `{fmt_coin(profit_closed_fiat, fiat_disp_cur)}`\n" if fiat_disp_cur else ""
            )
            markdown_msg = (
                f"{closed_roi_label}\n"
                f"∙ `{fmt_coin(profit_closed_coin, stake_cur)} "
                f"({format_pct(profit_closed_ratio_mean)}) "
                f"({profit_closed_percent} \N{GREEK CAPITAL LETTER SIGMA}%)`\n"
                f"{fiat_closed_trades}"
            )
        else:
            markdown_msg = no_closed_msg

        fiat_all_trades = (
            f"∙ `{fmt_coin(profit_all_fiat, fiat_disp_cur)}`\n" if fiat_disp_cur else ""
        )
        markdown_msg += (
            f"{all_roi_label}\n"
            f"∙ `{fmt_coin(profit_all_coin, stake_cur)} "
            f"({format_pct(profit_all_ratio_mean)}) "
            f"({profit_all_percent} \N{GREEK CAPITAL LETTER SIGMA}%)`\n"
            f"{fiat_all_trades}"
            + self._t("tg.profit.total_trade_count", chat_id=chat_id, count=trade_count)
            + self._t(
                "tg.profit.bot_started",
                chat_id=chat_id,
                bot_start_date=stats["bot_start_date"],
            )
            + self._t(
                "tg.profit.first_trade_opened"
                if not timescale
                else "tg.profit.showing_profit_since",
                chat_id=chat_id,
                date=first_trade_date,
            )
            + self._t("tg.profit.latest_trade_opened", chat_id=chat_id, date=latest_trade_date)
            + self._t(
                "tg.profit.win_loss",
                chat_id=chat_id,
                wins=stats["winning_trades"],
                losses=stats["losing_trades"],
            )
            + self._t("tg.profit.winrate", chat_id=chat_id, ratio=format_pct(winrate))
            + self._t(
                "tg.profit.expectancy",
                chat_id=chat_id,
                expectancy=f"{expectancy:.2f}",
                ratio=f"{expectancy_ratio:.2f}",
            )
        )

        if stats["closed_trade_count"] > 0:
            markdown_msg += (
                self._t("tg.profit.avg_duration", chat_id=chat_id, duration=avg_duration)
                + self._t(
                    "tg.profit.best_performing",
                    chat_id=chat_id,
                    pair=best_pair,
                    amount=best_pair_profit_abs,
                    ratio=format_pct(best_pair_profit_ratio),
                )
                + self._t(
                    "tg.profit.trading_volume",
                    chat_id=chat_id,
                    volume=fmt_coin(stats["trading_volume"], stake_cur),
                )
                + self._t(
                    "tg.profit.profit_factor",
                    chat_id=chat_id,
                    factor=f"{stats['profit_factor']:.2f}",
                )
                + self._t(
                    "tg.profit.max_drawdown",
                    chat_id=chat_id,
                    ratio=format_pct(stats["max_drawdown"]),
                    amount=fmt_coin(stats["max_drawdown_abs"], stake_cur),
                )
                + self._t(
                    "tg.profit.drawdown_from",
                    chat_id=chat_id,
                    date=stats["max_drawdown_start"],
                    amount=fmt_coin(stats["drawdown_high"], stake_cur),
                )
                + self._t(
                    "tg.profit.drawdown_to",
                    chat_id=chat_id,
                    date=stats["max_drawdown_end"],
                    amount=fmt_coin(stats["drawdown_low"], stake_cur),
                )
                + self._t(
                    "tg.profit.current_drawdown",
                    chat_id=chat_id,
                    ratio=format_pct(stats["current_drawdown"]),
                    amount=fmt_coin(stats["current_drawdown_abs"], stake_cur),
                )
                + self._t(
                    "tg.profit.drawdown_from",
                    chat_id=chat_id,
                    date=stats["current_drawdown_start"],
                    amount=fmt_coin(stats["current_drawdown_high"], stake_cur),
                )
            )

        return markdown_msg

    async def _profit_handler(
        self,
        update: Update,
        context: CallbackContext,
        direction: str | None = None,
    ) -> None:
        """
        Common handler for profit commands.

        :param update: Telegram update
        :param context: Callback context
        :param direction: Trade direction filter ('long', 'short', or None)
        :param callback_path: Callback path for message updates
        """
        stake_cur = self._config["stake_currency"]
        fiat_disp_cur = self._config.get("fiat_display_currency", "")

        start_date = dt_from_ts(0)
        timescale = None
        try:
            if context.args:
                if not direction:
                    arg = context.args[0].lower()
                    if arg in ("short", "long"):
                        direction = arg
                        context.args.pop(0)  # Remove direction from args
                timescale = int(context.args[0]) - 1
                today_start = datetime.combine(dt_now().date(), datetime.min.time())
                start_date = today_start - timedelta(days=timescale)
        except (TypeError, ValueError, IndexError):
            pass

        # Get stats with optional direction filter
        stats_kwargs = {
            "stake_currency": stake_cur,
            "fiat_display_currency": fiat_disp_cur,
            "start_date": start_date,
        }
        if direction:
            stats_kwargs["direction"] = direction

        stats = self._rpc._rpc_trade_statistics(**stats_kwargs)
        markdown_msg = self._format_profit_message(
            stats,
            stake_cur,
            fiat_disp_cur,
            timescale,
            direction,
            chat_id=self._update_chat_id(update),
        )

        await self._send_msg(
            markdown_msg,
            reload_able=True,
            callback_path="update_profit" if not direction else f"update_profit_{direction}",
            query=update.callback_query,
        )

    @authorized_only
    async def _profit(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /profit.
        Returns a cumulative profit statistics.
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        await self._profit_handler(update, context)

    @authorized_only
    async def _profit_long(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /profit_long.
        Returns cumulative profit statistics for long trades.
        """
        await self._profit_handler(update, context, direction="long")

    @authorized_only
    async def _profit_short(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /profit_short.
        Returns cumulative profit statistics for short trades.
        """
        await self._profit_handler(update, context, direction="short")

    @authorized_only
    async def _stats(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /stats
        Show stats of recent trades
        """
        chat_id = self._update_chat_id(update)
        stats = self._rpc._rpc_stats()

        reason_map = {
            "roi": self._t("tg.stats.reason_roi", chat_id=chat_id),
            "stop_loss": self._t("tg.stats.reason_stoploss", chat_id=chat_id),
            "trailing_stop_loss": self._t("tg.stats.reason_trailing_stop", chat_id=chat_id),
            "stoploss_on_exchange": self._t("tg.stats.reason_stoploss", chat_id=chat_id),
            "exit_signal": self._t("tg.stats.reason_exit_signal", chat_id=chat_id),
            "force_exit": self._t("tg.stats.reason_force_exit", chat_id=chat_id),
            "emergency_exit": self._t("tg.stats.reason_emergency_exit", chat_id=chat_id),
        }
        exit_reasons_tabulate = [
            [reason_map.get(reason, reason), sum(count.values()), count["wins"], count["losses"]]
            for reason, count in stats["exit_reasons"].items()
        ]
        exit_reasons_msg = self._t("tg.stats.no_trades", chat_id=chat_id)
        for reason in chunks(exit_reasons_tabulate, 25):
            exit_reasons_msg = tabulate(
                reason,
                headers=[
                    self._t("tg.stats.col_exit_reason", chat_id=chat_id),
                    self._t("tg.stats.col_exits", chat_id=chat_id),
                    self._t("tg.stats.wins", chat_id=chat_id),
                    self._t("tg.stats.losses", chat_id=chat_id),
                ],
            )
            if len(exit_reasons_tabulate) > 25:
                await self._send_msg(f"```\n{exit_reasons_msg}```", ParseMode.MARKDOWN)
                exit_reasons_msg = ""

        durations = stats["durations"]
        duration_msg = tabulate(
            [
                [
                    self._t("tg.stats.wins", chat_id=chat_id),
                    (
                        str(timedelta(seconds=durations["wins"]))
                        if durations["wins"] is not None
                        else self._t("tg.common.na", chat_id=chat_id)
                    ),
                ],
                [
                    self._t("tg.stats.losses", chat_id=chat_id),
                    (
                        str(timedelta(seconds=durations["losses"]))
                        if durations["losses"] is not None
                        else self._t("tg.common.na", chat_id=chat_id)
                    ),
                ],
            ],
            headers=["", self._t("tg.stats.col_avg_duration", chat_id=chat_id)],
        )
        msg = f"""```\n{exit_reasons_msg}```\n```\n{duration_msg}```"""

        await self._send_msg(msg, ParseMode.MARKDOWN)

    @authorized_only
    async def _balance(self, update: Update, context: CallbackContext) -> None:
        """Handler for /balance"""
        full_result = context.args and "full" in context.args
        result = self._rpc._rpc_balance(
            self._config["stake_currency"], self._config.get("fiat_display_currency", "")
        )

        balance_dust_level = self._config["telegram"].get("balance_dust_level", 0.0)
        if not balance_dust_level:
            balance_dust_level = DUST_PER_COIN.get(self._config["stake_currency"], 1.0)

        chat_id = self._update_chat_id(update)
        output = ""
        if self._config["dry_run"]:
            output += self._t("tg.balance.dry_warning", chat_id=chat_id)
        starting_cap = fmt_coin(result["starting_capital"], self._config["stake_currency"])
        output += self._t("tg.balance.starting_capital", chat_id=chat_id, amount=starting_cap)
        starting_cap_fiat = (
            fmt_coin(result["starting_capital_fiat"], self._config["fiat_display_currency"])
            if result["starting_capital_fiat"] > 0
            else ""
        )
        output += (f" `, {starting_cap_fiat}`.\n") if result["starting_capital_fiat"] > 0 else ".\n"

        # Keep this value on exactly the same mark-to-market basis as the
        # dashboard's "ROI: All trades" card and the /profit command:
        # closed profit + current profit of every filled open trade.
        profit_stats = self._rpc._rpc_trade_statistics(
            self._config["stake_currency"], self._config.get("fiat_display_currency", "")
        )
        all_trades_profit = profit_stats["profit_all_coin"]
        total_funds = result["starting_capital"] + all_trades_profit
        stake_currency = self._config["stake_currency"]
        output += (
            self._t("tg.balance.total_funds", chat_id=chat_id)
            + f"\t`{stake_currency}: {fmt_coin(total_funds, stake_currency, False)}`\n"
            + self._t(
                "tg.balance.all_trades_pnl",
                chat_id=chat_id,
                amount=fmt_coin(all_trades_profit, stake_currency, False),
                ratio=format_pct(profit_stats["profit_all_ratio"]),
            )
        )

        total_dust_balance = 0
        total_dust_currencies = 0
        for curr in result["currencies"]:
            curr_output = ""
            if (curr["is_position"] or curr["est_stake"] > balance_dust_level) and (
                full_result or curr["is_bot_managed"]
            ):
                if curr["is_position"]:
                    curr_output = (
                        f"*{curr['currency']}:*\n"
                        f"\t`{curr['side']}: {round_value(curr['position'], 8)}`\n"
                        + self._t(
                            "tg.balance.est",
                            chat_id=chat_id,
                            currency=curr["stake"],
                            amount=fmt_coin(curr["est_stake"], curr["stake"], False),
                        )
                    )
                else:
                    est_stake = fmt_coin(
                        curr["est_stake" if full_result else "est_stake_bot"], curr["stake"], False
                    )

                    curr_output = (
                        f"*{curr['currency']}:*\n"
                        + self._t(
                            "tg.balance.available",
                            chat_id=chat_id,
                            amount=fmt_coin(curr["free"], curr["currency"], False),
                        )
                        + self._t(
                            "tg.balance.balance",
                            chat_id=chat_id,
                            amount=fmt_coin(curr["balance"], curr["currency"], False),
                        )
                        + self._t(
                            "tg.balance.pending",
                            chat_id=chat_id,
                            amount=fmt_coin(curr["used"], curr["currency"], False),
                        )
                        + self._t(
                            "tg.balance.bot_owned",
                            chat_id=chat_id,
                            amount=fmt_coin(curr["bot_owned"], curr["currency"], False),
                        )
                        + self._t(
                            "tg.balance.est",
                            chat_id=chat_id,
                            currency=curr["stake"],
                            amount=est_stake,
                        )
                    )

            elif curr["est_stake"] <= balance_dust_level:
                total_dust_balance += curr["est_stake"]
                total_dust_currencies += 1

            # Handle overflowing message length
            if len(output + curr_output) >= MAX_MESSAGE_LENGTH:
                await self._send_msg(output)
                output = curr_output
            else:
                output += curr_output

        if total_dust_balance > 0:
            currency_word = plural(
                total_dust_currencies,
                self._t("tg.balance.currency", chat_id=chat_id),
                self._t("tg.balance.currencies", chat_id=chat_id),
            )
            output += self._t(
                "tg.balance.other_dust",
                chat_id=chat_id,
                count=total_dust_currencies,
                other=self._t("tg.balance.other", chat_id=chat_id),
                currency_word=currency_word,
                level=balance_dust_level,
                stake=result["stake"],
            ) + self._t(
                "tg.balance.est",
                chat_id=chat_id,
                currency=result["stake"],
                amount=fmt_coin(total_dust_balance, result["stake"], False),
            )
        tc = result["trade_count"] > 0
        stake_improve = f" `({result['starting_capital_ratio']:.2%})`" if tc else ""
        fiat_val = f" `({result['starting_capital_fiat_ratio']:.2%})`" if tc else ""
        value = fmt_coin(result["value" if full_result else "value_bot"], result["symbol"], False)
        total_stake = fmt_coin(
            result["total" if full_result else "total_bot"], result["stake"], False
        )
        fiat_estimated_value = (
            f"\t`{result['symbol']}: {value}`{fiat_val}\n" if result["symbol"] else ""
        )
        output += (
            self._t(
                "tg.balance.estimated_value",
                chat_id=chat_id,
                scope=(
                    "" if full_result else self._t("tg.balance.bot_managed_scope", chat_id=chat_id)
                ),
            )
            + f"\t`{result['stake']}: {total_stake}`{stake_improve}\n"
            + f"{fiat_estimated_value}"
        )
        await self._send_msg(
            output, reload_able=True, callback_path="update_balance", query=update.callback_query
        )

    @authorized_only
    async def _start(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /start.
        Starts TradeThread
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        msg = self._rpc._rpc_start()
        await self._send_msg(
            self._t(
                "tg.common.status",
                chat_id=self._update_chat_id(update),
                status=msg["status"],
            )
        )

    @authorized_only
    async def _stop(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /stop.
        Stops TradeThread
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        msg = self._rpc._rpc_stop()
        await self._send_msg(
            self._t(
                "tg.common.status",
                chat_id=self._update_chat_id(update),
                status=msg["status"],
            )
        )

    @authorized_only
    async def _reload_config(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /reload_config.
        Triggers a config file reload
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        msg = self._rpc._rpc_reload_config()
        await self._send_msg(
            self._t(
                "tg.common.status",
                chat_id=self._update_chat_id(update),
                status=msg["status"],
            )
        )

    @authorized_only
    async def _pause(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /stop_buy /stop_entry and /pause.
        Sets bot state to paused
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        msg = self._rpc._rpc_pause()
        await self._send_msg(
            self._t(
                "tg.common.status",
                chat_id=self._update_chat_id(update),
                status=msg["status"],
            )
        )

    @authorized_only
    async def _reload_trade_from_exchange(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /reload_trade <tradeid>.
        """
        if not context.args or len(context.args) == 0:
            raise RPCException(
                self._t(
                    "tg.common.trade_id_not_set",
                    chat_id=self._update_chat_id(update),
                )
            )
        trade_id = int(context.args[0])
        msg = self._rpc._rpc_reload_trade_from_exchange(trade_id)
        await self._send_msg(
            self._t(
                "tg.common.status",
                chat_id=self._update_chat_id(update),
                status=msg["status"],
            )
        )

    @authorized_only
    async def _force_exit(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /forceexit <id>.
        Sells the given trade at current price
        :param bot: telegram bot
        :param update: message update
        :return: None
        """

        if context.args:
            trade_id = context.args[0]
            await self._force_exit_action(trade_id)
        else:
            fiat_currency = self._config.get("fiat_display_currency", "")
            try:
                statlist, _, _, _ = self._rpc._rpc_status_table(
                    self._config["stake_currency"], fiat_currency
                )
            except RPCException:
                await self._send_msg(
                    msg=self._t(
                        "tg.force_exit.no_open_trade",
                        chat_id=self._update_chat_id(update),
                    )
                )
                return
            trades = []
            for trade in statlist:
                trades.append((trade[0], f"{trade[0]} {trade[1]} {trade[2]} {trade[3]}"))

            trade_buttons = [
                InlineKeyboardButton(text=trade[1], callback_data=f"force_exit__{trade[0]}")
                for trade in trades
            ]
            buttons_aligned = self._layout_inline_keyboard(trade_buttons, cols=1)

            buttons_aligned.append(
                [
                    InlineKeyboardButton(
                        text=self._t("tg.common.cancel", chat_id=self._update_chat_id(update)),
                        callback_data="force_exit__cancel",
                    )
                ]
            )
            await self._send_msg(
                msg=self._t("tg.force_exit.which_trade", chat_id=self._update_chat_id(update)),
                keyboard=buttons_aligned,
            )

    async def _force_exit_action(self, trade_id: str):
        if trade_id != "cancel":
            try:
                loop = asyncio.get_running_loop()
                # Workaround to avoid nested loops
                await loop.run_in_executor(None, safe_async_db(self._rpc._rpc_force_exit), trade_id)
            except RPCException as e:
                await self._send_msg(str(e))

    async def _force_exit_inline(self, update: Update, _: CallbackContext) -> None:
        if update.callback_query:
            query = update.callback_query
            if query.data and "__" in query.data:
                # Input data is "force_exit__<tradid|cancel>"
                trade_id = query.data.split("__")[1].split(" ")[0]
                if trade_id == "cancel":
                    await query.answer()
                    await query.edit_message_text(
                        text=self._t(
                            "tg.force_exit.canceled",
                            chat_id=self._update_chat_id(update),
                        )
                    )
                    return
                trade: Trade | None = (
                    Trade.get_trades(trade_filter=Trade.id == int(trade_id)).first()
                    if trade_id.isdigit()
                    else None
                )
                await query.answer()
                if trade:
                    await query.edit_message_text(
                        text=self._t(
                            "tg.force_exit.manual_exiting",
                            chat_id=self._update_chat_id(update),
                            trade_id=trade_id,
                            pair=trade.pair,
                        )
                    )
                    await self._force_exit_action(trade_id)
                else:
                    await query.edit_message_text(
                        text=self._t(
                            "tg.force_exit.not_found",
                            chat_id=self._update_chat_id(update),
                            trade_id=trade_id,
                        )
                    )

    async def _force_enter_action(self, pair, price: float | None, order_side: SignalDirection):
        if pair != "cancel":
            try:

                @safe_async_db
                def _force_enter():
                    self._rpc._rpc_force_entry(pair, price, order_side=order_side)

                loop = asyncio.get_running_loop()
                # Workaround to avoid nested loops
                await loop.run_in_executor(None, _force_enter)
            except RPCException as e:
                logger.exception("Forcebuy error!")
                await self._send_msg(str(e), ParseMode.HTML)

    async def _force_enter_inline(self, update: Update, _: CallbackContext) -> None:
        if update.callback_query:
            query = update.callback_query
            if query.data and "__" in query.data:
                # Input data is "force_enter__<pair|cancel>_<side>"
                payload = query.data.split("__")[1]
                if payload == "cancel":
                    await query.answer()
                    await query.edit_message_text(
                        text=self._t(
                            "tg.force_enter.canceled",
                            chat_id=self._update_chat_id(update),
                        )
                    )
                    return
                if payload and "_||_" in payload:
                    pair, side = payload.split("_||_")
                    order_side = SignalDirection(side)
                    await query.answer()
                    await query.edit_message_text(
                        text=self._t(
                            "tg.force_enter.manual_entering",
                            chat_id=self._update_chat_id(update),
                            side=order_side,
                            pair=pair,
                        )
                    )
                    await self._force_enter_action(pair, None, order_side)

    @staticmethod
    def _layout_inline_keyboard(
        buttons: list[InlineKeyboardButton], cols=3
    ) -> list[list[InlineKeyboardButton]]:
        return [buttons[i : i + cols] for i in range(0, len(buttons), cols)]

    @authorized_only
    async def _force_enter(
        self, update: Update, context: CallbackContext, order_side: SignalDirection
    ) -> None:
        """
        Handler for /forcelong <asset> <price> and `/forceshort <asset> <price>
        Buys a pair trade at the given or current price
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        if context.args:
            pair = context.args[0]
            price = float(context.args[1]) if len(context.args) > 1 else None
            await self._force_enter_action(pair, price, order_side)
        else:
            whitelist = self._rpc._rpc_whitelist()["whitelist"]
            pair_buttons = [
                InlineKeyboardButton(
                    text=pair, callback_data=f"force_enter__{pair}_||_{order_side}"
                )
                for pair in sorted(whitelist)
            ]
            buttons_aligned = self._layout_inline_keyboard(pair_buttons)

            buttons_aligned.append(
                [
                    InlineKeyboardButton(
                        text=self._t("tg.common.cancel", chat_id=self._update_chat_id(update)),
                        callback_data="force_enter__cancel",
                    )
                ]
            )
            await self._send_msg(
                msg=self._t("tg.force_enter.which_pair", chat_id=self._update_chat_id(update)),
                keyboard=buttons_aligned,
                query=update.callback_query,
            )

    @authorized_only
    async def _trades(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /trades <n>
        Returns last n recent trades.
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        stake_cur = self._config["stake_currency"]
        try:
            nrecent = int(context.args[0]) if context.args else 10
        except (TypeError, ValueError, IndexError):
            nrecent = 10
        nonspot = self._config.get("trading_mode", TradingMode.SPOT) != TradingMode.SPOT
        chat_id = self._update_chat_id(update)
        trades = self._rpc._rpc_trade_history(nrecent)
        trades_tab = tabulate(
            [
                [
                    dt_humanize_delta(dt_from_ts(trade["close_timestamp"])),
                    (
                        f"{trade['pair']} (#{trade['trade_id']}"
                        f"{(' ' + ('S' if trade['is_short'] else 'L')) if nonspot else ''})"
                    ),
                    f"{format_pct(trade['close_profit'])} ({trade['close_profit_abs']})",
                ]
                for trade in trades["trades"]
            ],
            headers=[
                self._t("tg.trades.col_close_date", chat_id=chat_id),
                (
                    self._t("tg.trades.col_pair_ls", chat_id=chat_id)
                    if nonspot
                    else self._t("tg.trades.col_pair", chat_id=chat_id)
                ),
                self._t("tg.trades.col_profit", chat_id=chat_id, stake=stake_cur),
            ],
            tablefmt="simple",
        )
        message = self._t(
            "tg.trades.recent",
            chat_id=chat_id,
            count=min(trades["trades_count"], nrecent),
        ) + (f"<pre>{trades_tab}</pre>" if trades["trades_count"] > 0 else "")
        await self._send_msg(message, parse_mode=ParseMode.HTML)

    @authorized_only
    async def _delete_trade(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /delete <id>.
        Delete the given trade
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        if not context.args or len(context.args) == 0:
            raise RPCException(
                self._t(
                    "tg.common.trade_id_not_set",
                    chat_id=self._update_chat_id(update),
                )
            )
        trade_id = int(context.args[0])
        msg = self._rpc._rpc_delete(trade_id)
        await self._send_msg(
            self._t(
                "tg.common.result_msg_note",
                chat_id=self._update_chat_id(update),
                result=msg["result_msg"],
            )
        )

    @authorized_only
    async def _cancel_open_order(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /cancel_open_order <id>.
        Cancel open order for tradeid
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        if not context.args or len(context.args) == 0:
            raise RPCException(
                self._t(
                    "tg.common.trade_id_not_set",
                    chat_id=self._update_chat_id(update),
                )
            )
        trade_id = int(context.args[0])
        self._rpc._rpc_cancel_open_order(trade_id)
        await self._send_msg(
            self._t(
                "tg.common.open_order_canceled",
                chat_id=self._update_chat_id(update),
            )
        )

    @authorized_only
    async def _performance(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /performance.
        Shows a performance statistic from finished trades
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        trades = self._rpc._rpc_performance()
        output = self._t("tg.performance.title", chat_id=self._update_chat_id(update))
        for i, trade in enumerate(trades):
            stat_line = (
                f"{i + 1}.\t <code>{trade['pair']}\t"
                f"{fmt_coin(trade['profit_abs'], self._config['stake_currency'])} "
                f"({format_pct(trade['profit_ratio'])}) "
                f"({trade['count']})</code>\n"
            )

            if len(output + stat_line) >= MAX_MESSAGE_LENGTH:
                await self._send_msg(output, parse_mode=ParseMode.HTML)
                output = stat_line
            else:
                output += stat_line

        await self._send_msg(
            output,
            parse_mode=ParseMode.HTML,
            reload_able=True,
            callback_path="update_performance",
            query=update.callback_query,
        )

    @authorized_only
    async def _enter_tag_performance(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /entries PAIR .
        Shows a performance statistic from finished trades
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        pair = None
        if context.args and isinstance(context.args[0], str):
            pair = context.args[0]

        trades = self._rpc._rpc_enter_tag_performance(pair)
        output = self._t("tg.entry_tag_perf.title", chat_id=self._update_chat_id(update))
        for i, trade in enumerate(trades):
            stat_line = (
                f"{i + 1}.\t `{trade['enter_tag']}\t"
                f"{fmt_coin(trade['profit_abs'], self._config['stake_currency'])} "
                f"({format_pct(trade['profit_ratio'])}) "
                f"({trade['count']})`\n"
            )

            if len(output + stat_line) >= MAX_MESSAGE_LENGTH:
                await self._send_msg(output, parse_mode=ParseMode.MARKDOWN)
                output = stat_line
            else:
                output += stat_line

        await self._send_msg(
            output,
            parse_mode=ParseMode.MARKDOWN,
            reload_able=True,
            callback_path="update_enter_tag_performance",
            query=update.callback_query,
        )

    @authorized_only
    async def _exit_reason_performance(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /exits.
        Shows a performance statistic from finished trades
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        pair = None
        if context.args and isinstance(context.args[0], str):
            pair = context.args[0]

        trades = self._rpc._rpc_exit_reason_performance(pair)
        output = self._t("tg.exit_reason_perf.title", chat_id=self._update_chat_id(update))
        for i, trade in enumerate(trades):
            stat_line = (
                f"{i + 1}.\t `{trade['exit_reason']}\t"
                f"{fmt_coin(trade['profit_abs'], self._config['stake_currency'])} "
                f"({format_pct(trade['profit_ratio'])}) "
                f"({trade['count']})`\n"
            )

            if len(output + stat_line) >= MAX_MESSAGE_LENGTH:
                await self._send_msg(output, parse_mode=ParseMode.MARKDOWN)
                output = stat_line
            else:
                output += stat_line

        await self._send_msg(
            output,
            parse_mode=ParseMode.MARKDOWN,
            reload_able=True,
            callback_path="update_exit_reason_performance",
            query=update.callback_query,
        )

    @authorized_only
    async def _mix_tag_performance(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /mix_tags.
        Shows a performance statistic from finished trades
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        pair = None
        if context.args and isinstance(context.args[0], str):
            pair = context.args[0]

        trades = self._rpc._rpc_mix_tag_performance(pair)
        output = self._t("tg.mix_tag_perf.title", chat_id=self._update_chat_id(update))
        for i, trade in enumerate(trades):
            stat_line = (
                f"{i + 1}.\t `{trade['mix_tag']}\t"
                f"{fmt_coin(trade['profit_abs'], self._config['stake_currency'])} "
                f"({format_pct(trade['profit_ratio'])}) "
                f"({trade['count']})`\n"
            )

            if len(output + stat_line) >= MAX_MESSAGE_LENGTH:
                await self._send_msg(output, parse_mode=ParseMode.MARKDOWN)
                output = stat_line
            else:
                output += stat_line

        await self._send_msg(
            output,
            parse_mode=ParseMode.MARKDOWN,
            reload_able=True,
            callback_path="update_mix_tag_performance",
            query=update.callback_query,
        )

    @authorized_only
    async def _count(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /count.
        Returns the number of trades running
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        counts = self._rpc._rpc_count()
        message = tabulate(
            {k: [v] for k, v in counts.items()},
            headers=[
                self._t("tg.count.col_current", chat_id=self._update_chat_id(update)),
                self._t("tg.count.col_max", chat_id=self._update_chat_id(update)),
                self._t("tg.count.col_total_stake", chat_id=self._update_chat_id(update)),
            ],
            tablefmt="simple",
        )
        message = f"<pre>{message}</pre>"
        logger.debug(message)
        await self._send_msg(
            message,
            parse_mode=ParseMode.HTML,
            reload_able=True,
            callback_path="update_count",
            query=update.callback_query,
        )

    @authorized_only
    async def _locks(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /locks.
        Returns the currently active locks
        """
        rpc_locks = self._rpc._rpc_locks()
        if not rpc_locks["locks"]:
            await self._send_msg(
                self._t("tg.locks.none", chat_id=self._update_chat_id(update)),
                parse_mode=ParseMode.HTML,
            )

        for locks in chunks(rpc_locks["locks"], 25):
            message = tabulate(
                [
                    [lock["id"], lock["pair"], lock["lock_end_time"], lock["reason"]]
                    for lock in locks
                ],
                headers=[
                    self._t("tg.locks.col_id", chat_id=self._update_chat_id(update)),
                    self._t("tg.locks.col_pair", chat_id=self._update_chat_id(update)),
                    self._t("tg.locks.col_until", chat_id=self._update_chat_id(update)),
                    self._t("tg.locks.col_reason", chat_id=self._update_chat_id(update)),
                ],
                tablefmt="simple",
            )
            message = f"<pre>{escape(message)}</pre>"
            logger.debug(message)
            await self._send_msg(message, parse_mode=ParseMode.HTML)

    @authorized_only
    async def _delete_locks(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /delete_locks.
        Returns the currently active locks
        """
        arg = context.args[0] if context.args and len(context.args) > 0 else None
        lockid = None
        pair = None
        if arg:
            try:
                lockid = int(arg)
            except ValueError:
                pair = arg

        self._rpc._rpc_delete_lock(lockid=lockid, pair=pair)
        await self._locks(update, context)

    @authorized_only
    async def _whitelist(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /whitelist
        Shows the currently active whitelist
        """
        whitelist = self._rpc._rpc_whitelist()

        if context.args:
            if "sorted" in context.args:
                whitelist["whitelist"] = sorted(whitelist["whitelist"])
            if "baseonly" in context.args:
                whitelist["whitelist"] = [pair.split("/")[0] for pair in whitelist["whitelist"]]

        header = self._t(
            "tg.whitelist.header",
            chat_id=self._update_chat_id(update),
            method=whitelist["method"],
            length=whitelist["length"],
        )
        messages: list[str] = []
        message = f"{header}`"
        has_pair = False

        for pair in whitelist["whitelist"]:
            token = f", {pair}" if has_pair else pair
            if has_pair and len(message) + len(token) + 1 > MAX_MESSAGE_LENGTH:
                messages.append(f"{message}`")
                message = f"`{pair}"
                has_pair = True
            elif not has_pair and len(message) + len(token) + 1 > MAX_MESSAGE_LENGTH:
                messages.append(header.rstrip())
                message = f"`{pair}"
                has_pair = True
            else:
                message += token
                has_pair = True

        messages.append(f"{message}`")
        for message in messages:
            logger.debug(message)
            await self._send_msg(message)

    @authorized_only
    async def _blacklist(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /blacklist
        Shows the currently active blacklist
        """
        await self.send_blacklist_msg(
            self._rpc._rpc_blacklist(context.args), self._update_chat_id(update)
        )

    async def send_blacklist_msg(self, blacklist: dict, chat_id: int | str | None = None):
        errmsgs = []
        for error in blacklist["errors"].values():
            errmsgs.append(
                self._t("tg.blacklist.error", chat_id=chat_id, message=error["error_msg"])
            )
        if errmsgs:
            await self._send_msg("\n".join(errmsgs))

        message = self._t("tg.blacklist.contains", chat_id=chat_id, length=blacklist["length"])
        message += f"`{', '.join(blacklist['blacklist'])}`"

        logger.debug(message)
        await self._send_msg(message)

    @authorized_only
    async def _blacklist_delete(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /bl_delete
        Deletes pair(s) from current blacklist
        """
        await self.send_blacklist_msg(
            self._rpc._rpc_blacklist_delete(context.args or []),
            self._update_chat_id(update),
        )

    @authorized_only
    async def _logs(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /logs
        Shows the latest logs
        """
        try:
            limit = int(context.args[0]) if context.args else 10
        except (TypeError, ValueError, IndexError):
            limit = 10
        logs = RPC._rpc_get_logs(limit)["logs"]
        msgs = ""
        msg_template = "*{}* {}: {} \\- `{}`"
        for logrec in logs:
            msg = msg_template.format(
                escape_markdown(logrec[0], version=2),
                escape_markdown(logrec[2], version=2),
                escape_markdown(logrec[3], version=2),
                escape_markdown(logrec[4], version=2),
            )
            if len(msgs + msg) + 10 >= MAX_MESSAGE_LENGTH:
                # Send message immediately if it would become too long
                await self._send_msg(msgs, parse_mode=ParseMode.MARKDOWN_V2)
                msgs = msg + "\n"
            else:
                # Append message to messages to send
                msgs += msg + "\n"

        if msgs:
            await self._send_msg(msgs, parse_mode=ParseMode.MARKDOWN_V2)

    @authorized_only
    async def _help(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /help.
        Show commands of the bot
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        chat_id = self._update_chat_id(update)
        force_enter_text = self._t("tg.help.forcelong", chat_id=chat_id)
        if self._rpc._freqtrade.trading_mode != TradingMode.SPOT:
            force_enter_text += self._t("tg.help.forceshort", chat_id=chat_id)
        message = (
            self._t("tg.help.section_control", chat_id=chat_id)
            + self._t("tg.help.separator", chat_id=chat_id)
            + self._t("tg.help.start", chat_id=chat_id)
            + self._t("tg.help.pause", chat_id=chat_id)
            + self._t("tg.help.stop", chat_id=chat_id)
            + self._t("tg.help.stopentry", chat_id=chat_id)
            + self._t("tg.help.forceexit", chat_id=chat_id)
            + self._t("tg.help.fx", chat_id=chat_id)
            + (force_enter_text if self._config.get("force_entry_enable", False) else "")
            + self._t("tg.help.delete", chat_id=chat_id)
            + self._t("tg.help.reload_trade", chat_id=chat_id)
            + self._t("tg.help.cancel_open_order", chat_id=chat_id)
            + self._t("tg.help.coo", chat_id=chat_id)
            + self._t("tg.help.whitelist", chat_id=chat_id)
            + self._t("tg.help.blacklist", chat_id=chat_id)
            + self._t("tg.help.blacklist_delete", chat_id=chat_id)
            + self._t("tg.help.reload_config", chat_id=chat_id)
            + self._t("tg.help.unlock", chat_id=chat_id)
            + self._t("tg.help.section_state", chat_id=chat_id)
            + self._t("tg.help.separator", chat_id=chat_id)
            + self._t("tg.help.show_config", chat_id=chat_id)
            + self._t("tg.help.locks", chat_id=chat_id)
            + self._t("tg.help.balance", chat_id=chat_id)
            + self._t("tg.help.balance_full", chat_id=chat_id)
            + self._t("tg.help.logs", chat_id=chat_id)
            + self._t("tg.help.count", chat_id=chat_id)
            + self._t("tg.help.health", chat_id=chat_id)
            + self._t("tg.help.marketdir", chat_id=chat_id)
            + self._t("tg.help.list_custom_data", chat_id=chat_id)
            + self._t("tg.help.list_custom_data_key_note", chat_id=chat_id)
            + self._t("tg.help.section_statistics", chat_id=chat_id)
            + self._t("tg.help.separator", chat_id=chat_id)
            + self._t("tg.help.status", chat_id=chat_id)
            + self._t("tg.help.status_id", chat_id=chat_id)
            + self._t("tg.help.status_id_note", chat_id=chat_id)
            + self._t("tg.help.status_table", chat_id=chat_id)
            + self._t("tg.help.status_table_buy", chat_id=chat_id)
            + self._t("tg.help.status_table_sell", chat_id=chat_id)
            + self._t("tg.help.entries", chat_id=chat_id)
            + self._t("tg.help.exits", chat_id=chat_id)
            + self._t("tg.help.mix_tags", chat_id=chat_id)
            + self._t("tg.help.trades", chat_id=chat_id)
            + self._t("tg.help.profit", chat_id=chat_id)
            + self._t("tg.help.profit_long", chat_id=chat_id)
            + self._t("tg.help.profit_short", chat_id=chat_id)
            + self._t("tg.help.performance", chat_id=chat_id)
            + self._t("tg.help.daily", chat_id=chat_id)
            + self._t("tg.help.weekly", chat_id=chat_id)
            + self._t("tg.help.monthly", chat_id=chat_id)
            + self._t("tg.help.stats", chat_id=chat_id)
            + self._t("tg.help.help", chat_id=chat_id)
            + self._t("tg.help.language", chat_id=chat_id)
            + self._t("tg.help.version", chat_id=chat_id)
        )

        await self._send_msg(message, parse_mode=ParseMode.MARKDOWN)

    @authorized_only
    @safe_async_db
    async def _language(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /language (alias /lang).
        Shows or changes the language of the bot messages.
        """
        chat_id = self._update_chat_id(update)
        choices = self._i18n.locale_choices(chat_id)
        if context.args:
            requested = context.args[0]
            code = self._i18n.set_locale(chat_id, requested)
            if code is None:
                await self._send_msg(
                    self._t(
                        "tg.language.invalid",
                        chat_id=chat_id,
                        value=requested,
                        codes=", ".join(SUPPORTED_LOCALES),
                    )
                )
                return
            name = next((native for c, native, _ in choices if c == code), code)
            await self._send_msg(
                self._t("tg.language.set", chat_id=chat_id, language=name, code=code)
            )
            return

        lines = [self._t("tg.language.title", chat_id=chat_id)]
        current = self._i18n.locale_for(chat_id)
        current_name = next((native for c, native, _ in choices if c == current), current)
        lines.append(
            self._t(
                "tg.language.current",
                chat_id=chat_id,
                language=current_name,
                code=current,
            )
        )
        lines.append(self._t("tg.language.available", chat_id=chat_id))
        for code, native, is_current in choices:
            lines.append(
                self._t(
                    "tg.language.line",
                    chat_id=chat_id,
                    language=native,
                    code=code,
                    marker=(self._t("tg.language.marker", chat_id=chat_id) if is_current else ""),
                )
            )
        lines.append(self._t("tg.language.usage", chat_id=chat_id))
        await self._send_msg("\n".join(lines))

    @authorized_only
    async def _health(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /health
        Shows the last process timestamp
        """
        health = self._rpc.health()
        chat_id = self._update_chat_id(update)
        message = self._t(
            "tg.health.last_process", chat_id=chat_id, time=health["last_process_loc"]
        )
        message += self._t("tg.health.initial_start", chat_id=chat_id, time=health["bot_start_loc"])
        message += self._t(
            "tg.health.last_restart", chat_id=chat_id, time=health["bot_startup_loc"]
        )
        await self._send_msg(message)

    @authorized_only
    async def _version(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /version.
        Show version information
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        chat_id = self._update_chat_id(update)
        strategy_version = self._rpc._freqtrade.strategy.version()
        version_string = self._t("tg.version.version", chat_id=chat_id, version=__version__)
        if strategy_version is not None:
            version_string += self._t(
                "tg.version.strategy_version", chat_id=chat_id, version=strategy_version
            )

        await self._send_msg(version_string)

    @authorized_only
    async def _show_config(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /show_config.
        Show config information information
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        val = RPC._rpc_show_config(self._config, self._rpc._freqtrade.state)

        chat_id = self._update_chat_id(update)
        if val["trailing_stop"]:
            sl_info = (
                self._t(
                    "tg.show_config.initial_stoploss",
                    chat_id=chat_id,
                    stoploss=val["stoploss"],
                )
                + self._t(
                    "tg.show_config.trailing_positive",
                    chat_id=chat_id,
                    value=val["trailing_stop_positive"],
                )
                + self._t(
                    "tg.show_config.trailing_offset",
                    chat_id=chat_id,
                    value=val["trailing_stop_positive_offset"],
                )
                + self._t(
                    "tg.show_config.trailing_only_offset",
                    chat_id=chat_id,
                    value=val["trailing_only_offset_is_reached"],
                )
            )

        else:
            sl_info = self._t("tg.show_config.stoploss", chat_id=chat_id, stoploss=val["stoploss"])

        if val["position_adjustment_enable"]:
            pa_info = self._t("tg.show_config.position_adjustment_on", chat_id=chat_id) + self._t(
                "tg.show_config.max_enter_adj",
                chat_id=chat_id,
                value=val["max_entry_position_adjustment"],
            )
        else:
            pa_info = self._t("tg.show_config.position_adjustment_off", chat_id=chat_id)

        await self._send_msg(
            self._t(
                "tg.show_config.mode",
                chat_id=chat_id,
                mode=(
                    self._t("tg.common.dry_run", chat_id=chat_id)
                    if val["dry_run"]
                    else self._t("tg.common.live", chat_id=chat_id)
                ),
            )
            + self._t(
                "tg.show_config.exchange",
                chat_id=chat_id,
                exchange=val["exchange"],
                demo=(
                    self._t("tg.common.demo_suffix", chat_id=chat_id) if val["demo_trading"] else ""
                ),
            )
            + self._t("tg.show_config.market", chat_id=chat_id, market=val["trading_mode"])
            + self._t(
                "tg.show_config.stake_per_trade",
                chat_id=chat_id,
                amount=val["stake_amount"],
                stake_currency=val["stake_currency"],
            )
            + self._t(
                "tg.show_config.max_open_trades",
                chat_id=chat_id,
                value=val["max_open_trades"],
            )
            + self._t("tg.show_config.minimum_roi", chat_id=chat_id, roi=val["minimal_roi"])
            + self._t(
                "tg.show_config.entry_strategy",
                chat_id=chat_id,
                strategy=json.dumps(val["entry_pricing"]),
            )
            + self._t(
                "tg.show_config.exit_strategy",
                chat_id=chat_id,
                strategy=json.dumps(val["exit_pricing"]),
            )
            + f"{sl_info}"
            + f"{pa_info}"
            + self._t("tg.show_config.timeframe", chat_id=chat_id, timeframe=val["timeframe"])
            + self._t("tg.show_config.strategy", chat_id=chat_id, strategy=val["strategy"])
            + self._t("tg.show_config.current_state", chat_id=chat_id, state=val["state"])
        )

    @authorized_only
    async def _list_custom_data(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /list_custom_data <id> <key>.
        List custom_data for specified trade (and key if supplied).
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        try:
            if not context.args or len(context.args) == 0:
                raise RPCException(
                    self._t(
                        "tg.common.trade_id_not_set",
                        chat_id=self._update_chat_id(update),
                    )
                )
            trade_id = int(context.args[0])
            key = None if len(context.args) < 2 else str(context.args[1])

            chat_id = self._update_chat_id(update)
            results = self._rpc._rpc_list_custom_data(trade_id, key)
            messages = []
            if len(results) > 0:
                trade_custom_data = results[0]["custom_data"]
                messages.append(
                    self._t(
                        "tg.custom_data.found_many"
                        if len(trade_custom_data) > 1
                        else "tg.custom_data.found_one",
                        chat_id=chat_id,
                    )
                )
                for custom_data in trade_custom_data:
                    lines = [
                        self._t(
                            "tg.custom_data.key",
                            chat_id=chat_id,
                            custom_key=custom_data["key"],
                        ),
                        self._t(
                            "tg.custom_data.type",
                            chat_id=chat_id,
                            type=custom_data["type"],
                        ),
                        self._t(
                            "tg.custom_data.value",
                            chat_id=chat_id,
                            value=custom_data["value"],
                        ),
                        self._t(
                            "tg.custom_data.create_date",
                            chat_id=chat_id,
                            date=format_date(custom_data["created_at"]),
                        ),
                        self._t(
                            "tg.custom_data.update_date",
                            chat_id=chat_id,
                            date=format_date(custom_data["updated_at"]),
                        ),
                    ]
                    # Filter empty lines using list-comprehension
                    messages.append("\n".join([line for line in lines if line]))
                for msg in messages:
                    if len(msg) > MAX_MESSAGE_LENGTH:
                        msg = self._t(
                            "tg.custom_data.too_long",
                            chat_id=chat_id,
                            max_length=MAX_MESSAGE_LENGTH,
                        )
                        logger.warning(msg)
                    await self._send_msg(msg)
            else:
                message = self._t("tg.custom_data.not_found", chat_id=chat_id, trade_id=trade_id)
                if key is not None:
                    message += self._t(
                        "tg.custom_data.not_found_key", chat_id=chat_id, custom_key=key
                    )
                await self._send_msg(message)

        except RPCException as e:
            await self._send_msg(str(e))

    async def _update_msg(
        self,
        query: CallbackQuery,
        msg: str,
        callback_path: str = "",
        reload_able: bool = False,
        parse_mode: str = ParseMode.MARKDOWN,
    ) -> None:
        if reload_able:
            reply_markup = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            self._t("tg.common.refresh", chat_id=self._chat_id),
                            callback_data=callback_path,
                        )
                    ],
                ]
            )
        else:
            reply_markup = InlineKeyboardMarkup([[]])
        msg += self._t("tg.common.updated", chat_id=self._chat_id, time=dt_now().ctime())
        if not query.message:
            return

        try:
            await query.edit_message_text(
                text=msg, parse_mode=parse_mode, reply_markup=reply_markup
            )
        except BadRequest as e:
            if "not modified" in e.message.lower():
                pass
            else:
                logger.warning("TelegramError: %s", e.message)
        except TelegramError as telegram_err:
            logger.warning("TelegramError: %s! Giving up on that message.", telegram_err.message)

    async def _send_msg(
        self,
        msg: str,
        parse_mode: str = ParseMode.MARKDOWN,
        disable_notification: bool = False,
        keyboard: list[list[InlineKeyboardButton]] | None = None,
        callback_path: str = "",
        reload_able: bool = False,
        query: CallbackQuery | None = None,
    ) -> None:
        """
        Send given markdown message
        :param msg: message
        :param bot: alternative bot
        :param parse_mode: telegram parse mode
        :return: None
        """
        reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup
        if query:
            await self._update_msg(
                query=query,
                msg=msg,
                parse_mode=parse_mode,
                callback_path=callback_path,
                reload_able=reload_able,
            )
            return
        if reload_able and self._config["telegram"].get("reload", True):
            reply_markup = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            self._t("tg.common.refresh", chat_id=self._chat_id),
                            callback_data=callback_path,
                        )
                    ]
                ]
            )
        else:
            if keyboard is not None:
                reply_markup = InlineKeyboardMarkup(keyboard)
            else:
                reply_markup = ReplyKeyboardMarkup(self._keyboard, resize_keyboard=True)
        try:
            try:
                await self._app.bot.send_message(
                    self._config["telegram"]["chat_id"],
                    text=msg,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                    disable_notification=disable_notification,
                    message_thread_id=self._config["telegram"].get("topic_id"),
                )
            except NetworkError as network_err:
                # Sometimes the telegram server resets the current connection,
                # if this is the case we send the message again.
                logger.warning(
                    "Telegram NetworkError: %s! Trying one more time.", network_err.message
                )
                await self._app.bot.send_message(
                    self._config["telegram"]["chat_id"],
                    text=msg,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                    disable_notification=disable_notification,
                    message_thread_id=self._config["telegram"].get("topic_id"),
                )
        except TelegramError as telegram_err:
            logger.warning("TelegramError: %s! Giving up on that message.", telegram_err.message)

    @authorized_only
    async def _changemarketdir(self, update: Update, context: CallbackContext) -> None:
        """
        Handler for /marketdir.
        Updates the bot's market_direction
        :param bot: telegram bot
        :param update: message update
        :return: None
        """
        if context.args and len(context.args) == 1:
            new_market_dir_arg = context.args[0]
            old_market_dir = self._rpc._get_market_direction()
            new_market_dir = None
            if new_market_dir_arg == "long":
                new_market_dir = MarketDirection.LONG
            elif new_market_dir_arg == "short":
                new_market_dir = MarketDirection.SHORT
            elif new_market_dir_arg == "even":
                new_market_dir = MarketDirection.EVEN
            elif new_market_dir_arg == "none":
                new_market_dir = MarketDirection.NONE

            if new_market_dir is not None:
                self._rpc._update_market_direction(new_market_dir)
                await self._send_msg(
                    self._t(
                        "tg.marketdir.updated",
                        chat_id=self._update_chat_id(update),
                        old=old_market_dir,
                        new=new_market_dir,
                    )
                )
            else:
                raise RPCException(
                    self._t(
                        "tg.marketdir.invalid",
                        chat_id=self._update_chat_id(update),
                    )
                )
        elif context.args is not None and len(context.args) == 0:
            old_market_dir = self._rpc._get_market_direction()
            await self._send_msg(
                self._t(
                    "tg.marketdir.current",
                    chat_id=self._update_chat_id(update),
                    direction=old_market_dir,
                )
            )
        else:
            raise RPCException(self._t("tg.marketdir.usage", chat_id=self._update_chat_id(update)))

    async def _tg_info(self, update: Update, context: CallbackContext) -> None:
        """
        Intentionally unauthenticated Handler for /tg_info.
        Returns information about the current telegram chat - even if chat_id does not
        correspond to this chat.

        :param update: message update
        :return: None
        """
        if not update.message:
            return
        chat_id = update.message.chat_id
        topic_id = update.message.message_thread_id
        user_id = (
            update.effective_user.id if topic_id is not None and update.effective_user else None
        )

        msg = self._t(
            "tg.tg_info.message",
            chat_id=chat_id,
            chat_id_value=chat_id,
            topic_id_line=(f'"topic_id": "{topic_id}",' if topic_id else ""),
            authorized_users_line=(
                f'//"authorized_users": ["{user_id}"]' if topic_id and user_id else ""
            ),
        )
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=msg,
                parse_mode=ParseMode.MARKDOWN_V2,
                message_thread_id=topic_id,
            )
        except TelegramError as telegram_err:
            logger.warning("TelegramError: %s! Giving up on that message.", telegram_err.message)
