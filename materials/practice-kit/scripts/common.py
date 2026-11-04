"""Общие операции эталона. Никаких оценок или зачёта обучающегося."""

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
WORK.mkdir(exist_ok=True)


def read_json(path):
    # Windows PowerShell 5.1 добавляет BOM при Set-Content -Encoding UTF8.
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(values, fraction):
    """Nearest rank; пустая выборка остаётся неизвестной."""
    if type(fraction) not in (int, float) or not 0 < fraction <= 1:
        raise ValueError("fraction must be in (0, 1]")
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in values):
        raise ValueError("measurements must be finite numbers")
    return (
        sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]
        if values
        else None
    )


def wilson(ok, total):
    """Интервал для независимых бинарных наблюдений; повторы не создают новые группы."""
    if type(ok) is not int or type(total) is not int or not 0 <= ok <= total:
        raise ValueError("invalid counters")
    if total == 0:
        return None
    z = 1.96
    p = ok / total
    den = 1 + z * z / total
    center = (p + z * z / (2 * total)) / den
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / den
    return [center - half, center + half]


def retrieval_metrics(ranked, relevant, k=3):
    """Бинарная релевантность; отсутствие разметки не означает нулевое качество."""
    if type(k) is not int or k < 1:
        raise ValueError("k must be a positive integer")
    ranked = list(dict.fromkeys(ranked))[:k]
    relevant = set(relevant)
    if not relevant:
        return {"recall": None, "rr": None, "ndcg": None}
    hits = [int(item in relevant) for item in ranked]
    dcg = sum(h / math.log2(i + 2) for i, h in enumerate(hits))
    ideal = sum(1 / math.log2(i + 2) for i in range(min(k, len(relevant))))
    return {
        "recall": sum(hits) / len(relevant),
        "rr": next((1 / (i + 1) for i, h in enumerate(hits) if h), 0),
        "ndcg": dcg / ideal,
    }


def edit_distance(left, right):
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(
                min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b))
            )
        previous = current
    return previous[-1]


def chat_content(response):
    """Проверить структуру ответа провайдера до обращения к полям.

    JSON может быть корректным синтаксически и иметь произвольный тип корня.
    Ошибка контракта остаётся отказом зависимости, без вывода её тела в журнал.
    """
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("invalid chat response") from error
    if not isinstance(content, str) or not content.strip():
        raise ValueError("chat content must be nonempty text")
    return content
