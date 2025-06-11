# 任务清单

## Phase 1: FaceEmbed API 增强

- [x] **添加人脸检测模型**:
    - [x] 将 `scrfd_10g.hef` 模型添加到 `services/face_embed_api/models/` 目录。
    - [x] 在 `FaceEmbedService` 中初始化人脸检测模型。
- [x] **实现人脸检测功能**:
    - [x] 添加 `/detect` API 端点。
    - [x] 实现图像预处理、模型推理和后处理逻辑。
- [x] **更新人脸嵌入流程**:
    - [x] 修改 `/embed` 端点以接受5点关键点作为输入。
    - [x] 实现基于关键点的人脸对齐。
- [x] **更新测试**:
    - [x] 为 `/detect` 端点添加单元测试。
    - [x] 为 `/detect` 端点添加集成测试。
    - [x] 更新现有测试以支持关键点。
