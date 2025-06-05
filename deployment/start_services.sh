#!/bin/bash
# 人脸识别门禁系统启动脚本 - 支持分布式部署

set -e

echo "🚀 启动人脸识别门禁系统 (分布式版本)..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查 Docker 和 Docker Compose
check_prerequisites() {
    log_info "检查系统依赖..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi
    
    # 检查 Docker 服务状态
    if ! docker info &> /dev/null; then
        log_error "Docker 服务未运行，请启动 Docker 服务"
        exit 1
    fi
    
    log_success "系统依赖检查通过"
}

# 创建必要的目录
create_directories() {
    log_info "创建必要的目录..."
    
    mkdir -p services/qdrant/storage
    mkdir -p services/qdrant/config
    mkdir -p services/mqtt/data
    mkdir -p services/mqtt/log
    mkdir -p services/node_red/data
    mkdir -p services/monitoring/prometheus
    mkdir -p services/monitoring/grafana/dashboards
    mkdir -p services/monitoring/grafana/datasources
    
    log_success "目录创建完成"
}

# 设置环境变量
setup_environment() {
    log_info "设置环境变量..."
    
    # 创建 .env 文件（如果不存在）
    if [ ! -f .env ]; then
        log_info "从模板创建 .env 配置文件..."
        if [ -f .env.example ]; then
            cp .env.example .env
            log_success "已从 .env.example 创建 .env 文件"
        else
            cat > .env << EOF
# 人脸识别门禁系统 - 分布式部署配置

# Hailo设备配置 (FaceEmbed API)
FACE_EMBED_API_HOST=192.168.10.179
FACE_EMBED_API_PORT=8000
FACE_EMBED_API_WORKERS=4

# 向量数据库配置 (Qdrant)
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=face_access_2025

# MQTT服务器配置
MQTT_HOST=localhost
MQTT_PORT=1883

# 算法参数配置
SIMILARITY_THRESHOLD=0.32
BATCH_SIZE=3
MAX_WAIT_TIME=100
API_TIMEOUT=5000

# 设备与Collection映射
COLLECTION_grove_vision_ai_v2_001=office_entrance
COLLECTION_grove_vision_ai_v2_002=warehouse_door
COLLECTION_grove_vision_ai_v2_003=lab_access

# 监控配置
GRAFANA_ADMIN_PASSWORD=admin123
PROMETHEUS_RETENTION=200h

# 部署模式配置
DEPLOY_MODE=production
COMPOSE_PROFILES=production

# 性能调优
MAX_CONCURRENT_CONNECTIONS=100
MEMORY_CACHE_SIZE=512
LOG_LEVEL=INFO
EOF
            log_success "创建默认 .env 配置文件"
        fi
    else
        log_info ".env 文件已存在，跳过创建"
    fi
    
    # 加载环境变量
    source .env
}

# 创建监控配置文件
setup_monitoring_config() {
    log_info "创建监控配置文件..."
    
    # Prometheus配置
    cat > services/monitoring/prometheus.yml << EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  # - "first_rules.yml"
  # - "second_rules.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'face-embed-api'
    static_configs:
      - targets: ['${FACE_EMBED_API_HOST:-192.168.10.179}:${FACE_EMBED_API_PORT:-8000}']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'qdrant'
    static_configs:
      - targets: ['${QDRANT_HOST:-localhost}:${QDRANT_PORT:-6333}']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'node-red'
    static_configs:
      - targets: ['localhost:1880']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'mqtt-broker'
    static_configs:
      - targets: ['localhost:1883']
    scrape_interval: 60s
EOF

    # Grafana数据源配置
    mkdir -p services/monitoring/grafana/datasources
    cat > services/monitoring/grafana/datasources/prometheus.yml << EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
EOF

    log_success "监控配置文件创建完成"
}

# 启动基础服务
start_infrastructure() {
    log_info "启动基础服务 (Qdrant, MQTT, 监控)..."
    
    # 检查并设置Docker Compose命令
    if command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    else
        DOCKER_COMPOSE_CMD="docker compose"
    fi
    
    # 启动基础服务
    $DOCKER_COMPOSE_CMD up -d qdrant mosquitto prometheus grafana
    
    # 等待服务启动
    log_info "等待服务启动..."
    sleep 15
    
    # 检查服务状态
    check_service_health
}

