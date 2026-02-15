#!/usr/bin/env python3
"""
Analyze each page to find the precise gray border rectangles around cards.
Scan for gray lines and determine exact card bounding boxes.
"""

import os
import fitz
from PIL import Image
import io
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARTAS_PDF = os.path.join(BASE_DIR, "Cartas.pdf")
DPI = 300
SCALE = DPI / 72

doc = fitz.open(CARTAS_PDF)

# The gray border color is approximately RGB(183, 178, 173) based on prior analysis
# We'll detect it more precisely per-page

for page_idx in range(len(doc)):
    page = doc[page_idx]
    mat = fitz.Matrix(SCALE, SCALE)
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_data)).convert("RGB")
    arr = np.array(img)
    h, w = arr.shape[:2]

    r, g, b = (
        arr[:, :, 0].astype(int),
        arr[:, :, 1].astype(int),
        arr[:, :, 2].astype(int),
    )

    # Detect the specific gray border color: look for consistent gray lines
    # The border is a thin line (1-2px) that spans most of the page width/height
    # Gray criteria: channels close together, in range ~160-210
    gray_mask = (np.abs(r - g) < 20) & (np.abs(g - b) < 20) & (r > 150) & (r < 220)

    # For horizontal border detection: count gray pixels per row
    # A border row should have a long continuous run of gray pixels
    row_gray = gray_mask.sum(axis=1)

    # For vertical border detection: count gray pixels per column
    col_gray = gray_mask.sum(axis=0)

    # Border lines span at least 25% of the page dimension
    h_threshold = w * 0.25
    v_threshold = h * 0.25

    h_lines = np.where(row_gray > h_threshold)[0]
    v_lines = np.where(col_gray > v_threshold)[0]

    # Group consecutive pixels into line positions (center of each group)
    def group_lines(indices, min_gap=10):
        if len(indices) == 0:
            return []
        groups = []
        start = indices[0]
        prev = indices[0]
        for idx in indices[1:]:
            if idx - prev > min_gap:
                groups.append((int(start), int(prev)))
                start = idx
            prev = idx
        groups.append((int(start), int(prev)))
        return groups

    h_groups = group_lines(h_lines)
    v_groups = group_lines(v_lines)

    print(f"Page {page_idx+1:2d}: H-borders={h_groups}  V-borders={v_groups}")

doc.close()
