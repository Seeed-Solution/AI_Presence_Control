#!/usr/bin/env python3
"""
FaceEmbed API单元测试
测试人脸嵌入API的各种功能和边界情况
"""

import unittest
import base64
import tempfile
import os
import json
import time
import sys
from typing import List
import asyncio

import cv2
import numpy as np
from fastapi import HTTPException
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# Mock Hailo platform before importing
sys.modules['hailo_platform'] = MagicMock()

from app import (
    app, FaceEmbedService, get_face_embed_service, BBoxModel, DetectRequest,
    DetectedFace, LandmarkPoint, EmbedRequest, HealthResponse
)


class TestFaceEmbedAPI(unittest.TestCase):
    """FaceEmbed API端到端测试 - Mocks the entire service layer"""
    
    @classmethod
    def setUpClass(cls):
        """设置测试类"""
        cls.client = TestClient(app)
    
    def setUp(self):
        """测试准备"""
        self.test_image = self._create_test_image()
        self.test_image_base64 = self._image_to_base64(self.test_image)
        self.valid_bbox = BBoxModel(x=50, y=50, w=100, h=120)
        
    def _create_test_image(self, width=300, height=300):
        """创建测试图像"""
        # 创建白色背景
        image = np.ones((height, width, 3), dtype=np.uint8) * 255
        
        # 在中心添加一个灰色矩形作为"人脸"
        face_x, face_y = 50, 50
        face_w, face_h = 100, 120
        cv2.rectangle(image, (face_x, face_y), (face_x + face_w, face_y + face_h), (128, 128, 128), -1)
        
        return image
    
    def _image_to_base64(self, image):
        """将图像转换为base64编码"""
        _, buffer = cv2.imencode('.jpg', image)
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        return image_base64
    
    @patch('app.get_face_embed_service')
    def test_health_endpoint(self, mock_get_service):
        """测试健康检查端点"""
        mock_service = Mock(spec=FaceEmbedService)
        mock_service.get_health.return_value = HealthResponse(
            status="ok",
            uptime_ms=1000,
            loaded_models=["mock_model1.hef", "mock_model2.hef"]
        )
        mock_get_service.return_value = mock_service
        
        response = self.client.get("/health")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # 验证响应结构
        self.assertIn("status", data)
        self.assertIn("uptime_ms", data)
        self.assertIn("loaded_models", data)
        
        # 验证数据类型
        self.assertIsInstance(data["uptime_ms"], int)
        self.assertTrue(data["uptime_ms"] >= 0)
        self.assertIsInstance(data["loaded_models"], list)
    
    def test_root_endpoint(self):
        """测试根端点"""
        response = self.client.get("/")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # 验证基本信息
        self.assertIn("message", data)
        self.assertIn("version", data)
        self.assertIn("status", data)
        self.assertEqual(data["message"], "FaceEmbed API")
    
    @patch('app.get_face_embed_service')
    def test_embed_endpoint_valid_request(self, mock_get_service):
        """测试有效的人脸嵌入请求"""
        mock_service = Mock(spec=FaceEmbedService)
        # Mock extract_embedding to return a valid 512-D normalized vector
        mock_vector = np.random.normal(0, 1, 512).astype(np.float32)
        mock_vector = mock_vector / np.linalg.norm(mock_vector)
        
        async def mock_extract_embedding(request):
            return mock_vector.tolist(), 10, 0.8
        mock_service.extract_embedding = mock_extract_embedding
        mock_get_service.return_value = mock_service
        
        request_data = {
            "image_base64": self.test_image_base64,
            "bbox": {
                "x": self.valid_bbox.x,
                "y": self.valid_bbox.y,
                "w": self.valid_bbox.w,
                "h": self.valid_bbox.h
            }
        }
        
        response = self.client.post("/embed", json=request_data)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # 验证响应结构
        self.assertIn("vector", data)
        self.assertIn("processing_time_ms", data)
        self.assertIn("confidence", data)
        
        # 验证向量
        vector = data["vector"]
        self.assertEqual(len(vector), 512)
        
        # 验证向量归一化
        norm = np.linalg.norm(np.array(vector))
        self.assertAlmostEqual(norm, 1.0, places=6)
        
        # 验证置信度范围
        confidence = data["confidence"]
        self.assertTrue(0.0 <= confidence <= 1.0)
        
        # 验证处理时间
        processing_time = data["processing_time_ms"]
        self.assertIsInstance(processing_time, int)
        self.assertTrue(processing_time > 0)
    
    @patch('app.get_face_embed_service')
    def test_embed_endpoint_invalid_bbox(self, mock_get_service):
        """测试无效边界框的人脸嵌入"""
        # Mock service to raise ValueError for invalid bbox
        async def mock_extract_embedding_error(request):
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Bounding box is out of image bounds")
            
        mock_service = Mock(spec=FaceEmbedService)
        mock_service.extract_embedding = mock_extract_embedding_error
        mock_get_service.return_value = mock_service
        
        request_data = {
            "image_base64": self.test_image_base64,
            "bbox": {
                "x": -10,  # 无效坐标
                "y": -10,
                "w": 50,
                "h": 50
            }
        }
        
        response = self.client.post("/embed", json=request_data)
        self.assertEqual(response.status_code, 400)
    
    def test_embed_endpoint_invalid_image(self):
        """测试无效的图像数据"""
        request_data = {
            "image_base64": "invalid_base64_data",
            "bbox": {
                "x": self.valid_bbox.x,
                "y": self.valid_bbox.y,
                "w": self.valid_bbox.w,
                "h": self.valid_bbox.h
            }
        }
        
        response = self.client.post("/embed", json=request_data)
        self.assertEqual(response.status_code, 400)
    
    def test_embed_endpoint_missing_fields(self):
        """测试缺少必要字段的请求"""
        # 缺少bbox字段
        request_data = {
            "image_base64": self.test_image_base64
        }
        
        response = self.client.post("/embed", json=request_data)
        self.assertEqual(response.status_code, 422)  # Validation error
    
    @patch('app.get_face_embed_service')
    def test_batch_embed_endpoint(self, mock_get_service):
        """测试批量人脸嵌入"""
        mock_service = Mock(spec=FaceEmbedService)
        mock_vector = np.random.normal(0, 1, 512).astype(np.float32)
        mock_vector = mock_vector / np.linalg.norm(mock_vector)

        async def mock_extract_embeddings_batch(requests):
            vectors = []
            processing_times = []
            for _ in requests:
                vectors.append(mock_vector.tolist())
                processing_times.append(10)
            return vectors, processing_times
        mock_service.extract_embeddings_batch = mock_extract_embeddings_batch
        mock_get_service.return_value = mock_service
        
        # 创建多个测试图像
        images = []
        for i in range(3):
            image = self._create_test_image()
            image_base64 = self._image_to_base64(image)
            images.append({
                "image_base64": image_base64,
                "bbox": {
                    "x": self.valid_bbox.x,
                    "y": self.valid_bbox.y,
                    "w": self.valid_bbox.w,
                    "h": self.valid_bbox.h
                }
            })
        
        request_data = {"images": images}
        
        response = self.client.post("/batch_embed", json=request_data)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # 验证响应结构
        self.assertIn("vectors", data)
        self.assertIn("processing_times", data)
        
        # 验证批量结果
        self.assertEqual(len(data["vectors"]), 3)
        self.assertEqual(len(data["processing_times"]), 3)
        
        # 验证每个向量
        for vector in data["vectors"]:
            self.assertEqual(len(vector), 512)
            norm = np.linalg.norm(np.array(vector))
            self.assertAlmostEqual(norm, 1.0, places=6)
    
    @patch('app.get_face_embed_service')
    def test_batch_embed_too_many_images(self, mock_get_service):
        """测试批量嵌入请求数量过多"""
        # The endpoint itself should raise an HTTPException for too many images
        # before the service is even called.
        async def mock_batch_embed(requests):
            # This should not be called
            return [], []

        mock_service = Mock(spec=FaceEmbedService)
        mock_service.extract_embeddings_batch = mock_batch_embed
        mock_get_service.return_value = mock_service
        
        images = [{"image_base64": "test", "bbox": {"x":0,"y":0,"w":1,"h":1}}] * 21
        request_data = {"images": images}
        
        response = self.client.post("/batch_embed", json=request_data)
        self.assertEqual(response.status_code, 400) # As defined in the endpoint logic

    @patch('app.get_face_embed_service')
    def test_detect_and_embed_endpoint(self, mock_get_service):
        """测试检测和嵌入端点"""
        mock_service = Mock(spec=FaceEmbedService)
        
        # Mock the combined service function
        async def mock_detect_and_embed(request):
            mock_vector = np.random.rand(512).tolist()
            return [
                {
                    "bbox": {"x": 10, "y": 10, "w": 50, "h": 50},
                    "landmarks": [{"x": 0, "y": 0}] * 5,
                    "detection_confidence": 0.99,
                    "embedding": {
                        "vector": mock_vector,
                        "processing_time_ms": 15,
                        "confidence": 0.9
                    }
                }
            ]
        
        mock_service.detect_and_embed = mock_detect_and_embed
        mock_get_service.return_value = mock_service

        request_data = {"image_base64": self.test_image_base64}
        response = self.client.post("/detect_and_embed", json=request_data)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertIn("embedding", data[0])
        self.assertEqual(len(data[0]["embedding"]["vector"]), 512)


