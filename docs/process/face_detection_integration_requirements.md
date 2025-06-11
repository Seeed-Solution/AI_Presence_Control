# 人脸检测模型集成修改需求文档

## 需求背景

由于 ArcFace 模型需要脸部的 landmark（5个关键点）进行精确的人脸对齐，而现有的 Grove Vision AI V2 设备内部模型无法提供这些关键点信息，因此需要将人脸检测和 landmark 提取功能完全迁移到 `services/face_embed_api/` 服务中实现。

## 当前架构问题

1. **Grove Vision AI V2** 只能提供粗略的人脸边界框（BBox），格式为 `[中心点x, 中心点y, 宽, 高]`
2. **缺少 landmark 信息**：ArcFace 模型需要 5个关键点（左眼、右眼、鼻尖、左嘴角、右嘴角）进行人脸对齐
3. **精度不足**：设备内部的检测精度可能不够，影响最终识别效果
4. **分辨率不匹配**：scrfd_10g.hef 模型需要 640x640 输入，而 Grove 设备当前使用较低分辨率

## ✅ 技术确认

- **模型可用性**: `scrfd_10g.hef` 已确认可以正常运行
- **性能可接受**: 处理时间在可接受范围内
- **兼容性要求**: 需要与现有 Grove 设备兼容，仅读取图片数据
- **分辨率需求**: scrfd 模型需要 640x640 分辨率输入

## 目标架构

```
Grove Vision AI V2 → Node-RED → FaceEmbed API (人脸检测+Landmark+特征提取) → Qdrant
     ↓                   ↓              ↓
  640x640图片        分辨率调整      完整处理流程
```

### 分辨率处理策略

