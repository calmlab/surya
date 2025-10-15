"""Page OCR endpoint - Direct OCR without layout detection"""
import os
import uuid
import traceback
from typing import List
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from PIL import Image

from surya.foundation import FoundationPredictor
from surya.detection import DetectionPredictor
from surya.recognition import RecognitionPredictor
from surya.api.config import settings
from surya.api.helpers.pdf_processor import (
    pdf_to_images,
    save_temp_file,
    cleanup_temp_file,
    is_pdf,
    is_image
)
from surya.api.helpers.format_converter import surya_ocr_to_page_format
from surya.logging import get_logger

logger = get_logger()

router = APIRouter()

# Global predictors (initialized on first use)
_foundation_predictor = None
_detection_predictor = None
_recognition_predictor = None


def get_predictors():
    """Get or initialize predictors (singleton pattern)"""
    global _foundation_predictor, _detection_predictor, _recognition_predictor

    if _foundation_predictor is None:
        logger.info("Initializing Surya predictors...")
        _foundation_predictor = FoundationPredictor()
        _detection_predictor = DetectionPredictor()  # Independent detector
        _recognition_predictor = RecognitionPredictor(_foundation_predictor)
        logger.info("Predictors initialized successfully")

    return _foundation_predictor, _detection_predictor, _recognition_predictor


@router.post("/page_ocr")
async def page_ocr(
    files: List[UploadFile] = File(...),
    lang: str = Form(settings.DEFAULT_LANG),
    start_page_id: int = Form(0),
    end_page_id: int = Form(99999),
):
    """
    Direct page OCR endpoint (no layout detection)

    Args:
        files: PDF or image files
        lang: OCR language (default: en)
        start_page_id: Start page index (0-based)
        end_page_id: End page index

    Returns:
        JSON response with OCR results in page format
    """
    temp_files = []

    try:
        logger.info(f"Processing {len(files)} file(s)")

        # Create unique temp directory
        unique_dir = os.path.join(settings.TEMP_DIR, str(uuid.uuid4()))
        os.makedirs(unique_dir, exist_ok=True)

        # Get predictors
        foundation_predictor, detection_predictor, recognition_predictor = get_predictors()

        # Process files
        all_results = []

        for file_idx, file in enumerate(files):
            logger.info(f"[File {file_idx + 1}/{len(files)}] Processing: {file.filename}")

            # Save uploaded file
            content = await file.read()
            temp_path = save_temp_file(content, file.filename, unique_dir)
            temp_files.append(temp_path)

            # Convert to images
            if is_pdf(file.filename):
                logger.info(f"  Converting PDF to images...")
                images, page_sizes = pdf_to_images(temp_path)
                logger.info(f"  Converted {len(images)} pages")
            elif is_image(file.filename):
                img = Image.open(temp_path)
                images = [img]
                page_sizes = [(img.width, img.height)]
                logger.info(f"  Loaded image: {img.size}")
            else:
                logger.error(f"  Unsupported file type: {file.filename}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "error": f"Unsupported file type: {file.filename}"
                    }
                )

            # Apply page range
            start_idx = max(0, start_page_id)
            end_idx = min(len(images), end_page_id + 1)
            images = images[start_idx:end_idx]
            page_sizes = page_sizes[start_idx:end_idx]
            logger.info(f"  Processing pages {start_idx} to {end_idx - 1} ({len(images)} pages)")

            # Run OCR (2-stage: Detection + Recognition)
            # Note: Surya doesn't use lang parameter, it's language-agnostic
            logger.info(f"  Running OCR on {len(images)} pages...")
            ocr_results = recognition_predictor(
                images,
                det_predictor=detection_predictor
            )
            logger.info(f"  OCR completed for {len(ocr_results)} pages")

            # Convert to output format
            logger.info(f"  Formatting results...")
            formatted_result = surya_ocr_to_page_format(
                ocr_results,
                file.filename,
                page_sizes
            )

            all_results.append(formatted_result)
            logger.info(f"  File processing completed: {file.filename}")

        # Cleanup temp files
        for temp_file in temp_files:
            cleanup_temp_file(temp_file)

        logger.info(f"All {len(files)} file(s) processed successfully")

        # Return first result (support for single file)
        if len(all_results) == 1:
            return JSONResponse(status_code=200, content=all_results[0])
        else:
            # Multiple files - combine results
            combined = {
                "status": "success",
                "backend": "surya",
                "files": [result["files"][0] for result in all_results]
            }
            return JSONResponse(status_code=200, content=combined)

    except Exception as e:
        # Log full error with stack trace
        logger.error(f"Error processing request: {str(e)}")
        logger.error(traceback.format_exc())

        # Cleanup on error
        for temp_file in temp_files:
            cleanup_temp_file(temp_file)

        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )
