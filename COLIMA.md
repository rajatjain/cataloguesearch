# Colima Setup for CatalogueSearch

Colima is a lightweight Docker Desktop replacement that runs Docker containers in a Linux VM on macOS. It's perfect for CPU-intensive workloads like our reranking models and provides excellent amd64 compatibility for cloud deployment.

## Why Colima?

- **Performance**: Uses macOS Virtualization framework (faster than Docker Desktop)
- **amd64 compatibility**: Native support for cloud VM compatibility
- **Resource control**: Easy CPU/RAM allocation for ML workloads
- **Lightweight**: No GUI overhead, just the container runtime
- **Free**: Open source alternative to Docker Desktop
- **Drop-in replacement**: Same docker/docker-compose commands work

## Installation

```bash
# Install Colima and Docker CLI tools
brew install colima docker docker-compose

# Verify installation
colima version
docker --version
docker-compose --version
```

## Configuration for CatalogueSearch

### Basic Setup
```bash
# Start Colima with performance settings for reranking models
colima start --arch amd64 --cpu 6 --memory 12 --disk 60

# Check status
colima status
```

### Advanced Configuration
```bash
# For maximum performance (if you have the resources)
colima start \
  --arch amd64 \
  --cpu 8 \
  --memory 16 \
  --disk 100 \
  --vm-type=vz \
  --mount-type=virtiofs

# For development (lighter resources)
colima start \
  --arch amd64 \
  --cpu 4 \
  --memory 8 \
  --disk 60
```

### Configuration Options Explained
- `--arch amd64`: Ensures x86_64 architecture for cloud compatibility
- `--cpu 6`: Allocates 6 CPU cores (adjust based on your Mac)
- `--memory 12`: Allocates 12GB RAM (important for ML models)
- `--disk 60`: 60GB disk space for containers and images
- `--vm-type=vz`: Uses Apple's Virtualization framework (faster)
- `--mount-type=virtiofs`: Faster file sharing (macOS 13+ only)

## Migration from Docker Desktop

### Step 1: Stop Docker Desktop
- Quit Docker Desktop application
- Optionally uninstall Docker Desktop

### Step 2: Start Colima
```bash
# Start with your preferred configuration
colima start --arch amd64 --cpu 6 --memory 12 --disk 60
```

### Step 3: Test Your Setup
```bash
# Your existing commands should work unchanged
docker-compose up -d
docker ps
docker logs opensearch-node

# Test the restoration script
./scripts/restore_snapshots.sh
```

## Daily Usage

### Starting/Stopping
```bash
# Start Colima
colima start

# Stop Colima (saves resources when not developing)
colima stop

# Restart with different settings
colima stop
colima start --arch amd64 --cpu 8 --memory 16
```

### Managing Resources
```bash
# Check current resource usage
colima status
docker system df
docker stats

# Clean up resources
docker system prune
colima ssh -- df -h  # Check disk usage in VM
```

### SSH into VM (if needed)
```bash
# Access the underlying Linux VM
colima ssh

# Useful for debugging mount issues or checking processes
colima ssh -- ps aux | grep opensearch
```

## Configuration File (Optional)

Create `~/.colima/default/colima.yaml` for persistent settings:

```yaml
# Colima configuration for CatalogueSearch
cpu: 6
memory: 12
disk: 60
arch: amd64
runtime: docker
kubernetes:
  enabled: false
network:
  address: true
vmType: vz
mountType: virtiofs
```

## Performance Tuning for ML Workloads

### CPU Allocation
```bash
# Monitor CPU usage during reranking
docker stats cataloguesearch-api

# Adjust CPU allocation if needed
colima stop
colima start --arch amd64 --cpu 8 --memory 12
```

### Memory Management
```bash
# For heavy ML models, increase memory
colima start --arch amd64 --cpu 6 --memory 16

# Monitor memory usage
docker exec cataloguesearch-api free -h
```

### Docker Daemon Tuning
```bash
# Access Docker daemon config in Colima
colima ssh
sudo vim /etc/docker/daemon.json

# Add performance settings
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "default-ulimits": {
    "memlock": {
      "hard": -1,
      "soft": -1
    }
  }
}
```

## Troubleshooting

### Common Issues

1. **Port binding issues**
   ```bash
   # Check if ports are available
   lsof -i :9200
   colima status
   ```

2. **Mount issues**
   ```bash
   # Check mount points
   colima ssh -- mount | grep host
   # Restart with different mount type
   colima start --mount-type=sshfs
   ```

3. **Architecture issues**
   ```bash
   # Verify architecture
   docker run --rm alpine uname -m
   # Should output: x86_64
   ```

4. **Performance issues**
   ```bash
   # Check resource allocation
   colima status
   docker system df
   # Increase resources if needed
   colima stop
   colima start --arch amd64 --cpu 8 --memory 16
   ```

### Getting Help
```bash
# Check logs
colima logs

# Get detailed status
colima status --verbose

# Reset if needed (WARNING: destroys all containers)
colima delete
colima start --arch amd64 --cpu 6 --memory 12
```

## Comparison: Colima vs Docker Desktop

| Feature | Colima | Docker Desktop |
|---------|---------|----------------|
| Cost | Free | Free for personal, paid for commercial |
| Performance | Fast (native virtualization) | Slower (multiple abstraction layers) |
| Resource Usage | Low | High (GUI + background services) |
| amd64 Support | Native | Good but heavier |
| Kubernetes | Optional | Built-in |
| GUI | None (CLI only) | Full GUI |
| Updates | Manual | Automatic |

## Next Steps

1. **Install Colima**: `brew install colima docker docker-compose`
2. **Configure for ML workloads**: Use the performance settings above
3. **Test with CatalogueSearch**: Run your existing docker-compose setup
4. **Monitor performance**: Check CPU/memory usage during reranking operations
5. **Tune as needed**: Adjust resources based on your workload

## Additional Resources

- [Colima GitHub](https://github.com/abiosoft/colima)
- [Colima Documentation](https://github.com/abiosoft/colima/blob/main/docs/README.md)
- [Docker CLI Reference](https://docs.docker.com/engine/reference/commandline/cli/)