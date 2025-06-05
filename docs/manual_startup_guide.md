# 手动启动服务指南

本文档提供人脸识别门禁系统各服务的手动启动方式，适用于调试和开发阶段。

## 🎯 系统组件

- **Qdrant向量数据库**：存储人脸特征向量
- **MQTT Broker (Mosquitto)**：消息传递
- **Node-RED**：业务逻辑控制流程
- **FaceEmbed API**：人脸特征提取服务（运行在Hailo设备上）

## 📋 启动顺序

### 1. 启动基础服务 (主服务器)

#### 1.1 启动Qdrant向量数据库
```bash
docker run -d \
  --name face_access_qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v $(pwd)/services/qdrant/storage:/qdrant/storage \
  -e QDRANT__SERVICE__HTTP_PORT=6333 \
  -e QDRANT__SERVICE__GRPC_PORT=6334 \
  -e QDRANT__LOG_LEVEL=INFO \
  -e QDRANT__SERVICE__API_KEY=face_access_2025 \
  qdrant/qdrant:v1.9.0
```

#### 1.2 启动MQTT Broker
```bash
docker run -d \
  --name face_access_mqtt \
  -p 1883:1883 \
  -p 9001:9001 \
  -v $(pwd)/services/mqtt/mosquitto.conf:/mosquitto/config/mosquitto.conf \
  -v $(pwd)/services/mqtt/data:/mosquitto/data \
  -v $(pwd)/services/mqtt/log:/mosquitto/log \
  eclipse-mosquitto:2.0
```

#### 1.3 启动Node-RED
```bash
docker run -d \
  --name face_access_nodered \
  -p 1880:1880 \
  -v $(pwd)/services/node_red/data:/data \
  -v $(pwd)/flows:/data/flows \
  -e TZ=Asia/Shanghai \
  nodered/node-red:3.1
```

### 2. 启动FaceEmbed API (Hailo设备: 192.168.10.179)

#### 2.1 连接到Hailo设备
```bash
ssh harvest@192.168.10.179
```

#### 2.2 安装依赖 (首次运行)
```bash
cd ~/face_embed_api
pip install -r requirements.txt
```

#### 2.3 启动FaceEmbed API
```bash
python app.py
```

或者使用后台运行：
```bash
nohup python app.py > face_embed_api.log 2>&1 &
```

## 🔧 服务配置验证

### 验证Qdrant
```bash
curl http://localhost:6333/health
```

### 验证MQTT
```bash
mosquitto_pub -h localhost -t test -m "hello"
```

### 验证Node-RED
访问：http://localhost:1880

### 验证FaceEmbed API
```bash
curl http://192.168.10.179:8000/health
```

## 📡 访问地址

- **Node-RED编辑器**：http://localhost:1880
- **Qdrant仪表板**：http://localhost:6333/dashboard
- **FaceEmbed API文档**：http://192.168.10.179:8000/docs

## 🛠️ 配置修改

### 修改Hailo设备IP地址
在Node-RED中，编辑"API URL 配置器"节点：
```javascript
const faceEmbedHost = '192.168.10.179';  // 修改为实际IP
```

### 修改设备Collection映射
在Node-RED中，编辑"准备向量搜索"节点：
```javascript
const deviceCollectionMap = {
    'grove_vision_ai_v2_001': 'office_entrance',
    'grove_vision_ai_v2_002': 'warehouse_door',
    // 添加新设备映射
};
```

### 修改相似度阈值
在Node-RED中，编辑"准备向量搜索"节点：
```javascript
const threshold = 0.32;  // 调整阈值 (0-1)
```

### 修改Qdrant配置
在Node-RED中，编辑"准备向量搜索"节点：
```javascript
const qdrantHost = 'localhost';  // Qdrant地址
const qdrantPort = '6333';       // Qdrant端口
```

## 🔍 调试技巧

### 查看服务日志
```bash
# Qdrant日志
docker logs -f face_access_qdrant

# MQTT日志
docker logs -f face_access_mqtt

# Node-RED日志
docker logs -f face_access_nodered

# FaceEmbed API日志 (在Hailo设备上)
tail -f face_embed_api.log
```

### 测试MQTT消息
```bash
# 订阅所有消息
mosquitto_sub -h localhost -t '#' -v

# 发送测试消息
mosquitto_pub -h localhost -t 'vision/frames/test_device' -m '{
  "ts": "2025-06-05T17:30:00Z",
  "img_b64": "test_image_data",
  "bboxes": [{"x": 100, "y": 100, "w": 200, "h": 200, "score": 0.95}]
}'
```

### 测试FaceEmbed API
```bash
curl -X POST http://192.168.10.179:8000/embed \
  -H "Content-Type: application/json" \
  -d '{
    "image_base64": "test_image_data",
    "bbox": {"x": 100, "y": 100, "w": 200, "h": 200}
  }'
```

## 🔄 重启服务

### 重启单个服务
```bash
# 重启Qdrant
docker restart face_access_qdrant

# 重启MQTT
docker restart face_access_mqtt

# 重启Node-RED
docker restart face_access_nodered

# 重启FaceEmbed API (在Hailo设备上)
pkill -f "python app.py"
python app.py
```

### 停止所有服务
```bash
# 主服务器
docker stop face_access_qdrant face_access_mqtt face_access_nodered

# Hailo设备
pkill -f "python app.py"
```

## 📋 常见问题

### 1. Node-RED无法连接MQTT
- 检查MQTT服务是否启动：`docker ps | grep mqtt`
- 检查端口占用：`netstat -an | grep 1883`

### 2. FaceEmbed API连接失败
- 检查Hailo设备网络：`ping 192.168.10.179`
- 检查API服务状态：`curl http://192.168.10.179:8000/health`

### 3. Qdrant存储失败
- 检查存储目录权限：`ls -la services/qdrant/storage`
- 查看Qdrant日志：`docker logs face_access_qdrant`

### 4. 人脸识别精度问题
- 调整相似度阈值（在Node-RED中）
- 检查人脸质量和光照条件
- 查看处理日志（Node-RED Debug面板）

## ⚙️ 性能调优

### FaceEmbed API性能
在Hailo设备上修改`app.py`：
```python
WORKERS = 4  # 调整worker数量
LOG_LEVEL = "INFO"  # 调整日志级别
```

### Node-RED内存使用
```bash
# 查看Node-RED内存使用
docker stats face_access_nodered
```

### MQTT消息频率限制
根据实际需要调整Grove Vision AI V2的发送频率，建议5fps。

---

**注意**：此手动启动方式适用于开发和调试阶段。生产环境建议使用自动化部署脚本。
