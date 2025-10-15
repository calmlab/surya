"""API response schemas"""
from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class APIResponse(BaseModel):
    """Base API response"""
    status: str
    message: Optional[str] = None


class ErrorResponse(APIResponse):
    """Error response"""
    status: str = "error"
    error: str


class SuccessResponse(APIResponse):
    """Success response with data"""
    status: str = "success"
    backend: str = "surya"
    version: str
    files: List[Dict[str, Any]]
