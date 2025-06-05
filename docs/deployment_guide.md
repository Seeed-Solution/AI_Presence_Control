# 人脸识别门禁系统部署指南

## 📋 部署概览

本指南将帮助您在生产环境中部署人脸识别门禁系统。系统采用微服务架构，支持多设备并发处理。

## 🏗️ 系统架构

```
Grove Vision AI V2 → MQTT → Node-RED → FaceEmbed API (Hailo-8) → Qdrant → 门禁控制
                                ↓
                         Prometheus + Grafana (监控)
```

## 💻 硬件要求

### 主控制器 (运行Hailo-8)
- **CPU**: Raspberry Pi 5 (推荐8GB RAM版本)
- **AI加速器**: Hailo-8 AI加速器模块
- **存储**: microSD卡 64GB+ (Class 10) 或 SSD
- **网络**: 千兆以太网连接
- **电源**: 5V/5A USB-C电源适配器

### 摄像头设备
- **型号**: Grove Vision AI V2
- **连接**: Wi-Fi/以太网
- **电源**: 5V/2A供电
- **安装**: 室内环境，避免强光直射

### 网络环境
- **局域网**: 稳定的千兆网络
- **MQTT**: 低延迟通信 (<10ms)
- **带宽**: 每设备约2Mbps (视频流)

## 🚀 快速部署

### 1. 环境准备

```bash
# 克隆项目
git clone <repository_url>
cd face_rec_r2000

# 检查系统要求
./deployment/start_services.sh --help
```

### 2. 服务启动

```bash
# 启动基础服务
./deployment/start_services.sh

# 启动完整服务 (包含Node-RED)
./deployment/start_services.sh --with-nodered

# 本地测试模式 (启动FaceEmbed API)
./deployment/start_services.sh --with-nodered --start-face-api
```

### 3. 系统验证

```bash
# 运行集成测试
python tests/integration_test.py

# 检查服务状态
docker-compose ps
```

## 🔧 详细配置

### Hailo设备配置

1. **安装Hailo SDK**
```bash
# 在Raspberry Pi 5上安装
sudo apt update
sudo apt install hailo-all

# 验证安装
hailortcli fw-control identify
```

2. **部署FaceEmbed API**
```bash
# 复制服务文件到Hailo设备
scp -r services/face_embed_api/ harvest@192.168.10.179:~/

# 在Hailo设备上启动
ssh harvest@192.168.10.179
cd ~/face_embed_api
pip install -r requirements.txt
python app.py
```

3. **模型文件配置**
```bash
# 下载预训练模型 (如果需要)
export FACE_DETECTION_HEF=/usr/share/hailo-models/scrfd_10g.hef
export FACE_RECOGNITION_HEF=/usr/share/hailo-models/arcface_mobilefacenet_v1.hef
```

### Grove Vision AI V2配置

1. **设备连接**
```bash
# 配置设备Wi-Fi
# 通过Grove Vision AI V2的Web界面配置网络

# 设置MQTT连接
MQTT_BROKER=192.168.10.100  # 主控制器IP
MQTT_PORT=1883
```

2. **数据格式配置**
```json
{
  "mqtt": {
    "topic": "vision/frames/{device_id}",
    "qos": 0,
    "format": "json"
  },
  "inference": {
    "model": "face_detection",
    "confidence_threshold": 0.7,
    "image_size": [480, 480]
  }
}
```

### Node-RED流程配置

1. **导入流程**
```bash
# 访问Node-RED界面
open http://localhost:1880

# 导入flows/face_access_control.json
# 配置MQTT连接和环境变量
```

2. **环境变量设置**
```javascript
// 在Node-RED设置中配置
env.QDRANT_API_KEY = "face_access_2025"
env.SIMILARITY_THRESHOLD = "0.32"
env.COLLECTION_grove_vision_ai_v2_001 = "office_entrance"
```

## 📊 监控配置

### Prometheus配置

```yaml
# services/monitoring/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'face-embed-api'
    static_configs:
      - targets: ['192.168.10.179:8000']

  - job_name: 'qdrant'
    static_configs:
      - targets: ['localhost:6333']

  - job_name: 'node-red'
    static_configs:
      - targets: ['localhost:1880']
```

### Grafana仪表板

```bash
# 访问Grafana
open http://localhost:3000
# 用户名: admin, 密码: admin123

# 导入预配置的仪表板
# 文件位置: services/monitoring/grafana/dashboards/
```

## 🔒 安全配置

### TLS加密

