# FaceEmbed API

基于Hailo-8 AI加速器的高性能人脸特征提取服务，提供512维人脸嵌入向量生成API。

## ✨ 特性

- 🚀 **高性能推理**: 基于Hailo-8硬件加速，推理延迟3-18ms
- 🎯 **标准化输出**: 512维L2归一化人脸嵌入向量
- 🔄 **异步处理**: 支持单张和批量图像处理
- ✨ **一体化检测与嵌入**: 单一接口完成人脸检测、对齐和特征提取
- 📊 **完整测试**: 11个测试用例，100%通过率
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
- 人脸检测模型文件 (scrfd_10g.hef)

### 3. 启动服务

```bash
# 设置PYTHONPATH并使用uvicorn启动 (推荐)
PYTHONPATH=src uv run uvicorn face_embed_api.app:app --host 0.0.0.0 --port 8000
```

### 4. 验证服务

```bash
# 健康检查
curl http://localhost:8000/health

# API测试
# (请参考下方的API示例进行测试)
```

## 📋 API 接口

### 健康检查
```http
GET /health
```
**响应**:
```json
{
  "status": "ok",
  "uptime_ms": 12345,
  "current_model": "path/to/model.hef"
}
```

### 一体化检测与嵌入
此接口在一个请求中完成人脸检测和特征提取，是推荐使用的主要接口。

```http
POST /detect_and_embed
Content-Type: application/json

{
  "image_base64": "base64_encoded_image",
  "confidence_threshold": 0.5
}
```
**响应**:
```json
[
  {
    "bbox": { "x": 50, "y": 50, "w": 100, "h": 120 },
    "landmarks": [
      {"x": 70, "y": 70},
      {"x": 130, "y": 70},
      {"x": 100, "y": 100},
      {"x": 80, "y": 130},
      {"x": 120, "y": 130}
    ],
    "detection_confidence": 0.98,
    "embedding": {
      "vector": [0.1, 0.2, "..."],
      "processing_time_ms": 15,
      "confidence": 0.95
    }
  }
]
```

### 单张人脸嵌入 (手动模式)
此接口需要您手动提供人脸的边界框 (bbox) 和关键点 (landmarks)。

```http
POST /embed
Content-Type: application/json

{
  "image_base64": "base64_encoded_image",
  "bbox": {"x": 50, "y": 50, "w": 100, "h": 120},
  "landmarks": [
      {"x": 70, "y": 70},
      {"x": 130, "y": 70},
      {"x": 100, "y": 100},
      {"x": 80, "y": 130},
      {"x": 120, "y": 130}
  ]
}
```

### 批量人脸嵌入 (手动模式)
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
uv run -- pytest -v
```

### 单独运行测试
```bash
# 单元测试
pytest tests/unit/ -v

# 集成测试  
pytest tests/integration/ -v
```

## 🐛 调试 (Debugging)

本服务内置了图像调试功能，可以将处理过程中的关键图像保存到本地，方便分析和排查问题。

### 如何启用

通过设置以下环境变量来启用调试模式：

```bash
export DEBUG_SAVE_IMAGES=true
export DEBUG_SAVE_INTERVAL_S=5 # 每5秒最多保存一张图，防止刷屏

# 然后启动服务
PYTHONPATH=src uv run uvicorn face_embed_api.app:app --host 0.0.0.0 --port 8000
```

### 调试环境变量

- **`DEBUG_SAVE_IMAGES`**: 设置为 `true`, `1`, 或 `t` 来启用图像保存功能。
- **`DEBUG_SAVE_INTERVAL_S`**: 控制保存图像的最小时间间隔（秒），默认为 `10`。这有助于防止在处理视频流或大量请求时产生过多的文件。

### 保存的图像类型

启用后，以下类型的图像将被保存到项目根目录下的 `debug_images/` 文件夹中：

- **`detected_*.jpg`**: 在原始图像上绘制了人脸检测框和关键点的结果图。
- **`cropped_for_embedding_*.jpg`**: 从原图中裁剪出、为送入嵌入模型而预处理的**无对齐**人脸图像。
- **`aligned_for_embedding_*.jpg`**: 使用关键点进行对齐后、为送入嵌入模型而预处理的人脸图像。

文件名中会包含时间戳和置信度等信息，方便追溯。

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
- **测试覆盖**: 11个测试，100%通过

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

# 发送请求到 detect_and_embed 接口
response = requests.post('http://localhost:8000/detect_and_embed', json={
    'image_base64': image_base64,
    'confidence_threshold': 0.5
})

# 获取结果
results = response.json()
if results:
    first_face = results[0]
    vector = first_face['embedding']['vector']  # 512维嵌入向量
    confidence = first_face['embedding']['confidence'] # 嵌入质量置信度
    detection_confidence = first_face['detection_confidence'] # 检测置信度
    print(f"Found {len(results)} faces. First face vector: {vector[:5]}...")
```

### Node-RED 集成
```javascript
// Node-RED Function节点
const payload = {
    image_base64: msg.payload.image,
    confidence_threshold: 0.5 // 可选
};

msg.url = "http://raspberry-pi:8000/detect_and_embed";
msg.method = "POST";
msg.headers = {"Content-Type": "application/json"};
msg.payload = payload;

return msg;
```

## 📈 部署

### 生产环境
```bash
# 启动服务
PYTHONPATH=src uv run uvicorn face_embed_api.app:app --host 0.0.0.0 --port 8000
```

### 环境变量
- `HOST`: 服务监听地址 (默认: 0.0.0.0)
- `PORT`: 服务端口 (默认: 8000)
- `FACE_RECOGNITION_HEF`: 人脸识别模型文件路径
- `FACE_DETECTION_HEF`: 人脸检测模型文件路径
- `DEBUG_SAVE_IMAGES`: 是否开启调试图像保存 (`true` / `false`)
- `DEBUG_SAVE_INTERVAL_S`: 调试图像保存时间间隔（秒，默认10)

## 🚨 依赖要求

### 必需安装
- **HailoRT 4.21.0**: 核心推理引擎
- **Hailo-8 AI Kit**: 硬件加速器
- **Raspberry Pi 5**: 支持PCIe的主板
- **人脸识别模型**: arcface_mobilefacenet.hef
- **人脸检测模型**: scrfd_10g.hef

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
