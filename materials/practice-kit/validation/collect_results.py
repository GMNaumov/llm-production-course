"""Сохранить публичные синтетические итоги авторского эталона, без секретов/логов."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from common import ROOT, WORK, read_json, write_json

benchmarks = {}
for tag in [
    "base-fp16-v1",
    "base-fp16-v2",
    "base-nf4-v2",
    "base-rag-nf4",
    "adapter-nf4-v2",
    "adapter-rag-nf4",
    "chat-alt-fp16",
]:
    path = WORK / f"benchmark-{tag}.json"
    if path.exists():
        report = read_json(path)
        benchmarks[tag] = {
            "dataset_sha256": report["dataset_sha256"],
            "summary": report["summary"],
            "rag_context": report.get("rag_context", False),
            "outcomes": [
                {
                    "id": r["id"],
                    "schema_ok": r["schema_ok"],
                    "correct": r["correct"],
                    "outcome": r["outcome"],
                    "serving": r.get("local_metrics"),
                }
                for r in report["rows"]
            ],
        }
write_json(
    ROOT / "validation/model-sources.json",
    {
        p.parent.name: read_json(p)
        for p in (ROOT / "models").glob("*/course-source.json")
    },
)
result = {
    "date": "2026-11-04",
    "scope": "public synthetic author runs; no student grading or independent enterprise acceptance",
    "benchmarks": benchmarks,
}
for name, path in [
    ("ocr", "ocr-summary.json"),
    ("vlm", "vlm-results.json"),
    ("ui", "ui-validation.json"),
    ("checks", "author-checks.json"),
    ("load", "load-4-rag.json"),
]:
    if (WORK / path).exists():
        result[name] = read_json(WORK / path)
for alias, path in [
    ("qlora", "adapter/run.json"),
    ("reranker", "reranker-adapted/run.json"),
]:
    if (WORK / path).exists():
        run = read_json(WORK / path)
        result[alias] = {
            k: run[k]
            for k in [
                "steps",
                "seed",
                "lr",
                "microbatch",
                "accumulation",
                "length",
                "train_sha256",
                "dev_sha256",
                "dev_loss",
                "elapsed_seconds",
                "seconds",
                "peak_allocated_bytes",
                "peak_reserved_bytes",
                "gpu",
                "versions",
                "cuda",
                "trainable_parameters",
                "warning",
            ]
            if k in run
        }
write_json(ROOT / "validation/results.json", result)
print("Public synthetic summaries saved; secrets and raw logs excluded")
