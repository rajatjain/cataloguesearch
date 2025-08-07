#!/bin/bash

# Docker Compose wrapper script for CatalogueSearch
# Usage: ./docker-run.sh [local|prod] [up|down|build|logs]

set -e

# Default values
ENV=${1:-local}
ACTION=${2:-up}

# Validate environment
if [[ "$ENV" != "local" && "$ENV" != "prod" ]]; then
    echo "Error: Environment must be 'local' or 'prod'"
    echo "Usage: $0 [local|prod] [up|down|build|logs]"
    exit 1
fi

# Validate action
if [[ "$ACTION" != "up" && "$ACTION" != "down" && "$ACTION" != "build" && "$ACTION" != "logs" && "$ACTION" != "build-api" && "$ACTION" != "restart-api" && "$ACTION" != "build-frontend" && "$ACTION" != "restart-frontend" ]]; then
    echo "Error: Action must be 'up', 'down', 'build', 'logs', 'build-api', 'restart-api', 'build-frontend', or 'restart-frontend'"
    echo "Usage: $0 [local|prod] [up|down|build|logs|build-api|restart-api|build-frontend|restart-frontend]"
    exit 1
fi

# Set environment file
ENV_FILE=".env.$ENV"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Error: Environment file $ENV_FILE not found"
    exit 1
fi

echo "Using environment: $ENV"
echo "Environment file: $ENV_FILE"
echo "Action: $ACTION"

# Run docker-compose with the specified environment
case $ACTION in
    "up")
        docker-compose --env-file "$ENV_FILE" up -d
        echo ""
        echo "Services are starting up..."
        echo "Frontend will be available at: http://localhost:3000"
        echo "API will be available at: http://localhost:8000"
        echo "OpenSearch Dashboards at: https://localhost:5601"
        echo ""
        echo "Check logs with: $0 $ENV logs"
        ;;
    "down")
        docker-compose --env-file "$ENV_FILE" down
        ;;
    "build")
        docker-compose --env-file "$ENV_FILE" build
        ;;
    "build-api")
        echo "Building only the API service..."
        docker-compose --env-file "$ENV_FILE" build cataloguesearch-api
        ;;
    "restart-api")
        echo "Rebuilding and restarting only the API service..."
        docker-compose --env-file "$ENV_FILE" build cataloguesearch-api
        docker-compose --env-file "$ENV_FILE" up -d --no-deps cataloguesearch-api
        echo "API service restarted. Available at: http://localhost:8000"
        ;;
    "build-frontend")
        echo "Building only the frontend service..."
        docker-compose --env-file "$ENV_FILE" build cataloguesearch-frontend
        ;;
    "restart-frontend")
        echo "Rebuilding and restarting only the frontend service..."
        docker-compose --env-file "$ENV_FILE" build cataloguesearch-frontend
        docker-compose --env-file "$ENV_FILE" up -d --no-deps cataloguesearch-frontend
        echo "Frontend service restarted. Available at: http://localhost:3000"
        ;;
    "logs")
        docker-compose --env-file "$ENV_FILE" logs -f
        ;;
esac