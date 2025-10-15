# Surya FastAPI 개발 계획서

## 1. 요구사항 정의

### 1.1 목표
Surya OCR을 FastAPI로 서비스화하여 MinerU와 통합 가능한 3가지 시나리오 지원

### 1.2 시나리오 분석

#### 시나리오 1) MinerU Layout + Surya OCR
```
PDF → MinerU (Layout 추출) → Surya /image_ocr API → MinerU (결과 병합)
```
- MinerU가 레이아웃 박스 이미지 리스트 생성
- MinerU 내부에서 Surya의 `/image_ocr` API 호출
- MinerU가 결과를 자체 포맷으로 병합하여 클라이언트에 반환

#### 시나리오 2) Surya Layout + Surya OCR (통합)
```
PDF → Surya /layout_ocr API → Layout 추출 + OCR → MinerU 호환 포맷 출력
```
- Surya의 Layout 모델로 레이아웃 박스 추출
- 각 레이아웃 박스별로 OCR 수행
- MinerU와 동일한 출력 포맷으로 반환
- **MinerU 클라이언트 프로그램과 호환**

#### 시나리오 3) Direct OCR (레이아웃 없음)
```
PDF → Surya /page_ocr API → 페이지 전체 OCR → 라인/캐릭터 출력
```
- 레이아웃 감지 없이 페이지 전체에서 text line 추출
- Line → Character 계층 구조로 출력
- 빠른 텍스트 추출용

---

## 2. API 엔드포인트 설계

### 2.1 엔드포인트 목록

| 엔드포인트 | 입력 | 출력 | 용도 |
|-----------|------|------|------|
| `/layout_ocr` | PDF/이미지 파일 | MinerU 호환 포맷 | 시나리오 2: Layout + OCR 통합 |
| `/page_ocr` | PDF/이미지 파일 | 간소화된 페이지 OCR | 시나리오 3: 빠른 텍스트 추출 |
| `/image_ocr` | 이미지 리스트 (Base64) | OCR 결과 리스트 | 시나리오 1: MinerU 연동용 |
| `/layout_ocr/stream` | WebSocket | 페이지별 스트리밍 | 시나리오 2 실시간 처리 |
| `/page_ocr/stream` | WebSocket | 페이지별 스트리밍 | 시나리오 3 실시간 처리 |

### 2.2 `/layout_ocr` - Layout + OCR 통합 API

#### 요청 (HTTP POST)
```python
{
  "files": [File],              # PDF 또는 이미지 파일
  "lang": "ko",                 # OCR 언어 (ch, en, ja, ko 등)
  "parse_method": "auto",       # auto/ocr/txt
  "include_discarded": false,   # discarded 블록 포함 여부
  "start_page_id": 0,          # 시작 페이지
  "end_page_id": 99999,        # 종료 페이지
  "output_dir": "./output"     # 임시 출력 디렉토리
}
```

#### 응답 (MinerU 호환)
```json
{
  "status": "success",
  "backend": "surya",
  "version": "0.17.0",
  "files": [{
    "filename": "document.pdf",
    "pages": [{
      "page_index": 0,
      "page_size": {"width": 1438, "height": 1928},
      "layout_boxes": [{
        "box_id": 0,
        "box_type": "text",              // Surya label: Text, Title, Table, Image 등
        "bbox": [166, 428, 905, 884],
        "score": 0.95,
        "position": 0,                   // Reading order
        "lines": [{
          "line_index": 0,
          "bbox": [169, 429, 894, 466],
          "text": "책에 바침이란...",
          "confidence": 0.993,
          "spans": [{
            "type": "text",
            "bbox": [169, 429, 894, 466],
            "content": "책에 바침이란...",
            "confidence": 0.993,
            "characters": [
              {"char": "책", "bbox": [653, 564, 743, 584], "confidence": 0.999, "char_index": 0},
              {"char": "에 바침", "bbox": [744, 564, 812, 584], "confidence": 0.998, "char_index": 1}
            ]
          }]
        }]
      }],
      "discarded_boxes": []  // include_discarded=true인 경우
    }]
  }]
}
```

