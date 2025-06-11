# Manual Service Startup Guide

This document provides instructions for manually starting the services of the face recognition access control system, suitable for debugging and development.

## 🎯 System Components

- **Qdrant Vector Database**: Stores face feature vectors.
- **MQTT Broker (Mosquitto)**: Handles message passing.
- **Node-RED**: Controls the business logic flow.
- **FaceEmbed API**: Face feature extraction service (runs on the Hailo device).

## 📋 Startup Sequence

### 1. Start Infrastructure Services (on Main Server)

#### 1.1 Start Qdrant Vector Database
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

#### 1.2 Start MQTT Broker
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

#### 1.3 Start Node-RED
```bash
docker run -d \
  --name face_access_nodered \
  -p 1880:1880 \
  -v $(pwd)/services/node_red/data:/data \
  -e TZ=Asia/Shanghai \
  nodered/node-red:3.1
```
*Note: Before running, ensure `face_access_control.json` is copied into `services/node_red/data/`. The automated script `./deployment/start_services.sh` handles this.*

### 2. Start FaceEmbed API (on Hailo Device: e.g., 192.168.10.179)

#### 2.1 Connect to the Hailo Device
```bash
ssh user@192.168.10.179
```

#### 2.2 Install Dependencies (First time only)
```bash
cd ~/face_embed_api
pip install -r requirements.txt
```

#### 2.3 Start FaceEmbed API
```bash
python app.py
```

Or run in the background:
```bash
nohup python app.py > face_embed_api.log 2>&1 &
```

## 🔧 Service Configuration and Verification

### Verify Qdrant
```bash
curl http://localhost:6333/health
```

### Verify MQTT
```bash
mosquitto_pub -h localhost -t test -m "hello"
```

### Verify Node-RED
Access: http://localhost:1880

### Verify FaceEmbed API
```bash
curl http://192.168.10.179:8000/health
```

## 📡 Service URLs

- **Node-RED Editor**: http://localhost:1880
- **Qdrant Dashboard**: http://localhost:6333/dashboard
- **FaceEmbed API Docs**: http://192.168.10.179:8000/docs

## 🛠️ Modifying Configurations

All critical configurations are managed within Node-RED nodes for simplicity.

### Change Hailo Device IP Address
In Node-RED, edit the **`[Global Config (Load on Start)]`** node:
```javascript
// Change to your actual IP
flow.set('hailo_host', '192.168.10.179');
```

### Change Device-to-Collection Mapping
In Node-RED, edit the **`Prepare Vector Search`** node:
```javascript
const deviceCollectionMap = {
    'grove_vision_ai_v2_001': 'office_entrance',
    'grove_vision_ai_v2_002': 'warehouse_door',
    // Add new device mappings here
};
```

### Change Similarity Threshold
In Node-RED, edit the **`Prepare Vector Search`** node:
```javascript
// Adjust the threshold (0-1)
const threshold = 0.32;
```

### Change Qdrant Configuration
In Node-RED, edit the **`[Global Config (Load on Start)]`** node:
```javascript
flow.set('qdrant_host', 'localhost'); // Qdrant address
flow.set('qdrant_port', '6333');      // Qdrant port
```

## 🔍 Debugging Tips

### View Service Logs
```bash
# Qdrant Logs
docker logs -f face_access_qdrant

# MQTT Logs
docker logs -f face_access_mqtt

# Node-RED Logs
docker logs -f face_access_nodered

# FaceEmbed API Logs (on Hailo device)
tail -f face_embed_api.log
```

### Test MQTT Messages
```bash
# Subscribe to all topics
mosquitto_sub -h localhost -t '#' -v

# Publish a test message
mosquitto_pub -h localhost -t 'vision/frames/test_device' -m '{
  "ts": "2025-06-05T17:30:00Z",
  "img_b64": "test_image_data",
  "bboxes": [{"x": 100, "y": 100, "w": 200, "h": 200, "score": 0.95}]
}'
```

### Test FaceEmbed API
```bash
curl -X POST http://192.168.10.179:8000/detect_and_embed \
  -H "Content-Type: application/json" \
  -d '{
    "image_base64": "your_base64_encoded_image_string"
  }'
```

## 🔄 Restarting Services

### Restart a Single Service
```bash
# Restart Qdrant
docker restart face_access_qdrant

# Restart MQTT
docker restart face_access_mqtt

# Restart Node-RED
docker restart face_access_nodered

# Restart FaceEmbed API (on Hailo device)
pkill -f "python app.py"
python app.py
```

### Stop All Services
```bash
# On the main server
docker stop face_access_qdrant face_access_mqtt face_access_nodered

# On the Hailo device
pkill -f "python app.py"
```

## 📋 Common Issues

### 1. Node-RED cannot connect to MQTT
- Check if the MQTT service is running: `docker ps | grep mqtt`
- Check for port conflicts: `netstat -an | grep 1883`

### 2. FaceEmbed API connection failed
- Check network to Hailo device: `ping 192.168.10.179`
- Check API service status: `curl http://192.168.10.179:8000/health`

### 3. Qdrant storage failure
- Check storage directory permissions: `ls -la services/qdrant/storage`
- View Qdrant logs: `docker logs face_access_qdrant`

### 4. Face recognition accuracy issues
- Adjust the similarity threshold (in Node-RED).
- Check face quality and lighting conditions.
- View processing logs in the Node-RED Debug panel.

## ⚙️ Performance Tuning

### FaceEmbed API Performance
On the Hailo device, modify `app.py`:
```python
WORKERS = 4  # Adjust worker count
LOG_LEVEL = "INFO"  # Adjust log level
```

### Node-RED Memory Usage
```bash
# Check Node-RED memory usage
docker stats face_access_nodered
```

### MQTT Message Frequency
Adjust the sending frequency of the Grove Vision AI V2 as needed, 5fps is recommended.

---

**Note**: This manual startup method is intended for development and debugging. For production environments, using the automated deployment script is recommended.
