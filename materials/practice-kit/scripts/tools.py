"""Локальный эталон preview/confirm: SQLite-транзакция и стойкая идемпотентность.
Не распределённая транзакция с PDM и не промышленная авторизация.
"""
import hashlib
import json
import secrets
import sqlite3
import time
from common import WORK


def connect(path=None):
    connection=sqlite3.connect(path or WORK/'effects.sqlite',timeout=3,isolation_level=None)
    connection.row_factory=sqlite3.Row
    connection.executescript('''
      CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, plant TEXT NOT NULL, quantity INTEGER NOT NULL, version INTEGER NOT NULL);
      INSERT OR IGNORE INTO orders VALUES ('TRN-0001','A',10,1),('TRN-0002','B',20,1);
      CREATE TABLE IF NOT EXISTS previews (token TEXT PRIMARY KEY, actor TEXT NOT NULL, plant TEXT NOT NULL, payload TEXT NOT NULL, expires REAL NOT NULL, result TEXT);
    ''')
    return connection


def authorize(actor, plant, order, write=False):
    # Доверенная личность в эталоне, не аргумент от модели. Роль моделирует IdP.
    rights={'reader-a':('A',False),'engineer-a':('A',True),'engineer-b':('B',True)}
    allowed=rights.get(actor)
    if not allowed or allowed[0]!=plant or order['plant']!=plant or (write and not allowed[1]):
        raise PermissionError('not permitted')


def preview(db,actor,plant,order_id,quantity):
    if type(quantity) is not int or not 1<=quantity<=1000:
        raise ValueError('quantity')
    row=db.execute('SELECT * FROM orders WHERE id=?',(order_id,)).fetchone()
    if row is None:
        raise PermissionError('not permitted')
    authorize(actor,plant,row,write=True)
    payload=json.dumps({'order_id':order_id,'old':row['quantity'],'new':quantity,'version':row['version']},sort_keys=True)
    token=secrets.token_urlsafe(32)
    db.execute('INSERT INTO previews VALUES(?,?,?,?,?,NULL)',(token,actor,plant,payload,time.time()+300))
    return {'confirmation_id':token,'effect':json.loads(payload),'expires_seconds':300,'payload_sha256':hashlib.sha256(payload.encode()).hexdigest()}


def confirm(db,actor,plant,token,explicit_confirmation):
    # explicit_confirmation приходит от отдельного человеческого интерфейса.
    if explicit_confirmation is not True:
        raise PermissionError('human confirmation required')
    db.execute('BEGIN IMMEDIATE')
    try:
        operation=db.execute('SELECT * FROM previews WHERE token=?',(token,)).fetchone()
        if operation is None or operation['actor']!=actor or operation['plant']!=plant:
            raise PermissionError('not permitted')
        payload=json.loads(operation['payload'])
        row=db.execute('SELECT * FROM orders WHERE id=?',(payload['order_id'],)).fetchone()
        authorize(actor,plant,row,write=True)  # Перепроверяем права и при replay.
        if operation['result']:
            result=json.loads(operation['result'])
        else:
            if operation['expires']<time.time():
                raise ValueError('expired')
            if row['version']!=payload['version']:
                raise ValueError('stale preview')
            db.execute('UPDATE orders SET quantity=?,version=version+1 WHERE id=?',(payload['new'],payload['order_id']))
            result={'order_id':payload['order_id'],'quantity':payload['new'],'version':payload['version']+1}
            db.execute('UPDATE previews SET result=? WHERE token=?',(json.dumps(result),token))
        db.execute('COMMIT')
        return result
    except Exception:
        db.execute('ROLLBACK')
        raise
