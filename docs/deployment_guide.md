# 人脸识别门禁系统部署指南 - 简化版

## 📋 部署概览

本指南将帮助您在调试和开发环境中部署人脸识别门禁系统。系统采用简化架构，专注于核心功能。

## 🏗️ 简化系统架构

```
Grove Vision AI V2 → MQTT → Node-RED → FaceEmbed API (Hailo-8) → Qdrant → 门禁控制
```

**核心组件**：
- **Qdrant**: 向量数据库，存储人脸特征
- **MQTT Broker**: 消息传递中间件
- **Node-RED**: 业务逻辑编排（包含所有配置）
- **FaceEmbed API**: AI推理服务（运行在Hailo设备上）

## 💻 硬件要求

### 主服务器
- **CPU**: 双核心以上
- **内存**: 4GB+ RAM
- **存储**: 20GB+ 可用空间
- **网络**: 千兆以太网连接
- **软件**: Ubuntu 22.04, Docker

### Hailo设备  
- **硬件**: Raspberry Pi 5 + Hailo-8 AI加速器
- **内存**: 8GB RAM (推荐)
- **存储**: microSD卡 32GB+ 或 SSD
- **网络**: 千兆以太网连接
- **IP地址**: 192.168.10.179 (可配置)

### Grove Vision AI V2
- **型号**: Grove Vision AI V2
- **连接**: Wi-Fi/以太网到主服务器
- **电源**: 5V/2A供电

## 🚀 快速部署

### 1. 环境准备

```bash
# 克隆项目
git clone <repository_url>
cd face_rec_r2000

# 检查Docker环境
docker --version
docker-compose --version
```

### 2. 查看手动启动说明

```bash
# 推荐：查看手动启动指南（用于调试）
./deployment/start_services.sh --manual
```

### 3. 自动化启动（可选）

```bash
# 启动基础服务（Qdrant + MQTT）
./deployment/start_services.sh

# 启动完整服务（包含Node-RED）
./deployment/start_services.sh --with-nodered

# 本地测试模式（启动本地FaceEmbed API）
./deployment/start_services.sh --with-nodered --start-face-api
```

## 🔧 详细配置

### 1. 主服务器手动启动

```bash
# 1. 启动Qdrant向量数据库
docker run -d \
  --name face_access_qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v $(pwd)/services/qdrant/storage:/qdrant/storage \
  -e QDRANT__SERVICE__API_KEY=face_access_2025 \
  qdrant/qdrant:v1.9.0

# 2. 启动MQTT Broker
docker run -d \
  --name face_access_mqtt \
  -p 1883:1883 \
  -p 9001:9001 \
  -v $(pwd)/services/mqtt/mosquitto.conf:/mosquitto/config/mosquitto.conf \
  eclipse-mosquitto:2.0

# 3. 启动Node-RED
docker run -d \
  --name face_access_nodered \
  -p 1880:1880 \
  -v $(pwd)/flows:/data/flows \
  -e TZ=Asia/Shanghai \
  nodered/node-red:3.1
```

### 2. Hailo设备配置

```bash
# 连接到Hailo设备
ssh harvest@192.168.10.179

# 复制FaceEmbed API文件
# (从主服务器执行)
scp -r services/face_embed_api/ harvest@192.168.10.179:~/

# 在Hailo设备上安装依赖
cd ~/face_embed_api
pip install -r requirements.txt

# 启动FaceEmbed API
python app.py

# 后台运行（可选）
nohup python app.py > face_embed_api.log 2>&1 &
```

### 3. Node-RED配置

访问 http://localhost:1880 并进行以下配置：

#### 修改Hailo设备IP地址
在 "API URL 配置器" 节点中：
```javascript
// 配置FaceEmbed API URL - 直接在此处修改IP地址
const faceEmbedHost = '192.168.10.179';  // Hailo设备IP
const faceEmbedPort = '8000';            // FaceEmbed API端口
```

#### 设备Collection映射
在 "准备向量搜索" 节点中：
```javascript
// 设备与Collection映射配置 - 在此处添加新设备
const deviceCollectionMap = {
    'grove_vision_ai_v2_001': 'office_entrance',
    'grove_vision_ai_v2_002': 'warehouse_door',
    'grove_vision_ai_v2_003': 'lab_access',
    'default': 'default_faces'
};
```

#### 相似度阈值调整
```javascript
const threshold = 0.32;  // 相似度阈值，可在此处调整
```

#### Qdrant配置
```javascript
// Qdrant配置 - 可在此处修改Qdrant地址
const qdrantHost = 'localhost';
const qdrantPort = '6333';
```

### 4. Grove Vision AI V2配置

```bash
# 通过Grove Vision AI V2的Web界面配置：
# - MQTT服务器: 主服务器IP:1883
# - MQTT主题: vision/frames/{device_id}
# - 设备ID: grove_vision_ai_v2_001 (示例)
```

## 📡 服务访问地址

- **Node-RED编辑器**: http://localhost:1880
- **Qdrant数据库**: http://localhost:6333/dashboard
- **MQTT测试**: mqtt://localhost:1883
- **FaceEmbed API**: http://192.168.10.179:8000/docs

## 🧪 测试和验证

### 1. 服务状态检查

```bash
# 检查Docker容器
docker ps --filter "name=face_access"

# 测试Qdrant
curl http://localhost:6333/health

# 测试FaceEmbed API
curl http://192.168.10.179:8000/health

# 测试MQTT
mosquitto_pub -h localhost -t test -m "hello"
```

### 2. 功能测试

