#!/usr/bin/env python3
"""
FaceEmbed API - 基于Hailo-8的人脸特征提取服务
支持单张和批量人脸嵌入向量生成
"""

import asyncio
import base64
import io
import json
import logging
import os
import time
import queue
import threading
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from skimage.transform import SimilarityTransform

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hailo imports
try:
    from hailo_platform import VDevice, HailoSchedulingAlgorithm
    from utils import HailoAsyncInference
except (ImportError, ModuleNotFoundError):
    # This will be raised by HailoAsyncInference, but we add a fallback here
    raise ImportError("HailoRT is not installed or not in the PYTHONPATH.")

# Models
class BBoxModel(BaseModel):
    x: int = Field(..., description="X coordinate")
    y: int = Field(..., description="Y coordinate") 
    w: int = Field(..., description="Width")
    h: int = Field(..., description="Height")

class LandmarkPoint(BaseModel):
    x: float = Field(..., description="X coordinate of the landmark")
    y: float = Field(..., description="Y coordinate of the landmark")

class DetectedFace(BaseModel):
    bbox: BBoxModel = Field(..., description="Face bounding box")
    landmarks: List[LandmarkPoint] = Field(..., description="5 face landmarks")
    confidence: float = Field(..., description="Detection confidence score")

class EmbedRequest(BaseModel):
    image_base64: str = Field(..., description="Base64 encoded JPEG image")
    bbox: BBoxModel = Field(..., description="Face bounding box")
    landmarks: Optional[List[LandmarkPoint]] = Field(None, description="List of 5 face landmarks (left_eye, right_eye, nose, left_mouth, right_mouth)")

class DetectRequest(BaseModel):
    image_base64: str = Field(..., description="Base64 encoded JPEG image")
    confidence_threshold: Optional[float] = Field(0.55, description="Minimum detection confidence threshold. Recommended: 0.55")
    nms_threshold: Optional[float] = Field(0.45, description="Non-Maximum Suppression (NMS) threshold. Recommended: 0.45")
    min_face_size: Optional[int] = Field(8, description="Minimum face size in pixels (width or height) to be considered a valid detection.")

class BatchEmbedRequest(BaseModel):
    images: List[EmbedRequest] = Field(..., description="List of images with bboxes and optional landmarks")

class EmbedResponse(BaseModel):
    vector: List[float] = Field(..., description="512-D face embedding vector")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    confidence: float = Field(..., description="Face quality confidence score")

class DetectResponse(BaseModel):
    faces: List[DetectedFace] = Field(..., description="List of detected faces")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    image_width: int = Field(..., description="Original image width")
    image_height: int = Field(..., description="Original image height")

class BatchEmbedResponse(BaseModel):
    vectors: List[List[float]] = Field(..., description="List of 512-D face embedding vectors")
    processing_times: List[int] = Field(..., description="Processing times in milliseconds")

class HealthResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    
    status: str = Field(..., description="Service status")
    uptime_ms: int = Field(..., description="Service uptime in milliseconds")
    loaded_models: List[str] = Field(..., description="List of currently loaded model hef files.")

class DetectAndEmbedResponseItem(BaseModel):
    bbox: BBoxModel
    landmarks: List[LandmarkPoint]
    detection_confidence: float
    embedding: EmbedResponse

