#!/usr/bin/env python3
"""Extract card images from Cartas.pdf and board images from Tableros.pdf."""

import os
import fitz  # PyMuPDF

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARTAS_PDF = os.path.join(BASE_DIR, "Cartas.pdf")
TABLEROS_PDF = os.path.join(BASE_DIR, "Tableros.pdf")
OUTPUT_DIR = os.path.join(BASE_DIR, "static", "cards")
BOARDS_DIR = os.path.join(BASE_DIR, "static", "boards")

DPI = 300
SCALE = DPI / 72  # PDF points to pixels at target DPI

# Card regions in PDF points (origin = bottom-left in PDF, but PyMuPDF uses top-left)
# We'll define crops in top-left origin coordinates after rendering.
# Page size: 792 x 612 pts (landscape letter)
PAGE_W_PT = 792
PAGE_H_PT = 612

def pts_to_px(val):
    return int(val * SCALE)

def extract_cards():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    doc = fitz.open(CARTAS_PDF)
    
    # Render all pages at 300 DPI
    print(f"Rendering {len(doc)} pages from Cartas.pdf at {DPI} DPI...")
    
    # Card layout detection: render first page and analyze
    # Pages 1-10: Action Deck (fronts on odd pages 1,3,5,7,9; backs on even 2,4,6,8,10)
    # Pages 11-22: Competition Cards (fronts on odd; backs on even)
    # Each page has 4 cards in a 2x2 grid
    
    # We'll auto-detect card boundaries by looking at the page content
    # Based on analysis: cards are centered on the page with margins
    
    # Action Deck cards (pages 1-10): cards 1-20
    # Page 1 (front): cards 1,2,3,4 -> Page 2 (back): cards 1,2,3,4
    # Page 3 (front): cards 5,6,7,8 -> Page 4 (back): cards 5,6,7,8
    # etc.
    
    # Competition cards (pages 11-22):
    # Pages 11-12: Warm cards 1-4 (front/back)
    # Pages 13-14: Warm cards 5-8
    # Pages 15-16: Warm cards 9-12
    # Pages 17-18: Cool cards 1-4
    # Pages 19-20: Cool cards 5-8
    # Pages 21-22: Cool cards 9-12
    
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        # Render at high DPI
        mat = fitz.Matrix(SCALE, SCALE)
        pix = page.get_pixmap(matrix=mat)
        
        page_w = pix.width
        page_h = pix.height
        
        # Save full page for debugging
        # pix.save(os.path.join(OUTPUT_DIR, f"page_{page_idx+1}.png"))
        
        # Determine card positions by analyzing page content
        # Cards are in a 2x2 grid. We need to find approximate positions.
        # Based on analysis, the grid is roughly:
        # Top-left, Top-right, Bottom-left, Bottom-right
        
        # For a 2x2 grid on landscape letter, estimate card regions
        # Card size is approximately 65mm x 101mm = ~184pt x 286pt
        # But the PDF has them laid out in a specific arrangement
        
        # Let's use a general approach: divide page into quadrants with some margin
        # and crop each quadrant
        
        # Margins (in pts): ~100pt left/right, ~80pt top/bottom, ~20pt gap between cards
        # We'll define generous crop regions and let the cards fill them
        
        if page_idx < 10:
            # Action deck pages - slightly different layout
            # Based on detailed analysis:
            # Horizontal: cards roughly at x=[141-384] and x=[465-670] (pts, bottom-left origin)
            # Vertical: cards roughly at y=[156-300] and y=[329-484] (pts, bottom-left origin)
            # Convert to top-left origin: top_y = PAGE_H - bottom_y_max, bottom_y = PAGE_H - bottom_y_min
            
            regions_pt = [
                # (x_min, y_min_topleft, x_max, y_max_topleft) in PDF points, top-left origin
                (130, PAGE_H_PT - 490, 395, PAGE_H_PT - 320),   # Top-left card
                (410, PAGE_H_PT - 490, 675, PAGE_H_PT - 320),   # Top-right card
                (130, PAGE_H_PT - 310, 395, PAGE_H_PT - 140),   # Bottom-left card
                (410, PAGE_H_PT - 310, 675, PAGE_H_PT - 140),   # Bottom-right card
            ]
        else:
            # Competition card pages
            regions_pt = [
                (105, PAGE_H_PT - 495, 395, PAGE_H_PT - 300),   # Top-left
                (395, PAGE_H_PT - 495, 690, PAGE_H_PT - 300),   # Top-right
                (105, PAGE_H_PT - 300, 395, PAGE_H_PT - 115),   # Bottom-left
                (395, PAGE_H_PT - 300, 690, PAGE_H_PT - 115),   # Bottom-right
            ]
        
        # Convert to pixel coordinates
        regions_px = []
        for (x1, y1, x2, y2) in regions_pt:
            regions_px.append((
                max(0, pts_to_px(x1)),
                max(0, pts_to_px(y1)),
                min(page_w, pts_to_px(x2)),
                min(page_h, pts_to_px(y2)),
            ))
        
        # Determine card numbers and side (front/back)
        is_front = (page_idx % 2 == 0)
        side = "front" if is_front else "back"
        
        if page_idx < 10:
            # Action deck: pages 0-9
            sheet_num = page_idx // 2  # 0-4
            base_card = sheet_num * 4 + 1  # 1, 5, 9, 13, 17
            card_type = "action"
        elif page_idx < 16:
            # Warm competition: pages 10-15
            sheet_num = (page_idx - 10) // 2  # 0-2
            base_card = sheet_num * 4 + 1  # 1, 5, 9
            card_type = "warm"
        else:
            # Cool competition: pages 16-21
            sheet_num = (page_idx - 16) // 2  # 0-2
            base_card = sheet_num * 4 + 1  # 1, 5, 9
            card_type = "cool"
        
        card_numbers = [base_card, base_card + 1, base_card + 2, base_card + 3]
        
        # Card order on page: top-left=1, top-right=2, bottom-left=3, bottom-right=4
        for i, (x1, y1, x2, y2) in enumerate(regions_px):
            card_num = card_numbers[i]
            
            # Crop by creating a new pixmap from samples
            from PIL import Image
            import io
            
            # Convert full page pixmap to PIL Image, crop, save
            img_data = pix.tobytes("png")
            full_img = Image.open(io.BytesIO(img_data))
            cropped_img = full_img.crop((x1, y1, x2, y2))
            
            filename = f"{card_type}_{card_num:02d}_{side}.png"
            filepath = os.path.join(OUTPUT_DIR, filename)
            cropped_img.save(filepath, "PNG")
            
            print(f"  Extracted: {filename} ({cropped.width}x{cropped.height}px)")
    
    doc.close()
    print(f"\nDone! {len(os.listdir(OUTPUT_DIR))} card images saved to {OUTPUT_DIR}")


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
