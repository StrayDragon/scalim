#!/usr/bin/env bash
set -euo pipefail

echo "[devcontainer] fix volume permissions (.venv and uv cache)"
sudo chown -R vscode:vscode "${PWD}/.venv" 2>/dev/null || true
sudo chown -R vscode:vscode /home/vscode/.cache/uv 2>/dev/null || true

echo "[devcontainer] tool versions"
python --version
uv --version
just --version
node --version
corepack --version

echo "[devcontainer] configure npm/pnpm registry (China mainland mirror)"
echo "  - npm registry (from env): $npm_config_registry"

echo "[devcontainer] install pnpm via npm"
# Install pnpm via npm (corepack has permission issues in some environments)
npm install -g pnpm
pnpm config set registry "https://registry.npmmirror.com"
pnpm --version
echo "  - pnpm registry: $(pnpm config get registry)"

echo "[devcontainer] install python deps (uv.lock)"
uv --preview-features extra-build-dependencies sync --dev --frozen

echo "[devcontainer] done"
