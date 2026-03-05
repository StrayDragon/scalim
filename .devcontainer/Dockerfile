FROM mcr.microsoft.com/devcontainers/python:3.10-trixie

ARG SCALIM_APT_DEBIAN_MIRROR="https://mirrors.tuna.tsinghua.edu.cn/debian"
ARG SCALIM_PYPI_INDEX_URL="https://mirrors.aliyun.com/pypi/simple/"

# Copy and run APT mirror configuration script
COPY .devcontainer/scripts/rewrite-apt-sources.py /tmp/rewrite-apt-sources.py
RUN python3 /tmp/rewrite-apt-sources.py \
    && rm /tmp/rewrite-apt-sources.py

# Minimal system deps for common Python wheels + optional source builds.
# Note: just is available in Debian 13 (trixie), no need to download from GitHub
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    ca-certificates \
    curl \
    just \
    && rm -rf /var/lib/apt/lists/*

# Tooling used by this repo (see `README.md` / `justfile`).
# Install uv, ruff, basedpyright via pipx to global location so all users can access
ARG SCALIM_PYPI_INDEX_URL
ENV PIPX_HOME=/usr/local/pipx
ENV PIPX_BIN_DIR=/usr/local/bin
RUN mkdir -p ${PIPX_HOME} ${PIPX_BIN_DIR} && \
    PIP_INDEX_URL="${SCALIM_PYPI_INDEX_URL}" pipx install uv && \
    pipx install --pip-args="--index-url=${SCALIM_PYPI_INDEX_URL}" ruff && \
    pipx install --pip-args="--index-url=${SCALIM_PYPI_INDEX_URL}" basedpyright

# Create uv cache directory with vscode user ownership (for uv cache volume mount)
# The vscode user (UID 1000) is created by the base image
RUN mkdir -p /home/vscode/.cache/uv && chown -R 1000:1000 /home/vscode/.cache
