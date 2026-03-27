"""Асинхронная отправка метрик в Kafka."""

import asyncio
import json
import logging
from typing import Any, Optional

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

from .config import KafkaConfig, KafkaSecurityConfig
from .collector import Metric


logger = logging.getLogger(__name__)


class KafkaSender:
    """Асинхронный отправщик метрик в Kafka."""

    def __init__(
        self,
        config: KafkaConfig,
        performance_config: dict[str, Any],
    ):
        self.config = config
        self.performance_config = performance_config
        self._producer: Optional[AIOKafkaProducer] = None
        self._retry_count = config.producer.retries
        self._retry_backoff = config.producer.retry_backoff_ms / 1000  # ms -> s

    async def start(self) -> None:
        """Инициализировать Kafka продюсер."""
        # SSL настройки
        ssl_context = None
        security = self.config.security
        if security.protocol in ("SSL", "SASL_SSL"):
            import ssl

            ssl_context = ssl.create_default_context(cafile=security.ssl.ca_file)
            if security.ssl.cert_file and security.ssl.key_file:
                ssl_context.load_cert_chain(
                    certfile=security.ssl.cert_file,
                    keyfile=security.ssl.key_file,
                    password=security.ssl.password or None,
                )

        # SASL настройки
        sasl_mechanism = None
        sasl_plain_username = None
        sasl_plain_password = None

        if security.protocol in ("SASL_PLAINTEXT", "SASL_SSL"):
            sasl_mechanism = security.sasl.mechanism
            sasl_plain_username = security.sasl.username
            sasl_plain_password = security.sasl.password

        self._producer = AIOKafkaProducer(
            bootstrap_servers=",".join(self.config.brokers),
            security_protocol=security.protocol,
            ssl_context=ssl_context,
            sasl_mechanism=sasl_mechanism,
            sasl_plain_username=sasl_plain_username,
            sasl_plain_password=sasl_plain_password,
            batch_size=self.config.producer.batch_size,
            linger_ms=self.config.producer.linger_ms,
            compression_type=self.config.producer.compression_type,
            acks=self.config.producer.acks,
            retries=self.config.producer.retries,
            retry_backoff_ms=self.config.producer.retry_backoff_ms,
        )

        await self._producer.start()

    async def stop(self) -> None:
        """Закрыть Kafka продюсер."""
        if self._producer:
            await self._producer.stop()
            self._producer = None

    async def send(self, metric: Metric, formatted: str) -> bool:
        """Отправить метрику в Kafka с retry."""
        if not self._producer:
            raise RuntimeError("Sender not started. Call start() first.")

        for attempt in range(self._retry_count + 1):
            try:
                await asyncio.wait_for(
                    self._producer.send_and_wait(
                        self.config.topic,
                        value=formatted.encode("utf-8"),
                        key=metric.name.encode("utf-8"),
                    ),
                    timeout=self.performance_config.get("send_timeout", 5),
                )
                logger.debug(f"Sent metric {metric.name} to {self.config.topic}")
                return True

            except asyncio.TimeoutError:
                logger.warning(f"Timeout sending metric {metric.name}, attempt {attempt + 1}")
                if attempt < self._retry_count:
                    await asyncio.sleep(self._retry_backoff * (attempt + 1))

            except KafkaError as e:
                logger.warning(f"Kafka error sending metric {metric.name}: {e}, attempt {attempt + 1}")
                if attempt < self._retry_count:
                    await asyncio.sleep(self._retry_backoff * (attempt + 1))
                else:
                    logger.error(f"Failed to send metric {metric.name} after {self._retry_count + 1} attempts")

            except Exception as e:
                logger.error(f"Unexpected error sending metric {metric.name}: {e}")
                return False

        return False

    async def send_batch(self, metrics: list[tuple[Metric, str]]) -> int:
        """Отправить пакет метрик. Возвращает количество успешно отправленных."""
        if not self._producer:
            raise RuntimeError("Sender not started. Call start() first.")

        sent_count = 0
        tasks = []

        for metric, formatted in metrics:
            tasks.append(self._send_with_retry(metric, formatted))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if result is True:
                sent_count += 1

        return sent_count

    async def _send_with_retry(self, metric: Metric, formatted: str) -> bool:
        """Отправить с retry логикой."""
        for attempt in range(self._retry_count + 1):
            try:
                await asyncio.wait_for(
                    self._producer.send_and_wait(
                        self.config.topic,
                        value=formatted.encode("utf-8"),
                        key=metric.name.encode("utf-8"),
                    ),
                    timeout=self.performance_config.get("send_timeout", 5),
                )
                return True

            except (asyncio.TimeoutError, KafkaError) as e:
                logger.debug(f"Retry {attempt + 1}/{self._retry_count} for {metric.name}: {e}")
                if attempt < self._retry_count:
                    await asyncio.sleep(self._retry_backoff * (attempt + 1))

            except Exception as e:
                logger.error(f"Unexpected error sending metric {metric.name}: {e}")
                return False

        return False
