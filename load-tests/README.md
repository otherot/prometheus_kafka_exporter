# Load Tests for Prometheus Kafka Exporter

Load testing suite for Prometheus metrics exporter to Kafka.

## 📁 Structure

```
load-tests/
├── k6/
│   └── http_load_test.js       # k6 HTTP load test scenario
├── locust/
│   └── locustfile.py           # Locust scenario (optional)
├── config/
│   ├── prometheus-load.yaml    # Prometheus config for load test
│   └── config.load.yaml        # Exporter config for load test
├── e2e_load_test.py            # End-to-End asyncio test
├── README.md                   # This file (English)
└── README.ru.md                # Russian version
```

## 🚀 Quick Start

### 1. Start Test Environment

```bash
# Start all services (Zookeeper, Kafka, Prometheus, Exporter, k6, Grafana)
docker compose -f docker-compose.load.yaml up -d

# Check status
docker compose -f docker-compose.load.yaml ps

# View exporter logs
docker compose -f docker-compose.load.yaml logs -f exporter
```

### 2. Run k6 Test

```bash
# Basic test (5 minutes, up to 100 VUs)
docker compose -f docker-compose.load.yaml run k6

# Highload test (up to 1000 VUs)
docker compose -f docker-compose.load.yaml run --env TEST_TYPE=highload k6

# Stress test (up to 500 VUs, 5 minutes at peak)
docker compose -f docker-compose.load.yaml run --env TEST_TYPE=stress k6
```

### 3. Run End-to-End Test

```bash
# Install dependencies
pip install aiohttp aiokafka

# Run e2e test (60 seconds, 100 RPS)
python load-tests/e2e_load_test.py --duration 60 --rps 100

# High load (300 seconds, 500 RPS)
python load-tests/e2e_load_test.py --duration 300 --rps 500 --consumers 5
```

### 4. Stop

```bash
docker compose -f docker-compose.load.yaml down
```

## 📊 Test Scenarios

### k6 HTTP Load Test

Tests the exporter HTTP endpoint (`:8080/metrics`).

| Scenario | Duration | Peak VUs | Description |
|----------|----------|----------|-------------|
| `default` | 4 min | 100 | Basic load |
| `highload` | 7 min | 1000 | High load |
| `stress` | 8.5 min | 500 | Stress test (long peak) |

**Metrics:**
- HTTP request duration (p50, p95, p99)
- Error rate
- Scrape latency
- Metrics count per response

**Thresholds:**
- `http_req_duration p95 < 500ms`
- `http_req_duration p99 < 1000ms`
- `error rate < 1%`

### End-to-End Test

Tests the full pipeline: **Prometheus → Exporter → Kafka → Validation**

**Parameters:**
- `--duration` — test duration (seconds)
- `--rps` — target RPS
- `--consumers` — number of Kafka consumers for validation

**Metrics:**
- Scrape latency (p50, p95, p99)
- Kafka send latency
- Total messages sent
- Validation errors

## 📈 Visualization

### Grafana

Grafana available at: http://localhost:3000

- Login: `admin`
- Password: `admin`

**DataSource:** Prometheus pre-configured (http://prometheus:9090)

### Prometheus

Prometheus UI: http://localhost:9090

**Useful queries:**
```promql
# Exporter metrics count
rate(python_scrape_duration_seconds_count[1m])

# Exporter latency
histogram_quantile(0.95, rate(python_scrape_duration_seconds_bucket[1m]))

# Kafka throughput
rate(kafka_produce_duration_seconds_count[1m])
```

## 🔧 Configuration

### Change k6 Load

Edit `load-tests/k6/http_load_test.js`:

```javascript
const STAGES = {
  custom: [
    { duration: '1m', target: 200 },  // 200 VUs
    { duration: '5m', target: 200 },  // Hold for 5 minutes
    { duration: '1m', target: 0 },    // Ramp down
  ],
};

export const options = {
  stages: STAGES.custom,
  // ...
};
```

### Change Exporter Config

Edit `load-tests/config/config.load.yaml`:

```yaml
performance:
  scrape_workers: 8        # Number of scrape workers
  send_buffer_size: 1000   # Send buffer size
  scrape_timeout: 3        # Scrape timeout (seconds)
  send_timeout: 10         # Send timeout (seconds)
```

### Add Metrics to Prometheus

Edit `load-tests/config/prometheus-load.yaml` to add new targets.

## 📋 Pre-Test Checklist

- [ ] Docker is running and accessible
- [ ] Sufficient resources (minimum 4 CPU, 8GB RAM)
- [ ] Ports available: 9090, 9092, 8080, 3000, 2181
- [ ] k6 installed (for local run): `brew install k6` or https://k6.io/docs/getting-started/installation/

## 🐛 Troubleshooting

### k6 Container Not Starting

```bash
# Check logs
docker compose -f docker-compose.load.yaml logs k6

# Run without docker compose
k6 run load-tests/k6/http_load_test.js
```

### Exporter Not Collecting Metrics

```bash
# Check Prometheus availability
curl http://localhost:9090/metrics

# Check exporter logs
docker compose -f docker-compose.load.yaml logs -f exporter
```

### Kafka Errors

```bash
# Check Kafka status
docker compose -f docker-compose.load.yaml logs kafka

# Recreate topic
docker compose -f docker-compose.load.yaml exec kafka kafka-topics --bootstrap-server localhost:9092 --delete --topic prometheus-metrics
```

## 📊 Interpreting Results

### Good Results

| Metric | Value |
|--------|-------|
| Scrape p95 | < 200ms |
| Scrape p99 | < 500ms |
| Kafka p95 | < 100ms |
| Error rate | < 0.1% |

### Issues and Solutions

| Issue | Possible Cause | Solution |
|-------|----------------|----------|
| High scrape latency | Not enough workers | Increase `scrape_workers` |
| Kafka timeout | Small batch size | Increase `batch_size`, `linger_ms` |
| Send errors | Kafka unavailable | Check Kafka status |
| Memory leak | Long test | Increase Docker memory limits |

## 📝 Reporting

Test results saved to:
- `load-tests/results/k6_report_*.json` — k6 report
- E2E test console output — copy manually

## 🔗 Additional Resources

- [k6 Documentation](https://k6.io/docs/)
- [Locust Documentation](https://docs.locust.io/)
- [Prometheus Performance](https://prometheus.io/docs/operating/performance/)
- [Kafka Performance Tuning](https://kafka.apache.org/documentation/#performance)

---

**🇷🇺 Russian version:** [README.ru.md](README.ru.md)
