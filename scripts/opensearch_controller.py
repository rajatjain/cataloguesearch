import docker
import argparse
import sys
import os
import time

# =================================================================
# OpenSearch Docker Control Script (Using Docker SDK for Python)
#
# This script manages a local OpenSearch container for
# development and test.
# =================================================================

# Default Configuration
DEFAULTS = {
    "test": {
        "CONTAINER_NAME": "opensearch-cataloguesearch-test",
        "DASHBOARDS_CONTAINER_NAME": "opensearch-dashboards-cataloguesearch-test",
        "DOCKER_NETWORK_NAME": "opensearch-custom-network-test",
        "DATA_PATH": os.path.expanduser("~/cataloguesearch/opensearch-test"),
        "PORTS": {"9200/tcp": 19200, "9600/tcp": 19600},
        "DASHBOARDS_PORTS": {"5601/tcp": 15601}
    },
    "dev": {
        "CONTAINER_NAME": "opensearch-cataloguesearch",
        "DASHBOARDS_CONTAINER_NAME": "opensearch-dashboards-cataloguesearch",
        "DOCKER_NETWORK_NAME": "opensearch-custom-network",
        "DATA_PATH": os.path.expanduser("~/cataloguesearch/opensearch"),
        "PORTS": {"9200/tcp": 9200, "9600/tcp": 9600},
        "DASHBOARDS_PORTS": {"5601/tcp": 5601}
    }
}

IMAGE_NAME = "opensearchproject/opensearch:3.0.0"
DASHBOARDS_IMAGE_NAME = "opensearchproject/opensearch-dashboards:3.0.0"
ADMIN_PASSWORD = "Admin@Password123!"
HEAP_SIZE = "512m"

def get_docker_client():
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

def stop_container(client: docker.DockerClient, config):
    containers_to_stop = [config["CONTAINER_NAME"], config["DASHBOARDS_CONTAINER_NAME"]]
    for name in containers_to_stop:
        try:
            container = client.containers.get(name)
            print(f"Stopping container '{name}'...")
            container.stop(timeout=10)
            print(f"Removing container '{name}'...")
            container.remove()
            print(f"Container '{name}' stopped and removed successfully.")
        except docker.errors.NotFound:
            print(f"Container '{name}' not found. Nothing to do.")
        except docker.errors.APIError as e:
            print(f"An API error occurred with container '{name}': {e}")

    try:
        network = client.networks.get(config["DOCKER_NETWORK_NAME"])
        print(f"Removing network '{config['DOCKER_NETWORK_NAME']}'...")
        network.remove()
        print(f"Network '{config['DOCKER_NETWORK_NAME']}' removed successfully.")
    except docker.errors.NotFound:
        print(f"Network '{config['DOCKER_NETWORK_NAME']}' not found. Nothing to do.")
    except docker.errors.APIError as e:
        print(f"An API error occurred while removing network '{config['DOCKER_NETWORK_NAME']}': {e}")


def wait_for_opensearch(client: docker.DockerClient, container_name: str, admin_password: str, port: int, max_attempts=40, delay=5):
    print(f"Waiting for OpenSearch container '{container_name}' to be healthy...")
    for attempt in range(1, max_attempts + 1):
        try:
            container = client.containers.get(container_name)

            # This is running within the docker container. Hence use the default 9200 port.
            command = (
                f"curl -k -s -o /dev/null -w '%{{http_code}}' "
                f"-u 'admin:{admin_password}' "
                f"https://localhost:9200/_cluster/health?wait_for_status=yellow&timeout=5s"
            )
            print(f"Command: {command}")
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