### 2.3 `/page_ocr` - 페이지 직접 OCR API

#### 요청
```python
{
  "files": [File],
  "lang": "ko",
  "start_page_id": 0,
  "end_page_id": 99999
}
```

#### 응답 (간소화된 포맷)
```json
{
  "status": "success",
  "backend": "surya",
  "version": "0.17.0",
  "files": [{
    "filename": "document.pdf",
    "pages": [{
      "page_index": 0,
      "page_size": {"width": 1438, "height": 1928},
      "text_lines": [{
        "line_id": 0,
        "bbox": [608, 554, 789, 595],
        "polygon": [[608, 554], [789, 554], [789, 595], [608, 595]],
        "text": "책에 바침",
        "confidence": 0.993,
        "characters": [
          {"char": "책", "bbox": [653, 564, 743, 584], "confidence": 0.999, "char_index": 0},
          {"char": "에 바침", "bbox": [744, 564, 812, 584], "confidence": 0.998, "char_index": 1}
        ],
        "words": [
          {"text": "책에", "bbox": [653, 564, 780, 584], "confidence": 0.999}
        ]
      }]
    }]
  }]
}
```

### 2.4 `/image_ocr` - 이미지 리스트 OCR API

#### 요청
```json
{
  "images": [
    {
      "image_data": "base64_encoded_image_1",
      "image_id": "layout_box_0"
    },
    {
      "image_data": "base64_encoded_image_2",
      "image_id": "layout_box_1"
    }
  ],
  "lang": "ko",
  "task_name": "ocr_with_boxes"  // ocr_with_boxes, ocr_without_boxes, block_without_boxes
}
```

#### 응답
```json
{
  "status": "success",
  "results": [{
    "image_id": "layout_box_0",
    "text_lines": [{
      "text": "텍스트 내용",
      "bbox": [10, 20, 100, 40],
      "confidence": 0.995,
      "characters": [...]
    }]
  }]
}
```

### 2.5 WebSocket 스트리밍 API

#### `/layout_ocr/stream`, `/page_ocr/stream`

**클라이언트 → 서버 (초기 요청)**
```json
{
  "pdf_base64": "base64_encoded_pdf",
  "filename": "document.pdf",
  "lang": "ko",
  "parse_method": "auto",
  "include_discarded": false,
  "start_page_id": 0,
  "end_page_id": 99999
}
```

**서버 → 클라이언트 (스트리밍 메시지)**
```json
// 1. 시작
{"status": "started", "message": "Processing started"}

// 2. 분석 시작
{"status": "analyzing", "total_pages": 10, "message": "Analyzing document"}

// 3. 페이지별 진행 (실시간)
{
  "status": "processing",
  "page_index": 0,
  "progress": 0.1,
  "data": {
    "page_index": 0,
    "layout_boxes": [...],
    ...
  }
}

// 4. 완료
{"status": "completed", "message": "All pages processed"}

// 5. 에러
{"status": "error", "message": "Error message"}
{"status": "page_error", "page_index": 3, "message": "Page 3 error"}
```

---

## 3. 프로젝트 구조

```
surya/
├── api/
│   ├── __init__.py
│   ├── main.py                      # FastAPI 애플리케이션
│   ├── endpoints/
│   │   ├── __init__.py
│   │   ├── layout_ocr.py           # /layout_ocr 엔드포인트
│   │   ├── page_ocr.py             # /page_ocr 엔드포인트
│   │   ├── image_ocr.py            # /image_ocr 엔드포인트
│   │   └── websocket.py            # WebSocket 엔드포인트
│   ├── helpers/
│   │   ├── __init__.py
│   │   ├── char_bbox_fix.py       # Character bbox 수정 로직 (외부 helper)
│   │   ├── format_converter.py    # MinerU 포맷 변환
│   │   ├── pdf_processor.py       # PDF 처리 유틸
│   │   └── image_utils.py         # 이미지 처리 유틸
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── request.py             # API 요청 스키마
│   │   └── response.py            # API 응답 스키마
│   └── config.py                  # API 설정
├── scripts/
│   └── run_api.py                 # API 서버 실행 스크립트
└── examples/
    └── api_client.py              # API 클라이언트 예제
```

