"""Функциональная API-проверка UI в отдельном validation-volume, не оценка участника."""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from common import WORK, write_json

with httpx.Client(timeout=60) as client:
    base = "http://webui:8080"
    config = client.get(base + "/api/config")
    config.raise_for_status()
    email = "validation@course.invalid"
    password = Path("/run/secrets/ui-validation-password.txt").read_text().strip()
    # Отдельный disposable validation-volume; никаких реальных учётных записей.
    created = client.post(
        base + "/api/v1/auths/signin", json={"email": email, "password": password}
    )
    if created.status_code != 200:
        created = client.post(
            base + "/api/v1/auths/signup",
            json={"name": "Course validation", "email": email, "password": password},
        )
    created.raise_for_status()
    token = created.json()["token"]
    headers = {"Authorization": "Bearer " + token}
    models = client.get(base + "/api/models", headers=headers)
    models.raise_for_status()
    ids = [m["id"] for m in models.json()["data"]]
    if ids != ["training"]:
        raise RuntimeError("unexpected model list: " + str(ids))
    response = client.post(
        base + "/api/chat/completions",
        headers=headers,
        json={
            "model": "training",
            "messages": [{"role": "user", "content": "Верни одно слово: тест"}],
            "stream": False,
            "max_tokens": 16,
        },
    )
    if response.status_code != 200:
        write_json(
            WORK / "ui-error.json",
            {
                "status": response.status_code,
                "models": ids,
                "synthetic_error": response.text,
            },
        )
    response.raise_for_status()
    result = response.json()
    write_json(
        WORK / "ui-validation.json",
        {
            "config_status": config.status_code,
            "models": ids,
            "chat_status": response.status_code,
            "answer": result["choices"][0]["message"]["content"],
            "stream": False,
            "scope": "separate local validation volume; synthetic input; credentials not logged",
        },
    )
    print("Open WebUI: config/models/non-stream chat succeeded")
