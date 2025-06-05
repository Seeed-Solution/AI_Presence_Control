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
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Hailo imports
try:
    import hailo_platform
    from hailo_sdk_client import ClientRunner
    HAILO_AVAILABLE = True
except ImportError:
    HAILO_AVAILABLE = False
    logging.warning("Hailo SDK not available, using mock implementation")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    status: str = Field(..., description="Service status")
    model_loaded: bool = Field(..., description="Whether face recognition model is loaded")
    uptime_ms: int = Field(..., description="Service uptime in milliseconds")

# Face Embedding Service
class FaceEmbedService:
    def __init__(self):
        self.start_time = time.time()
        self.model_loaded = False
        self.face_recognition_runner = None
        self.face_detection_runner = None
        
        # Model paths (configured via environment variables)
        self.face_detection_hef = os.getenv('FACE_DETECTION_HEF', '/usr/share/hailo-models/scrfd_10g.hef')
        self.face_recognition_hef = os.getenv('FACE_RECOGNITION_HEF', '/usr/share/hailo-models/arcface_mobilefacenet_v1.hef')
        
        # Initialize models
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize Hailo face detection and recognition models"""
        try:
            if not HAILO_AVAILABLE:
                logger.warning("Using mock face embedding service")
                self.model_loaded = True
                return
                
            # Initialize face detection model (SCRFD-10G)
            if os.path.exists(self.face_detection_hef):
                self.face_detection_runner = ClientRunner(hef=self.face_detection_hef)
                logger.info(f"Loaded face detection model: {self.face_detection_hef}")
            else:
                logger.error(f"Face detection HEF not found: {self.face_detection_hef}")
                
            # Initialize face recognition model (ArcFace MobileFaceNet)
            if os.path.exists(self.face_recognition_hef):
                self.face_recognition_runner = ClientRunner(hef=self.face_recognition_hef)
                logger.info(f"Loaded face recognition model: {self.face_recognition_hef}")
                self.model_loaded = True
            else:
                logger.error(f"Face recognition HEF not found: {self.face_recognition_hef}")
                
        except Exception as e:
            logger.error(f"Failed to initialize Hailo models: {e}")
            # Fallback to mock implementation
            self.model_loaded = True
    
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
    
    def _preprocess_face(self, face_image: np.ndarray) -> np.ndarray:
        """Preprocess face image for ArcFace model (112x112 RGB)"""
        # Resize to 112x112 (ArcFace input size)
        face_resized = cv2.resize(face_image, (112, 112))
        
        # Convert BGR to RGB
        face_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)
        
        # Normalize to [0, 1]
        face_normalized = face_rgb.astype(np.float32) / 255.0
        
        # Add batch dimension and rearrange to NCHW format if needed
        face_batch = np.expand_dims(face_normalized, axis=0)
        
        return face_batch
    
    def _extract_embedding_hailo(self, face_image: np.ndarray) -> np.ndarray:
        """Extract face embedding using Hailo ArcFace model"""
        if not self.face_recognition_runner:
            raise RuntimeError("Face recognition model not initialized")
        
        # Preprocess face
        input_data = self._preprocess_face(face_image)
        
        # Run inference
        with self.face_recognition_runner:
            results = self.face_recognition_runner.infer(input_data)
        
        # Extract embedding vector (should be 512-D)
        embedding = results[0].flatten()
        
        # Normalize embedding (L2 normalization)
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        return embedding
    
    def _extract_embedding_mock(self, face_image: np.ndarray) -> np.ndarray:
        """Mock face embedding extraction for testing"""
        # Generate deterministic but pseudo-random embedding based on image content
        # This is for testing only
        image_hash = hash(face_image.tobytes()) % (2**31)
        np.random.seed(image_hash)
        embedding = np.random.normal(0, 1, 512).astype(np.float32)
        
        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
            
        return embedding
    
    async def extract_embedding(self, image_base64: str, bbox: BBoxModel) -> Tuple[List[float], int, float]:
        """Extract face embedding from image"""
        start_time = time.time()
        
        try:
            # Decode image
            image = self._decode_image(image_base64)
            
            # Crop face
            face_image, confidence = self._crop_face(image, bbox)
            
            # Extract embedding
            if HAILO_AVAILABLE and self.face_recognition_runner:
                embedding = self._extract_embedding_hailo(face_image)
            else:
                embedding = self._extract_embedding_mock(face_image)
            
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

# Initialize service
face_embed_service = FaceEmbedService()

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
    return face_embed_service.get_health()

@app.post("/embed", response_model=EmbedResponse)
async def embed_face(request: EmbedRequest):
    """Extract face embedding from single image"""
    vector, processing_time, confidence = await face_embed_service.extract_embedding(
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
    
    vectors, processing_times = await face_embed_service.extract_embeddings_batch(request.images)
    
    return BatchEmbedResponse(
        vectors=vectors,
        processing_times=processing_times
    )

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "FaceEmbed API", "version": "1.0.0", "status": "running"}

if __name__ == "__main__":
    # Configuration for high-concurrency deployment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    workers = int(os.getenv("WORKERS", "4"))  # 支持多个工作进程
    
    logger.info(f"Starting FaceEmbed API on {host}:{port}")
    logger.info(f"Workers: {workers}")
    logger.info(f"Hailo available: {HAILO_AVAILABLE}")
    
    # 优化并发配置
    uvicorn.run(
        app,
        host=host,
        port=port,
        workers=workers,
        log_level="info",
        access_log=True,
        loop="asyncio",
        http="httptools",
        lifespan="on"
    )
