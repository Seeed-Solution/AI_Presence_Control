# FaceEmbed API 更新日志

## 版本 2.0.0 (2024-06-06) - 硬件专用版本

### 🚨 重大变更 (Breaking Changes)

本次更新移除了Docker和Mock模式支持，现在**必须**安装Hailo-8硬件才能运行服务。

### 📋 变更概述

#### 🗑️ 已删除的功能
- **Docker支持**: 完全移除Docker部署选项
- **Mock模式**: 移除所有软件模拟推理功能
- **智能降级**: 移除硬件不可用时的fallback机制

#### ✨ 新特性
- **硬件专用**: 专门为Hailo-8 AI加速器优化
- **严格验证**: 启动时强制检查Hailo环境
- **清晰错误**: 缺少依赖时提供详细安装指引

### 📂 文件变更详情

#### 🏗️ 项目结构变动

**删除的文件:**
```
face_embed_api/
├── Dockerfile                   # ❌ 已删除 - Docker容器配置
└── .dockerignore               # ❌ 已删除 - Docker忽略文件
```

**保持的核心结构:**
```
face_embed_api/
├── src/
│   └── face_embed_api/
│       ├── app.py              # 🔧 重构 - 移除Mock支持
│       ├── utils.py            # 🔧 重构 - 简化为Hailo专用
│       └── __init__.py         # ✅ 保持不变
├── tests/
│   ├── unit/
│   │   └── test_face_embed_api.py    # 🔧 更新 - 添加Mock测试
│   └── integration/
│       └── test_api_integration.py   # 🔧 更新 - 集成测试优化
├── docs/
│   ├── reference/              # ✅ 保持不变
│   └── HAILO_SETUP.md         # 🔧 更新 - 强调必需依赖
├── models/                     # ✅ 保持不变 - HEF模型文件
├── scripts/                    # ✅ 保持不变 - 启动脚本
├── logs/                       # ✅ 保持不变 - 日志目录
├── README.md                   # 🔧 重大更新 - 移除Docker说明
├── pyproject.toml             # 🔧 更新 - 强调必需依赖
├── requirements.txt           # ✅ 保持不变
└── CHANGELOG.md               # ✨ 新增 - 本更新日志
```

**代码行数变化:**
- `src/face_embed_api/utils.py`: ~400行 → ~300行 (-25% 代码量)
- `src/face_embed_api/app.py`: ~450行 → ~350行 (-22% 代码量)
- 总体代码简化: 移除约150行Mock相关代码

#### 🗑️ 已删除的文件
```
- Dockerfile                    # Docker容器配置
- .dockerignore                # Docker忽略文件
```

#### 🔧 已修改的核心文件

##### `src/face_embed_api/utils.py`
- ❌ 移除所有Mock类 (`MockHEF`, `MockVDevice` 等)
- ❌ 移除 `HAILO_PLATFORM_AVAILABLE` 检查
- ✅ 直接导入 `hailo_platform`，失败时抛出详细错误
- 🔧 修复 `run()` 方法中的变量作用域问题
- 🔧 改进错误处理和异常信息

##### `src/face_embed_api/app.py`
- ❌ 移除 `HAILO_AVAILABLE` 检查和fallback逻辑
- ❌ 移除 `_extract_embedding_mock()` 方法
- ✅ 改为延迟初始化服务，避免导入时初始化硬件
- 🔧 修复相对导入路径 (`from .utils import HailoAsyncInference`)
- 🔧 添加类型转换确保模型尺寸为整数
- 🔧 改进错误处理，硬件初始化失败时抛出 `RuntimeError`

##### `tests/unit/test_face_embed_api.py`
- ✅ 添加Mock支持，避免测试时初始化真实硬件
- 🔧 使用 `@patch` 装饰器Mock Hailo组件
- ❌ 移除 `test_extract_embedding_mock()` 相关测试
- 🔧 保持26个测试全部通过

##### `tests/integration/test_api_integration.py`
- ✅ 添加Mock支持用于集成测试
- 🔧 调整性能预期（Mock模式下的合理值）
- 🔧 修改一致性测试逻辑

