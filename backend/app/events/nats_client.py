"""NATS Client with JetStream support for Base Camp OS."""
import os
import json
import asyncio
from typing import Optional, Callable, Any, Dict, List
from datetime import datetime

import nats
from nats.js.api import StreamConfig, ConsumerConfig, DeliverPolicy, AckPolicy
from nats.aio.client import Client as NATSConnection
from nats.js import JetStreamContext


class NATSClient:
    SUBJECTS = {
        "ingestion": "basecamp.ingestion.*",
        "enrichment": "basecamp.enrichment.*",
        "entity": "basecamp.entity.*",
    }

    STREAM_NAME = "BASECAMP"

    def __init__(self, nats_url=None):
        self.nats_url = nats_url or os.getenv("NATS_URL", "nats://localhost:4222")
        self._nc = None
        self._js = None
        self._subscriptions = {}
        self._connected = False

    @property
    def is_connected(self):
        return self._connected and self._nc is not None and self._nc.is_connected

    async def connect(self):
        if self.is_connected:
            return
        try:
            self._nc = await nats.connect(
                self.nats_url,
                reconnect_time_wait=2,
                max_reconnect_attempts=10,
                error_cb=self._error_callback,
                disconnected_cb=self._disconnected_callback,
                reconnected_cb=self._reconnected_callback,
            )
            self._js = self._nc.jetstream()
            self._connected = True
            await self._ensure_stream()
            print(f"Connected to NATS at {self.nats_url}")
        except Exception as e:
            self._connected = False
            print(f"Failed to connect to NATS: {e}")
            raise

    async def disconnect(self):
        if self._nc:
            for sub in self._subscriptions.values():
                await sub.unsubscribe()
            self._subscriptions.clear()
            await self._nc.drain()
            await self._nc.close()
            self._nc = None
            self._js = None
            self._connected = False
            print("Disconnected from NATS")

    async def _ensure_stream(self):
        if not self._js:
            return
        try:
            await self._js.stream_info(self.STREAM_NAME)
        except nats.js.errors.NotFoundError:
            await self._js.add_stream(
                name=self.STREAM_NAME,
                subjects=[
                    "basecamp.ingestion.*",
                    "basecamp.enrichment.*",
                    "basecamp.entity.*",
                ],
                retention="limits",
                max_msgs=100000,
                max_bytes=1024 * 1024 * 512,
                max_age=86400 * 7,
                storage="file",
                num_replicas=1,
            )
            print(f"Created JetStream stream: {self.STREAM_NAME}")

    async def publish_event(self, subject, data, headers=None):
        if not self.is_connected:
            await self.connect()
        if "timestamp" not in data:
            data["timestamp"] = datetime.utcnow().isoformat()
        payload = json.dumps(data).encode()
        if self._js:
            ack = await self._js.publish(subject, payload, headers=headers)
            print(f"Published event to {subject}, seq: {ack.seq}")
            return str(ack.seq)
        else:
            await self._nc.publish(subject, payload)
            print(f"Published event to {subject} (core NATS)")
            return "0"

    async def subscribe(self, subject, callback, durable=None, queue=None):
        if not self.is_connected:
            await self.connect()

        async def message_handler(msg):
            try:
                data = json.loads(msg.data.decode())
                await callback(data)
                if hasattr(msg, "ack"):
                    await msg.ack()
            except Exception as e:
                print(f"Error processing message from {msg.subject}: {e}")
                if hasattr(msg, "nak"):
                    await msg.nak()

        sub_id = f"{subject}_{len(self._subscriptions)}"
        if self._js and durable:
            sub = await self._js.subscribe(subject, durable=durable, queue=queue, cb=message_handler)
        else:
            sub = await self._nc.subscribe(subject, queue=queue or "", cb=message_handler)
        self._subscriptions[sub_id] = sub
        print(f"Subscribed to {subject} with ID {sub_id}")
        return sub_id

    async def unsubscribe(self, subscription_id):
        if subscription_id in self._subscriptions:
            await self._subscriptions[subscription_id].unsubscribe()
            del self._subscriptions[subscription_id]
            print(f"Unsubscribed from {subscription_id}")
            return True
        return False

    def get_subscriptions(self):
        return list(self._subscriptions.keys())

    @staticmethod
    async def _error_callback(e):
        print(f"NATS error: {e}")

    async def _disconnected_callback(self):
        self._connected = False
        print("Disconnected from NATS")

    async def _reconnected_callback(self):
        self._connected = True
        print("Reconnected to NATS")


_nats_client = None


async def get_nats_client():
    global _nats_client
    if _nats_client is None:
        _nats_client = NATSClient()
    if not _nats_client.is_connected:
        await _nats_client.connect()
    return _nats_client