# Face Embedding Service
class FaceEmbedService:
    def __init__(self):
        self.start_time = time.time()

        # Debug image saving settings from environment variables
        self.debug_save_images = os.getenv('DEBUG_SAVE_IMAGES', 'false').lower() in ('true', '1', 't')
        self.debug_save_interval_s = int(os.getenv('DEBUG_SAVE_INTERVAL_S', '10'))
        self.last_embed_save_time = 0
        self.last_detect_save_time = 0
        self.debug_image_dir = "debug_images"
        if self.debug_save_images:
            os.makedirs(self.debug_image_dir, exist_ok=True)
            logger.info(f"Debug image saving is enabled. Images will be saved to '{self.debug_image_dir}'.")
        
        # Model paths
        self.face_recognition_hef = os.getenv(
            'FACE_RECOGNITION_HEF', 
            os.path.join(os.path.dirname(__file__), '..', 'models', 'arcface_mobilefacenet.hef')
        )
        self.face_detection_hef = os.getenv(
            'FACE_DETECTION_HEF',
            os.path.join(os.path.dirname(__file__), '..', 'models', 'scrfd_10g.hef')
        )
        
        # Pre-check that model files exist to fail early
        if not os.path.exists(self.face_recognition_hef):
            raise FileNotFoundError(f"Recognition model not found: {self.face_recognition_hef}")
        if not os.path.exists(self.face_detection_hef):
            raise FileNotFoundError(f"Detection model not found: {self.face_detection_hef}")

        # --- Multi-model Hailo setup ---
        self.target = None
        self.det_infer_model = None
        self.rec_infer_model = None
        self.det_input_queue = queue.Queue(maxsize=20)
        self.det_output_queue = queue.Queue(maxsize=20)
        self.rec_input_queue = queue.Queue(maxsize=20)
        self.rec_output_queue = queue.Queue(maxsize=20)
        self.det_quant_infos = {} # To store dequantization parameters
        self.rec_quant_infos = {} # To store dequantization parameters for recognition model
        self.det_thread = None
        self.rec_thread = None
        self._initialize_hailo_device()

    def _initialize_hailo_device(self):
        """Initializes a single VDevice and loads all models onto it."""
        logger.info("Initializing Hailo VDevice and loading models...")
        try:
            params = VDevice.create_params()
            params.scheduling_algorithm = HailoSchedulingAlgorithm.ROUND_ROBIN
            self.target = VDevice(params)

            logger.info(f"Loading detection model: {self.face_detection_hef}")
            self.det_infer_model = self.target.create_infer_model(self.face_detection_hef)
            
            # --- Extract and store quantization parameters for the detection model ---
            vstream_infos = self.det_infer_model.hef.get_output_vstream_infos()
            self.det_quant_infos = {
                info.name: (info.quant_info.qp_scale, info.quant_info.qp_zp)
                for info in vstream_infos
            }
            logger.info("--- Detection Model Quantization Info ---")
            for name, params in self.det_quant_infos.items():
                logger.info(f"Layer: {name}, Scale: {params[0]:.4f}, Zero-Point: {params[1]}")
            logger.info("-------------------------------------------")

            logger.info(f"Loading recognition model: {self.face_recognition_hef}")
            self.rec_infer_model = self.target.create_infer_model(self.face_recognition_hef)

            # --- Extract and store quantization parameters for the recognition model ---
            rec_vstream_infos = self.rec_infer_model.hef.get_output_vstream_infos()
            self.rec_quant_infos = {
                info.name: (info.quant_info.qp_scale, info.quant_info.qp_zp)
                for info in rec_vstream_infos
            }
            logger.info("--- Recognition Model Quantization Info ---")
            for name, params in self.rec_quant_infos.items():
                logger.info(f"Layer: {name}, Scale: {params[0]:.4f}, Zero-Point: {params[1]}")
            logger.info("-------------------------------------------")

            # Start inference threads for each model
            self.det_thread = threading.Thread(
                target=self._run_inference_loop, 
                args=("detection", self.det_infer_model, self.det_input_queue, self.det_output_queue),
                daemon=True
            )
            self.rec_thread = threading.Thread(
                target=self._run_inference_loop,
                args=("recognition", self.rec_infer_model, self.rec_input_queue, self.rec_output_queue),
                daemon=True
            )
            self.det_thread.start()
            self.rec_thread.start()

            logger.info("All models loaded and inference threads started.")
        except Exception as e:
            logger.error(f"Failed to initialize Hailo device or models: {e}", exc_info=True)
            raise RuntimeError("Hailo initialization failed.") from e

    def _run_inference_loop(self, name: str, infer_model, input_queue: queue.Queue, output_queue: queue.Queue):
        """
        Generic inference loop for a given model.
        This function runs in a dedicated thread for each model.
        """
        # Using a list as a mutable container to pass the exception from the callback
        # thread back to this inference thread. This avoids using 'user_data' which
        # is not supported in all hailort versions.
        callback_exception_container = [None]

        def inference_callback(completion_info):
            # This callback is executed in a different thread context by the HailoRT driver.
            # We cannot raise from here, so we store the exception in the container.
            if completion_info.exception:
                callback_exception_container[0] = completion_info.exception
                logger.error(f"[{name}] Async inference error in callback: {completion_info.exception}")

        with infer_model.configure() as configured_model:
            while True:
                batch_data = input_queue.get()
                if batch_data is None:
                    logger.info(f"[{name}] Stopping inference loop.")
                    break
                
                original_frame, preprocessed_frame = batch_data
                # Reset exception from previous run before new inference
                callback_exception_container[0] = None

                try:
                    # Explicitly create output buffers with the correct dtype
                    output_buffers = {
                        info.name: np.empty(info.shape, dtype=np.uint8)
                        for info in infer_model.outputs
                    }

                    # --- CRITICAL FIX ---
                    # Zero out the output buffers before inference. This is crucial because
                    # if the async job fails silently without raising an exception, we prevent
                    # returning stale data from a previous inference run. Returning a zero
                    # vector is a safe failure mode.
                    for buf in output_buffers.values():
                        buf.fill(0)

                    bindings = configured_model.create_bindings(output_buffers=output_buffers)
                    bindings.input().set_buffer(preprocessed_frame)
                    
                    configured_model.wait_for_async_ready(timeout_ms=10000)
                    job = configured_model.run_async(
                        [bindings], 
                        callback=inference_callback
                    )
                    job.wait(10000)

                    # After job completion, check if the callback caught an exception
                    if callback_exception_container[0]:
                        # An exception occurred in the callback. Propagate it.
                        raise callback_exception_container[0]

                    output_queue.put((original_frame, output_buffers))

                except Exception as e:
                    logger.error(f"[{name}] An exception occurred during inference: {e}", exc_info=True)
                    # Put a marker to signal error to the consumer
                    output_queue.put((original_frame, None))

    def _decode_image(self, image_base64: str) -> np.ndarray:
        """Decodes a base64 string to a BGR numpy array."""
        try:
            image_bytes = base64.b64decode(image_base64)
            image_np = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("Decoded image is null.")
            return image
        except Exception as e:
            logger.error(f"Failed to decode base64 image: {e}")
            raise ValueError("Invalid base64 image format.")

    def _crop_face(self, image: np.ndarray, bbox: BBoxModel) -> Tuple[np.ndarray, float]:
        """Crops the face from the image using the bounding box."""
        if not (bbox.w > 0 and bbox.h > 0):
            raise ValueError("BBox width and height must be positive.")
        
        img_h, img_w, _ = image.shape
        x1, y1 = max(0, bbox.x), max(0, bbox.y)
        x2, y2 = min(img_w, bbox.x + bbox.w), min(img_h, bbox.y + bbox.h)
        
        if x1 >= x2 or y1 >= y2:
            raise ValueError("BBox is completely outside the image.")

        # Calculate confidence as the ratio of the cropped area to the original bbox area
        cropped_area = (x2 - x1) * (y2 - y1)
        original_area = bbox.w * bbox.h
        confidence = cropped_area / original_area if original_area > 0 else 0.0
        
        cropped_face = image[y1:y2, x1:x2]
        return cropped_face, confidence

    def _align_face(self, image: np.ndarray, landmarks: List[LandmarkPoint]) -> np.ndarray:
        """Aligns a face image using 5 landmarks."""
        # Standard 5-point landmarks for a 112x112 image
        dst_landmarks = np.array([
            [38.2946, 51.6963], [73.5318, 51.5014],
            [56.0252, 71.7366], [41.5493, 92.3655],
            [70.7299, 92.2041]
        ], dtype=np.float32)

        src_landmarks = np.array([(p.x, p.y) for p in landmarks], dtype=np.float32)

        # Estimate similarity transform
        tform = SimilarityTransform()
        tform.estimate(src_landmarks, dst_landmarks)
        M = tform.params[0:2, :]

        # Apply the warp
        aligned_face = cv2.warpAffine(image, M, (112, 112), borderValue=0.0)
        return aligned_face

    def _preprocess_face_for_hailo(self, face_image: np.ndarray, model_shape: Tuple[int, int, int]) -> np.ndarray:
        """Preprocesses a cropped face image for the Hailo embedding model."""
        # Ensure the image is in BGR format
        if len(face_image.shape) == 2:
            face_image = cv2.cvtColor(face_image, cv2.COLOR_GRAY2BGR)
        
        # Resize to model's expected input size (e.g., 112x112)
        h, w, c = model_shape
        resized_face = cv2.resize(face_image, (w, h), interpolation=cv2.INTER_AREA)

        # Save debug image if needed
        if self.debug_save_images and (time.time() - self.last_embed_save_time > self.debug_save_interval_s):
            self.last_embed_save_time = time.time()
            # Save unaligned cropped face for comparison
            cv2.imwrite(
                os.path.join(self.debug_image_dir, f"cropped_for_embedding_{self.last_embed_save_time:.0f}.jpg"),
                face_image
            )
            # Save aligned face ready for embedding
            cv2.imwrite(
                os.path.join(self.debug_image_dir, f"aligned_for_embedding_{self.last_embed_save_time:.0f}.jpg"),
                resized_face
            )

        # BGR -> RGB and HWC -> CHW
        rgb_face = resized_face[:, :, ::-1]
        chw_face = np.transpose(rgb_face, (2, 0, 1))
        
        # Add batch dimension and ensure it's a contiguous C-style array
        # This is CRITICAL for hailo buffer compatibility.
        return np.expand_dims(chw_face, axis=0).astype(np.uint8)


    def _extract_embedding_hailo(self, face_image: np.ndarray, confidence: float, is_aligned: bool = False) -> np.ndarray:
        """
        Extracts a 512-D embedding vector from a single face image using the Hailo device.
        This is a synchronous wrapper around the async inference loop.
        """
        start_time = time.time()

        try:
            # Get input layer shape from the model
            input_shape = self.rec_infer_model.inputs[0].shape
            
            # Preprocess the face
            if not is_aligned:
                # The _align_face function is now separate. If landmarks are available, it should be called before this.
                # Here, we just resize. A more robust flow would ensure alignment happens first.
                processed_face = self._preprocess_face_for_hailo(face_image, input_shape[1:])
            else:
                # Image is already aligned and resized
                processed_face = face_image

            # Send to inference queue and wait for result
            self.rec_input_queue.put((face_image, processed_face))
            
            # Wait for result with a timeout to prevent indefinite blocking
            try:
                original_frame_ignored, raw_output = self.rec_output_queue.get(timeout=2.0)
                if raw_output is None:
                    raise RuntimeError("Inference job failed and returned no output.")
            except queue.Empty:
                logger.error("Timeout waiting for recognition inference result.")
                raise RuntimeError("Timeout waiting for recognition result.")

            # Post-process the raw output from the Hailo device
            # This assumes a single output from the recognition model.
            output_name = self.rec_infer_model.outputs[0].name
            raw_vector = raw_output[output_name].flatten()

            # Dequantize the output if quantization info is available
            if output_name in self.rec_quant_infos:
                scale, zp = self.rec_quant_infos[output_name]
                vector_dequantized = (raw_vector.astype(np.float32) - zp) * scale
            else:
                # Fallback if quant_info is not found (though it should be)
                vector_dequantized = raw_vector.astype(np.float32)

            # L2 Normalization
            norm = np.linalg.norm(vector_dequantized)
            if norm == 0:
                # Handle zero-vector case to avoid division by zero
                normalized_vector = np.zeros_like(vector_dequantized)
            else:
                normalized_vector = vector_dequantized / norm

            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            
            return normalized_vector, processing_time_ms, confidence

        except Exception as e:
            logger.error(f"Error during embedding extraction: {e}", exc_info=True)
            # Return a zero vector on failure as a safe default
            return np.zeros(512), 0, 0.0

    async def extract_embedding(self, request: EmbedRequest) -> Tuple[List[float], int, float]:
        """High-level function to handle a single embedding request."""
        image = self._decode_image(request.image_base64)

        if request.landmarks and len(request.landmarks) == 5:
            # Align the original, full-resolution image first
            aligned_face_full_res = self._align_face(image, request.landmarks)
            # The pre-processing step will handle resizing
            face_to_embed = aligned_face_full_res
            # Since we are aligning, confidence is assumed to be high
            confidence = 1.0 
            is_aligned = True
        else:
            # Fallback to simple crop if no landmarks are provided
            logger.warning("No landmarks provided. Falling back to simple crop. Results may be less accurate.")
            face_to_embed, confidence = self._crop_face(image, request.bbox)
            is_aligned = False
        
        # Run in executor to avoid blocking the event loop with synchronous Hailo calls
        loop = asyncio.get_running_loop()
        vector, processing_time, final_confidence = await loop.run_in_executor(
            None, self._extract_embedding_hailo, face_to_embed, confidence, is_aligned
        )
        return vector.tolist(), processing_time, final_confidence

    async def extract_embeddings_batch(self, requests: List[EmbedRequest]) -> Tuple[List[List[float]], List[int]]:
        """Handles batch embedding requests."""
        # Note: This is a simple sequential implementation. For true batching,
        # the Hailo inference loop needs to be adapted to handle batches.
        vectors = []
        processing_times = []
        for req in requests:
            vector, ptime, _ = await self.extract_embedding(req)
            vectors.append(vector)
            processing_times.append(ptime)
        return vectors, processing_times

    def _preprocess_image_for_detection(self, image: np.ndarray) -> Tuple[np.ndarray, float, Tuple[int, int]]:
        """Preprocesses an image for the SCRFD detection model."""
        img_h, img_w = image.shape[:2]
        
        # Assuming model input is 640x640 for scrfd_10g
        input_shape = self.det_infer_model.inputs[0].shape
        model_h, model_w = input_shape[1], input_shape[2]

        scale = min(model_h / img_h, model_w / img_w)
        scaled_w, scaled_h = int(img_w * scale), int(img_h * scale)
        
        scaled_img = cv2.resize(image, (scaled_w, scaled_h), interpolation=cv2.INTER_LINEAR)
        
        # Pad to model input size
        padded_img = np.zeros((model_h, model_w, 3), dtype=np.uint8)
        padded_img[:scaled_h, :scaled_w, :] = scaled_img
        
        offset = ( (model_w - scaled_w) // 2, (model_h - scaled_h) // 2 )

        # HWC -> CHW and add batch dimension
        chw_img = np.transpose(padded_img, (2, 0, 1))
        
        return np.expand_dims(chw_img, axis=0).astype(np.uint8), scale, offset

    def _non_maximum_suppression(self, boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> List[int]:
        """
        Performs Non-Maximum Suppression (NMS) on bounding boxes.
        
        Args:
            boxes (np.ndarray): Bounding boxes, shape (N, 4) -> (x1, y1, x2, y2).
            scores (np.ndarray): Confidence scores for each box, shape (N,).
            iou_threshold (float): IoU threshold for suppression.

        Returns:
            List[int]: List of indices of the boxes to keep.
        """
        if boxes.size == 0:
            return []

        x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]

        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)

            # Calculate IoU
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            intersection = w * h
            
            union = areas[i] + areas[order[1:]] - intersection
            iou = intersection / (union + 1e-8)

            # Keep boxes with IoU less than the threshold
            inds = np.where(iou <= iou_threshold)[0]
            order = order[inds + 1]

        return keep

    def _generate_anchors(self, model_input_shape: Tuple[int, int], strides: List[int] = [8, 16, 32], num_anchors: int = 2) -> Dict[int, np.ndarray]:
        """
        Generates anchors for each stride for the SCRFD model.
        This should be pre-calculated and cached for efficiency.
        """
        h, w = model_input_shape
        anchors_by_stride = {}
        for stride in strides:
            feature_h, feature_w = h // stride, w // stride
            
            # Create a grid of anchor centers
            x_centers = (np.arange(feature_w) + 0.5) * stride
            y_centers = (np.arange(feature_h) + 0.5) * stride
            
            xv, yv = np.meshgrid(x_centers, y_centers)
            grid = np.stack((xv, yv), axis=-1).reshape(-1, 2)
            
            # Repeat for each anchor at a given location
            # SCRFD has 2 anchors per location
            all_anchors = np.repeat(grid, num_anchors, axis=0)
            anchors_by_stride[stride] = all_anchors

        return anchors_by_stride

    def _parse_detection_results(self, 
                                 raw_outputs: Dict[str, np.ndarray], 
                                 original_image_shape: Tuple[int, int],
                                 model_input_shape: Tuple[int, int],
                                 scale: float, 
                                 offset: Tuple[int, int], 
                                 confidence_threshold: float,
                                 nms_threshold: float, 
                                 min_face_size: int) -> List[DetectedFace]:
        """Parses the raw output of the SCRFD model to get final bounding boxes."""
        
        strides = [8, 16, 32]
        num_anchors = 2
        anchors = self._generate_anchors(model_input_shape)
        
        all_bboxes = []
        all_scores = []
        all_landmarks = []

        for stride in strides:
            # --- Get raw outputs ---
            # Shape is (1, H, W, num_anchors * 2) for scores, (1, H, W, num_anchors * 4) for bboxes, (1, H, W, num_anchors * 10) for landmarks
            score_tensor = raw_outputs.get(f'score_{stride}', raw_outputs.get(f'face_rpn_cls_prob_reshape_stride{stride}'))
            bbox_tensor = raw_outputs.get(f'bbox_{stride}', raw_outputs.get(f'face_rpn_bbox_pred_stride{stride}'))
            landmark_tensor = raw_outputs.get(f'landmark_{stride}', raw_outputs.get(f'face_rpn_landmark_pred_stride{stride}'))
            
            if score_tensor is None or bbox_tensor is None or landmark_tensor is None:
                logger.warning(f"Missing one of the output tensors for stride {stride}. Skipping.")
                continue

            # --- Dequantize outputs ---
            score_scale, score_zp = self.det_quant_infos.get(score_tensor.name, (1.0, 0))
            bbox_scale, bbox_zp = self.det_quant_infos.get(bbox_tensor.name, (1.0, 0))
            landmark_scale, landmark_zp = self.det_quant_infos.get(landmark_tensor.name, (1.0, 0))
            
            scores = (score_tensor.astype(np.float32) - score_zp) * score_scale
            bboxes = (bbox_tensor.astype(np.float32) - bbox_zp) * bbox_scale
            landmarks = (landmark_tensor.astype(np.float32) - landmark_zp) * landmark_scale
            
            # --- Reshape and process ---
            scores = scores.reshape(-1, 1) # Reshaping to (num_proposals, 1)
            bboxes = bboxes.reshape(-1, 4)
            landmarks = landmarks.reshape(-1, 10)

            # --- Filter by confidence threshold ---
            confident_indices = np.where(scores > confidence_threshold)[0]
            if len(confident_indices) == 0:
                continue

            scores = scores[confident_indices]
            bboxes = bboxes[confident_indices]
            landmarks = landmarks[confident_indices]
            stride_anchors = anchors[stride][confident_indices]
            
            # --- Decode bounding boxes ---
            # bboxes are deltas (dx, dy, dw, dh), need to apply to anchors
            # Anchor centers are (cx, cy)
            anchor_cx, anchor_cy = stride_anchors[:, 0], stride_anchors[:, 1]
            
            # Box centers
            pred_cx = anchor_cx + bboxes[:, 0] * stride
            pred_cy = anchor_cy + bboxes[:, 1] * stride
            
            # Box width/height
            pred_w = np.exp(bboxes[:, 2]) * stride
            pred_h = np.exp(bboxes[:, 3]) * stride

            # Convert to (x1, y1, x2, y2)
            x1 = pred_cx - pred_w * 0.5
            y1 = pred_cy - pred_h * 0.5
            x2 = pred_cx + pred_w * 0.5
            y2 = pred_cy + pred_h * 0.5
            decoded_bboxes = np.vstack([x1, y1, x2, y2]).T

            # --- Decode landmarks ---
            # Landmarks are deltas relative to anchor centers
            decoded_landmarks = np.zeros_like(landmarks)
            for i in range(5):
                decoded_landmarks[:, i*2]   = anchor_cx + landmarks[:, i*2] * stride # x
                decoded_landmarks[:, i*2+1] = anchor_cy + landmarks[:, i*2+1] * stride # y

            all_bboxes.append(decoded_bboxes)
            all_scores.append(scores.flatten())
            all_landmarks.append(decoded_landmarks)

        if not all_bboxes:
            return []

        # --- Combine results from all strides ---
        final_bboxes = np.concatenate(all_bboxes)
        final_scores = np.concatenate(all_scores)
        final_landmarks = np.concatenate(all_landmarks)

        # --- Scale back to original image coordinates ---
        img_h, img_w = original_image_shape
        final_bboxes /= scale
        final_landmarks /= scale

        # Clip to image boundaries
        final_bboxes[:, 0::2] = np.clip(final_bboxes[:, 0::2], 0, img_w)
        final_bboxes[:, 1::2] = np.clip(final_bboxes[:, 1::2], 0, img_h)
        final_landmarks[:, 0::2] = np.clip(final_landmarks[:, 0::2], 0, img_w)
        final_landmarks[:, 1::2] = np.clip(final_landmarks[:, 1::2], 0, img_h)

        # --- Apply Non-Maximum Suppression (NMS) ---
        keep_indices = self._non_maximum_suppression(final_bboxes, final_scores, nms_threshold)
        
        # --- Format final results ---
        detected_faces = []
        for idx in keep_indices:
            bbox = final_bboxes[idx]
            landmarks_raw = final_landmarks[idx]
            
            x1, y1, x2, y2 = bbox
            w, h = x2 - x1, y2 - y1

            # Filter by min face size
            if w < min_face_size or h < min_face_size:
                continue

            detected_faces.append(
                DetectedFace(
                    bbox=BBoxModel(x=int(x1), y=int(y1), w=int(w), h=int(h)),
                    landmarks=[LandmarkPoint(x=landmarks_raw[i*2], y=landmarks_raw[i*2+1]) for i in range(5)],
                    confidence=float(final_scores[idx])
                )
            )

        return detected_faces
        
    async def detect_faces(self, request: DetectRequest) -> Tuple[List[DetectedFace], int, int, int]:
        """High-level function to handle a single face detection request."""
        start_time = time.time()
        
        image = self._decode_image(request.image_base64)
        original_h, original_w = image.shape[:2]
        
        # Preprocess for detection model
        preprocessed_image, scale, offset = self._preprocess_image_for_detection(image)
        
        # Run inference in executor
        loop = asyncio.get_running_loop()
        
        self.det_input_queue.put((image, preprocessed_image))
        try:
            original_frame, raw_outputs = self.det_output_queue.get(timeout=2.0)
            if raw_outputs is None:
                raise RuntimeError("Detection inference job failed and returned no output.")
        except queue.Empty:
            logger.error("Timeout waiting for detection inference result.")
            raise RuntimeError("Timeout waiting for detection result.")

        # --- Debug Save Detected Image ---
        if self.debug_save_images and (time.time() - self.last_detect_save_time > self.debug_save_interval_s):
            self.last_detect_save_time = time.time()
            debug_img = original_frame.copy()
            # The drawing happens after parsing, we need the parsed results
        else:
            debug_img = None

        # Parse results
        model_input_shape = self.det_infer_model.inputs[0].shape[1:3] # H, W
        detected_faces = self._parse_detection_results(
            raw_outputs,
            (original_h, original_w),
            model_input_shape,
            scale,
            offset,
            request.confidence_threshold,
            request.nms_threshold,
            request.min_face_size
        )
        
        end_time = time.time()
        processing_time_ms = int((end_time - start_time) * 1000)

        # --- Draw on debug image and save ---
        if debug_img is not None:
            for face in detected_faces:
                b = face.bbox
                cv2.rectangle(debug_img, (b.x, b.y), (b.x + b.w, b.y + b.h), (0, 255, 0), 2)
                for lm in face.landmarks:
                    cv2.circle(debug_img, (int(lm.x), int(lm.y)), 2, (0, 0, 255), -1)
            cv2.imwrite(
                os.path.join(self.debug_image_dir, f"detected_{self.last_detect_save_time:.0f}.jpg"),
                debug_img
            )

        return detected_faces, processing_time_ms, original_w, original_h

    async def detect_and_embed(self, request: DetectRequest):
        """Combined detection and embedding endpoint."""
        # 1. Detect all faces in the image
        detected_faces, detection_time_ms, _, _ = await self.detect_faces(request)

        if not detected_faces:
            return []

        # 2. For each detected face, perform embedding
        results = []
        # Create a list of embedding tasks to run concurrently
        embedding_tasks = []

        image_full = self._decode_image(request.image_base64)

        for face in detected_faces:
            # Create an EmbedRequest for each detected face
            embed_request = EmbedRequest(
                image_base64=request.image_base64, # Pass the original image
                bbox=face.bbox,
                landmarks=face.landmarks
            )
            # Add the embedding task to the list
            embedding_tasks.append(self.extract_embedding(embed_request))
        
        # Run all embedding tasks in parallel
        embedding_results = await asyncio.gather(*embedding_tasks)

        # 3. Combine detection and embedding results
        for face, (vector, ptime, confidence) in zip(detected_faces, embedding_results):
            results.append(
                DetectAndEmbedResponseItem(
                    bbox=face.bbox,
                    landmarks=face.landmarks,
                    detection_confidence=face.confidence,
                    embedding=EmbedResponse(
                        vector=vector,
                        processing_time_ms=ptime,
                        confidence=confidence
                    )
                )
            )
        
        return results

    def get_health(self) -> HealthResponse:
        """Returns the health status of the service."""
        uptime_ms = int((time.time() - self.start_time) * 1000)
        return HealthResponse(
            status="ok",
            uptime_ms=uptime_ms,
            loaded_models=[self.face_detection_hef, self.face_recognition_hef]
        )

    def __del__(self):
        """Graceful shutdown."""
        logger.info("Shutting down FaceEmbedService...")
        if self.det_thread and self.det_thread.is_alive():
            self.det_input_queue.put(None)
            self.det_thread.join(timeout=5)
        if self.rec_thread and self.rec_thread.is_alive():
            self.rec_input_queue.put(None)
            self.rec_thread.join(timeout=5)
        
        # Clean up Hailo resources
        if self.det_infer_model:
            self.det_infer_model = None
        if self.rec_infer_model:
            self.rec_infer_model = None
        if self.target:
            self.target.release()
            self.target = None
        logger.info("FaceEmbedService shutdown complete.")