#### 📝 已更新的文档

##### `README.md`
```diff
- 🛡️ **智能降级**: 硬件不可用时自动切换到Mock模式
+ ❗ **必需依赖**: 必须安装Hailo-8硬件支持

- #### Hailo-8 硬件配置 (可选)
+ ### 2. Hailo-8 硬件配置 (必需)

- > 💡 **注意**: 如果没有Hailo硬件，API会自动切换到Mock模式
+ **必需组件**:
+ - Raspberry Pi 5 + Hailo-8 AI Kit  
+ - HailoRT 4.21.0 (系统包 + Python包)
+ - PCIe驱动和配置
+ - 人脸识别模型文件

- ### 生产环境
- # Docker部署
- docker build -t face-embed-api .
- docker run -p 8000:8000 face-embed-api
+ ## 🚨 依赖要求
+ ### 必需安装
+ - **HailoRT 4.21.0**: 核心推理引擎
+ - **Hailo-8 AI Kit**: 硬件加速器
```

##### `pyproject.toml`
```diff
- # NOTE: The service will automatically fall back to mock mode if HailoRT is not available
+ # NOTE: Service will NOT start without proper HailoRT installation

+ # 4. Model Requirements:
+ #    - Place HEF model file at: /home/harvest/face_embed_api/models/arcface_mobilefacenet.hef
+ #    - Or set FACE_RECOGNITION_HEF environment variable to model path
```

##### `docs/HAILO_SETUP.md`
```diff
- # Hailo-8 安装配置指南
+ # Hailo-8 必需依赖安装指南

+ **重要提示**: FaceEmbed API 服务需要Hailo-8硬件支持，没有Hailo环境将无法启动。

- 如果看到较高的处理时间（>50ms），可能在使用Mock模式。
+ **注意**: 如果服务无法启动或显示导入错误，说明HailoRT安装不完整。
```

### 🔄 迁移指南

#### 从 v1.x 升级到 v2.0

1. **检查硬件环境**
   ```bash
   # 验证Hailo设备是否可用
   python -c "
   try:
       import hailo_platform as hp
       devices = hp.Device.scan()
       print(f'Found {len(devices)} Hailo device(s): {devices}')
   except Exception as e:
       print(f'Error: {e}')
   "
   ```

2. **安装Hailo依赖** (如果尚未安装)
   - 按照 `docs/HAILO_SETUP.md` 完整指南操作
   - 下载并安装HailoRT 4.21.0
   - 配置PCIe驱动和设置

3. **移除Docker相关文件** (如果有本地修改)
   ```bash
   rm -f Dockerfile .dockerignore
   ```

4. **更新启动方式**
   ```bash
   # 旧方式 (已废弃)
   docker run -p 8000:8000 face-embed-api
   
   # 新方式
   python scripts/start_server.py
   ```

### 🧪 测试状态

- ✅ **单元测试**: 26个测试全部通过
- ✅ **集成测试**: 9个测试全部通过  
- ✅ **API功能**: 所有端点正常工作
- ✅ **错误处理**: 依赖缺失时提供清晰错误信息

### 💡 技术改进

1. **性能优化**
   - 移除Mock模式判断开销
   - 专注于Hailo硬件优化
   - 减少代码分支和复杂度

2. **代码质量**
   - 更清晰的错误处理
   - 移除死代码和未使用功能
   - 改进类型安全

3. **维护性**
   - 简化部署流程
   - 减少配置选项
   - 专注于单一用例

### 🚨 注意事项

- **硬件要求**: 现在必须有Hailo-8硬件才能运行
- **无fallback**: 没有软件模拟选项
- **测试环境**: 开发时需要Mock来避免硬件依赖
- **部署简化**: 不再需要考虑Docker环境

### 📞 支持

如果在迁移过程中遇到问题：

1. 检查 [Hailo安装指南](docs/HAILO_SETUP.md)
2. 验证硬件连接和驱动安装
3. 确认模型文件路径正确
4. 查看错误日志获取详细信息

---

**FaceEmbed API v2.0** - 专为Hailo-8硬件加速器优化的人脸特征提取服务 🚀 