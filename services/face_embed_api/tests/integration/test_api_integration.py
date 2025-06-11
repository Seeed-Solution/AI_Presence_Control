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
        cls.timeout = 20 # Increased timeout for safety
        
        # Wait for the server to be ready
        max_retries = 20 # Increased retries
        retry_interval = 2  # seconds
        for i in range(max_retries):
            try:
                response = requests.get(f"{cls.api_url}/health", timeout=cls.timeout)
                if response.status_code == 200:
                    print("✅ API server is ready.")
                    break
            except requests.ConnectionError:
                print(f"🔌 API server not ready yet. Retrying in {retry_interval}s... ({i+1}/{max_retries})")
                time.sleep(retry_interval)
        else:
            raise RuntimeError("❌ API server did not start in time.")
        
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
        assert "uptime_ms" in data
        assert "loaded_models" in data
        assert isinstance(data["uptime_ms"], int)
        assert data["uptime_ms"] >= 0
        assert isinstance(data["loaded_models"], list)
        assert "scrfd_10g.hef" in data["loaded_models"]
        assert "arcface_mobilefacenet.hef" in data["loaded_models"]
    
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
    
    def test_api_embed_with_landmarks(self):
        """测试使用关键点进行嵌入"""
        test_image = self._create_test_image()
        image_base64 = self._image_to_base64(test_image)
        
        # 提供了关键点时，bbox 仍然是必需的，但服务会优先使用关键点进行对齐
        request_data = {
            "image_base64": image_base64,
            "bbox": {"x": 50, "y": 50, "w": 100, "h": 120},
            "landmarks": [
                {"x": 84.0, "y": 90.0},
                {"x": 130.0, "y": 89.0},
                {"x": 107.0, "y": 117.0},
                {"x": 89.0, "y": 142.0},
                {"x": 126.0, "y": 142.0}
            ]
        }
        
        response = requests.post(
            f"{self.api_url}/embed", 
            json=request_data, 
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "vector" in data
        vector = data["vector"]
        assert len(vector) == 512
        norm = np.linalg.norm(vector)
        assert abs(norm - 1.0) < 0.01

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
        
        # 多次请求获取向量
        vectors = []
        for _ in range(3):
            response = requests.post(f"{self.api_url}/embed", json=request_data, timeout=self.timeout)
            assert response.status_code == 200
            vectors.append(np.array(response.json()["vector"]))
            
        # 比较所有向量是否一致
        for i in range(1, len(vectors)):
            np.testing.assert_allclose(vectors[0], vectors[i], rtol=1e-5, atol=1e-5)

    def test_api_detect_and_embed(self):
        """测试检测并嵌入的组合API"""
        test_image = self._create_test_image(width=400, height=400)
        image_base64 = self._image_to_base64(test_image)
        
        request_data = {
            "image_base64": image_base64,
            "confidence_threshold": 0.4
        }
        
        response = requests.post(
            f"{self.api_url}/detect_and_embed",
            json=request_data,
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return a list of results
        assert isinstance(data, list)
        # Our test image should have at least one face
        assert len(data) > 0
        
        face_result = data[0]
        assert "bbox" in face_result
        assert "landmarks" in face_result
        assert "detection_confidence" in face_result
        assert "embedding" in face_result
        
        # Check embedding structure
        embedding = face_result["embedding"]
        assert "vector" in embedding
        assert len(embedding["vector"]) == 512
        norm = np.linalg.norm(embedding["vector"])
        assert abs(norm - 1.0) < 0.01

    def test_api_performance(self):
        """测试API性能"""
        test_image = self._create_test_image()
        image_base64 = self._image_to_base64(test_image)
        
        request_data = {
            "image_base64": image_base64,
            "bbox": {"x": 50, "y": 50, "w": 100, "h": 120}
        }
        
        start_time = time.time()
        response = requests.post(f"{self.api_url}/embed", json=request_data, timeout=self.timeout)
        end_time = time.time()
        
        assert response.status_code == 200
        
        # 检查端到端延迟
        e2e_latency = (end_time - start_time) * 1000
        print(f"E2E Latency: {e2e_latency:.2f}ms")
        assert e2e_latency < 2000  # 2秒内完成
        
        # 检查服务器报告的处理时间
        # 在mock环境下，这个值是固定的
        # 在真实硬件上，这个值会反映Hailo的性能
        processing_time = response.json()["processing_time_ms"]
        assert processing_time < 1000  # 小于1秒 