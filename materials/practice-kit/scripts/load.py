"""Закрытая модель нагрузки: параллельные клиенты. Ошибки входят в отчёт."""
import argparse
import asyncio
import time
from pathlib import Path
import httpx
from common import ROOT,WORK,write_json,percentile

async def main(args):
    token=Path('/run/secrets/gateway-token.txt').read_text().strip()
    sem=asyncio.Semaphore(args.clients)
    rows=[]
    start=time.perf_counter()
    async with httpx.AsyncClient(timeout=40) as client:
        async def one(index):
            async with sem:
                begin=time.perf_counter()
                status=0
                state='transport_error'
                try:
                    response=await client.post(args.base+'/ask',headers={'Authorization':'Bearer '+token},json={'question':'Что проверяют перед выпуском спецификации?','route':args.route})
                    status=response.status_code
                    state=response.json().get('state','http_error')
                except (httpx.HTTPError,ValueError):
                    pass
                rows.append({'index':index,'status':status,'state':state,'latency_ms':1000*(time.perf_counter()-begin)})
        await asyncio.gather(*(one(i) for i in range(args.requests)))
    elapsed=time.perf_counter()-start
    success=[r for r in rows if r['status']==200]
    states={state:sum(r['state']==state for r in rows) for state in sorted({r['state'] for r in rows})}
    summary={'model':'closed loop; scheduling wait excluded','clients':args.clients,'n':len(rows),'elapsed_seconds':elapsed,'completed_per_second':len(rows)/elapsed,'http_success_per_second':len(success)/elapsed,'generated_per_second':states.get('draft_for_review',0)/elapsed,'states':states,'http_error_fraction':1-len(success)/len(rows),'all_p50_ms':percentile([r['latency_ms'] for r in rows],.5),'all_p95_ms':percentile([r['latency_ms'] for r in rows],.95),'http_success_p95_ms':percentile([r['latency_ms'] for r in success],.95),'gpu_vram':'sample nvidia-smi separately; not inferred from HTTP'}
    write_json(WORK/f'load-{args.clients}-{args.route}.json',{'summary':summary,'rows':rows})
    print(summary)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',default='http://gateway:8080')
    parser.add_argument('--clients',type=int,choices=[1,2,4,8],default=4)
    parser.add_argument('--requests',type=int,choices=range(1,201),default=20)
    parser.add_argument('--route',choices=['search','rag'],default='search')
    asyncio.run(main(parser.parse_args()))
