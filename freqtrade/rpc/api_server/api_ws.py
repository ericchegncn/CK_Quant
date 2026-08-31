import logging
import time
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.websockets import WebSocket
from pydantic import ValidationError

from freqtrade.enums import RPCMessageType, RPCRequestType
from freqtrade.exceptions import FreqtradeException
from freqtrade.rpc.api_server.api_auth import validate_ws_token
from freqtrade.rpc.api_server.deps import get_message_stream, get_rpc
from freqtrade.rpc.api_server.ws.channel import WebSocketChannel, create_channel
from freqtrade.rpc.api_server.ws.message_stream import MessageStream
from freqtrade.rpc.api_server.ws_schemas import (
    WSAnalyzedDFMessage,
    WSErrorMessage,
    WSMessageSchema,
    WSRequestSchema,
    WSWhitelistMessage,
)
from freqtrade.rpc.rpc import RPC


logger = logging.getLogger(__name__)

# Private router, protected by API Key authentication
router = APIRouter()


async def channel_reader(
    channel: WebSocketChannel,
    rpc: RPC,
    message_stream: MessageStream,
    subscriber_id: int,
):
    """
    Iterate over the messages from the channel and process the request
    """
    async for message in channel:
        try:
            await _process_consumer_request(message, channel, rpc, message_stream, subscriber_id)
        except FreqtradeException:
            logger.exception(f"Error processing request from {channel}")
            response = WSErrorMessage(data="Error processing request")

            await channel.send(response.model_dump(exclude_none=True))


async def channel_broadcaster(
    channel: WebSocketChannel,
    message_stream: MessageStream,
    subscriber_id: int,
):
    """
    Iterate over the messages for this channel's subscription and send them.
    4.5 低内存加固：每个连接按自己的订阅注册到有界 MessageStream，
    未订阅的消息类型不会进入此连接的队列（内存有界）。
    """
    async for message, ts in message_stream.iterate(subscriber_id):
        if channel.is_closed():
            break
        # Log a warning if this channel is behind
        # on the message stream by a lot
        if (time.time() - ts) > 60:
            logger.warning(
                f"Channel {channel} is behind MessageStream by 1 minute,"
                " this can cause a memory leak if you see this message"
                " often, consider reducing pair list size or amount of"
                " consumers."
            )

        await channel.send(message, use_timeout=True)


async def _process_consumer_request(
    request: dict[str, Any],
    channel: WebSocketChannel,
    rpc: RPC,
    message_stream: MessageStream,
    subscriber_id: int,
):
    """
    Validate and handle a request from a websocket consumer
    """
    # Validate the request, makes sure it matches the schema
    response: WSMessageSchema
    try:
        websocket_request = WSRequestSchema.model_validate(request)
    except ValidationError as e:
        logger.error(f"Invalid request from {channel}: {e}")
        response = WSErrorMessage(data=f"Invalid request type: {request.get('type')}")

        await channel.send(response.model_dump(exclude_none=True))
        return

    type_, data = websocket_request.type, websocket_request.data

    logger.debug(f"Request of type {type_} from {channel}")

    # If we have a request of type SUBSCRIBE, set the topics in this channel
    if type_ == RPCRequestType.SUBSCRIBE:
        # If the request is empty, do nothing
        if not data:
            return

        # If all topics passed are a valid RPCMessageType, set subscriptions on channel
        if all([any(x.value == topic for x in RPCMessageType) for topic in data]):
            channel.set_subscriptions(data)
            # 4.5：同步更新 MessageStream 订阅 —— 未订阅的类型不再入队
            message_stream.set_subscriptions(subscriber_id, data)

        # We don't send a response for subscriptions
        return

    elif type_ == RPCRequestType.WHITELIST:
        # Get whitelist
        whitelist = rpc._ws_request_whitelist()

        # Format response
        response = WSWhitelistMessage(data=whitelist)
        await channel.send(response.model_dump(exclude_none=True))

    elif type_ == RPCRequestType.PING:
        # 4.4 应用层心跳：响应 PONG，响应体保持极小（不访问数据库）
        await channel.send({"type": "pong", "data": ""})

    elif type_ == RPCRequestType.ANALYZED_DF:
        # Limit the amount of candles per dataframe to 'limit' or 1500
        limit = int(min(data.get("limit", 1500), 1500)) if data else None
        pair = data.get("pair", None) if data else None

        # For every pair in the generator, send a separate message
        for message in rpc._ws_request_analyzed_df(limit, pair):
            # Format response
            response = WSAnalyzedDFMessage(data=message)
            await channel.send(response.model_dump(exclude_none=True))


@router.websocket("/message/ws")
async def message_endpoint(
    websocket: WebSocket,
    token: str = Depends(validate_ws_token),
    rpc: RPC = Depends(get_rpc),
    message_stream: MessageStream = Depends(get_message_stream),
):
    if token:
        async with create_channel(websocket) as channel:
            # 4.5：每个连接注册一个订阅者；断开时在 finally 中注销
            subscriber_id = message_stream.subscribe([t.value for t in RPCMessageType])
            try:
                await channel.run_channel_tasks(
                    channel_reader(channel, rpc, message_stream, subscriber_id),
                    channel_broadcaster(channel, message_stream, subscriber_id),
                )
            finally:
                message_stream.unsubscribe(subscriber_id)
