# Face Recognition Access Control System - Simplified Deployment Guide

## 📋 Deployment Overview

This guide will help you deploy the face recognition access control system in a debug and development environment. The system uses a simplified architecture, focusing on core functionality.

## 🏗️ Simplified System Architecture

```
Grove Vision AI V2 → MQTT → Node-RED → FaceEmbed API (Hailo-8) → Qdrant → Access Control
```

**Core Components**:
- **Qdrant**: Vector database for storing face embeddings.
- **MQTT Broker**: Message-passing middleware.
- **Node-RED**: Business logic orchestration (contains all configurations).
- **FaceEmbed API**: AI inference service (running on a Hailo device).

## 💻 Hardware Requirements

### Main Server
- **CPU**: Dual-core or higher
- **Memory**: 4GB+ RAM
- **Storage**: 20GB+ free space
- **Network**: Gigabit Ethernet connection
- **Software**: Ubuntu 22.04, Docker

### Hailo Device
- **Hardware**: Raspberry Pi 5 + Hailo-8 AI Accelerator
- **Memory**: 8GB RAM (recommended)
- **Storage**: 32GB+ microSD card or SSD
- **Network**: Gigabit Ethernet connection
- **IP Address**: 192.168.10.179 (configurable)

### Grove Vision AI V2
- **Model**: Grove Vision AI V2
- **Connection**: Wi-Fi/Ethernet to the main server
- **Power**: 5V/2A power supply

## 🚀 Quick Deployment

### 1. Environment Setup

```bash
# Clone the project
git clone <repository_url>
cd face_rec_r2000

# Check Docker environment
docker --version
docker-compose --version
```

### 2. View Manual Startup Instructions

```bash
# Recommended: View the manual startup guide (for debugging)
./deployment/start_services.sh --manual
```

### 3. Automated Startup (Optional)

```bash
# Start basic services (Qdrant + MQTT)
./deployment/start_services.sh

# Start full services (including Node-RED)
./deployment/start_services.sh --with-nodered
```

## 🔧 Detailed Configuration

### 1. Main Server Manual Startup

```bash
# 1. Start Qdrant Vector Database
docker run -d \
  --name face_access_qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v $(pwd)/services/qdrant/storage:/qdrant/storage \
  -e QDRANT__SERVICE__API_KEY=face_access_2025 \
  qdrant/qdrant:v1.9.0

# 2. Start MQTT Broker
docker run -d \
  --name face_access_mqtt \
  -p 1883:1883 \
  -p 9001:9001 \
  -v $(pwd)/services/mqtt/mosquitto.conf:/mosquitto/config/mosquitto.conf \
  eclipse-mosquitto:2.0

# 3. Start Node-RED
docker run -d \
  --name face_access_nodered \
  -p 1880:1880 \
  -v $(pwd)/services/node_red/data:/data \
  -e TZ=Asia/Shanghai \
  nodered/node-red:3.1
```
*Note: The startup script `start_services.sh` automatically copies the flow file `services/node_red/face_access_control.json` into the `services/node_red/data` volume.*

### 2. Hailo Device Configuration

```bash
# Connect to the Hailo device
ssh user@192.168.10.179

# Copy the FaceEmbed API files
# (Execute from the main server)
scp -r services/face_embed_api/ user@192.168.10.179:~/

# On the Hailo device, install dependencies
cd ~/face_embed_api
pip install -r requirements.txt

# Start the FaceEmbed API
python app.py

# Run in the background (optional)
nohup python app.py > face_embed_api.log 2>&1 &
```

### 3. Node-RED Configuration

Access http://localhost:1880 and perform the following configurations. **All settings are managed within Node-RED nodes, eliminating the need for environment variables.**

#### Modify Hailo Device IP Address
In the **`[Global Config (Load on Start)]`** node:
```javascript
// Configure FaceEmbed API URL - modify the IP address here
flow.set('hailo_host', '192.168.10.179'); // Hailo device IP
flow.set('hailo_port', '8000');           // FaceEmbed API port
```

#### Map Devices to Collections
In the **`Prepare Vector Search`** node:
```javascript
// Device-to-Collection mapping - add new devices here
const deviceCollectionMap = {
    'grove_vision_ai_v2_001': 'office_entrance',
    'grove_vision_ai_v2_002': 'warehouse_door',
    'grove_vision_ai_v2_003': 'lab_access',
    'default': 'default_faces'
};
```

#### Adjust Similarity Threshold
In the **`Prepare Vector Search`** node:
```javascript
const threshold = 0.32;  // Similarity threshold, adjustable here
```

#### Configure Qdrant
In the **`[Global Config (Load on Start)]`** node:
```javascript
// Qdrant Configuration - modify Qdrant address here
flow.set('qdrant_host', 'localhost');
flow.set('qdrant_port', '6333');
```

### 4. Grove Vision AI V2 Configuration

```bash
# Configure via the Grove Vision AI V2 Web UI:
# - MQTT Server: <main_server_ip>:1883
# - MQTT Topic: vision/frames/{device_id}
# - Device ID: grove_vision_ai_v2_001 (example)
```

## 📡 Service URLs

- **Node-RED Editor**: http://localhost:1880
- **Qdrant Dashboard**: http://localhost:6333/dashboard
- **MQTT Broker**: mqtt://localhost:1883
- **FaceEmbed API**: http://192.168.10.179:8000/docs

## 🧪 Testing and Validation

### 1. Service Health Checks

```bash
# Check Docker containers
docker ps --filter "name=face_access"

# Test Qdrant
curl http://localhost:6333/health

# Test FaceEmbed API
curl http://192.168.10.179:8000/health

# Test MQTT
mosquitto_pub -h localhost -t test -m "hello"
```

