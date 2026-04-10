#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="$PROJECT_ROOT/src/main/java"
BUILD_DIR="$PROJECT_ROOT/build/classes"
DIST_DIR="$PROJECT_ROOT/dist"
JAR_NAME="neighborsig-match.jar"

mkdir -p "$BUILD_DIR" "$DIST_DIR"
find "$BUILD_DIR" -type f -delete

HADOOP_CP="$(hadoop classpath)"
JAVA_SOURCES=$(find "$SRC_DIR" -name '*.java')

javac -Xlint:unchecked -cp "$HADOOP_CP" -d "$BUILD_DIR" $JAVA_SOURCES
jar -cvf "$DIST_DIR/$JAR_NAME" -C "$BUILD_DIR" . >/dev/null

echo "Built $DIST_DIR/$JAR_NAME"
