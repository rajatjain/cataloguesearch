import docker
import argparse
import sys
import os
import time

# =================================================================
# OpenSearch Docker Control Script (Using Docker SDK for Python)
#
# This script manages a local OpenSearch container for development.
# =================================================================

# --- Configuration ---
# You can modify these variables as needed.
CONTAINER_NAME = "opensearch-cataloguesearch"
DASHBOARDS_CONTAINER_NAME = "opensearch-dashboards-cataloguesearch"
IMAGE_NAME = "opensearchproject/opensearch:3.0.0"
DASHBOARDS_IMAGE_NAME = "opensearchproject/opensearch-dashboards:3.0.0"
ADMIN_PASSWORD = "Admin@Password123!" # IMPORTANT: Change this!
HEAP_SIZE = "512m"
DOCKER_NETWORK_NAME = "opensearch-custom-network"

def get_docker_client():
    """Initializes and returns a Docker client."""
    try:
        socket_path = f"unix://{os.path.expanduser('~')}/.docker/run/docker.sock"
        print(f"Temporarily setting DOCKER_HOST for this script to: {socket_path}")
        os.environ['DOCKER_HOST'] = socket_path
        client = docker.from_env()
        client.ping()
        print("Successfully connected to Docker.")
        return client

    except TypeError as e:
        if 'load_config' in str(e) and 'config_dict' in str(e):
            print("\nCritical Error: Conflicting Docker libraries detected.")
            print("You likely have both 'docker' and 'docker-py' installed, which are incompatible.")
            print("\nPlease fix your environment by running these commands:")
            print("  pip uninstall -y docker docker-py")
            print("  pip install docker")
        else:
            print(f"\nAn unexpected TypeError occurred: {e}")
        sys.exit(1)

    except Exception as e:
        print(f"\nError: Failed to connect to Docker.")
        print("This might be due to conflicting Docker libraries in your Python environment.")
        print("If this error persists, please try reinstalling the library:")
        print("pip uninstall docker docker-py")
        print("pip install docker")
        print(f"\nError details: {e}")
        sys.exit(1)

def stop_container(client: docker.DockerClient):
    """Stops and removes the OpenSearch and OpenSearch Dashboards containers, and removes the custom network."""
    containers_to_stop = [CONTAINER_NAME, DASHBOARDS_CONTAINER_NAME]
    for name in containers_to_stop:
        try:
            container = client.containers.get(name)
            print(f"Stopping container '{name}'...")
            container.stop(timeout=10) # Give it 10 seconds to stop gracefully
            print(f"Removing container '{name}'...")
            container.remove()
            print(f"Container '{name}' stopped and removed successfully.")
        except docker.errors.NotFound:
            print(f"Container '{name}' not found. Nothing to do.")
        except docker.errors.APIError as e:
            print(f"An API error occurred with container '{name}': {e}")

    # Remove the custom network after containers are stopped
    try:
        network = client.networks.get(DOCKER_NETWORK_NAME)
        print(f"Removing network '{DOCKER_NETWORK_NAME}'...")
        network.remove()
        print(f"Network '{DOCKER_NETWORK_NAME}' removed successfully.")
    except docker.errors.NotFound:
        print(f"Network '{DOCKER_NETWORK_NAME}' not found. Nothing to do.")
    except docker.errors.APIError as e:
        print(f"An API error occurred while removing network '{DOCKER_NETWORK_NAME}': {e}")


def wait_for_opensearch(client: docker.DockerClient, container_name: str, admin_password: str, max_attempts=40, delay=5): # Increased max_attempts
    """
    Waits for the OpenSearch container to be healthy and ready.
    Pings the _cluster/health endpoint with authentication.
    """
    print(f"Waiting for OpenSearch container '{container_name}' to be healthy...")
    for attempt in range(1, max_attempts + 1):
        try:
            container = client.containers.get(container_name)
            command = (
                f"curl -k -s -o /dev/null -w '%{{http_code}}' "
                f"-u 'admin:{admin_password}' "
                f"https://localhost:9200/_cluster/health?wait_for_status=yellow&timeout=5s"
            )
            exec_result = container.exec_run(command, user="opensearch")
            http_code = exec_result.output.decode('utf-8').strip()

            if http_code == "200":
                print(f"OpenSearch is healthy and ready after {attempt * delay} seconds.")
                return True
            elif http_code == "401":
                print(f"Attempt {attempt}/{max_attempts}: OpenSearch returned 401 (Unauthorized). Security plugin might be initializing. Retrying in {delay} seconds...")
            else:
                print(f"Attempt {attempt}/{max_attempts}: OpenSearch not ready (HTTP {http_code}). Retrying in {delay} seconds...")
        except docker.errors.NotFound:
            print(f"OpenSearch container '{container_name}' not found. Exiting wait.")
            return False
        except Exception as e:
            print(f"Attempt {attempt}/{max_attempts}: Error checking OpenSearch health: {e}. Retrying in {delay} seconds...")

        time.sleep(delay)
    print("OpenSearch did not become healthy within the allotted time. Check container logs for errors.")
    return False

