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

from face_embed_api.app import (
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
    
    @patch('face_embed_api.app.get_face_embed_service')
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
    
    @patch('face_embed_api.app.get_face_embed_service')
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
    
    @patch('face_embed_api.app.get_face_embed_service')
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
    
    @patch('face_embed_api.app.get_face_embed_service')
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
    
    @patch('face_embed_api.app.get_face_embed_service')
    def test_batch_embed_too_many_images(self, mock_get_service):
        """测试批量嵌入请求（图像过多）"""
        mock_service = Mock(spec=FaceEmbedService)
        async def mock_batch_embed(requests):
            if len(requests) > 10:
                raise HTTPException(status_code=400, detail="Maximum 10 images per batch")
            return [], []
        mock_service.extract_embeddings_batch = mock_batch_embed
        mock_get_service.return_value = mock_service
        
        # 创建超过10个的图像请求
        images = []
        for i in range(11):
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

    @patch('face_embed_api.app.get_face_embed_service')
    def test_detect_and_embed_endpoint(self, mock_get_service):
        """测试检测和嵌入端点"""
        mock_service = Mock(spec=FaceEmbedService)
        mock_vector = np.random.normal(0, 1, 512).astype(np.float32)
        mock_vector = mock_vector / np.linalg.norm(mock_vector)

        async def mock_detect_and_embed(request):
            mock_embedding_response = {
                "vector": mock_vector.tolist(),
                "processing_time_ms": 10,
                "confidence": 0.8
            }
            mock_face_result = {
                "bbox": BBoxModel(x=10, y=10, w=50, h=50).model_dump(),
                "landmarks": [LandmarkPoint(x=1.0, y=1.0).model_dump() for _ in range(5)],
                "detection_confidence": 0.99,
                "embedding": mock_embedding_response
            }
            return [mock_face_result]
        mock_service.detect_and_embed = mock_detect_and_embed
        mock_get_service.return_value = mock_service
        
        request_data = {
            "image_base64": self.test_image_base64,
        }
        response = self.client.post("/detect_and_embed", json=request_data)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        face = data[0]
        self.assertIn("bbox", face)
        self.assertIn("embedding", face)
        self.assertEqual(len(face["embedding"]["vector"]), 512)


class TestFaceEmbedService(unittest.TestCase):
    """
    FaceEmbedService的单元测试 - Mocks Hailo hardware interactions.
    """
    
    @patch('face_embed_api.app.FaceEmbedService._initialize_hailo_device')
    def setUp(self, mock_init_hailo):
        """
        为服务测试设置环境，并模拟Hailo硬件初始化
        """
        # Patch the Hailo initialization to prevent it from running
        self.mock_init_hailo_patcher = mock_init_hailo
        self.mock_init_hailo_patcher.start()
        
        self.service = FaceEmbedService()
        
        # Create mock inference models for detection and recognition
        self.mock_det_infer_model = MagicMock()
        # Mock the input() method to return another mock with a shape attribute
        self.mock_det_infer_model.input.return_value = MagicMock(shape=(640, 640, 3))
        self.mock_det_infer_model.outputs = [MagicMock(name='output1', shape=(1, 80, 80, 16))]
        
        self.mock_rec_infer_model = MagicMock()
        # Mock the input() method to return another mock with a shape attribute
        self.mock_rec_infer_model.input.return_value = MagicMock(shape=(112, 112, 3))
        self.mock_rec_infer_model.outputs = [MagicMock(name='output1', shape=(1, 512))]

        # Assign mocks to the service instance
        self.service.det_infer_model = self.mock_det_infer_model
        self.service.rec_infer_model = self.mock_rec_infer_model

        # Add back test attributes
        self.test_image = self._create_test_image()
        self.valid_bbox = BBoxModel(x=50, y=50, w=100, h=120)
        
    def tearDown(self):
        """测试清理"""
        self.mock_init_hailo_patcher.stop()

    def _create_test_image(self):
        """创建测试图像"""
        image = np.ones((300, 300, 3), dtype=np.uint8) * 255
        cv2.rectangle(image, (50, 50), (150, 170), (128, 128, 128), -1)
        return image
    
    def _image_to_base64(self, image):
        """将图像转换为base64编码"""
        _, buffer = cv2.imencode('.jpg', image)
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        return image_base64

    def test_decode_image_valid(self):
        """测试有效图像解码"""
        decoded_image = self.service._decode_image(self._image_to_base64(self.test_image))
        self.assertIsInstance(decoded_image, np.ndarray)
        self.assertEqual(len(decoded_image.shape), 3)

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
        """测试无效边界框（尺寸为0）"""
        with self.assertRaises(ValueError):
            self.service._crop_face(self.test_image, BBoxModel(x=-10, y=-10, w=50, h=50))
    
    def test_crop_face_out_of_bounds(self):
        """测试裁剪边界框超出图像范围"""
        with self.assertRaises(ValueError):
            self.service._crop_face(self.test_image, BBoxModel(x=250, y=250, w=100, h=100))
    
    def test_preprocess_face_for_hailo(self):
        """测试人脸预处理以适配Hailo模型"""
        face_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        model_shape = (112, 112, 3)
        processed_face = self.service._preprocess_face_for_hailo(face_image, model_shape)
        
        # 验证输出尺寸
        self.assertEqual(processed_face.shape, model_shape)
        
        # 验证图像是否居中
        # The sum of the padded area should be zero.
        # Since the 100x100 image is scaled to 112x112, there is no padding.
        # We need a non-square image to test padding.
        face_image_non_square = np.random.randint(0, 255, (80, 100, 3), dtype=np.uint8)
        processed_face_padded = self.service._preprocess_face_for_hailo(face_image_non_square, model_shape)

        self.assertEqual(processed_face_padded.shape, model_shape)
        # Top and bottom rows should be padded (black)
        self.assertEqual(np.sum(processed_face_padded[0, :]), 0)
        self.assertEqual(np.sum(processed_face_padded[-1, :]), 0)

    def test_get_health(self):
        """测试健康状况获取"""
        # Mock loaded models for predictability
        self.service.face_detection_hef = "det.hef"
        self.service.face_recognition_hef = "rec.hef"
        
        health = self.service.get_health()
    
        self.assertEqual(health.status, "ok")
        self.assertIsInstance(health.uptime_ms, int)
        self.assertIn("det.hef", health.loaded_models)
        self.assertIn("rec.hef", health.loaded_models)

    @patch('face_embed_api.app.queue.Queue')
    def test_detect_faces_logic(self, mock_queue):
        """Test the internal logic of face detection"""
        # Setup mocks
        mock_input_q = Mock()
        mock_output_q = Mock()
        
        mock_detection_result = np.random.rand(8400, 15).astype(np.float32)
        mock_output_q.get.return_value = (None, {'output1': mock_detection_result})
        
        self.service.det_input_queue = mock_input_q
        self.service.det_output_queue = mock_output_q

        # Create request
        test_image = self._create_test_image()
        req = DetectRequest(image_base64=self._image_to_base64(test_image))
        
        # Run detection
        faces, _, _, _ = asyncio.run(self.service.detect_faces(req))
        
        # Assertions
        mock_input_q.put.assert_called_once()
        mock_output_q.get.assert_called_once()
        self.assertIsInstance(faces, list)


class TestBBoxModel(unittest.TestCase):
    """BBoxModel的测试"""
    
    def test_valid_bbox(self):
        """测试有效的边界框"""
        bbox = BBoxModel(x=10, y=20, w=50, h=60)
        
        self.assertEqual(bbox.x, 10)
        self.assertEqual(bbox.y, 20)
        self.assertEqual(bbox.w, 50)
        self.assertEqual(bbox.h, 60)
    
    def test_bbox_validation(self):
        """测试边界框验证"""
        pass


if __name__ == '__main__':
    unittest.main(verbosity=2)