---

## 4. 핵심 구현 사항

### 4.1 Token-Based OCR Recognition (TokenRecognitionPredictor)

**설계 원칙**:
- Surya의 Foundation Model은 그대로 사용 (이미 token-bbox 1:1 출력)
- RecognitionPredictor를 상속하여 token-level 처리 구현
- 기존 Surya 내부 코드는 수정하지 않음 (안전한 업데이트 대응)

**문제점**:
- 현재 `RecognitionPredictor.get_bboxes_text()` 메소드가 decode() 후 character 단위로 split
- Token 경계가 손실되어 bbox 중복 발생

**해결 방안**:
- `TokenRecognitionPredictor` 클래스 생성 (RecognitionPredictor 상속)
- `get_bboxes_text()` 메소드만 override하여 token-bbox 1:1 유지

#### `surya/api/helpers/token_recognition.py`
```python
from surya.recognition import RecognitionPredictor
from surya.recognition.schema import TextChar
from surya.common.surya.schema import TaskNames

class TokenRecognitionPredictor(RecognitionPredictor):
    """
    Token-level bbox를 유지하는 RecognitionPredictor

    기존 RecognitionPredictor는 decode() 후 character로 split하지만,
    이 클래스는 token 단위로 유지하여 token-bbox 1:1 대응 보장
    """

    def get_bboxes_text(
        self,
        flat: dict,
        predicted_tokens: list,
        scores: list,
        predicted_polygons: list,
        drop_repeated_text: bool = False,
    ) -> list:
        """
        Override: Token-level bbox를 유지

        차이점:
        - 기존: decode(all_tokens) → enumerate(text) → character split
        - 개선: decode(each_token) → token 단위 유지
        """
        char_predictions = []
        needs_boxes = [
            self.tasks[task_name]["needs_bboxes"]
            for task_name in flat["task_names"]
        ]

        for slice_idx, (...) in enumerate(zip(...)):
            # ... 기존 로직 동일 ...

            img_chars = []
            for sequence in detokenize_sequences:
                token_ids, seq_score, bboxes, token_type = sequence

                if token_type == "ocr":
                    # ★ 핵심 변경: 각 토큰을 개별 decode
                    for token_idx, (token_id, bbox, score) in enumerate(
                        zip(token_ids, bboxes, seq_score)
                    ):
                        # 토큰 하나씩 decode (token 경계 유지)
                        token_text = self.processor.ocr_tokenizer.decode(
                            [token_id],
                            task=TaskNames.ocr_with_boxes
                        )

                        # clean_close_polygons() 적용
                        cleaned_bbox = clean_close_polygons([bbox])[0]

                        # TextChar 생성 (1 token = 1 TextChar)
                        img_chars.append(
                            TextChar(
                                text=token_text,
                                polygon=cleaned_bbox,
                                confidence=score,
                                bbox_valid=True,
                            )
                        )
                # ... special, block 타입 처리는 기존과 동일 ...

            char_predictions.append(img_chars)

        return char_predictions
```

**사용 방식**:
```python
# surya/api/endpoints/page_ocr.py
from surya.api.helpers.token_recognition import TokenRecognitionPredictor

def get_predictors():
    global _foundation_predictor, _detection_predictor, _recognition_predictor

    if _foundation_predictor is None:
        _foundation_predictor = FoundationPredictor()
        _detection_predictor = DetectionPredictor()

        # TokenRecognitionPredictor 사용 (기존 RecognitionPredictor 대신)
        _recognition_predictor = TokenRecognitionPredictor(_foundation_predictor)

    return _foundation_predictor, _detection_predictor, _recognition_predictor
```

