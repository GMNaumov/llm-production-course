"""Регрессии найденных при ревью ошибок эталона; работы участников не читаются.

Запуск из полной копии репозитория; Docker-команда находится в README комплекта.
Сеть и GPU не требуются.
Подставные ответы проверяют границы контракта, а не качество языковой модели.
"""

import asyncio
import io
import json
import re
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import benchmark
import gateway
import httpx
import rag
from common import chat_content, percentile, read_json, retrieval_metrics, wilson
from contracts import Source, StatusField, route
from documents import extract_status
from documents import run as run_ocr
from fastapi.testclient import TestClient


def completion(content):
    return {"choices": [{"message": {"content": content}}]}


class TheoryChecks(unittest.TestCase):
    def test_executable_theory_examples(self):
        modules = Path(__file__).resolve().parents[2] / "modules"
        self.assertTrue(
            modules.is_dir(), "Mount the full repository, including materials/modules"
        )
        executed = 0
        for path in sorted(modules.glob("*/self-study.md")):
            for block in re.findall(
                r"^```python\s*\n(.*?)^```",
                path.read_text(encoding="utf-8"),
                re.M | re.S,
            ):
                if "import torch" in block:
                    continue  # Конфигурация PEFT проверяется отдельно в GPU-образе.
                with (
                    self.subTest(module=path.parent.name),
                    redirect_stdout(io.StringIO()),
                ):
                    exec(compile(block, str(path), "exec"), {})
                executed += 1
        self.assertEqual(executed, 12)


class ResponseChecks(unittest.TestCase):
    def setUp(self):
        self.docs = [{"id": "allowed-1", "text": "Разрешённый источник"}]

    def test_invalid_envelope(self):
        for response in (
            None,
            [],
            {},
            {"choices": []},
            completion(None),
            completion(" "),
        ):
            with self.subTest(response=response), self.assertRaises(ValueError):
                chat_content(response)

    def test_invalid_generated_json(self):
        invalid = [
            "null",
            "[]",
            "42",
            '"text"',
            '{"state": [], "answer": "x", "citations": []}',
            '{"state": "answer", "answer": "x", "citations": []}',
            '{"state": "answer", "answer": "x", "citations": ["plant-B"]}',
        ]
        for raw in invalid:
            with (
                self.subTest(raw=raw),
                patch.object(rag, "post", return_value=completion(raw)),
            ):
                self.assertEqual(
                    rag.answer("вопрос", self.docs, ["allowed-1"], "unused")["state"],
                    "abstain",
                )

    def test_dependency_failure_has_distinct_state(self):
        for response in ([], {"choices": []}, completion(None)):
            with (
                self.subTest(response=response),
                patch.object(rag, "post", return_value=response),
            ):
                self.assertEqual(
                    rag.answer("вопрос", self.docs, ["allowed-1"], "unused")["state"],
                    "dependency_error",
                )
        with patch.object(
            rag, "post", side_effect=urllib.error.URLError("synthetic failure")
        ):
            self.assertEqual(
                rag.answer("вопрос", self.docs, ["allowed-1"], "unused")["state"],
                "dependency_error",
            )

    def test_valid_citations_and_empty_retrieval(self):
        result = {"state": "answer", "answer": "Факт", "citations": ["allowed-1"]}
        with patch.object(rag, "post", return_value=completion(json.dumps(result))):
            self.assertEqual(
                rag.answer("вопрос", self.docs, ["allowed-1"], "unused"), result
            )
        with patch.object(rag, "post") as post:
            self.assertEqual(rag.answer("вопрос", [], [], "unused")["state"], "abstain")
            post.assert_not_called()

    def test_benchmark_preserves_invalid_envelopes(self):
        for envelope in ([], {"choices": []}, completion(None)):
            with (
                self.subTest(envelope=envelope),
                tempfile.TemporaryDirectory() as directory,
            ):
                path = Path(directory)
                dataset = path / "cases.json"
                dataset.write_text(
                    json.dumps(
                        [
                            {
                                "id": "one",
                                "text": "text",
                                "group": "g1",
                                "expected": "unknown",
                            }
                        ]
                    )
                )
                with (
                    patch.object(benchmark, "WORK", path),
                    patch.object(
                        benchmark.urllib.request,
                        "urlopen",
                        return_value=io.StringIO(json.dumps(envelope)),
                    ),
                ):
                    summary = benchmark.run("http://unused", "training", "v2", dataset)
                report = json.loads((path / "benchmark-v2.json").read_text())
                self.assertEqual(summary["n"], 1)
                self.assertEqual(summary["correct_fraction"], 0)
                self.assertEqual(report["rows"][0]["outcome"], "transport_error")


