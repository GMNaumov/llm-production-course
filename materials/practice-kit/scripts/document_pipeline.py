"""Полный малый эталон OCR→поля/позиции→provenance→review-очередь.
Парсер ограничен явно сгенерированным шаблоном. Никогда не угадывает поле.
"""
import re
import math
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator
from common import WORK,read_json,write_json,checksum
from contracts import Source,StatusField,route
from documents import PAGES,extract_status


class QuantityField(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    state:Literal['read','missing','unreadable','conflict']
    value:float|None
    unit:Literal['шт.']|None
    source:Source|None

    @model_validator(mode='after')
    def evidence(self):
        if self.state=='read':
            if self.value is None or not math.isfinite(self.value) or self.value<0 or self.unit is None or self.source is None:
                raise ValueError('quantity evidence')
        elif self.value is not None or self.unit is not None:
            raise ValueError('unread quantity')
        return self


def bounding_box(words,image_size):
    if not words: return None
    width,height=image_size
    boxes=[w['bbox_px'] for w in words]
    return (min(b[0] for b in boxes)/width,min(b[1] for b in boxes)/height,
            max(b[0]+b[2] for b in boxes)/width,max(b[1]+b[3] for b in boxes)/height)


def extract(row):
    from PIL import Image
    text=row.get('prediction') or ''
    image=PAGES/row['file']
    width,height=Image.open(image).size
    # Source bbox = вся область распознанных слов: источник локализован грубо и требует review.
    box=bounding_box(row.get('words',[]),(width,height))
    source=Source(document=row['family'],revision='synthetic-1',page=row['page'],bbox=box)
    status=StatusField.model_validate(extract_status(text,row['family'],'synthetic-1',row['page']))
    if status.source:
        status.source=source
    positions=[]
    # Обозначение и позиция не выводятся из имени файла/эталона.
    for match in re.finditer(r'(\d+)\s*\|\s*([А-ЯA-Z]+-\d+)\s*\|\s*(\d+(?:[.,]\d+)?)\s*\|\s*(шт\.)',text):
        value=QuantityField(state='read',value=float(match[3].replace(',','.')),unit='шт.',source=source)
        positions.append({'position':int(match[1]),'designation':match[2],'quantity':value.model_dump()})
    reasons=[]
    if row['state']!='ok': reasons.append('dependency_error')
    if status.state!='read': reasons.append('status_'+status.state)
    if not positions: reasons.append('table_unreadable')
    reasons.append('source_and_critical_values_require_human_verification')
    # Нельзя автоматически принять только потому, что regex/schema совпали.
    return {'id':row['id'],'pipeline':'template-ocr-v1','original_sha256':checksum(image),'family':row['family'],
            'page':row['page'],'variant':row['variant'],'status':status.model_dump(),'positions':positions,
            'route':'review','reasons':reasons,'dimension':{'state':'unreadable','value':None,'reason':'dimension extraction not validated; inspect original'}}


if __name__=='__main__':
    rows=read_json(WORK/'ocr-results.json')
    results=[extract(row) for row in rows]
    write_json(WORK/'extracted-documents.json',results)
    # Очередь содержит ссылки/причины; эталонные ответы сюда не подмешиваются.
    queue=[{'id':r['id'],'image':str(PAGES/(r['id']+'.png')),'reasons':r['reasons'],'reviewer':None,'decision':None,'minutes':None} for r in results]
    write_json(WORK/'review-queue.json',queue)
    print({'documents':len(results),'review':len(queue),'automatic_acceptance':0,'note':'strict baseline; calibrate dev signals and verify source before enabling auto'})