**예상 출력** (개선 후):
```json
{
  "text": "책에 바침",
  "characters": [
    {"char": "책", "bbox": [1345.0, 1176.0, 1555.0, 1224.0], "char_index": 0},
    {"char": "에 바침", "bbox": [1346.0, 1176.0, 1554.0, 1224.0], "char_index": 1}
  ]
}
```

**주의사항**:
- `"characters"` 필드명은 MinerU 호환성을 위해 유지하지만, 실제로는 **tokens**를 의미
- 한 token에 여러 문자가 포함될 수 있음 (예: "에 바침")
- Character-level split은 나중에 문서 구조 재구성 단계에서 수행

### 4.2 MinerU 포맷 변환 (Helper 모듈)

#### `surya/api/helpers/format_converter.py`
```python
def surya_layout_to_mineru_format(
    layout_results: List[LayoutResult],
    ocr_results: List[OCRResult],
    pdf_filename: str,
    page_sizes: List[Tuple[int, int]],
    include_discarded: bool = False
) -> dict:
    """
    Surya의 Layout + OCR 결과를 MinerU 포맷으로 변환

    Args:
        layout_results: Surya LayoutPredictor 출력
        ocr_results: Surya RecognitionPredictor 출력 (layout box별)
        pdf_filename: PDF 파일명
        page_sizes: 페이지 크기 리스트
        include_discarded: discarded 블록 포함 여부

    Returns:
        MinerU 호환 JSON 구조
    """
    result = {
        "status": "success",
        "backend": "surya",
        "version": __version__,
        "files": [{
            "filename": pdf_filename,
            "pages": []
        }]
    }

    for page_idx, (layout_result, page_size) in enumerate(zip(layout_results, page_sizes)):
        page_data = {
            "page_index": page_idx,
            "page_size": {"width": page_size[0], "height": page_size[1]},
            "layout_boxes": []
        }

        # Layout box별로 처리
        for box_id, layout_box in enumerate(layout_result.bboxes):
            # Surya label을 MinerU box_type으로 매핑
            box_type = map_surya_label_to_box_type(layout_box.label)

            # 해당 layout box 영역의 OCR 결과 매칭
            ocr_lines = match_ocr_to_layout_box(
                ocr_results[page_idx],
                layout_box
            )

            layout_box_data = {
                "box_id": box_id,
                "box_type": box_type,
                "bbox": layout_box.bbox,
                "score": layout_box.confidence,
                "position": layout_box.position,
                "lines": format_ocr_lines_to_mineru(ocr_lines)
            }

            page_data["layout_boxes"].append(layout_box_data)

        result["files"][0]["pages"].append(page_data)

    return result


def surya_ocr_to_page_format(
    ocr_results: List[OCRResult],
    pdf_filename: str,
    page_sizes: List[Tuple[int, int]]
) -> dict:
    """
    Surya OCR 결과를 페이지 직접 OCR 포맷으로 변환 (layout 없음)
    """
    result = {
        "status": "success",
        "backend": "surya",
        "version": __version__,
        "files": [{
            "filename": pdf_filename,
            "pages": []
        }]
    }

    for page_idx, (ocr_result, page_size) in enumerate(zip(ocr_results, page_sizes)):
        page_data = {
            "page_index": page_idx,
            "page_size": {"width": page_size[0], "height": page_size[1]},
            "text_lines": []
        }

        for line_id, text_line in enumerate(ocr_result.text_lines):
            line_data = {
                "line_id": line_id,
                "bbox": text_line.bbox,
                "polygon": text_line.polygon,
                "text": text_line.text,
                "confidence": text_line.confidence,
                "characters": [
                    {
                        "char": char.text,
                        "bbox": char.bbox,
                        "confidence": char.confidence,
                        "char_index": idx
                    }
                    for idx, char in enumerate(text_line.chars)
                    if char.bbox_valid
                ],
                "words": [
                    {
                        "text": word.text,
                        "bbox": word.bbox,
                        "confidence": word.confidence
                    }
                    for word in (text_line.words or [])
                ] if text_line.words else []
            }

            page_data["text_lines"].append(line_data)

        result["files"][0]["pages"].append(page_data)

    return result
```

### 4.3 레이블 매핑

