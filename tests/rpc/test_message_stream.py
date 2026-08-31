import asyncio

import pytest

from freqtrade.rpc.api_server.ws.message_stream import (
    MessageStream,
    QUEUE_MAX_SIZE,
    _Subscriber,
)


@pytest.mark.parametrize("method", ["_publish_critical", "_publish_stateful"])
def test_stream_unsubscribed_type_not_queued(method):
    """未订阅的消息类型不会入队（4.5 低内存加固核心）"""
    loop = asyncio.new_event_loop()
    try:
        stream = MessageStream()
        sub_id = stream.subscribe(["status"])
        sub = stream._subscribers[sub_id]

        if method == "_publish_critical":
            stream.publish({"type": "whitelist", "data": ["ETH/USDT"]})
            assert sub._get_critical_queue().empty()
        else:
            stream.publish({"type": "status", "data": "test"})
            assert sub._get_critical_queue().empty() is False

        stream.unsubscribe(sub_id)
    finally:
        loop.close()


def test_stream_stateful_merge_keeps_latest():
    """状态型消息（whitelist）合并：只保留最新值"""
    loop = asyncio.new_event_loop()
    try:
        stream = MessageStream()
        sub_id = stream.subscribe(["whitelist"])
        sub = stream._subscribers[sub_id]

        stream.publish({"type": "whitelist", "data": ["A"]})
        stream.publish({"type": "whitelist", "data": ["B"]})

        # 合并槽只有一个值（最新）
        assert len(sub._stateful) == 1
        topic, (message, _ts) = sub._stateful.popitem()
        assert message["data"] == ["B"]

        stream.unsubscribe(sub_id)
    finally:
        loop.close()


def test_stream_bounded_queue_disconnects_slow_consumer():
    """慢消费者：队列有界，满时主动断开并记录（不无限增长）"""
    loop = asyncio.new_event_loop()
    try:
        stream = MessageStream(max_queue_size=5)
        sub_id = stream.subscribe(["entry_fill"])

        for i in range(10):
            stream.publish({"type": "entry_fill", "data": f"trade-{i}"})

        # 队列满后慢消费者被断开
        assert sub_id not in stream._subscribers
        assert stream.dropped_count > 0

        stream.unsubscribe(sub_id)
    finally:
        loop.close()


def test_stream_unsubscribe_clears_queue():
    """断开连接后队列清空、订阅者数归零"""
    loop = asyncio.new_event_loop()
    try:
        stream = MessageStream()
        sub_id = stream.subscribe(["status"])
        stream.publish({"type": "status", "data": "x"})

        assert stream.subscriber_count == 1
        stream.unsubscribe(sub_id)

        assert stream.subscriber_count == 0
        assert sub_id not in stream._subscribers
    finally:
        loop.close()


def test_stream_two_clients_independent():
    """两个客户端可同时连接、互不阻塞、各自收各自的消息"""
    loop = asyncio.new_event_loop()
    try:
        stream = MessageStream()
        sub_a = stream.subscribe(["status"])
        sub_b = stream.subscribe(["status", "entry_fill"])

        stream.publish({"type": "status", "data": "s"})
        stream.publish({"type": "entry_fill", "data": "e"})

        a = stream._subscribers[sub_a]
        b = stream._subscribers[sub_b]
        assert not a._get_critical_queue().empty()
        # B 订阅了两个类型，两个消息都入队
        assert b._get_critical_queue().qsize() == 2

        stream.unsubscribe(sub_a)
        stream.unsubscribe(sub_b)
    finally:
        loop.close()


def test_subscriber_aiter_delivers_critical_then_stateful():
    """迭代器先送关键事件，再送合并的状态消息"""
    loop = asyncio.new_event_loop()
    try:
        stream = MessageStream()
        sub_id = stream.subscribe(["status", "whitelist"])

        stream.publish({"type": "status", "data": "first"})
        stream.publish({"type": "whitelist", "data": ["W"]})

        async def collect():
            messages = []
            async for message, _ts in stream.iterate(sub_id):
                messages.append(message)
                if len(messages) >= 2:
                    break
            return messages

        messages = loop.run_until_complete(collect())
        types = [m["type"] for m in messages]
        # 关键事件 status 先于状态消息 whitelist
        assert types[0] == "status"
        assert "whitelist" in types

        stream.unsubscribe(sub_id)
    finally:
        loop.close()
