"""Маленький полностью синтетический набор для механики SFT, не доказательство качества."""
import json
from common import WORK,write_json

output=WORK/'training-data'
output.mkdir(exist_ok=True)
templates={
 'train': [('t1','Карточка проекта {n}. Статус: draft.','draft'),('t2','Спецификация {n}. Статус: approved.','approved'),('t3','Документ {n}. Статус не указан.','unknown')],
 'dev': [('v1','Проект №{n} находится в состоянии draft.','draft'),('v2','В карточке №{n} явно написано: approved.','approved'),('v3','В файле №{n} есть подпись. Статус отсутствует.','unknown')]
}
system='Верни JSON с единственным полем status: draft, approved или unknown. Классифицируй только по тексту.'
for split,groups in templates.items():
    rows=[]
    for group,text,label in groups:
        for n in range(1,7 if split=='train' else 3):
            rows.append({'id':f'{group}-{n}','group':group,'split':split,'synthetic':True,'source':'course-template-v1','license':'course-original-synthetic','expert_review':'required-before-course','messages':[{'role':'system','content':system},{'role':'user','content':text.format(n=n)},{'role':'assistant','content':json.dumps({'status':label})}]})
    (output/f'{split}.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
write_json(output/'README.json',{'train_groups':['t1','t2','t3'],'dev_groups':['v1','v2','v3'],'test':'must be supplied and locked independently; none is secretly generated here','warning':'paraphrase families may remain correlated; inspect near duplicates manually'})
print('18 train, 6 dev; независимый test организуется отдельно')
