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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hailo imports
from .utils import HailoAsyncInference

# Models
class BBoxModel(BaseModel):
    x: int = Field(..., description="X coordinate")
    y: int = Field(..., description="Y coordinate") 
    w: int = Field(..., description="Width")
    h: int = Field(..., description="Height")

class EmbedRequest(BaseModel):
    image_base64: str = Field(..., description="Base64 encoded JPEG image")
    bbox: BBoxModel = Field(..., description="Face bounding box")

class BatchEmbedRequest(BaseModel):
    images: List[EmbedRequest] = Field(..., description="List of images with bboxes")

class EmbedResponse(BaseModel):
    vector: List[float] = Field(..., description="512-D face embedding vector")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    confidence: float = Field(..., description="Face quality confidence score")

class BatchEmbedResponse(BaseModel):
    vectors: List[List[float]] = Field(..., description="List of 512-D face embedding vectors")
    processing_times: List[int] = Field(..., description="Processing times in milliseconds")

class HealthResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    
    status: str = Field(..., description="Service status")
    model_loaded: bool = Field(..., description="Whether face recognition model is loaded")
    uptime_ms: int = Field(..., description="Service uptime in milliseconds")

# Face Embedding Service
class FaceEmbedService:
    def __init__(self):
        self.start_time = time.time()
        self.model_loaded = False
        self.hailo_inference = None
        self.input_queue = None
        self.output_queue = None
        self.inference_thread = None
        
        # Model paths
        self.face_recognition_hef = os.getenv(
            'FACE_RECOGNITION_HEF', 
            '/home/harvest/face_embed_api/models/arcface_mobilefacenet.hef'
        )
        
        # Initialize models
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize Hailo face recognition models"""
        try:
            # 检查模型文件是否存在
            if not os.path.exists(self.face_recognition_hef):
                raise FileNotFoundError(f"Model file not found: {self.face_recognition_hef}")
                
            # 初始化队列
            self.input_queue = queue.Queue(maxsize=10)
            self.output_queue = queue.Queue(maxsize=10)
            
            # 创建HailoAsyncInference实例
            self.hailo_inference = HailoAsyncInference(
                hef_path=self.face_recognition_hef,
                input_queue=self.input_queue,
                output_queue=self.output_queue,
                batch_size=1,
                send_original_frame=True
            )
            
            # 启动推理线程
            self.inference_thread = threading.Thread(target=self.hailo_inference.run, daemon=True)
            self.inference_thread.start()
            
            logger.info(f"Loaded Hailo model: {self.face_recognition_hef}")
            logger.info("Hailo inference thread started")
            self.model_loaded = True
                
        except Exception as e:
            logger.error(f"Failed to initialize Hailo models: {e}")
            logger.exception("Full traceback:")
            raise RuntimeError(f"Failed to initialize Hailo models: {e}")
    
    def _decode_image(self, image_base64: str) -> np.ndarray:
        """Decode base64 image to numpy array"""
        try:
            image_data = base64.b64decode(image_base64)
            image_array = np.frombuffer(image_data, dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("Failed to decode image")
            return image
        except Exception as e:
            raise ValueError(f"Invalid image data: {e}")
    
    def _crop_face(self, image: np.ndarray, bbox: BBoxModel) -> Tuple[np.ndarray, float]:
        """Crop face from image using bounding box"""
        h, w = image.shape[:2]
        
        # Validate bbox
        if bbox.x < 0 or bbox.y < 0 or bbox.x + bbox.w > w or bbox.y + bbox.h > h:
            raise ValueError("Bounding box is out of image bounds")
        
        if bbox.w <= 0 or bbox.h <= 0:
            raise ValueError("Invalid bounding box dimensions")
        
        # Crop face region
        face_image = image[bbox.y:bbox.y + bbox.h, bbox.x:bbox.x + bbox.w]
        
        # Calculate confidence based on face size and aspect ratio
        face_area = bbox.w * bbox.h
        total_area = w * h
        area_ratio = face_area / total_area
        
        # Aspect ratio score (ideal face aspect ratio ~0.75)
        aspect_ratio = bbox.h / bbox.w
        aspect_score = 1.0 - abs(aspect_ratio - 0.75) / 0.75
        
        # Size score (prefer larger faces)
        size_score = min(area_ratio * 10, 1.0)
        
        confidence = (aspect_score + size_score) / 2.0
        confidence = max(0.1, min(1.0, confidence))
        
        return face_image, confidence
    
    def _preprocess_face_for_hailo(self, face_image: np.ndarray) -> np.ndarray:
        """Preprocess face image for Hailo model"""
        # 获取模型输入尺寸
        input_shape = self.hailo_inference.get_input_shape()
        model_h, model_w = int(input_shape[0]), int(input_shape[1])  # Ensure integers
        
        # 调整尺寸
        face_resized = cv2.resize(face_image, (model_w, model_h))
        
        return face_resized
    
    def _extract_embedding_hailo(self, face_image: np.ndarray) -> np.ndarray:
        """Extract face embedding using Hailo model"""
        if not self.hailo_inference or not self.input_queue or not self.output_queue:
            raise RuntimeError("Hailo inference not initialized")
        
        # 预处理人脸图像
        preprocessed_face = self._preprocess_face_for_hailo(face_image)
        
        # 发送到推理队列
        self.input_queue.put(([face_image], [preprocessed_face]))
        
        # 获取推理结果
        try:
            original_frame, result = self.output_queue.get(timeout=5.0)
            
            # 处理结果，转换为512维向量
            if isinstance(result, dict):
                # 多输出情况，选择第一个输出
                embedding = list(result.values())[0]
            else:
                # 单输出情况
                embedding = result
            
            # 确保是numpy数组
            if not isinstance(embedding, np.ndarray):
                embedding = np.array(embedding)
            
            # 展平到1维
            embedding = embedding.flatten()
            
            # 如果不是512维，进行填充或截断
            if len(embedding) != 512:
                if len(embedding) > 512:
                    embedding = embedding[:512]
                else:
                    # 填充到512维
                    padding = np.zeros(512 - len(embedding))
                    embedding = np.concatenate([embedding, padding])
            
            # L2归一化
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            
            return embedding.astype(np.float32)
            
        except queue.Empty:
            raise RuntimeError("Hailo inference timeout")
    
    async def extract_embedding(self, image_base64: str, bbox: BBoxModel) -> Tuple[List[float], int, float]:
        """Extract face embedding from image"""
        start_time = time.time()
        
        try:
            # Decode image
            image = self._decode_image(image_base64)
            
            # Crop face
            face_image, confidence = self._crop_face(image, bbox)
            
            # Extract embedding using Hailo hardware
            embedding = self._extract_embedding_hailo(face_image)
            logger.info("Used Hailo hardware for inference")
            
            # Convert to list
            vector = embedding.tolist()
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return vector, processing_time, confidence
            
        except Exception as e:
            logger.error(f"Face embedding extraction failed: {e}")
            raise HTTPException(status_code=400, detail=str(e))
    
    async def extract_embeddings_batch(self, requests: List[EmbedRequest]) -> Tuple[List[List[float]], List[int]]:
        """Extract face embeddings for multiple images"""
        vectors = []
        processing_times = []
        
        for req in requests:
            vector, proc_time, _ = await self.extract_embedding(req.image_base64, req.bbox)
            vectors.append(vector)
            processing_times.append(proc_time)
        
        return vectors, processing_times
    
    def get_health(self) -> HealthResponse:
        """Get service health status"""
        uptime_ms = int((time.time() - self.start_time) * 1000)
        
        return HealthResponse(
            status="ok" if self.model_loaded else "model_loading",
            model_loaded=self.model_loaded,
            uptime_ms=uptime_ms
        )
    
    def __del__(self):
        """Cleanup resources"""
        if self.input_queue:
            try:
                self.input_queue.put(None)  # Stop signal
            except:
                pass

# Global service instance - will be initialized lazily
face_embed_service = None

def get_face_embed_service():
    """Get or create face embed service instance"""
    global face_embed_service
    if face_embed_service is None:
        face_embed_service = FaceEmbedService()
    return face_embed_service

# FastAPI app with optimized settings for concurrent access
app = FastAPI(
    title="FaceEmbed API",
    description="基于Hailo-8的人脸特征提取服务 - 支持多设备并发访问",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware - optimized for cross-machine access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许Node-RED服务器跨域访问
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
    return response

# Routes
@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    return get_face_embed_service().get_health()

@app.post("/embed", response_model=EmbedResponse)
async def embed_face(request: EmbedRequest):
    """Extract face embedding from single image"""
    service = get_face_embed_service()
    vector, processing_time, confidence = await service.extract_embedding(
        request.image_base64, request.bbox
    )
    
    return EmbedResponse(
        vector=vector,
        processing_time_ms=processing_time,
        confidence=confidence
    )

@app.post("/batch_embed", response_model=BatchEmbedResponse)
async def batch_embed_faces(request: BatchEmbedRequest):
    """Extract face embeddings from multiple images"""
    if len(request.images) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 images per batch")
    
    service = get_face_embed_service()
    vectors, processing_times = await service.extract_embeddings_batch(request.images)
    
    return BatchEmbedResponse(
        vectors=vectors,
        processing_times=processing_times
    )

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "FaceEmbed API", "version": "1.0.0", "status": "running"}
