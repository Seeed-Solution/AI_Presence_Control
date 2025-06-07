# 文件结构更新说明

## 📁 Node-RED 流程文件移动 (2025-06-06)

### 变更说明
为了更好地组织项目结构，将 Node-RED 流程文件从根目录移动到对应的服务目录下。

### 文件移动
```bash
# 移动前
flows/face_access_control.json

# 移动后  
services/node_red/face_access_control.json
```

### 更新的文件

#### 1. `deployment/start_services.sh`
- **更新**: `start_nodered()` 函数中的流程文件复制逻辑
- **变更**: 优先从 `services/node_red/` 查找流程文件，向后兼容旧路径
- **新增**: 文件查找失败时的警告信息

#### 2. `docker-compose.yml`  
- **移除**: `./flows:/data/flows` 卷挂载
- **保留**: `./services/node_red/data:/data` 核心数据挂载
- **简化**: Node-RED 配置更加清晰

#### 3. `README.md`
- **更新**: 项目结构说明
- **变更**: 反映新的文件组织方式

#### 4. `doc/process/todo.md`
- **更新**: Node-RED 流程目录引用
- **变更**: `flows/` → `services/node_red/`

#### 5. `docs/deployment_guide.md`
- **更新**: 流程文件导入说明
- **更新**: 备份脚本中的路径引用

### 新的目录结构
```
services/node_red/
├── data/                           # Node-RED 运行时数据 (Docker 挂载)
└── face_access_control.json       # 人脸识别流程配置文件
```

### 部署影响
- ✅ **向后兼容**: 启动脚本会检查新旧两个位置
- ✅ **无需手动操作**: 启动脚本自动处理文件复制
- ✅ **Docker 配置简化**: 减少了一个卷挂载

### 优势
1. **结构清晰**: 每个服务的配置文件都在对应目录下
2. **便于维护**: Node-RED 相关文件统一管理
3. **减少混乱**: 避免根目录文件过多
4. **Docker 优化**: 简化容器配置

### 使用说明
```bash
# 启动服务时，脚本会自动复制流程文件
./deployment/start_services.sh --with-nodered

# 手动导入流程文件 (如果需要)
cp services/node_red/face_access_control.json services/node_red/data/

# 在 Node-RED 中导入
# 访问 http://localhost:1880
# 使用导入功能加载流程文件
```

### 注意事项
- 旧的 `flows/` 目录可以安全删除
- 如果有自定义的流程文件，请移动到新位置
- 启动脚本会处理路径兼容性，无需担心

---

**更新时间**: 2025-06-06  
**影响范围**: 部署配置和文档  
**兼容性**: 完全向后兼容 