def start_container(client: docker.DockerClient, config):
    stop_container(client, config)
    print(f"Creating Docker network '{config['DOCKER_NETWORK_NAME']}'...")
    try:
        network = client.networks.create(config["DOCKER_NETWORK_NAME"], driver="bridge")
        print(f"Network '{config['DOCKER_NETWORK_NAME']}' created successfully.")
    except docker.errors.APIError as e:
        if "network with name" in str(e) and "already exists" in str(e):
            print(f"Network '{config['DOCKER_NETWORK_NAME']}' already exists. Using existing network.")
            network = client.networks.get(config["DOCKER_NETWORK_NAME"])
        else:
            print(f"Error creating network '{config['DOCKER_NETWORK_NAME']}': {e}")
            sys.exit(1)

    print(f"Pulling latest image: {IMAGE_NAME}...")
    try:
        client.images.pull(IMAGE_NAME)
    except docker.errors.APIError as e:
        print(f"Error pulling image '{IMAGE_NAME}': {e}")
        sys.exit(1)

    print(f"Pulling latest image: {DASHBOARDS_IMAGE_NAME}...")
    try:
        client.images.pull(DASHBOARDS_IMAGE_NAME)
    except docker.errors.APIError as e:
        print(f"Error pulling image '{DASHBOARDS_IMAGE_NAME}': {e}")
        sys.exit(1)

    print(f"Starting OpenSearch container '{config['CONTAINER_NAME']}'...")
    environment = {
        "discovery.type": "single-node",
        "OPENSEARCH_INITIAL_ADMIN_PASSWORD": ADMIN_PASSWORD,
        "OPENSEARCH_JAVA_OPTS": f"-Xms{HEAP_SIZE} -Xmx{HEAP_SIZE}",
    }
    opensearch_container = None

    # Create host directory for persistent data and mount it as a volume.
    data_path = config["DATA_PATH"]
    print(f"Ensuring host data directory exists for persistence: {data_path}")
    os.makedirs(data_path, exist_ok=True)

    try:
        opensearch_container = client.containers.run(
            image=IMAGE_NAME,
            name=config["CONTAINER_NAME"],
            environment=environment,
            ports=config["PORTS"],
            detach=True,
            network=config["DOCKER_NETWORK_NAME"],
            volumes=[f'{data_path}:/usr/share/opensearch/data']
        )
    except docker.errors.APIError as e:
        print(f"Failed to start OpenSearch container '{config['CONTAINER_NAME']}': {e}")
        sys.exit(1)

    print("OpenSearch container started successfully.")
    print("You can check the status with:")
    for host_port in config["PORTS"].values():
        print(f"curl -k -u 'admin:{ADMIN_PASSWORD}' https://localhost:{host_port}")

    if not wait_for_opensearch(client, config["CONTAINER_NAME"], ADMIN_PASSWORD, list(config["PORTS"].values())[0]):
        print("OpenSearch did not become healthy. Cannot proceed with plugin installation or Dashboards.")
        sys.exit(1)

    print(f"Installing plugins in container '{config['CONTAINER_NAME']}'...")
    try:
        # Install analysis-icu for multilingual support
        print("--> Installing 'analysis-icu' plugin...")
        exec_result_icu = opensearch_container.exec_run("opensearch-plugin install --batch analysis-icu")
        if exec_result_icu.exit_code != 0:
            print(f"Error installing 'analysis-icu':\n{exec_result_icu.output.decode('utf-8')}", file=sys.stderr)
            sys.exit(1)
        else:
            print("'analysis-icu' plugin installed successfully.")

        # Install repository-gcs for GCS snapshots
        print("--> Installing 'repository-gcs' plugin...")
        exec_result_gcs = opensearch_container.exec_run("opensearch-plugin install --batch repository-gcs")
        if exec_result_gcs.exit_code != 0:
            print(f"Error installing 'repository-gcs':\n{exec_result_gcs.output.decode('utf-8')}", file=sys.stderr)
            sys.exit(1)
        else:
            print("'repository-gcs' plugin installed successfully.")

        print("Restarting OpenSearch container for all plugin changes to take effect...")
        opensearch_container.restart()
        if not wait_for_opensearch(client, config["CONTAINER_NAME"], ADMIN_PASSWORD, list(config["PORTS"].values())[0]):
            print("OpenSearch did not become healthy after plugin installation and restart. Cannot proceed with Dashboards.")
            sys.exit(1)
    except Exception as e:
        print(f"Error during plugin installation: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\nStarting OpenSearch Dashboards container '{config['DASHBOARDS_CONTAINER_NAME']}'...")
    dashboards_environment = {
        "OPENSEARCH_HOSTS": f'["https://{config["CONTAINER_NAME"]}:9200"]',
        "OPENSEARCH_USERNAME": "admin",
        "OPENSEARCH_PASSWORD": ADMIN_PASSWORD,
        "SERVER_BASEPATH": "",
        "SERVER_HOST": "0.0.0.0",
        "OPENSEARCH_SSL_VERIFICATION_MODE": "none"
    }

    try:
        dashboards_container = client.containers.run(
            image=DASHBOARDS_IMAGE_NAME,
            name=config["DASHBOARDS_CONTAINER_NAME"],
            environment=dashboards_environment,
            ports=config["DASHBOARDS_PORTS"],
            detach=True,
            network=config["DOCKER_NETWORK_NAME"]
        )
        print("OpenSearch Dashboards container started successfully.")
        for host_port in config["DASHBOARDS_PORTS"].values():
            print(f"OpenSearch Dashboards should be available at https://localhost:{host_port}")
        print("It may take a moment for Dashboards to fully initialize and connect.")
        print("\nWaiting an additional 90 seconds for OpenSearch Dashboards to fully initialize and connect (can take longer with security enabled)...")
        time.sleep(90)
        print("Additional wait complete. Check OpenSearch Dashboards logs if issues persist.")
    except docker.errors.APIError as e:
        print(f"Failed to start OpenSearch Dashboards container '{config['DASHBOARDS_CONTAINER_NAME']}': {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="A Python script to control a local OpenSearch Docker container using the Docker SDK.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--start", action="store_true", help="Starts the OpenSearch container.")
    group.add_argument("--stop", action="store_true", help="Stops and removes the OpenSearch container.")

    test_group = parser.add_mutually_exclusive_group()
    test_group.add_argument("--test", dest="test", action="store_true", help="Use test containers (default).")
    test_group.add_argument("--dev", dest="test", action="store_false", help="Use dev containers.")
    parser.set_defaults(test=True)

    args = parser.parse_args()
    config = DEFAULTS["test"] if args.test else DEFAULTS["dev"]
    client = get_docker_client()

    if args.start:
        start_container(client, config)
    elif args.stop:
        stop_container(client, config)

if __name__ == "__main__":
    main()
