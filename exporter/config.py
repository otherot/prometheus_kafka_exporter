"""Модуль загрузки и валидации конфигурации."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass
class SSLConfig:
    """Настройки SSL."""
    enabled: bool = False
    ca_file: str = ""
    cert_file: str = ""
    key_file: str = ""
    verify: bool = True
    password: str = ""


@dataclass
class AuthConfig:
    """Настройки аутентификации."""
    enabled: bool = False
    username: str = ""
    password: str = ""
    token: str = ""


@dataclass
class PrometheusConfig:
    """Настройки подключения к Prometheus."""
    url: str = "http://prometheus:9090"
    metrics: list[str] = field(default_factory=lambda: ["up"])
    ssl: SSLConfig = field(default_factory=SSLConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)


@dataclass
class SASLConfig:
    """Настройки SASL аутентификации."""
    mechanism: str = "PLAIN"
    username: str = ""
    password: str = ""


@dataclass
class KafkaSecurityConfig:
    """Настройки безопасности Kafka."""
    protocol: str = "PLAINTEXT"
    ssl: SSLConfig = field(default_factory=SSLConfig)
    sasl: SASLConfig = field(default_factory=SASLConfig)


@dataclass
class KafkaProducerConfig:
    """Настройки Kafka продюсера."""
    batch_size: int = 16384
    linger_ms: int = 10
    compression_type: str = "snappy"
    acks: str = "all"
    retries: int = 3
    retry_backoff_ms: int = 100


@dataclass
class KafkaConfig:
    """Настройки Kafka."""
    brokers: list[str] = field(default_factory=lambda: ["kafka:9092"])
    topic: str = "prometheus-metrics"
    security: KafkaSecurityConfig = field(default_factory=KafkaSecurityConfig)
    producer: KafkaProducerConfig = field(default_factory=KafkaProducerConfig)


@dataclass
class FormatConfig:
    """Настройки формата JSON."""
    json_template: str = field(
        default_factory=lambda: '{"name":"{name}","value":{value},"timestamp":{timestamp},"labels":{labels},"type":"{type}"}'
    )
    timestamp_format: str = "unix_ms"


@dataclass
class LoggingStdoutConfig:
    """Настройки логирования в stdout."""
    enabled: bool = True
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class LoggingKafkaConfig:
    """Настройки логирования в Kafka."""
    enabled: bool = False
    topic: str = "prometheus-exporter-logs"
    format: str = ""


@dataclass
class LoggingConfig:
    """Настройки логирования."""
    level: str = "INFO"
    stdout: LoggingStdoutConfig = field(default_factory=LoggingStdoutConfig)
    kafka: LoggingKafkaConfig = field(default_factory=LoggingKafkaConfig)


@dataclass
class ExporterMetricsConfig:
    """Настройки метрик экспортера."""
    enabled: bool = True
    port: int = 8080
    path: str = "/metrics"


@dataclass
class PerformanceConfig:
    """Настройки производительности."""
    scrape_workers: int = 4
    send_buffer_size: int = 1000
    scrape_timeout: int = 10
    send_timeout: int = 5


@dataclass
class Config:
    """Основная конфигурация приложения."""
    scrape_interval: int = 30
    prometheus: PrometheusConfig = field(default_factory=PrometheusConfig)
    kafka: KafkaConfig = field(default_factory=KafkaConfig)
    format: FormatConfig = field(default_factory=FormatConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    exporter_metrics: ExporterMetricsConfig = field(default_factory=ExporterMetricsConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)


def load_config(config_path: str | Path) -> Config:
    """Загрузить конфигурацию из YAML файла."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return _parse_config(data)