#### Surya Layout Labels
```python
# surya/layout/label.py 참조
SURYA_LABELS = {
    "Caption", "Footnote", "Formula", "List-item",
    "Page-footer", "Page-header", "Picture", "Figure",
    "Section-header", "Table", "Form", "Table-of-contents",
    "Handwriting", "Text", "Text-inline-math"
}
```

#### MinerU 호환 Box Types
```python
BOX_TYPE_MAPPING = {
    "Text": "text",
    "Section-header": "title",
    "Table": "table",
    "Picture": "image",
    "Figure": "image",
    "Formula": "interline_equation",
    "Caption": "caption",
    "Footnote": "footnote",
    "Page-header": "discarded",
    "Page-footer": "discarded",
    # ... 나머지 매핑
}
```

---

## 5. 구현 순서

### Phase 1: 기본 구조 구축 (2-3일)
1. ✅ FastAPI 프로젝트 구조 생성
2. ✅ `/page_ocr` 엔드포인트 구현 (가장 간단)
   - PDF → 이미지 변환
   - Surya OCR 호출
   - 간소화된 포맷으로 변환
3. ✅ Character bbox fix helper 구현
4. ✅ 기본 테스트

### Phase 2: Layout OCR 구현 (3-4일)
1. ✅ `/layout_ocr` 엔드포인트 구현
   - Layout detection (LayoutPredictor)
   - Layout box별 OCR 수행
   - MinerU 포맷 변환
2. ✅ Format converter helper 구현
3. ✅ MinerU 클라이언트 호환성 테스트
4. ✅ 다양한 문서 타입 테스트

### Phase 3: Image OCR 구현 (1-2일)
1. ✅ `/image_ocr` 엔드포인트 구현
   - Base64 이미지 디코딩
   - 배치 OCR 처리
   - 결과 리스트 반환
2. ✅ MinerU 연동 테스트

### Phase 4: WebSocket 스트리밍 (2-3일)
1. ✅ `/layout_ocr/stream` 구현
2. ✅ `/page_ocr/stream` 구현
3. ✅ 페이지별 병렬 처리 최적화
4. ✅ Progress tracking
5. ✅ Error handling

### Phase 5: 테스트 및 최적화 (2-3일)
1. ✅ 통합 테스트
2. ✅ 성능 최적화
3. ✅ API 문서화 (Swagger)
4. ✅ 예제 클라이언트 작성
5. ✅ README 작성

**총 예상 기간**: 10-15일

---

## 6. MinerU 통합 방안

### 6.1 MinerU에서 Surya API 호출

#### `mineru/backend/surya_ocr_adapter.py` (신규 생성)
```python
import requests
from typing import List, Dict
import base64
from io import BytesIO
from PIL import Image

class SuryaOCRAdapter:
    """MinerU에서 Surya API를 호출하기 위한 어댑터"""

    def __init__(self, surya_api_url: str = "http://localhost:8001"):
        self.surya_api_url = surya_api_url

    def ocr_layout_boxes(
        self,
        layout_box_images: List[Image.Image],
        lang: str = "ko"
    ) -> List[Dict]:
        """
        레이아웃 박스 이미지 리스트를 Surya에 전송하여 OCR 수행

        Args:
            layout_box_images: PIL Image 리스트
            lang: OCR 언어

        Returns:
            OCR 결과 리스트
        """
        # 이미지를 Base64로 인코딩
        encoded_images = []
        for idx, img in enumerate(layout_box_images):
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            img_b64 = base64.b64encode(buffer.getvalue()).decode()
            encoded_images.append({
                "image_data": img_b64,
                "image_id": f"layout_box_{idx}"
            })

        # Surya /image_ocr API 호출
        response = requests.post(
            f"{self.surya_api_url}/image_ocr",
            json={
                "images": encoded_images,
                "lang": lang
            },
            timeout=300
        )

        if response.status_code == 200:
            result = response.json()
            return result["results"]
        else:
            raise Exception(f"Surya API error: {response.status_code}")
```

