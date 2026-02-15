#!/usr/bin/env python3
"""Extract card images from Cartas.pdf and board images from Tableros.pdf.

Card detection strategy:
  Each PDF page has 4 cards in a 2x2 grid, delimited by gray border lines.
  We render at 300 DPI (page = 2550×3300 px) and detect the gray grid lines
  by scanning rows/columns for the border color (~RGB 183,178,173).

  Detected grid (consistent across all 22 pages at 300 DPI):
    Horizontal borders: y=457,  y=1649-1650,  y=2842
    Vertical borders:   x=507,  x=1274-1275,  x=2042

  This gives four card cells. We crop just inside the border (1 px inset)
  so the cards have clean edges without the shared gray divider line.
"""

import os
import io
import fitz  # PyMuPDF
from PIL import Image
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARTAS_PDF = os.path.join(BASE_DIR, "Cartas.pdf")
TABLEROS_PDF = os.path.join(BASE_DIR, "Tableros.pdf")
OUTPUT_DIR = os.path.join(BASE_DIR, "static", "cards")
BOARDS_DIR = os.path.join(BASE_DIR, "static", "boards")

DPI = 300
SCALE = DPI / 72  # PDF points → pixels


# ---------------------------------------------------------------------------
# Gray-border detection helpers
# ---------------------------------------------------------------------------


def _detect_grid(arr):
    """Detect the 3 horizontal and 3 vertical gray border lines in a rendered page.

    The border lines are thin (1-2 px) but span almost the full width (for
    horizontal lines) or full height (for vertical lines) of the page.
    Interior card-content gray areas are thicker but only span within one card
    (~30% of the page width).  Using a 50% threshold cleanly separates them.

    Returns (h_lines, v_lines) where each is a list of (start, end) tuples.
    Falls back to known positions if detection fails.
    """
    h, w = arr.shape[:2]
    r, g, b = (
        arr[:, :, 0].astype(int),
        arr[:, :, 1].astype(int),
        arr[:, :, 2].astype(int),
    )

    # Gray border pixels: channels close together, mid-range brightness
    gray_mask = (np.abs(r - g) < 20) & (np.abs(g - b) < 20) & (r > 150) & (r < 220)

    row_count = gray_mask.sum(axis=1)
    col_count = gray_mask.sum(axis=0)

    # Use a high threshold: border lines span ~60% of page width and ~72% of
    # page height.  Card-content gray areas only span ~30%.
    # Setting threshold at 50% catches only true border lines.
    h_threshold = w * 0.50
    v_threshold = h * 0.50

    def _group(indices, min_gap=10):
        if len(indices) == 0:
            return []
        groups = []
        start = prev = int(indices[0])
        for idx in indices[1:]:
            idx = int(idx)
            if idx - prev > min_gap:
                groups.append((start, prev))
                start = idx
            prev = idx
        groups.append((start, prev))
        return groups

    h_lines = _group(np.where(row_count > h_threshold)[0])
    v_lines = _group(np.where(col_count > v_threshold)[0])

    # We expect exactly 3 lines in each direction.
    # If detection gives a different count, use known fallback positions.
    FALLBACK_H = [(457, 457), (1649, 1650), (2842, 2842)]
    FALLBACK_V = [(507, 507), (1274, 1275), (2042, 2042)]

    if len(h_lines) != 3:
        h_lines = FALLBACK_H
    if len(v_lines) != 3:
        v_lines = FALLBACK_V

    return h_lines, v_lines