def _parse_config(data: dict[str, Any]) -> Config:
    """Распарсить словарь в объект Config."""
    config = Config()

    config.scrape_interval = data.get("scrape_interval", config.scrape_interval)

    # Prometheus
    if "prometheus" in data:
        p = data["prometheus"]
        config.prometheus = PrometheusConfig(
            url=p.get("url", config.prometheus.url),
            metrics=p.get("metrics", config.prometheus.metrics),
            ssl=_parse_ssl(p.get("ssl", {})),
            auth=_parse_auth(p.get("auth", {})),
        )

    # Kafka
    if "kafka" in data:
        k = data["kafka"]
        config.kafka = KafkaConfig(
            brokers=k.get("brokers", config.kafka.brokers),
            topic=k.get("topic", config.kafka.topic),
            security=_parse_kafka_security(k.get("security", {})),
            producer=_parse_kafka_producer(k.get("producer", {})),
        )

    # Format
    if "format" in data:
        f = data["format"]
        config.format = FormatConfig(
            json_template=f.get("json_template", config.format.json_template),
            timestamp_format=f.get("timestamp_format", config.format.timestamp_format),
        )

    # Logging
    if "logging" in data:
        log = data["logging"]
        config.logging = LoggingConfig(
            level=log.get("level", config.logging.level),
            stdout=_parse_logging_stdout(log.get("stdout", {})),
            kafka=_parse_logging_kafka(log.get("kafka", {})),
        )

    # Exporter metrics
    if "exporter_metrics" in data:
        em = data["exporter_metrics"]
        config.exporter_metrics = ExporterMetricsConfig(
            enabled=em.get("enabled", config.exporter_metrics.enabled),
            port=em.get("port", config.exporter_metrics.port),
            path=em.get("path", config.exporter_metrics.path),
        )

    # Performance
    if "performance" in data:
        perf = data["performance"]
        config.performance = PerformanceConfig(
            scrape_workers=perf.get("scrape_workers", config.performance.scrape_workers),
            send_buffer_size=perf.get("send_buffer_size", config.performance.send_buffer_size),
            scrape_timeout=perf.get("scrape_timeout", config.performance.scrape_timeout),
            send_timeout=perf.get("send_timeout", config.performance.send_timeout),
        )

    return config


def _parse_ssl(data: dict[str, Any]) -> SSLConfig:
    return SSLConfig(
        enabled=data.get("enabled", False),
        ca_file=data.get("ca_file", ""),
        cert_file=data.get("cert_file", ""),
        key_file=data.get("key_file", ""),
        verify=data.get("verify", True),
        password=data.get("password", ""),
    )


def _parse_auth(data: dict[str, Any]) -> AuthConfig:
    return AuthConfig(
        enabled=data.get("enabled", False),
        username=data.get("username", ""),
        password=data.get("password", ""),
        token=data.get("token", ""),
    )


def _parse_kafka_security(data: dict[str, Any]) -> KafkaSecurityConfig:
    return KafkaSecurityConfig(
        protocol=data.get("protocol", "PLAINTEXT"),
        ssl=_parse_ssl(data.get("ssl", {})),
        sasl=SASLConfig(
            mechanism=data.get("sasl", {}).get("mechanism", "PLAIN"),
            username=data.get("sasl", {}).get("username", ""),
            password=data.get("sasl", {}).get("password", ""),
        ),
    )


def _parse_kafka_producer(data: dict[str, Any]) -> KafkaProducerConfig:
    return KafkaProducerConfig(
        batch_size=data.get("batch_size", 16384),
        linger_ms=data.get("linger_ms", 10),
        compression_type=data.get("compression_type", "snappy"),
        acks=data.get("acks", "all"),
        retries=data.get("retries", 3),
        retry_backoff_ms=data.get("retry_backoff_ms", 100),
    )


def _parse_logging_stdout(data: dict[str, Any]) -> LoggingStdoutConfig:
    return LoggingStdoutConfig(
        enabled=data.get("enabled", True),
        format=data.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
    )


def _parse_logging_kafka(data: dict[str, Any]) -> LoggingKafkaConfig:
    return LoggingKafkaConfig(
        enabled=data.get("enabled", False),
        topic=data.get("topic", "prometheus-exporter-logs"),
        format=data.get("format", ""),
    )
