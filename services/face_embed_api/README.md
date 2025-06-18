# FaceEmbed API

A high-performance face feature extraction service based on the Hailo-8 AI accelerator, providing a 512-dimension face embedding vector generation API.

## ✨ Features

- 🚀 **High-Performance Inference**: 3-18ms latency based on Hailo-8 hardware acceleration.
- 🎯 **Standardized Output**: 512-dimension, L2-normalized face embedding vectors.
- 🔄 **Asynchronous Processing**: Supports both single and batch image processing.
- ✨ **All-in-One Detection & Embedding**: A single endpoint for face detection, alignment, and feature extraction.
- 📊 **Comprehensive Tests**: 28 test cases with 100% pass rate.
- 🌐 **Cross-Origin Support**: Enables access from clients like Node-RED on different machines.

## 🏗️ Project Structure

```
face_embed_api/
├── 📂 src/                         # Core source code
│   ├── app.py                      # FastAPI application
│   └── utils.py                    # Hailo inference utilities
│   └── __init__.py                 # Package initializer
├── 📂 tests/                       # Test suite
│   ├── unit/                       # Unit tests
│   └── integration/                # Integration tests
├── 📂 scripts/                     # Utility scripts
│   ├── start_server.py             # Start the server
│   ├── run_tests.py                # Run tests
│   └── test_hailo_request.py       # API test script
├── 📂 models/                      # AI model files
├── 📂 docs/                        # Documentation
└── 📂 logs/                        # Runtime logs
```

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Activate the virtual environment
source .venv/bin/activate

# Install base dependencies
uv sync
```

### 2. Hailo-8 Hardware Configuration (Required)

**Important**: This service requires Hailo-8 hardware. Please follow these steps for configuration:

1.  **Download HailoRT**: Visit the [Hailo Developer Zone](https://hailo.ai/developer-zone/software-downloads/) to download the necessary files.
2.  **System Configuration**: Refer to the [Hailo Setup Guide](docs/HAILO_SETUP.md) for detailed instructions.
3.  **Verify Installation**: Use test scripts to ensure the hardware is working correctly.

**Required Components**:
- Raspberry Pi 5 + Hailo-8 AI Kit
- HailoRT 4.21.0 (System packages + Python package)
- PCIe drivers and configuration
- Face recognition model file (arcface_mobilefacenet.hef)
- Face detection model file (scrfd_10g.hef)

### 3. Start the Service

```bash
# Set PYTHONPATH and start with uvicorn (recommended)
PYTHONPATH=src uv run uvicorn app:app --host 0.0.0.0 --port 8000
```

### 4. Verify the Service

```bash
# Health check
curl http://localhost:8000/health

# API test
# (Please refer to the API examples below for testing)
```

## 📋 API Endpoints

### Health Check
```http
GET /health
```
**Response**:
```json
{
  "status": "ok",
  "uptime_ms": 12345,
  "current_model": "path/to/model.hef"
}
```

### All-in-One Detection and Embedding
This endpoint performs both face detection and feature extraction in a single request. It is the **recommended** primary endpoint.

```http
POST /detect_and_embed
Content-Type: application/json

{
  "image_base64": "base64_encoded_image",
  "confidence_threshold": 0.5
}
```
**Response**:
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

### Single Face Embedding (Manual Mode)
This endpoint requires you to provide the bounding box (bbox) and landmarks for the face.

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

### Batch Face Embedding (Manual Mode)
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

## 🧪 Testing

### Run All Tests
```bash
uv run -- pytest -v
```

### Run Tests Individually
```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v
```

## 🐛 Debugging

This service includes a built-in image debugging feature that saves key images from the processing pipeline to the local disk, making it easier to analyze and troubleshoot issues.

### How to Enable

Enable debugging mode by setting the following environment variables:

```bash
export DEBUG_SAVE_IMAGES=true
export DEBUG_SAVE_INTERVAL_S=5 # Save one image at most every 5 seconds to prevent disk flooding

