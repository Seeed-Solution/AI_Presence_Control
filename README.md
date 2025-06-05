# 人脸识别权限控制系统 (Face Recognition Access Control System)

基于Hailo-8 AI加速器和Grove Vision AI V2的**分布式**边缘人脸识别门禁系统，支持多设备并发和跨机器部署。

## 🏗️ 分布式系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Grove Vision AI │───→│   MQTT Broker   │───→│    Node-RED     │
│      V2         │    │   (主服务器)    │    │   (主服务器)    │
│   (多设备)      │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                         │
                                                         ▼ HTTP API
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  FaceEmbed API  │◀───│     Qdrant      │◀───│ Vector Search   │
│ (Hailo设备)     │    │   (主服务器)    │    │                 │
│  并发处理       │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## ✨ 核心特性

- 🚀 **低延迟**：端到端 < 300ms 响应时间
- 🔀 **分布式**：Node-RED与Hailo设备分离部署
- ⚡ **高并发**：支持多设备同时处理，单Hailo设备支持20+并发流
- 🔒 **离线运行**：无需云端依赖
- 🏢 **多租户**：支持多个独立Collection
- 📱 **无接触**：基于人脸的身份验证
- 🎯 **高精度**：基于ArcFace深度学习模型
- 📊 **批量处理**：优化的批量向量提取

## 📋 分布式部署架构说明

### 主服务器 (Node-RED + Qdrant + MQTT)
- **功能**：业务逻辑编排、向量存储、消息代理、监控
- **硬件**：普通服务器或工控机
- **地址**：局域网固定IP

### Hailo设备 (FaceEmbed API)
- **功能**：AI推理、人脸向量提取
- **硬件**：Raspberry Pi 5 + Hailo-8
- **地址**：192.168.10.179 (可配置)
- **并发**：支持多设备同时调用

### Grove Vision AI V2
- **功能**：人脸检测、图像采集
- **连接**：通过MQTT连接到主服务器
- **数量**：支持多台设备

## 📋 快速开始

### 环境要求

#### 主服务器
- **硬件**：4GB+ RAM, 双核CPU
- **软件**：Ubuntu 22.04, Docker, Docker Compose
- **网络**：千兆以太网

#### Hailo设备  
- **硬件**：Raspberry Pi 5 + Hailo-8 AI加速器
- **软件**：HailoRT, Python 3.10+
- **网络**：千兆以太网连接

### 部署步骤

#### 1. 主服务器部署

```bash
# 克隆项目
git clone <repository_url>
cd face_rec_r2000

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，设置 FACE_EMBED_API_HOST=192.168.10.179

# 启动主服务器服务
./deployment/start_services.sh --with-nodered

# 服务访问地址：
# - Node-RED: http://localhost:1880
# - Qdrant: http://localhost:6333
# - Grafana: http://localhost:3000
```

#### 2. Hailo设备部署

```bash
# 在Hailo设备上 (192.168.10.179)
ssh harvest@192.168.10.179

# 复制FaceEmbed API代码
scp -r services/face_embed_api/ harvest@192.168.10.179:~/

# 在Hailo设备上启动
cd ~/face_embed_api
pip install -r requirements.txt
python app.py

# API地址: http://192.168.10.179:8000
```

#### 3. Grove Vision AI V2配置

```bash
# 配置MQTT连接
MQTT_BROKER="主服务器IP:1883"
TOPIC_PATTERN="vision/frames/{device_id}"

# 设备ID示例
DEVICE_ID="grove_vision_ai_v2_001"
```

## 🔧 并发性能优化

### FaceEmbed API并发配置

```python
# services/face_embed_api/app.py
# 支持多worker进程
WORKERS=4  # 根据Hailo设备性能调整

# 异步处理
async def extract_embedding(...)
```

### Node-RED批量处理

```javascript
// 批量处理配置
BATCH_SIZE=3           // 批量大小
MAX_WAIT_TIME=100      // 最大等待时间(ms)
API_TIMEOUT=5000       // API超时时间(ms)
```

### 性能指标

- **单设备延迟**：< 40ms (FaceEmbed API)
- **端到端延迟**：< 300ms (完整流程)
- **并发处理**：20+ 设备同时处理
- **吞吐量**：5fps/设备

## 📡 API接口

### FaceEmbed API

#### 单张处理
```bash
POST http://192.168.10.179:8000/embed
Content-Type: application/json

{
  "image_base64": "base64_encoded_image",
  "bbox": {"x": 100, "y": 100, "w": 200, "h": 200}
}
```

#### 批量处理 (并发优化)
```bash
POST http://192.168.10.179:8000/batch_embed
Content-Type: application/json

{
  "images": [
    {
      "image_base64": "...",
      "bbox": {"x": 100, "y": 100, "w": 200, "h": 200}
    }
  ]
}
```

### MQTT消息格式

