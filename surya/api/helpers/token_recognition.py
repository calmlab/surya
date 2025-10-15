"""Token-based Recognition Predictor

This module provides a TokenRecognitionPredictor that maintains token-bbox 1:1 correspondence.
Unlike the standard RecognitionPredictor which decodes all tokens at once and splits into characters,
this predictor decodes each token individually to preserve token boundaries.
"""
from __future__ import annotations

import re
from typing import List

from surya.recognition import RecognitionPredictor
from surya.recognition.schema import TextChar
from surya.recognition.util import clean_close_polygons
from surya.common.surya.schema import TaskNames
from surya.common.surya.processor import NOMATH_TOKEN
from surya.foundation.util import detect_repeat_token
from surya.logging import get_logger

logger = get_logger()


class TokenRecognitionPredictor(RecognitionPredictor):
    """
    Token-level bbox Recognition Predictor

    Extends RecognitionPredictor to maintain strict 1:1 correspondence between tokens and bboxes.

    Key difference from parent class:
    - Parent: decode(all_tokens) → enumerate(text) → splits into individual characters
    - This: decode(each_token) → preserves token boundaries

    Example:
        Foundation model outputs: [token1="책", token2="에 바침"]
        Parent would create: 5 TextChar objects (one per character) with bbox duplication
        This creates: 2 TextChar objects (one per token) with 1:1 bbox correspondence

    Note:
        The "char" field name is maintained for MinerU compatibility, but it actually
        represents tokens which may contain multiple characters.
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
        Override parent method to maintain token-level granularity

        Args:
            flat: Dictionary containing slices, task_names, etc.
            predicted_tokens: Token IDs predicted by the model
            scores: Confidence scores for each token
            predicted_polygons: Bboxes for each token (1:1 correspondence)
            drop_repeated_text: Whether to drop repeated tokens

        Returns:
            List of character predictions (actually tokens) for each slice
        """
        logger.info(f"[TokenRecognition] get_bboxes_text called with {len(predicted_tokens)} slices")
        char_predictions = []
        needs_boxes = [
            self.tasks[task_name]["needs_bboxes"] for task_name in flat["task_names"]
        ]

        for slice_idx, (
            slice_image,
            image_tokens,
            image_polygons,
            image_scores,
            needs_box,
        ) in enumerate(
            zip(
                flat["slices"],
                predicted_tokens,
                predicted_polygons,
                scores,
                needs_boxes,
            )
        ):
            blank_bbox = [[0, 0], [0, 1], [1, 1], [1, 0]]
            if self.processor.no_output_token in image_tokens:
                char_predictions.append(None)
                continue

            # If the image is very out of distribution, we can get nonsense repeats
            if drop_repeated_text and detect_repeat_token(image_tokens):
                char_predictions.append(
                    [
                        TextChar(
                            text="",
                            polygon=blank_bbox,
                            confidence=0,
                            bbox_valid=False,
                        )
                    ]
                )
                continue

            image_polygons = image_polygons[: len(image_tokens)].cpu().numpy().tolist()

            detokenize_sequences = []
            detokenize_sequence = []

            def _add_detokenize_sequence(
                special_token: bool,
                past_special_token: bool,
                force: bool = False,
            ):
                nonlocal detokenize_sequence, detokenize_sequences

                if (
                    special_token
                    or past_special_token
                    or force
                ) and detokenize_sequence:
                    chars = [dt[0] for dt in detokenize_sequence]
                    scores = [dt[1] for dt in detokenize_sequence]
                    bboxes = [dt[2] for dt in detokenize_sequence]

                    if past_special_token:
                        detokenize_sequences.append((chars, scores, None, "special"))
                    else:
                        detokenize_sequences.append((chars, scores, bboxes, "ocr"))

                    detokenize_sequence = []

            # Split up into sequences to detokenize separately
            past_special_token = False
            for bbox, char_id, score in zip(image_polygons, image_tokens, image_scores):
                if char_id in [
                    self.processor.eos_token_id,
                    self.processor.pad_token_id,
                ]:
                    break

                special_token = (
                    char_id >= self.processor.ocr_tokenizer.ocr_tokenizer.SPECIAL_BASE
                )
                _add_detokenize_sequence(
                    special_token, past_special_token
                )
                detokenize_sequence.append((char_id, score, bbox))
                past_special_token = special_token

            _add_detokenize_sequence(
                False, past_special_token, force=True
            )

            # ★ KEY DIFFERENCE: Decode tokens individually to preserve token boundaries
            img_chars = []
            for sequence in detokenize_sequences:
                token_ids, seq_score, bboxes, token_type = sequence

                if token_type == "ocr":
                    # ★ DO NOT use clean_close_polygons() - it merges UTF-16 tokens
                    # We want to maintain strict 1:1 token-bbox correspondence

                    logger.info(f"[TokenRecognition] Processing OCR sequence with {len(token_ids)} tokens, {len(bboxes)} bboxes")

                    # Decode each token individually to maintain token-bbox 1:1 correspondence
                    for token_idx, (token_id, bbox, score) in enumerate(
                        zip(token_ids, bboxes, seq_score)
                    ):
                        # Decode single token (preserves token boundary)
                        token_text = self.processor.ocr_tokenizer.decode(
                            [token_id],
                            task=TaskNames.ocr_with_boxes
                        )

                        logger.info(f"[TokenRecognition] Token {token_idx}: id={token_id}, text='{token_text}', bbox={bbox[:2] if len(bbox) > 0 else 'empty'}")

                        # Create one TextChar per token (not per character!)
                        img_chars.append(
                            TextChar(
                                text=token_text,
                                polygon=bbox,
                                confidence=score,
                                bbox_valid=True,
                            )
                        )

                elif token_type == "special":
                    text = self.processor.ocr_tokenizer.decode(
                        token_ids, task="ocr_without_boxes"
                    )
                    if text in [NOMATH_TOKEN] or re.match(r"<SCRIPT-\w+>", text):
                        continue

                    img_chars.append(
                        TextChar(
                            text=text,
                            polygon=blank_bbox,
                            confidence=seq_score[0],
                            bbox_valid=False,
                        )
                    )
                else:
                    # block_without_boxes type
                    text = self.processor.ocr_tokenizer.decode(
                        token_ids, task=TaskNames.block_without_boxes
                    )
                    img_chars.append(
                        TextChar(
                            text=text,
                            polygon=blank_bbox,
                            confidence=seq_score[0],
                            bbox_valid=False,
                        )
                    )

            char_predictions.append(img_chars)

        return char_predictions
