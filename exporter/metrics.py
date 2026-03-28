"""Метрики Prometheus для мониторинга экспортера."""

from prometheus_client import Counter, Gauge, Histogram, Summary

# Метрики сбора метрик
scrape_duration = Histogram(
    "exporter_scrape_duration_seconds",
    "Duration of Prometheus metrics scraping",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

scrape_count = Counter(
    "exporter_scrape_count_total",
    "Total number of Prometheus scrapes",
    labelnames=["status"],  # success, error
)

scrape_metrics_count = Gauge(
    "exporter_scrape_metrics_count",
    "Number of metrics collected in last scrape",
)

# Метрики отправки в Kafka
kafka_send_duration = Histogram(
    "exporter_kafka_send_duration_seconds",
    "Duration of Kafka send operations",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

kafka_send_count = Counter(
    "exporter_kafka_send_count_total",
    "Total number of Kafka send operations",
    labelnames=["status"],  # success, error
)

kafka_messages_count = Counter(
    "exporter_kafka_messages_count_total",
    "Total number of messages sent to Kafka",
)

kafka_batch_size = Histogram(
    "exporter_kafka_batch_size",
    "Size of Kafka message batches",
    buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000),
)

# Метрики ошибок
errors_total = Counter(
    "exporter_errors_total",
    "Total number of exporter errors",
    labelnames=["type"],  # scrape, format, send, kafka
)

# Метрики состояния
up = Gauge(
    "exporter_up",
    "Exporter health status (1 = up, 0 = down)",
)

last_scrape_timestamp = Gauge(
    "exporter_last_scrape_timestamp_seconds",
    "Timestamp of the last successful scrape",
)

last_send_timestamp = Gauge(
    "exporter_last_send_timestamp_seconds",
    "Timestamp of the last successful Kafka send",
)

# Метрики производительности
scrape_interval = Gauge(
    "exporter_scrape_interval_seconds",
    "Configured scrape interval",
)

active_workers = Gauge(
    "exporter_active_workers",
    "Number of active scrape workers",
)
