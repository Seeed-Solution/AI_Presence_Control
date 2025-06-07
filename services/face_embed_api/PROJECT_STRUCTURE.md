# FaceEmbed API 项目结构

## 📁 目录结构

```
face_embed_api/
├── 📂 src/                              # 源代码目录
│   └── face_embed_api/                  # 主要API包
│       ├── __init__.py                  # 包初始化
│       ├── app.py                       # FastAPI应用主文件
│       └── utils.py                     # Hailo推理工具类
│
├── 📂 tests/                            # 测试目录
│   ├── __init__.py                      # 测试包初始化
│   ├── unit/                            # 单元测试
│   │   ├── __init__.py
│   │   └── test_face_embed_api.py       # API单元测试
│   └── integration/                     # 集成测试
│       ├── __init__.py
│       └── test_api_integration.py      # API集成测试
│
├── 📂 scripts/                          # 脚本目录
│   ├── start_server.py                  # 服务器启动脚本
│   ├── test_hailo_request.py           # API测试脚本
│   └── run_tests.py                    # 测试运行脚本
│
├── 📂 models/                           # AI模型文件
│   ├── arcface_mobilefacenet.hef       # 人脸嵌入模型
│   └── scrfd_10g.hef                   # 人脸检测模型
│
├── 📂 docs/                             # 文档目录
│   ├── TEST_REPORT.md                   # 测试报告
│   ├── run_instruction.md               # 运行说明
│   └── reference/                       # 参考文档
│       ├── hailo_python_guide.md        # Hailo Python API指南
│       ├── detection_with_tracker.py    # 参考代码示例
│       └── utils.py                     # 参考工具类
│
├── 📂 logs/                             # 日志目录
│   └── hailort.log                      # Hailo运行日志
│
├── 📂 examples/                         # 示例代码目录
│   └── (待添加示例代码)
│
├── 📄 README.md                         # 项目说明
├── 📄 PROJECT_STRUCTURE.md              # 项目结构说明 (本文件)
├── 📄 pyproject.toml                    # 项目配置
├── 📄 requirements.txt                  # Python依赖
├── 📄 uv.lock                          # UV锁定文件
├── 📄 Dockerfile                       # Docker配置
├── 📄 .python-version                  # Python版本
└── 📄 main.py                          # 备用启动文件
```

## 🚀 快速开始

### 1. 启动服务
```bash
# 方法1: 使用启动脚本 (推荐)
source .venv/bin/activate
python scripts/start_server.py

# 方法2: 直接启动
source .venv/bin/activate
cd src && python -m face_embed_api.app
```

### 2. 运行测试
```bash
# 方法1: 使用测试脚本 (推荐)
source .venv/bin/activate
python scripts/run_tests.py

# 方法2: 直接运行pytest
source .venv/bin/activate
pytest tests/ -v
```

### 3. 测试API
```bash
# 使用测试脚本
source .venv/bin/activate
python scripts/test_hailo_request.py
```

## 📋 文件说明

### 核心源码
- **`src/face_embed_api/app.py`**: 主要的FastAPI应用，包含所有API端点
- **`src/face_embed_api/utils.py`**: Hailo异步推理工具类
- **`src/face_embed_api/__init__.py`**: 包导入配置

### 测试文件
- **`tests/unit/test_face_embed_api.py`**: 单元测试，测试各个功能模块
- **`tests/integration/test_api_integration.py`**: 集成测试，测试完整API流程

### 脚本工具
- **`scripts/start_server.py`**: 启动服务器的便捷脚本
- **`scripts/run_tests.py`**: 运行所有测试的脚本  
- **`scripts/test_hailo_request.py`**: API功能测试脚本

### 文档资料
- **`docs/TEST_REPORT.md`**: 详细的测试报告
- **`docs/reference/`**: 参考文档和示例代码

## 🔧 开发工作流

### 添加新功能
1. 在 `src/face_embed_api/` 中实现功能
2. 在 `tests/unit/` 中添加单元测试
3. 在 `tests/integration/` 中添加集成测试
4. 运行测试确保通过
5. 更新文档

### 部署准备
1. 运行完整测试套件: `python scripts/run_tests.py`
2. 检查API功能: `python scripts/test_hailo_request.py`
3. 启动服务: `python scripts/start_server.py`

## 📊 测试覆盖

- **单元测试**: 19个测试
- **集成测试**: 9个测试
- **总计**: 28个测试
- **通过率**: 100%

## 🛠️ 技术栈

- **API框架**: FastAPI
- **AI推理**: Hailo-8 + HailoAsyncInference
- **测试框架**: pytest + unittest
- **依赖管理**: UV
- **文档**: Markdown

---

*项目结构优化完成于 2024年6月6日* 