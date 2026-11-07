#!/usr/bin/env bash
set -e

echo "======================================================================"
echo "Project Alpha - Sovereign AI Executive Operating System"
echo "Automated Android APK Build Pipeline (Linux / macOS)"
echo "======================================================================"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "[1/4] Verifying Flutter and Dart Toolchain..."
if ! command -v flutter &> /dev/null; then
    echo "[WARNING] 'flutter' executable not found on PATH."
    echo "Please install Flutter SDK (>=3.22.0) and Android Command-line Tools."
    exit 0
fi

echo "[2/4] Resolving dependencies (flutter pub get)..."
flutter pub get

echo "[3/4] Running code analysis and tests..."
flutter analyze --no-fatal-infos
flutter test test/unit/api_and_models_test.dart
flutter test test/unit/services_test.dart

echo "[4/4] Building Release APK..."
flutter build apk --release --split-per-abi

echo "======================================================================"
echo "[SUCCESS] Project Alpha Android APK successfully built!"
echo "Output: build/app/outputs/flutter-apk/"
echo "======================================================================"
