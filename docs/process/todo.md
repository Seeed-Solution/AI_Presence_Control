# 任务清单

## Phase 1: FaceEmbed API 增强 (已完成)

- [x] **重构API为一体化服务**:
    - [x] 添加 `/detect_and_embed` API 端点，在一个请求中完成人脸检测、对齐和特征提取。
    - [x] 此变更旨在解决Hailo硬件一次只能加载一个模型的限制。
- [x] **保留手动嵌入流程**:
    - [x] 保留 `/embed` 和 `/batch_embed` 端点，用于支持外部提供边界框和关键点的手动模式。
- [x] **更新测试**:
    - [x] 为新的 `/detect_and_embed` 端点添加并更新了单元测试和集成测试。
    - [x] 确认所有 28 个测试用例均通过。

## Phase 2: Node-RED 流程修改 (已完成)

- [x] **集成一体化API**:
    - [x] 在 `Grove数据整合器` 之后，修改 `http request` 节点以调用新的 `/detect_and_embed` API。
    - [x] 更新 `处理视觉帧` 函数节点以解析 `/detect_and_embed` API 的响应（可能返回0个、1个或多个人脸）。
- [x] **简化数据流**:
    - [x] 在Node-RED流程中移除原先对 `/detect` 和 `/embed` 的链式调用逻辑。
    - [x] 确保后续流程能正确处理包含完整人脸信息（边界框、关键点、嵌入向量）的单个消息。

## Phase 3: 文档更新 (已完成)

- [x] **更新 `README.md` (根目录)**:
    - [x] 更新API文档，将 `/detect_and_embed` 作为主要推荐接口，并说明其使用方法和响应格式。
    - [x] 简要说明保留 `/embed` 和 `/batch_embed` 是用于高级或手动场景。
    - [x] 确保项目结构和架构图的文字说明与新的API模式保持一致。
- [x] **同步 `services/face_embed_api/` 目录下的文档**:
    - [x] 确保 `services/face_embed_api/README.md` 的内容准确无误。
    - [x] 检查 `services/face_embed_api/PROJECT_STRUCTURE.md` 内容保持同步。
- [x] **完成所有任务**:
    - [x] 当所有任务完成后，在此处标记。
