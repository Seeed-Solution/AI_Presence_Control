# Home Assistant Countdown Control System — Product Requirements Document (PRD)

## 1. 项目背景

基于现有的人脸识别权限控制系统（参见 README.md）已完成的身份验证能力，我们希望在 Home Assistant (HA) 平台上提供一个示例方案，实现**计时授权 + 设备控制**模式：

- 每次身份验证成功后，授予 15 分钟的使用时长（可在配置中修改）。
- 计时器实时倒计，倒计时归零即关闭目标设备（如智能插座、继电器、灯、门锁等）。
- HA Lovelace 面板实时显示剩余时间，并允许手动重置/暂停/调节时长（权限受限）。

该示例旨在：

1. 向开发者展示如何将自有身份验证事件流 (MQTT) 接入 HA。
2. 提供一个可复用的 YAML Blueprint / 自定义集成，快速落地到不同硬件场景。
3. 为后续商业化部署（健身房、共享工位、实验室仪器、充电桩等）奠定基础。

---

## 2. 目标与衡量

| 目标        | 关键指标                         | 通过标准      |
| --------- | ---------------------------- | --------- |
| 身份验证后自动授权 | 首次验证→计时开始延迟 < 1 s            | ✅ ≤ 1 s   |
| 面板实时性     | Lovelace 卡片刷新周期 ≤ 1 s        | ✅ 1 Hz 刷新 |
| 可靠关停      | 倒计时=0 后 500 ms 内执行关停命令       | ✅         |
| 易部署       | Blueprint 一键导入 + 启用成功率 100 % | ✅         |
| 安全        | 非授权用户无法手动延长计时                | ✅ 通过权限测试  |

---

## 3. 关键用户故事 (User Stories)

1. **作为设备管理员**，我希望在 HA 中看到剩余授权时长，以便了解设备何时会被关闭。
2. **作为验证通过的用户**，我希望每次刷脸成功后获得 15 分钟的设备使用权，无需手动点击按钮。
3. **作为系统维护者**，我希望在倒计时结束后设备能够可靠地被关闭，以确保安全和节能。
4. **作为家长/教师**，我希望可以在面板上手动暂停计时或提前终止，以便管理孩子/学生使用时长。

---

## 4. 功能需求

### 4.1 身份验证事件接入

- **MQTT Topic**: `access/verify`，Payload 示例：
  ```json
  {"device_id": "door1", "user_id": "u123", "result": true, "timestamp": 1717923000 }
  ```
- 仅当 `result=true` 时触发重置计时。
- HA 通过 `mqtt` 集成将该 Topic 映射为 `binary_sensor.face_auth_door1`.

### 4.2 计时逻辑

- 使用 HA **timer** 或 **input_number + automation** 实现 1 s 级倒计。
- 默认时长 15 min，可在 Blueprint 参数化配置（5–120 分钟）。
- 身份验证成功时：
  1. 如果倒计时不存在 → 创建并启动；
  2. 如果倒计时正在运行 → 重置为满时长。
- 支持 **pause / cancel** 服务供管理员调用。

### 4.3 设备控制

- 目标设备以 `switch.*` 或 `light.*` 等实体表示；Blueprint 参数指定。
- **Automation**：倒计时完成 (timer.finished) 时立即执行 `homeassistant.turn_off`.
- 可选：在倒计时低于阈值 (e.g. 2 min) 时发出 TTS/通知。

### 4.4 Lovelace 面板

- 提供一张自定义卡片（示例用 `custom:mushroom-timer-card` 或 `custom:timer-bar-card`）：
  - 显示剩余时间、大型进度条。
  - 显示最近一次验证用户（`sensor.last_user_id`）。
  - 管理员专属按钮：**暂停** / **终止** / **手动加时 5 min**。
- Dashboard YAML 片段附后。

### 4.5 权限与安全

- 通过 HA **用户角色**：仅管理员可操作计时器服务。
- 身份验证事件必须来自受信任 MQTT broker，使用 TLS + 用户名/密码。
- 记录所有加时/终止操作到 HA 日志.

### 4.6 可配置项

| 项目       | 默认值             | 说明                      |
| -------- | --------------- | ----------------------- |
| 授权时长     | 15 min          | Blueprint 参数 `duration` |
| 验证 Topic | `access/verify` | 参数 `mqtt_topic`         |
| 目标设备实体   | N/A             | 参数 `target_entity`      |
| 低电量阈值    | 2 min           | 参数 `warn_threshold`     |
| 通知方式     | HA 通知           | 参数 `notify_service`     |

---

## 5. 系统架构 & 数据流

```
 ┌────────────┐     MQTT     ┌────────────┐   native  ┌────────────┐
 │ Grove/Edge │─────────────▶│  HA MQTT   │──────────▶│   Timer    │
 │  Devices   │  auth event ││  Broker    │ event bus │  Entity    │
 └────────────┘              └────────────┘           └────────────┘
                                        ▲                      │
                                        │ automation           │timer.finished
                                        │ reset                ▼
                                   ┌────────────┐       ┌────────────┐
                                   │ Lovelace UI│◀──────│ switch.*   │
                                   └────────────┘  turn_off └────────────┘
```

---

## 6. 关键技术方案

1. **Blueprint** (`blueprints/automation/countdown_control.yaml`)
   - 定义输入：MQTT topic, duration, target entity, warn threshold, notify service.
   - 创建/管理 **timer** 实体。
   - 监听 `mqtt_event` + `timer.finished`.
2. **自定义传感器** (template / MQTT)
   - `sensor.remaining_time_<device_id>` 显示当前剩余秒数。
   - `sensor.last_user_<device_id>` 保存最近一次成功验证的 `user_id`.
3. **Lovelace Card**
   - 示例 YAML 使用 `stack-in-card` + `timer-bar-card`.

---

## 7. 验收标准

1. 按关键指标全部通过。
2. 全流程离线演示：模拟连续刷脸 → 面板实时更新 → 倒计 0 → 设备关闭。
3. Blueprint 导入向导无报错，普通用户可按 README 步骤 15 min 内完成部署。

---

## 8. 附录

### 8.1 Blueprint 片段 (概要)

```yaml
blueprint:
  name: Countdown Control Blueprint
  domain: automation
  input:
    mqtt_topic:
      name: MQTT Topic
      default: "access/verify"
    duration:
      name: Duration (minutes)
      default: 15
    target_entity:
      name: Target Entity
      selector:
        entity:
          domain:
            - switch
            - light
```

### 8.2 Lovelace 卡片示例

```yaml
type: custom:timer-bar-card
entity: timer.device1
name: 设备剩余时间
show_controls: false
```
