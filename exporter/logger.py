"""Logging configuration."""

import logging
import sys
from asyncio import Queue
from logging.handlers import QueueHandler, QueueListener
from typing import Any, Optional

from .config import LoggingConfig, LoggingKafkaConfig


class KafkaHandler(logging.Handler):
    """Kafka logging handler."""

    def __init__(
        self,
        kafka_config: LoggingKafkaConfig,
        kafka_params: dict[str, Any],
    ):
        super().__init__()
        self.kafka_config = kafka_config
        self.kafka_params = kafka_params
        self._producer = None
        self._queue: Optional[Queue] = None
        self._listener: Optional[QueueListener] = None

    def start(self) -> None:
        """Start async logging."""
        import asyncio
        from aiokafka import AIOKafkaProducer

        self._queue = Queue(maxsize=1000)

        # Create producer for logs
        security = self.kafka_params.get("security", {})
        ssl_context = None
        if security.get("protocol") in ("SSL", "SASL_SSL"):
            import ssl

            ssl_config = security.get("ssl", {})
            ssl_context = ssl.create_default_context(cafile=ssl_config.get("ca_file", ""))
            if ssl_config.get("cert_file") and ssl_config.get("key_file"):
                ssl_context.load_cert_chain(
                    certfile=ssl_config["cert_file"],
                    keyfile=ssl_config["key_file"],
                    password=ssl_config.get("password") or None,
                )

        sasl_mechanism = None
        sasl_username = None
        sasl_password = None
        if security.get("protocol") in ("SASL_PLAINTEXT", "SASL_SSL"):
            sasl = security.get("sasl", {})
            sasl_mechanism = sasl.get("mechanism", "PLAIN")
            sasl_username = sasl.get("username", "")
            sasl_password = sasl.get("password", "")

        self._producer = AIOKafkaProducer(
            bootstrap_servers=",".join(self.kafka_params.get("brokers", ["kafka:9092"])),
            security_protocol=security.get("protocol", "PLAINTEXT"),
            ssl_context=ssl_context,
            sasl_mechanism=sasl_mechanism,
            sasl_plain_username=sasl_username,
            sasl_plain_password=sasl_password,
        )

        async def send_logs():
            await self._producer.start()
            try:
                while True:
                    record = await self._queue.get()
                    if record is None:
                        break
                    try:
                        message = self.format(record)
                        await self._producer.send_and_wait(
                            self.kafka_config.topic,
                            value=message.encode("utf-8"),
                        )
                    except Exception as e:
                        sys.stderr.write(f"Kafka log error: {e}\n")
            finally:
                await self._producer.stop()

        self._listener = QueueListener(self._queue, asyncio.create_task(send_logs()))
        self._listener.start()

    def stop(self) -> None:
        """Stop logging."""
        if self._listener:
            self._queue.put_nowait(None)
            self._listener.stop()
            self._listener = None

    def emit(self, record: logging.LogRecord) -> None:
        """Send record to queue."""
        try:
            msg = self.format(record)
            if self._queue:
                try:
                    self._queue.put_nowait(record)
                except asyncio.QueueFull:
                    sys.stderr.write(f"Log queue full, dropping: {msg}\n")
        except Exception:
            self.handleError(record)


def setup_logging(config: LoggingConfig, kafka_params: Optional[dict[str, Any]] = None) -> logging.Logger:
    """Configure logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level.upper(), logging.INFO))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Stdout handler
    if config.stdout.enabled:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(getattr(logging, config.level.upper(), logging.INFO))
        stdout_handler.setFormatter(logging.Formatter(config.stdout.format))
        root_logger.addHandler(stdout_handler)

    # Kafka handler
    if config.kafka.enabled and kafka_params:
        kafka_handler = KafkaHandler(config.kafka, kafka_params)
        kafka_handler.setLevel(getattr(logging, config.level.upper(), logging.INFO))
        if config.kafka.format:
            kafka_handler.setFormatter(logging.Formatter(config.kafka.format))
        kafka_handler.start()

    return root_logger
