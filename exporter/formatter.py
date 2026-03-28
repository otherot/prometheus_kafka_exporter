"""Форматирование метрик в JSON."""

import json
import time
from datetime import datetime, timezone
from typing import Any

from .config import FormatConfig
from .collector import Metric


class MetricFormatter:
    """Форматирование метрик в JSON."""

    def __init__(self, config: FormatConfig):
        self.config = config
        self._template = config.json_template

    def format(self, metric: Metric) -> str:
        """Форматировать метрику в JSON строку."""
        data = self._build_data(metric)
        # Парсим labels обратно в dict для JSON сериализации
        data["labels"] = json.loads(data["labels"])
        return json.dumps(data, ensure_ascii=False)

    def format_batch(self, metrics: list[Metric]) -> list[str]:
        """Форматировать пакет метрик."""
        return [self.format(m) for m in metrics]

    def _build_data(self, metric: Metric) -> dict[str, Any]:
        """Построить данные для форматирования."""
        return {
            "name": metric.name,
            "value": metric.value,
            "timestamp": self._format_timestamp(metric.timestamp),
            "labels": json.dumps(metric.labels, ensure_ascii=False),
            "help": metric.help_text or "",
            "type": metric.metric_type or "gauge",
        }

    def _format_timestamp(self, timestamp_ms: int) -> int | str:
        """Форматировать timestamp согласно настройкам."""
        if self.config.timestamp_format == "unix_ms":
            return timestamp_ms
        elif self.config.timestamp_format == "unix_s":
            return timestamp_ms // 1000
        elif self.config.timestamp_format == "iso":
            dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
            return dt.isoformat()
        else:
            return timestamp_ms

    def validate_template(self) -> tuple[bool, str]:
        """Проверить валидность шаблона."""
        try:
            # Пробуем форматировать тестовую метрику
            test_metric = Metric(
                name="test_metric",
                value=1.0,
                timestamp=int(time.time() * 1000),
                labels={"label1": "value1"},
            )
            self.format(test_metric)
            return True, ""
        except KeyError as e:
            return False, f"Missing key in template: {e}"
        except Exception as e:
            return False, f"Template error: {e}"
