"""Отдельные синтетические секреты Docker volume с минимальным UID/GID-доступом.
Не меняет файлы хоста и не ротирует существующие значения.
"""
import os
from pathlib import Path
import secrets

directory=Path('/run/course-secrets')
for name,group in [('gateway-token.txt',0),('api-token.txt',1654),('db-admin.txt',999),('db-reader.txt',999),('ui-validation-password.txt',0)]:
    path=directory/name
    if not path.exists():
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o400)
        with os.fdopen(descriptor,'w') as stream:
            stream.write(secrets.token_urlsafe(32))
        os.chown(path,0,group)
        os.chmod(path,0o400 if group==0 else 0o440)
print('Synthetic container credentials provisioned; existing values unchanged')
