# Home Assistant 倒计时授权控制示例

本项目演示了如何将外部的身份验证事件（如本仓库中的人脸识别）接入Home Assistant，实现一个"**刷脸开机，倒计时关机**"的自动化应用场景。

它完全基于Home Assistant的原生组件和一个可选的社区UI插件实现，无需编写任何自定义Python代码，做到了轻量、高效和易于集成。

## ✨ 核心功能

- **MQTT触发**：监听指定的MQTT主题，当收到合规的成功验证消息后，自动启动或重置倒计时。
- **定时控制**：控制一个指定的设备实体（如`switch`或`light`），在计时开始时确保其开启，在计时结束后自动将其关闭。
- **动态倒计时**：默认授权15分钟使用时长，该时长可在创建自动化时自由配置。
- **实时UI展示**：在Lovelace仪表盘上通过进度条实时显示剩余授权时间。
- **管理员控制**：为管理员提供专属UI按钮，可以手动为设备**增加时长**、**暂停**或**终止**计时。

---

## 📁 文件说明

- `blueprints/automation/countdown_control.yaml`：**核心自动化蓝图**。它包含了所有的触发和控制逻辑。
- `dashboards/countdown_example.yaml`：**Lovelace仪表盘视图示例**。它展示了如何配置一个美观且功能完整的监控面板。
- `scripts/timer_controls.yaml`：**UI控制脚本示例**。为管理员提供"+"5分钟"功能的后台逻辑。

---

## 🚀 部署指南

### ✅ 前提条件

1.  **一个正在运行的Home Assistant实例**。
2.  **MQTT Broker已配置**：Home Assistant需要已集成并连接到一个MQTT服务器（如Mosquitto）。
3.  **(可选) Timer Bar Card**：为了获得最佳的UI效果，建议通过HACS（Home Assistant Community Store）安装`timer-bar-card`。如果不想安装，您也可以使用HA原生的`entity`卡片来显示计时器状态。

### 📝 部署步骤

#### 第1步：复制蓝图文件

将`blueprints/automation/countdown_control.yaml`文件复制到您Home Assistant配置目录下的`/blueprints/automation/`文件夹中。

例如，如果使用Samba访问，路径通常是 `\\<HA_IP_ADDRESS>\config\blueprints\automation`。

复制完成后，需要**重启Home Assistant**或在开发者工具中**重载自动化**来让HA识别到新的蓝图。

#### 第2步：创建Timer助手

这是倒计时的核心。
1.  前往 **设置** -> **设备与服务** -> **辅助元素**。
2.  点击 **创建辅助元素**，然后选择 **计时器 (Timer)**。
3.  **命名**：给它一个清晰的名字，例如 `人脸识别授权计时器`。其实体ID将自动生成（例如 `timer.face_auth_timer`），请记下这个**实体ID**。
4.  其他选项（图标、恢复）可留空，直接点击 **创建**。

#### 第3步：基于蓝图创建自动化

1.  前往 **设置** -> **自动化与场景** -> **蓝图**。
2.  找到名为 `Robust Countdown Control (MQTT triggered)` 的蓝图，点击 **创建自动化**。
3.  **配置自动化**:
    - **MQTT Topic**：填写您的人脸识别系统发布成功消息的主题（默认为 `access/verify`）。
    - **Target Device**：点击`选择实体`，选择您想要控制的设备，例如一个 `switch.smart_plug`。
    - **Timer Helper**：点击`选择实体`，选择您在第2步中创建的那个**计时器助手**。
    - **Duration (minutes)**：根据需要设置授权时长，默认为15分钟。
4.  点击 **保存**。

#### 第4步：添加脚本配置

此项目包含一个用于"+"5分钟"功能的脚本。请将 `scripts/timer_controls.yaml` 文件中的内容添加到您 Home Assistant 的脚本配置中。这通常意味着将其内容复制粘贴到您的 `scripts.yaml` 文件里。

**重要**：添加后，请务必将脚本中所有的 `timer.your_timer_entity_id` 替换为您在第2步中创建的计时器的**真实实体ID**。

配置完成后，请在开发者工具中**重载脚本**或重启 Home Assistant。

#### 第5步：添加Lovelace仪表盘视图

1.  打开您想要添加监控卡片的仪表盘。
2.  点击右上角的 **三个点** -> **编辑仪表盘**。
3.  点击右下角的 **"+"** 按钮添加一个新视图，或在现有视图中点击 **"添加卡片"**。
4.  如果您想快速搭建，可以进入 **原始配置编辑器**，将`dashboards/countdown_example.yaml`中的内容复制进去。
5.  **重要**：在卡片配置中，您需要修改以下占位符：
    - 将所有 `timer.your_timer_entity_id` 替换为您在第2步中创建的计时器的**真实实体ID**。
    - 将 `YOUR_USER_ID_HERE` 替换为您自己的管理员用户ID，以确保控制按钮对您可见。

#### 第6步：测试

现在，通过MQTT向您配置的主题发布一条消息，例如：
- Topic: `access/verify`
- Payload: `{"result": true, "user": "test"}`

您应该能在HA的仪表盘上看到倒计时开始，并且您选择控制的设备会自动开启。等待倒计时结束后，设备会自动关闭。

---

## 🔧 故障排查

- **蓝图未显示**：请确认文件已放置在正确的`config/blueprints/automation`目录下，并已重启HA或重载自动化。
- **自动化不触发**：请使用MQTT Explorer等工具检查MQTT消息的主题和Payload格式是否与蓝图配置完全一致。特别是`"result": true`部分。
- **UI卡片显示错误**：请确认`timer-bar-card`已通过HACS正确安装，或者将卡片类型改回原生卡片。同时，检查卡片配置中引用的实体ID是否正确无误。 