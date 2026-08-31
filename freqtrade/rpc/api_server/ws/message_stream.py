import asyncio
import time
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# 状态型消息（可按主题合并，只保留最新值）
STATEFUL_MESSAGE_TYPES = ("analyzed_df", "new_candle", "whitelist")
# 关键事件消息（不能静默丢失，走独立有界队列）
CRITICAL_MESSAGE_TYPES = (
    "entry",
    "entry_fill",
    "entry_cancel",
    "exit",
    "exit_fill",
    "exit_cancel",
    "exception",
    "strategy_msg",
)
# 每个订阅者队列的最大长度（防止慢消费者无限增长内存）
QUEUE_MAX_SIZE = 100
# 状态消息合并槽数量上限（analyzed_df 等按 pair 合并）
STATEFUL_SLOT_MAX = 2000


class MessageStream:
    """
    A bounded, per-subscriber message stream.

    Subscribers register their subscription types up front; publish() only
    enqueues messages for subscribers that actually care about the type.
    Stateful messages (analyzed_df / new_candle / whitelist) are merged into a
    single slot per topic (only the newest value is kept), while critical
    events (entry/exit fills, cancels, exceptions) are delivered through a
    bounded queue - a chronically slow consumer is disconnected with a
    rate-limit warning instead of growing memory without limit.
    """

    def __init__(self, max_queue_size: int = QUEUE_MAX_SIZE):
        self._max_queue_size = max_queue_size
        self._subscribers: dict[int, _Subscriber] = {}
        self._next_id = 0

        # 公开只读指标（不暴露 Token）
        self.subscriber_count = 0
        self.merged_count = 0
        self.dropped_count = 0
        self.max_latency = 0.0

    # ------------------------------------------------------------------ #
    # 订阅 / 取消订阅

    def subscribe(self, message_types: list[str]) -> int:
        """Register a subscriber for the given message types.

        Returns a unique subscriber id used to unsubscribe.
        """
        self._next_id += 1
        sub = _Subscriber(set(message_types), self._max_queue_size)
        self._subscribers[self._next_id] = sub
        self.subscriber_count = len(self._subscribers)
        return self._next_id

    def unsubscribe(self, subscriber_id: int) -> None:
        """Remove a subscriber and drop all queued/merged messages."""
        sub = self._subscribers.pop(subscriber_id, None)
        if sub is not None:
            sub.close()
        self.subscriber_count = len(self._subscribers)

    def subscribed_to(self, subscriber_id: int, message_type: str) -> bool:
        sub = self._subscribers.get(subscriber_id)
        return sub is not None and message_type in sub.message_types

    def set_subscriptions(self, subscriber_id: int, message_types: list[str]) -> None:
        """Update a subscriber's message types (e.g. after a SUBSCRIBE request)."""
        sub = self._subscribers.get(subscriber_id)
        if sub is not None:
            sub.message_types = set(message_types)

    # ------------------------------------------------------------------ #
    # 发布

    def publish(self, message: dict) -> None:
        """Publish a message to all subscribers that are subscribed to its type.

        :param message: dict with at least a "type" key (RPCMessageType value)
        """
        msg_type = message.get("type", "")
        if msg_type in STATEFUL_MESSAGE_TYPES:
            self._publish_stateful(msg_type, message)
        else:
            self._publish_critical(msg_type, message)

    def _publish_stateful(self, msg_type: str, message: dict) -> None:
        # 状态型消息：每个订阅者按主题合并（只保留最新值）
        topic = self._stateful_topic(msg_type, message)
        for sub in list(self._subscribers.values()):
            if msg_type in sub.message_types:
                if sub.merge_stateful(msg_type, topic, message):
                    self.merged_count += 1

    def _publish_critical(self, msg_type: str, message: dict) -> None:
        # 关键事件：必须按顺序送达；队列持续满时断开慢客户端
        ts = time.time()
        for sub_id, sub in list(self._subscribers.items()):
            if msg_type in sub.message_types:
                try:
                    sub.enqueue_critical(message, ts)
                except _QueueFull:
                    self.dropped_count += 1
                    logger.warning(
                        f"Subscriber {sub_id} is too slow (queue full, {self._max_queue_size}"
                        " messages), disconnecting to prevent memory growth."
                    )
                    self.unsubscribe(sub_id)

    @staticmethod
    def _stateful_topic(msg_type: str, message: dict) -> str:
        if msg_type == "new_candle":
            # new_candle: [pair, timeframe] —— 按 pair 合并
            data = message.get("data")
            if isinstance(data, (list, tuple)) and data:
                return f"{msg_type}:{data[0]}"
            return f"{msg_type}:"
        if msg_type == "analyzed_df":
            # analyzed_df: data["pair"] —— 按 pair 合并
            data = message.get("data")
            if isinstance(data, dict):
                return f"{msg_type}:{data.get('pair', '')}"
            return f"{msg_type}:"
        # whitelist 等：全局单槽（整个列表是最新值）
        return f"{msg_type}:"

    # ------------------------------------------------------------------ #
    # 消费者迭代

    def subscribe_and_iterate(self, message_types: list[str]):
        """Context manager helper: subscribe, yield messages, unsubscribe on exit.

        Usage:
            async with stream.subscribe_and_iterate(types) as (sub_id, messages):
                async for message, ts in messages:
                    ...
        """
        return _SubscriberContext(self, message_types)

    def iterate(self, subscriber_id: int):
        """Return the async iterator for an existing subscriber."""
        sub = self._subscribers.get(subscriber_id)
        if sub is None:
            raise KeyError(f"Subscriber {subscriber_id} not found")
        return sub.__aiter__()