```bash
# 人脸入库测试
mosquitto_pub -h localhost -t "access/enroll/test_device" \
  -m '{"name": "张三", "action": "start"}'

# 监听访问结果
mosquitto_sub -h localhost -t "access/result/+" -v

# 模拟人脸识别数据
mosquitto_pub -h localhost -t "vision/frames/test_device" \
  -m '{
    "ts": "2025-06-05T17:30:00Z",
    "img_b64": "test_image_data",
    "bboxes": [{"x": 100, "y": 100, "w": 200, "h": 200, "score": 0.95}]
  }'
```

### 3. 性能测试

```bash
# 运行集成测试
python tests/integration_test.py

# 运行FaceEmbed API测试
python tests/test_face_embed_api.py
```

## 🔒 基础安全配置

### API认证
```bash
# Qdrant API Key（在Node-RED中配置）
api-key: face_access_2025

# 可以修改为更安全的密钥
```

### 网络安全
```bash
# 防火墙配置
sudo ufw allow 1883/tcp   # MQTT
sudo ufw allow 6333/tcp   # Qdrant
sudo ufw allow 1880/tcp   # Node-RED
sudo ufw allow 8000/tcp   # FaceEmbed API (Hailo设备)
sudo ufw enable
```

## 🚨 故障排除

### 常见问题

#### 1. FaceEmbed API连接失败
```bash
# 检查网络连接
ping 192.168.10.179

# 检查API服务状态
curl http://192.168.10.179:8000/health

# 查看Hailo设备日志
ssh harvest@192.168.10.179
tail -f ~/face_embed_api.log
```

#### 2. Qdrant连接失败
```bash
# 检查容器状态
docker logs face_access_qdrant

# 检查存储权限
ls -la services/qdrant/storage

# 重启服务
docker restart face_access_qdrant
```

#### 3. MQTT消息丢失
```bash
# 检查MQTT服务
docker logs face_access_mqtt

# 测试MQTT连接
mosquitto_sub -h localhost -t '#' -v

# 检查端口占用
netstat -an | grep 1883
```

#### 4. Node-RED配置问题
```bash
# 查看Node-RED日志
docker logs face_access_nodered

# 访问Node-RED界面
open http://localhost:1880

# 检查流程配置
# 导入 services/node_red/face_access_control.json
```

### 日志分析

```bash
# 查看所有服务日志
docker logs -f face_access_qdrant
docker logs -f face_access_mqtt
docker logs -f face_access_nodered

# Hailo设备日志
ssh harvest@192.168.10.179
tail -f ~/face_embed_api.log
```

## 📈 性能优化

### 系统调优

```bash
# Hailo设备性能优化
# 在 services/face_embed_api/app.py 中调整
WORKERS = 4  # 根据设备性能调整
LOG_LEVEL = "INFO"

# Node-RED内存优化
# 监控容器资源使用
docker stats face_access_nodered

# MQTT消息频率限制
# 建议Grove Vision AI V2发送频率为5fps
```

### 配置优化

```javascript
// Node-RED中的批量处理配置
const batchSize = 3;           // 批量大小
const maxWaitTime = 100;       // 最大等待时间(ms)
const apiTimeout = 5000;       // API超时时间(ms)
```

## 📝 维护指南

### 日常维护

- **每日**: 检查系统状态和日志
- **每周**: 清理Docker日志和临时文件
- **每月**: 更新系统软件

### 备份策略

```bash
# 备份Qdrant数据
docker cp face_access_qdrant:/qdrant/storage ./backup/qdrant_$(date +%Y%m%d)

# 备份Node-RED流程
cp services/node_red/face_access_control.json backup/

# 备份配置文件
tar -czf backup/config_$(date +%Y%m%d).tar.gz services/*/config/
```

### 服务重启

```bash
# 重启单个服务
docker restart face_access_qdrant
docker restart face_access_mqtt
docker restart face_access_nodered

# 重启FaceEmbed API (在Hailo设备上)
ssh harvest@192.168.10.179
pkill -f "python app.py"
cd ~/face_embed_api && python app.py

# 停止所有服务
docker stop face_access_qdrant face_access_mqtt face_access_nodered
```

## 📞 技术支持

### 问题诊断步骤

1. **检查服务状态**: `docker ps`
2. **查看日志**: `docker logs [container_name]`
3. **网络连通性**: `ping` 和 `curl` 测试
4. **配置验证**: 检查Node-RED中的配置

### 常用命令

```bash
# 完整系统重启
docker-compose down
docker-compose up -d

# 查看系统资源
docker stats
free -h
df -h

# 网络诊断
netstat -tulpn | grep -E '(1883|6333|1880|8000)'
```

---

## 📋 部署检查清单

完成部署后，请确认以下项目：

- [ ] Docker容器正常运行 (qdrant, mosquitto, node-red)
- [ ] Qdrant向量数据库可访问 (http://localhost:6333)
- [ ] MQTT服务正常 (mqtt://localhost:1883)
- [ ] Node-RED界面可访问 (http://localhost:1880)
- [ ] FaceEmbed API运行正常 (http://192.168.10.179:8000)
- [ ] Node-RED流程已导入并配置
- [ ] 设备Collection映射已设置
- [ ] Grove Vision AI V2设备已连接
- [ ] 基础功能测试通过
- [ ] 日志记录正常
- [ ] 备份策略已实施

**部署完成！** 🎉

---

**注意**: 此简化版本专注于核心功能，适合开发和调试环境。所有配置都在Node-RED中管理，无需复杂的环境变量设置。
