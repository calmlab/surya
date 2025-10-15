#!/usr/bin/env python3
"""
Simple test client for /layout_ocr endpoint

Usage:
    python surya/examples/test_layout_ocr.py <pdf_file>
    python surya/examples/test_layout_ocr.py temp/doc_240924_9776.pdf
    python surya/examples/test_layout_ocr.py temp/doc_240924_9776.pdf --lang ko --start-page 0 --end-page 2
"""
import argparse
import json
import os
import sys
import requests
from pathlib import Path


def test_layout_ocr(
    pdf_path: str,
    server_url: str = "http://localhost:8001",
    lang: str = "en",
    parse_method: str = "auto",
    include_discarded: bool = False,
    start_page: int = 0,
    end_page: int = 99999,
    output_file: str = None
):
    """
    Test /layout_ocr endpoint

    Args:
        pdf_path: Path to PDF file
        server_url: API server URL
        lang: OCR language
        parse_method: auto/ocr/txt
        include_discarded: Include discarded boxes
        start_page: Start page index
        end_page: End page index
        output_file: Optional output JSON file path
    """
    if not os.path.exists(pdf_path):
        print(f"❌ Error: File not found: {pdf_path}")
        return False

    url = f"{server_url}/layout_ocr"

    print(f"📄 Testing /layout_ocr endpoint")
    print(f"   File: {pdf_path}")
    print(f"   Server: {url}")
    print(f"   Language: {lang}")
    print(f"   Parse method: {parse_method}")
    print(f"   Include discarded: {include_discarded}")
    if end_page < 99999:
        print(f"   Pages: {start_page}-{end_page}")
    print()

    try:
        # Get file size for progress info
        file_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
        print(f"📦 File size: {file_size_mb:.2f} MB")
        print()

        # Send request
        print("⏳ Uploading file...")
        with open(pdf_path, 'rb') as f:
            files = {'files': (Path(pdf_path).name, f, 'application/pdf')}
            data = {
                'lang': lang,
                'parse_method': parse_method,
                'include_discarded': str(include_discarded).lower(),
                'start_page_id': str(start_page),
                'end_page_id': str(end_page)
            }

            print("🔄 Processing on server (this may take a while)...")
            print("   - Converting PDF to images")
            print("   - Running layout detection")
            print("   - Cropping layout boxes")
            print("   - Running OCR on each box")
            print("   - Converting to MinerU format")
            print()

            import time
            start_time = time.time()
            response = requests.post(url, files=files, data=data, timeout=600)
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
                files_data = result.get('files', [])
                if files_data:
                    file_data = files_data[0]
                    pages = file_data.get('pages', [])

                    print(f"📊 Summary:")
                    print(f"   Filename: {file_data.get('filename')}")
                    print(f"   Backend: {result.get('backend')}")
                    print(f"   Total pages: {len(pages)}")
                    print()

                    # First page summary
                    if pages:
                        page_0 = pages[0]
                        layout_boxes = page_0.get('layout_boxes', [])
                        page_size = page_0.get('page_size', {})

                        print(f"📖 First page:")
                        print(f"   Page index: {page_0.get('page_index')}")
                        print(f"   Page size: {page_size.get('width')} x {page_size.get('height')}")
                        print(f"   Layout boxes: {len(layout_boxes)}")
                        print()

                        # Layout box type distribution
                        box_types = {}
                        for box in layout_boxes:
                            box_type = box.get('box_type', 'unknown')
                            box_types[box_type] = box_types.get(box_type, 0) + 1

                        print(f"📦 Layout box types (first page):")
                        for box_type, count in sorted(box_types.items()):
                            print(f"   {box_type}: {count}")
                        print()

                        # Sample first layout box
                        if layout_boxes:
                            first_box = layout_boxes[0]
                            lines = first_box.get('lines', [])
                            print(f"🔍 First layout box:")
                            print(f"   Box ID: {first_box.get('box_id')}")
                            print(f"   Box type: {first_box.get('box_type')}")
                            print(f"   BBox: {first_box.get('bbox')}")
                            print(f"   Score: {first_box.get('score', 0):.3f}")
                            print(f"   Position: {first_box.get('position')}")
                            print(f"   Lines: {len(lines)}")
                            print()

                            # Sample first 3 lines
                            if lines:
                                print(f"📝 Sample text lines from first box (first 3):")
                                for i, line in enumerate(lines[:3]):
                                    text = line.get('text', '')
                                    confidence = line.get('confidence', 0)
                                    spans = line.get('spans', [])
                                    char_count = sum(len(s.get('characters', [])) for s in spans)
                                    print(f"   Line {i}: \"{text}\" (conf: {confidence:.3f}, chars: {char_count})")
                                print()

                                # Character bbox check
                                first_line = lines[0]
                                spans = first_line.get('spans', [])
                                if spans:
                                    chars = spans[0].get('characters', [])
                                    if chars:
                                        print(f"🔍 Character bbox check (first line, first 3 chars):")
                                        for char in chars[:3]:
                                            char_text = char.get('char')
                                            bbox = char.get('bbox')
                                            print(f"   '{char_text}': bbox={bbox}")
                                        print()

                        # Discarded boxes
                        discarded_boxes = page_0.get('discarded_boxes', [])
                        if discarded_boxes:
                            print(f"🗑️  Discarded boxes: {len(discarded_boxes)}")
                            print()

            # Save to file
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"💾 Result saved to: {output_file}")
            else:
                # Auto-generate output filename
                pdf_name = Path(pdf_path).stem
                output_file = f"{pdf_name}_layout_ocr_result.json"
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
        print(f"❌ Timeout Error: Request took longer than 600 seconds")
        print()
        print("💡 Suggestions:")
        print("   - Try processing fewer pages (use --start-page and --end-page)")
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
        description='Test /layout_ocr endpoint',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python surya/examples/test_layout_ocr.py temp/doc_240924_9776.pdf

  # Korean OCR with page range
  python surya/examples/test_layout_ocr.py temp/doc_240924_9776.pdf --lang ko --start-page 0 --end-page 2

  # Include discarded boxes (headers/footers)
  python surya/examples/test_layout_ocr.py temp/doc_240924_9776.pdf --include-discarded

  # Custom server
  python surya/examples/test_layout_ocr.py temp/doc_240924_9776.pdf --server http://192.168.1.100:8001

  # Save to specific output file
  python surya/examples/test_layout_ocr.py temp/doc_240924_9776.pdf --output result.json
        """
    )

    parser.add_argument('pdf_path', help='Path to PDF file')
    parser.add_argument('--server', default='http://localhost:8001', help='Server URL')
    parser.add_argument('--lang', default='en', help='OCR language (default: en)')
    parser.add_argument('--parse-method', default='auto', choices=['auto', 'ocr', 'txt'],
                       help='Parse method (default: auto)')
    parser.add_argument('--include-discarded', action='store_true',
                       help='Include discarded boxes (PageHeader, PageFooter)')
    parser.add_argument('--start-page', type=int, default=0, help='Start page (default: 0)')
    parser.add_argument('--end-page', type=int, default=99999, help='End page (default: 99999)')
    parser.add_argument('--output', help='Output JSON file path')

    args = parser.parse_args()

    success = test_layout_ocr(
        args.pdf_path,
        args.server,
        args.lang,
        args.parse_method,
        args.include_discarded,
        args.start_page,
        args.end_page,
        args.output
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
