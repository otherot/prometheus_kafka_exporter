/**
 * k6 сценарий для нагрузочного тестирования Prometheus Kafka Exporter
 * Тестирует HTTP endpoint метрик экспортера
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Кастомные метрики
const errorRate = new Rate('errors');
const scrapeLatency = new Trend('scrape_latency_ms');
const metricsCount = new Counter('metrics_count');

// Конфигурация нагрузки
const STAGES = {
  // По умолчанию - базовая нагрузка
  default: [
    { duration: '30s', target: 10 },   // Разогрев: 10 VUs
    { duration: '1m', target: 50 },    // Нагрузка: 50 VUs
    { duration: '2m', target: 100 },   // Пик: 100 VUs
    { duration: '1m', target: 50 },    // Снижение
    { duration: '30s', target: 0 },    // Остановка
  ],
  // Highload тест
  highload: [
    { duration: '1m', target: 100 },
    { duration: '3m', target: 500 },
    { duration: '2m', target: 1000 },
    { duration: '1m', target: 0 },
  ],
  // Стресс тест
  stress: [
    { duration: '30s', target: 100 },
    { duration: '1m', target: 300 },
    { duration: '2m', target: 500 },
    { duration: '5m', target: 500 },
    { duration: '30s', target: 0 },
  ],
};

export const options = {
  stages: STAGES.default,
  thresholds: {
    http_req_duration: ['p(50)<100', 'p(95)<500', 'p(99)<1000'],
    http_req_failed: ['rate<0.01'],
    errors: ['rate<0.01'],
    scrape_latency_ms: ['p(95)<500'],
  },
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
};

const BASE_URL = __ENV.EXPORTER_URL || 'http://localhost:8080';

export default function () {
  // Запрос к endpoint метрик
  const params = {
    headers: {
      'Accept': 'text/plain',
    },
  };
  
  const startTime = Date.now();
  const res = http.get(`${BASE_URL}/metrics`, params);
  const latency = Date.now() - startTime;
  
  scrapeLatency.add(latency);
  
  // Проверки
  const checks = {
    'status is 200': res.status === 200,
    'response time < 5s': res.timings.duration < 5000,
    'has content': res.body && res.body.length > 0,
  };
  
  const checkResult = check(res, checks);
  errorRate.add(!checkResult);
  
  // Подсчёт количества метрик (примерно по количеству строк)
  if (res.body) {
    const lines = res.body.split('\n').length;
    metricsCount.add(lines);
  }
  
  // Небольшая пауза между запросами
  sleep(0.1);
}

export function handleSummary(data) {
  // Генерация отчёта
  const report = {
    timestamp: new Date().toISOString(),
    test_type: 'k6_http_load',
    summary: {
      total_requests: data.metrics.http_reqs.values.count,
      avg_latency_ms: data.metrics.http_req_duration.values.avg,
      p95_latency_ms: data.metrics.http_req_duration.values['p(95)'],
      p99_latency_ms: data.metrics.http_req_duration.values['p(99)'],
      error_rate: data.metrics.http_req_failed.values.rate,
      avg_scrape_latency_ms: data.metrics.scrape_latency_ms.values.avg,
      avg_metrics_count: data.metrics.metrics_count.values.avg,
    },
    thresholds: {
      passed: data.metrics.http_req_failed.values.rate < 0.01,
    },
  };
  
  return {
    'stdout': JSON.stringify(report, null, 2),
    [`results/k6_report_${Date.now()}.json`]: JSON.stringify(report, null, 2),
  };
}
