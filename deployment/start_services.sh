#!/bin/bash
# Simplified startup script for the Face Recognition Access Control System - Debug Version

set -e

echo "🚀 Starting Face Recognition Access Control System (Simplified Version)..."

# Color Definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging Functions
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

# Check for Docker and Docker Compose
check_prerequisites() {
    log_info "Checking system dependencies..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check Docker service status
    if ! docker info &> /dev/null; then
        log_error "Docker service is not running. Please start the Docker service."
        exit 1
    fi
    
    log_success "System dependencies check passed."
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."
    
    mkdir -p services/mqtt/data
    mkdir -p services/mqtt/log
    mkdir -p services/node_red/data
    
    log_success "Directories created."
}

# Start infrastructure services
start_infrastructure() {
    log_info "Starting infrastructure services (MQTT)..."
    
    # Check and set Docker Compose command
    if command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    else
        DOCKER_COMPOSE_CMD="docker compose"
    fi
    
    # Start infrastructure services
    $DOCKER_COMPOSE_CMD up -d mosquitto
    
    # Wait for services to start
    log_info "Waiting for services to start..."
    sleep 10
    
    # Check service status
    check_service_health
}

# Check service health status
check_service_health() {
    log_info "Checking service health..."
    
    # Check MQTT
    log_info "Checking MQTT service..."
    if nc -z localhost 1883 &> /dev/null; then
        log_success "MQTT service is running (mqtt://localhost:1883)"
    else
        log_warning "MQTT service may not be fully started yet."
    fi
}

# Check and connect to the remote FaceEmbed API
check_and_connect_remote_face_api() {
    log_info "Checking remote FaceEmbed API connection status..."
    
    local api_host="192.168.10.179"
    local api_port="8000"
    local api_url="http://${api_host}:${api_port}/health"
    
    log_info "Attempting to connect to: $api_url"
    
    # Check network connectivity
    if ! ping -c 1 -W 3 "$api_host" &> /dev/null; then
        log_error "Cannot ping Hailo device ($api_host)."
        log_info "Please check the network connection and device status."
        return 1
    fi
    
    # Check API service status
    if curl -f --connect-timeout 5 --max-time 10 "$api_url" &> /dev/null; then
        log_success "✅ FaceEmbed API connection is OK."
        
        # Get API details
        local api_info
        api_info=$(curl -s "$api_url" 2>/dev/null)
        if [ $? -eq 0 ]; then
            log_info "API Status: $api_info"
        fi
        
        # Test API functionality
        log_info "Testing basic API functionality..."
        if curl -f "$api_url" -H "Accept: application/json" &> /dev/null; then
            log_success "API functionality test passed."
        fi
        
        return 0
    else
        log_warning "❌ Could not connect to FaceEmbed API."
        log_info ""
        log_info "🔧 To start the FaceEmbed API on the Hailo device:"
        log_info "   ssh user@$api_host"
        log_info "   cd ~/face_embed_api"
        log_info "   source .venv/bin/activate"
        log_info "   python src/face_embed_api/app.py"
        log_info ""
        log_info "Or use the start script:"
        log_info "   ssh user@$api_host 'cd ~/face_embed_api && python scripts/start_server.py'"
        log_info ""
        log_info "To verify it started successfully:"
        log_info "   curl http://$api_host:$api_port/health"
        log_info ""
        
        return 1
    fi
}


# Start Node-RED
start_nodered() {
    if [ "$WITH_NODERED" = true ]; then
        log_info "Starting Node-RED..."
        
        # Ensure data directory exists and copy the flow file
        mkdir -p services/node_red/data
        if [ -f services/node_red/face_access_control.json ]; then
            cp services/node_red/face_access_control.json services/node_red/data/
            log_info "Copied Node-RED flow file."
        elif [ -f flows/face_access_control.json ]; then
            cp flows/face_access_control.json services/node_red/data/
            log_info "Copied Node-RED flow file (from legacy path)."
        else
            log_warning "Node-RED flow file not found. Please import it manually."
        fi
        
        $DOCKER_COMPOSE_CMD up -d node-red
        
        log_info "Waiting for Node-RED to start..."
        for i in {1..30}; do
            if curl -f http://localhost:1880 &> /dev/null; then
                log_success "Node-RED is running: http://localhost:1880"
                break
            fi
            sleep 2
            if [ $i -eq 30 ]; then
                log_warning "Node-RED startup timed out."
            fi
        done
    fi
}

