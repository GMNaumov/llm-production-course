import argparse
import time
from pathlib import Path

import torch
from common import WORK, write_json
from PIL import Image
from transformers import AutoModelForImageTextToText, AutoProcessor

parser = argparse.ArgumentParser()
parser.add_argument("--model", default="/models/vlm")
parser.add_argument("--image", type=Path, default=WORK / "documents/A-p1-clean.png")
args = parser.parse_args()
torch.set_num_threads(2)
device = "cuda" if torch.cuda.is_available() else "cpu"
processor = AutoProcessor.from_pretrained(
    args.model, local_files_only=True, trust_remote_code=False
)
model = (
    AutoModelForImageTextToText.from_pretrained(
        args.model,
        local_files_only=True,
        trust_remote_code=False,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
    )
    .to(device)
    .eval()
)
original = Image.open(args.image).convert("RGB")
crop = (850, 800, 1350, 980)
views = {
    "overview": original.resize((700, 500)),
    "original": original,
    "crop": original.crop(crop),
}
results = []
for name, picture in views.items():
    prompt = "Read the nominal diameter, tolerance, unit and position from the image. If unreadable say unreadable. Do not guess."
    messages = [
        {
            "role": "user",
            "content": [{"type": "image"}, {"type": "text", "text": prompt}],
        }
    ]
    text = processor.apply_chat_template(messages, add_generation_prompt=True)
    inputs = processor(text=text, images=[picture], return_tensors="pt").to(device)
    start = time.perf_counter()
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=96, do_sample=False)
    response = processor.batch_decode(
        output[:, inputs["input_ids"].shape[1] :], skip_special_tokens=True
    )[0]
    results.append(
        {
            "view": name,
            "image": args.image.name,
            "size": picture.size,
            "crop_original_px": crop if name == "crop" else None,
            "answer": response,
            "latency_ms": 1000 * (time.perf_counter() - start),
            "peak_allocated_bytes": torch.cuda.max_memory_allocated()
            if device == "cuda"
            else None,
            "review": "required: no automatic acceptance of dimensions",
        }
    )
write_json(WORK / "vlm-results.json", results)
print(results)