#### MinerU `/layout_ocr` 엔드포인트 수정
```python
# mineru/cli/fast_api.py

from mineru.backend.surya_ocr_adapter import SuryaOCRAdapter

@app.post(path="/layout_ocr")
async def layout_ocr(...):
    # ... 기존 레이아웃 추출 로직 ...

    # Surya OCR 호출 옵션 추가
    use_surya_ocr = request_data.get("use_surya_ocr", False)
    surya_api_url = request_data.get("surya_api_url", "http://localhost:8001")

    if use_surya_ocr:
        # Surya 어댑터 생성
        surya_adapter = SuryaOCRAdapter(surya_api_url)

        # 레이아웃 박스별로 이미지 추출
        layout_box_images = extract_layout_box_images(layout_boxes, page_image)

        # Surya OCR 호출
        ocr_results = surya_adapter.ocr_layout_boxes(
            layout_box_images,
            lang=lang
        )

        # 결과 병합
        merged_result = merge_layout_and_ocr(layout_boxes, ocr_results)
    else:
        # 기존 MinerU OCR 사용
        merged_result = original_mineru_ocr(layout_boxes)

    return merged_result
```

### 6.2 클라이언트 호환성

**MinerU 클라이언트 프로그램** (`layout_ocr_client.py`)은 **엔드포인트 URL만 변경**하면 바로 사용 가능:

```bash
# MinerU 서버 사용
python layout_ocr_client.py document.pdf \
  --server http://localhost:8000 \
  --mode http

# Surya 서버 사용 (동일한 클라이언트!)
python layout_ocr_client.py document.pdf \
  --server http://localhost:8001 \
  --mode http
```

**출력 포맷이 동일**하므로 클라이언트는 서버 차이를 인식하지 못함!

---

## 7. API 서버 실행

### 7.1 설치
```bash
cd /Users/pipaek/project/surya
pip install fastapi uvicorn python-multipart websockets
```

### 7.2 서버 실행 스크립트

#### `surya/scripts/run_api.py`
```python
#!/usr/bin/env python3
import click
import uvicorn
from surya.api.main import app

@click.command()
@click.option('--host', default='127.0.0.1', help='Server host')
@click.option('--port', default=8001, type=int, help='Server port')
@click.option('--reload', is_flag=True, help='Enable auto-reload')
@click.option('--workers', default=1, type=int, help='Number of workers')
def main(host, port, reload, workers):
    """Start Surya FastAPI server"""
    print(f"Starting Surya API Server: http://{host}:{port}")
    print(f"API documentation: http://{host}:{port}/docs")

    uvicorn.run(
        "surya.api.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1
    )

if __name__ == "__main__":
    main()
```

### 7.3 실행
```bash
# 개발 모드 (auto-reload)
python surya/scripts/run_api.py --reload

# 프로덕션 모드 (multi-worker)
python surya/scripts/run_api.py --host 0.0.0.0 --port 8001 --workers 4
```

---

## 8. 테스트 계획

### 8.1 유닛 테스트
```python
# tests/api/test_char_bbox_fix.py
def test_character_bbox_fix():
    """Character bbox 수정이 올바르게 작동하는지 테스트"""
    pass

# tests/api/test_format_converter.py
def test_surya_to_mineru_conversion():
    """Surya → MinerU 포맷 변환 테스트"""
    pass
```

### 8.2 통합 테스트
```bash
# 1. 페이지 OCR 테스트
curl -X POST http://localhost:8001/page_ocr \
  -F "files=@test.pdf" \
  -F "lang=ko"

# 2. Layout OCR 테스트
curl -X POST http://localhost:8001/layout_ocr \
  -F "files=@test.pdf" \
  -F "lang=ko"

# 3. Image OCR 테스트
curl -X POST http://localhost:8001/image_ocr \
  -H "Content-Type: application/json" \
  -d @test_images.json

# 4. MinerU 클라이언트 호환성 테스트
python /Users/pipaek/project/MinerU/examples/layout_ocr_client.py test.pdf \
  --server http://localhost:8001 \
  --mode http
```

