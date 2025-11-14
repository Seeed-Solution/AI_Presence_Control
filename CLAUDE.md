# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI_Presence_Control is a distributed edge face recognition access control system based on Hailo-8 AI accelerator and Grove Vision AI V2. The system supports multi-device concurrency and cross-machine deployment with <300ms end-to-end latency.

### System Architecture

The system uses a distributed architecture with three main components:

1. **Main Server** (Node-RED + MQTT Broker)
   - Business logic orchestration in Node-RED
   - MQTT broker for device communication
   - Runs in Docker containers

2. **Hailo Device** (FaceEmbed API on Raspberry Pi 5 + Hailo-8)
   - AI inference service at `192.168.10.179:8000`
   - Face detection (SCRFD) and embedding extraction (ArcFace MobileFaceNet)
   - 512-dim L2-normalized vectors, 3-18ms inference latency
   - Runs as native Python process (NOT containerized, requires direct hardware access)
   - 100% test coverage (28/28 tests passed)

3. **Grove Vision AI V2** (Multiple edge devices)
   - Face capture and image transmission via MQTT
   - Supports multiple concurrent devices

### Key Design Decisions

- **No External Vector Database**: FaceEmbed API includes built-in SQLite vector storage, eliminating the need for Qdrant or similar services
- **Centralized Configuration**: All configuration is managed in Node-RED's `[Global Config (Load on Start)]` node - no `.env` files needed
- **Hailo Device Runs Natively**: Cannot be containerized due to direct hardware requirements (PCIe driver, HailoRT)
- **MQTT-Based Communication**: Grove devices communicate with main server via MQTT topics

## Common Commands

### Main Server (Docker Services)

```bash
# Start main server services (MQTT + Node-RED)
./deployment/start_services.sh --with-nodered

# View manual startup instructions
./deployment/start_services.sh --manual

# Stop all services
docker-compose down

# View service logs
docker logs -f face_access_mqtt
docker logs -f face_access_nodered

# Check service status
docker ps --filter "name=face_access"
```

### FaceEmbed API (Hailo Device)

**Note**: Commands must be run on the Hailo device at `192.168.10.179` (user: harvest, password: 12345678)

```bash
# SSH to Hailo device
ssh harvest@192.168.10.179

# Navigate to project
cd ~/face_embed_api/services/face_embed_api

# Activate virtual environment
source .venv/bin/activate

# Start the API service
PYTHONPATH=src uv run uvicorn app:app --host 0.0.0.0 --port 8000

# Alternative: Use convenience script
cd ~/face_embed_api
python scripts/start_server.py

# Health check (from any machine)
curl http://192.168.10.179:8000/health

# View API documentation
open http://192.168.10.179:8000/docs
```

### Testing

```bash
# Run all FaceEmbed API tests (on Hailo device)
cd ~/face_embed_api/services/face_embed_api
uv run pytest -v

# Run specific test types
pytest tests/unit/ -v
pytest tests/integration/ -v

# Run integration tests (from main server)
cd tests/
python integration_test.py
```

### Development with UV (Python Package Manager)

```bash
# Install dependencies
uv sync

# Add new dependency
uv add <package-name>

# Run Python with uv
uv run python script.py
```

## Configuration

### Node-RED Configuration (Main Entry Point)

All system configuration is in Node-RED at `http://localhost:1880`:

1. Find the `[Global Config (Load on Start)]` node (top-left of "Face Access Control" flow)
2. Double-click to edit these settings:
   - `hailo_host`: FaceEmbed API address (default: `192.168.10.179`)
   - `hailo_port`: FaceEmbed API port (default: `8000`)
   - `image_width`, `image_height`: Camera resolution (default: 480x480)

3. Device-to-collection mapping in `Prepare Vector Search` node:
   ```javascript
   const deviceCollectionMap = {
     'grove_vision_ai_v2_001': 'office_entrance',
     'grove_vision_ai_v2_002': 'warehouse_door',
     'default': 'default_collection'
   };
   ```

4. Similarity threshold adjustment (same node):
   ```javascript
   const threshold = 0.32;  // Lower = stricter, Higher = looser
   ```

### Environment Variables (FaceEmbed API)

```bash
# Debug mode - saves processing images to debug_images/
export DEBUG_SAVE_IMAGES=true
export DEBUG_SAVE_INTERVAL_S=5

# Model paths (optional, has defaults)
export FACE_RECOGNITION_HEF=/path/to/arcface_mobilefacenet.hef
export FACE_DETECTION_HEF=/path/to/scrfd_10g.hef

# Database path (optional)
export DB_FILE=data/vectors.db
```

