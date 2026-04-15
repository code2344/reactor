#!/bin/zsh
set -euo pipefail

# ---- config ----
# Put your real token here (starts with pypi-...)
PYPI_TOKEN="pypi-AgEIcHlwaS5vcmcCJGMzMThjZWMzLTRlN2UtNGQxYS1iYzI2LTQ4OTg1YzIyZWZmOQACKlszLCIyZTViMzgxMS01ZmEzLTQ5MWYtYjE2NS1jODE3ZThkNDU3NjUiXQAABiC57yQWoGptcdzQkvucjuFVh5DwoamWPKuEG2pRSzGXpA"
# Set to "https://test.pypi.org/legacy/" for TestPyPI
TWINE_REPOSITORY_URL="https://upload.pypi.org/legacy/"
# Match your runtime target to avoid macOS binary mismatch
export MACOSX_DEPLOYMENT_TARGET="16.0"
# Version bump part: patch, minor, or major
BUMP_PART="${BUMP_PART:-patch}"
# ----------------

cd "$(dirname "$0")"

if [[ "$PYPI_TOKEN" == "pypi-REPLACE_ME" ]]; then
  echo "ERROR: set PYPI_TOKEN in build.sh"
  exit 1
fi

echo "Cleaning old build artifacts..."
rm -rf dist/

echo "Bumping version in pyproject.toml ($BUMP_PART)..."
NEW_VERSION=$(BUMP_PART="$BUMP_PART" python3 - <<'PY'
from pathlib import Path
import os
import re

pyproject_path = Path("pyproject.toml")
text = pyproject_path.read_text(encoding="utf-8")

in_project = False
current_version = None

lines = text.splitlines()
for i, line in enumerate(lines):
  stripped = line.strip()
  if stripped.startswith("[") and stripped.endswith("]"):
    in_project = stripped == "[project]"
    continue
  if in_project:
    match = re.match(r'\s*version\s*=\s*"(\d+)\.(\d+)\.(\d+)"\s*$', line)
    if match:
      major, minor, patch = map(int, match.groups())
      part = os.environ.get("BUMP_PART", "patch")
      if part == "major":
        major += 1
        minor = 0
        patch = 0
      elif part == "minor":
        minor += 1
        patch = 0
      else:
        patch += 1
      current_version = f"{major}.{minor}.{patch}"
      lines[i] = f'version = "{current_version}"'
      break

if current_version is None:
  raise SystemExit("Could not find [project] version in pyproject.toml")

pyproject_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(current_version)
PY
)
echo "New version: ${NEW_VERSION}"

echo "Installing build tools..."
python3 -m pip install --upgrade build twine

echo "Building package..."
python3 -m build

echo "Checking distributions..."
python3 -m twine check dist/*

echo "Uploading to PyPI..."
TWINE_USERNAME="__token__" \
TWINE_PASSWORD="$PYPI_TOKEN" \
python3 -m twine upload \
  --non-interactive \
  --repository-url "$TWINE_REPOSITORY_URL" \
  dist/*

echo "Done."