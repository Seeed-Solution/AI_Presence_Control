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

import cv2
import numpy as np
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# Mock Hailo platform before importing
sys.modules['hailo_platform'] = MagicMock()

from face_embed_api.app import app, FaceEmbedService, get_face_embed_service
from face_embed_api.app import BBoxModel


class TestFaceEmbedAPI(unittest.TestCase):
    """FaceEmbed API端到端测试"""
    
    @classmethod
    def setUpClass(cls):
        """设置测试类"""
        cls.client = TestClient(app)
    
    def setUp(self):
        """测试准备"""
        self.test_image = self._create_test_image()
        self.test_image_base64 = self._image_to_base64(self.test_image)
        self.valid_bbox = BBoxModel(x=50, y=50, w=100, h=120)
        
        # Mock the service to avoid real Hailo initialization
        self.mock_service = Mock(spec=FaceEmbedService)
        self.mock_service.get_health.return_value = Mock(
            status="ok",
            model_loaded=True,
            uptime_ms=1000,
            model_dump=lambda: {"status": "ok", "model_loaded": True, "uptime_ms": 1000}
        )
        
        # Mock extract_embedding to return a valid 512-D normalized vector
        mock_vector = np.random.normal(0, 1, 512).astype(np.float32)
        mock_vector = mock_vector / np.linalg.norm(mock_vector)
        
        async def mock_extract_embedding(image_base64, bbox):
            return mock_vector.tolist(), 10, 0.8
            
        self.mock_service.extract_embedding = mock_extract_embedding
        
        async def mock_extract_embeddings_batch(requests):
            vectors = []
            processing_times = []
            for _ in requests:
                vectors.append(mock_vector.tolist())
                processing_times.append(10)
            return vectors, processing_times
            
        self.mock_service.extract_embeddings_batch = mock_extract_embeddings_batch
    
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
    
    @patch('face_embed_api.app.get_face_embed_service')
    def test_health_endpoint(self, mock_get_service):
        """测试健康检查端点"""
        mock_get_service.return_value = self.mock_service
        
        response = self.client.get("/health")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # 验证响应结构
        self.assertIn("status", data)
        self.assertIn("model_loaded", data)
        self.assertIn("uptime_ms", data)
        
        # 验证数据类型
        self.assertIsInstance(data["model_loaded"], bool)
        self.assertIsInstance(data["uptime_ms"], int)
        self.assertTrue(data["uptime_ms"] >= 0)
    
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
    
    @patch('face_embed_api.app.get_face_embed_service')
    def test_embed_endpoint_valid_request(self, mock_get_service):
        """测试有效的人脸嵌入请求"""
        mock_get_service.return_value = self.mock_service
        
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
    
    @patch('face_embed_api.app.get_face_embed_service')
    def test_embed_endpoint_invalid_bbox(self, mock_get_service):
        """测试无效边界框的人脸嵌入"""
        # Mock service to raise ValueError for invalid bbox
        async def mock_extract_embedding_error(image_base64, bbox):
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
    
    @patch('face_embed_api.app.get_face_embed_service')
    def test_batch_embed_endpoint(self, mock_get_service):
        """测试批量人脸嵌入"""
        mock_get_service.return_value = self.mock_service
        
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
    
    def test_batch_embed_too_many_images(self):
        """测试批量请求图像数量超限"""
        # 创建超过限制的图像数量
        images = []
        for i in range(11):  # 超过最大10张的限制
            images.append({
                "image_base64": self.test_image_base64,
                "bbox": {
                    "x": self.valid_bbox.x,
                    "y": self.valid_bbox.y,
                    "w": self.valid_bbox.w,
                    "h": self.valid_bbox.h
                }
            })
        
        request_data = {"images": images}
        
        response = self.client.post("/batch_embed", json=request_data)
        self.assertEqual(response.status_code, 400)


