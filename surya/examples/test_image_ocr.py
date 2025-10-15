#!/usr/bin/env python3
"""
Simple test client for /image_ocr endpoint

This tests the MinerU integration scenario where layout boxes are sent as base64 images.

Usage:
    python surya/examples/test_image_ocr.py <image_file1> [image_file2 ...]
    python surya/examples/test_image_ocr.py temp/box1.png temp/box2.png
    python surya/examples/test_image_ocr.py temp/*.png --lang ko
"""
import argparse
import json
import os
import sys
import base64
import requests
from pathlib import Path
from typing import List


def encode_image_to_base64(image_path: str) -> str:
    """
    Encode image file to base64 string

    Args:
        image_path: Path to image file

    Returns:
        Base64 encoded string
    """
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def test_image_ocr(
    image_paths: List[str],
    server_url: str = "http://localhost:8001",
    lang: str = "en",
    task_name: str = "ocr_with_boxes",
    output_file: str = None
):
    """
    Test /image_ocr endpoint

    Args:
        image_paths: List of image file paths
        server_url: API server URL
        lang: OCR language
        task_name: Task name (ocr_with_boxes, ocr_without_boxes, block_without_boxes)
        output_file: Optional output JSON file path
    """
    # Validate files
    for image_path in image_paths:
        if not os.path.exists(image_path):
            print(f"❌ Error: File not found: {image_path}")
            return False

    url = f"{server_url}/image_ocr"

    print(f"🖼️  Testing /image_ocr endpoint")
    print(f"   Images: {len(image_paths)} files")
    print(f"   Server: {url}")
    print(f"   Language: {lang}")
    print(f"   Task: {task_name}")
    print()

    try:
        # Encode images to base64
        print("📦 Encoding images to base64...")
        images_data = []
        total_size = 0

        for idx, image_path in enumerate(image_paths):
            file_size = os.path.getsize(image_path)
            total_size += file_size
            file_size_kb = file_size / 1024

            print(f"   [{idx + 1}/{len(image_paths)}] {Path(image_path).name} ({file_size_kb:.1f} KB)")

            base64_data = encode_image_to_base64(image_path)
            images_data.append({
                "image_data": base64_data,
                "image_id": f"layout_box_{idx}"
            })

        total_size_mb = total_size / (1024 * 1024)
        print(f"   Total size: {total_size_mb:.2f} MB")
        print()

        # Prepare request
        request_data = {
            "images": images_data,
            "lang": lang,
            "task_name": task_name
        }

        # Send request
        print("⏳ Sending request...")
        print("🔄 Processing on server (this may take a while)...")
        print("   - Decoding base64 images")
        print("   - Running text detection")
        print("   - Running OCR recognition")
        print()

        import time
        start_time = time.time()
        response = requests.post(url, json=request_data, timeout=300)
        elapsed = time.time() - start_time
        print(f"⏱️  Server processing time: {elapsed:.1f}s")
        print()

        # Check response
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success!")
            print()

            # Print summary
            if result.get('status') == 'success':
                results = result.get('results', [])

                print(f"📊 Summary:")
                print(f"   Backend: {result.get('backend')}")
                print(f"   Total images processed: {len(results)}")
                print()

                # Process each image result
                for idx, img_result in enumerate(results):
                    image_id = img_result.get('image_id')
                    text_lines = img_result.get('text_lines', [])
                    image_size = img_result.get('image_size', {})

                    print(f"📖 Image {idx + 1} ({image_id}):")
                    print(f"   Image size: {image_size.get('width')} x {image_size.get('height')}")
                    print(f"   Text lines: {len(text_lines)}")

                    # Sample text lines
                    if text_lines:
                        print(f"   Sample lines (first 3):")
                        for i, line in enumerate(text_lines[:3]):
                            text = line.get('text', '')
                            confidence = line.get('confidence', 0)
                            char_count = len(line.get('characters', []))
                            print(f"      Line {i}: \"{text}\" (conf: {confidence:.3f}, chars: {char_count})")

                        # Character bbox check for first line
                        first_line = text_lines[0]
                        chars = first_line.get('characters', [])
                        if chars:
                            print(f"   Character bbox check (first line, first 3 chars):")
                            for char in chars[:3]:
                                char_text = char.get('char')
                                bbox = char.get('bbox')
                                conf = char.get('confidence', 0)
                                print(f"      '{char_text}': bbox={bbox}, conf={conf:.3f}")

                    print()

            # Save to file
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"💾 Result saved to: {output_file}")
            else:
                # Auto-generate output filename
                output_file = "image_ocr_result.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"💾 Result saved to: {output_file}")

            return True

        else:
            print(f"❌ Error: Server returned {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('error', 'Unknown error')}")

                # Print traceback if available
                if 'traceback' in error_data:
                    print()
                    print("📋 Server Traceback:")
                    print(error_data['traceback'])
            except:
                print(f"   Message: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print()
        print(f"❌ Connection Error: Cannot connect to server at {server_url}")
        print()
        print("💡 Troubleshooting:")
        print("   1. Make sure the server is running:")
        print(f"      python surya/scripts/run_api.py --host 0.0.0.0 --port 8001")
        print(f"   2. Check if the server is accessible:")
        print(f"      curl {server_url}/health")
        print()
        return False
    except requests.exceptions.Timeout:
        print()
        print(f"❌ Timeout Error: Request took longer than 300 seconds")
        print()
        print("💡 Suggestions:")
        print("   - Try processing fewer images")
        print("   - Check server logs for processing status")
        print()
        return False
    except Exception as e:
        print()
        print(f"❌ Unexpected Error: {e}")
        print()
        print("📋 Full traceback:")
        import traceback
        traceback.print_exc()
        print()
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Test /image_ocr endpoint (MinerU integration scenario)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage - single image
  python surya/examples/test_image_ocr.py temp/box1.png

  # Multiple images
  python surya/examples/test_image_ocr.py temp/box1.png temp/box2.png temp/box3.png

  # Using wildcards (bash will expand)
  python surya/examples/test_image_ocr.py temp/*.png

  # Korean OCR
  python surya/examples/test_image_ocr.py temp/*.png --lang ko

  # Custom server
  python surya/examples/test_image_ocr.py temp/*.png --server http://192.168.1.100:8001

  # Save to specific output file
  python surya/examples/test_image_ocr.py temp/*.png --output result.json

Note:
  This endpoint is designed for MinerU integration where layout detection
  is done by MinerU, and cropped layout box images are sent to Surya for OCR.
        """
    )

    parser.add_argument('image_paths', nargs='+', help='Path(s) to image file(s)')
    parser.add_argument('--server', default='http://localhost:8001', help='Server URL')
    parser.add_argument('--lang', default='en', help='OCR language (default: en)')
    parser.add_argument('--task', default='ocr_with_boxes',
                       choices=['ocr_with_boxes', 'ocr_without_boxes', 'block_without_boxes'],
                       help='Task name (default: ocr_with_boxes)')
    parser.add_argument('--output', help='Output JSON file path')

    args = parser.parse_args()

    success = test_image_ocr(
        args.image_paths,
        args.server,
        args.lang,
        args.task,
        args.output
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
