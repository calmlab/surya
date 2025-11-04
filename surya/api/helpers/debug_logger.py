"""Debug logging utilities for development troubleshooting"""
import os
from datetime import datetime
from typing import List, Optional
from pathlib import Path
from surya.recognition.schema import TextLine
from surya.layout.schema import LayoutBox
from surya.api.config import settings
from surya.logging import get_logger

logger = get_logger()


class PageDebugLogger:
    """Helper class to write detailed per-page debug logs"""

    def __init__(self, request_id: str, filename: str):
        """
        Initialize debug logger for a request

        Args:
            request_id: Unique request identifier (e.g., UUID)
            filename: Original filename being processed
        """
        self.enabled = settings.DEBUG_LOG_ENABLED
        self.request_id = request_id
        self.filename = filename
        self.log_dir = None

        if self.enabled:
            # Create log directory: DEBUG_LOG_DIR/filename_timestamp_requestid/
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
            dir_name = f"{safe_filename}_{timestamp}_{request_id[:8]}"
            self.log_dir = Path(settings.DEBUG_LOG_DIR) / dir_name
            self.log_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[DEBUG] Created debug log directory: {self.log_dir}")

    def log_page_processing(
        self,
        page_idx: int,
        layout_boxes: List[LayoutBox],
        text_lines: List[TextLine],
        matched_lines: dict,
        page_size: tuple
    ):
        """
        Write detailed debug log for a single page

        Args:
            page_idx: Page index
            layout_boxes: List of detected layout boxes
            text_lines: List of OCR text lines
            matched_lines: Dictionary of {box_idx: [text_lines]}
            page_size: (width, height) tuple
        """
        if not self.enabled:
            return

        log_file = self.log_dir / f"page_{page_idx:05d}.log"

        with open(log_file, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write(f"DEBUG LOG: Page {page_idx}\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Request ID: {self.request_id}\n")
            f.write(f"Filename: {self.filename}\n")
            f.write(f"Page Size: {page_size[0]}x{page_size[1]}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n\n")

            # Section 1: Layout Detection Summary
            f.write("-" * 80 + "\n")
            f.write("1. LAYOUT DETECTION SUMMARY\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total Layout Boxes: {len(layout_boxes)}\n\n")

            for box_idx, layout_box in enumerate(layout_boxes):
                f.write(f"  Box #{box_idx}:\n")
                f.write(f"    Label: {layout_box.label}\n")
                f.write(f"    BBox: {layout_box.bbox}\n")
                f.write(f"    Confidence: {layout_box.confidence:.4f}\n")
                f.write(f"    Position: {layout_box.position}\n")
                # Calculate box area
                w = layout_box.bbox[2] - layout_box.bbox[0]
                h = layout_box.bbox[3] - layout_box.bbox[1]
                f.write(f"    Area: {w:.1f} x {h:.1f} = {w*h:.0f}\n\n")

            # Section 2: OCR Text Lines Summary
            f.write("-" * 80 + "\n")
            f.write("2. OCR TEXT LINES SUMMARY\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total Text Lines: {len(text_lines)}\n\n")

            for line_idx, text_line in enumerate(text_lines):
                f.write(f"  Line #{line_idx}:\n")
                f.write(f"    Text: {text_line.text}\n")
                f.write(f"    BBox: {text_line.bbox}\n")
                f.write(f"    Confidence: {text_line.confidence:.4f}\n")
                # Calculate center point
                x_center = (text_line.bbox[0] + text_line.bbox[2]) / 2.0
                y_center = (text_line.bbox[1] + text_line.bbox[3]) / 2.0
                f.write(f"    Center: ({x_center:.1f}, {y_center:.1f})\n")
                f.write(f"    Chars: {len(text_line.chars)}\n\n")

            # Section 3: Matching Results
            f.write("-" * 80 + "\n")
            f.write("3. TEXTLINE-TO-LAYOUTBOX MATCHING RESULTS\n")
            f.write("-" * 80 + "\n\n")

            # Count total matched and orphan lines
            total_matched = sum(len(lines) for idx, lines in matched_lines.items() if idx != -1)
            orphan_count = len(matched_lines.get(-1, []))

            f.write(f"Summary:\n")
            f.write(f"  Total Text Lines: {len(text_lines)}\n")
            f.write(f"  Matched to Boxes: {total_matched}\n")
            f.write(f"  Orphan Lines: {orphan_count}\n\n")

            # Detail matching per box
            for box_idx in sorted(matched_lines.keys()):
                if box_idx == -1:
                    continue  # Handle orphans separately

                lines = matched_lines[box_idx]
                f.write(f"  Box #{box_idx} ({layout_boxes[box_idx].label}): {len(lines)} lines\n")

                if lines:
                    for line in lines:
                        f.write(f"    - \"{line.text[:50]}...\"\n" if len(line.text) > 50 else f"    - \"{line.text}\"\n")
                else:
                    f.write(f"    (no lines matched)\n")
                f.write("\n")

            # Orphan lines detail
            if orphan_count > 0:
                f.write(f"  ORPHAN LINES (not matched to any box): {orphan_count}\n")
                for line in matched_lines[-1]:
                    x_center = (line.bbox[0] + line.bbox[2]) / 2.0
                    y_center = (line.bbox[1] + line.bbox[3]) / 2.0
                    f.write(f"    - Center: ({x_center:.1f}, {y_center:.1f})\n")
                    f.write(f"      Text: \"{line.text[:60]}...\"\n" if len(line.text) > 60 else f"      Text: \"{line.text}\"\n")
                    f.write(f"      BBox: {line.bbox}\n\n")

            # Section 4: Potential Issues
            f.write("-" * 80 + "\n")
            f.write("4. POTENTIAL ISSUES\n")
            f.write("-" * 80 + "\n\n")

            issues = []

            # Check for boxes with no lines
            empty_boxes = [idx for idx, lines in matched_lines.items() if idx != -1 and len(lines) == 0]
            if empty_boxes:
                issues.append(f"Empty boxes (no lines matched): {len(empty_boxes)} boxes")
                for box_idx in empty_boxes:
                    issues.append(f"  - Box #{box_idx} ({layout_boxes[box_idx].label}): {layout_boxes[box_idx].bbox}")

            # Check for high orphan ratio
            if len(text_lines) > 0:
                orphan_ratio = orphan_count / len(text_lines)
                if orphan_ratio > 0.3:
                    issues.append(f"High orphan ratio: {orphan_ratio*100:.1f}% of lines are orphans")

            # Check if no layout boxes detected
            if len(layout_boxes) == 0:
                issues.append("WARNING: No layout boxes detected on this page!")

            if issues:
                for issue in issues:
                    f.write(f"  - {issue}\n")
            else:
                f.write("  No obvious issues detected.\n")

            f.write("\n" + "=" * 80 + "\n")
            f.write("END OF DEBUG LOG\n")
            f.write("=" * 80 + "\n")

        logger.info(f"[DEBUG] Wrote debug log for page {page_idx}: {log_file}")

    def log_summary(self, total_pages: int, total_errors: int = 0):
        """
        Write summary log for the entire request

        Args:
            total_pages: Total number of pages processed
            total_errors: Number of pages with errors
        """
        if not self.enabled:
            return

        summary_file = self.log_dir / "summary.log"

        with open(summary_file, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("REQUEST PROCESSING SUMMARY\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Request ID: {self.request_id}\n")
            f.write(f"Filename: {self.filename}\n")
            f.write(f"Total Pages: {total_pages}\n")
            f.write(f"Errors: {total_errors}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n\n")

            f.write(f"Debug log directory: {self.log_dir}\n")
            f.write(f"Page logs: page_00000.log ~ page_{total_pages-1:05d}.log\n\n")

            f.write("=" * 80 + "\n")

        logger.info(f"[DEBUG] Wrote summary log: {summary_file}")
