"""Integration tests for Prometheus Kafka Exporter."""

import asyncio
import json
import time
from typing import Any

import pytest
from aiohttp import ClientSession
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer


class KafkaIntegrationTest:
    """Base class for Kafka integration tests."""

    KAFKA_BOOTSTRAP = "localhost:9092"
    PROMETHEUS_URL = "http://localhost:9090"
    EXPORTER_METRICS = "http://localhost:8080"

    @pytest.fixture
    def topic(self) -> str:
        """Default topic for tests."""
        return "test-topic"

    @pytest.fixture
    async def kafka_producer(self):
        """Create Kafka producer for tests."""
        producer = AIOKafkaProducer(bootstrap_servers=self.KAFKA_BOOTSTRAP)
        await producer.start()
        try:
            yield producer
        finally:
            await producer.stop()

    @pytest.fixture
    async def kafka_consumer(self, topic: str):
        """Create Kafka consumer for tests."""
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
        """Create HTTP session for tests."""
        async with ClientSession() as session:
            yield session


class TestPrometheusAvailability(KafkaIntegrationTest):
    """Prometheus availability tests."""

    @pytest.mark.asyncio
    async def test_prometheus_health(self, http_session: ClientSession):
        """Check Prometheus health."""
        async with http_session.get(f"{self.PROMETHEUS_URL}/-/healthy") as response:
            assert response.status == 200

    @pytest.mark.asyncio
    async def test_prometheus_api(self, http_session: ClientSession):
        """Check Prometheus API."""
        async with http_session.get(
            f"{self.PROMETHEUS_URL}/api/v1/query",
            params={"query": "up"},
        ) as response:
            assert response.status == 200
            data = await response.json()
            assert data["status"] == "success"


class TestExporterMetrics(KafkaIntegrationTest):
    """Exporter metrics tests."""

    @pytest.mark.asyncio
    async def test_exporter_metrics_endpoint(self, http_session: ClientSession):
        """Check exporter metrics endpoint."""
        async with http_session.get(f"{self.EXPORTER_METRICS}/metrics") as response:
            assert response.status == 200
            content = await response.text()
            # Standard Python metrics
            assert "python_" in content or "process_" in content
            # Custom exporter metrics
            assert "exporter_up" in content
            assert "exporter_scrape_duration_seconds" in content
            assert "exporter_scrape_count_total" in content
            assert "exporter_kafka_send_duration_seconds" in content
            assert "exporter_kafka_messages_count_total" in content

    @pytest.mark.asyncio
    async def test_exporter_up_metric(self, http_session: ClientSession):
        """Check exporter_up metric."""
        async with http_session.get(f"{self.EXPORTER_METRICS}/metrics") as response:
            assert response.status == 200
            content = await response.text()
            # Exporter should be in up status
            assert "exporter_up 1.0" in content

    @pytest.mark.asyncio
    async def test_exporter_scrape_metrics(self, http_session: ClientSession):
        """Check scrape metrics."""
        async with http_session.get(f"{self.EXPORTER_METRICS}/metrics") as response:
            assert response.status == 200
            content = await response.text()
            # Scrape metrics should be present
            assert "exporter_scrape_duration_seconds" in content
            assert "exporter_scrape_count_total" in content
            assert "exporter_scrape_metrics_count" in content
            assert "exporter_last_scrape_timestamp_seconds" in content

    @pytest.mark.asyncio
    async def test_exporter_kafka_metrics(self, http_session: ClientSession):
        """Check Kafka metrics."""
        async with http_session.get(f"{self.EXPORTER_METRICS}/metrics") as response:
            assert response.status == 200
            content = await response.text()
            # Kafka metrics should be present
            assert "exporter_kafka_send_duration_seconds" in content
            assert "exporter_kafka_send_count_total" in content
            assert "exporter_kafka_messages_count_total" in content
            assert "exporter_kafka_batch_size" in content
            assert "exporter_last_send_timestamp_seconds" in content

    @pytest.mark.asyncio
    async def test_exporter_error_metrics(self, http_session: ClientSession):
        """Check error metrics."""
        async with http_session.get(f"{self.EXPORTER_METRICS}/metrics") as response:
            assert response.status == 200
            content = await response.text()
            # Error metric should be present (even if 0)
            assert "exporter_errors_total" in content

    @pytest.mark.asyncio
    async def test_exporter_config_metrics(self, http_session: ClientSession):
        """Check config metrics."""
        async with http_session.get(f"{self.EXPORTER_METRICS}/metrics") as response:
            assert response.status == 200
            content = await response.text()
            # Config metrics
            assert "exporter_scrape_interval_seconds" in content


class TestMetricCollection(KafkaIntegrationTest):
    """Metric collection tests."""

    @pytest.mark.asyncio
    async def test_collect_up_metric(self, http_session: ClientSession):
        """Check collection of 'up' metric."""
        async with http_session.get(
            f"{self.PROMETHEUS_URL}/api/v1/query",
            params={"query": "up"},
        ) as response:
            data = await response.json()
            assert data["status"] == "success"
            result = data["data"]["result"]
            assert len(result) > 0


class TestKafkaIntegration(KafkaIntegrationTest):
    """Kafka integration tests."""

    @pytest.mark.asyncio
    async def test_kafka_produce_consume(self, kafka_producer, kafka_consumer):
        """Check sending and receiving messages."""
        topic = "test-topic"
        message = b"test message"

        # Send message
        await kafka_producer.send_and_wait(topic, value=message)

        # Receive message
        msg = await kafka_consumer.getone()
        assert msg.value == message

    @pytest.mark.asyncio
    async def test_kafka_json_message(self, kafka_producer):
        """Check sending JSON messages."""
        topic = "test-json-topic"
        data = {"name": "test_metric", "value": 123.45, "timestamp": int(time.time() * 1000)}

        # Create consumer for this topic
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=self.KAFKA_BOOTSTRAP,
            auto_offset_reset="earliest",
            consumer_timeout_ms=5000,
        )
        await consumer.start()
        try:
            # Send JSON
            await kafka_producer.send_and_wait(topic, value=json.dumps(data).encode())

            # Receive and parse
            msg = await consumer.getone()
            received = json.loads(msg.value.decode())
            assert received["name"] == data["name"]
            assert received["value"] == data["value"]
        finally:
            await consumer.stop()


class TestExporterEndToEnd(KafkaIntegrationTest):
    """End-to-end exporter tests."""

    @pytest.mark.asyncio
    async def test_metrics_in_kafka(self):
        """Check metrics in Kafka after exporter runs."""
        topic = "prometheus-metrics"

        # Create consumer for this topic
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=self.KAFKA_BOOTSTRAP,
            auto_offset_reset="earliest",
            consumer_timeout_ms=10000,
        )
        await consumer.start()
        try:
            # Wait for messages with timeout
            messages = []
            async for msg in consumer:
                messages.append(msg)
                if len(messages) >= 5:
                    break

            # Check message format
            for msg in messages:
                data = json.loads(msg.value.decode())
                assert "name" in data
                assert "value" in data
                assert "timestamp" in data
        finally:
            await consumer.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
