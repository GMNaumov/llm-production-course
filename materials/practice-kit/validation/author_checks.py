"""Авторская проверка только комплектных эталонов, не сдаваемых работ.
Требует запущенных учебных gateway/db/api. Не ищет решения участников.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import httpx
import psycopg
from pydantic import ValidationError
from common import ROOT,WORK,read_json,write_json,retrieval_metrics,wilson
from contracts import StatusField,Source,route
from document_pipeline import QuantityField
from demo import gate
from rag import authorized,bm25,rrf
from tools import connect,preview,confirm
from tool_dispatch import dispatch
from sql_client import ast_guard,TEMPLATES,execute

observations=[]
def check(label,condition):
    if not condition: raise AssertionError(label)
    observations.append(label)

def rejects(label,action,exceptions=(ValueError,PermissionError,ValidationError)):
    try: action()
    except exceptions: observations.append(label); return
    raise AssertionError(label+' did not reject')

check('ndcg hand calculation',abs(retrieval_metrics(['C','B','A'],['A','B'])['ndcg']-.6934264036)<1e-8)
check('empty relevant unknown',retrieval_metrics([],[])['recall'] is None)
check('wilson bound',.763<wilson(19,20)[0]<.765)
check('rrf order',rrf([['A','B','C'],['B','D','A']])[:2]==['B','A'])
for label,values,expected in [
 ('gate pass',(0,.95,100,.9,500),'pass'),('gate critical',(1,.99,100,.9,500),'fail'),
 ('gate missing',(0,None,100,.9,500),'insufficient evidence'),('gate nan',(0,float('nan'),100,.9,500),'insufficient evidence'),
 ('gate inf',(0,.95,float('inf'),.9,500),'insufficient evidence'),('gate bool',(False,.95,100,.9,500),'insufficient evidence'),
 ('gate regression',(0,.7,100,.9,500),'fail'),('gate negative latency',(0,.95,-1,.9,500),'insufficient evidence')]:
    check(label,gate(*values)==expected)
source=Source(document='A',revision='1',page=1,bbox=(0.,0.,1.,1.))
check('status valid',StatusField(state='read',value='draft',source=source).state=='read')
rejects('read no source',lambda:StatusField(state='read',value='draft',source=None))
rejects('unknown with value',lambda:StatusField(state='unreadable',value='draft',source=None))
rejects('invalid bbox',lambda:Source(document='A',revision='1',page=1,bbox=(1.,0.,0.,1.)))
for value in [float('nan'),float('inf'),-1.]:
    rejects('quantity invalid '+str(value),lambda:QuantityField(state='read',value=value,unit='шт.',source=source))
check('unverified field reviewed',route(StatusField(state='read',value='draft',source=source))=='review')
corpus=read_json(ROOT/'data/corpus.json')
docs=authorized(corpus,'A')
check('ACL before ranking',all(d['plant']=='A' and d['active'] for d in docs))
check('canary absent from candidates',not any('CANARY-PLANT-B' in d['text'] for d in docs))
check('revocation overlay',not any(d['document'] in ['release','shortage'] for d in authorized(corpus,'A',['release'],['shortage'])))

with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'state.sqlite'
    db=connect(path)
    rejects('bool quantity',lambda:preview(db,'engineer-a','A','TRN-0001',True))
    rejects('reader write',lambda:preview(db,'reader-a','A','TRN-0001',12))
    rejects('wrong plant',lambda:preview(db,'engineer-a','A','TRN-0002',12))
    plan=preview(db,'engineer-a','A','TRN-0001',12)
    token=plan['confirmation_id']
    rejects('no human confirmation',lambda:confirm(db,'engineer-a','A',token,False))
    check('preview no effect',db.execute("SELECT quantity FROM orders WHERE id='TRN-0001'").fetchone()[0]==10)
    rejects('wrong confirmer',lambda:confirm(db,'engineer-b','B',token,True))
    stale=preview(db,'engineer-a','A','TRN-0001',13)
    expired=preview(db,'engineer-a','A','TRN-0001',14)
    db.execute('UPDATE previews SET expires=0 WHERE token=?',(expired['confirmation_id'],))
    rejects('expired confirmation',lambda:confirm(db,'engineer-a','A',expired['confirmation_id'],True))
    first=confirm(db,'engineer-a','A',token,True)
    rejects('stale preview',lambda:confirm(db,'engineer-a','A',stale['confirmation_id'],True))
    db.close()
    def replay(_):
        connection=connect(path)
        try: return confirm(connection,'engineer-a','A',token,True)
        finally: connection.close()
    with ThreadPoolExecutor(max_workers=4) as pool:
        repeated=list(pool.map(replay,range(8)))
    check('persistent concurrent replay',all(r==first for r in repeated))
    db=connect(path)
    check('one effect after replay',dict(db.execute("SELECT * FROM orders WHERE id='TRN-0001'").fetchone())['version']==2)
    db.close()

result=asyncio.run(dispatch({'name':'get_order_status','arguments':{'order_id':'TRN-0001','actor':'admin'}},'reader-a'))
check('tool role injection rejected',result['state']=='invalid_arguments')
for op,template in TEMPLATES.items():
    check('approved AST '+op,ast_guard(template.replace('%s',':order_id'),op))
for candidate in [
 'SELECT 1; SELECT 2','SELECT pg_sleep(10)','DELETE FROM training_api.orders',
 'WITH x AS (DELETE FROM training_api.orders RETURNING *) SELECT * FROM x',
 'SELECT * FROM pg_catalog.pg_authid','SELECT * FROM training_api.orders',
 'SELECT order_id,status INTO x FROM training_api.allowed_orders_a',
 'SELECT order_id,status FROM training_api.allowed_orders_a UNION SELECT order_id,status FROM training_api.orders']:
    rejects('blocked SQL '+str(len(observations)),lambda:ast_guard(candidate,'status'))
check('SQL semantics plant A',execute('shortage','TRN-0001')[0][1]==6)
check('SQL surplus clamped',execute('shortage','TRN-0002')[0][1]==0)
check('SQL null not zero',execute('shortage','TRN-0003')==[])
password=Path('/run/secrets/db-reader.txt').read_text().strip()
with psycopg.connect(host='db',dbname='training',user='reader_a',password=password,autocommit=True) as connection:
    rejects('DB base table denied',lambda:connection.execute('SELECT * FROM training_api.orders'),(psycopg.Error,))
    rejects('DB update denied',lambda:connection.execute("UPDATE training_api.orders SET status='approved'"),(psycopg.Error,))

with httpx.Client(timeout=3) as client:
    api_token=Path('/run/secrets/api-token.txt').read_text().strip()
    check('API unauthorized',client.get('http://api:8090/orders/TRN-0001').status_code==401)
    headers={'Authorization':'Bearer '+api_token}
    for ident,expected in [('TRN-0001',200),('TRN-0403',403),('TRN-0503',503),('TRN-9999',404)]:
        check('API '+ident,client.get('http://api:8090/orders/'+ident,headers=headers).status_code==expected)
    check('gateway unauthorized',client.post('http://gateway:8080/ask',json={'question':'test'}).status_code==401)
    token=Path('/run/secrets/gateway-token.txt').read_text().strip()
    headers={'Authorization':'Bearer '+token}
    check('gateway extra scope rejected',client.post('http://gateway:8080/ask',headers=headers,json={'question':'test','plant':'B'}).status_code==422)
    response=client.post('http://gateway:8080/ask',headers=headers,json={'question':'регламент выпуска','route':'search'})
    check('gateway authorized search',response.status_code==200)
    check('gateway source ACL',all(d['plant']=='A' for d in response.json()['sources']))
    check('request ID server generated',len(response.headers['x-request-id'])==32)
    check('inference unknown route rejected',client.post('http://inference:8000/v1/chat/completions',json={'model':'outside-allowlist','messages':[{'role':'user','content':'test'}]}).status_code==422)
    check('inference streaming rejected',client.post('http://inference:8000/v1/chat/completions',json={'stream':True,'messages':[{'role':'user','content':'test'}]}).status_code==422)
    check('inference context rejected',client.post('http://inference:8000/v1/chat/completions',json={'messages':[{'role':'user','content':'A '*3000}],'max_tokens':64}).status_code==413)

events=[json.loads(line) for line in (WORK/'audit.jsonl').read_text().splitlines()]
allowed={'request_id','release_id','policy','prompt','model','status','latency_ms'}
check('audit allowlist',all(set(e)<=allowed for e in events))
serialized=json.dumps(events)
check('audit no tokens',api_token not in serialized and token not in serialized)
check('audit no corpus canary','CANARY-PLANT-B' not in serialized)
write_json(WORK/'author-checks.json',{'scope':'reference kit only, not student submissions','count':len(observations),'checks':observations})
print('Author reference checks:',len(observations))