class _Subscriber:
    """Per-subscriber state: critical-event queue + stateful merge slots."""

    def __init__(self, message_types: set[str], max_queue: int):
        self.message_types = message_types
        self._max_queue = max_queue
        self._critical: asyncio.Queue | None = None
        self._stateful: dict[str, tuple[dict, float]] = {}
        self._closed = False

    def _get_critical_queue(self) -> asyncio.Queue:
        # 惰性创建：MessageStream 可能在没有事件循环的同步上下文中构造（如测试）
        if self._critical is None:
            self._critical = asyncio.Queue(maxsize=self._max_queue)
        return self._critical

    def enqueue_critical(self, message: dict, ts: float) -> None:
        if self._closed:
            return
        q = self._get_critical_queue()
        if q.full():
            raise _QueueFull()
        q.put_nowait((message, ts))

    def merge_stateful(self, msg_type: str, topic: str, message: dict) -> bool:
        """Merge a stateful message into the per-topic slot. Returns True if replaced."""
        if self._closed:
            return False
        if len(self._stateful) >= STATEFUL_SLOT_MAX and topic not in self._stateful:
            # 防止 stateful 槽无限增长（极端情况下丢弃最旧的槽）
            self._stateful.pop(next(iter(self._stateful)))
        self._stateful[topic] = (message, time.time())
        return True

    async def __aiter__(self):
        """Iterate critical events first, then flush merged stateful slots."""
        q = self._get_critical_queue()
        while not self._closed:
            # 关键事件优先
            try:
                message, ts = q.get_nowait()
                yield message, ts
                continue
            except asyncio.QueueEmpty:
                pass

            # 状态型消息：取出即从槽中移除（避免 yield 期间持有消息对象）
            if self._stateful:
                topic, (message, ts) = self._stateful.popitem()
                yield message, ts
                continue

            # 全部为空：等待关键事件到达或关闭
            if self._closed:
                return
            try:
                message, ts = await asyncio.wait_for(
                    q.get(), timeout=1.0
                )
                yield message, ts
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                return

    def close(self) -> None:
        self._closed = True
        self._stateful.clear()


class _QueueFull(Exception):
    pass


class _SubscriberContext:
    """async context manager that subscribes and always unsubscribes."""

    def __init__(self, stream: MessageStream, message_types: list[str]):
        self._stream = stream
        self._message_types = message_types

    async def __aenter__(self):
        self._sub_id = self._stream.subscribe(self._message_types)
        sub = self._stream._subscribers[self._sub_id]
        return self._sub_id, sub

    async def __aexit__(self, *exc):
        # 客户端断开后必须在 finally 中注销订阅者并清空队列
        if hasattr(self, "_sub_id"):
            self._stream.unsubscribe(self._sub_id)
        return False
