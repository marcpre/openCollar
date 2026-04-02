#!/usr/bin/env bash
set -euo pipefail

TARGET_ROOT="${1:-/media/sf_DEL_ME}"
APP_NAME="open-collar"
DEPLOY_ROOT="${TARGET_ROOT}/${APP_NAME}-deploy"
RELEASES_DIR="${DEPLOY_ROOT}/releases"
CURRENT_DIR="${DEPLOY_ROOT}/current"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
RELEASE_DIR="${RELEASES_DIR}/${TIMESTAMP}"
BUILD_WINDOWS_EXE="${BUILD_WINDOWS_EXE:-1}"
SKIP_FRONTEND_TESTS="${SKIP_FRONTEND_TESTS:-0}"
WORKER_EXE_NAME="open-collar-worker.exe"
APP_EXE_NAME="open-collar.exe"

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

require_command() {
  local command_name="$1"
  local message="$2"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "${message}" >&2
    exit 1
  fi
}

copy_source_handoff() {
  local destination="$1"
  mkdir -p "${destination}/docs"
  rsync -a README.md "${destination}/README.md"
  rsync -a docs/ "${destination}/docs/"
  rsync -a scripts/ "${destination}/scripts/"
  cat > "${destination}/DEPLOYMENT_MANIFEST.txt" <<EOF
open collar deployment bundle

created_at=${TIMESTAMP}
mode=source-only
target_root=${TARGET_ROOT}
release_dir=${destination}

notes:
- portable Windows build not produced
- run on Windows with BUILD_WINDOWS_EXE=1 to create a testable portable app
EOF
}

copy_portable_bundle() {
  local destination="$1"
  local app_exe_path="$2"
  local worker_exe_path="$3"

  mkdir -p "${destination}/worker" "${destination}/logs" "${destination}/data" "${destination}/docs"
  cp "${app_exe_path}" "${destination}/${APP_EXE_NAME}"
  cp "${worker_exe_path}" "${destination}/worker/${WORKER_EXE_NAME}"
  rsync -a README.md "${destination}/README.md"
  rsync -a docs/ "${destination}/docs/"
  rsync -a dist/ "${destination}/dist/"

  cat > "${destination}/RUN_OPEN_COLLAR.bat" <<'EOF'
@echo off
setlocal
set "ROOT_DIR=%~dp0"
set "OPEN_COLLAR_WORKER_EXECUTABLE=%ROOT_DIR%worker\open-collar-worker.exe"
set "OPEN_COLLAR_LOG_DIR=%ROOT_DIR%logs"
set "OPEN_COLLAR_APP_DATA_DIR=%ROOT_DIR%data"

if not exist "%ROOT_DIR%open-collar.exe" (
  echo Missing executable: %ROOT_DIR%open-collar.exe
  pause
  exit /b 1
)

if not exist "%OPEN_COLLAR_WORKER_EXECUTABLE%" (
  echo Missing worker executable: %OPEN_COLLAR_WORKER_EXECUTABLE%
  pause
  exit /b 1
)

if not exist "%OPEN_COLLAR_LOG_DIR%" mkdir "%OPEN_COLLAR_LOG_DIR%"
if not exist "%OPEN_COLLAR_APP_DATA_DIR%" mkdir "%OPEN_COLLAR_APP_DATA_DIR%"

echo Launching open collar...
echo Logs: %OPEN_COLLAR_LOG_DIR%\open-collar.log
"%ROOT_DIR%open-collar.exe"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo open collar exited with code %EXIT_CODE%.
  echo Check logs at %OPEN_COLLAR_LOG_DIR%\open-collar.log
  pause
  exit /b %EXIT_CODE%
)
EOF

  cat > "${destination}/DEPLOYMENT_MANIFEST.txt" <<EOF
open collar deployment bundle

created_at=${TIMESTAMP}
mode=portable
target_root=${TARGET_ROOT}
release_dir=${destination}
app_exe=${destination}/${APP_EXE_NAME}
worker_exe=${destination}/worker/${WORKER_EXE_NAME}
log_dir=${destination}/logs
data_dir=${destination}/data

notes:
- launch with RUN_OPEN_COLLAR.bat for attached startup diagnostics
- the portable build is intended for Windows testing from the shared folder
EOF
}

if [[ ! -d "${TARGET_ROOT}" ]]; then
  echo "Target directory does not exist: ${TARGET_ROOT}" >&2
  exit 1
fi

require_command rsync "rsync is required for deployment."

mkdir -p "${RELEASES_DIR}" "${CURRENT_DIR}"
rm -rf "${RELEASE_DIR}"
mkdir -p "${RELEASE_DIR}"

if [[ "${BUILD_WINDOWS_EXE}" == "0" ]]; then
  echo "Creating explicit source-only handoff bundle..."
  copy_source_handoff "${RELEASE_DIR}"
  rsync -a --delete "${RELEASE_DIR}/" "${CURRENT_DIR}/"
  echo "Source-only handoff staged at ${CURRENT_DIR}"
  exit 0
fi

if ! is_windows_host; then
  echo "Portable Windows build requires running this script on Windows." >&2
  echo "Use BUILD_WINDOWS_EXE=0 only if you intentionally want a source-only handoff." >&2
  exit 1
fi

require_command npm "npm is required for deployment."
require_command cargo "cargo is required to build the portable Windows app."

if [[ "${SKIP_FRONTEND_TESTS}" != "1" ]]; then
  echo "Running frontend tests before packaging..."
  npm test
fi

echo "Building frontend bundle..."
npm run build

echo "Packaging portable worker executable..."
bash scripts/build_worker_portable.sh

echo "Building Tauri release executable..."
npm run tauri:build

APP_EXE_SOURCE=""
if [[ -f "src-tauri/target/release/${APP_EXE_NAME}" ]]; then
  APP_EXE_SOURCE="src-tauri/target/release/${APP_EXE_NAME}"
elif [[ -f "target/release/${APP_EXE_NAME}" ]]; then
  APP_EXE_SOURCE="target/release/${APP_EXE_NAME}"
else
  echo "Tauri build completed, but ${APP_EXE_NAME} was not found." >&2
  exit 1
fi

WORKER_EXE_SOURCE="worker/dist/${WORKER_EXE_NAME}"
if [[ ! -f "${WORKER_EXE_SOURCE}" ]]; then
  echo "Worker packaging completed, but ${WORKER_EXE_SOURCE} was not found." >&2
  exit 1
fi

copy_portable_bundle "${RELEASE_DIR}" "${APP_EXE_SOURCE}" "${WORKER_EXE_SOURCE}"

echo "Refreshing current deployment snapshot..."
rsync -a --delete "${RELEASE_DIR}/" "${CURRENT_DIR}/"

echo
echo "Portable deployment staged successfully."
echo "Release: ${RELEASE_DIR}"
echo "Current: ${CURRENT_DIR}"
echo "Launcher: ${CURRENT_DIR}/RUN_OPEN_COLLAR.bat"