# Display deployment information
show_deployment_info() {
    log_info "Simplified System Deployment Information:"
    echo
    echo "🏗️  System Architecture (New):"
    echo "  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐"
    echo "  │ Grove Vision AI │───→│   MQTT Broker   │───→│    Node-RED     │"
    echo "  │      V2         │    │   (Main Server) │    │   (Main Server) │"
    echo "  │   (Multiple)    │    │                 │    │                 │"
    echo "  └─────────────────┘    └─────────────────┘    └─────────────────┘"
    echo "           ▲                                             │"
    echo "           │                                             │"
    echo "           │ MQTT                                        │ HTTP API"
    echo "           │                                             │"
    echo "           └────────────────────┬──────────────────────────┘"
    echo "                                │"
    echo "                                ▼"
    echo "                      ┌─────────────────┐"
    echo "                      │  FaceEmbed API  │"
    echo "                      │ (with SQLite DB)│"
    echo "                      │ 192.168.10.179  │"
    echo "                      └─────────────────┘"
    echo
    
    echo "🌐 Service URLs:"
    echo "  • MQTT Broker:           mqtt://localhost:1883"
    
    if docker ps | grep -q face_access_nodered; then
        echo "  • Node-RED (Flows):   http://localhost:1880"
    fi
    
    echo "  • FaceEmbed API:         http://192.168.10.179:8000/docs"
    echo
}

# Display service status
show_service_status() {
    echo "📋 Docker Container Status:"
    docker ps --filter "name=face_access" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo
    
    echo "🔧 Quick Actions:"
    echo "  • View Logs: docker logs -f [container_name]"
    echo "  • Stop Services: docker-compose down"
    echo "  • Restart Service: docker restart [container_name]"
    echo "  • Check FaceEmbed API: curl http://192.168.10.179:8000/health"
    echo
}

# Display manual startup instructions
show_manual_instructions() {
    echo "📝 Manual Startup (Recommended for Debugging):"
    echo
    echo "1. Start MQTT:"
    echo "   docker run -d --name face_access_mqtt -p 1883:1883 \\"
    echo "     -v \$(pwd)/services/mqtt/mosquitto.conf:/mosquitto/config/mosquitto.conf \\"
    echo "     eclipse-mosquitto:2.0"
    echo
    echo "2. Start Node-RED:"
    echo "   docker run -d --name face_access_nodered -p 1880:1880 \\"
    echo "     -v \$(pwd)/services/node_red:/data -e TZ=Asia/Shanghai \\"
    echo "     nodered/node-red:3.1"
    echo
    echo "4. Start FaceEmbed API (on Hailo device):"
    echo "   ssh user@192.168.10.179"
    echo "   cd ~/face_embed_api"
    echo "   source .venv/bin/activate"
    echo "   python src/face_embed_api/app.py"
    echo ""
    echo "   Or use the convenience script:"
    echo "   python scripts/start_server.py"
    echo ""
    echo "   Verify service status:"
    echo "   curl http://192.168.10.179:8000/health"
    echo
    echo "For a detailed manual startup guide, see: docs/manual_startup_guide.md"
    echo
}

# Display configuration info
show_configuration_info() {
    echo "⚙️  Node-RED Configuration:"
    echo
    echo "Access http://localhost:1880 and modify the following nodes:"
    echo
    echo "• Modify Hailo device IP (in 'Global Config' node):"
    echo "  flow.set('hailo_host', '192.168.10.179');"
    echo
    echo "• Map devices to collections (in 'Prepare Vector Search' node):"
    echo "  const deviceCollectionMap = {"
    echo "    'grove_vision_ai_v2_001': 'office_entrance',"
    echo "    'grove_vision_ai_v2_002': 'warehouse_door'"
    echo "  };"
    echo
    echo "• Adjust similarity threshold (in 'Prepare Vector Search' node):"
    echo "  const threshold = 0.32;"
    echo
}

# Main function
main() {
    echo "========================================"
    echo "🎯 Face Recognition Access System Start"
    echo "========================================"
    
    # Global variables
    WITH_NODERED=false
    MANUAL_MODE=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --with-nodered)
                WITH_NODERED=true
                shift
                ;;
            --manual)
                MANUAL_MODE=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo
                echo "Options:"
                echo "  --with-nodered     Also start the Node-RED container."
                echo "  --manual           Only display manual startup instructions."
                echo "  --help, -h         Show this help message."
                echo
                echo "About this simplified system:"
                echo "  • Includes only MQTT and Node-RED core services."
                echo "  • All configuration is managed in Node-RED and the FaceEmbed API, no .env files needed."
                echo "  • The FaceEmbed API runs on a separate Hailo device (192.168.10.179)."
                echo "  • For debugging, using --manual is recommended."
                echo
                exit 0
                ;;
            *)
                log_error "Unknown parameter: $1"
                echo "Use --help for available options."
                exit 1
                ;;
        esac
    done
    
    # If in manual mode, just show instructions and exit
    if [ "$MANUAL_MODE" = true ]; then
        show_manual_instructions
        show_configuration_info
        exit 0
    fi
    
    # Execute startup steps
    check_prerequisites
    create_directories
    start_infrastructure
    
    if [ "$WITH_NODERED" = true ]; then
        start_nodered
    fi
    
    # Check remote FaceEmbed API connection
    check_and_connect_remote_face_api
    
    show_deployment_info
    show_service_status
    show_manual_instructions
    show_configuration_info
    
    log_success "Face Recognition Access Control System (Simplified Version) startup complete!"
    log_info "For debugging, it is recommended to use the manual start method: ./deployment/start_services.sh --manual"
}

# Run main function
main "$@"
