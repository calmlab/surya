"""Main FastAPI application"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from surya.api.config import settings
from surya.api.endpoints import page_ocr

# Create FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOW_ORIGINS,
    allow_credentials=settings.ALLOW_CREDENTIALS,
    allow_methods=settings.ALLOW_METHODS,
    allow_headers=settings.ALLOW_HEADERS,
)

# Add GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include routers
app.include_router(page_ocr.router, tags=["OCR"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Surya OCR API",
        "version": settings.API_VERSION,
        "docs": "/docs",
        "endpoints": {
            "page_ocr": "/page_ocr - Direct page OCR without layout detection",
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}
