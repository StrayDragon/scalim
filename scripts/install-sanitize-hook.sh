#!/usr/bin/env bash
# Install pre-commit hook: check sanitize leaks before each commit.
# Usage: bash scripts/install-sanitize-hook.sh
set -euo pipefail

hook="$(git rev-parse --show-toplevel)/.git/hooks/pre-commit"

cat > "$hook" << 'HOOK'
#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
echo "🔍 [pre-commit] Checking staged changes for sanitize leaks..."
python scripts/check-staged-sanitize.py
rc=$?
if [ "$rc" -ne 0 ]; then
    echo "❌ Commit blocked: sanitize leaks detected. Fix them or use 'git commit --no-verify' to bypass."
    exit "$rc"
fi
HOOK

chmod +x "$hook"
echo "✅ Pre-commit hook installed at $hook"
