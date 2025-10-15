"""
Character bbox fix helper module

This module provides functions to fix character-level bounding boxes
without modifying Surya's internal code.

The issue: surya/recognition/__init__.py uses clean_close_polygons() which
over-merges character bboxes, causing all characters in a line to have
identical bboxes.

The solution: Use the original predicted polygons directly, bypassing
the problematic merge logic.
"""
from typing import List
import numpy as np
from surya.recognition.schema import TextChar, TextLine


def fix_character_bboxes_in_lines(
    text_lines: List[TextLine],
    predicted_polygons_batch: List[np.ndarray]
) -> List[TextLine]:
    """
    Fix character bboxes using original model predictions

    This function takes the raw polygon predictions from the model
    and applies them to characters without the over-aggressive merging
    that happens in clean_close_polygons().

    Args:
        text_lines: List of TextLine objects from Surya OCR
        predicted_polygons_batch: Raw polygon predictions from foundation model
                                  Shape: (num_lines, max_tokens, 4, 2)

    Returns:
        List of TextLine objects with corrected character bboxes
    """
    fixed_lines = []

    for line_idx, text_line in enumerate(text_lines):
        if line_idx >= len(predicted_polygons_batch):
            # No polygon data for this line, keep original
            fixed_lines.append(text_line)
            continue

        polygons = predicted_polygons_batch[line_idx]
        fixed_chars = []
        polygon_idx = 0

        for char in text_line.chars:
            if char.bbox_valid and polygon_idx < len(polygons):
                # Use original polygon from model (not merged)
                char.polygon = polygons[polygon_idx].tolist()
                # Update bbox from polygon
                char.update_bbox_from_polygon()
                polygon_idx += 1

            fixed_chars.append(char)

        # Create new TextLine with fixed characters
        fixed_line = TextLine(
            text=text_line.text,
            confidence=text_line.confidence,
            polygon=text_line.polygon,
            bbox=text_line.bbox,
            chars=fixed_chars,
            words=text_line.words,
            original_text_good=text_line.original_text_good
        )
        fixed_lines.append(fixed_line)

    return fixed_lines


def apply_char_bbox_fix(ocr_results, predicted_polygons_batch):
    """
    Apply character bbox fix to OCR results

    Args:
        ocr_results: List of OCRResult objects from Surya
        predicted_polygons_batch: Raw predictions from model

    Returns:
        Fixed OCR results with corrected character bboxes
    """
    if not predicted_polygons_batch or len(predicted_polygons_batch) == 0:
        return ocr_results

    fixed_results = []

    for result_idx, ocr_result in enumerate(ocr_results):
        # Get polygons for this result
        if result_idx < len(predicted_polygons_batch):
            result_polygons = predicted_polygons_batch[result_idx]
        else:
            result_polygons = []

        # Fix character bboxes in all text lines
        fixed_lines = fix_character_bboxes_in_lines(
            ocr_result.text_lines,
            result_polygons
        )

        # Create new OCRResult with fixed lines
        from surya.recognition.schema import OCRResult
        fixed_result = OCRResult(
            text_lines=fixed_lines,
            image_bbox=ocr_result.image_bbox
        )
        fixed_results.append(fixed_result)

    return fixed_results
