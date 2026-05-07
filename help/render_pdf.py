"""One-time renderer that converts the bundled ZSB Portal PDF into page PNGs.

Run from the repo root:
    python -m help.render_pdf

The script is idempotent — re-running overwrites the PNGs in help/static/. If
the source PDF is updated, just run it again. The script fails loudly when
anything is missing so a broken render is impossible to ship.
"""

import os
import sys

import fitz  # pymupdf

EXPECTED_PAGES = 12
SCALE = 2  # 2x renders for retina displays

_HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE_PDF = os.path.join(_HERE, 'source', 'ZSB_Portal.pdf')
OUTPUT_DIR = os.path.join(_HERE, 'static')


def render() -> list[str]:
    if not os.path.isfile(SOURCE_PDF):
        raise FileNotFoundError(f"Source PDF not found at {SOURCE_PDF}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    doc = fitz.open(SOURCE_PDF)
    if doc.page_count < EXPECTED_PAGES:
        raise RuntimeError(
            f"PDF has {doc.page_count} pages, expected at least {EXPECTED_PAGES}"
        )

    matrix = fitz.Matrix(SCALE, SCALE)
    written = []
    for i in range(EXPECTED_PAGES):
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        out_path = os.path.join(OUTPUT_DIR, f"page_{i + 1:02d}.png")
        pix.save(out_path)
        written.append(out_path)
    doc.close()

    missing = [p for p in written if not os.path.isfile(p)]
    if missing:
        raise RuntimeError(f"Render claimed success but files missing: {missing}")

    expected = {os.path.join(OUTPUT_DIR, f"page_{i + 1:02d}.png") for i in range(EXPECTED_PAGES)}
    actually_present = {p for p in expected if os.path.isfile(p)}
    if actually_present != expected:
        raise RuntimeError(
            f"Missing PNGs after render: {sorted(expected - actually_present)}"
        )

    return written


if __name__ == '__main__':
    paths = render()
    for p in paths:
        print(f"wrote {p}")
    print(f"OK — {len(paths)} pages rendered to {OUTPUT_DIR}", file=sys.stderr)
