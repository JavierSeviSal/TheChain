#!/usr/bin/env python3
"""Analyze a PDF page to detect gray card borders."""

import os
import sys
import fitz
from PIL import Image
import io
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARTAS_PDF = os.path.join(BASE_DIR, "Cartas.pdf")
DPI = 300
SCALE = DPI / 72

doc = fitz.open(CARTAS_PDF)

# Analyze pages 0 (action front), 10 (warm front), 16 (cool front)
for page_idx in [0, 1, 10, 11, 16, 17]:
    page = doc[page_idx]
    mat = fitz.Matrix(SCALE, SCALE)
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_data)).convert("RGB")
    arr = np.array(img)
    
    print(f"\n=== Page {page_idx + 1} ({pix.width}x{pix.height}px) ===")
    print(f"  Page size in pts: {page.rect.width} x {page.rect.height}")
    
    # Look for gray pixels. Gray = R≈G≈B, not white, not black
    # Typical gray border would be ~128-200 range
    r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
    
    # Find pixels that are gray: similar R,G,B values, in mid-range
    gray_mask = (
        (np.abs(r.astype(int) - g.astype(int)) < 15) & 
        (np.abs(g.astype(int) - b.astype(int)) < 15) & 
        (np.abs(r.astype(int) - b.astype(int)) < 15) &
        (r > 80) & (r < 220) &
        (g > 80) & (g < 220)
    )
    
    # Find rows and columns with significant gray content
    # (the border lines should show up as rows/columns with many gray pixels)
    row_gray_count = gray_mask.sum(axis=1)
    col_gray_count = gray_mask.sum(axis=0)
    
    # A border line would have a long run of gray on one row or column
    # Look for rows where >30% of pixels are gray
    h, w = arr.shape[:2]
    threshold_col = w * 0.15  # At least 15% of width is gray
    threshold_row = h * 0.15
    
    prominent_rows = np.where(row_gray_count > threshold_col)[0]
    prominent_cols = np.where(col_gray_count > threshold_row)[0]
    
    print(f"  Gray pixel total: {gray_mask.sum()}")
    print(f"  Prominent gray rows (>15% width): count={len(prominent_rows)}")
    if len(prominent_rows) > 0:
        # Find contiguous groups of prominent rows
        groups = []
        start = prominent_rows[0]
        prev = prominent_rows[0]
        for r_idx in prominent_rows[1:]:
            if r_idx - prev > 3:
                groups.append((start, prev))
                start = r_idx
            prev = r_idx
        groups.append((start, prev))
        print(f"  Row groups: {groups}")
    
    print(f"  Prominent gray cols (>15% height): count={len(prominent_cols)}")
    if len(prominent_cols) > 0:
        groups = []
        start = prominent_cols[0]
        prev = prominent_cols[0]
        for c_idx in prominent_cols[1:]:
            if c_idx - prev > 3:
                groups.append((start, prev))
                start = c_idx
            prev = c_idx
        groups.append((start, prev))
        print(f"  Col groups: {groups}")

    # Also let's look at specific gray values to identify the border color
    gray_pixels = arr[gray_mask]
    if len(gray_pixels) > 0:
        avg_gray = gray_pixels.mean(axis=0)
        print(f"  Average gray pixel RGB: ({avg_gray[0]:.0f}, {avg_gray[1]:.0f}, {avg_gray[2]:.0f})")
        
        # Look at most common gray value
        gray_vals = gray_pixels[:, 0]  # R channel is representative
        unique, counts = np.unique(gray_vals, return_counts=True)
        top5_idx = counts.argsort()[-5:][::-1]
        print(f"  Top gray R values: {[(int(unique[i]), int(counts[i])) for i in top5_idx]}")

doc.close()
