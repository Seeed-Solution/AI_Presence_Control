# Development & API Documentation

This document provides a deep dive into the system's architecture, API specifications, and development guidelines.

## 🔧 Concurrency Performance Optimization

### FaceEmbed API Concurrency Configuration

```python
# services/face_embed_api/app.py
# Supports multiple worker processes
WORKERS=4 # Adjust based on Hailo device performance

# Asynchronous processing
async def extract_embedding(...)
```

### Node-RED Batch Processing

```javascript
// Batch processing configuration
BATCH_SIZE=3           // Batch size
MAX_WAIT_TIME=100      // Maximum wait time (ms)
API_TIMEOUT=5000       // API timeout (ms)
```

### Performance Metrics

- **Single Device Latency**: < 40ms (FaceEmbed API)
- **End-to-End Latency**: < 300ms (Full pipeline)
- **Concurrent Processing**: 20+ devices simultaneously
- **Throughput**: 5fps/device

## 📡 API Interface

### FaceEmbed API

Due to the limitation that Hailo-8 hardware can only load and run one AI model at a time, the API has been refactored into an all-in-one interface to simplify calls and optimize performance.

#### Primary Recommended Endpoint

##### Detect and Embed Faces
This endpoint is the recommended method for the standard workflow. It performs face detection, landmark localization, face alignment, and feature vector extraction in a single API call.

```bash
POST http://192.168.10.179:8000/detect_and_embed
Content-Type: application/json

{
  "image_base64": "base64_encoded_image"
}
```
**Response Example (one face detected)**:
```json
[
  {
    "bbox": [100, 100, 200, 200],
    "landmarks": [
      [120, 120], [180, 120], [150, 150], [130, 180], [170, 180]
    ],
    "embedding": [0.123, -0.456, ..., 0.789]
  }
]
```
*If no faces are detected, it returns an empty list `[]`.*

---

#### Advanced / Manual Endpoints

These endpoints are for advanced scenarios, such as when you have already obtained the bounding box and landmarks through other means.

##### Single Image (Manual)
```bash
POST http://192.168.10.179:8000/embed
Content-Type: application/json

{
  "image_base64": "base64_encoded_image",
  "bbox": {"x": 100, "y": 100, "w": 200, "h": 200},
  "landmarks": [
      {"x": 120, "y": 120},
      {"x": 180, "y": 120},
      {"x": 150, "y": 150},
      {"x": 130, "y": 180},
      {"x": 170, "y": 180}
  ]
}
```

##### Batch Processing (Manual)
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

### MQTT Message Format

#### Vision Input
```json
Topic: vision/frames/grove_vision_ai_v2_001
{
  "ts": "2025-06-05T16:30:00Z",
  "img_b64": "base64_image_data"
}
```
*Note: This is the standardized format after being processed by Node-RED. For details, see the [Data Flow Documentation](DATA_FLOW.md).*

#### Access Result
```json
Topic: access/result/grove_vision_ai_v2_001
{
  "ts": "2025-06-05T16:30:00Z",
  "device_id": "grove_vision_ai_v2_001",
  "decision": true,
  "name": "John Doe",
  "distance": 0.28,
  "confidence": 0.95,
  "processing_time_ms": 280,
  "matched_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef"
}
```

#### Face Enrollment
```json
Topic: access/enroll/{device_id}
{
  "name": "Jane Smith",
  "action": "start",
  "collection": "office_entrance"
}
```

## 📁 Project Structure

```
face_rec_r2000/
├── services/                 # Core services
│   ├── face_embed_api/      # ✅ Hailo-8 Face Embedding API (Validated, Deployed Standalone)
│   │   ├── src/             # Source code directory
│   │   │   └── face_embed_api/
│   │   │       ├── app.py   # FastAPI Application (Concurrency supported)
│   │   │       └── utils.py # Hailo Async Inference Engine
│   │   ├── tests/           # Complete test suite (28 tests, 100% pass)
│   │   ├── scripts/         # Start and test scripts
│   │   ├── models/          # AI model files (arcface_mobilefacenet.hef, scrfd_10g.hef)
│   │   └── docs/            # API documentation and test reports
│   ├── qdrant/              # Vector database configuration (Main Server)
│   ├── mqtt/                # MQTT configuration (Main Server)
│   └── node_red/            # Node-RED data and configuration
│       ├── data/            # Node-RED runtime data
│       └── face_access_control.json  # Face recognition flow configuration
├── deployment/              # Deployment scripts
│   └── start_services.sh    # Distributed deployment script (Main Server)
├── tests/                   # Integration test code
├── docs/                    # Deployment documentation
└── docker-compose.yml       # Main Server service orchestration (Qdrant + MQTT + Node-RED)
```