#### 视觉输入
```json
Topic: vision/frames/grove_vision_ai_v2_001
{
  "ts": "2025-06-05T16:30:00Z",
  "img_b64": "base64_image_data",
  "bboxes": [
    {"x": 100, "y": 100, "w": 200, "h": 200, "score": 0.95}
  ]
}
```

#### 访问结果
```json
Topic: access/result/grove_vision_ai_v2_001
{
  "ts": "2025-06-05T16:30:00Z",
  "device_id": "grove_vision_ai_v2_001",
  "decision": true,
  "name": "张三",
  "distance": 0.28,
  "confidence": 0.95,
  "processing_time_ms": 280
}
```

## 📁 项目结构

```
face_rec_r2000/
├── services/                 # 核心服务
│   ├── face_embed_api/      # Hailo-8人脸嵌入API (部署到Hailo设备)
│   │   ├── app.py           # FastAPI应用 (支持并发)
│   │   ├── Dockerfile       # 容器化部署
│   │   └── requirements.txt
│   ├── qdrant/              # 向量数据库配置 (主服务器)
│   ├── mqtt/                # MQTT配置 (主服务器)
│   └── monitoring/          # 监控配置 (主服务器)
├── flows/                   # Node-RED流程文件
│   └── face_access_control.json  # 支持跨机器API调用
├── deployment/              # 部署脚本
│   └── start_services.sh    # 分布式部署脚本
├── tests/                   # 测试代码
├── docs/                    # 部署文档
├── .env.example            # 环境配置模板
└── docker-compose.yml      # 服务编排 (支持分布式)
```

## 🔧 配置说明

### 环境变量配置 (.env)

```bash
# Hailo设备配置
FACE_EMBED_API_HOST=192.168.10.179
FACE_EMBED_API_PORT=8000
FACE_EMBED_API_WORKERS=4

# 主服务器配置
QDRANT_HOST=localhost
MQTT_HOST=localhost

# 并发优化
BATCH_SIZE=3
MAX_WAIT_TIME=100
API_TIMEOUT=5000

# 设备映射
COLLECTION_grove_vision_ai_v2_001=office_entrance
COLLECTION_grove_vision_ai_v2_002=warehouse_door
```

### Docker Compose配置

```yaml
# 支持分布式部署的profile
services:
  node-red:
    environment:
      - FACE_EMBED_API_HOST=192.168.10.179  # 远程Hailo设备
      
  face-embed-api:
    profiles:
      - local-test  # 仅本地测试时启用
```

## ⚡ 性能监控

### Grafana仪表板

- **系统监控**：http://localhost:3000
- **用户名/密码**：admin/admin123
- **监控指标**：
  - API响应时间
  - 并发连接数
  - 错误率统计
  - 设备在线状态

### Prometheus指标

- FaceEmbed API性能 (192.168.10.179:8000/metrics)
- Qdrant向量库状态
- Node-RED流程状态
- MQTT消息统计

## 🚨 故障排除

### 常见问题

1. **FaceEmbed API连接失败**
```bash
# 检查Hailo设备网络
ping 192.168.10.179

# 检查API服务状态
curl http://192.168.10.179:8000/health
```

2. **并发性能不足**
```bash
# 调整worker数量
export FACE_EMBED_API_WORKERS=8

# 优化批量处理
export BATCH_SIZE=5
```

3. **Node-RED流程错误**
```bash
# 查看Node-RED日志
docker-compose logs -f node-red

# 检查环境变量配置
```

## 🔒 安全特性

- **网络隔离**：局域网部署，无外网依赖
- **API认证**：支持API Key验证
- **数据加密**：HTTPS/TLS传输
- **隐私保护**：仅存储向量，不保存原图

## 🚧 开发状态

- [x] 分布式架构设计
- [x] FaceEmbed API并发优化
- [x] Node-RED跨机器调用
- [x] Docker容器化部署
- [x] 批量处理优化
- [x] 监控和日志系统
- [x] 部署脚本和文档
- [ ] 端到端集成测试
- [ ] 性能基准测试

## 🤝 贡献指南

1. Fork项目
2. 创建特性分支 (`git checkout -b feature/distributed-deployment`)
3. 提交更改 (`git commit -m 'Add distributed deployment support'`)
4. 推送分支 (`git push origin feature/distributed-deployment`)
5. 创建Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🆘 技术支持

### 部署支持
- 📖 查看 [部署指南](docs/deployment_guide.md)
- 🐛 创建 [Issue](../../issues)
- 💬 技术讨论

### 性能优化
- 🔧 并发配置调优
- 📊 监控指标分析
- ⚡ 延迟优化建议

### 硬件选型
- 🖥️ 主服务器配置建议
- 🔌 Hailo设备选型
- 📡 网络环境要求

---

**注意**：此项目针对分布式部署进行了优化，支持多设备并发处理。建议在部署前仔细阅读 [部署指南](docs/deployment_guide.md)。