### 2. Functional Testing

```bash
# Test Face Enrollment
mosquitto_pub -h localhost -t "access/enroll/test_device" \
  -m '{"name": "John Doe", "action": "start"}'

# Listen for Access Results
mosquitto_sub -h localhost -t "access/result/+" -v

# Simulate Face Recognition Data
mosquitto_pub -h localhost -t "vision/frames/test_device" \
  -m '{
    "ts": "2025-06-05T17:30:00Z",
    "img_b64": "test_image_data",
    "bboxes": [{"x": 100, "y": 100, "w": 200, "h": 200, "score": 0.95}]
  }'
```

### 3. Performance Testing

```bash
# Run integration tests
python tests/integration_test.py

# Run FaceEmbed API tests
python tests/test_face_embed_api.py
```

## 🔒 Basic Security Configuration

### API Authentication
```bash
# Qdrant API Key (configured in Node-RED)
api-key: face_access_2025

# This can be changed to a more secure key.
```

### Network Security
```bash
# Firewall configuration
sudo ufw allow 1883/tcp   # MQTT
sudo ufw allow 6333/tcp   # Qdrant
sudo ufw allow 1880/tcp   # Node-RED
sudo ufw allow 8000/tcp   # FaceEmbed API (on Hailo device)
sudo ufw enable
```

## 🚨 Troubleshooting

### Common Issues

#### 1. FaceEmbed API Connection Failure
```bash
# Check network connectivity
ping 192.168.10.179

# Check API service status
curl http://192.168.10.179:8000/health

# View Hailo device logs
ssh user@192.168.10.179
tail -f ~/face_embed_api.log
```

#### 2. Qdrant Connection Failure
```bash
# Check container logs
docker logs face_access_qdrant

# Check storage permissions
ls -la services/qdrant/storage

# Restart the service
docker restart face_access_qdrant
```

#### 3. MQTT Message Loss
```bash
# Check MQTT service logs
docker logs face_access_mqtt

# Test MQTT connection
mosquitto_sub -h localhost -t '#' -v

# Check for port conflicts
netstat -an | grep 1883
```

#### 4. Node-RED Configuration Issues
```bash
# View Node-RED logs
docker logs face_access_nodered

# Access the Node-RED UI
open http://localhost:1880

# Check flow configuration
# Import from services/node_red/face_access_control.json
```

### Log Analysis

```bash
# View all service logs
docker logs -f face_access_qdrant
docker logs -f face_access_mqtt
docker logs -f face_access_nodered

# Hailo device logs
ssh user@192.168.10.179
tail -f ~/face_embed_api.log
```

## 📈 Performance Optimization

### System Tuning

```bash
# Hailo device performance optimization
# Adjust in services/face_embed_api/app.py
WORKERS = 4  # Adjust based on device performance
LOG_LEVEL = "INFO"

# Node-RED memory optimization
# Monitor container resource usage
docker stats face_access_nodered

# MQTT message rate limiting
# Recommended sending frequency for Grove Vision AI V2 is 5fps
```

### Configuration Optimization

```javascript
// Batch processing settings in Node-RED
const batchSize = 3;           // Batch size
const maxWaitTime = 100;       // Max wait time (ms)
const apiTimeout = 5000;       // API timeout (ms)
```

## 📝 Maintenance Guide

### Routine Maintenance

- **Daily**: Check system status and logs.
- **Weekly**: Clean up Docker logs and temporary files.
- **Monthly**: Update system software.

### Backup Strategy

```bash
# Backup Qdrant data
docker cp face_access_qdrant:/qdrant/storage ./backup/qdrant_$(date +%Y%m%d)

# Backup Node-RED flow
cp services/node_red/face_access_control.json backup/

# Backup configuration files
tar -czf backup/config_$(date +%Y%m%d).tar.gz services/*/
```

### Service Restart

```bash
# Restart a single service
docker restart face_access_qdrant
docker restart face_access_mqtt
docker restart face_access_nodered

# Restart FaceEmbed API (on Hailo device)
ssh user@192.168.10.179
pkill -f "python app.py"
cd ~/face_embed_api && python app.py

# Stop all services
docker stop face_access_qdrant face_access_mqtt face_access_nodered
```

## 📞 Technical Support

### Diagnostic Steps

1. **Check Service Status**: `docker ps`
2. **View Logs**: `docker logs [container_name]`
3. **Network Connectivity**: `ping` and `curl` tests
4. **Configuration Verification**: Check settings in Node-RED.

### Common Commands

```bash
# Full system restart
docker-compose down
docker-compose up -d

# Check system resources
docker stats
free -h
df -h

# Network diagnostics
netstat -tulpn | grep -E '(1883|6333|1880|8000)'
```

---

## 📋 Deployment Checklist

After completing the deployment, please verify the following:

- [ ] Docker containers are running correctly (qdrant, mosquitto, node-red).
- [ ] Qdrant vector database is accessible (http://localhost:6333).
- [ ] MQTT service is running (mqtt://localhost:1883).
- [ ] Node-RED UI is accessible (http://localhost:1880).
- [ ] FaceEmbed API is running correctly (http://192.168.10.179:8000).
- [ ] Node-RED flow has been imported and configured.
- [ ] Device-to-Collection mapping is set up.
- [ ] Grove Vision AI V2 devices are connected.
- [ ] Basic functional tests pass.
- [ ] Logging is working correctly.
- [ ] A backup strategy has been implemented.

**Deployment Complete!** 🎉

---

**Note**: This simplified version focuses on core functionality and is suitable for development and debugging environments. All configuration is managed in Node-RED, eliminating the need for complex environment variable setups.
