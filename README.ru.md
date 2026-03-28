# Prometheus Kafka Exporter

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/otherot/prometheus_kafka_exporter/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Асинхронный экспортёр метрик Prometheus в Kafka с разработанный с прицелом на highload.

**🇬🇧 English version:** [README.md](README.md)

---

## 🚀 Возможности

- **Асинхронная архитектура** — aiohttp + aiokafka для высокой производительности
- **Настраиваемый формат JSON** — гибкий шаблон для форматирования метрик
- **SSL/TLS поддержка** — безопасное подключение к Prometheus и Kafka
- **SASL аутентификация** — PLAIN, SCRAM-SHA-256, SCRAM-SHA-512
- **Конфигурация через ConfigMap** — все настройки в Kubernetes ConfigMap
- **Логирование в stdout и Kafka** — настраиваемый уровень и формат
- **Retry логика** — автоматические повторные попытки при ошибках
- **Kubernetes ready** — Deployment, HPA, PDB, ServiceAccount
- **Istio совместимость** — готово для service mesh
- **Метрики экспортера** — встроенный Prometheus endpoint

## 📁 Структура проекта

```
prometheus_kafka_exporter/
├── exporter/
│   ├── __init__.py
│   ├── main.py          # Точка входа
│   ├── config.py        # Конфигурация
│   ├── collector.py     # Сбор метрик с Prometheus
│   ├── formatter.py     # Форматирование в JSON
│   ├── sender.py        # Отправка в Kafka
│   └── logger.py        # Логирование
├── tests/
│   ├── __init__.py
│   ├── test_integration.py
│   └── prometheus.yml
├── config/
│   ├── config.example.yaml
│   └── config.test.yaml
├── k8s/
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── serviceaccount.yaml
│   ├── hpa.yaml
│   └── pdb.yaml
├── load-tests/          # Нагрузочное тестирование
│   ├── k6/
│   ├── config/
│   ├── e2e_load_test.py
│   └── README.md
├── Dockerfile
├── docker-compose.yml
├── docker-compose.load.yaml
├── requirements.txt
└── README.md
```

## ⚡ Быстрый старт

### Локальный запуск с Docker Compose

```bash
# Запустить Kafka, Zookeeper, Prometheus и экспортер
docker-compose up -d

# Проверить логи
docker-compose logs -f exporter

# Остановить
docker-compose down
```

### Деплой в Kubernetes

```bash
# Создать namespace и ресурсы
kubectl apply -f k8s/

# Проверить статус
kubectl get pods -n prometheus-kafka-exporter

# Посмотреть логи
kubectl logs -f deployment/prometheus-kafka-exporter -n prometheus-kafka-exporter
```

## ⚙️ Конфигурация

Все настройки находятся в ConfigMap (`k8s/configmap.yaml`).

### Основные параметры

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `scrape_interval` | Интервал сбора метрик (сек) | 30 |
| `prometheus.url` | URL Prometheus | `http://prometheus:9090` |
| `prometheus.metrics` | Список метрик для сбора | `["up"]` |
| `kafka.brokers` | Список брокеров Kafka | `["kafka:9092"]` |
| `kafka.topic` | Топик для метрик | `prometheus-metrics` |
| `format.json_template` | Шаблон JSON | См. config.example.yaml |
| `logging.level` | Уровень логирования | `INFO` |
| `performance.scrape_workers` | Количество воркеров | 4 |

### SSL для Prometheus

```yaml
prometheus:
  ssl:
    enabled: true
    ca_file: "/etc/ssl/certs/ca-certificates.crt"
    cert_file: "/etc/ssl/certs/client.crt"
    key_file: "/etc/ssl/certs/client.key"
    verify: true
```

### SASL/SSL для Kafka

```yaml
kafka:
  security:
    protocol: "SASL_SSL"
    ssl:
      ca_file: "/etc/ssl/certs/ca-certificates.crt"
      cert_file: "/etc/ssl/certs/client.crt"
      key_file: "/etc/ssl/certs/client.key"
    sasl:
      mechanism: "SCRAM-SHA-512"
      username: "user"
      password: "password"
```

### Формат JSON

Доступные переменные: `{name}`, `{value}`, `{timestamp}`, `{labels}`, `{help}`, `{type}`

```yaml
format:
  json_template: |
    {"metric":"{name}","value":{value},"ts":{timestamp},"labels":{labels}}
  timestamp_format: "unix_ms"  # unix_ms, unix_s, iso
```

## 📊 Производительность

### Ресурсы Kubernetes

По умолчанию настроено:
- **Requests:** 500m CPU / 1Gi memory
- **Limits:** 2 CPU / 4Gi memory
- **HPA:** 2-10 реплик, 70% CPU / 80% memory

Для highload (10k+ RPS) рекомендуется:
- Увеличить `performance.scrape_workers` до 8-16
- Увеличить лимиты до 4 CPU / 8Gi memory
- Включить сжатие `compression_type: "zstd"`

### Tuning

```yaml
performance:
  scrape_workers: 8
  send_buffer_size: 2000
  scrape_timeout: 15
  send_timeout: 10

kafka:
  producer:
    batch_size: 32768
    linger_ms: 20
    compression_type: "zstd"
```

## 📈 Мониторинг

Метрики экспортера доступны на порту 8080:

```bash
kubectl port-forward deployment/prometheus-kafka-exporter 8080:8080 -n prometheus-kafka-exporter
curl http://localhost:8080/metrics
```

## 🧪 Тестирование

### Интеграционные тесты

```bash
# Запустить тестовое окружение
docker-compose up -d

# Запустить тесты
pip install -r requirements.txt pytest pytest-asyncio
pytest tests/ -v --asyncio-mode=auto

# Остановить
docker-compose down
```

### Нагрузочное тестирование

См. [load-tests/README.ru.md](load-tests/README.ru.md) для подробной документации по нагрузочному тестированию.

```bash
# Запустить окружение для нагрузочного теста
docker compose -f docker-compose.load.yaml up -d

# Запустить k6 HTTP нагрузочный тест
docker compose -f docker-compose.load.yaml run k6

# Запустить End-to-End тест
python load-tests/e2e_load_test.py --duration 60 --rps 100

# Остановить
docker compose -f docker-compose.load.yaml down
```

## 📋 Требования

- Python 3.10+
- Docker & Docker Compose
- Kubernetes 1.25+ (для деплоя)
- Istio (опционально)

## 📄 Лицензия

MIT

---

**Документация по нагрузочному тестированию:** [load-tests/README.ru.md](load-tests/README.ru.md)

**English Version:** [README.md](README.md)
