# Home Assistant Countdown Control Demo — Lightweight Tech Guide

> **版本 1.0  (2025-06-09)**  
> 本指南演示如何 **仅凭 Home Assistant 原生组件 + 社区 Lovelace 卡片** 实现“刷脸验证 → 15 分钟倒计时 → 到期关闭设备”的完整闭环。无需任何自定义 Python 组件，也不包含 Docker／Compose 步骤，便于直接集成到已部署的 HA 环境。

---

## 1 目标回顾
- 每次收到 **MQTT 验证成功事件**，即刻把倒计时重置为满 15 分钟（可配置）。  
- 在 HA Lovelace 面板实时展示剩余时长。  
- 倒计时为 0 时，自动关闭指定设备 (`switch.*`、`light.*` 等)。  
- 管理员可在 UI 上 **加时 / 暂停 / 终止** 计时器；普通用户看不到这些按钮。

---

## 2 所需原生组件 / 插件
| 作用 | 选用实体或插件 | 备注 |
|------|---------------|------|
| 接收刷脸事件 | **MQTT 集成** → `mqtt` 触发器 | 已在系统里启用的 Mosquitto 或其他 Broker |
| 倒计时计时器 | **`timer` 实体** (Settings ➜ Automations & Scenes ➜ Helpers ➜ Timer) | 1 s 精度足够 |
| 自动化执行 | **YAML Automation / Blueprint** | 本示例提供 Blueprint 1 个 |
| UI 倒计显示 | 核心 **Entities 卡片** 或社区 **`timer-bar-card`** | 后者更美观（HACS 可安装） |
| 管理员按钮 | **Conditional 卡片** + Button 卡片 | 条件基于 `user:` |

> *除 `timer-bar-card` 外，其余均为官方功能。若不使用社区卡片，可改用 `entities` 或 `mushroom`。*

---

## 3 系统流程图
```
MQTT  Topic  access/verify   (result=true)
          │
          ▼
Automation Trigger (MQTT)
          │  action 1            ┌────────────┐
          ├──────── timer.start ─▶ timer.face │
          │                       └────────────┘
          │  action 2 (可选)
          └──────── switch.turn_on (预先打开设备)
                                  │
                   timer.finished │ event
                                  ▼
                       Automation ➜ switch.turn_off
```

---

## 4 文件结构（示例仓库）
```
repo/
├── blueprints/
│   └── automation/
│        └── countdown_control.yaml   # 本示例 Blueprint
├── dashboards/
│   └── countdown_example.yaml        # Lovelace 视图示例
└── README.md                         # 步骤说明（见第 8 节）
```

---

## 5 Blueprint 详解  (`blueprints/automation/countdown_control.yaml`)
```yaml
blueprint:
  name: Countdown Control (MQTT + Timer)
  domain: automation
  description: >
    接收 MQTT 刷脸成功事件，重置计时器并在到期后自动关闭指定设备。
  input:
    mqtt_topic:
      name: MQTT Topic
      default: access/verify
    duration:
      name: Duration (minutes)
      default: 15
    target_entity:
      name: Entity to turn off when timer finishes
      selector:
        entity:
          domain: [switch, light]

mode: restart  # 可重复触发
variables:
  dur_sec: "{{ (duration | int) * 60 }}"

trigger:
  - platform: mqtt
    topic: !input mqtt_topic
    value_template: "{{ value_json.result }}"

action:
  - service: timer.start
    data:
      entity_id: "timer.face_auth"
      duration: "{{ dur_sec }}"

  - condition: state
    entity_id: !input target_entity
    state: "off"
  - service: homeassistant.turn_on
    target:
      entity_id: !input target_entity

  - wait_for_trigger:
      - platform: event
        event_type: timer.finished
        event_data:
          entity_id: timer.face_auth
    continue_on_timeout: false
  - service: homeassistant.turn_off
    target:
      entity_id: !input target_entity
```

---

## 6 Lovelace 视图示例 (`dashboards/countdown_example.yaml`)
```yaml
views:
  - title: Countdown Demo
    path: countdown-demo
    cards:
      - type: vertical-stack
        cards:
          - type: custom:timer-bar-card
            entity: timer.face_auth
            name: 剩余时间
            invert: true

          - type: conditional
            conditions:
              - condition: user
                user: Admin
            card:
              type: horizontal-stack
              cards:
                - type: button
                  name: +5 min
                  icon: mdi:timer-plus
                  tap_action:
                    action: call-service
                    service: timer.start
                    data:
                      entity_id: timer.face_auth
                      duration: "{{ (state_attr('timer.face_auth','duration')|as_timedelta).total_seconds() + 300 }}"
                - type: button
                  name: Pause
                  icon: mdi:pause
                  tap_action:
                    action: call-service
                    service: timer.pause
                    data:
                      entity_id: timer.face_auth
                - type: button
                  name: Stop
                  icon: mdi:stop
                  tap_action:
                    action: call-service
                    service: timer.cancel
                    data:
                      entity_id: timer.face_auth
```

---

## 7 测试清单
| 编号 | 场景 | 通过标准 |
|------|------|----------|
| T-1 | 发布 `result:false` | 计时器不创建 / 不重置 |
| T-2 | 首次刷脸 (`result:true`) | `timer.face_auth` state=`active`，剩余=15 min |
| T-3 | 倒计进行中再次刷脸 | 计时器剩余恢复 15 min |
| T-4 | 计时器到期 | 目标设备 state 变为 `off`，倒计器 state=`idle` |
| T-5 | 管理员点击 `+5 min` 按钮 | 剩余时长 +300 s |
| T-6 | 非管理员账号登录面板 | 不显示控制按钮 |

---

## 8 部署步骤
1. 启用 MQTT 集成，确保 `access/verify` 主题下能收到 `{ "result": true }` 消息。
2. 创建 Timer Helper：`timer.face_auth`。
3. 导入 Blueprint 并配置：
   - Topic: `access/verify`
   - Duration: `15`
   - Target entity: `switch.xx` 或 `light.xx`
4. 导入 Lovelace 视图或手动添加卡片。
5. 测试刷脸 ➜ 验证 ➜ 倒计时 ➜ 到期关闭设备。

---

> 完成！所有功能基于原生集成功能，无需自定义组件。
