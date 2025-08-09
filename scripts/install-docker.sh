#!/bin/bash

# Docker Installation Script for Ubuntu/Debian
# Usage: ./scripts/install-docker.sh

set -e

echo "🐳 Installing Docker and Docker Compose..."
echo "================================================"

# Update package index
echo "📦 Updating package index..."
apt-get update -qq

# Install prerequisites
echo "🔧 Installing prerequisites..."
apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's official GPG key
echo "🔑 Adding Docker GPG key..."
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up Docker repository
echo "📁 Setting up Docker repository..."
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update package index with Docker repo
echo "🔄 Updating package index with Docker repository..."
apt-get update -qq

# Install Docker Engine
echo "🐳 Installing Docker Engine..."
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start and enable Docker service
echo "🚀 Starting Docker service..."
systemctl enable docker
systemctl start docker

# Add current user to docker group (if not root)
if [ "$EUID" -ne 0 ]; then
    echo "👤 Adding $USER to docker group..."
    usermod -aG docker $USER
    echo "⚠️  Please log out and log back in for group changes to take effect"
fi

# Install Docker Compose (standalone)
echo "🔗 Installing Docker Compose..."
DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Create symlink for docker-compose plugin compatibility
ln -sf /usr/local/bin/docker-compose /usr/local/bin/docker-compose

# Test installations
echo ""
echo "🧪 Testing installations..."
echo "================================================"

# Test Docker
docker --version
if docker run hello-world > /dev/null 2>&1; then
    echo "✅ Docker is working correctly"
else
    echo "❌ Docker test failed"
    exit 1
fi

# Test Docker Compose
docker-compose --version
echo "✅ Docker Compose is installed"

# Clean up
echo ""
echo "🧹 Cleaning up..."
docker rmi hello-world > /dev/null 2>&1 || true
apt-get autoremove -y
apt-get autoclean

echo ""
echo "🎉 Docker installation completed successfully!"
echo "================================================"
echo "Docker version: $(docker --version)"
echo "Docker Compose version: $(docker-compose --version)"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo "⚠️  IMPORTANT: Please log out and log back in to use Docker without sudo"
    echo "   Or run: newgrp docker"
else
    echo "✅ Ready to use Docker!"
fi

echo ""
echo "📋 Next steps:"
echo "1. Copy docker-compose.prod.yml to your server"
echo "2. Copy snapshots directory to your server" 
echo "3. Run: docker-compose -f docker-compose.prod.yml up -d"