# Then start the service
PYTHONPATH=src uv run uvicorn app:app --host 0.0.0.0 --port 8000
```

### Debug Environment Variables

- **`DEBUG_SAVE_IMAGES`**: Set to `true`, `1`, or `t` to enable image saving.
- **`DEBUG_SAVE_INTERVAL_S`**: Controls the minimum time interval (in seconds) between saving images. Default is `10`. This helps prevent generating excessive files when processing video streams or large batches of requests.

### Saved Image Types

When enabled, the following types of images will be saved to the `debug_images/` folder in the project root:

- **`detected_*.jpg`**: The original image with face detection boxes and landmarks drawn on it.
- **`cropped_for_embedding_*.jpg`**: The **unaligned** face image cropped from the original, pre-processed for the embedding model.
- **`aligned_for_embedding_*.jpg`**: The face image after being aligned using landmarks, ready for the embedding model.

Filenames include timestamps and confidence scores for easy tracking.

## 🔧 Development

### Adding New Features
1. Implement the feature in `src/`.
2. Add unit tests in `tests/unit/`.
3. Add integration tests in `tests/integration/`.
4. Run tests to ensure they pass.

### Code Structure
- **app.py**: FastAPI application and route definitions.
- **utils.py**: Hailo asynchronous inference engine.
- **tests/**: Complete test coverage.

## 🛠️ Tech Stack

- **API Framework**: FastAPI + Uvicorn
- **AI Inference**: Hailo-8 + HailoAsyncInference
- **Image Processing**: OpenCV + NumPy
- **Testing Framework**: pytest + unittest
- **Dependency Management**: UV

## 📊 Performance Metrics

- **Inference Latency**: 3-18ms (Hailo hardware)
- **Vector Dimension**: 512-dim standard ArcFace
- **Normalization**: L2 normalization (norm=1.0)
- **Concurrency Support**: Asynchronous multithreading
- **Test Coverage**: 28 tests, 100% pass rate

## 🔍 API Examples

### Python Client
```python
import requests
import base64
import cv2

# Prepare image
image = cv2.imread('face.jpg')
_, buffer = cv2.imencode('.jpg', image)
image_base64 = base64.b64encode(buffer).decode('utf-8')

# Send request to the detect_and_embed endpoint
response = requests.post('http://localhost:8000/detect_and_embed', json={
    'image_base64': image_base64,
    'confidence_threshold': 0.5
})

# Get results
results = response.json()
if results:
    first_face = results[0]
    vector = first_face['embedding']['vector']  # 512-dim embedding vector
    confidence = first_face['embedding']['confidence'] # Embedding quality confidence
    detection_confidence = first_face['detection_confidence'] # Detection confidence
    print(f"Found {len(results)} faces. First face vector: {vector[:5]}...")
```

### Node-RED Integration
```javascript
// In a Node-RED Function node
const payload = {
    image_base64: msg.payload.image,
    confidence_threshold: 0.5 // Optional
};

msg.url = "http://raspberry-pi:8000/detect_and_embed";
msg.method = "POST";
msg.headers = {"Content-Type": "application/json"};
msg.payload = payload;

return msg;
```

## 📈 Deployment

### Production Environment
```bash
# Start the service
PYTHONPATH=src uv run uvicorn app:app --host 0.0.0.0 --port 8000
```

### Environment Variables
- `HOST`: Service listening address (default: 0.0.0.0)
- `PORT`: Service port (default: 8000)
- `FACE_RECOGNITION_HEF`: Path to the face recognition model file
- `FACE_DETECTION_HEF`: Path to the face detection model file
- `DEBUG_SAVE_IMAGES`: Enable debug image saving (`true` / `false`)
- `DEBUG_SAVE_INTERVAL_S`: Interval for saving debug images in seconds (default: 10)

## 🚨 Dependencies

### Required Installations
- **HailoRT 4.21.0**: Core inference engine
- **Hailo-8 AI Kit**: Hardware accelerator
- **Raspberry Pi 5**: Host board with PCIe support
- **Face Recognition Model**: arcface_mobilefacenet.hef
- **Face Detection Model**: scrfd_10g.hef

### System Requirements
- **OS**: Linux (Raspberry Pi OS or Ubuntu)
- **Python**: 3.11+
- **Memory**: 4GB+ recommended
- **Storage**: 8GB+ available space

## 📚 Documentation

- [Project Structure Details](PROJECT_STRUCTURE.md)
- [Hailo Installation Guide](docs/HAILO_SETUP.md)
- [Hailo API Guide](docs/reference/hailo_python_guide.md)

## 🤝 Contributing

1. Fork the project
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 License

MIT License

---

**FaceEmbed API** - High-performance face feature extraction service powered by Hailo-8 🚀
