"""Интеграционные тесты для Prometheus Kafka Exporter."""

import asyncio
import json
import time
from typing import Any

import pytest
from aiohttp import ClientSession
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer


class KafkaIntegrationTest:
    """Базовый класс для интеграционных тестов с Kafka."""

    KAFKA_BOOTSTRAP = "localhost:9092"
    PROMETHEUS_URL = "http://localhost:9090"
    EXPORTER_METRICS = "http://localhost:8080"

    @pytest.fixture
    async def kafka_producer(self):
        """Создать Kafka продюсер для тестов."""
        producer = AIOKafkaProducer(bootstrap_servers=self.KAFKA_BOOTSTRAP)
        await producer.start()
        try:
            yield producer
        finally:
            await producer.stop()

    @pytest.fixture
    async def kafka_consumer(self, topic: str):
        """Создать Kafka консьюмер для тестов."""
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=self.KAFKA_BOOTSTRAP,
            auto_offset_reset="earliest",
            consumer_timeout_ms=5000,
        )
        await consumer.start()
        try:
            yield consumer
        finally:
            await consumer.stop()

    @pytest.fixture
    async def http_session(self):
        """Создать HTTP сессию для тестов."""
        async with ClientSession() as session:
            yield session


class TestPrometheusAvailability(KafkaIntegrationTest):
    """Тесты доступности Prometheus."""

    @pytest.mark.asyncio
    async def test_prometheus_health(self, http_session: ClientSession):
        """Проверка здоровья Prometheus."""
        async with http_session.get(f"{self.PROMETHEUS_URL}/-/healthy") as response:
            assert response.status == 200

    @pytest.mark.asyncio
    async def test_prometheus_api(self, http_session: ClientSession):
        """Проверка API Prometheus."""
        async with http_session.get(
            f"{self.PROMETHEUS_URL}/api/v1/query",
            params={"query": "up"},
        ) as response:
            assert response.status == 200
            data = await response.json()
            assert data["status"] == "success"


class TestExporterMetrics(KafkaIntegrationTest):
    """Тесты метрик экспортера."""

    @pytest.mark.asyncio
    async def test_exporter_metrics_endpoint(self, http_session: ClientSession):
        """Проверка endpoint метрик экспортера."""
        async with http_session.get(f"{self.EXPORTER_METRICS}/metrics") as response:
            assert response.status == 200
            content = await response.text()
            assert "python_" in content or "process_" in content


class TestMetricCollection(KafkaIntegrationTest):
    """Тесты сбора метрик."""

    @pytest.mark.asyncio
    async def test_collect_up_metric(self, http_session: ClientSession):
        """Проверка сбора метрики 'up'."""
        async with http_session.get(
            f"{self.PROMETHEUS_URL}/api/v1/query",
            params={"query": "up"},
        ) as response:
            data = await response.json()
            assert data["status"] == "success"
            result = data["data"]["result"]
            assert len(result) > 0


class TestKafkaIntegration(KafkaIntegrationTest):
    """Тесты интеграции с Kafka."""

    @pytest.mark.asyncio
    async def test_kafka_produce_consume(self, kafka_producer, kafka_consumer):
        """Проверка отправки и получения сообщений."""
        topic = "test-topic"
        message = b"test message"

        # Отправить сообщение
        await kafka_producer.send_and_wait(topic, value=message)

        # Получить сообщение
        msg = await kafka_consumer.getone()
        assert msg.value == message

    @pytest.mark.asyncio
    async def test_kafka_json_message(self, kafka_producer, kafka_consumer):
        """Проверка отправки JSON сообщений."""
        topic = "test-json-topic"
        data = {"name": "test_metric", "value": 123.45, "timestamp": int(time.time() * 1000)}

        # Отправить JSON
        await kafka_producer.send_and_wait(topic, value=json.dumps(data).encode())

        # Получить и распарсить
        msg = await kafka_consumer.getone()
        received = json.loads(msg.value.decode())
        assert received["name"] == data["name"]
        assert received["value"] == data["value"]


class TestExporterEndToEnd(KafkaIntegrationTest):
    """Сквозные тесты экспортера."""

    @pytest.mark.asyncio
    async def test_metrics_in_kafka(self, kafka_consumer):
        """Проверка наличия метрик в Kafka после работы экспортера."""
        topic = "prometheus-metrics"

        # Ждем сообщения с таймаутом
        messages = []
        async for msg in kafka_consumer:
            messages.append(msg)
            if len(messages) >= 5:
                break

        # Проверяем формат сообщений
        for msg in messages:
            data = json.loads(msg.value.decode())
            assert "name" in data
            assert "value" in data
            assert "timestamp" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
