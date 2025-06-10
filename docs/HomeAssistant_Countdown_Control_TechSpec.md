# Home Assistant Countdown Control System — Technical Design Specification (TDS)

> 版本 0.9 — 2025‑06‑09  
> **依赖**：请先阅读《Home Assistant Countdown Control System — PRD》并确认需求。

---

## 1 整体架构

```
repo/
├── custom_components/
│   └── countdown_control/
│        ├── __init__.py        # 注册 MQTT 侦听 / 计时器逻辑
│        ├── manifest.json      # HA 自定义集成元数据
│        ├── blueprint.yaml     # 自动化 Blueprint（与 PRD 中一致）
│        └── services.yaml      # 公开服务: start, pause, cancel, add_time
├── blueprints/
│   └── automation/
│        └── countdown_control.yaml (软链接到上方文件)
├── dashboards/
│   └── countdown_example.yaml   # Lovelace UI 样例
├── config/
│   ├── configuration.yaml       # 仅示例片段
│   └── secrets.yaml             # MQTT 凭据
├── tests/                       # pytest + HA-core fixtures
│   ├── conftest.py
│   └── test_countdown.py
├── docker-compose.yml           # Mosquitto + HA + Node‑RED + Qdrant
└── README.md
```

### 核心流程

1. **MQTT Handler** (`async_setup_entry`)  
   - 订阅 topic `access/verify` (可多实例)。  
   - 收到 `result:true` → 调用 `async_reset_timer(entity_id, duration)`。
2. **Timer 实体**  
   - 由 `hass.helpers.event.async_track_time_interval` 每秒减少 1 s。  
   - 剩余值存储在 `hass.data[DOMAIN][device_id]['remaining']`。
3. **Services**  
   - `countdown_control.start` — 手动/自动重置计时。  
   - `countdown_control.pause` — 暂停计时（内部停止 async task）。  
   - `countdown_control.cancel` — 直接归零并触发关停。  
   - `countdown_control.add_time` — 在运行中动态增加 N 秒。
4. **Automation Blueprint**  
   - 对不想安装自定义集成的场景，仅用原生 timer + automation 实现同流程（无 Python 逻辑）。

---

## 2 自定义集成实现

### 2.1 `manifest.json`

```json
{
  "domain": "countdown_control",
  "name": "Countdown Control",
  "version": "0.1.0",
  "config_flow": false,
  "requirements": [],
  "iot_class": "local_push",
  "dependencies": ["mqtt"],
  "services": ["start", "pause", "cancel", "add_time"]
}
```

### 2.2 MQTT 订阅示例（片段）

```python
async def async_setup_entry(hass, entry):
    mqtt = hass.components.mqtt
    topic = entry.data.get("mqtt_topic", "access/verify")

    async def _handle(msg):
        payload = json.loads(msg.payload)
        if payload.get("result"):
            dev = payload["device_id"]
            await async_reset_timer(hass, dev, entry.data.get("duration", 900))
    await mqtt.async_subscribe(topic, _handle, 1)
    return True
```

### 2.3 Timer 逻辑

```python
async def async_reset_timer(hass, device_id, duration):
    data = hass.data.setdefault(DOMAIN, {})
    # 取消旧计时器
    if handler := data.get(device_id, {}).get("handler"):
        handler()
    # 新计时器
    remaining = duration

    async def _tick(now):
        nonlocal remaining
        remaining -= 1
        if remaining <= 0:
            await hass.services.async_call(
                "homeassistant", "turn_off", {"entity_id": dev_entity(device_id)}
            )
            handler()  # stop
        else:
            hass.states.async_set(f"sensor.remaining_{device_id}", remaining)
    handler = async_track_time_interval(hass, _tick, timedelta(seconds=1))
    data[device_id] = {"handler": handler}
```

> **注意**：若使用原生 `timer` 实体方案，不必编写此逻辑。

---

## 3 Blueprint (完整 YAML)