def _card_regions_from_grid(h_lines, v_lines):
    """Given 3 horizontal and 3 vertical border line groups, return 4 card crop rects.

    Each rect is (left, top, right, bottom) in PIL crop convention (right/bottom exclusive).
    We crop 1 px inside the border so the shared divider line is excluded.
    """
    if len(h_lines) < 3 or len(v_lines) < 3:
        raise ValueError(f"Expected 3 border lines, got H={h_lines} V={v_lines}")

    # Unpack border line boundaries
    top_border_start, top_border_end = h_lines[0]
    mid_h_start, mid_h_end = h_lines[1]
    bot_border_start, bot_border_end = h_lines[2]

    left_border_start, left_border_end = v_lines[0]
    mid_v_start, mid_v_end = v_lines[1]
    right_border_start, right_border_end = v_lines[2]

    # Include the outer border, split at the midpoint of mid-lines
    # Top-left card:        from outer top-left to just before mid dividers
    # Top-right card:       from just after mid-v to outer right, top to mid-h
    # Bottom-left card:     from outer left, just after mid-h to outer bottom
    # Bottom-right card:    from just after mid-v, just after mid-h to outer bot-right

    regions = [
        # Top-left
        (left_border_start, top_border_start, mid_v_start, mid_h_start),
        # Top-right
        (mid_v_end + 1, top_border_start, right_border_end + 1, mid_h_start),
        # Bottom-left
        (left_border_start, mid_h_end + 1, mid_v_start, bot_border_end + 1),
        # Bottom-right
        (mid_v_end + 1, mid_h_end + 1, right_border_end + 1, bot_border_end + 1),
    ]
    return regions


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------


def extract_cards():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    doc = fitz.open(CARTAS_PDF)

    print(f"Rendering {len(doc)} pages from Cartas.pdf at {DPI} DPI …")
    print("Detecting gray borders per page and cropping cards.\n")

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        mat = fitz.Matrix(SCALE, SCALE)
        pix = page.get_pixmap(matrix=mat)

        # Convert to PIL / numpy
        img_data = pix.tobytes("png")
        full_img = Image.open(io.BytesIO(img_data)).convert("RGB")
        arr = np.array(full_img)

        # Detect grid
        h_lines, v_lines = _detect_grid(arr)

        # Compute crop regions
        regions = _card_regions_from_grid(h_lines, v_lines)

        # Card numbering
        is_front = page_idx % 2 == 0
        side = "front" if is_front else "back"

        if page_idx < 10:
            card_type = "action"
            sheet_num = page_idx // 2
            base_card = sheet_num * 4 + 1
        elif page_idx < 16:
            card_type = "warm"
            sheet_num = (page_idx - 10) // 2
            base_card = sheet_num * 4 + 1
        else:
            card_type = "cool"
            sheet_num = (page_idx - 16) // 2
            base_card = sheet_num * 4 + 1

        card_numbers = [base_card, base_card + 1, base_card + 2, base_card + 3]

        for i, (x1, y1, x2, y2) in enumerate(regions):
            card_num = card_numbers[i]
            cropped = full_img.crop((x1, y1, x2, y2))

            filename = f"{card_type}_{card_num:02d}_{side}.png"
            filepath = os.path.join(OUTPUT_DIR, filename)
            cropped.save(filepath, "PNG")

            print(
                f"  Page {page_idx+1:2d} → {filename}  ({cropped.width}×{cropped.height})"
            )

    doc.close()
    n = len([f for f in os.listdir(OUTPUT_DIR) if f.endswith(".png")])
    print(f"\nDone! {n} card images saved to {OUTPUT_DIR}")


def extract_boards():
    os.makedirs(BOARDS_DIR, exist_ok=True)
    doc = fitz.open(TABLEROS_PDF)

    print(f"\nRendering {len(doc)} pages from Tableros.pdf at {DPI} DPI...")

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        mat = fitz.Matrix(SCALE, SCALE)
        pix = page.get_pixmap(matrix=mat)

        names = ["inventory_mat_1", "inventory_mat_2", "track_mat"]
        filename = f"{names[page_idx]}.png"
        filepath = os.path.join(BOARDS_DIR, filename)
        pix.save(filepath)
        print(f"  Saved: {filename} ({pix.width}x{pix.height}px)")

    doc.close()


if __name__ == "__main__":
    extract_cards()
    extract_boards()
    print("\nAll extractions complete!")
