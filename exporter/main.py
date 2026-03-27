"""Prometheus Kafka Exporter - точка входа."""

import asyncio
import logging
import signal
import sys
from pathlib import Path

from prometheus_client import start_http_server

from .config import Config, load_config
from .collector import PrometheusCollector
from .formatter import MetricFormatter
from .sender import KafkaSender
from .logger import setup_logging


logger = logging.getLogger(__name__)


class PrometheusKafkaExporter:
    """Основной класс экспортера."""

    def __init__(self, config: Config):
        self.config = config
        self._collector: Optional[PrometheusCollector] = None
        self._sender: Optional[KafkaSender] = None
        self._formatter: Optional[MetricFormatter] = None
        self._running = False

    async def start(self) -> None:
        """Запустить экспортер."""
        logger.info("Starting Prometheus Kafka Exporter...")

        # Настроить логирование
        kafka_params = {
            "brokers": self.config.kafka.brokers,
            "security": {
                "protocol": self.config.kafka.security.protocol,
                "ssl": {
                    "ca_file": self.config.kafka.security.ssl.ca_file,
                    "cert_file": self.config.kafka.security.ssl.cert_file,
                    "key_file": self.config.kafka.security.ssl.key_file,
                    "password": self.config.kafka.security.ssl.password,
                },
                "sasl": {
                    "mechanism": self.config.kafka.security.sasl.mechanism,
                    "username": self.config.kafka.security.sasl.username,
                    "password": self.config.kafka.security.sasl.password,
                },
            },
        }
        setup_logging(self.config.logging, kafka_params)

        # Запустить метрики экспортера
        if self.config.exporter_metrics.enabled:
            start_http_server(
                self.config.exporter_metrics.port,
                addr="0.0.0.0",
            )
            logger.info(
                f"Exporter metrics available at :{self.config.exporter_metrics.port}"
                f"{self.config.exporter_metrics.path}"
            )

        # Инициализировать компоненты
        self._formatter = MetricFormatter(self.config.format)

        self._collector = PrometheusCollector(
            self.config.prometheus,
            {
                "scrape_timeout": self.config.performance.scrape_timeout,
                "scrape_workers": self.config.performance.scrape_workers,
            },
        )
        await self._collector.start()
        logger.info(f"Collector initialized for {self.config.prometheus.url}")

        self._sender = KafkaSender(
            self.config.kafka,
            {
                "send_timeout": self.config.performance.send_timeout,
                "send_buffer_size": self.config.performance.send_buffer_size,
            },
        )
        await self._sender.start()
        logger.info(f"Sender initialized for {self.config.kafka.brokers}")

        self._running = True
        logger.info("Prometheus Kafka Exporter started successfully")

    async def stop(self) -> None:
        """Остановить экспортер."""
        logger.info("Stopping Prometheus Kafka Exporter...")
        self._running = False

        if self._collector:
            await self._collector.stop()

        if self._sender:
            await self._sender.stop()

        logger.info("Prometheus Kafka Exporter stopped")

    async def run(self) -> None:
        """Основный цикл работы."""
        if not self._running:
            raise RuntimeError("Exporter not started. Call start() first.")

        logger.info(
            f"Starting scrape loop with interval={self.config.scrape_interval}s"
        )

        while self._running:
            try:
                await self._scrape_and_send()
            except Exception as e:
                logger.error(f"Error in scrape loop: {e}")

            await asyncio.sleep(self.config.scrape_interval)

    async def _scrape_and_send(self) -> None:
        """Собрать и отправить метрики."""
        # Собрать метрики
        metrics = await self._collector.collect()
        logger.debug(f"Collected {len(metrics)} metrics")

        if not metrics:
            logger.warning("No metrics collected")
            return

        # Форматировать метрики
        formatted = []
        for metric in metrics:
            try:
                json_str = self._formatter.format(metric)
                formatted.append((metric, json_str))
            except Exception as e:
                logger.error(f"Error formatting metric {metric.name}: {e}")

        # Отправить в Kafka
        if formatted:
            sent = await self._sender.send_batch(formatted)
            logger.info(f"Sent {sent}/{len(formatted)} metrics to Kafka")


async def main(config_path: str = "/etc/config/config.yaml") -> None:
    """Точка входа."""
    # Загрузить конфигурацию
    config_file = Path(config_path)
    if not config_file.exists():
        # Попробовать альтернативные пути
        for alt_path in ["config/config.yaml", "./config.yaml", "/config/config.yaml"]:
            config_file = Path(alt_path)
            if config_file.exists():
                break

    if not config_file.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    config = load_config(config_file)
    logger.info(f"Loaded config from {config_file}")

    exporter = PrometheusKafkaExporter(config)

    # Обработчики сигналов
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()

    def signal_handler():
        logger.info("Received shutdown signal")
        shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await exporter.start()
        
        # Запустить основной цикл и ждать сигнала остановки
        main_task = asyncio.create_task(exporter.run())
        
        await shutdown_event.wait()
        
        exporter._running = False
        await asyncio.sleep(0.1)  # Дать циклу завершиться
        main_task.cancel()
        
        try:
            await main_task
        except asyncio.CancelledError:
            pass

    except Exception as e:
        logger.error(f"Exporter error: {e}")
        raise
    finally:
        await exporter.stop()


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "/etc/config/config.yaml"
    asyncio.run(main(config_path))
