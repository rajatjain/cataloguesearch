# Use the exact same version of the official OpenSearch image as your local controller for consistency
FROM opensearchproject/opensearch:3.0.0

# Install the GCS repository plugin required for snapshot/restore
RUN /usr/share/opensearch/bin/opensearch-plugin install repository-gcs --batch

# Copy the custom entrypoint script into the container
COPY docker/opensearch_entrypoint.sh /usr/local/bin/entrypoint.sh

# Make the script executable
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the custom script as the entrypoint for the container
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]