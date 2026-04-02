#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_VENV_DIR="${ROOT_DIR}/.portable-build-venv"
WORKER_DIST_DIR="${ROOT_DIR}/worker/dist"
WORKER_BUILD_DIR="${ROOT_DIR}/worker/build"
WORKER_NAME="open-collar-worker"

is_windows_host() {
  case "$(uname -s)" in
    CYGWIN*|MINGW*|MSYS*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

if ! is_windows_host; then
  echo "Portable worker packaging is only supported on Windows hosts." >&2
  exit 1
fi

PYTHON_BIN="${OPEN_COLLAR_BUILD_PYTHON:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v py >/dev/null 2>&1; then
    PYTHON_BIN="py -3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "Python is required to package the worker executable." >&2
    exit 1
  fi
fi

echo "Creating portable build venv at ${BUILD_VENV_DIR}..."
rm -rf "${BUILD_VENV_DIR}" "${WORKER_DIST_DIR}" "${WORKER_BUILD_DIR}"
eval "${PYTHON_BIN} -m venv \"${BUILD_VENV_DIR}\""

PIP_EXE="${BUILD_VENV_DIR}/Scripts/pip.exe"
PYINSTALLER_EXE="${BUILD_VENV_DIR}/Scripts/pyinstaller.exe"

if [[ ! -f "${PIP_EXE}" ]]; then
  echo "Expected pip at ${PIP_EXE}, but it was not found." >&2
  exit 1
fi

echo "Installing worker build dependencies..."
"${PIP_EXE}" install -r "${ROOT_DIR}/worker/requirements-build.txt"

echo "Packaging Python worker executable..."
"${PYINSTALLER_EXE}" \
  --noconfirm \
  --clean \
  --onefile \
  --name "${WORKER_NAME}" \
  --distpath "${WORKER_DIST_DIR}" \
  --workpath "${WORKER_BUILD_DIR}" \
  --paths "${ROOT_DIR}/worker" \
  --collect-submodules open_collar \
  --collect-submodules pywinauto \
  --collect-submodules PIL \
  --collect-submodules playwright \
  "${ROOT_DIR}/worker/main.py"

echo "Packaged worker executable: ${WORKER_DIST_DIR}/${WORKER_NAME}.exe"
