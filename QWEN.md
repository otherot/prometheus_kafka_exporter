# prometheus_kafka_exporter

## Project Overview

Асинхронный экспортёр метрик Prometheus в Kafka с поддержкой highload (10k+ RPS).

**Версия:** 0.1.0 (в разработке)

**Архитектура:**
- **aiohttp** — асинхронный HTTP-клиент для сбора метрик с Prometheus
- **aiokafka** — асинхронный Kafka-продюсер для отправки метрик
- **asyncio** — конкурентный сбор и отправка метрик

**Структура проекта:**
```
prometheus_kafka_exporter/
├── exporter/
│   ├── __init__.py
│   ├── main.py          # Точка входа, основной цикл
│   ├── config.py        # Загрузка и валидация конфигурации
│   ├── collector.py     # Асинхронный сбор метрик с Prometheus
│   ├── formatter.py     # Форматирование метрик в JSON
│   ├── sender.py        # Асинхронная отправка в Kafka с retry
│   └── logger.py        # Логирование в stdout и Kafka
├── tests/
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
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

**Технологии:**
- Python 3.12
- aiohttp, aiokafka, pyyaml, prometheus-client
- Docker, Kubernetes, Istio-ready

## Building and Running

**Локальный запуск:**
```bash
pip install -r requirements.txt
python -m exporter.main config/config.example.yaml
```

**Docker Compose (тесты):**
```bash
docker compose up -d
docker compose logs -f exporter
docker compose down
```

**Kubernetes:**
```bash
kubectl apply -f k8s/
kubectl get pods -n prometheus-kafka-exporter
kubectl logs -f deployment/prometheus-kafka-exporter -n prometheus-kafka-exporter
```

**Сборка Docker:**
```bash
docker build -t prometheus-kafka-exporter:0.1.0 .
```

## Configuration

Все настройки через ConfigMap (никаких environment variables):

- `scrape_interval` — интервал сбора метрик
- `prometheus.url` — URL Prometheus
- `prometheus.metrics` — список метрик для сбора
- `kafka.brokers` — брокеры Kafka
- `kafka.topic` — топик для метрик
- `kafka.security.protocol` — PLAINTEXT, SSL, SASL_PLAINTEXT, SASL_SSL
- `format.json_template` — шаблон JSON
- `logging.level` — DEBUG, INFO, WARNING, ERROR, CRITICAL
- `performance.scrape_workers` — количество воркеров

## Development

**Структура кода:**
- Асинхронная архитектура на asyncio
- Connection pooling для HTTP
- Batching для Kafka
- Retry логика с backoff

**Тестирование:**
- Интеграционные тесты с Docker (Kafka + Zookeeper + Prometheus)
- pytest + pytest-asyncio
- **Требуется Docker для запуска тестов**

**Ресурсы для highload:**
- Requests: 500m CPU / 1Gi memory
- Limits: 2 CPU / 4Gi memory
- HPA: 2-10 реплик

## Current Status (v0.1.0)

**Выполнено:**
- ✅ Базовая структура проекта
- ✅ Конфигурация через YAML (все настройки)
- ✅ Асинхронный сбор метрик (aiohttp + SSL)
- ✅ Асинхронная отправка в Kafka (aiokafka + SASL/SSL)
- ✅ Настраиваемый JSON-формат
- ✅ Логирование в stdout и Kafka
- ✅ Dockerfile (multi-stage)
- ✅ docker-compose.yml для тестов
- ✅ Kubernetes манифесты (Deployment, ConfigMap, Service, HPA, PDB)
- ✅ Интеграционные тесты (pytest)
- ✅ Документация (README.md)

**Следующие шаги:**
- [ ] Запустить интеграционные тесты (требуется Docker)
- [ ] Исправить ошибки если есть
- [ ] Создать PR и замержить в main
- [ ] Создать тег v0.1.0
- [ ] Опубликовать Docker образ

## Git

**Ветка:** 0.1.0 (запушена в origin)

**Коммиты:**
```
ed4f201 chore: добавить __init__.py для tests и .qwen/ конфигурацию
efb459e docs: добавить документацию
293fb8c feat: добавить Kubernetes манифесты (часть 2)
79951af feat: добавить Kubernetes манифесты (часть 1)
93daff8 test: добавить интеграционные тесты
e0af643 feat: добавить Docker и тестовое окружение
69597a5 feat: реализовать точку входа и основной цикл
1d0d2f2 feat: реализовать отправку в Kafka и логирование
3ea544c feat: реализовать сбор и форматирование метрик
46772bc feat: реализовать систему конфигурации
f0a3f90 feat: добавить базовую структуру проекта и зависимости
```

**PR:** https://github.com/otherot/prometheus_kafka_exporter/pull/new/0.1.0