class MetricChecks(unittest.TestCase):
    def test_windows_json_bom(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text('{"synthetic": true}', encoding="utf-8-sig")
            self.assertEqual(read_json(path), {"synthetic": True})

    def test_retrieval_outage_stays_in_denominator(self):
        question = {"id": "q", "question": "text", "relevant": ["A"]}
        with (
            patch.object(rag, "read_json", side_effect=[[], [question]]),
            patch.object(
                rag, "rank", side_effect=urllib.error.URLError("synthetic failure")
            ),
            patch.object(rag, "write_json"),
        ):
            report = rag.evaluate("dense")
        self.assertEqual(len(report["rows"]), 1)
        self.assertEqual(report["rows"][0]["outcome"], "dependency_error")
        self.assertEqual(report["mean"], {"recall": 0, "rr": 0, "ndcg": 0})

    def test_invalid_parameters(self):
        for counters in ((-1, 1), (2, 1), (True, 1), (0, -1)):
            with self.subTest(counters=counters), self.assertRaises(ValueError):
                wilson(*counters)
        for fraction in (0, -0.1, 1.1, True, float("nan")):
            with self.subTest(fraction=fraction), self.assertRaises(ValueError):
                percentile([1], fraction)
        for k in (0, -1, True):
            with self.subTest(k=k), self.assertRaises(ValueError):
                retrieval_metrics([], ["A"], k)

    def test_empty_observations_stay_unknown(self):
        self.assertIsNone(wilson(0, 0))
        self.assertIsNone(percentile([], 0.95))
        self.assertIsNone(retrieval_metrics([], [])["recall"])
        self.assertEqual(rag.bm25("query", [{"id": "empty", "text": ""}]), [])
        with (
            patch.object(rag, "read_json", side_effect=[[], []]),
            patch.object(rag, "write_json"),
        ):
            self.assertEqual(
                rag.evaluate("lexical")["mean"],
                {"recall": None, "rr": None, "ndcg": None},
            )

    def test_route_requires_finite_calibrated_numbers(self):
        field = StatusField(
            state="read",
            value="draft",
            source=Source(document="A", revision="1", page=1),
        )
        for signal in (True, "0.9", float("nan"), float("inf"), -0.1):
            with self.subTest(signal=signal):
                self.assertEqual(route(field, True, signal, 0.8), "review")
        self.assertEqual(route(field, "yes", 0.9, 0.8), "review")
        self.assertEqual(route(field, True, 0.9, 0.8), "auto")

    def test_status_requires_whole_word(self):
        self.assertEqual(
            extract_status("Статус: approvedX", "A", "1", 1)["state"], "unreadable"
        )
        self.assertEqual(
            extract_status("Статус: approved.", "A", "1", 1)["value"], "approved"
        )

    def test_missing_ocr_binary_is_recorded(self):
        row = {
            "id": "one",
            "file": "missing.png",
            "reference": "text",
            "variant": "clean",
        }
        with (
            patch("documents.read_json", return_value=[row]),
            patch("documents.generate"),
            patch("documents.ocr", side_effect=FileNotFoundError()),
            patch("documents.write_json") as write,
        ):
            # PDF baseline здесь подставлен, потому что проверяется именно отказ OCR.
            with patch("documents.PdfReader") as pdf:
                pdf.return_value.pages[0].extract_text.return_value = "text"
                summary = run_ocr()
        self.assertEqual(summary["by_variant"]["clean"]["failures"], 1)
        self.assertIsNone(write.call_args_list[0].args[1][0]["prediction"])


class GatewayChecks(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.work = Path(self.directory.name)
        self.work_patch = patch.object(gateway, "WORK", self.work)
        self.work_patch.start()
        self.addCleanup(self.work_patch.stop)
        self.identity_patch = patch.object(
            gateway, "identity", AsyncMock(return_value=("reader-a", "A"))
        )
        self.identity_patch.start()
        self.addCleanup(self.identity_patch.stop)
        gateway.arrivals.clear()
        gateway.used.clear()
        gateway.semaphore = asyncio.Semaphore(2)

    def test_unexpected_failure_is_audited_and_releases_slot(self):
        with TestClient(gateway.app) as client:
            with patch.object(
                gateway, "read_json", side_effect=RuntimeError("PRIVATE-MARKER")
            ):
                failed = client.post("/ask", json={"question": "test"})
            success = client.post("/ask", json={"question": "выпуск"})
        self.assertEqual(failed.status_code, 503)
        self.assertEqual(success.status_code, 200)
        events_text = (self.work / "audit.jsonl").read_text()
        events = [json.loads(line) for line in events_text.splitlines()]
        self.assertEqual([e["status"] for e in events], [503, 200])
        self.assertEqual(events[0]["request_id"], failed.headers["x-request-id"])
        self.assertNotIn("PRIVATE-MARKER", events_text + failed.text)
        self.assertEqual(gateway.semaphore._value, 2)

    def test_malformed_provider_becomes_search_degradation(self):
        for envelope in ([], {"choices": []}, completion(None)):
            with self.subTest(envelope=envelope):
                upstream = AsyncMock()
                upstream.post.return_value = httpx.Response(
                    200, json=envelope, request=httpx.Request("POST", "http://unused")
                )
                context = AsyncMock()
                context.__aenter__.return_value = upstream
                with (
                    TestClient(gateway.app) as client,
                    patch.object(gateway.httpx, "AsyncClient", return_value=context),
                ):
                    response = client.post(
                        "/ask", json={"question": "регламент выпуска", "route": "rag"}
                    )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["state"], "degraded_search")


if __name__ == "__main__":
    unittest.main(verbosity=2)
