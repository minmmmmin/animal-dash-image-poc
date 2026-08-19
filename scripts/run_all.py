"""Run the full pipeline (preprocess + Gemini status) over every image in samples/.

Useful for smoke-testing all sample drawings at once, and doubles as a way to
start collecting the generation-time / success-rate record the project notes
ask for (生成時間・成功率・失敗例の記録). One failing image (e.g. a transient
Gemini 503) does not stop the rest from running.
"""

from __future__ import annotations

import time
from pathlib import Path

from dotenv import load_dotenv

from animal_dash_image_poc import pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = REPO_ROOT / "samples"
OUTPUT_DIR = REPO_ROOT / "output"
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def main() -> None:
    load_dotenv()

    images = sorted(p for p in SAMPLES_DIR.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if not images:
        print(f"no images found in {SAMPLES_DIR}")
        return

    results = []
    for image_path in images:
        name = image_path.stem
        t0 = time.time()
        try:
            pipeline.run_full_pipeline(str(image_path), str(OUTPUT_DIR / name))
            elapsed = time.time() - t0
            results.append((name, True, elapsed))
            print(f"[OK]   {name:<20} {elapsed:5.1f}s")
        except Exception as e:
            elapsed = time.time() - t0
            results.append((name, False, elapsed))
            print(f"[FAIL] {name:<20} {elapsed:5.1f}s  {e}")

    ok = sum(1 for _, success, _ in results if success)
    print(f"\n{ok}/{len(results)} succeeded")


if __name__ == "__main__":
    main()