# 检查服务健康状态
check_service_health() {
    log_info "检查服务健康状态..."
    
    # 检查 Qdrant
    log_info "检查 Qdrant 服务..."
    for i in {1..30}; do
        if curl -f http://localhost:6333/health &> /dev/null; then
            log_success "Qdrant 服务正常 (http://localhost:6333)"
            break
        fi
        sleep 2
        if [ $i -eq 30 ]; then
            log_warning "Qdrant 服务启动超时，可能需要更多时间"
        fi
    done
    
    # 检查 MQTT
    log_info "检查 MQTT 服务..."
    if nc -z localhost 1883 &> /dev/null; then
        log_success "MQTT 服务正常 (mqtt://localhost:1883)"
    else
        log_warning "MQTT 服务可能未完全启动"
    fi
    
    # 检查 Prometheus
    log_info "检查 Prometheus 服务..."
    for i in {1..20}; do
        if curl -f http://localhost:9090/-/healthy &> /dev/null; then
            log_success "Prometheus 服务正常 (http://localhost:9090)"
            break
        fi
        sleep 2
        if [ $i -eq 20 ]; then
            log_warning "Prometheus 服务启动超时"
        fi
    done
    
    # 检查 Grafana
    log_info "检查 Grafana 服务..."
    for i in {1..20}; do
        if curl -f http://localhost:3000/api/health &> /dev/null; then
            log_success "Grafana 服务正常 (http://localhost:3000)"
            break
        fi
        sleep 2
        if [ $i -eq 20 ]; then
            log_warning "Grafana 服务启动超时"
        fi
    done
}

# 检查远程FaceEmbed API连接
check_remote_face_api() {
    log_info "检查远程 FaceEmbed API 连接..."
    
    local api_host=${FACE_EMBED_API_HOST:-192.168.10.179}
    local api_port=${FACE_EMBED_API_PORT:-8000}
    local api_url="http://${api_host}:${api_port}/health"
    
    log_info "尝试连接到: $api_url"
    
    if curl -f "$api_url" &> /dev/null; then
        log_success "FaceEmbed API 连接正常"
        return 0
    else
        log_warning "无法连接到 FaceEmbed API"
        log_info "请确保在 Hailo 设备 ($api_host) 上启动了 FaceEmbed API 服务"
        log_info "在 Hailo 设备上运行:"
        log_info "  cd /path/to/face_embed_api"
        log_info "  python app.py"
        return 1
    fi
}

# 初始化 Qdrant 集合
init_qdrant_collections() {
    log_info "初始化 Qdrant 人脸向量集合..."
    
    # 等待 Qdrant 完全启动
    timeout=60
    while [ $timeout -gt 0 ]; do
        if curl -f http://localhost:6333/health &> /dev/null; then
            break
        fi
        sleep 1
        ((timeout--))
    done
    
    if [ $timeout -eq 0 ]; then
        log_error "Qdrant 启动超时"
        return 1
    fi
    
    # 创建默认集合
    collections=("default_faces" "office_entrance" "warehouse_door" "lab_access")
    
    for collection in "${collections[@]}"; do
        log_info "创建集合: $collection"
        
        curl -X PUT "http://localhost:6333/collections/$collection" \
            -H "Content-Type: application/json" \
            -H "api-key: ${QDRANT_API_KEY:-face_access_2025}" \
            -d '{
                "vectors": {
                    "size": 512,
                    "distance": "Cosine"
                },
                "optimizers_config": {
                    "default_segment_number": 2
                },
                "replication_factor": 1
            }' &> /dev/null || log_info "集合 $collection 可能已存在"
    done
    
    log_success "Qdrant 集合初始化完成"
}

# 启动 Node-RED
start_nodered() {
    if [ "$WITH_NODERED" = true ]; then
        log_info "启动 Node-RED..."
        
        # 确保flows目录存在并复制流程文件
        mkdir -p services/node_red/data
        if [ -f flows/face_access_control.json ]; then
            cp flows/face_access_control.json services/node_red/data/
            log_info "已复制 Node-RED 流程文件"
        fi
        
        $DOCKER_COMPOSE_CMD up -d node-red
        
        log_info "等待 Node-RED 启动..."
        for i in {1..30}; do
            if curl -f http://localhost:1880 &> /dev/null; then
                log_success "Node-RED 已启动: http://localhost:1880"
                break
            fi
            sleep 2
            if [ $i -eq 30 ]; then
                log_warning "Node-RED 启动超时"
            fi
        done
    fi
}

# 启动本地测试的 FaceEmbed API
start_local_face_api() {
    if [ "$START_FACE_API" = true ]; then
        log_info "启动本地 FaceEmbed API (仅用于测试)..."
        $DOCKER_COMPOSE_CMD --profile local-test up -d face-embed-api
        
        log_info "等待 FaceEmbed API 启动..."
        for i in {1..30}; do
            if curl -f http://localhost:8000/health &> /dev/null; then
                log_success "本地 FaceEmbed API 已启动: http://localhost:8000"
                break
            fi
            sleep 2
            if [ $i -eq 30 ]; then
                log_warning "FaceEmbed API 启动超时"
            fi
        done
    fi
}

