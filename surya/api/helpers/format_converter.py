"""Format conversion utilities for MinerU compatibility"""
from typing import List, Tuple, Dict, Any, Optional
from surya.recognition.schema import OCRResult, TextLine
from surya.layout.schema import LayoutResult, LayoutBox


# Surya label to MinerU box_type mapping
LABEL_TO_BOX_TYPE = {
    "Text": "text",
    "SectionHeader": "title",
    "Table": "table",
    "Picture": "image",
    "Figure": "image",
    "Equation": "interline_equation",
    "Caption": "caption",
    "Footnote": "footnote",
    "PageHeader": "discarded",
    "PageFooter": "discarded",
    "ListItem": "text",
    "TableOfContents": "text",
    "Form": "text",
    "Code": "text",
}


def map_surya_label_to_box_type(label: str) -> str:
    """
    Map Surya layout label to MinerU box_type

    Args:
        label: Surya layout label (e.g., "Text", "SectionHeader")

    Returns:
        MinerU box_type (e.g., "text", "title")
    """
    return LABEL_TO_BOX_TYPE.get(label, "text")


def surya_ocr_to_page_format(
    ocr_results: List[OCRResult],
    filename: str,
    page_sizes: List[Tuple[int, int]]
) -> dict:
    """
    Convert Surya OCR results to page format (layout-free)

    Args:
        ocr_results: List of Surya OCRResult objects
        filename: Source filename
        page_sizes: List of (width, height) tuples for each page

    Returns:
        Formatted JSON response compatible with MinerU format
    """
    result = {
        "status": "success",
        "backend": "surya",
        "files": [{
            "filename": filename,
            "pages": []
        }]
    }

    for page_idx, (ocr_result, page_size) in enumerate(zip(ocr_results, page_sizes)):
        page_data = {
            "page_index": page_idx,
            "page_size": {"width": page_size[0], "height": page_size[1]},
            "text_lines": []
        }

        for line_id, text_line in enumerate(ocr_result.text_lines):
            # Extract characters (actually tokens) with valid bboxes
            characters = []
            for char_idx, char in enumerate(text_line.chars):
                if char.bbox_valid:
                    char_data = {
                        "char": char.text,
                        "bbox": char.bbox,
                        "confidence": char.confidence,
                        "char_index": char_idx
                    }
                    characters.append(char_data)

            # Extract words if available
            words = []
            if text_line.words:
                for word in text_line.words:
                    words.append({
                        "text": word.text,
                        "bbox": word.bbox,
                        "confidence": word.confidence
                    })

            line_data = {
                "line_id": line_id,
                "bbox": text_line.bbox,
                "polygon": text_line.polygon,
                "text": text_line.text,
                "confidence": text_line.confidence,
                "characters": characters,
                "words": words
            }

            page_data["text_lines"].append(line_data)

        result["files"][0]["pages"].append(page_data)

    return result


def surya_layout_ocr_to_mineru_format(
    layout_results: List[LayoutResult],
    page_ocr_results: List[OCRResult],
    filename: str,
    page_sizes: List[Tuple[int, int]],
    include_discarded: bool = False
) -> dict:
    """
    Convert Surya Layout + OCR results to MinerU format (Plan 1)

    This implementation uses page-level OCR and matches TextLines to LayoutBoxes
    based on center point containment, rather than cropping and OCRing each box.

    Args:
        layout_results: List of LayoutResult (one per page)
        page_ocr_results: List of OCRResult (page-level OCR, one per page)
        filename: Source filename
        page_sizes: List of (width, height) tuples for each page
        include_discarded: Whether to include discarded boxes (PageHeader, PageFooter)

    Returns:
        MinerU-compatible JSON structure
    """
    result = {
        "status": "success",
        "backend": "surya",
        "files": [{
            "filename": filename,
            "pages": []
        }]
    }

    for page_idx, (layout_result, page_ocr, page_size) in enumerate(
        zip(layout_results, page_ocr_results, page_sizes)
    ):
        page_data = {
            "page_index": page_idx,
            "page_size": {"width": page_size[0], "height": page_size[1]},
            "layout_boxes": []
        }

        discarded_boxes = []

        # Step 1: Match TextLines to LayoutBoxes based on center point
        matched_lines = match_textlines_to_layout_boxes(
            page_ocr.text_lines,
            layout_result.bboxes
        )

        # Step 2: Handle orphan TextLines (if any)
        orphan_lines = matched_lines.get(-1, [])
        layout_boxes = list(layout_result.bboxes)  # Copy to allow modification

        if orphan_lines:
            # Create virtual orphan box
            orphan_box = create_orphan_layout_box(orphan_lines, page_idx)
            if orphan_box:
                # Add orphan box to layout boxes
                orphan_box_idx = len(layout_boxes)
                layout_boxes.append(orphan_box)
                # Add orphan lines to matched_lines
                matched_lines[orphan_box_idx] = orphan_lines

        # Step 3: Process each layout box (including orphan box if created)
        for box_id, layout_box in enumerate(layout_boxes):
            # Map Surya label to MinerU box_type
            box_type = map_surya_label_to_box_type(layout_box.label)

            # Get TextLines matched to this box
            box_text_lines = matched_lines.get(box_id, [])

            # Convert TextLines to MinerU lines format
            lines = format_textlines_to_mineru_lines(box_text_lines)

            # Create layout box data
            layout_box_data = {
                "box_id": box_id,
                "box_type": box_type,
                "bbox": layout_box.bbox,
                "score": layout_box.confidence,
                "position": layout_box.position,
                "lines": lines
            }

            # Separate discarded boxes
            if box_type == "discarded":
                if include_discarded:
                    discarded_boxes.append(layout_box_data)
            else:
                page_data["layout_boxes"].append(layout_box_data)

        # Add discarded boxes if requested
        if include_discarded and discarded_boxes:
            page_data["discarded_boxes"] = discarded_boxes

        result["files"][0]["pages"].append(page_data)

    return result


