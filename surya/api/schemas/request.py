"""API request schemas"""
from pydantic import BaseModel, Field
from typing import List, Optional


class PageOCRRequest(BaseModel):
    """Request schema for /page_ocr endpoint"""
    lang: str = Field(default="en", description="OCR language (en, ch, ja, ko, etc.)")
    start_page_id: int = Field(default=0, description="Start page index (0-based)")
    end_page_id: int = Field(default=99999, description="End page index")


class ImageOCRRequest(BaseModel):
    """Request schema for /image_ocr endpoint"""
    images: List[dict] = Field(..., description="List of image data with IDs")
    lang: str = Field(default="en", description="OCR language")
    task_name: str = Field(default="ocr_with_boxes", description="Task name for OCR")


class LayoutOCRRequest(BaseModel):
    """Request schema for /layout_ocr endpoint"""
    lang: str = Field(default="en", description="OCR language")
    parse_method: str = Field(default="auto", description="Parse method (auto/ocr/txt)")
    include_discarded: bool = Field(default=False, description="Include discarded blocks")
    start_page_id: int = Field(default=0, description="Start page index")
    end_page_id: int = Field(default=99999, description="End page index")
