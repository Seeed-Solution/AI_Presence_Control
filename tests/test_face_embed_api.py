#!/usr/bin/env python3
"""
FaceEmbed API 单元测试
测试人脸嵌入向量生成功能
"""

import base64
import io
import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

# 添加服务路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'face_embed_api'))

from app import app, FaceEmbedService, BBoxModel


class TestFaceEmbedAPI(unittest.TestCase):
    """FaceEmbed API测试类"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        cls.client = TestClient(app)
        cls.service = FaceEmbedService()
        
    def setUp(self):
        """每个测试前的准备"""
        # 创建测试图像
        self.test_image = self._create_test_image()
        self.test_image_base64 = self._image_to_base64(self.test_image)
        self.valid_bbox = BBoxModel(x=50, y=50, w=100, h=120)
        
    def _create_test_image(self, width=300, height=300):
        """创建测试图像"""
        # 创建一个简单的测试图像（白色背景，中央有个矩形）
        image = np.ones((height, width, 3), dtype=np.uint8) * 255
        
        # 在中央绘制一个矩形来模拟人脸区域
        cv2.rectangle(image, (50, 50), (150, 170), (128, 128, 128), -1)
        
        return image
    
    def _image_to_base64(self, image):
        """将图像转换为base64字符串"""
        _, buffer = cv2.imencode('.jpg', image)
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        return image_base64
    
    def test_health_endpoint(self):
        """测试健康检查端点"""
        response = self.client.get("/health")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn("status", data)
        self.assertIn("model_loaded", data)
        self.assertIn("uptime_ms", data)
        self.assertTrue(isinstance(data["uptime_ms"], int))
        self.assertTrue(data["uptime_ms"] >= 0)
    
    def test_root_endpoint(self):
        """测试根端点"""
        response = self.client.get("/")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["message"], "FaceEmbed API")
        self.assertEqual(data["version"], "1.0.0")
        self.assertEqual(data["status"], "running")
    
    def test_embed_endpoint_valid_request(self):
        """测试有效的人脸嵌入请求"""
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
        
        # 验证向量维度
        self.assertEqual(len(data["vector"]), 512)
        
        # 验证向量是归一化的
        vector = np.array(data["vector"])
        norm = np.linalg.norm(vector)
        self.assertAlmostEqual(norm, 1.0, places=6)
        
        # 验证处理时间
        self.assertTrue(isinstance(data["processing_time_ms"], int))
        self.assertTrue(data["processing_time_ms"] > 0)
        
        # 验证置信度
        self.assertTrue(0.0 <= data["confidence"] <= 1.0)
    
    def test_embed_endpoint_invalid_bbox(self):
        """测试无效的边界框"""
        # 测试超出图像边界的bbox
        invalid_bbox = {
            "x": 250,  # 超出图像宽度
            "y": 250,  # 超出图像高度
            "w": 100,
            "h": 100
        }
        
        request_data = {
            "image_base64": self.test_image_base64,
            "bbox": invalid_bbox
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
    
    def test_batch_embed_endpoint(self):
        """测试批量人脸嵌入"""
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
    
    def setUp(self):
        """测试准备"""
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
        preprocessed = self.service._preprocess_face(face_image)
        
        self.assertIsInstance(preprocessed, np.ndarray)
        self.assertEqual(preprocessed.shape, (1, 112, 112, 3))  # Batch, H, W, C
        self.assertTrue(preprocessed.min() >= 0.0)
        self.assertTrue(preprocessed.max() <= 1.0)
    
    def test_extract_embedding_mock(self):
        """测试模拟人脸嵌入提取"""
        face_image, _ = self.service._crop_face(self.test_image, self.valid_bbox)
        embedding = self.service._extract_embedding_mock(face_image)
        
        self.assertIsInstance(embedding, np.ndarray)
        self.assertEqual(embedding.shape, (512,))
        
        # 验证归一化
        norm = np.linalg.norm(embedding)
        self.assertAlmostEqual(norm, 1.0, places=6)
    
    def test_extract_embedding_deterministic(self):
        """测试嵌入提取的确定性"""
        face_image, _ = self.service._crop_face(self.test_image, self.valid_bbox)
        
        # 多次提取同一图像的嵌入
        embedding1 = self.service._extract_embedding_mock(face_image)
        embedding2 = self.service._extract_embedding_mock(face_image)
        
        # 应该得到相同的结果
        np.testing.assert_array_almost_equal(embedding1, embedding2)
    
    def test_get_health(self):
        """测试健康状态获取"""
        health = self.service.get_health()
        
        self.assertIn("status", health.dict())
        self.assertIn("model_loaded", health.dict())
        self.assertIn("uptime_ms", health.dict())
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