class TestFaceEmbedService(unittest.TestCase):
    """Tests the FaceEmbedService class logic directly"""
    
    @patch('app.FaceEmbedService._initialize_hailo_device')
    def setUp(self, mock_init_hailo):
        """Setup a FaceEmbedService instance before each test"""
        # Prevent Hailo initialization during unit tests
        mock_init_hailo.return_value = None
        
        # We need to manually create the service to test its methods
        self.service = FaceEmbedService()
        
        # Mock the internal HailoAsyncInference instances if they are created
        self.service.det_infer_model = MagicMock()
        self.service.rec_infer_model = MagicMock()
        self.service.det_input_queue = MagicMock()
        self.service.det_output_queue = MagicMock()
        self.service.rec_input_queue = MagicMock()
        self.service.rec_output_queue = MagicMock()

    def tearDown(self):
        """Cleanup after each test"""
        # Clean up any created debug files
        if self.service.debug_save_images:
            for f in os.listdir(self.service.debug_image_dir):
                os.remove(os.path.join(self.service.debug_image_dir, f))

    def _create_test_image(self):
        return np.ones((100, 100, 3), dtype=np.uint8) * 255

    def _image_to_base64(self, image):
        _, buffer = cv2.imencode('.jpg', image)
        return base64.b64encode(buffer).decode('utf-8')

    def test_decode_image_valid(self):
        """测试有效的base64图像解码"""
        image = self._create_test_image()
        b64_str = self._image_to_base64(image)
        decoded_image = self.service._decode_image(b64_str)
        self.assertIsInstance(decoded_image, np.ndarray)
        self.assertEqual(decoded_image.shape, (100, 100, 3))

    def test_decode_image_invalid(self):
        """测试无效的base64图像解码"""
        with self.assertRaises(ValueError):
            self.service._decode_image("invalid-base64")

    def test_crop_face_valid(self):
        """测试有效的人脸裁剪"""
        image = self._create_test_image()
        bbox = BBoxModel(x=10, y=10, w=50, h=50)
        cropped, confidence = self.service._crop_face(image, bbox)
        self.assertEqual(cropped.shape, (50, 50, 3))
        self.assertEqual(confidence, 1.0)

    def test_crop_face_invalid_bbox(self):
        """测试无效的BBox进行裁剪"""
        with self.assertRaises(ValueError):
            self.service._crop_face(self._create_test_image(), BBoxModel(x=10, y=10, w=0, h=50))

    def test_crop_face_out_of_bounds(self):
        """测试部分在图像外的BBox"""
        image = self._create_test_image() # 100x100
        bbox = BBoxModel(x=80, y=80, w=50, h=50) # Goes up to 130x130
        cropped, confidence = self.service._crop_face(image, bbox)
        self.assertEqual(cropped.shape, (20, 20, 3)) # Should be clipped to 20x20
        self.assertLess(confidence, 1.0)

    def test_preprocess_face_for_hailo(self):
        """Test the preprocessing pipeline for face embedding."""
        face_image = np.zeros((112, 112, 3), dtype=np.uint8)
        
        # Mock model input shape
        model_shape = (1, 3, 112, 112)
        
        # Since _initialize_hailo_device is mocked, we need to mock the model info
        self.service.rec_infer_model.inputs = [Mock()]
        self.service.rec_infer_model.inputs[0].shape = model_shape

        processed_face = self.service._preprocess_face_for_hailo(face_image, model_shape[1:])
        
        # Check shape, should be (1, C, H, W)
        self.assertEqual(processed_face.shape, model_shape)
        self.assertEqual(processed_face.dtype, np.uint8)

    def test_get_health(self):
        """Test service health check logic"""
        health_status = self.service.get_health()
        self.assertEqual(health_status.status, "ok")
        self.assertGreater(health_status.uptime_ms, 0)

    # This test is more complex as it involves the full async machinery
    @patch('app.queue.Queue')
    def test_detect_faces_logic(self, mock_queue):
        """Test the core logic of face detection, mocking the queue"""
        # This is a simplified test case. A full test would be an integration test.
        request = DetectRequest(image_base64=self._image_to_base64(self._create_test_image()))
        
        # Mock the model to return some dummy raw output
        raw_output = { 'score_8': np.random.rand(1, 80, 80, 2).astype(np.uint8) }
        
        # Mock the queue to return our dummy output
        mock_output_queue = MagicMock()
        mock_output_queue.get.return_value = (self._create_test_image(), raw_output)
        self.service.det_output_queue = mock_output_queue

        # Mock the model's quantization info
        self.service.det_quant_infos = {
            'score_8': (0.01, 0),
            'bbox_8': (0.1, 0),
            'landmark_8': (0.1, 0)
        }

        # Mock the model's hef info
        mock_hef = MagicMock()
        mock_hef.get_output_vstream_infos.return_value = []
        self.service.det_infer_model.hef = mock_hef
        self.service.det_infer_model.outputs = [Mock(name="score_8")]

        # This test can't fully run without a running event loop and Hailo device
        # but we can check that it doesn't crash and returns a list.
        # result = asyncio.run(self.service.detect_faces(request))
        # self.assertIsInstance(result, tuple)


class TestBBoxModel(unittest.TestCase):
    """Tests the Pydantic BBoxModel"""
    def test_valid_bbox(self):
        """Test valid BBox creation"""
        bbox = BBoxModel(x=10, y=20, w=30, h=40)
        self.assertEqual(bbox.x, 10)
        self.assertEqual(bbox.y, 20)
        self.assertEqual(bbox.w, 30)
        self.assertEqual(bbox.h, 40)

    def test_bbox_validation(self):
        """Test Pydantic validation for BBox"""
        with self.assertRaises(ValueError):
            # w and h must be positive in the service logic, but Pydantic allows 0
            # Our internal logic should catch this. Pydantic checks for type.
            BBoxModel(x=10, y=10, w="a", h=10)


if __name__ == '__main__':
    unittest.main()
