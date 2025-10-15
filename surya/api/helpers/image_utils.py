"""Image processing utilities"""
from typing import List, Tuple
from PIL import Image
import numpy as np
from surya.layout.schema import LayoutBox


def crop_layout_box(image: Image.Image, layout_box: LayoutBox, padding: int = 0) -> Image.Image:
    """
    Crop a layout box region from an image

    Args:
        image: Source PIL Image
        layout_box: LayoutBox with bbox coordinates
        padding: Additional padding around the box (pixels)

    Returns:
        Cropped PIL Image
    """
    # Get bbox coordinates
    bbox = layout_box.bbox
    x1, y1, x2, y2 = bbox

    # Apply padding
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(image.width, x2 + padding)
    y2 = min(image.height, y2 + padding)

    # Crop image
    cropped = image.crop((x1, y1, x2, y2))
    return cropped


def crop_layout_boxes(
    image: Image.Image,
    layout_boxes: List[LayoutBox],
    padding: int = 0
) -> List[Tuple[Image.Image, LayoutBox]]:
    """
    Crop multiple layout boxes from an image

    Args:
        image: Source PIL Image
        layout_boxes: List of LayoutBox objects
        padding: Additional padding around each box (pixels)

    Returns:
        List of (cropped_image, layout_box) tuples
    """
    results = []
    for layout_box in layout_boxes:
        cropped = crop_layout_box(image, layout_box, padding)
        results.append((cropped, layout_box))

    return results


def polygon_to_bbox(polygon: List[List[float]]) -> List[float]:
    """
    Convert polygon coordinates to bounding box [x1, y1, x2, y2]

    Args:
        polygon: List of [x, y] points

    Returns:
        Bounding box [x1, y1, x2, y2]
    """
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]

    x1 = min(xs)
    y1 = min(ys)
    x2 = max(xs)
    y2 = max(ys)

    return [x1, y1, x2, y2]


def bbox_to_polygon(bbox: List[float]) -> List[List[float]]:
    """
    Convert bounding box to polygon (4 corners)

    Args:
        bbox: [x1, y1, x2, y2]

    Returns:
        List of [x, y] corner points (clockwise from top-left)
    """
    x1, y1, x2, y2 = bbox
    return [
        [x1, y1],  # top-left
        [x2, y1],  # top-right
        [x2, y2],  # bottom-right
        [x1, y2],  # bottom-left
    ]


def adjust_bbox_to_image_coordinates(
    bbox: List[float],
    crop_offset: Tuple[int, int]
) -> List[float]:
    """
    Adjust bbox coordinates from cropped image to original image coordinates

    Args:
        bbox: Bounding box in cropped image coordinates [x1, y1, x2, y2]
        crop_offset: (x_offset, y_offset) of the crop in original image

    Returns:
        Bounding box in original image coordinates
    """
    x_offset, y_offset = crop_offset
    x1, y1, x2, y2 = bbox

    return [
        x1 + x_offset,
        y1 + y_offset,
        x2 + x_offset,
        y2 + y_offset
    ]


def adjust_polygon_to_image_coordinates(
    polygon: List[List[float]],
    crop_offset: Tuple[int, int]
) -> List[List[float]]:
    """
    Adjust polygon coordinates from cropped image to original image coordinates

    Args:
        polygon: Polygon in cropped image coordinates
        crop_offset: (x_offset, y_offset) of the crop in original image

    Returns:
        Polygon in original image coordinates
    """
    x_offset, y_offset = crop_offset
    adjusted = []

    for point in polygon:
        adjusted.append([
            point[0] + x_offset,
            point[1] + y_offset
        ])

    return adjusted
