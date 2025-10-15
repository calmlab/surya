"""Format conversion utilities for MinerU compatibility"""
from typing import List, Tuple, Dict, Any
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
    box_ocr_results: List[List[OCRResult]],
    filename: str,
    page_sizes: List[Tuple[int, int]],
    include_discarded: bool = False
) -> dict:
    """
    Convert Surya Layout + OCR results to MinerU format

    Args:
        layout_results: List of LayoutResult (one per page)
        box_ocr_results: List of List of OCRResult (page -> layout_box -> OCR result)
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

    for page_idx, (layout_result, page_box_ocrs, page_size) in enumerate(
        zip(layout_results, box_ocr_results, page_sizes)
    ):
        page_data = {
            "page_index": page_idx,
            "page_size": {"width": page_size[0], "height": page_size[1]},
            "layout_boxes": []
        }

        discarded_boxes = []

        # Process each layout box
        for box_id, (layout_box, ocr_result) in enumerate(
            zip(layout_result.bboxes, page_box_ocrs)
        ):
            # Map Surya label to MinerU box_type
            box_type = map_surya_label_to_box_type(layout_box.label)

            # Format OCR lines for this box
            lines = []
            for line_id, text_line in enumerate(ocr_result.text_lines):
                # Extract characters
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

                lines.append({
                    "line_index": line_id,
                    "bbox": text_line.bbox,
                    "text": text_line.text,
                    "confidence": text_line.confidence,
                    "spans": spans
                })

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
                discarded_boxes.append(layout_box_data)
            else:
                page_data["layout_boxes"].append(layout_box_data)

        # Add discarded boxes if requested
        if include_discarded:
            page_data["discarded_boxes"] = discarded_boxes

        result["files"][0]["pages"].append(page_data)

    return result