# ============================================================================
# Plan 1 Helper Functions: TextLine ↔ LayoutBox Matching
# ============================================================================

def point_in_bbox(x: float, y: float, bbox: List[float]) -> bool:
    """
    Check if point (x, y) is inside bbox [x0, y0, x1, y1]

    Args:
        x: X coordinate of point
        y: Y coordinate of point
        bbox: Bounding box [x0, y0, x1, y1]

    Returns:
        True if point is inside bbox, False otherwise
    """
    return bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]


def match_textlines_to_layout_boxes(
    text_lines: List[TextLine],
    layout_boxes: List[LayoutBox]
) -> Dict[int, List[TextLine]]:
    """
    Match TextLines to LayoutBoxes based on center point containment

    Algorithm:
    - Calculate center point of each TextLine bbox
    - Check if center point is inside any LayoutBox
    - Assign TextLine to first matching LayoutBox
    - TextLines not matching any box are assigned to index -1 (orphans)

    Args:
        text_lines: List of TextLine from page-level OCR
        layout_boxes: List of LayoutBox from layout detection

    Returns:
        Dictionary mapping {box_index: [matched_textlines]}
        box_index = -1 for orphan TextLines (not contained in any box)
    """
    # Initialize matched lines dict
    matched_lines = {i: [] for i in range(len(layout_boxes))}
    matched_lines[-1] = []  # Orphan lines

    for text_line in text_lines:
        # Calculate TextLine bbox center point
        x_center = (text_line.bbox[0] + text_line.bbox[2]) / 2.0
        y_center = (text_line.bbox[1] + text_line.bbox[3]) / 2.0

        # Find LayoutBox containing this center point
        matched = False
        for box_idx, layout_box in enumerate(layout_boxes):
            if point_in_bbox(x_center, y_center, layout_box.bbox):
                matched_lines[box_idx].append(text_line)
                matched = True
                break  # Assign to first matching box only

        # Orphan line (not in any box)
        if not matched:
            matched_lines[-1].append(text_line)

    return matched_lines


def create_orphan_layout_box(
    orphan_lines: List[TextLine],
    page_idx: int
) -> Optional[LayoutBox]:
    """
    Create a virtual LayoutBox to contain orphan TextLines

    Orphan TextLines are those whose center point doesn't fall within
    any detected LayoutBox. This function creates a virtual box to
    contain them.

    Args:
        orphan_lines: List of orphan TextLines
        page_idx: Page index (for logging/debugging)

    Returns:
        Virtual LayoutBox containing all orphan lines, or None if no orphans
    """
    if not orphan_lines:
        return None

    # Calculate bounding box covering all orphan lines
    min_x = min(line.bbox[0] for line in orphan_lines)
    min_y = min(line.bbox[1] for line in orphan_lines)
    max_x = max(line.bbox[2] for line in orphan_lines)
    max_y = max(line.bbox[3] for line in orphan_lines)

    # Create virtual LayoutBox
    orphan_box = LayoutBox(
        label="Text",  # Treat orphans as generic text
        bbox=[min_x, min_y, max_x, max_y],
        polygon=[[min_x, min_y], [max_x, min_y],
                 [max_x, max_y], [min_x, max_y]],
        confidence=0.0,  # Mark as virtual box with 0 confidence
        position=999999  # Place at end of reading order
    )

    return orphan_box


def format_textlines_to_mineru_lines(text_lines: List[TextLine]) -> List[dict]:
    """
    Convert list of TextLine objects to MinerU lines format

    This extracts the logic from surya_layout_ocr_to_mineru_format()
    to make it reusable for Plan 1 implementation.

    Args:
        text_lines: List of TextLine objects

    Returns:
        List of line dictionaries in MinerU format
    """
    lines = []

    for line_id, text_line in enumerate(text_lines):
        # Extract characters (actually tokens) with valid bboxes
        characters = []
        for char_idx, char in enumerate(text_line.chars):
            if char.bbox_valid:
                characters.append({
                    "char": char.text,
                    "bbox": char.bbox,
                    "confidence": char.confidence,
                    "char_index": char_idx
                })

        # Create spans (MinerU format uses spans)
        spans = [{
            "type": "text",
            "bbox": text_line.bbox,
            "content": text_line.text,
            "confidence": text_line.confidence,
            "characters": characters
        }]

        # Create line data
        line_data = {
            "line_index": line_id,
            "bbox": text_line.bbox,
            "text": text_line.text,
            "confidence": text_line.confidence,
            "spans": spans
        }

        lines.append(line_data)

    return lines