### 8.3 성능 테스트
- 다양한 페이지 수 (1, 10, 50, 100 페이지)
- 다양한 문서 타입 (텍스트, 표, 이미지 혼합)
- 병렬 처리 효율성
- WebSocket vs HTTP 성능 비교

---

## 9. 주의사항

### 9.1 오픈소스 업데이트 대응
- ✅ Surya 내부 코드 직접 수정 금지
- ✅ 모든 커스터마이징은 `surya/api/helpers/` 모듈로 분리
- ✅ Surya 업데이트 시 helper만 조정

### 9.2 Token-Based BBox 처리
- ✅ `TokenRecognitionPredictor` 사용으로 token-bbox 1:1 대응 유지
- ✅ Token 단위 decode로 경계 보존
- ✅ Character split은 문서 구조 재구성 단계에서 수행

### 9.3 메모리 관리
- 페이지별 처리로 메모리 최적화
- WebSocket 사용 시 적절한 버퍼 크기 설정
- 대용량 PDF 처리 시 chunk 처리

### 9.4 에러 처리
- 각 페이지 에러는 전체 처리 중단하지 않음
- 상세한 에러 메시지 반환
- Retry 로직 구현

---

## 10. 향후 개선 사항

### 10.1 단기 (1개월)
- [ ] 배치 처리 최적화
- [ ] 캐싱 메커니즘
- [ ] 진행률 상세 추적
- [ ] 더 많은 언어 지원

### 10.2 중기 (3개월)
- [ ] GPU 메모리 최적화
- [ ] 분산 처리 지원
- [ ] 결과 후처리 옵션
- [ ] BBox 시각화 API

### 10.3 장기 (6개월)
- [ ] 모델 버전 관리
- [ ] A/B 테스트 기능
- [ ] 실시간 피드백 학습
- [ ] 클라우드 배포 지원

---

## 11. 참고 자료

### 11.1 관련 파일
- `surya/recognition/__init__.py` - OCR 예측 로직
- `surya/layout/__init__.py` - Layout 예측 로직
- `surya/scripts/ocr_text.py` - CLI OCR 구현
- `surya/scripts/detect_layout.py` - CLI Layout 구현
- `/Users/pipaek/project/MinerU/mineru/cli/fast_api.py` - MinerU API 참조
- `/Users/pipaek/project/MinerU/examples/layout_ocr_client.py` - 클라이언트 예제

### 11.2 Surya 데이터 구조
```python
# OCR 결과
class TextChar(BaseModel):
    text: str
    confidence: float
    polygon: List[List[float]]
    bbox: List[float]
    bbox_valid: bool

class TextLine(BaseModel):
    text: str
    confidence: float
    polygon: List[List[float]]
    bbox: List[float]
    chars: List[TextChar]
    words: List[TextWord] | None

class OCRResult(BaseModel):
    text_lines: List[TextLine]
    image_bbox: List[float]

# Layout 결과
class LayoutBox(BaseModel):
    label: str              # Text, Title, Table, Image 등
    position: int           # Reading order
    confidence: float
    polygon: List[List[float]]
    bbox: List[float]
    top_k: Dict[str, float] | None

class LayoutResult(BaseModel):
    bboxes: List[LayoutBox]
    image_bbox: List[float]
```

---

## 12. 결론

이 개발 계획을 통해:

1. ✅ Surya를 FastAPI로 서비스화
2. ✅ MinerU와 완벽한 호환성 확보
3. ✅ 3가지 시나리오 모두 지원
4. ✅ Character-level bbox 정확도 개선
5. ✅ 오픈소스 업데이트에 안전한 구조
6. ✅ WebSocket 실시간 스트리밍 지원

**핵심 원칙**:
- Surya 내부 코드 수정 없이 helper 모듈로 확장
- MinerU 클라이언트 프로그램과 100% 호환
- 페이지별 병렬 처리로 성능 최적화
- 명확한 에러 처리 및 진행률 추적

**다음 단계**: Phase 1부터 순차 구현 시작!
