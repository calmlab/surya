"""Layout OCR endpoint - Layout detection + OCR integration"""
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
from surya.layout import LayoutPredictor
from surya.api.config import settings
from surya.api.helpers.pdf_processor import (
    pdf_to_images,
    save_temp_file,
    cleanup_temp_file,
    is_pdf,
    is_image
)
from surya.api.helpers.format_converter import surya_layout_ocr_to_mineru_format
from surya.logging import get_logger

logger = get_logger()

router = APIRouter()

# Global predictors (initialized on first use)
_foundation_predictor = None
_detection_predictor = None
_recognition_predictor = None
_layout_predictor = None


def get_predictors():
    """Get or initialize predictors (singleton pattern)"""
    global _foundation_predictor, _detection_predictor, _recognition_predictor, _layout_predictor

    if _foundation_predictor is None:
        logger.info("Initializing Surya predictors...")
        _foundation_predictor = FoundationPredictor()
        _detection_predictor = DetectionPredictor()
        _recognition_predictor = RecognitionPredictor(_foundation_predictor)
        _layout_predictor = LayoutPredictor(_foundation_predictor)
        logger.info("Predictors initialized successfully")

    return _foundation_predictor, _detection_predictor, _recognition_predictor, _layout_predictor


def process_images_with_layout_ocr(
    images: List[Image.Image],
    page_sizes: List[tuple],
    filename: str,
    include_discarded: bool,
    foundation_predictor,
    detection_predictor,
    recognition_predictor,
    layout_predictor
):
    """
    Common logic for processing images with layout detection + OCR (Plan 1)

    This implementation uses page-level OCR and matches TextLines to LayoutBoxes,
    rather than cropping each box and running OCR separately.

    Args:
        images: List of PIL images
        page_sizes: List of (width, height) tuples
        filename: Original filename for result
        include_discarded: Include discarded boxes
        predictors: All required predictors

    Returns:
        Formatted result in MinerU format
    """
    # Step 1: Run layout detection
    logger.info(f"  Running layout detection on {len(images)} pages...")
    layout_results = layout_predictor(images)
    logger.info(f"  Layout detection completed for {len(layout_results)} pages")

    # Step 2: Run page-level OCR (once per page)
    logger.info(f"  Running page-level OCR on {len(images)} pages...")
    page_ocr_results = recognition_predictor(
        images,
        det_predictor=detection_predictor
    )
    logger.info(f"  Page-level OCR completed for {len(page_ocr_results)} pages")

    # Log summary for each page
    for page_idx, (layout_result, ocr_result) in enumerate(zip(layout_results, page_ocr_results)):
        logger.info(
            f"    [Page {page_idx + 1}/{len(images)}] "
            f"Found {len(layout_result.bboxes)} layout boxes, "
            f"{len(ocr_result.text_lines)} text lines"
        )

    # Step 3: Convert to MinerU format (TextLine matching happens in format_converter)
    logger.info(f"  Formatting results to MinerU format...")
    formatted_result = surya_layout_ocr_to_mineru_format(
        layout_results,
        page_ocr_results,
        filename,
        page_sizes,
        include_discarded
    )

    return formatted_result


@router.post("/layout_ocr_images")
async def layout_ocr_images(
    images: List[UploadFile] = File(...),
    lang: str = Form(settings.DEFAULT_LANG),
    parse_method: str = Form("auto"),
    include_discarded: bool = Form(False),
):
    """
    Layout detection + OCR for page images (without PDF conversion)

    This endpoint performs:
    1. Layout detection on each page image
    2. Crops each layout box as separate image
    3. Runs OCR on each cropped box
    4. Returns results in MinerU-compatible format

    This is optimized for clients that want to process specific pages
    without sending the entire PDF multiple times.

    Args:
        images: List of image files (one per page)
        lang: OCR language (default: en, note: Surya is language-agnostic)
        parse_method: auto/ocr/txt (for MinerU compatibility, currently unused)
        include_discarded: Include discarded boxes (PageHeader, PageFooter)

    Returns:
        JSON response with layout + OCR results in MinerU format
    """
    temp_files = []

    try:
        logger.info(f"Processing {len(images)} page image(s) with layout detection + OCR")

        # Create unique temp directory
        unique_dir = os.path.join(settings.TEMP_DIR, str(uuid.uuid4()))
        os.makedirs(unique_dir, exist_ok=True)

        # Get predictors
        foundation_predictor, detection_predictor, recognition_predictor, layout_predictor = get_predictors()

        # Load all images
        pil_images = []
        page_sizes = []

        for idx, image_file in enumerate(images):
            logger.info(f"[Image {idx + 1}/{len(images)}] Loading: {image_file.filename}")

            # Validate image file
            if not is_image(image_file.filename):
                logger.error(f"  Not an image file: {image_file.filename}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "error": f"Not an image file: {image_file.filename}"
                    }
                )

            # Save and load image
            content = await image_file.read()
            temp_path = save_temp_file(content, image_file.filename, unique_dir)
            temp_files.append(temp_path)

            img = Image.open(temp_path)
            pil_images.append(img)
            page_sizes.append((img.width, img.height))
            logger.info(f"  Loaded image: {img.size}")

        # Process images with layout detection + OCR
        formatted_result = process_images_with_layout_ocr(
            pil_images,
            page_sizes,
            "images",  # Generic filename
            include_discarded,
            foundation_predictor,
            detection_predictor,
            recognition_predictor,
            layout_predictor
        )

        # Cleanup temp files
        for temp_file in temp_files:
            cleanup_temp_file(temp_file)

        logger.info(f"All {len(images)} image(s) processed successfully")

        return JSONResponse(status_code=200, content=formatted_result)

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


@router.post("/layout_ocr")
async def layout_ocr(
    files: List[UploadFile] = File(...),
    lang: str = Form(settings.DEFAULT_LANG),
    parse_method: str = Form("auto"),
    include_discarded: bool = Form(False),
    start_page_id: int = Form(0),
    end_page_id: int = Form(99999),
):
    """
    Layout detection + OCR integration endpoint

    This endpoint performs:
    1. Layout detection on each page
    2. Crops each layout box as separate image
    3. Runs OCR on each cropped box
    4. Returns results in MinerU-compatible format

    Args:
        files: PDF or image files
        lang: OCR language (default: en, note: Surya is language-agnostic)
        parse_method: auto/ocr/txt (for MinerU compatibility, currently unused)
        include_discarded: Include discarded boxes (PageHeader, PageFooter)
        start_page_id: Start page index (0-based)
        end_page_id: End page index

    Returns:
        JSON response with layout + OCR results in MinerU format
    """
    temp_files = []

    try:
        logger.info(f"Processing {len(files)} file(s) with layout detection + OCR")

        # Create unique temp directory
        unique_dir = os.path.join(settings.TEMP_DIR, str(uuid.uuid4()))
        os.makedirs(unique_dir, exist_ok=True)

        # Get predictors
        foundation_predictor, detection_predictor, recognition_predictor, layout_predictor = get_predictors()

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

            # Process images with layout detection + OCR
            formatted_result = process_images_with_layout_ocr(
                images,
                page_sizes,
                file.filename,
                include_discarded,
                foundation_predictor,
                detection_predictor,
                recognition_predictor,
                layout_predictor
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
