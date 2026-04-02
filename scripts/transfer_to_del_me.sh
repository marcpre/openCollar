#!/usr/bin/env bash
set -euo pipefail

TARGET_ROOT="${1:-/media/sf_DEL_ME}"
APP_NAME="open-collar"
TRANSFER_ROOT="${TARGET_ROOT}/${APP_NAME}-transfer"
RELEASES_DIR="${TRANSFER_ROOT}/releases"
CURRENT_DIR="${TRANSFER_ROOT}/current"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
RELEASE_DIR="${RELEASES_DIR}/${TIMESTAMP}"

require_command() {
  local command_name="$1"
  local message="$2"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "${message}" >&2
    exit 1
  fi
}

if [[ ! -d "${TARGET_ROOT}" ]]; then
  echo "Target directory does not exist: ${TARGET_ROOT}" >&2
  exit 1
fi

require_command rsync "rsync is required to transfer the project."

mkdir -p "${RELEASES_DIR}" "${CURRENT_DIR}"
rm -rf "${RELEASE_DIR}"
mkdir -p "${RELEASE_DIR}"

echo "Copying open collar source tree into ${RELEASE_DIR}..."
rsync -a \
  --delete \
  --exclude ".git/" \
  --exclude "node_modules/" \
  --exclude ".venv/" \
  --exclude ".portable-build-venv/" \
  --exclude ".pytest_cache/" \
  --exclude ".tmp-artifacts/" \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  --exclude "dist/" \
  --exclude "build/" \
  --exclude "target/" \
  --exclude "src-tauri/target/" \
  ./ "${RELEASE_DIR}/"

cat > "${RELEASE_DIR}/TRANSFER_MANIFEST.txt" <<EOF
open collar transfer bundle

created_at=${TIMESTAMP}
target_root=${TARGET_ROOT}
release_dir=${RELEASE_DIR}
mode=source-transfer

notes:
- this is a source handoff for running or building on Windows
- see docs/WINDOWS_RUN.md after opening the project on Windows
EOF

echo "Refreshing current transfer snapshot..."
rsync -a --delete "${RELEASE_DIR}/" "${CURRENT_DIR}/"

echo
echo "Transfer completed successfully."
echo "Release: ${RELEASE_DIR}"
echo "Current: ${CURRENT_DIR}"
echo "Windows guide: ${CURRENT_DIR}/docs/WINDOWS_RUN.md"
