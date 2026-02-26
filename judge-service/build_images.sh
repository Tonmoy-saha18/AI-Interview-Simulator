#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LANGS_DIR="$SCRIPT_DIR/languages"

echo "=== Building InterviewIQ language runner images ==="

docker build -t interviewiq-python:3.11   "$LANGS_DIR/python"
docker build -t interviewiq-node:20       "$LANGS_DIR/javascript"
docker build -t interviewiq-java:21       "$LANGS_DIR/java"
docker build -t interviewiq-cpp:latest    "$LANGS_DIR/cpp"
docker build -t interviewiq-go:1.22       "$LANGS_DIR/go"

echo "=== All language images built successfully ==="
docker images | grep interviewiq
