# FaceEmbed API

基于Hailo-8 AI加速器的高性能人脸特征提取服务，提供512维人脸嵌入向量生成API。

## ✨ 特性

- 🚀 **高性能推理**: 基于Hailo-8硬件加速，推理延迟3-18ms
- 🎯 **标准化输出**: 512维L2归一化人脸嵌入向量
- 🔄 **异步处理**: 支持单张和批量图像处理
- 📊 **完整测试**: 28个测试用例，100%通过率
- 🌐 **跨域支持**: 支持Node-RED等跨机器访问

## 🏗️ 项目结构

```
face_embed_api/
├── 📂 src/face_embed_api/          # 核心源码
│   ├── app.py                      # FastAPI应用
│   ├── utils.py                    # Hailo推理工具
│   └── __init__.py                 # 包初始化
├── 📂 tests/                       # 测试套件
│   ├── unit/                       # 单元测试
│   └── integration/                # 集成测试
├── 📂 scripts/                     # 便捷脚本
│   ├── start_server.py             # 启动服务
│   ├── run_tests.py                # 运行测试
│   └── test_hailo_request.py       # API测试
├── 📂 models/                      # AI模型文件
├── 📂 docs/                        # 文档资料
└── 📂 logs/                        # 运行日志
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 激活虚拟环境
source .venv/bin/activate

# 安装基础依赖
uv sync
```

### 2. Hailo-8 硬件配置 (必需)

**重要**: 本服务需要Hailo-8硬件支持，请按照以下步骤配置：

1. **下载HailoRT**: 访问 [Hailo开发者中心](https://hailo.ai/developer-zone/software-downloads/) 下载必要文件
2. **系统配置**: 参考 [Hailo安装指南](docs/HAILO_SETUP.md) 进行详细配置
3. **验证安装**: 使用测试脚本验证硬件是否正常工作

**必需组件**:
- Raspberry Pi 5 + Hailo-8 AI Kit
- HailoRT 4.21.0 (系统包 + Python包)
- PCIe驱动和配置
- 人脸识别模型文件 (arcface_mobilefacenet.hef)

### 3. 启动服务

```bash
# 使用启动脚本 (推荐)
python scripts/start_server.py

# 或直接启动
cd src && python -m face_embed_api.app
```

### 4. 验证服务

```bash
# 健康检查
curl http://localhost:8000/health

# API测试
python scripts/test_hailo_request.py
```

## 📋 API 接口

### 健康检查
```http
GET /health
```

### 单张人脸嵌入
```http
POST /embed
Content-Type: application/json

{
  "image_base64": "base64_encoded_image",
  "bbox": {"x": 50, "y": 50, "w": 100, "h": 120}
}
```

### 批量人脸嵌入
```http
POST /batch_embed
Content-Type: application/json

{
  "images": [
    {
      "image_base64": "base64_encoded_image",
      "bbox": {"x": 50, "y": 50, "w": 100, "h": 120}
    }
  ]
}
```

## 🧪 测试

### 运行所有测试
```bash
python scripts/run_tests.py
```

### 单独运行测试
```bash
# 单元测试
pytest tests/unit/ -v

# 集成测试  
pytest tests/integration/ -v
```

## 🔧 开发

### 添加新功能
1. 在 `src/face_embed_api/` 中实现功能
2. 在 `tests/unit/` 中添加单元测试
3. 在 `tests/integration/` 中添加集成测试
4. 运行测试确保通过

### 代码结构
- **app.py**: FastAPI应用和路由定义
- **utils.py**: Hailo异步推理引擎
- **tests/**: 完整的测试覆盖

## 🛠️ 技术栈

- **API框架**: FastAPI + Uvicorn
- **AI推理**: Hailo-8 + HailoAsyncInference
- **图像处理**: OpenCV + NumPy
- **测试框架**: pytest + unittest
- **依赖管理**: UV

## 📊 性能指标

- **推理延迟**: 3-18ms (Hailo硬件)
- **向量维度**: 512维标准ArcFace
- **归一化**: L2归一化 (norm=1.0)
- **并发支持**: 异步多线程
- **测试覆盖**: 28个测试，100%通过

## 🔍 API 示例

### Python 客户端
```python
import requests
import base64
import cv2

# 准备图像
image = cv2.imread('face.jpg')
_, buffer = cv2.imencode('.jpg', image)
image_base64 = base64.b64encode(buffer).decode('utf-8')

# 发送请求
response = requests.post('http://localhost:8000/embed', json={
    'image_base64': image_base64,
    'bbox': {'x': 50, 'y': 50, 'w': 100, 'h': 120}
})

# 获取结果
data = response.json()
vector = data['vector']  # 512维嵌入向量
confidence = data['confidence']  # 置信度
```

### Node-RED 集成
```javascript
// Node-RED Function节点
const payload = {
    image_base64: msg.payload.image,
    bbox: msg.payload.bbox
};

msg.url = "http://raspberry-pi:8000/embed";
msg.method = "POST";
msg.headers = {"Content-Type": "application/json"};
msg.payload = payload;

return msg;
```

## 📈 部署

### 生产环境
```bash
# 启动服务
HOST=0.0.0.0 PORT=8000 python scripts/start_server.py
```

### 环境变量
- `HOST`: 服务监听地址 (默认: 0.0.0.0)
- `PORT`: 服务端口 (默认: 8000)
- `FACE_RECOGNITION_HEF`: 模型文件路径

## 🚨 依赖要求

### 必需安装
- **HailoRT 4.21.0**: 核心推理引擎
- **Hailo-8 AI Kit**: 硬件加速器
- **Raspberry Pi 5**: 支持PCIe的主板
- **人脸识别模型**: arcface_mobilefacenet.hef

### 系统要求
- **操作系统**: Linux (树莓派 OS 或 Ubuntu)
- **Python**: 3.11+
- **内存**: 4GB+ 推荐
- **存储**: 8GB+ 可用空间

## 📚 文档

- [项目结构说明](PROJECT_STRUCTURE.md)
- [Hailo安装指南](docs/HAILO_SETUP.md)
- [Hailo API指南](docs/reference/hailo_python_guide.md)

## 🤝 贡献

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 📄 许可证

MIT License

---

**FaceEmbed API** - 基于Hailo-8的高性能人脸特征提取服务 🚀 