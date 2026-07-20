# Custom OpenHands agent-server sandbox image with Bilun dependencies baked in.
#
# Why this exists: the base image ghcr.io/openhands/agent-server:1.36.0-python ships with
# only Python 3.13 — no polars/pandas/duckdb/xlrd/etc. Every agent run paid a 5-15 min
# `pip install` tax with no wheel cache, and often timed out before finishing. This image
# layers Bilun's requirements.txt on top so sandboxes spawn ready to run checkers.
#
# Build:
#   docker build -t bilun/agent-server:1.36.0-bilun -f scripts/agent/sandbox/Dockerfile .
#
# Use (set on the openhands-app container):
#   -e AGENT_SERVER_IMAGE_REPOSITORY=bilun/agent-server
#   -e AGENT_SERVER_IMAGE_TAG=1.36.0-bilun
#
# Rebuild when requirements.txt changes:
#   docker build -t bilun/agent-server:1.36.0-bilun -f scripts/agent/sandbox/Dockerfile .
#
# Tag bumps: when OpenHands upgrades (e.g. agent-server:1.37.0), update FROM below + the
# tag, rebuild, restart openhands-app with the new env vars.

FROM ghcr.io/openhands/agent-server:1.36.0-python

# Bilun requirements. Copy just the file first to maximize Docker layer caching —
# requirements.txt changes rarely, so this layer is reused on rebuilds.
COPY requirements.txt /tmp/bilun-requirements.txt

# Install as the openhands user (the image's default non-root user, uid 10001).
# --no-cache-dir keeps the image smaller; wheels are baked in, no cache needed at runtime.
# Note: we intentionally do NOT install the bilun package itself (no `pip install -e .`)
# because the repo is mounted read-only at /workspace/bilun at runtime and the agents
# import it via sys.path, not via an installed package. This avoids version drift between
# the baked-in package and the mounted source.
#
# We do NOT `rm /tmp/bilun-requirements.txt` after install — COPY places the file as root,
# the openhands user (uid 10001) can't delete it ("Operation not permitted"), and the file
# is harmless left in the image (8KB, never read at runtime).
RUN pip install --no-cache-dir -r /tmp/bilun-requirements.txt

# mem0 + local HF embedder for agent memory (plans/tooling/mem0-integration-design.md).
# CPU-ONLY torch (the +CPU variant) — skips the ~1.5GB of CUDA/nvidia wheels that the
# default torch pulls. The laptop sandbox has no GPU, so GPU torch is pure waste.
# Pin torch first from the CPU index, then mem0ai + sentence-transformers (which depend
# on torch but don't care which variant). bge-small-en (~130MB) downloads on first mem0
# use, cached thereafter in the Qdrant data dir.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir mem0ai sentence-transformers

# Sanity check: confirm the key imports resolve (fail the build early if not).
RUN python -c "import polars, pandas, duckdb, xlrd, openpyxl, pyarrow, fastapi, yaml; print('bilun deps OK')" \
    && python -c "import mem0, sentence_transformers; print('mem0 + sentence-transformers OK')"

# Image is ready. No CMD/ENTRYPOINT override — the base image's entrypoint runs the
# agent-server, and OpenHands spawns it with the right args.