# --- FastAPI App ---

service_instance: Optional[FaceEmbedService] = None

def get_face_embed_service():
    global service_instance
    if service_instance is None:
        logger.info("Creating and initializing FaceEmbedService instance...")
        service_instance = FaceEmbedService()
        logger.info("FaceEmbedService instance created.")
    return service_instance

app = FastAPI(
    title="FaceEmbed API",
    description="A high-performance face feature extraction service based on the Hailo-8 AI accelerator.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.2f}ms")
    return response

@app.get("/health", response_model=HealthResponse)
async def health():
    """Returns the health status of the service."""
    service = get_face_embed_service()
    return service.get_health()

@app.post("/embed", response_model=EmbedResponse)
async def embed_face(request: EmbedRequest):
    """
    Extracts a 512-D embedding vector from a single face image, given its bounding box and landmarks.
    This is a manual endpoint. For an all-in-one solution, use `/detect_and_embed`.
    """
    try:
        service = get_face_embed_service()
        vector, ptime, confidence = await service.extract_embedding(request)
        return EmbedResponse(vector=vector, processing_time_ms=ptime, confidence=confidence)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in /embed endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/batch_embed", response_model=BatchEmbedResponse)
async def batch_embed_faces(request: BatchEmbedRequest):
    """
    Extracts embedding vectors from a batch of face images.
    """
    if len(request.images) > 20:
         raise HTTPException(status_code=400, detail="Batch size cannot exceed 20 images.")
    try:
        service = get_face_embed_service()
        vectors, ptimes = await service.extract_embeddings_batch(request.images)
        return BatchEmbedResponse(vectors=vectors, processing_times=ptimes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in /batch_embed endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/detect", response_model=DetectResponse)
async def detect_faces(request: DetectRequest):
    """
    Detects faces in an image and returns their bounding boxes and landmarks.
    """
    try:
        service = get_face_embed_service()
        faces, ptime, width, height = await service.detect_faces(request)
        return DetectResponse(faces=faces, processing_time_ms=ptime, image_width=width, image_height=height)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in /detect endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/detect_and_embed", response_model=List[DetectAndEmbedResponseItem])
async def detect_and_embed_faces(request: DetectRequest):
    """
    Performs both face detection and feature embedding in a single call.
    This is the recommended primary endpoint.
    """
    try:
        service = get_face_embed_service()
        results = await service.detect_and_embed(request)
        return results
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in /detect_and_embed endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/")
async def root():
    return {"message": "Welcome to the FaceEmbed API. See /docs for details."} 
