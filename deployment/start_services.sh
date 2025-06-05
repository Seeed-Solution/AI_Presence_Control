#!/bin/bash
# 人脸识别门禁系统简化启动脚本 - 调试版本

set -e

echo "🚀 启动人脸识别门禁系统 (简化版本)..."

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
    mkdir -p services/mqtt/data
    mkdir -p services/mqtt/log
    mkdir -p services/node_red/data
    
    log_success "目录创建完成"
}

# 启动基础服务
start_infrastructure() {
    log_info "启动基础服务 (Qdrant, MQTT)..."
    
    # 检查并设置Docker Compose命令
    if command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    else
        DOCKER_COMPOSE_CMD="docker compose"
    fi
    
    # 启动基础服务
    $DOCKER_COMPOSE_CMD up -d qdrant mosquitto
    
    # 等待服务启动
    log_info "等待服务启动..."
    sleep 10
    
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
}

# 检查远程FaceEmbed API连接
check_remote_face_api() {
    log_info "检查远程 FaceEmbed API 连接..."
    
    local api_host="192.168.10.179"
    local api_port="8000"
    local api_url="http://${api_host}:${api_port}/health"
    
    log_info "尝试连接到: $api_url"
    
    if curl -f "$api_url" &> /dev/null; then
        log_success "FaceEmbed API 连接正常"
        return 0
    else
        log_warning "无法连接到 FaceEmbed API"
        log_info "请确保在 Hailo 设备 ($api_host) 上启动了 FaceEmbed API 服务"
        log_info "在 Hailo 设备上运行:"
        log_info "  ssh harvest@$api_host"
        log_info "  cd ~/face_embed_api"
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
            -H "api-key: face_access_2025" \
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
    log_info "简化系统部署信息:"
    echo
    echo "🏗️  系统架构:"
    echo "  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐"
    echo "  │ Grove Vision AI │───→│   MQTT Broker   │───→│    Node-RED     │"
    echo "  │      V2         │    │   (主服务器)    │    │   (主服务器)    │"
    echo "  │   (多设备)      │    │                 │    │  ┌─────────────┐ │"
    echo "  └─────────────────┘    └─────────────────┘    │  │ 配置都在    │ │"
    echo "                                              │  │ Node-RED中  │ │"
    echo "                                              │  └─────────────┘ │"
    echo "                                              └─────────────────┘"
    echo "                                                         │"
    echo "                                                         ▼ HTTP API"
    echo "  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐"
    echo "  │  FaceEmbed API  │◀───│     Qdrant      │◀───│ Vector Search   │"
    echo "  │ (Hailo设备)     │    │   (主服务器)    │    │                 │"
    echo "  │  192.168.10.179 │    │                 │    │                 │"
    echo "  └─────────────────┘    └─────────────────┘    └─────────────────┘"
    echo
    
    echo "🌐 服务访问地址:"
    echo "  • Qdrant (向量数据库):    http://localhost:6333/dashboard"
    echo "  • MQTT Broker:           mqtt://localhost:1883"
    
    if docker ps | grep -q face_access_nodered; then
        echo "  • Node-RED (流程编排):   http://localhost:1880"
    fi
    
    echo "  • FaceEmbed API:         http://192.168.10.179:8000/docs"
    echo
}

# 显示服务状态
show_service_status() {
    echo "📋 Docker 容器状态:"
    docker ps --filter "name=face_access" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo
    
    echo "🔧 快速操作:"
    echo "  • 查看日志: docker logs -f [container_name]"
    echo "  • 停止服务: docker-compose down"
    echo "  • 重启服务: docker restart [container_name]"
    echo "  • 检查FaceEmbed API: curl http://192.168.10.179:8000/health"
    echo
}

# 显示手动启动说明
show_manual_instructions() {
    echo "📝 手动启动服务 (推荐用于调试):"
    echo
    echo "1. 启动Qdrant:"
    echo "   docker run -d --name face_access_qdrant -p 6333:6333 \\"
    echo "     -v \$(pwd)/services/qdrant/storage:/qdrant/storage \\"
    echo "     -e QDRANT__SERVICE__API_KEY=face_access_2025 \\"
    echo "     qdrant/qdrant:v1.9.0"
    echo
    echo "2. 启动MQTT:"
    echo "   docker run -d --name face_access_mqtt -p 1883:1883 \\"
    echo "     -v \$(pwd)/services/mqtt/mosquitto.conf:/mosquitto/config/mosquitto.conf \\"
    echo "     eclipse-mosquitto:2.0"
    echo
    echo "3. 启动Node-RED:"
    echo "   docker run -d --name face_access_nodered -p 1880:1880 \\"
    echo "     -v \$(pwd)/flows:/data/flows -e TZ=Asia/Shanghai \\"
    echo "     nodered/node-red:3.1"
    echo
    echo "4. 启动FaceEmbed API (在Hailo设备上):"
    echo "   ssh harvest@192.168.10.179"
    echo "   cd ~/face_embed_api"
    echo "   python app.py"
    echo
    echo "详细的手动启动指南请查看: docs/manual_startup_guide.md"
    echo
}

# 显示配置说明
show_configuration_info() {
    echo "⚙️  Node-RED 配置说明:"
    echo
    echo "访问 http://localhost:1880 后，在以下节点中修改配置："
    echo
    echo "• 修改Hailo设备IP (API URL 配置器节点):"
    echo "  const faceEmbedHost = '192.168.10.179';"
    echo
    echo "• 设备Collection映射 (准备向量搜索节点):"
    echo "  const deviceCollectionMap = {"
    echo "    'grove_vision_ai_v2_001': 'office_entrance',"
    echo "    'grove_vision_ai_v2_002': 'warehouse_door'"
    echo "  };"
    echo
    echo "• 相似度阈值调整:"
    echo "  const threshold = 0.32;"
    echo
    echo "• Qdrant配置:"
    echo "  const qdrantHost = 'localhost';"
    echo "  const qdrantPort = '6333';"
    echo
}

# 主函数
main() {
    echo "========================================"
    echo "🎯 人脸识别门禁系统启动脚本 (简化版本)"
    echo "========================================"
    
    # 全局变量
    WITH_NODERED=false
    START_FACE_API=false
    MANUAL_MODE=false
    
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
            --manual)
                MANUAL_MODE=true
                shift
                ;;
            --help|-h)
                echo "使用方法: $0 [选项]"
                echo
                echo "选项:"
                echo "  --with-nodered     同时启动 Node-RED 容器"
                echo "  --start-face-api   在本地启动 FaceEmbed API (仅用于测试)"
                echo "  --manual           仅显示手动启动说明"
                echo "  --help, -h         显示此帮助信息"
                echo
                echo "简化系统说明:"
                echo "  • 仅包含 Qdrant、MQTT、Node-RED 三个核心服务"
                echo "  • 配置都在 Node-RED 中管理，无需环境变量"
                echo "  • FaceEmbed API 运行在 Hailo 设备 (192.168.10.179)"
                echo "  • 推荐使用 --manual 查看手动启动方式进行调试"
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
    
    # 如果是手动模式，只显示说明
    if [ "$MANUAL_MODE" = true ]; then
        show_manual_instructions
        show_configuration_info
        exit 0
    fi
    
    # 执行启动步骤
    check_prerequisites
    create_directories
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
    show_manual_instructions
    show_configuration_info
    
    log_success "人脸识别门禁系统 (简化版本) 启动完成！"
    log_info "建议使用手动启动方式进行调试: ./deployment/start_services.sh --manual"
}

# 运行主函数
main "$@"
