#!/usr/bin/env sh
# Remove Ufinder. Your source files are never touched.
#
#   sh uninstall.sh            stop the stack, keep the index
#   sh uninstall.sh --purge    also delete the index, thumbnails and vectors
#   sh uninstall.sh --purge --models    also delete the model weights
set -eu
cd "$(dirname "$0")"

PURGE=0
MODELS=0
for arg in "$@"; do
  case "$arg" in
    --purge) PURGE=1 ;;
    --models) MODELS=1 ;;
    *) echo "unknown option: $arg"; exit 2 ;;
  esac
done

if [ "$PURGE" -eq 1 ]; then
  docker compose down -v
  echo "ufinder: stack stopped. Index, thumbnails and vectors deleted."
else
  docker compose down
  echo "ufinder: stack stopped. The index is kept, so a restart reads nothing again."
fi

if [ "$MODELS" -eq 1 ]; then
  rm -rf models/qwen3-vl-embedding-2b models/whisper
  echo "ufinder: model weights deleted."
fi

echo "ufinder: your source files were not touched."
