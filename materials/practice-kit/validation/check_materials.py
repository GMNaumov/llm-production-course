"""Структурная авторская проверка учебных файлов. Не читает сдаваемые работы."""

import ast
import re
import sys
from pathlib import Path
from urllib.parse import unquote

root = Path(sys.argv[1] if len(sys.argv) > 1 else "/repo")
materials = root / "materials"
paths = [
    p
    for p in materials.rglob("*.md")
    if not any(x in p.parts for x in ["work", "models", "secrets", "bundle"])
]
errors = []
links = 0
paths.extend(root / name for name in ("README.md", "AGENTS.md", "curriculum.md"))
python_blocks = 0
for path in paths:
    text = path.read_text(encoding="utf-8-sig")
    if "\ufffd" in text:
        errors.append(str(path) + ": replacement character")
    if len(re.findall(r"^```", text, re.M)) % 2:
        errors.append(str(path) + ": code fences")
    for block in re.findall(r"^```python\s*\n(.*?)^```", text, re.M | re.S):
        python_blocks += 1
        try:
            ast.parse(block, filename=str(path))
        except SyntaxError as error:
            errors.append(str(error))
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if target.startswith(("https://", "http://", "mailto:", "#")):
            continue
        destination = target.split("#", 1)[0].split(' "', 1)[0].strip("<>")
        if destination:
            links += 1
            if not (path.parent / unquote(destination)).exists():
                errors.append(str(path) + ": missing " + target)
guides = sorted(materials.glob("modules/*/practice/p*-*.md"))
solutions = sorted(materials.glob("modules/*/solutions/p*-*.md"))
if len(guides) != 40 or len(solutions) != 40:
    errors.append("count != 40+40")
curriculum = (root / "curriculum.md").read_text(encoding="utf-8-sig")
hours = 0
practice_by_module = {}
for path in guides:
    text = path.read_text(encoding="utf-8-sig")
    ident = re.search(r"^# (П\d+\.\d+)\.", text)[1]
    row = next(
        line
        for line in curriculum.splitlines()
        if line.startswith("- **" + ident + ".")
    )
    expected = int(re.search(r"\((\d+) ч\)", row)[1])
    actual = int(re.search(r"\*\*Объём:\*\* (\d+) ак\.", text)[1])
    hours += actual
    module_number = int(ident[1:].split(".")[0])
    practice_by_module[module_number] = (
        practice_by_module.get(module_number, 0) + actual
    )
    if actual != expected:
        errors.append(ident + ": hours mismatch")
    if row.split("**Приёмка:**")[1].strip() not in text:
        errors.append(ident + ": acceptance mismatch")
    solution = path.parent.parent / "solutions" / path.name
    if not solution.exists():
        errors.append(ident + ": no reference")
    timing = re.search(
        r"Подготовка — (\d+) мин; реализация/эксперимент — (\d+); негативные случаи — (\d+); анализ и оформление — (\d+)",
        text,
    )
    if not timing or sum(map(int, timing.groups())) != 45 * actual:
        errors.append(ident + ": minutes mismatch")
if hours != 112:
    errors.append("practice sum !=112")
# Сверяем каждую строку плана, а не только общий итог часов практики.
module_rows = re.findall(
    r"^\| (\d+) \| [^|]+ \| (\d+) \| (\d+) \| (\d+) \|$", curriculum, re.M
)
if len(module_rows) != 12:
    errors.append("module table !=12")
totals = [0, 0, 0]
for number, total, study, practice in module_rows:
    number, total, study, practice = map(int, (number, total, study, practice))
    if total != study + practice or practice_by_module.get(number) != practice:
        errors.append(f"module {number}: hours mismatch")
    directories = list(materials.glob(f"modules/{number:02d}-*"))
    if len(directories) != 1:
        errors.append(f"module {number}: directory mismatch")
        continue
    overview = (directories[0] / "README.md").read_text(encoding="utf-8-sig")
    if (
        f"**Объём:** {total} ак. ч.: {study} self-study и {practice} контактной"
        not in overview
    ):
        errors.append(f"module {number}: overview hours mismatch")
    theory = (directories[0] / "self-study.md").read_text(encoding="utf-8-sig")
    route = re.search(
        r"\*\*(\d+) академическ(?:их|ий) час(?:а|ов)? \((\d+) минут\)", theory
    )
    if not route or tuple(map(int, route.groups())) != (study, 45 * study):
        errors.append(f"module {number}: self-study route mismatch")
    route_line = next(
        (
            line
            for line in theory.splitlines()
            if line.startswith("**") and "минут" in line
        ),
        "",
    )
    if sum(map(int, re.findall(r"— (\d+)", route_line))) != 45 * study:
        errors.append(f"module {number}: self-study minutes mismatch")
    totals = [a + b for a, b in zip(totals, (total, study, practice))]
if totals != [150, 38, 112]:
    errors.append("module sums !=150/38/112")
scripts = list((materials / "practice-kit/scripts").glob("*.py")) + list(
    (materials / "practice-kit/validation").glob("*.py")
)
for path in scripts:
    try:
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    except SyntaxError as error:
        errors.append(str(error))
print(
    {
        "markdown_files": len(paths),
        "local_links": links,
        "guides": len(guides),
        "references": len(solutions),
        "practice_hours": hours,
        "python_files": len(scripts),
        "python_blocks": python_blocks,
        "errors": errors,
    }
)
if errors:
    raise SystemExit(1)
