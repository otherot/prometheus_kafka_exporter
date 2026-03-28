"""Асинхронный сбор метрик с Prometheus endpoint."""

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientSession, ClientTimeout, TCPConnector

from .config import Config, PrometheusConfig
from . import metrics as exporter_metrics


@dataclass
class Metric:
    """Представление метрики Prometheus."""

    name: str
    value: float
    timestamp: int  # milliseconds
    labels: dict[str, str]
    help_text: str = ""
    metric_type: str = ""


class PrometheusCollector:
    """Асинхронный коллектор метрик Prometheus."""

    def __init__(self, config: PrometheusConfig, performance_config: dict[str, Any]):
        self.config = config
        self.timeout = ClientTimeout(total=performance_config.get("scrape_timeout", 10))
        self._session: Optional[ClientSession] = None
        self._compiled_metrics: list[re.Pattern] = []

    async def start(self) -> None:
        """Инициализировать HTTP сессию."""
        # SSL настройки
        ssl_context = None
        if self.config.ssl.enabled:
            import ssl

            ssl_context = ssl.create_default_context(cafile=self.config.ssl.ca_file)
            if self.config.ssl.cert_file and self.config.ssl.key_file:
                ssl_context.load_cert_chain(
                    certfile=self.config.ssl.cert_file,
                    keyfile=self.config.ssl.key_file,
                    password=self.config.ssl.password or None,
                )
            ssl_context.check_hostname = self.config.ssl.verify
            ssl_context.verify_mode = ssl.CERT_REQUIRED if self.config.ssl.verify else ssl.CERT_NONE

        connector = TCPConnector(
            limit=100,
            limit_per_host=50,
            ttl_dns_cache=300,
            use_dns_cache=True,
            ssl=ssl_context if self.config.ssl.enabled else None,
        )

        # Заголовки
        headers = {}
        if self.config.auth.enabled:
            if self.config.auth.token:
                headers["Authorization"] = f"Bearer {self.config.auth.token}"
            elif self.config.auth.username and self.config.auth.password:
                import base64

                credentials = f"{self.config.auth.username}:{self.config.auth.password}"
                encoded = base64.b64encode(credentials.encode()).decode()
                headers["Authorization"] = f"Basic {encoded}"

        self._session = ClientSession(
            timeout=self.timeout,
            connector=connector,
            headers=headers,
        )

        # Компилируем паттерны метрик
        for pattern in self.config.metrics:
            self._compiled_metrics.append(re.compile(f"^{pattern}$"))

    async def stop(self) -> None:
        """Закрыть HTTP сессию."""
        if self._session:
            await self._session.close()
            self._session = None

    async def collect(self) -> list[Metric]:
        """Собрать все метрики с Prometheus endpoint."""
        if not self._session:
            raise RuntimeError("Collector not started. Call start() first.")

        start_time = time.time()
        url = urljoin(self.config.url, "/api/v1/query?query={query}")
        metrics = []

        try:
            # Собираем метрики конкурентно
            tasks = []
            for pattern in self.config.metrics:
                tasks.append(self._collect_by_pattern(pattern, url))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    metrics.extend(result)
                elif isinstance(result, Exception):
                    # Логируем ошибку, но продолжаем
                    exporter_metrics.errors_total.labels(type="scrape").inc()

            # Обновляем метрики
            duration = time.time() - start_time
            exporter_metrics.scrape_duration.observe(duration)
            exporter_metrics.scrape_count.labels(status="success").inc()
            exporter_metrics.scrape_metrics_count.set(len(metrics))
            exporter_metrics.last_scrape_timestamp.set(time.time())

        except Exception as e:
            exporter_metrics.scrape_count.labels(status="error").inc()
            exporter_metrics.errors_total.labels(type="scrape").inc()
            raise

        return metrics

    async def _collect_by_pattern(self, pattern: str, query_url: str) -> list[Metric]:
        """Собрать метрики по паттерну."""
        metrics = []

        # Запрос к Prometheus API
        async with self._session.get(query_url.format(query=pattern)) as response:
            if response.status != 200:
                return metrics

            data = await response.json()
            if data.get("status") != "success":
                return metrics

            result = data.get("data", {}).get("result", [])
            for item in result:
                metric = self._parse_metric(item, pattern)
                if metric:
                    metrics.append(metric)

        return metrics

    def _parse_metric(self, item: dict[str, Any], pattern: str) -> Optional[Metric]:
        """Распарсить метрику из ответа Prometheus."""
        try:
            metric_name = item.get("metric", {}).get("__name__", pattern)
            labels = item.get("metric", {})
            labels.pop("__name__", None)

            value_data = item.get("value", [])
            if len(value_data) < 2:
                return None

            timestamp = int(float(value_data[0]) * 1000)  # seconds -> ms
            value = float(value_data[1])

            return Metric(
                name=metric_name,
                value=value,
                timestamp=timestamp,
                labels=labels,
            )
        except (KeyError, ValueError, TypeError):
            return None

    async def collect_all(self) -> list[Metric]:
        """Собрать все метрики одним запросом (более эффективно)."""
        if not self._session:
            raise RuntimeError("Collector not started. Call start() first.")

        url = urljoin(self.config.url, "/api/v1/query")
        metrics = []

        # Запрос всех метрик
        async with self._session.get(url, params={"query": "up"}) as response:
            if response.status != 200:
                return metrics

            data = await response.json()
            if data.get("status") != "success":
                return metrics

        # Для каждого паттерна делаем отдельный запрос
        tasks = []
        for pattern in self.config.metrics:
            tasks.append(self._fetch_metric_pattern(url, pattern))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, list):
                metrics.extend(result)

        return metrics

    async def _fetch_metric_pattern(self, base_url: str, pattern: str) -> list[Metric]:
        """Получить метрики по паттерну."""
        metrics = []

        async with self._session.get(base_url, params={"query": pattern}) as response:
            if response.status != 200:
                return metrics

            data = await response.json()
            if data.get("status") != "success":
                return metrics

            result = data.get("data", {}).get("result", [])
            for item in result:
                metric = self._parse_metric(item, pattern)
                if metric:
                    metrics.append(metric)

        return metrics