class TestFaceEmbedService(unittest.TestCase):
    """FaceEmbedService单元测试"""
    
    @patch('face_embed_api.utils.HailoAsyncInference')
    @patch('os.path.exists')
    def setUp(self, mock_exists, mock_hailo_inference):
        """测试准备"""
        mock_exists.return_value = True  # Mock model file exists
        
        # Mock Hailo inference
        mock_inference_instance = Mock()
        mock_inference_instance.get_input_shape.return_value = (224, 224, 3)  # Return actual tuple
        mock_inference_instance.run = Mock()  # Mock the run method to avoid thread issues
        mock_hailo_inference.return_value = mock_inference_instance
        
        self.service = FaceEmbedService()
        self.test_image = self._create_test_image()
        self.valid_bbox = BBoxModel(x=50, y=50, w=100, h=120)
    
    def _create_test_image(self):
        """创建测试图像"""
        image = np.ones((300, 300, 3), dtype=np.uint8) * 255
        cv2.rectangle(image, (50, 50), (150, 170), (128, 128, 128), -1)
        return image
    
    def test_decode_image_valid(self):
        """测试有效图像解码"""
        _, buffer = cv2.imencode('.jpg', self.test_image)
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        
        decoded_image = self.service._decode_image(image_base64)
        
        self.assertIsInstance(decoded_image, np.ndarray)
        self.assertEqual(len(decoded_image.shape), 3)  # H, W, C
    
    def test_decode_image_invalid(self):
        """测试无效图像解码"""
        with self.assertRaises(ValueError):
            self.service._decode_image("invalid_base64")
    
    def test_crop_face_valid(self):
        """测试有效的人脸裁剪"""
        face_image, confidence = self.service._crop_face(self.test_image, self.valid_bbox)
        
        self.assertIsInstance(face_image, np.ndarray)
        self.assertEqual(face_image.shape[:2], (self.valid_bbox.h, self.valid_bbox.w))
        self.assertTrue(0.0 <= confidence <= 1.0)
    
    def test_crop_face_invalid_bbox(self):
        """测试无效边界框的人脸裁剪"""
        invalid_bbox = BBoxModel(x=-10, y=-10, w=50, h=50)  # 负坐标
        
        with self.assertRaises(ValueError):
            self.service._crop_face(self.test_image, invalid_bbox)
    
    def test_crop_face_out_of_bounds(self):
        """测试超出边界的人脸裁剪"""
        out_of_bounds_bbox = BBoxModel(x=250, y=250, w=100, h=100)  # 超出图像边界
        
        with self.assertRaises(ValueError):
            self.service._crop_face(self.test_image, out_of_bounds_bbox)
    
    def test_preprocess_face(self):
        """测试人脸预处理"""
        face_image, _ = self.service._crop_face(self.test_image, self.valid_bbox)
        preprocessed = self.service._preprocess_face_for_hailo(face_image)
        
        self.assertIsInstance(preprocessed, np.ndarray)
        # 注意：实际的预处理输出尺寸取决于Hailo模型的输入要求
        # 这里只验证基本属性
        self.assertEqual(len(preprocessed.shape), 3)  # H, W, C format
    
    def test_get_health(self):
        """测试健康状态获取"""
        health = self.service.get_health()
        
        self.assertIn("status", health.model_dump())
        self.assertIn("model_loaded", health.model_dump())
        self.assertIn("uptime_ms", health.model_dump())
        self.assertTrue(isinstance(health.uptime_ms, int))


class TestBBoxModel(unittest.TestCase):
    """BBoxModel测试"""
    
    def test_valid_bbox(self):
        """测试有效的边界框"""
        bbox = BBoxModel(x=10, y=20, w=50, h=60)
        
        self.assertEqual(bbox.x, 10)
        self.assertEqual(bbox.y, 20)
        self.assertEqual(bbox.w, 50)
        self.assertEqual(bbox.h, 60)
    
    def test_bbox_validation(self):
        """测试边界框验证"""
        # 这里可以添加更多的验证逻辑，如果BBoxModel包含验证的话
        pass


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)
