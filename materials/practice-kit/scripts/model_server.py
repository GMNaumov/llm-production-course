"""Минимальный локальный inference/embedding/rerank сервер для синтетического стенда.
OpenAI-совместим только реализованный subset, streaming/tools/JSON grammar отсутствуют.
"""

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Literal

import torch
from fastapi import FastAPI, HTTPException
from peft import PeftModel
from pydantic import BaseModel, ConfigDict, Field, field_validator
from transformers import (
    AutoModel,
    AutoModelForCausalLM,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    BitsAndBytesConfig,
)

torch.set_num_threads(2)
device = "cuda" if torch.cuda.is_available() else "cpu"
path = os.getenv("MODEL_PATH", "/models/chat-small")
source_file = Path(path) / "course-source.json"
source_revision = (
    json.loads(source_file.read_text())["revision"]
    if source_file.exists()
    else "unrecorded"
)
tokenizer = AutoTokenizer.from_pretrained(
    path, local_files_only=True, trust_remote_code=False
)
options = {
    "local_files_only": True,
    "trust_remote_code": False,
    "torch_dtype": torch.float16 if device == "cuda" else torch.float32,
}
if os.getenv("QUANTIZE", "0") == "1":
    if device != "cuda":
        raise RuntimeError("4bit profile requires CUDA")
    options["quantization_config"] = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )
    options["device_map"] = {"": 0}
model = AutoModelForCausalLM.from_pretrained(path, **options)
if "device_map" not in options:
    model = model.to(device)
if os.getenv("ADAPTER_PATH"):
    model = PeftModel.from_pretrained(
        model, os.environ["ADAPTER_PATH"], local_files_only=True
    )
model.eval()
lock = threading.Lock()
embedding = None
ranker = None
app = FastAPI(docs_url=None, redoc_url=None)


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    role: Literal["system", "user", "assistant"]
    content: str = Field(max_length=20000)


class Chat(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    model: Literal["training"] = "training"
    stream: Literal[False] = False
    messages: list[Message] = Field(min_length=1, max_length=20)
    max_tokens: int = Field(default=128, ge=1, le=512)
    temperature: float = Field(default=0, ge=0, le=2, allow_inf_nan=False)

    @field_validator("stream", mode="before")
    @classmethod
    def no_streaming(cls, value):
        # Literal[False] сам по себе также принимает числовой 0 в Pydantic.
        if value is not False:
            raise ValueError("stream must be false; streaming is unsupported")
        return value


class Embeddings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    input: list[str] = Field(min_length=1, max_length=32)


class Rerank(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(max_length=2000)
    documents: list[str] = Field(min_length=1, max_length=20)


@app.get("/live")
@app.get("/ready")
def ready():
    return {
        "state": "ready",
        "device": device,
        "quantized": os.getenv("QUANTIZE", "0") == "1",
        "adapter": bool(os.getenv("ADAPTER_PATH")),
        "base_revision": source_revision,
        "template_sha256": hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(),
    }


@app.get("/v1/models")
def models():
    return {
        "object": "list",
        "data": [{"id": "training", "object": "model", "owned_by": "local-course"}],
    }


@app.post("/v1/chat/completions")
def chat(request: Chat):
    start = time.perf_counter()
    with lock, torch.inference_mode():
        messages = [m.model_dump() for m in request.messages]
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(text, return_tensors="pt", add_special_tokens=False).to(
            device
        )
        count = inputs["input_ids"].shape[1]
        if count + request.max_tokens > 2048:
            raise HTTPException(413, "context budget exceeded")
        torch.cuda.reset_peak_memory_stats() if device == "cuda" else None
        generation = {
            "max_new_tokens": request.max_tokens,
            "do_sample": request.temperature > 0,
            "pad_token_id": tokenizer.eos_token_id,
        }
        if request.temperature > 0:
            generation["temperature"] = request.temperature
        output = model.generate(**inputs, **generation)
        answer = tokenizer.decode(output[0, count:], skip_special_tokens=True)
        return {
            "id": "local",
            "object": "chat.completion",
            "model": "training",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": answer},
                    "finish_reason": "length"
                    if output.shape[1] - count >= request.max_tokens
                    else "stop",
                }
            ],
            "usage": {
                "prompt_tokens": count,
                "completion_tokens": output.shape[1] - count,
                "total_tokens": output.shape[1],
            },
            "local_metrics": {
                "latency_ms": 1000 * (time.perf_counter() - start),
                "peak_allocated_bytes": torch.cuda.max_memory_allocated()
                if device == "cuda"
                else None,
                "quantized": os.getenv("QUANTIZE", "0") == "1",
                "adapter": bool(os.getenv("ADAPTER_PATH")),
                "base_revision": source_revision,
            },
        }


@app.post("/v1/embeddings")
def embed(request: Embeddings):
    global embedding
    if any(len(x) > 8000 for x in request.input):
        raise HTTPException(413, "embedding length")
    with lock, torch.inference_mode():
        if embedding is None:
            ep = os.getenv("EMBEDDING_PATH", "/models/embedding")
            embedding = (
                AutoTokenizer.from_pretrained(ep, local_files_only=True),
                AutoModel.from_pretrained(ep, local_files_only=True).eval(),
            )
        tok, encoder = embedding
        batch = tok(request.input, padding=True, truncation=False, return_tensors="pt")
        if batch["input_ids"].shape[1] > 512:
            raise HTTPException(413, "embedding token budget")
        hidden = encoder(**batch).last_hidden_state
        mask = batch["attention_mask"].unsqueeze(-1)
        pooled = (hidden * mask).sum(1) / mask.sum(1)
        vectors = torch.nn.functional.normalize(pooled, p=2, dim=1).tolist()
        return {"data": [{"index": i, "embedding": v} for i, v in enumerate(vectors)]}


@app.post("/rerank")
def rerank(request: Rerank):
    global ranker
    if any(len(x) > 8000 for x in request.documents):
        raise HTTPException(413, "reranker length")
    with lock, torch.inference_mode():
        if ranker is None:
            rp = os.getenv("RERANKER_PATH", "/models/reranker")
            ranker = (
                AutoTokenizer.from_pretrained(rp, local_files_only=True),
                AutoModelForSequenceClassification.from_pretrained(
                    rp, local_files_only=True
                ).eval(),
            )
        tok, encoder = ranker
        batch = tok(
            [request.query] * len(request.documents),
            request.documents,
            padding=True,
            truncation=False,
            return_tensors="pt",
        )
        if batch["input_ids"].shape[1] > 512:
            raise HTTPException(413, "reranker token budget")
        scores = encoder(**batch).logits.flatten().tolist()
        return {"scores": scores}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False, limit_concurrency=16)