def start_container(client: docker.DockerClient):
    """Starts the OpenSearch container and then the OpenSearch Dashboards container."""
    # Ensure no containers or networks with the same names exist
    stop_container(client)

    # Create a custom Docker network
    print(f"Creating Docker network '{DOCKER_NETWORK_NAME}'...")
    try:
        network = client.networks.create(DOCKER_NETWORK_NAME, driver="bridge")
        print(f"Network '{DOCKER_NETWORK_NAME}' created successfully.")
    except docker.errors.APIError as e:
        if "network with name" in str(e) and "already exists" in str(e):
            print(f"Network '{DOCKER_NETWORK_NAME}' already exists. Using existing network.")
            network = client.networks.get(DOCKER_NETWORK_NAME)
        else:
            print(f"Error creating network '{DOCKER_NETWORK_NAME}': {e}")
            sys.exit(1)

    # Pull OpenSearch image
    print(f"Pulling latest image: {IMAGE_NAME}...")
    try:
        client.images.pull(IMAGE_NAME)
    except docker.errors.APIError as e:
        print(f"Error pulling image '{IMAGE_NAME}': {e}")
        sys.exit(1)

    # Pull Dashboards image
    print(f"Pulling latest image: {DASHBOARDS_IMAGE_NAME}...")
    try:
        client.images.pull(DASHBOARDS_IMAGE_NAME)
    except docker.errors.APIError as e:
        print(f"Error pulling image '{DASHBOARDS_IMAGE_NAME}': {e}")
        sys.exit(1)

    print(f"Starting OpenSearch container '{CONTAINER_NAME}'...")
    environment = {
        "discovery.type": "single-node",
        "OPENSEARCH_INITIAL_ADMIN_PASSWORD": ADMIN_PASSWORD,
        "OPENSEARCH_JAVA_OPTS": f"-Xms{HEAP_SIZE} -Xmx{HEAP_SIZE}",
    }
    ports = {
        "9200/tcp": 9200,
        "9600/tcp": 9600
    }

    opensearch_container = None
    try:
        opensearch_container = client.containers.run(
            image=IMAGE_NAME,
            name=CONTAINER_NAME,
            environment=environment,
            ports=ports,
            detach=True,
            network=DOCKER_NETWORK_NAME
        )
    except docker.errors.APIError as e:
        print(f"Failed to start OpenSearch container '{CONTAINER_NAME}': {e}")
        sys.exit(1)

    print("OpenSearch container started successfully.")
    print("You can check the status with:")
    print(f"curl -k -u 'admin:{ADMIN_PASSWORD}' https://localhost:9200")

    # Wait for OpenSearch to be healthy, passing ADMIN_PASSWORD
    if not wait_for_opensearch(client, CONTAINER_NAME, ADMIN_PASSWORD):
        print("OpenSearch did not become healthy. Cannot proceed with plugin installation or Dashboards.")
        sys.exit(1)

    print(f"Installing 'analysis-icu' plugin in container '{CONTAINER_NAME}'...")
    try:
        exec_result = opensearch_container.exec_run("opensearch-plugin install --batch analysis-icu")
        print(f"Plugin install stdout:\n{exec_result.output.decode('utf-8')}")
        if exec_result.exit_code != 0:
            print(f"Plugin install stderr:\n{exec_result.output.decode('utf-8')}", file=sys.stderr)
            print(f"Error installing plugin. Exit code: {exec_result.exit_code}", file=sys.stderr)
        else:
            print("'analysis-icu' plugin installed successfully.")
            print("Restarting OpenSearch container for plugin changes to take effect...")
            opensearch_container.restart()
            # Wait again after restart, passing ADMIN_PASSWORD
            if not wait_for_opensearch(client, CONTAINER_NAME, ADMIN_PASSWORD):
                print("OpenSearch did not become healthy after plugin installation and restart. Cannot proceed with Dashboards.")
                sys.exit(1)

    except Exception as e:
        print(f"Error during plugin installation: {e}", file=sys.stderr)
        sys.exit(1)

    # --- Start OpenSearch Dashboards container ---
    print(f"\nStarting OpenSearch Dashboards container '{DASHBOARDS_CONTAINER_NAME}'...")
    dashboards_environment = {
        "OPENSEARCH_HOSTS": f'["https://{CONTAINER_NAME}:9200"]',
        "OPENSEARCH_USERNAME": "admin",
        "OPENSEARCH_PASSWORD": ADMIN_PASSWORD,
        "SERVER_BASEPATH": "",
        "SERVER_HOST": "0.0.0.0",
        "OPENSEARCH_SSL_VERIFICATION_MODE": "none" # Important for self-signed certificates
    }
    dashboards_ports = {
        "5601/tcp": 5601
    }

    try:
        dashboards_container = client.containers.run(
            image=DASHBOARDS_IMAGE_NAME,
            name=DASHBOARDS_CONTAINER_NAME,
            environment=dashboards_environment,
            ports=dashboards_ports,
            detach=True,
            network=DOCKER_NETWORK_NAME
        )
        print("OpenSearch Dashboards container started successfully.")
        print(f"OpenSearch Dashboards should be available at https://localhost:5601")
        print("It may take a moment for Dashboards to fully initialize and connect.")
        print("\nWaiting an additional 90 seconds for OpenSearch Dashboards to fully initialize and connect (can take longer with security enabled)...") # Increased wait
        time.sleep(90)
        print("Additional wait complete. Check OpenSearch Dashboards logs if issues persist.")

    except docker.errors.APIError as e:
        print(f"Failed to start OpenSearch Dashboards container '{DASHBOARDS_CONTAINER_NAME}': {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main function to parse arguments and call the appropriate function."""
    parser = argparse.ArgumentParser(
        description="A Python script to control a local OpenSearch Docker container using the Docker SDK.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--start", action="store_true", help="Starts the OpenSearch container.")
    group.add_argument("--stop", action="store_true", help="Stops and removes the OpenSearch container.")

    args = parser.parse_args()
    client = get_docker_client()

    if args.start:
        start_container(client)
    elif args.stop:
        stop_container(client)

if __name__ == "__main__":
    main()