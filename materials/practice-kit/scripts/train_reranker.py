"""Реальное дообучение cross-encoder на маленьких синтетических hard negatives.
Нужна независимая экспертная проверка negatives и отдельный закрытый test.
"""
import argparse
import json
import random
import time
from pathlib import Path
import torch
from transformers import AutoTokenizer,AutoModelForSequenceClassification
from common import ROOT,WORK,read_json,write_json

parser=argparse.ArgumentParser()
parser.add_argument('--model',default='/models/reranker')
parser.add_argument('--out',type=Path,default=WORK/'reranker-adapted')
parser.add_argument('--steps',type=int,default=12)
args=parser.parse_args()
random.seed(17)
torch.manual_seed(17)
torch.set_num_threads(2)
device='cuda' if torch.cuda.is_available() else 'cpu'
tokenizer=AutoTokenizer.from_pretrained(args.model,local_files_only=True)
model=AutoModelForSequenceClassification.from_pretrained(args.model,local_files_only=True).to(device)
corpus=read_json(ROOT/'data/corpus.json')
by_id={d['id']:d['text'] for d in corpus}
# Только dev-пример механики. Для финального эксперимента заменить разрешённым train.
pairs=[('Что проверять перед выпуском?',by_id['release:r2:p1'],1.),
       ('Что проверять перед выпуском?',by_id['release:r1:p1'],0.),
       ('Можно угадать нечитаемый допуск?',by_id['drawing:r1:p1'],1.),
       ('Можно угадать нечитаемый допуск?',by_id['approval:r1:p3'],0.)]
optimizer=torch.optim.AdamW(model.parameters(),lr=2e-5)
start=time.perf_counter()
losses=[]
model.train()
for step in range(args.steps):
    query,document,label=pairs[step%len(pairs)]
    inputs=tokenizer(query,document,return_tensors='pt',truncation=False).to(device)
    if inputs['input_ids'].shape[1]>256: raise ValueError('length: inspect truncation')
    optimizer.zero_grad()
    logit=model(**inputs).logits.flatten()
    loss=torch.nn.functional.binary_cross_entropy_with_logits(logit,torch.tensor([label],device=device))
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
    optimizer.step()
    losses.append(float(loss.detach()))
args.out.mkdir(parents=True,exist_ok=True)
model.save_pretrained(args.out)
tokenizer.save_pretrained(args.out)
write_json(args.out/'run.json',{'base':args.model,'seed':17,'steps':args.steps,'lr':2e-5,'losses':losses,'seconds':time.perf_counter()-start,'pairs':pairs,'warning':'4 public demonstration pairs; cannot establish generalization or tune on final test'})
print('reranker saved; evaluate on independent human-labelled queries through /rerank')
