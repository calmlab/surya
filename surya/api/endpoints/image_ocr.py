"""Image OCR endpoint - OCR for base64-encoded image list"""
import base64
import traceback
from io import BytesIO
from typing import List
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from PIL import Image

from surya.foundation import FoundationPredictor
from surya.detection import DetectionPredictor
from surya.recognition import RecognitionPredictor
from surya.api.config import settings
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
        _detection_predictor = DetectionPredictor()
        _recognition_predictor = RecognitionPredictor(_foundation_predictor)
        logger.info("Predictors initialized successfully")

    return _foundation_predictor, _detection_predictor, _recognition_predictor


class ImageData(BaseModel):
    """Single image data with base64 encoding"""
    image_data: str  # Base64 encoded image
    image_id: str    # Identifier for this image (e.g., "layout_box_0")


class ImageOCRRequest(BaseModel):
    """Request schema for /image_ocr endpoint"""
    images: List[ImageData]
    lang: str = settings.DEFAULT_LANG
    task_name: str = "ocr_with_boxes"  # ocr_with_boxes, ocr_without_boxes, block_without_boxes


class ImageOCRResult(BaseModel):
    """OCR result for a single image"""
    image_id: str
    text_lines: List[dict]  # Using dict for flexibility
    image_size: dict  # width, height


class ImageOCRResponse(BaseModel):
    """Response schema for /image_ocr endpoint"""
    status: str
    backend: str = "surya"
    results: List[ImageOCRResult]


@router.post("/image_ocr", response_model=ImageOCRResponse)
async def image_ocr(request: ImageOCRRequest):
    """
    OCR endpoint for base64-encoded image list

    This endpoint is designed for MinerU integration:
    - MinerU performs layout detection
    - MinerU crops layout boxes as images
    - MinerU sends image list to this endpoint
    - Surya performs OCR on each image
    - Returns OCR results preserving image_id for matching

    Args:
        request: ImageOCRRequest with list of base64-encoded images

    Returns:
        ImageOCRResponse with OCR results for each image
    """
    try:
        logger.info(f"Processing {len(request.images)} image(s) for OCR")

        # Get predictors
        foundation_predictor, detection_predictor, recognition_predictor = get_predictors()

        # Decode base64 images
        pil_images = []
        image_ids = []

        for idx, img_data in enumerate(request.images):
            try:
                # Decode base64
                image_bytes = base64.b64decode(img_data.image_data)
                img = Image.open(BytesIO(image_bytes))

                # Convert to RGB if needed
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                pil_images.append(img)
                image_ids.append(img_data.image_id)

                logger.info(f"  [{idx + 1}/{len(request.images)}] Decoded image {img_data.image_id}: {img.size}")

            except Exception as e:
                logger.error(f"  Failed to decode image {img_data.image_id}: {str(e)}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "error": f"Failed to decode image {img_data.image_id}: {str(e)}"
                    }
                )

        # Run OCR on all images (batch processing)
        logger.info(f"Running OCR on {len(pil_images)} images...")
        ocr_results = recognition_predictor(
            pil_images,
            det_predictor=detection_predictor
        )
        logger.info(f"OCR completed for {len(ocr_results)} images")

        # Format results
        results = []
        for image_id, ocr_result, img in zip(image_ids, ocr_results, pil_images):
            text_lines = []

            for line_id, text_line in enumerate(ocr_result.text_lines):
                # Extract characters (tokens) with valid bboxes
                characters = []
                for char_idx, char in enumerate(text_line.chars):
                    if char.bbox_valid:
                        characters.append({
                            "char": char.text,
                            "bbox": char.bbox,
                            "confidence": char.confidence,
                            "char_index": char_idx
                        })

                # Extract words if available
                words = []
                if text_line.words:
                    for word in text_line.words:
                        words.append({
                            "text": word.text,
                            "bbox": word.bbox,
                            "confidence": word.confidence
                        })

                text_lines.append({
                    "line_id": line_id,
                    "text": text_line.text,
                    "bbox": text_line.bbox,
                    "polygon": text_line.polygon,
                    "confidence": text_line.confidence,
                    "characters": characters,
                    "words": words
                })

            results.append(ImageOCRResult(
                image_id=image_id,
                text_lines=text_lines,
                image_size={"width": img.width, "height": img.height}
            ))

        logger.info(f"Successfully processed {len(results)} images")

        return ImageOCRResponse(
            status="success",
            backend="surya",
            results=results
        )

    except Exception as e:
        logger.error(f"Error processing image OCR request: {str(e)}")
        logger.error(traceback.format_exc())

        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )
