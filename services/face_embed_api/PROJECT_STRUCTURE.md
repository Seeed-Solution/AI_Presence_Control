# FaceEmbed API Project Structure

## 📁 Directory Structure

```
face_embed_api/
├── 📂 src/                              # Source Code Directory
│   ├── __init__.py                      # Package Initializer
│   ├── app.py                           # FastAPI Application Main File
│   └── utils.py                         # Hailo Inference Utility Classes
│
├── 📂 tests/                            # Tests Directory
│   ├── __init__.py                      # Tests Package Initializer
│   ├── unit/                            # Unit Tests
│   │   ├── __init__.py
│   │   └── test_face_embed_api.py       # API Unit Tests
│   └── integration/                     # Integration Tests
│       ├── __init__.py
│       └── test_api_integration.py      # API Integration Tests
│
├── 📂 scripts/                          # Scripts Directory
│   ├── run_tests.py                     # Test Runner Script
│   ├── test_hailo_request.py            # Standalone API Request Test Script
│   └── verify_multi_model.py            # Script to verify Hailo multi-model concurrent execution
│
├── 📂 models/                           # AI Model Files
│   ├── arcface_mobilefacenet.hef        # Face Embedding Model
│   └── scrfd_10g.hef                    # Face Detection Model
│
├── 📂 docs/                             # Documentation Directory
│   ├── TEST_REPORT.md                   # Test Report
│   ├── run_instruction.md               # Running Instructions
│   └── reference/                       # Reference Documents
│       ├── hailo_python_guide.md        # Hailo Python API Guide
│       ├── detection_with_tracker.py    # Reference Code Example
│       └── utils.py                     # Reference Utility Classes
│
├── 📂 logs/                             # Logs Directory
│   └── hailort.log                      # Hailo Runtime Log
│
├── 📂 examples/                         # Examples Directory
│   └── (Example code to be added)
│
├── 📄 README.md                         # Project README
├── 📄 PROJECT_STRUCTURE.md              # Project Structure (This file)
├── 📄 pyproject.toml                     # Project Configuration
├── 📄 requirements.txt                   # Python Dependencies
├── 📄 uv.lock                           # UV Lock File
└── 📄 .python-version                   # Python Version
```

## 🚀 Quick Start

### 1. Start the Service
```bash
# Set PYTHONPATH and start with uvicorn
source .venv/bin/activate
PYTHONPATH=src uv run uvicorn app:app --host 0.0.0.0 --port 8000
```

### 2. Run Tests
```bash
# Run all tests
source .venv/bin/activate
uv run -- pytest -v
```

## 📋 File Descriptions

### Core Source Code
- **`src/app.py`**: The main FastAPI application, containing all API endpoints.
- **`src/utils.py`**: Hailo asynchronous inference utility classes.
- **`src/`**: The root of the core application source code.

### Test Files
- **`tests/unit/test_face_embed_api.py`**: Unit tests for individual functional modules.
- **`tests/integration/test_api_integration.py`**: Integration tests for the complete API flow.

### Script Utilities
- **`scripts/run_tests.py`**: Script to run all tests.
- **`scripts/test_hailo_request.py`**: Standalone script for testing API requests.
- **`scripts/verify_multi_model.py`**: Script to verify concurrent execution of multiple models on Hailo.

### Documentation
- **`docs/TEST_REPORT.md`**: Detailed test report.
- **`docs/reference/`**: Reference documents and code examples.

## 🔧 Development Workflow

### Adding New Features
1. Implement the feature in `src/`.
2. Add unit tests in `tests/unit/`.
3. Add integration tests in `tests/integration/`.
4. Run tests to ensure they pass.
5. Update documentation.

### Deployment Preparation
1. Run the full test suite: `uv run -- pytest -v`
2. Start the service: `PYTHONPATH=src uv run uvicorn app:app --host 0.0.0.0 --port 8000`

## 📊 Test Coverage

- **Unit Tests**: 19 tests
- **Integration Tests**: 9 tests
- **Total**: 28 tests
- **Pass Rate**: 100% (Verified)

## 🛠️ Tech Stack

- **API Framework**: FastAPI
- **AI Inference**: Hailo-8 + HailoAsyncInference
- **Testing Framework**: pytest + unittest
- **Dependency Management**: UV
- **Documentation**: Markdown

---

*Project structure optimized on July 27, 2024* 