## API Endpoints (FaceEmbed API)

### Primary Endpoint (Recommended)

**POST** `/detect_and_embed` - All-in-one detection and embedding
```json
{
  "image_base64": "base64_encoded_image",
  "confidence_threshold": 0.5
}
```

### Vector Database Endpoints

**POST** `/vectors/add` - Add face vector to collection
```json
{
  "collection": "office_entrance",
  "user_id": "user_001",
  "vector": [0.1, 0.2, ...]
}
```

**POST** `/vectors/search` - Search for similar vectors
```json
{
  "collection": "office_entrance",
  "vector": [0.11, 0.22, ...],
  "threshold": 0.32
}
```

**POST** `/vectors/delete` - Delete user vectors
```json
{
  "collection": "office_entrance",
  "user_id": "user_001"
}
```

## MQTT Topics

```
vision/frames/{device_id}        - Input: Base64 images from Grove devices
access/result/{device_id}        - Output: Recognition results
access/enroll/{device_id}        - Input: Face enrollment requests
```

## Development Workflow

### Adding New Features

Based on `.clinerules/sys_rule_dev.md`, follow these principles:

1. **Task Planning**: Create task list in `/docs/process/todo.md` and check off items as completed
2. **Code Exploration**: Familiarize yourself with existing code before making changes
3. **Modular Design**: Keep modules decoupled, generic, and well-tested
4. **Testing**: Write unit tests for each module and verify they pass before submitting PR
5. **Documentation**: Update README.md to help future developers quickly understand new features
6. **Git Workflow**: Use local git for version control, review as architect before submitting PR

### Tools and Technologies

- **Python Package Manager**: `uv` (NOT pip)
- **API Framework**: FastAPI + Uvicorn
- **AI Hardware**: Hailo-8 + HailoRT 4.21.0
- **Image Processing**: OpenCV + NumPy
- **Testing**: pytest
- **Orchestration**: Node-RED for business logic
- **Message Broker**: Mosquitto MQTT

## Hailo-8 Hardware Requirements

### Required Models (Place in `services/face_embed_api/models/`)

1. `scrfd_10g.hef` - Face detection model
2. `arcface_mobilefacenet.hef` - Face recognition model

Download from: https://github.com/hailo-ai/hailo_model_zoo

### Hardware Setup

- Raspberry Pi 5 + Hailo-8 AI Kit
- HailoRT 4.21.0 (system packages + Python wheel)
- PCIe drivers properly configured
- At least 4GB RAM

See `docs/HAILO_SETUP.md` for detailed installation instructions.

## Troubleshooting

### FaceEmbed API Not Responding

```bash
# Check network connectivity
ping 192.168.10.179

# Verify API is running
curl http://192.168.10.179:8000/health

# SSH to device and check logs
ssh harvest@192.168.10.179
cd ~/face_embed_api
# Check if process is running
ps aux | grep uvicorn
```

### Recognition Too Strict or Too Loose

Adjust the `threshold` value in Node-RED's `Prepare Vector Search` node:
- **Too strict** (rejecting known faces): Increase threshold (e.g., 0.32 → 0.38)
- **Too loose** (accepting unknown faces): Decrease threshold (e.g., 0.32 → 0.28)

### Debug Image Saving

Enable debug mode to save intermediate processing images:
```bash
export DEBUG_SAVE_IMAGES=true
export DEBUG_SAVE_INTERVAL_S=5
PYTHONPATH=src uv run uvicorn app:app --host 0.0.0.0 --port 8000
```

Images saved to `debug_images/`:
- `detected_*.jpg` - Original with bounding boxes
- `cropped_for_embedding_*.jpg` - Unaligned face crop
- `aligned_for_embedding_*.jpg` - Aligned face ready for embedding

## Important Notes

- **Never containerize FaceEmbed API** - Hailo-8 requires direct PCIe hardware access
- **Use `uv` not `pip`** - This project uses UV for Python dependency management
- **Configuration in Node-RED** - Don't create `.env` files, use Node-RED's Global Config node
- **Remote Hailo Device** - FaceEmbed API runs on separate hardware at 192.168.10.179, not on main server
- **Built-in Vector Database** - SQLite vector storage is integrated into FaceEmbed API, no external Qdrant needed
- **Test Before PR** - Ensure all tests pass (especially the 28 FaceEmbed API tests) before submitting changes

## Performance Metrics

- Single inference: 3-18ms (Hailo-8)
- End-to-end latency: <300ms (full pipeline)
- Concurrent devices: 20+ supported
- Vector dimension: 512-dim (L2-normalized)
- Test coverage: 100% (28/28 tests passed)