**Grove Vision AI V2 分辨率选项** (基于 [SSCMA AT协议](https://github.com/Seeed-Studio/SSCMA-Micro/blob/main/docs/protocol/at-protocol-en_US.md))：
- `OPT_ID=0`: "240x240 Auto"
- `OPT_ID=1`: "480x480 Auto" 
- `OPT_ID=2`: "640x480 Auto"

**解决方案**：
1. **设备端配置**: 使用 `AT+SENSOR=1,1,2` 设置为 640x480 分辨率
2. **Node-RED处理**: 新增图像调整节点，将 640x480 调整为 640x640
3. **填充策略**: 使用 letterbox 方式保持宽高比，上下填充黑边

## 修改方案

### 1. FaceEmbed API 服务增强

#### 1.1 添加人脸检测模型支持

**文件位置**: `services/face_embed_api/src/face_embed_api/`

**新增功能**:
- 加载 `scrfd_10g.hef` 人脸检测模型
- 实现人脸检测 API 接口
- 提取 5个关键点 landmark 信息
- 支持多人脸检测和筛选

**技术实现**:
```python
# 新增类和方法
class FaceDetectionService:
    - load_face_detection_model()  # 加载 scrfd_10g.hef
    - detect_faces()               # 人脸检测
    - extract_landmarks()          # 提取5点landmark
    - filter_best_face()          # 选择最佳人脸

# 修改现有类
class FaceEmbedService:
    - 集成人脸检测服务
    - 修改预处理流程
    - 支持端到端处理
```

#### 1.2 新增 API 接口

**新接口**:
1. `POST /detect_faces` - 纯人脸检测接口
   ```json
   Request: {"image_base64": "..."}
   Response: {
     "faces": [
       {
         "bbox": {"x": 100, "y": 100, "w": 200, "h": 200},
         "confidence": 0.98,
         "landmarks": [
           {"x": 120, "y": 130}, // 左眼
           {"x": 180, "y": 130}, // 右眼  
           {"x": 150, "y": 160}, // 鼻尖
           {"x": 130, "y": 200}, // 左嘴角
           {"x": 170, "y": 200}  // 右嘴角
         ]
       }
     ]
   }
   ```

2. `POST /embed_full` - 端到端处理接口
   ```json
   Request: {"image_base64": "..."}
   Response: {
     "vector": [...],
     "face_info": {
       "bbox": {...},
       "landmarks": [...],
       "confidence": 0.98
     },
     "processing_time_ms": 45
   }
   ```

#### 1.3 修改现有接口

**保持兼容性**的前提下，增强 `/embed` 接口：
- 如果只提供 `image_base64`，自动进行人脸检测
- 如果提供 `bbox` 和 `landmarks`，使用现有流程
- 优先使用检测到的最佳人脸

### 2. Node-RED 流程修改

#### 2.1 数据流调整

**当前流程**:
```
Grove Vision AI V2 → Grove数据整合器 → 处理视觉帧 → FaceEmbed API (/embed)
   ↓                      ↓                ↓              ↓
图片+检测框          组合数据        选择最大人脸      bbox裁剪+特征提取
```

**修改后流程**:
```
Grove Vision AI V2 → Grove数据简化器 → 处理视觉帧 → FaceEmbed API (/embed_full)
   ↓                      ↓                ↓              ↓
   原始图片            原始图片         原始图片      完整检测+特征提取
```

#### 2.2 Node-RED 节点修改

**修改节点**:

1. **Grove数据整合器** → **Grove数据简化器**
   - 只传递原始图片数据
   - 移除检测框处理逻辑
   - 简化消息格式

2. **处理视觉帧**
   - 移除人脸筛选逻辑
   - 直接转发原始图片
   - 调用新的 `/embed_full` 接口

3. **API URL 配置器**
   - 切换到 `/embed_full` 端点
   - 调整请求格式

**向后兼容**:
- 保留原有节点作为备用方案
- 新增开关控制使用哪种模式

### 3. 模型管理

#### 3.1 模型文件部署

**确认模型位置**:
- ✅ `services/face_embed_api/models/arcface_mobilefacenet.hef` (已存在)
- ✅ `services/face_embed_api/models/scrfd_10g.hef` (已存在)

#### 3.2 模型初始化策略

**加载顺序**:
1. 优先加载人脸检测模型 (scrfd_10g.hef)
2. 然后加载人脸识别模型 (arcface_mobilefacenet.hef)
3. 支持独立的健康检查

**资源管理**:
- 使用不同的推理线程
- 合理分配 Hailo 设备资源
- 实现模型切换机制

### 4. 性能优化

#### 4.1 处理流程优化

**智能检测策略**:
- 设置人脸检测置信度阈值 (默认 0.5)
- 人脸大小过滤 (最小像素要求)
- 多人脸情况下选择最佳人脸

**缓存机制**:
- 对于入库流程，缓存检测结果
- 避免重复检测同一帧

#### 4.2 错误处理

**降级策略**:
- 如果人脸检测失败，尝试使用传统方法
- 提供详细的错误信息
- 支持调试模式输出中间结果

## 修改清单

### Phase 1: FaceEmbed API 增强

- [ ] 1.1 添加 `FaceDetectionService` 类
- [ ] 1.2 集成 `scrfd_10g.hef` 模型加载
- [ ] 1.3 实现人脸检测和 landmark 提取
- [ ] 1.4 新增 `/detect_faces` API
- [ ] 1.5 新增 `/embed_full` API  
- [ ] 1.6 修改 `/embed` API 支持自动检测
- [ ] 1.7 更新 API 文档和类型定义

### Phase 2: Node-RED 流程调整

- [ ] 2.1 创建 `Grove数据简化器` 节点
- [ ] 2.2 修改 `处理视觉帧` 节点
- [ ] 2.3 更新 `API URL 配置器`
- [ ] 2.4 添加模式切换开关
- [ ] 2.5 更新流程文档

### Phase 3: 测试和验证

- [ ] 3.1 单元测试覆盖新功能
- [ ] 3.2 集成测试端到端流程
- [ ] 3.3 性能基准测试
- [ ] 3.4 与现有流程对比验证
- [ ] 3.5 文档更新

## 风险评估

### 技术风险

1. **模型兼容性**: scrfd_10g.hef 模型输出格式需要验证
2. **性能影响**: 增加检测步骤可能增加处理时间
3. **资源竞争**: 两个模型共享 Hailo 设备资源

### 缓解措施

1. **渐进式部署**: 保持现有接口兼容性，逐步切换
2. **A/B测试**: 支持新旧流程并行运行对比
3. **回滚方案**: 保留现有完整流程作为备用

## 预期收益

1. **精度提升**: 使用专业检测模型和精确 landmark 对齐
2. **架构统一**: 所有AI处理集中在一个服务中
3. **维护简化**: 减少设备端模型依赖
4. **扩展性增强**: 便于后续添加更多AI功能

## 时间规划

- **Phase 1**: 3-4天 (FaceEmbed API 增强)
- **Phase 2**: 2-3天 (Node-RED 流程调整)  
- **Phase 3**: 2-3天 (测试和验证)
- **总计**: 7-10天

## 下一步行动

1. **确认需求**: 与你确认修改方案的可行性
2. **技术验证**: 验证 scrfd_10g.hef 模型的输出格式
3. **开始开发**: 按照 Phase 划分逐步实施

---

**文档创建时间**: 2025-06-10  
**修改状态**: 草案，等待确认
