# ==============================================================================
# FaceID Biometric Recognition & Role-Based Access Control System
# Copyright (c) 2026 Saitharun Cherukuri. All rights reserved.
# Author: Saitharun Cherukuri
# ==============================================================================

import io
import re
import base64
import threading
from typing import Optional, Tuple, List, Dict, Any
import cv2
import numpy as np
from PIL import Image

from config import (
    YUNET_MODEL_PATH,
    SFACE_MODEL_PATH,
    DEFAULT_COSINE_THRESHOLD,
    MIN_DETECTION_CONFIDENCE,
)

_lock = threading.Lock()


class FaceEngine:
    def __init__(self):
        # Initialize detector with default size (320, 320)
        self.detector = cv2.FaceDetectorYN.create(
            YUNET_MODEL_PATH,
            "",
            (320, 320),
            score_threshold=MIN_DETECTION_CONFIDENCE,
            nms_threshold=0.3,
            top_k=5000
        )
        self.recognizer = cv2.FaceRecognizerSF.create(SFACE_MODEL_PATH, "")

    @staticmethod
    def decode_image(image_data: Any) -> Optional[np.ndarray]:
        """
        Decode image from base64 string, bytes, or PIL Image into OpenCV BGR numpy array.
        """
        try:
            if isinstance(image_data, np.ndarray):
                return image_data

            if isinstance(image_data, str):
                # Handle base64 data URI format
                if "," in image_data:
                    image_data = image_data.split(",", 1)[1]
                image_bytes = base64.b64decode(image_data)
            elif isinstance(image_data, bytes):
                image_bytes = image_data
            elif hasattr(image_data, "read"):
                image_bytes = image_data.read()
            else:
                return None

            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img
        except Exception as e:
            print(f"[FaceEngine] Error decoding image: {e}")
            return None

    def detect_faces(self, img: np.ndarray) -> Optional[np.ndarray]:
        """
        Detect faces in image. Returns array of detected faces or None.
        Each face is 15 elements: [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rcm, y_rcm, x_lcm, y_lcm, score]
        """
        if img is None:
            return None

        h, w = img.shape[:2]
        with _lock:
            self.detector.setInputSize((w, h))
            _, faces = self.detector.detect(img)

        return faces

    def extract_embedding(self, img: np.ndarray, face: np.ndarray) -> np.ndarray:
        """
        Align face and extract 128-dimensional embedding vector.
        """
        with _lock:
            aligned = self.recognizer.alignCrop(img, face)
            feature = self.recognizer.feature(aligned)
        return feature.flatten()

    @staticmethod
    def cosine_similarity(feat1: np.ndarray, feat2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two feature vectors.
        """
        f1 = np.asarray(feat1, dtype=np.float32)
        f2 = np.asarray(feat2, dtype=np.float32)
        norm1 = np.linalg.norm(f1)
        norm2 = np.linalg.norm(f2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(f1, f2) / (norm1 * norm2))

    @staticmethod
    def calculate_accuracy_percentage(score: float, threshold: float = DEFAULT_COSINE_THRESHOLD) -> float:
        """
        Convert SFace cosine similarity score into a human-intuitive accuracy percentage (0.0% to 99.9%).
        - If score >= threshold: Scales from 70.0% to 99.9% (Verified match range)
        - If score < threshold: Scales from 0.0% to 69.9% (Below threshold / Non-match)
        """
        score = max(-1.0, min(1.0, float(score)))

        if score >= threshold:
            # Map [threshold, 1.0] -> [70.0, 99.9]
            if 1.0 - threshold <= 0.0001:
                return 99.9
            fraction = (score - threshold) / (1.0 - threshold)
            accuracy = 70.0 + (fraction * 29.9)
            return round(min(99.9, max(70.0, accuracy)), 2)
        else:
            # Map [0.0, threshold] -> [0.0, 69.0]
            if threshold <= 0.0001:
                return 0.0
            fraction = max(0.0, score) / threshold
            accuracy = fraction * 69.0
            return round(min(69.0, max(0.0, accuracy)), 2)

    def crop_face(self, img: np.ndarray, face: np.ndarray, target_size: Tuple[int, int] = (250, 250)) -> np.ndarray:
        """
        Crop face region with generous padding for profile display.
        """
        h_img, w_img = img.shape[:2]
        x, y, w, h = [int(v) for v in face[:4]]

        # 25% padding
        pad_x = int(w * 0.25)
        pad_y = int(h * 0.35)

        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(w_img, x + w + pad_x)
        y2 = min(h_img, y + h + int(pad_y * 0.8))

        cropped = img[y1:y2, x1:x2]
        if cropped.size == 0:
            return cv2.resize(img, target_size)
        return cv2.resize(cropped, target_size, interpolation=cv2.INTER_AREA)

    def process_face_registration(self, image_data: Any) -> Tuple[bool, str, Optional[np.ndarray], Optional[list], Optional[dict]]:
        """
        Process face image for registration.
        Validates that exactly one clear face is found.
        Returns: (success, message, cropped_bgr, embedding_list, face_meta)
        """
        img = self.decode_image(image_data)
        if img is None:
            return False, "Unable to decode image. Please provide a valid JPEG/PNG.", None, None, None

        faces = self.detect_faces(img)
        if faces is None or len(faces) == 0:
            return False, "No face detected. Please ensure your face is well-lit and facing the camera directly.", None, None, None

        if len(faces) > 1:
            # Sort by detection confidence
            faces = sorted(faces, key=lambda f: f[-1], reverse=True)
            # If the second face also has high confidence, advise single person
            if faces[1][-1] > 0.7:
                return False, "Multiple faces detected. Please ensure only one person is in the frame.", None, None, None

        primary_face = faces[0]
        confidence = float(primary_face[-1])
        if confidence < MIN_DETECTION_CONFIDENCE:
            return False, f"Face detection confidence is low ({confidence*100:.1f}%). Please improve lighting and position.", None, None, None

        cropped = self.crop_face(img, primary_face)
        embedding = self.extract_embedding(img, primary_face).tolist()

        face_meta = {
            "bbox": [int(v) for v in primary_face[:4]],
            "confidence": round(confidence * 100, 1)
        }

        return True, "Face processed successfully", cropped, embedding, face_meta

    def identify_face(
        self,
        image_data: Any,
        registered_users: List[Dict[str, Any]],
        threshold: float = DEFAULT_COSINE_THRESHOLD
    ) -> Dict[str, Any]:
        """
        Identify face in image against a list of registered users.
        Each user in registered_users must have 'user_id', 'full_name', and 'embedding'.
        Returns identification result with match status and facial accuracy.
        """
        img = self.decode_image(image_data)
        if img is None:
            return {
                "status": "ERROR",
                "message": "Invalid image data received",
                "matched": False,
                "user": None,
                "accuracy_percent": 0.0,
                "similarity_score": 0.0,
                "face_detected": False
            }

        faces = self.detect_faces(img)
        if faces is None or len(faces) == 0:
            return {
                "status": "NO_FACE",
                "message": "No face detected in camera feed",
                "matched": False,
                "user": None,
                "accuracy_percent": 0.0,
                "similarity_score": 0.0,
                "face_detected": False
            }

        # Select the largest face in frame
        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        primary_face = faces[0]
        bbox = [int(v) for v in primary_face[:4]]
        detection_confidence = round(float(primary_face[-1]) * 100, 1)

        # Extract embedding
        query_embedding = self.extract_embedding(img, primary_face)

        if not registered_users:
            return {
                "status": "NO_REGISTERED_USERS",
                "message": "No registered users in the database yet",
                "matched": False,
                "user": None,
                "accuracy_percent": 0.0,
                "similarity_score": 0.0,
                "face_detected": True,
                "bbox": bbox,
                "detection_confidence": detection_confidence
            }

        # Compare against registered users
        best_user = None
        best_score = -1.0

        for user in registered_users:
            emb = user.get("embedding")
            if not emb:
                continue
            sim = self.cosine_similarity(query_embedding, np.array(emb, dtype=np.float32))
            if sim > best_score:
                best_score = sim
                best_user = user

        accuracy = self.calculate_accuracy_percentage(best_score, threshold)
        is_match = (best_score >= threshold) and (best_user is not None)

        if is_match:
            # Remove embedding before returning to avoid leaking biometric vectors
            safe_user = {k: v for k, v in best_user.items() if k != "embedding"}
            return {
                "status": "VERIFIED",
                "message": f"Identity verified: {safe_user.get('full_name')}",
                "matched": True,
                "user": safe_user,
                "accuracy_percent": accuracy,
                "similarity_score": round(best_score, 4),
                "threshold_used": round(threshold, 4),
                "face_detected": True,
                "bbox": bbox,
                "detection_confidence": detection_confidence
            }
        else:
            return {
                "status": "UNRECOGNIZED",
                "message": "Face not recognized. Access Denied.",
                "matched": False,
                "user": None,
                "accuracy_percent": accuracy,
                "similarity_score": round(max(0.0, best_score), 4),
                "threshold_used": round(threshold, 4),
                "face_detected": True,
                "bbox": bbox,
                "detection_confidence": detection_confidence
            }


# Global singleton instance
face_engine = FaceEngine()