# 显示部署信息
show_deployment_info() {
    log_info "分布式部署信息:"
    echo
    echo "🏗️  系统架构:"
    echo "  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐"
    echo "  │ Grove Vision AI │───→│   MQTT Broker   │───→│    Node-RED     │"
    echo "  │      V2         │    │   (本机)        │    │    (本机)       │"
    echo "  └─────────────────┘    └─────────────────┘    └─────────────────┘"
    echo "                                                         │"
    echo "                                                         ▼"
    echo "  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐"
    echo "  │  FaceEmbed API  │◀───│     Qdrant      │◀───│ HTTP Request    │"
    echo "  │ (Hailo设备)     │    │    (本机)       │    │                 │"
    echo "  └─────────────────┘    └─────────────────┘    └─────────────────┘"
    echo
    
    echo "🌐 服务访问地址:"
    echo "  • Qdrant (向量数据库):    http://localhost:6333/dashboard"
    echo "  • MQTT Broker:           mqtt://localhost:1883"
    echo "  • Prometheus (监控):     http://localhost:9090"
    echo "  • Grafana (仪表板):      http://localhost:3000 (admin/${GRAFANA_ADMIN_PASSWORD:-admin123})"
    
    if docker ps | grep -q face_access_nodered; then
        echo "  • Node-RED (流程编排):   http://localhost:1880"
    fi
    
    echo "  • FaceEmbed API:         http://${FACE_EMBED_API_HOST:-192.168.10.179}:${FACE_EMBED_API_PORT:-8000}/docs"
    echo
}

# 显示服务状态
show_service_status() {
    echo "📋 Docker 容器状态:"
    docker ps --filter "name=face_access" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo
    
    echo "🔧 快速操作:"
    echo "  • 查看日志: docker-compose logs -f [service_name]"
    echo "  • 停止服务: docker-compose down"
    echo "  • 重启服务: docker-compose restart [service_name]"
    echo "  • 检查FaceEmbed API: curl http://${FACE_EMBED_API_HOST:-192.168.10.179}:${FACE_EMBED_API_PORT:-8000}/health"
    echo
}

# 显示下一步操作
show_next_steps() {
    echo "🎯 下一步操作:"
    echo
    echo "1. 📱 配置 Grove Vision AI V2 设备:"
    echo "   - 连接到网络: ${MQTT_HOST:-localhost}:${MQTT_PORT:-1883}"
    echo "   - 配置MQTT主题: vision/frames/{device_id}"
    echo
    echo "2. 🔧 在 Hailo 设备上启动 FaceEmbed API:"
    echo "   ssh harvest@${FACE_EMBED_API_HOST:-192.168.10.179}"
    echo "   cd ~/face_embed_api"
    echo "   python app.py"
    echo
    echo "3. 🌊 导入和配置 Node-RED 流程:"
    if [ "$WITH_NODERED" = true ]; then
        echo "   - 访问: http://localhost:1880"
        echo "   - 导入: flows/face_access_control.json"
        echo "   - 配置环境变量 (参考 .env 文件)"
    else
        echo "   - 重新运行脚本并添加 --with-nodered 参数"
    fi
    echo
    echo "4. 🧪 测试系统功能:"
    echo "   - 人脸入库: 发送MQTT消息到 access/enroll/{device_id}"
    echo "   - 人脸识别: Grove Vision AI V2 自动发送帧数据"
    echo "   - 监控系统: 访问 Grafana 仪表板"
    echo
}

# 主函数
main() {
    echo "========================================"
    echo "🎯 人脸识别门禁系统启动脚本 (分布式版本)"
    echo "========================================"
    
    # 全局变量
    WITH_NODERED=false
    START_FACE_API=false
    
    # 检查参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --with-nodered)
                WITH_NODERED=true
                shift
                ;;
            --start-face-api)
                START_FACE_API=true
                shift
                ;;
            --help|-h)
                echo "使用方法: $0 [选项]"
                echo
                echo "选项:"
                echo "  --with-nodered     同时启动 Node-RED 容器"
                echo "  --start-face-api   在本地启动 FaceEmbed API (仅用于测试)"
                echo "  --help, -h         显示此帮助信息"
                echo
                echo "分布式部署说明:"
                echo "  • Node-RED 和 Qdrant 运行在主服务器"
                echo "  • FaceEmbed API 运行在 Hailo 设备 (${FACE_EMBED_API_HOST:-192.168.10.179})"
                echo "  • Grove Vision AI V2 通过 MQTT 连接到主服务器"
                echo
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                echo "使用 --help 查看可用选项"
                exit 1
                ;;
        esac
    done
    
    # 执行启动步骤
    check_prerequisites
    create_directories
    setup_environment
    setup_monitoring_config
    start_infrastructure
    init_qdrant_collections
    
    if [ "$WITH_NODERED" = true ]; then
        start_nodered
    fi
    
    if [ "$START_FACE_API" = true ]; then
        start_local_face_api
    else
        check_remote_face_api
    fi
    
    show_deployment_info
    show_service_status
    show_next_steps
    
    log_success "人脸识别门禁系统 (分布式版本) 启动完成！"
}

# 运行主函数
main "$@"
