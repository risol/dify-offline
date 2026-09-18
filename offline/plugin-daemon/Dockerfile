FROM langgenius/dify-plugin-daemon:0.6.10-local

USER root

COPY offline/plugins/openai_api_compatible /opt/offline-plugins/openai_api_compatible
ENV UV_CACHE_DIR=/opt/offline-uv-cache

# Resolve and cache every Python artifact while the image is built. Runtime is
# forced offline, so an air-gapped host never needs PyPI for the bundled plugin.
RUN mkdir -p "$UV_CACHE_DIR" \
    && cd /opt/offline-plugins/openai_api_compatible \
    && /usr/local/bin/uv sync --frozen --no-dev \
    && rm -rf /opt/offline-plugins/openai_api_compatible/.venv

COPY offline/plugin-daemon/entrypoint.sh /offline-entrypoint.sh
RUN chmod 0755 /offline-entrypoint.sh

ENV UV_OFFLINE=1
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/offline-entrypoint.sh"]
CMD ["/bin/bash", "-c", "/app/commandline migrate && exec /app/main"]
