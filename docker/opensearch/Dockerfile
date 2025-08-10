FROM opensearchproject/opensearch:3.0.0

# Install required plugins
RUN /usr/share/opensearch/bin/opensearch-plugin install --batch analysis-icu && \
    /usr/share/opensearch/bin/opensearch-plugin install --batch repository-gcs

# Install jq for JSON parsing
USER root
RUN yum install -y jq && \
    yum clean all

# Copy custom scripts
COPY --chown=opensearch:opensearch docker/opensearch/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY --chown=opensearch:opensearch docker/opensearch/restore-snapshot.sh /usr/local/bin/restore-snapshot.sh

# Make scripts executable
RUN chmod +x /usr/local/bin/entrypoint.sh && \
    chmod +x /usr/local/bin/restore-snapshot.sh

USER opensearch

# Use custom entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
