"""Наблюдаемые эталонные расчёты, без проверки/оценивания сдаваемых работ."""

import argparse
import json

from common import (
    WORK,
    percentile,
    retrieval_metrics,
    wilson,
    write_json,
)
from contracts import StatusField, route
from documents import extract_status
from rag import evaluate
from tools import confirm, connect, preview


def baseline():
    times = [240, 180, 300, 210, 270, 600, 120, 360, 240, 180]
    return {
        "synthetic": True,
        "n": len(times),
        "p50_seconds": percentile(times, 0.5),
        "p95_seconds": percentile(times, 0.95),
        "rework_fraction": 2 / 10,
        "candidates": ["поиск действующей редакции", "перенос спецификации"],
        "blocked": "автономная производственная запись",
    }


def metrics():
    return {
        "retrieval": retrieval_metrics(["C", "B", "A"], ["A", "B"], 3),
        "wilson_19_of_20": wilson(19, 20),
        "empty_latency": percentile([], 0.95),
    }


def fields():
    outputs = []
    for text in [
        "Статус: approved",
        "Статус не указан",
        "Статус: draft; Статус: approved",
    ]:
        field = StatusField.model_validate(extract_status(text, "synthetic-A", "1", 1))
        outputs.append({"field": field.model_dump(), "route": route(field)})
    return outputs


def effects():
    # Отдельный файл данного демонстрационного запуска, не reset учебных результатов.
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        db = connect(directory + "/effects.sqlite")
        before = dict(db.execute("SELECT * FROM orders WHERE id='TRN-0001'").fetchone())
        plan = preview(db, "engineer-a", "A", "TRN-0001", 12)
        refused = False
        try:
            confirm(db, "engineer-a", "A", plan["confirmation_id"], False)
        except PermissionError:
            refused = True
        first = confirm(db, "engineer-a", "A", plan["confirmation_id"], True)
        db.close()
        db = connect(directory + "/effects.sqlite")
        replay = confirm(db, "engineer-a", "A", plan["confirmation_id"], True)
        after = dict(db.execute("SELECT * FROM orders WHERE id='TRN-0001'").fetchone())
        db.close()
        return {
            "before": before,
            "without_confirmation_refused": refused,
            "first": first,
            "after_restart_replay": replay,
            "after": after,
        }


def economics():
    return [
        {
            "saved_minutes": saved,
            "monthly_net": 600 * saved / 60 * 1200 * 0.7 - 12000 - 600 * (5 + 3),
            "six_month_net": 6 * (600 * saved / 60 * 1200 * 0.7 - 12000 - 600 * (5 + 3))
            - 60000,
        }
        for saved in (2, 5, 8)
    ]


def gate(critical, quality, p95, min_quality, max_p95):
    import math

    if type(critical) is not int or critical < 0:
        return "insufficient evidence"
    if critical > 0:
        return "fail"
    values = [quality, p95, min_quality, max_p95]
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in values):
        return "insufficient evidence"
    if not 0 <= quality <= 1 or not 0 <= min_quality <= 1 or p95 < 0 or max_p95 < 0:
        return "insufficient evidence"
    return "pass" if quality >= min_quality and p95 <= max_p95 else "fail"


def gates():
    return {
        "illustrative_thresholds_only": True,
        "good": gate(0, 0.95, 100, 0.9, 500),
        "critical": gate(1, 0.99, 100, 0.9, 500),
        "missing": gate(0, None, 100, 0.9, 500),
        "regression": gate(0, 0.7, 100, 0.9, 500),
    }


if __name__ == "__main__":
    actions = {
        "baseline": baseline,
        "metrics": metrics,
        "rag": lambda: evaluate("lexical"),
        "fields": fields,
        "effects": effects,
        "economics": economics,
        "gates": gates,
    }
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=[*actions, "all"])
    name = parser.parse_args().action
    result = (
        {key: action() for key, action in actions.items()}
        if name == "all"
        else actions[name]()
    )
    write_json(WORK / f"demo-{name}.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
