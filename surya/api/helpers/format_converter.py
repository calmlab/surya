"""Format conversion utilities for MinerU compatibility"""
from typing import List, Tuple
from surya.recognition.schema import OCRResult


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