```yaml
blueprint:
  name: "Countdown Control (MQTT + Timer)"
  description: >
    当指定 MQTT 主题收到 result=true 时，重置计时器并在到期后关闭设备。
  domain: automation
  input:
    mqtt_topic:
      name: MQTT Topic
      default: access/verify
    duration:
      name: Duration (minutes)
      default: 15
    target_entity:
      name: Target entity to control
      selector:
        entity:
          domain: [switch, light]
    warn_threshold:
      name: Warn threshold (minutes)
      default: 2
    notify_service:
      name: Notify service (optional)
      default: ""

mode: restart
variables:
  t_seconds: "{{ duration | int * 60 }}"

trigger:
  - platform: mqtt
    topic: !input mqtt_topic
    payload: "{"result":true}"
    value_template: "{{ value_json.result }}"

condition: []

action:
  - service: timer.start
    data:
      entity_id: "timer.{{ trigger.payload_json.device_id }}"
      duration: "{{ t_seconds }}"
  - service: switch.turn_on
    data:
      entity_id: !input target_entity

  # 可选预警
  - wait_for_trigger:
      - platform: event
        event_type: timer.finished
        event_data:
          entity_id: "timer.{{ trigger.payload_json.device_id }}"
        timeout: "{{ (warn_threshold | int) * 60 }}"
    continue_on_timeout: false
  - choose:
      - conditions:
          - "{{ wait.remaining == 0 }}"
        sequence:
          - service: switch.turn_off
            data:
              entity_id: !input target_entity
          - if: "{{ notify_service != '' }}"
            then:
              - service: "{{ notify_service }}"
                data:
                  message: "{{ trigger.payload_json.device_id }} 倒计时已结束，设备已关闭。"
```

---

## 4 Lovelace Dashboard 片段

```yaml
views:
  - title: Countdown
    path: countdown
    badges: []
    cards:
      - type: vertical-stack
        cards:
          - type: custom:timer-bar-card
            entity: timer.door1
            name: 剩余时间
          - type: conditional             # 管理员专属按钮
            conditions:
              - condition: user
                user: Admin
            card:
              type: horizontal-stack
              cards:
                - type: button
                  name: 加时 5 min
                  icon: mdi:timer-plus
                  tap_action:
                    action: call-service
                    service: countdown_control.add_time
                    data:
                      device_id: door1
                      seconds: 300
                - type: button
                  name: 暂停
                  icon: mdi:pause
                  tap_action:
                    action: call-service
                    service: countdown_control.pause
                    data:
                      device_id: door1
                - type: button
                  name: 终止
                  icon: mdi:stop
                  tap_action:
                    action: call-service
                    service: countdown_control.cancel
                    data:
                      device_id: door1
```

---

## 5 Docker Compose（示例）

```yaml
version: "3.9"
services:
  mqtt:
    image: eclipse-mosquitto:2
    ports: [1883:1883]
    volumes:
      - ./config/mosquitto.conf:/mosquitto/config/mosquitto.conf
  homeassistant:
    image: ghcr.io/home-assistant/home-assistant:stable
    depends_on: [mqtt]
    ports: [8123:8123]
    volumes:
      - ./config:/config
      - /etc/localtime:/etc/localtime:ro
    environment:
      - TZ=Asia/Shanghai
```

---

## 6 测试计划

| 用例编号 | 场景                    | 期望结果                            |
| ---- | --------------------- | ------------------------------- |
| TC‑1 | MQTT 推送 result=false  | 不创建/重置计时器                       |
| TC‑2 | 计时进行中再次刷脸             | 剩余时间恢复满值 (15 min)               |
| TC‑3 | 倒计至 0                 | `switch.turn_off` 被调用，state=off |
| TC‑4 | 管理员点击“加时”             | 计时器 +300 s，Lovecace 实时更新        |
| TC‑5 | 非管理员访问面板              | 不显示专属按钮                         |
| TC‑6 | Blueprint 导入后 YAML 校验 | HA 重载配置无错误                      |

在 `tests/test_countdown.py` 使用 HA-Core 官方 `pytest_homeassistant_custom_component` 框架编写单元测试。

---

## 7 CI/CD

- **GitHub Actions**：
  1. Lint (`ruff`) + Unit Tests。  
  2. Version bump → 打包 `release.tar.gz`，含 blueprint 和 dashboard YAML。  
  3. 可选：打镜像并推送到 GHCR `countdown_demo`，用于一键 demo 部署。

---

## 8 后续迭代

- 支持多并发计时器（多设备、多用户）。  
- 集成 Zigbee‑MQTT 或 Matter 设备。  
- 增加 WebSocket 实时推送到外部客户端（如 React 控制面板）。
