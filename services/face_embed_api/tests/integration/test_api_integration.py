#!/usr/bin/env python3
"""
FaceEmbed API集成测试
测试API的实际HTTP接口
"""

import base64
import pytest
import requests
import cv2
import numpy as np
import time
import sys
import os
from unittest.mock import MagicMock

# 添加项目根目录到路径  
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Mock Hailo platform before importing
sys.modules['hailo_platform'] = MagicMock()

from src.face_embed_api.app import app, FaceEmbedService, BBoxModel


class TestFaceEmbedAPIIntegration:
    """FaceEmbed API集成测试类"""
    
    @classmethod
    def setup_class(cls):
        """测试类初始化"""
        cls.api_url = "http://localhost:8000"
        cls.timeout = 10
        
    def _create_test_image(self, width=300, height=300):
        """创建测试图像"""
        image = np.ones((height, width, 3), dtype=np.uint8) * 255
        cv2.rectangle(image, (50, 50), (150, 170), (128, 128, 128), -1)
        return image
    
    def _image_to_base64(self, image):
        """将图像转换为base64"""
        _, buffer = cv2.imencode('.jpg', image)
        return base64.b64encode(buffer).decode('utf-8')
    
    def test_api_health_check(self):
        """测试API健康检查"""
        response = requests.get(f"{self.api_url}/health", timeout=self.timeout)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "model_loaded" in data
        assert "uptime_ms" in data
        assert isinstance(data["uptime_ms"], int)
        assert data["uptime_ms"] >= 0
    
    def test_api_root_endpoint(self):
        """测试API根端点"""
        response = requests.get(f"{self.api_url}/", timeout=self.timeout)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["message"] == "FaceEmbed API"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"
    
    def test_api_embed_valid_request(self):
        """测试有效的嵌入请求"""
        test_image = self._create_test_image()
        image_base64 = self._image_to_base64(test_image)
        
        request_data = {
            "image_base64": image_base64,
            "bbox": {"x": 50, "y": 50, "w": 100, "h": 120}
        }
        
        response = requests.post(
            f"{self.api_url}/embed", 
            json=request_data, 
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # 验证响应结构
        assert "vector" in data
        assert "processing_time_ms" in data
        assert "confidence" in data
        
        # 验证向量
        vector = data["vector"]
        assert len(vector) == 512
        
        # 验证向量归一化
        norm = np.linalg.norm(vector)
        assert abs(norm - 1.0) < 0.01
        
        # 验证其他字段
        assert isinstance(data["processing_time_ms"], int)
        assert data["processing_time_ms"] > 0
        assert 0.0 <= data["confidence"] <= 1.0
    
    def test_api_embed_invalid_bbox(self):
        """测试无效边界框"""
        test_image = self._create_test_image()
        image_base64 = self._image_to_base64(test_image)
        
        request_data = {
            "image_base64": image_base64,
            "bbox": {"x": 350, "y": 350, "w": 100, "h": 100}  # 超出边界
        }
        
        response = requests.post(
            f"{self.api_url}/embed", 
            json=request_data, 
            timeout=self.timeout
        )
        
        assert response.status_code == 400
    
    def test_api_embed_invalid_image(self):
        """测试无效图像数据"""
        request_data = {
            "image_base64": "invalid_base64_data",
            "bbox": {"x": 50, "y": 50, "w": 100, "h": 100}
        }
        
        response = requests.post(
            f"{self.api_url}/embed", 
            json=request_data, 
            timeout=self.timeout
        )
        
        assert response.status_code == 400
    
    def test_api_batch_embed(self):
        """测试批量嵌入请求"""
        images = []
        for i in range(3):
            test_image = self._create_test_image()
            image_base64 = self._image_to_base64(test_image)
            images.append({
                "image_base64": image_base64,
                "bbox": {"x": 50, "y": 50, "w": 100, "h": 120}
            })
        
        request_data = {"images": images}
        
        response = requests.post(
            f"{self.api_url}/batch_embed", 
            json=request_data, 
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # 验证响应结构
        assert "vectors" in data
        assert "processing_times" in data
        
        # 验证批量结果
        assert len(data["vectors"]) == 3
        assert len(data["processing_times"]) == 3
        
        # 验证每个向量
        for vector in data["vectors"]:
            assert len(vector) == 512
            norm = np.linalg.norm(vector)
            assert abs(norm - 1.0) < 0.01
    
    def test_api_batch_embed_too_many_images(self):
        """测试批量请求超过限制"""
        test_image = self._create_test_image()
        image_base64 = self._image_to_base64(test_image)
        
        images = []
        for i in range(11):  # 超过最大10张限制
            images.append({
                "image_base64": image_base64,
                "bbox": {"x": 50, "y": 50, "w": 100, "h": 120}
            })
        
        request_data = {"images": images}
        
        response = requests.post(
            f"{self.api_url}/batch_embed", 
            json=request_data, 
            timeout=self.timeout
        )
        
        assert response.status_code == 400
    
    def test_api_embedding_consistency(self):
        """测试嵌入结果的一致性"""
        test_image = self._create_test_image()
        image_base64 = self._image_to_base64(test_image)
        
        request_data = {
            "image_base64": image_base64,
            "bbox": {"x": 50, "y": 50, "w": 100, "h": 120}
        }
        
        # 发送多次相同请求
        vectors = []
        for _ in range(3):
            response = requests.post(
                f"{self.api_url}/embed", 
                json=request_data, 
                timeout=self.timeout
            )
            assert response.status_code == 200
            vectors.append(response.json()["vector"])
        
        # 由于使用了确定性的mock，向量应该是一致的
        for i in range(1, len(vectors)):
            similarity = np.dot(vectors[0], vectors[i])
            assert similarity > 0.99  # 高相似度
    
    def test_api_performance(self):
        """测试API性能"""
        test_image = self._create_test_image()
        image_base64 = self._image_to_base64(test_image)
        
        request_data = {
            "image_base64": image_base64,
            "bbox": {"x": 50, "y": 50, "w": 100, "h": 120}
        }
        
        # 测试单次请求性能
        start_time = time.time()
        response = requests.post(
            f"{self.api_url}/embed", 
            json=request_data, 
            timeout=self.timeout
        )
        end_time = time.time()
        
        assert response.status_code == 200
        
        # API响应时间应该合理 (包括网络延迟)
        api_time = (end_time - start_time) * 1000
        assert api_time < 5000  # 小于5秒
        
        # 服务器报告的处理时间应该更快
        processing_time = response.json()["processing_time_ms"]
        assert processing_time < 1000  # 小于1秒 