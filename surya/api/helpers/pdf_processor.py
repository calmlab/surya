"""PDF processing utilities"""
import os
from pathlib import Path
from typing import List, Tuple
from PIL import Image
import pypdfium2 as pdfium


def pdf_to_images(pdf_path: str, dpi: int = 200) -> Tuple[List[Image.Image], List[Tuple[int, int]]]:
    """
    Convert PDF pages to images

    Args:
        pdf_path: Path to PDF file
        dpi: Resolution for rendering (default: 200)

    Returns:
        Tuple of (images, page_sizes)
        - images: List of PIL Image objects
        - page_sizes: List of (width, height) tuples
    """
    pdf = pdfium.PdfDocument(pdf_path)
    images = []
    page_sizes = []

    for page_idx in range(len(pdf)):
        page = pdf[page_idx]

        # Render page to image
        bitmap = page.render(scale=dpi/72)
        pil_image = bitmap.to_pil()

        images.append(pil_image)
        page_sizes.append((pil_image.width, pil_image.height))

    pdf.close()
    return images, page_sizes


def save_temp_file(content: bytes, filename: str, temp_dir: str = "./temp") -> str:
    """
    Save uploaded file to temporary directory

    Args:
        content: File content bytes
        filename: Original filename
        temp_dir: Temporary directory path

    Returns:
        Path to saved file
    """
    os.makedirs(temp_dir, exist_ok=True)

    temp_path = os.path.join(temp_dir, filename)
    with open(temp_path, "wb") as f:
        f.write(content)

    return temp_path


def cleanup_temp_file(file_path: str):
    """Remove temporary file"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Warning: Failed to cleanup {file_path}: {e}")


def get_file_extension(filename: str) -> str:
    """Get file extension in lowercase"""
    return Path(filename).suffix.lower()


def is_pdf(filename: str) -> bool:
    """Check if file is PDF"""
    return get_file_extension(filename) == ".pdf"


def is_image(filename: str) -> bool:
    """Check if file is image"""
    image_extensions = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}
    return get_file_extension(filename) in image_extensions
