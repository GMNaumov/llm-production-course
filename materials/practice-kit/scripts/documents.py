"""Генератор синтетических входов и реальный baseline Tesseract/PDF."""

import argparse
import csv
import io
import re
import subprocess
import time

from common import WORK, edit_distance, percentile, read_json, write_json
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pypdf import PdfReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
PAGES = WORK / "documents"


def generate():
    PAGES.mkdir(exist_ok=True)
    font = ImageFont.truetype(FONT, 32)
    small = ImageFont.truetype(FONT, 20)
    rows = []
    for index in range(1, 5):
        # Семьи A/B — development, C/D — открытые примеры переноса, не независимый test.
        family = chr(64 + index)
        lines = [
            f"Спецификация TRN-{index:04d}",
            "Статус: approved" if index % 2 else "Статус: draft",
            "Позиция | Обозначение | Количество | Ед.",
            f"1 | ДЕТ-{index:02d} | {index * 2} | шт.",
            "Диаметр: 10±0,1 мм",
            f"Проект {family}, лист 1 из 2",
        ]
        for page in (1, 2):
            current = (
                lines
                if page == 1
                else [
                    f"Спецификация TRN-{index:04d}, продолжение",
                    "Позиция | Обозначение | Количество | Ед.",
                    f"2 | КРП-{index:02d} | 3 | шт.",
                    f"Проект {family}, лист 2 из 2",
                ]
            )
            picture = Image.new("RGB", (1400, 1000), "white")
            draw = ImageDraw.Draw(picture)
            for line_number, line in enumerate(current):
                draw.text((70, 70 + line_number * 100), line, font=font, fill="black")
            # Нарочно мелкая критичная подпись; сопоставить overview/crop.
            draw.text((900, 850), "Поз. 7: 5±0,02 мм", font=small, fill="black")
            variants = {
                "clean": picture,
                "rotated": picture.rotate(90, expand=True),
                "blur": picture.filter(ImageFilter.GaussianBlur(2)),
                "cropped": picture.crop((0, 0, 1100, 400)),
            }
            stamped = picture.copy()
            sd = ImageDraw.Draw(stamped)
            sd.ellipse((300, 330, 820, 520), outline="red", width=14)
            sd.text((320, 420), "ПРОВЕРЕНО / 7?", font=font, fill="red")
            sd.line((850, 500, 1150, 540, 900, 580), fill="blue", width=5)
            variants["stamp-notes"] = (
                stamped  # Рукописеподобный росчерк, не реальная рукопись.
            )
            for variant, image in variants.items():
                ident = f"{family}-p{page}-{variant}"
                image.save(PAGES / f"{ident}.png")
                rows.append(
                    {
                        "id": ident,
                        "family": family,
                        "page": page,
                        "variant": variant,
                        "reference": "\n".join(current) + "\nПоз. 7: 5±0,02 мм",
                        "file": f"{ident}.png",
                    }
                )
            picture.save(PAGES / f"{family}-p{page}-scan.pdf", "PDF", resolution=150)
        pdfmetrics.registerFont(TTFont("DejaVu", FONT))
        c = canvas.Canvas(str(PAGES / f"{family}-text.pdf"), pagesize=(700, 500))
        for page in (1, 2):
            c.setFont("DejaVu", 13)
            current = (
                lines
                if page == 1
                else [
                    f"Продолжение {family}",
                    "Позиция | Обозначение | Количество | Ед.",
                    f"2 | КРП-{index:02d} | 3 | шт.",
                ]
            )
            for n, line in enumerate(current):
                c.drawString(35, 450 - 40 * n, line)
            c.showPage()
        c.save()
    (PAGES / "broken.pdf").write_bytes(b"%PDF-1.4\nBROKEN")
    write_json(PAGES / "manifest.json", rows)
    return {"pages": len(rows), "families": 4, "directory": str(PAGES)}


def normalize(text):
    # Сохраняем знаки допуска, регистр и цифры; только пробельная нормализация.
    return " ".join(text.split())


def ocr(path):
    result = subprocess.run(
        ["tesseract", str(path), "stdout", "-l", "rus+eng", "--psm", "6", "tsv"],
        capture_output=True,
        text=True,
        timeout=25,
        check=True,
    )
    words = []
    for row in csv.DictReader(
        io.StringIO(result.stdout), delimiter="\t", quoting=csv.QUOTE_NONE
    ):
        if row["text"].strip():
            words.append(
                {
                    "text": row["text"],
                    "bbox_px": [
                        int(row[x]) for x in ["left", "top", "width", "height"]
                    ],
                    "confidence": float(row["conf"]),
                }
            )
    return words


def run():
    if not (PAGES / "manifest.json").exists():
        generate()
    results = []
    for row in read_json(PAGES / "manifest.json"):
        start = time.perf_counter()
        try:
            words = ocr(PAGES / row["file"])
            text = " ".join(w["text"] for w in words)
            ref = normalize(row["reference"])
            pred = normalize(text)
            result = {
                "state": "ok",
                "prediction": text,
                "words": words,
                "cer": edit_distance(ref, pred) / len(ref),
                "wer": edit_distance(ref.split(), pred.split()) / len(ref.split()),
            }
        except (OSError, subprocess.SubprocessError, ValueError):
            result = {
                "state": "dependency_error",
                "prediction": None,
                "cer": None,
                "wer": None,
            }
        results.append(
            {**row, **result, "latency_ms": 1000 * (time.perf_counter() - start)}
        )
    write_json(WORK / "ocr-results.json", results)
    text_pdf = PdfReader(PAGES / "A-text.pdf").pages[0].extract_text()
    scan_pdf = PdfReader(PAGES / "A-p1-scan.pdf").pages[0].extract_text()
    summary = {
        "observations": len(results),
        "p95_ms": percentile([r["latency_ms"] for r in results], 0.95),
        "text_pdf_chars": len(text_pdf),
        "scan_pdf_chars": len(scan_pdf),
        "by_variant": {},
    }
    for variant in sorted({r["variant"] for r in results}):
        subset = [r for r in results if r["variant"] == variant]
        valid = [r["cer"] for r in subset if r["cer"] is not None]
        summary["by_variant"][variant] = {
            "n": len(subset),
            "macro_cer": sum(valid) / len(valid) if valid else None,
            "failures": sum(r["state"] != "ok" for r in subset),
        }
    write_json(WORK / "ocr-summary.json", summary)
    return summary


def extract_status(text, document, revision, page):
    """Предметный парсер baseline; не приписываем ему способности LLM/OCR."""
    # Граница слова исключает ложное распознавание approvedX как approved.
    matches = re.findall(r"Статус:\s*(approved|draft)\b", text)
    values = set(matches)
    state = (
        "read" if len(values) == 1 else "conflict" if len(values) > 1 else "unreadable"
    )
    return {
        "state": state,
        "value": next(iter(values)) if state == "read" else None,
        "source": {"document": document, "revision": revision, "page": page}
        if state == "read"
        else None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["generate", "ocr"])
    args = parser.parse_args()
    print(generate() if args.action == "generate" else run())
