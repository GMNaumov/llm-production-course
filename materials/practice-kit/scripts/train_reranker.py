"""Реальное дообучение cross-encoder на маленьких синтетических hard negatives.
Нужна независимая экспертная проверка negatives и отдельный закрытый test.
"""

import argparse
import importlib.metadata
import random
import time
from pathlib import Path

import torch
from common import ROOT, WORK, checksum, read_json, write_json
from transformers import AutoModelForSequenceClassification, AutoTokenizer

parser = argparse.ArgumentParser()
parser.add_argument("--model", default="/models/reranker")
parser.add_argument("--out", type=Path, default=WORK / "reranker-adapted")
parser.add_argument("--steps", type=int, default=12)
parser.add_argument(
    "--pairs",
    type=Path,
    help="JSON-массив [query, document, label] для разрешённого train",
)
args = parser.parse_args()
if args.steps < 1:
    parser.error("steps must be positive")
random.seed(17)
torch.manual_seed(17)
torch.set_num_threads(2)
device = "cuda" if torch.cuda.is_available() else "cpu"
corpus = read_json(ROOT / "data/corpus.json")
by_id = {d["id"]: d["text"] for d in corpus}
# Только dev-пример механики. Для финального эксперимента заменить разрешённым train.
pairs = [
    ("Что проверять перед выпуском?", by_id["release:r2:p1"], 1.0),
    ("Что проверять перед выпуском?", by_id["release:r1:p1"], 0.0),
    ("Можно угадать нечитаемый допуск?", by_id["drawing:r1:p1"], 1.0),
    ("Можно угадать нечитаемый допуск?", by_id["approval:r1:p3"], 0.0),
]
if args.pairs:
    pairs = read_json(args.pairs)
if not isinstance(pairs, list) or not pairs:
    raise ValueError("nonempty training pairs required")
for pair in pairs:
    if (
        not isinstance(pair, (list, tuple))
        or len(pair) != 3
        or not all(isinstance(value, str) and value.strip() for value in pair[:2])
        or type(pair[2]) not in (int, float)
        or pair[2] not in (0, 1)
    ):
        raise ValueError("expected [query, document, binary label]")
# Проверяем входы до загрузки весов: неверный набор не занимает GPU.
tokenizer = AutoTokenizer.from_pretrained(
    args.model, local_files_only=True, trust_remote_code=False
)
model = AutoModelForSequenceClassification.from_pretrained(
    args.model, local_files_only=True, trust_remote_code=False
).to(device)
optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5)
start = time.perf_counter()
losses = []
model.train()
for step in range(args.steps):
    query, document, label = pairs[step % len(pairs)]
    inputs = tokenizer(query, document, return_tensors="pt", truncation=False).to(
        device
    )
    if inputs["input_ids"].shape[1] > 256:
        raise ValueError("length: inspect truncation")
    optimizer.zero_grad()
    logit = model(**inputs).logits.flatten()
    loss = torch.nn.functional.binary_cross_entropy_with_logits(
        logit, torch.tensor([label], device=device)
    )
    if not torch.isfinite(loss):
        raise RuntimeError("nonfinite loss")
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    optimizer.step()
    losses.append(float(loss.detach()))
args.out.mkdir(parents=True, exist_ok=True)
model.save_pretrained(args.out)
tokenizer.save_pretrained(args.out)
write_json(
    args.out / "run.json",
    {
        "base": args.model,
        "base_source": read_json(Path(args.model) / "course-source.json")
        if (Path(args.model) / "course-source.json").exists()
        else None,
        "pairs_sha256": checksum(args.pairs) if args.pairs else None,
        "corpus_sha256": checksum(ROOT / "data/corpus.json")
        if not args.pairs
        else None,
        "versions": {
            package: importlib.metadata.version(package)
            for package in ("torch", "transformers", "tokenizers")
        },
        "device": device,
        "cuda": torch.version.cuda,
        "max_length": 256,
        "optimizer": "AdamW; weight_decay=0.01; gradient_clip_norm=1.0",
        "batch_size": 1,
        "seed": 17,
        "steps": args.steps,
        "lr": 2e-5,
        "losses": losses,
        "seconds": time.perf_counter() - start,
        "pairs": pairs,
        "warning": "training pairs require provenance, group split and independent human validation; public demonstration is not evidence of generalization",
    },
)
print("reranker saved; evaluate on independent human-labelled queries through /rerank")
