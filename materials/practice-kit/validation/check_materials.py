"""Структурная авторская проверка учебных файлов. Не читает сдаваемые работы."""
import ast
import re
from pathlib import Path
import sys
from urllib.parse import unquote

root=Path(sys.argv[1] if len(sys.argv)>1 else '/repo')
materials=root/'materials'
paths=[p for p in materials.rglob('*.md') if not any(x in p.parts for x in ['work','models','secrets','bundle'])]
errors=[]
links=0
for path in paths:
    text=path.read_text(encoding='utf-8-sig')
    if '\ufffd' in text: errors.append(str(path)+': replacement character')
    if len(re.findall(r'^```',text,re.M))%2: errors.append(str(path)+': code fences')
    for target in re.findall(r'\]\(([^)]+)\)',text):
        if target.startswith(('https://','http://','mailto:','#')): continue
        destination=target.split('#',1)[0].split(' "',1)[0].strip('<>')
        if destination:
            links+=1
            if not (path.parent/unquote(destination)).exists(): errors.append(str(path)+': missing '+target)
guides=sorted(materials.glob('modules/*/practice/p*-*.md'))
solutions=sorted(materials.glob('modules/*/solutions/p*-*.md'))
if len(guides)!=40 or len(solutions)!=40: errors.append('count != 40+40')
curriculum=(root/'curriculum.md').read_text(encoding='utf-8-sig')
hours=0
for path in guides:
    text=path.read_text(encoding='utf-8-sig')
    ident=re.search(r'^# (П\d+\.\d+)\.',text)[1]
    row=next(line for line in curriculum.splitlines() if line.startswith('- **'+ident+'.'))
    expected=int(re.search(r'\((\d+) ч\)',row)[1])
    actual=int(re.search(r'\*\*Объём:\*\* (\d+) ак\.',text)[1])
    hours+=actual
    if actual!=expected: errors.append(ident+': hours mismatch')
    if row.split('**Приёмка:**')[1].strip() not in text: errors.append(ident+': acceptance mismatch')
    solution=path.parent.parent/'solutions'/path.name
    if not solution.exists(): errors.append(ident+': no reference')
    timing=re.search(r'Подготовка — (\d+) мин; реализация/эксперимент — (\d+); негативные случаи — (\d+); анализ и оформление — (\d+)',text)
    if not timing or sum(map(int,timing.groups()))!=45*actual: errors.append(ident+': minutes mismatch')
if hours!=112: errors.append('practice sum !=112')
scripts=list((materials/'practice-kit/scripts').glob('*.py'))+list((materials/'practice-kit/validation').glob('*.py'))
for path in scripts:
    try: ast.parse(path.read_text(encoding='utf-8-sig'),filename=str(path))
    except SyntaxError as error: errors.append(str(error))
print({'markdown_files':len(paths),'local_links':links,'guides':len(guides),'references':len(solutions),'practice_hours':hours,'python_files':len(scripts),'errors':errors})
if errors: raise SystemExit(1)
