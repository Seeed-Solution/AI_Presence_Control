#!/usr/bin/env python3
"""
测试Hailo硬件的API请求
"""

import base64
import cv2
import numpy as np
import requests
import json

def test_hailo_request():
    # 创建测试图像
    image = np.ones((300, 300, 3), dtype=np.uint8) * 255
    cv2.rectangle(image, (50, 50), (150, 170), (128, 128, 128), -1)

    # 转换为base64
    _, buffer = cv2.imencode('.jpg', image)
    image_base64 = base64.b64encode(buffer).decode('utf-8')

    # 发送请求
    request_data = {
        'image_base64': image_base64,
        'bbox': {'x': 50, 'y': 50, 'w': 100, 'h': 120}
    }

    try:
        response = requests.post('http://localhost:8000/embed', json=request_data, timeout=10)
        print(f'Status: {response.status_code}')
        
        if response.status_code == 200:
            data = response.json()
            print(f'Processing time: {data["processing_time_ms"]}ms')
            print(f'Confidence: {data["confidence"]}')
            print(f'Vector length: {len(data["vector"])}')
            print(f'Vector norm: {np.linalg.norm(data["vector"]):.6f}')
            print(f'First 5 values: {data["vector"][:5]}')
            return True
        else:
            print(f'Error: {response.text}')
            return False
            
    except Exception as e:
        print(f'Request failed: {e}')
        return False

if __name__ == "__main__":
    test_hailo_request() 