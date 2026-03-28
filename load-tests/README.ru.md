# Нагрузочное тестирование Prometheus Kafka Exporter

Набор тестов для нагрузочного тестирования экспортера метрик Prometheus в Kafka.

## 📁 Структура

```
load-tests/
├── k6/
│   └── http_load_test.js       # k6 сценарий для HTTP нагрузки
├── locust/
│   └── locustfile.py           # Locust сценарий (опционально)
├── config/
│   ├── prometheus-load.yaml    # Конфигурация Prometheus для теста
│   └── config.load.yaml        # Конфигурация экспортера для теста
├── e2e_load_test.py            # End-to-End тест на asyncio
├── README.md                   # Английская версия
└── README.ru.md                # Этот файл (русский)
```

## 🚀 Быстрый старт

### 1. Запуск тестового окружения

```bash
# Запустить все сервисы (Zookeeper, Kafka, Prometheus, Exporter, k6, Grafana)
docker compose -f docker-compose.load.yaml up -d

# Проверить статус
docker compose -f docker-compose.load.yaml ps

# Просмотр логов экспортера
docker compose -f docker-compose.load.yaml logs -f exporter
```

### 2. Запуск k6 теста

```bash
# Базовый тест (5 минут, до 100 VUs)
docker compose -f docker-compose.load.yaml run k6

# Highload тест (до 1000 VUs)
docker compose -f docker-compose.load.yaml run --env TEST_TYPE=highload k6

# Стресс тест (до 500 VUs, 5 минут на пике)
docker compose -f docker-compose.load.yaml run --env TEST_TYPE=stress k6
```

### 3. Запуск End-to-End теста

```bash
# Установить зависимости
pip install aiohttp aiokafka

# Запустить e2e тест (60 секунд, 100 RPS)
python load-tests/e2e_load_test.py --duration 60 --rps 100

# Высокая нагрузка (300 секунд, 500 RPS)
python load-tests/e2e_load_test.py --duration 300 --rps 500 --consumers 5
```

### 4. Остановка

```bash
docker compose -f docker-compose.load.yaml down
```

## 📊 Сценарии тестирования

### k6 HTTP Load Test

Тестирует HTTP endpoint экспортера (`:8080/metrics`).

| Сценарий | Длительность | Пик VUs | Описание |
|----------|--------------|---------|----------|
| `default` | 4 мин | 100 | Базовая нагрузка |
| `highload` | 7 мин | 1000 | Высокая нагрузка |
| `stress` | 8.5 мин | 500 | Стресс тест (длительный пик) |

**Метрики:**
- HTTP request duration (p50, p95, p99)
- Error rate
- Scrape latency
- Metrics count per response

**Пороговые значения (thresholds):**
- `http_req_duration p95 < 500ms`
- `http_req_duration p99 < 1000ms`
- `error rate < 1%`

### End-to-End Test

Тестирует полный цикл: **Prometheus → Exporter → Kafka → Валидация**

**Параметры:**
- `--duration` — длительность теста (секунды)
- `--rps` — целевой RPS
- `--consumers` — количество Kafka консьюмеров для валидации

**Метрики:**
- Scrape latency (p50, p95, p99)
- Kafka send latency
- Total messages sent
- Validation errors

## 📈 Визуализация

### Grafana

Grafana доступна по адресу: http://localhost:3000

- Логин: `admin`
- Пароль: `admin`

**DataSource:** Prometheus уже настроен (http://prometheus:9090)

### Prometheus

Prometheus UI: http://localhost:9090

**Полезные запросы:**
```promql
# Количество метрик в экспортере
rate(python_scrape_duration_seconds_count[1m])

# Latency экспортера
histogram_quantile(0.95, rate(python_scrape_duration_seconds_bucket[1m]))

# Kafka throughput
rate(kafka_produce_duration_seconds_count[1m])
```

## 🔧 Настройка

### Изменение нагрузки k6

Отредактируйте `load-tests/k6/http_load_test.js`:

```javascript
const STAGES = {
  custom: [
    { duration: '1m', target: 200 },  // 200 VUs
    { duration: '5m', target: 200 },  // Держим 5 минут
    { duration: '1m', target: 0 },    // Снижение
  ],
};

export const options = {
  stages: STAGES.custom,
  // ...
};
```

### Изменение конфигурации экспортера

Отредактируйте `load-tests/config/config.load.yaml`:

```yaml
performance:
  scrape_workers: 8        # Количество воркеров сбора
  send_buffer_size: 1000   # Размер буфера отправки
  scrape_timeout: 3        # Таймаут сбора (сек)
  send_timeout: 10         # Таймаут отправки (сек)
```

### Добавление метрик в Prometheus

Отредактируйте `load-tests/config/prometheus-load.yaml` для добавления новых target'ов.

## 📋 Чеклист перед тестированием

- [ ] Docker запущен и доступен
- [ ] Достаточно ресурсов (минимум 4 CPU, 8GB RAM)
- [ ] Порты свободны: 9090, 9092, 8080, 3000, 2181
- [ ] k6 установлен (для локального запуска): `brew install k6` или https://k6.io/docs/getting-started/installation/

## 🐛 Troubleshooting

### k6 контейнер не запускается

```bash
# Проверить логи
docker compose -f docker-compose.load.yaml logs k6

# Запустить без docker compose
k6 run load-tests/k6/http_load_test.js
```

### Exporter не собирает метрики

```bash
# Проверить доступность Prometheus
curl http://localhost:9090/metrics

# Проверить логи экспортера
docker compose -f docker-compose.load.yaml logs -f exporter
```

### Kafka ошибки

```bash
# Проверить статус Kafka
docker compose -f docker-compose.load.yaml logs kafka

# Пересоздать топик
docker compose -f docker-compose.load.yaml exec kafka kafka-topics --bootstrap-server localhost:9092 --delete --topic prometheus-metrics
```

## 📊 Интерпретация результатов

### Хорошие результаты

| Метрика | Значение |
|---------|----------|
| Scrape p95 | < 200ms |
| Scrape p99 | < 500ms |
| Kafka p95 | < 100ms |
| Error rate | < 0.1% |

### Проблемы и решения

| Проблема | Возможная причина | Решение |
|----------|-------------------|---------|
| Высокий scrape latency | Мало воркеров | Увеличить `scrape_workers` |
| Kafka timeout | Маленький batch | Увеличить `batch_size`, `linger_ms` |
| Ошибки отправки | Kafka недоступен | Проверить статус Kafka |
| Memory leak | Долгий тест | Увеличить лимиты памяти в Docker |

## 📝 Отчётность

Результаты тестов сохраняются в:
- `load-tests/results/k6_report_*.json` — отчёт k6
- Консольный вывод e2e теста — скопировать вручную

## 🔗 Дополнительные ресурсы

- [k6 Documentation](https://k6.io/docs/)
- [Locust Documentation](https://docs.locust.io/)
- [Prometheus Performance](https://prometheus.io/docs/operating/performance/)
- [Kafka Performance Tuning](https://kafka.apache.org/documentation/#performance)

---

**🇬🇧 English version:** [README.md](README.md)
