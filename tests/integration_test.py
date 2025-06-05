#!/usr/bin/env python3
"""
人脸识别门禁系统集成测试
验证核心功能是否正常工作
"""

import asyncio
import base64
import json
import os
import sys
import time
from typing import Dict, List
import requests
import cv2
import numpy as np

# MQTT client
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    print("Warning: paho-mqtt not installed, MQTT tests will be skipped")
    MQTT_AVAILABLE = False

class IntegrationTester:
    def __init__(self):
        self.face_embed_api_url = "http://localhost:8000"
        self.qdrant_url = "http://localhost:6333"
        self.mqtt_broker = "localhost"
        self.mqtt_port = 1883
        self.api_key = "face_access_2025"
        
        self.test_collection = "test_faces"
        self.mqtt_client = None
        self.mqtt_messages = []
        
    def log_info(self, message):
        print(f"[INFO] {message}")
        
    def log_success(self, message):
        print(f"[SUCCESS] ✅ {message}")
        
    def log_error(self, message):
        print(f"[ERROR] ❌ {message}")
        
    def log_warning(self, message):
        print(f"[WARNING] ⚠️  {message}")

    def create_test_image(self, person_id=1):
        """创建测试人脸图像"""
        # 创建一个简单的测试图像
        image = np.ones((480, 480, 3), dtype=np.uint8) * 255
        
        # 绘制不同的人脸模拟区域
        if person_id == 1:
            # 人脸1 - 较大的矩形
            cv2.rectangle(image, (140, 140), (340, 340), (200, 150, 100), -1)
            cv2.rectangle(image, (170, 180), (190, 200), (50, 50, 50), -1)  # 左眼
            cv2.rectangle(image, (290, 180), (310, 200), (50, 50, 50), -1)  # 右眼
            cv2.rectangle(image, (220, 250), (260, 280), (100, 50, 50), -1)  # 嘴巴
        elif person_id == 2:
            # 人脸2 - 不同形状
            cv2.rectangle(image, (120, 120), (360, 360), (150, 200, 100), -1)
            cv2.rectangle(image, (160, 170), (180, 190), (30, 30, 30), -1)  # 左眼
            cv2.rectangle(image, (300, 170), (320, 190), (30, 30, 30), -1)  # 右眼
            cv2.rectangle(image, (210, 260), (270, 290), (80, 40, 40), -1)  # 嘴巴
        
        return image

    def image_to_base64(self, image):
        """将图像转换为base64"""
        _, buffer = cv2.imencode('.jpg', image)
        return base64.b64encode(buffer).decode('utf-8')

    def test_face_embed_api_health(self):
        """测试FaceEmbed API健康状态"""
        try:
            response = requests.get(f"{self.face_embed_api_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.log_success(f"FaceEmbed API健康检查通过: {data['status']}")
                return True
            else:
                self.log_error(f"FaceEmbed API健康检查失败: {response.status_code}")
                return False
        except Exception as e:
            self.log_error(f"无法连接到FaceEmbed API: {e}")
            return False

    def test_face_embedding(self):
        """测试人脸嵌入功能"""
        try:
            # 创建测试图像
            test_image = self.create_test_image(1)
            image_base64 = self.image_to_base64(test_image)
            
            # 构造请求
            request_data = {
                "image_base64": image_base64,
                "bbox": {"x": 140, "y": 140, "w": 200, "h": 200}
            }
            
            # 发送请求
            response = requests.post(
                f"{self.face_embed_api_url}/embed",
                json=request_data,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                vector = data["vector"]
                
                # 验证向量
                if len(vector) == 512:
                    # 验证归一化
                    norm = np.linalg.norm(vector)
                    if abs(norm - 1.0) < 0.01:
                        self.log_success(f"人脸嵌入提取成功，处理时间: {data['processing_time_ms']}ms")
                        return vector
                    else:
                        self.log_error(f"向量未正确归一化，norm: {norm}")
                else:
                    self.log_error(f"向量维度错误: {len(vector)}")
            else:
                self.log_error(f"人脸嵌入请求失败: {response.status_code}")
                
        except Exception as e:
            self.log_error(f"人脸嵌入测试失败: {e}")
        
        return None

    def test_qdrant_health(self):
        """测试Qdrant健康状态"""
        try:
            response = requests.get(f"{self.qdrant_url}/health", timeout=5)
            if response.status_code == 200:
                self.log_success("Qdrant健康检查通过")
                return True
            else:
                self.log_error(f"Qdrant健康检查失败: {response.status_code}")
                return False
        except Exception as e:
            self.log_error(f"无法连接到Qdrant: {e}")
            return False

    def test_qdrant_collection(self):
        """测试Qdrant集合创建和操作"""
        try:
            # 创建测试集合
            collection_config = {
                "vectors": {
                    "size": 512,
                    "distance": "Cosine"
                },
                "optimizers_config": {
                    "default_segment_number": 2
                },
                "replication_factor": 1
            }
            
            response = requests.put(
                f"{self.qdrant_url}/collections/{self.test_collection}",
                json=collection_config,
                headers={"api-key": self.api_key},
                timeout=10
            )
            
            if response.status_code in [200, 409]:  # 200=created, 409=already exists
                self.log_success(f"测试集合 '{self.test_collection}' 准备就绪")
                return True
            else:
                self.log_error(f"创建集合失败: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_error(f"Qdrant集合测试失败: {e}")
            return False

    def test_vector_storage_and_search(self):
        """测试向量存储和搜索"""
        try:
            # 获取测试向量
            vector1 = self.test_face_embedding()
            if not vector1:
                return False
            
            # 存储向量
            point_data = {
                "points": [
                    {
                        "id": 1,
                        "vector": vector1,
                        "payload": {
                            "name": "测试用户1",
                            "created_at": time.time()
                        }
                    }
                ]
            }
            
            response = requests.put(
                f"{self.qdrant_url}/collections/{self.test_collection}/points",
                json=point_data,
                headers={"api-key": self.api_key},
                timeout=10
            )
            
            if response.status_code == 200:
                self.log_success("向量存储成功")
            else:
                self.log_error(f"向量存储失败: {response.status_code}")
                return False
            
            # 等待索引
            time.sleep(1)
            
            # 搜索向量
            search_data = {
                "vector": vector1,
                "limit": 3,
                "with_payload": True,
                "score_threshold": 0.5
            }
            
            response = requests.post(
                f"{self.qdrant_url}/collections/{self.test_collection}/points/search",
                json=search_data,
                headers={"api-key": self.api_key},
                timeout=10
            )
            
            if response.status_code == 200:
                results = response.json()["result"]
                if results and len(results) > 0:
                    best_match = results[0]
                    score = best_match["score"]
                    name = best_match["payload"]["name"]
                    self.log_success(f"向量搜索成功，最佳匹配: {name} (相似度: {score:.4f})")
                    return True
                else:
                    self.log_warning("搜索结果为空")
            else:
                self.log_error(f"向量搜索失败: {response.status_code}")
                
        except Exception as e:
            self.log_error(f"向量存储和搜索测试失败: {e}")
        
        return False

    def setup_mqtt_client(self):
        """设置MQTT客户端"""
        if not MQTT_AVAILABLE:
            return False
            
        try:
            self.mqtt_client = mqtt.Client()
            
            def on_connect(client, userdata, flags, rc):
                if rc == 0:
                    self.log_success("MQTT连接成功")
                    # 订阅测试主题
                    client.subscribe("access/result/test_device")
                    client.subscribe("system/heartbeat")
                else:
                    self.log_error(f"MQTT连接失败: {rc}")
            
            def on_message(client, userdata, msg):
                try:
                    message = {
                        "topic": msg.topic,
                        "payload": json.loads(msg.payload.decode()),
                        "timestamp": time.time()
                    }
                    self.mqtt_messages.append(message)
                    self.log_info(f"收到MQTT消息: {msg.topic}")
                except Exception as e:
                    self.log_warning(f"MQTT消息解析失败: {e}")
            
            self.mqtt_client.on_connect = on_connect
            self.mqtt_client.on_message = on_message
            
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
            
            time.sleep(2)  # 等待连接
            return True
            
        except Exception as e:
            self.log_error(f"MQTT客户端设置失败: {e}")
            return False

    def test_mqtt_communication(self):
        """测试MQTT通信"""
        if not MQTT_AVAILABLE or not self.mqtt_client:
            self.log_warning("跳过MQTT测试 (客户端不可用)")
            return True
            
        try:
            # 发送测试消息
            test_message = {
                "test": True,
                "timestamp": time.time(),
                "device_id": "test_device"
            }
            
            self.mqtt_client.publish(
                "test/integration",
                json.dumps(test_message),
                qos=1
            )
            
            self.log_success("MQTT消息发送成功")
            return True
            
        except Exception as e:
            self.log_error(f"MQTT通信测试失败: {e}")
            return False

    def cleanup_test_data(self):
        """清理测试数据"""
        try:
            # 删除测试集合
            response = requests.delete(
                f"{self.qdrant_url}/collections/{self.test_collection}",
                headers={"api-key": self.api_key},
                timeout=10
            )
            
            if response.status_code in [200, 404]:
                self.log_success("测试数据清理完成")
            
            # 断开MQTT连接
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
                
        except Exception as e:
            self.log_warning(f"清理测试数据时出错: {e}")

    def run_all_tests(self):
        """运行所有集成测试"""
        print("=" * 60)
        print("🧪 人脸识别门禁系统集成测试")
        print("=" * 60)
        
        test_results = {}
        
        # 1. FaceEmbed API测试
        self.log_info("1. 测试FaceEmbed API...")
        test_results["face_embed_health"] = self.test_face_embed_api_health()
        test_results["face_embedding"] = self.test_face_embedding() is not None
        
        # 2. Qdrant测试
        self.log_info("2. 测试Qdrant向量数据库...")
        test_results["qdrant_health"] = self.test_qdrant_health()
        test_results["qdrant_collection"] = self.test_qdrant_collection()
        test_results["vector_ops"] = self.test_vector_storage_and_search()
        
        # 3. MQTT测试
        self.log_info("3. 测试MQTT通信...")
        test_results["mqtt_setup"] = self.setup_mqtt_client()
        test_results["mqtt_comm"] = self.test_mqtt_communication()
        
        # 汇总结果
        print("\n" + "=" * 60)
        print("📊 测试结果汇总")
        print("=" * 60)
        
        passed_tests = sum(1 for result in test_results.values() if result)
        total_tests = len(test_results)
        
        for test_name, result in test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"  {test_name:20} {status}")
        
        print(f"\n通过率: {passed_tests}/{total_tests} ({passed_tests/total_tests*100:.1f}%)")
        
        # 清理
        self.cleanup_test_data()
        
        if passed_tests == total_tests:
            print("\n🎉 所有测试通过！系统准备就绪。")
            return True
        else:
            print(f"\n⚠️  有 {total_tests - passed_tests} 项测试失败，请检查系统配置。")
            return False

def main():
    """主函数"""
    print("开始集成测试...")
    
    # 检查必要的服务是否运行
    print("正在检查必要的服务...")
    
    tester = IntegrationTester()
    success = tester.run_all_tests()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 集成测试完成，系统正常运行！")
        print("\n下一步:")
        print("1. 连接Grove Vision AI V2设备")
        print("2. 在Hailo设备上启动FaceEmbed API")
        print("3. 导入Node-RED流程")
        print("4. 进行实际的人脸识别测试")
    else:
        print("❌ 集成测试发现问题，请检查系统配置")
        print("\n故障排除:")
        print("1. 确保所有Docker容器正在运行: docker-compose ps")
        print("2. 检查服务日志: docker-compose logs [service_name]")
        print("3. 验证网络连接和端口是否可用")
    
    print("=" * 60)
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())