**Key Notes**:
- ✅ **FaceEmbed API**: Hardware integration is complete and verified, running on a dedicated Hailo device.
- 🐳 **Docker Services**: Only includes main server components, not AI services requiring direct hardware access.
- 🌐 **Distributed Architecture**: A field-proven cross-machine deployment model.
- ⚙️ **Centralized Configuration**: All parameters are managed within a single Node-RED node, eliminating the need for `.env` files.

## 🔧 Configuration Details

The latest version of this system uses a **radically simplified** configuration method. All addresses and critical parameters for external dependencies (Hailo API, Qdrant DB) are **managed centrally within a single Node-RED node**. There is no need to handle `.env` files or modify Docker Compose variables.

1.  **After starting services, access Node-RED**: `http://<main-server-ip>:1880`
2.  **Find the `[Global Config (Load on Start)]` node**, located in the top-left corner of the "Face Access Control" flow.
3.  **Double-click the node to edit all configurations**, then click "Deploy" to apply changes.

```javascript
// Example from inside the [Global Config (Load on Start)] node

// Qdrant Vector Database Configuration
flow.set('qdrant_host', 'localhost');
flow.set('qdrant_port', '6333');
flow.set('qdrant_api_key', 'face_access_2025');

// Hailo AI Chip (Face Vector API) Configuration
flow.set('hailo_host', '192.168.10.179');
flow.set('hailo_port', '8000');

// Grove Vision AI Camera Configuration
flow.set('image_width', 480);
flow.set('image_height', 480);
```

## 🚨 Troubleshooting

### Common Issues

1. **FaceEmbed API Connection Failed**
```bash
# Check Hailo device network connectivity
ping 192.168.10.179

# Check API service status
curl http://192.168.10.179:8000/health
```

2. **Insufficient Concurrent Performance**
```bash
# Adjust the number of workers
export FACE_EMBED_API_WORKERS=8

# Optimize batch processing
export BATCH_SIZE=5
```

3. **Node-RED Flow Errors**
```bash
# View Node-RED logs
docker-compose logs -f node-red

# Check environment variable configurations
```

## 🔒 Security Features

- **Network Isolation**: Deployed on a local area network with no external internet dependency.
- **API Authentication**: Supports API Key validation.
- **Data Encryption**: Supports HTTPS/TLS for data in transit.
- **Privacy Protection**: Stores only vector embeddings, not original images.

## 🚧 Development Status

- [x] Distributed Architecture Design
- [x] FaceEmbed API Concurrency Optimization
- [x] Cross-Machine Calls in Node-RED
- [x] Docker Containerization (Main Server)
- [x] Batch Processing Optimization
- [x] System Simplification and Centralized Configuration
- [x] Deployment Scripts and Documentation
- [x] ✅ **Full English Documentation and Code Comments** (All user-facing docs translated)
- [x] ✅ **Hailo-8 Hardware Integration Validation** (28 tests passed, 3-18ms inference)
- [x] ✅ **FaceEmbed API Production Deployment** (Async inference, 512-dim vectors)
- [x] ✅ **Cross-Network API Call Validation** (Node-RED ↔ Hailo Device)
- [x] Grove Vision AI V2 Full Integration Test
- [x] End-to-End Distributed Flow Validation
- [ ] Multi-Device Concurrent Performance Test

## 🤝 Contribution Guide

1. Fork the project
2. Create a feature branch (`git checkout -b feature/distributed-deployment`)
3. Commit your changes (`git commit -m 'Add distributed deployment support'`)
4. Push to the branch (`git push origin feature/distributed-deployment`)
5. Create a Pull Request

## 🆘 Technical Support

### Documentation
- 📄 **[Data Flow and Formats](docs/DATA_FLOW.md)**: Detailed documentation on data flow and formats between modules.

### Deployment Support
- 📖 See the [Deployment Guide](docs/deployment_guide.md)
- 🐛 Create an [Issue](../../issues)
- 💬 Join the technical discussion

### Performance Optimization
- 🔧 Concurrency configuration tuning
- 📊 Monitoring metric analysis
- ⚡ Latency optimization suggestions

### Hardware Selection
- 🖥️ Main server configuration recommendations
- 🔌 Hailo device selection
- 📡 Network environment requirements

---

**Note**: This project is optimized for distributed deployment and supports concurrent processing from multiple devices. It is recommended to carefully read the [Deployment Guide](docs/deployment_guide.md) before deployment. 