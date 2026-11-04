"""Только локальные учебные случайные токены; не корпоративное secret storage."""

import secrets

from common import ROOT

directory = ROOT / "secrets"
directory.mkdir(exist_ok=True)
for name in ["gateway-token.txt", "api-token.txt", "db-admin.txt", "db-reader.txt"]:
    target = directory / name
    if not target.exists():
        target.write_text(secrets.token_urlsafe(32), encoding="utf-8")
        target.chmod(0o600)
print(
    "Учебные секреты созданы без вывода значений. Ограничьте Windows ACL каталога secrets."
)
