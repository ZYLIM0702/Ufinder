#!/usr/bin/env sh
# Ufinder engine: one-command install, run by the NAS owner.
#
#   sh install.sh --sources /path/to/folders --users /path/to/user-homes
#
# What it does: checks the machine, fetches pinned model weights, starts the stack.
# What it never does: write to your source folders, or change them in any way.
set -eu
cd "$(dirname "$0")"

SOURCES=""
USERS_DIR="./data/exchange"
PORT="8787"
QWEN_REV="9f2f7e710d6d81056aa5c0a4f04764fec6bb7bda"

while [ $# -gt 0 ]; do
  case "$1" in
    --sources) SOURCES="$2"; shift 2 ;;
    --users) USERS_DIR="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    *) echo "unknown option: $1"; exit 2 ;;
  esac
done

say() { printf '%s\n' "ufinder: $1"; }
die() { printf '%s\n' "ufinder: $1" >&2; exit 1; }

[ -n "$SOURCES" ] || die "pass --sources with the folder that holds your data"
[ -d "$SOURCES" ] || die "no such folder: $SOURCES"
command -v docker >/dev/null || die "Docker is required. Install it from the UGOS App Center."
docker compose version >/dev/null 2>&1 || die "Docker Compose is required."

mem_kb=$(docker info --format '{{.MemTotal}}' 2>/dev/null || echo 0)
mem_gb=$((mem_kb / 1073741824))
[ "$mem_gb" -ge 12 ] || die "the local model needs about 9 GB of RAM. Docker has ${mem_gb} GB."
say "memory ok: ${mem_gb} GB"

if [ ! -f models/qwen3-vl-embedding-2b/model.safetensors ] || [ ! -f models/whisper/base/model.bin ]; then
  command -v hf >/dev/null || command -v uvx >/dev/null || die "install huggingface_hub to fetch the model weights, once"
  HF="hf"
  command -v hf >/dev/null || HF='uvx --from huggingface_hub[cli] hf'
  say "fetching pinned model weights, about 4.4 GB. This is the only download."
  $HF download Qwen/Qwen3-VL-Embedding-2B --revision "$QWEN_REV" --local-dir models/qwen3-vl-embedding-2b
  $HF download Systran/faster-whisper-base --local-dir models/whisper/base
fi

[ -f config/ufinder.json ] || die "edit config/ufinder.json first: list your folders, users and who may read what"
grep -q 'demo-pass' config/ufinder.json && say "warning: config/ufinder.json still has the sample passwords. Change them."

say "building and starting the stack"
UFINDER_SOURCE_ROOT="$SOURCES" UFINDER_EXCHANGE_ROOT="$USERS_DIR" UFINDER_PORT="$PORT" docker compose up -d --build

say "started. Containers restart on their own after a reboot."
say "open http://localhost:${PORT} and sign in. Search works now, and improves as indexing runs."
say "check health with: sh doctor.sh"