1. **MQTT TLS配置**
```bash
# 生成SSL证书
openssl req -x509 -newkey rsa:4096 -keyout mqtt-key.pem -out mqtt-cert.pem -days 365 -nodes

# 更新mosquitto.conf
listener 8883
protocol mqtt
cafile /mosquitto/config/ca.crt
certfile /mosquitto/config/server.crt
keyfile /mosquitto/config/server.key
```

2. **API认证**
```bash
# 更新API Key
export QDRANT_API_KEY="your-secure-api-key"
export FACE_EMBED_API_KEY="your-face-api-key"
```

### 防火墙配置

```bash
# Ubuntu/Debian
sudo ufw allow 1883/tcp   # MQTT
sudo ufw allow 8000/tcp   # FaceEmbed API
sudo ufw allow 6333/tcp   # Qdrant
sudo ufw allow 1880/tcp   # Node-RED
sudo ufw allow 3000/tcp   # Grafana
sudo ufw enable
```

## 🧪 测试和验证

### 功能测试

1. **人脸入库测试**
```bash
# 通过MQTT发送入库请求
mosquitto_pub -h localhost -t "access/enroll/test_device" \
  -m '{"name": "张三", "action": "start"}'
```

2. **人脸识别测试**
```bash
# 模拟Grove Vision AI V2数据
python tests/simulate_vision_ai.py
```

3. **性能测试**
```bash
# 延迟测试
python tests/latency_test.py

# 吞吐量测试
python tests/throughput_test.py
```

### 负载测试

```bash
# 多设备并发测试
python tests/load_test.py --devices 20 --duration 300
```

## 📈 性能优化

### 系统调优

1. **内存优化**
```bash
# 增加GPU内存分配
echo 'gpu_mem=128' >> /boot/config.txt

# 优化Docker内存限制
# 在docker-compose.yml中设置内存限制
```

2. **网络优化**
```bash
# 增加网络缓冲区
echo 'net.core.rmem_max = 16777216' >> /etc/sysctl.conf
echo 'net.core.wmem_max = 16777216' >> /etc/sysctl.conf
```

3. **存储优化**
```bash
# 使用SSD存储
# 配置tmpfs用于临时文件
tmpfs /tmp tmpfs defaults,noatime,nosuid,size=100m 0 0
```

## 🚨 故障排除

### 常见问题

1. **FaceEmbed API无法启动**
```bash
# 检查Hailo驱动
lsmod | grep hailo

# 检查模型文件
ls -la /usr/share/hailo-models/

# 查看API日志
tail -f services/face_embed_api/face_embed_api.log
```

2. **Qdrant连接失败**
```bash
# 检查服务状态
docker-compose logs qdrant

# 测试连接
curl http://localhost:6333/health
```

3. **MQTT消息丢失**
```bash
# 检查MQTT broker状态
docker-compose logs mosquitto

# 测试MQTT连接
mosquitto_sub -h localhost -t "vision/frames/+"
```

### 日志分析

```bash
# 系统日志
docker-compose logs -f

# 特定服务日志
docker-compose logs -f qdrant
docker-compose logs -f mosquitto

# 应用日志
tail -f services/face_embed_api/face_embed_api.log
```

## 📝 维护计划

### 日常维护

- **每日**: 检查系统状态和性能指标
- **每周**: 清理日志文件和临时数据
- **每月**: 更新系统软件和安全补丁
- **每季度**: 备份人脸数据库和配置文件

### 备份策略

```bash
# 备份Qdrant数据
docker exec face_access_qdrant qdrant-backup

# 备份Node-RED流程
cp services/node_red/data/flows.json backup/

# 备份配置文件
tar -czf config_backup.tar.gz .env services/*/config/
```

### 扩展计划

1. **横向扩展**
   - 添加更多Hailo设备节点
   - 配置负载均衡器
   - 实现数据分片

2. **功能扩展**
   - 集成活体检测
   - 添加年龄/性别识别
   - 实现Web管理界面

## 📞 技术支持

如遇到问题，请按以下步骤：

1. 查看本文档的故障排除部分
2. 检查GitHub Issues
3. 运行诊断脚本: `python tests/diagnostic.py`
4. 收集日志文件并联系技术支持

---

## 📋 检查清单

部署完成后，请确认以下项目：

- [ ] 所有Docker容器正常运行
- [ ] FaceEmbed API健康检查通过
- [ ] Qdrant向量数据库可访问
- [ ] MQTT消息正常传输
- [ ] Node-RED流程已导入并运行
- [ ] Grove Vision AI V2设备已连接
- [ ] 监控系统正常工作
- [ ] 安全配置已启用
- [ ] 备份策略已实施
- [ ] 团队成员已培训

部署成功！🎉
