"""
End-to-End нагрузочный тест для Prometheus Kafka Exporter.

Тестирует полный цикл:
1. Сбор метрик с Prometheus
2. Форматирование в JSON
3. Отправка в Kafka
4. Чтение из Kafka и валидация

Запуск:
    python load-tests/e2e_load_test.py --duration 60 --rps 100
"""

import argparse
import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer


@dataclass
class TestStats:
    """Статистика теста."""
    total_scrapes: int = 0
    successful_scrapes: int = 0
    failed_scrapes: int = 0
    total_messages: int = 0
    kafka_errors: int = 0
    scrape_latencies: list = field(default_factory=list)
    kafka_latencies: list = field(default_factory=list)
    start_time: float = 0
    end_time: float = 0


class EndToEndLoadTest:
    """End-to-End нагрузочный тест."""

    def __init__(
        self,
        exporter_url: str = "http://localhost:8080",
        kafka_bootstrap: str = "localhost:9092",
        kafka_topic: str = "prometheus-metrics",
        duration: int = 60,
        target_rps: int = 100,
        num_consumers: int = 3,
    ):
        self.exporter_url = exporter_url
        self.kafka_bootstrap = kafka_bootstrap
        self.kafka_topic = kafka_topic
        self.duration = duration
        self.target_rps = target_rps
        self.num_consumers = num_consumers
        self.stats = TestStats()
        self._stop_event = asyncio.Event()
        self._session: Optional[aiohttp.ClientSession] = None
        self._producer: Optional[AIOKafkaProducer] = None
        self._consumers: list[AIOKafkaConsumer] = []

    async def setup(self):
        """Инициализация соединений."""
        # HTTP сессия
        connector = aiohttp.TCPConnector(limit=200, limit_per_host=50)
        self._session = aiohttp.ClientSession(connector=connector)

        # Kafka продюсер
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.kafka_bootstrap,
            max_batch_size=16384,
            linger_ms=10,
            compression_type="gzip",
        )
        await self._producer.start()

        # Kafka консьюмеры для валидации
        for i in range(self.num_consumers):
            consumer = AIOKafkaConsumer(
                self.kafka_topic,
                bootstrap_servers=self.kafka_bootstrap,
                auto_offset_reset="earliest",
                consumer_timeout_ms=1000,
                group_id=f"load-test-consumer-{i}",
            )
            await consumer.start()
            self._consumers.append(consumer)

    async def teardown(self):
        """Закрытие соединений."""
        if self._session:
            await self._session.close()
        if self._producer:
            await self._producer.stop()
        for consumer in self._consumers:
            await consumer.stop()

    async def run(self):
        """Запуск теста."""
        print(f"\n{'='*60}")
        print(f"End-to-End Load Test")
        print(f"{'='*60}")
        print(f"Exporter URL: {self.exporter_url}")
        print(f"Kafka: {self.kafka_bootstrap}/{self.kafka_topic}")
        print(f"Duration: {self.duration}s")
        print(f"Target RPS: {self.target_rps}")
        print(f"Consumers: {self.num_consumers}")
        print(f"{'='*60}\n")

        await self.setup()

        self.stats.start_time = time.time()
        end_time = self.stats.start_time + self.duration

        # Запускаем воркеры
        scrape_worker = asyncio.create_task(self._scrape_worker(end_time))
        validate_worker = asyncio.create_task(self._validate_worker())

        # Ждём завершения
        await scrape_worker
        self._stop_event.set()
        await validate_worker

        self.stats.end_time = time.time()
        self._print_report()

        await self.teardown()

    async def _scrape_worker(self, end_time: float):
        """Воркер для сбора метрик."""
        interval = 1.0 / self.target_rps

        while time.time() < end_time:
            start = time.time()
            try:
                # Запрос к exporter metrics endpoint
                async with self._session.get(
                    f"{self.exporter_url}/metrics",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    self.stats.total_scrapes += 1

                    if response.status == 200:
                        self.stats.successful_scrapes += 1
                        latency = (time.time() - start) * 1000
                        self.stats.scrape_latencies.append(latency)

                        # Отправка в Kafka (симуляция работы экспортера)
                        await self._send_to_kafka(await response.text())
                    else:
                        self.stats.failed_scrapes += 1

            except Exception as e:
                self.stats.failed_scrapes += 1
                print(f"Scrape error: {e}")

            # Контроль RPS
            elapsed = time.time() - start
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)

    async def _send_to_kafka(self, metrics_text: str):
        """Отправка метрик в Kafka."""
        try:
            # Парсим метрики (упрощённо)
            lines = metrics_text.strip().split('\n')
            messages = []

            for line in lines[:10]:  # Ограничим для теста
                if line and not line.startswith('#'):
                    parts = line.split()
                    if len(parts) >= 2:
                        msg = {
                            "name": parts[0],
                            "value": float(parts[1]) if parts[1].replace('.', '').isdigit() else 0,
                            "timestamp": int(time.time() * 1000),
                        }
                        messages.append(json.dumps(msg).encode())

            # Отправка батчем
            if messages:
                send_start = time.time()
                for msg in messages:
                    await self._producer.send_and_wait(self.kafka_topic, value=msg)
                    self.stats.total_messages += 1

                kafka_latency = (time.time() - send_start) * 1000
                self.stats.kafka_latencies.append(kafka_latency)

        except Exception as e:
            self.stats.kafka_errors += 1
            print(f"Kafka send error: {e}")

    async def _validate_worker(self):
        """Воркер для валидации сообщений в Kafka."""
        validated = 0
        errors = 0

        while not self._stop_event.is_set():
            for consumer in self._consumers:
                try:
                    msg = await consumer.getone()
                    if msg:
                        try:
                            data = json.loads(msg.value.decode())
                            if "name" in data and "value" in data and "timestamp" in data:
                                validated += 1
                            else:
                                errors += 1
                        except json.JSONDecodeError:
                            errors += 1
                except Exception:
                    pass

        print(f"\nValidation: {validated} valid, {errors} errors")

    def _print_report(self):
        """Печать отчёта."""
        duration = self.stats.end_time - self.stats.start_time
        actual_rps = self.stats.total_scrapes / duration if duration > 0 else 0

        scrape_p50 = self._percentile(self.stats.scrape_latencies, 50) if self.stats.scrape_latencies else 0
        scrape_p95 = self._percentile(self.stats.scrape_latencies, 95) if self.stats.scrape_latencies else 0
        scrape_p99 = self._percentile(self.stats.scrape_latencies, 99) if self.stats.scrape_latencies else 0

        kafka_p50 = self._percentile(self.stats.kafka_latencies, 50) if self.stats.kafka_latencies else 0
        kafka_p95 = self._percentile(self.stats.kafka_latencies, 95) if self.stats.kafka_latencies else 0
        kafka_p99 = self._percentile(self.stats.kafka_latencies, 99) if self.stats.kafka_latencies else 0

        print(f"\n{'='*60}")
        print("LOAD TEST REPORT")
        print(f"{'='*60}")
        print(f"\n📊 Общие метрики:")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Total scrapes: {self.stats.total_scrapes}")
        print(f"  Successful: {self.stats.successful_scrapes}")
        print(f"  Failed: {self.stats.failed_scrapes}")
        print(f"  Actual RPS: {actual_rps:.2f}")
        print(f"  Target RPS: {self.target_rps}")
        print(f"  Success rate: {self.stats.successful_scrapes / self.stats.total_scrapes * 100:.2f}%")

        print(f"\n📈 Scrape latency (ms):")
        print(f"  p50: {scrape_p50:.2f}")
        print(f"  p95: {scrape_p95:.2f}")
        print(f"  p99: {scrape_p99:.2f}")

        print(f"\n📤 Kafka latency (ms):")
        print(f"  p50: {kafka_p50:.2f}")
        print(f"  p95: {kafka_p95:.2f}")
        print(f"  p99: {kafka_p99:.2f}")

        print(f"\n💾 Kafka messages:")
        print(f"  Total sent: {self.stats.total_messages}")
        print(f"  Errors: {self.stats.kafka_errors}")

        print(f"\n{'='*60}\n")

    @staticmethod
    def _percentile(data: list, percentile: int) -> float:
        """Вычисление перцентиля."""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]


def main():
    parser = argparse.ArgumentParser(description="End-to-End Load Test")
    parser.add_argument("--exporter-url", default="http://localhost:8080", help="Exporter URL")
    parser.add_argument("--kafka-bootstrap", default="localhost:9092", help="Kafka bootstrap servers")
    parser.add_argument("--kafka-topic", default="prometheus-metrics", help="Kafka topic")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument("--rps", type=int, default=100, help="Target requests per second")
    parser.add_argument("--consumers", type=int, default=3, help="Number of Kafka consumers")

    args = parser.parse_args()

    test = EndToEndLoadTest(
        exporter_url=args.exporter_url,
        kafka_bootstrap=args.kafka_bootstrap,
        kafka_topic=args.kafka_topic,
        duration=args.duration,
        target_rps=args.rps,
        num_consumers=args.consumers,
    )

    asyncio.run(test.run())


if __name__ == "__main__":
    main()
