# Dify Air-Gapped Edition

This branch turns the self-hosted Dify stack into an air-gapped runtime and
bundles the official `langgenius/openai_api_compatible` plugin (version
`0.0.66`) as the default plugin for newly created tenants.

## Disabled by default

The Docker environment disables Marketplace access, update checks, GitHub
plugin installation, Creators Platform integration, web crawlers, Next.js and
Weaviate telemetry, sandbox network access, plugin remote debugging, and PyPI
mirror probing. Local `.difypkg` installation remains available. `FORCE_VERIFYING_SIGNATURE=false` is used because the bundled official plugin is rebuilt from pinned source rather than distributed as an officially signed Marketplace package; only install packages you trust in this mode.

The runtime flag is `OFFLINE_MODE=true`. GitHub plugin API endpoints reject
requests while this flag is enabled.

## Build on a connected staging machine

The final deployment host does not need Internet access, but the images must be
built once where Docker registries and package registries are reachable:

```bash
cd docker
cp .env.example .env
docker compose build api web plugin_daemon
docker compose pull --ignore-buildable
```

The plugin-daemon image resolves the pinned plugin `uv.lock` during this
connected build and embeds the resulting uv cache. At runtime `UV_OFFLINE=1`
and `PIP_EXTRA_ARGS=--offline` prevent dependency resolution from using PyPI.

Export every image used by the resolved Compose configuration:

```bash
docker compose config --images | sort -u > offline-images.txt
docker save -o dify-offline-images.tar $(cat offline-images.txt)
```

Transfer the repository, `.env`, and `dify-offline-images.tar` to the
air-gapped host.

## Start on the air-gapped host

```bash
docker load -i dify-offline-images.tar
cd docker
docker compose up -d
```

The first workspace/tenant created after startup queues installation of the
bundled `langgenius/openai_api_compatible` package. Configure that provider
with the URL of an OpenAI-compatible model server reachable from the Dify
network (for example a local vLLM, llama.cpp, or LM Studio endpoint).

Existing tenants are not silently mutated during an upgrade. They can install
the same bundled package through the local-package installation path.
