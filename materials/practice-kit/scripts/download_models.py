"""Только публичные учебные модели. Запуск с сетью — на этапе подготовки.
Получаем immutable commit один раз и сохраняем источник/checksums для офлайн.
"""

import argparse

from common import ROOT, checksum, write_json
from huggingface_hub import HfApi, snapshot_download

CANDIDATES = {
    "chat-small": "Qwen/Qwen2.5-0.5B-Instruct",
    "chat-alt": "Qwen/Qwen2.5-1.5B-Instruct",
    "embedding": "intfloat/multilingual-e5-small",
    "reranker": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
    "vlm": "HuggingFaceTB/SmolVLM-256M-Instruct",
}
parser = argparse.ArgumentParser()
parser.add_argument(
    "aliases", nargs="*", choices=list(CANDIDATES), default=list(CANDIDATES)
)
args = parser.parse_args()
api = HfApi()
for alias in args.aliases:
    repo = CANDIDATES[alias]
    destination = ROOT / "models" / alias
    lock = destination / "course-source.json"
    if lock.exists():
        print(alias, "already prepared; use a new directory for another revision")
        continue
    info = api.model_info(repo)
    snapshot_download(
        repo,
        revision=info.sha,
        local_dir=destination,
        allow_patterns=[
            "*.json",
            "*.safetensors",
            "*.txt",
            "*.model",
            "*.md",
            "LICENSE*",
            "*.jinja",
        ],
        ignore_patterns=[
            "onnx/*",
            "openvino/*",
            "*.onnx",
            "*.bin",
            "*.h5",
            "*.msgpack",
            "*.ot",
        ],
        max_workers=2,
    )
    # Некоторые старые cross-encoder распространяются только как pytorch_model.bin.
    if not list(destination.glob("*.safetensors")):
        snapshot_download(
            repo,
            revision=info.sha,
            local_dir=destination,
            allow_patterns=["pytorch_model.bin"],
            max_workers=1,
        )
    files = {
        str(p.relative_to(destination)): checksum(p)
        for p in destination.rglob("*")
        if p.is_file() and ".cache" not in p.parts
    }
    write_json(
        lock,
        {
            "repository": repo,
            "revision": info.sha,
            "files": files,
            "use": "synthetic-teaching-only; review model card and license",
        },
    )
    print(alias, info.sha, len(files), "files")
