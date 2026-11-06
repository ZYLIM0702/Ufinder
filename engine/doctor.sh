#!/usr/bin/env sh
# Ufinder health check. Reads state only and changes nothing.
#
#   sh doctor.sh
#
# Exit code 0 means every check passed.
set -u
cd "$(dirname "$0")"

fails=0
pass() { printf 'ok    %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; fails=$((fails + 1)); }

for service in edge gateway indexer embedder qdrant; do
  state=$(docker compose ps --format '{{.Service}} {{.State}}' 2>/dev/null | awk -v s="$service" '$1 == s {print $2}')
  [ "$state" = "running" ] && pass "$service is running" || fail "$service is ${state:-not running}"
done

published=$(docker compose ps --format '{{.Service}}={{.Ports}}' 2>/dev/null | grep -- '->' | cut -d= -f1 | tr '\n' ' ')
[ "$published" = "edge " ] && pass "only the edge forwarder publishes a port" || fail "published ports: ${published:-none}"

route=$(docker compose exec -T indexer python -c "
import socket
try:
    socket.create_connection(('1.1.1.1', 443), 3)
    print('open')
except Exception:
    print('closed')" 2>/dev/null)
[ "$route" = "closed" ] && pass "indexer has no route to the internet" || fail "indexer may reach the internet: ${route:-unknown}"

write=$(docker compose exec -T indexer python -c "
try:
    open('/sources/.ufinder-write-test', 'w')
    print('writable')
except OSError:
    print('read-only')" 2>/dev/null)
[ "$write" = "read-only" ] && pass "source folders are read-only" || fail "source folders are ${write:-unknown}"

docker compose exec -T gateway python - 2>/dev/null <<'EOF' || fail "index could not be read"
import json, sqlite3
c = sqlite3.connect("/data/ufinder.db")
files = c.execute("select count(*) from files where state='live'").fetchone()[0]
done = c.execute("select count(*) from blobs where status='done'").fetchone()[0]
waiting = c.execute("select count(*) from blobs where status in ('pending','working')").fetchone()[0]
failed = c.execute("select count(*) from blobs where status='failed'").fetchone()[0]
ghosts = c.execute("select count(*) from ghosts where resolved_file is null").fetchone()[0]
print(f"ok    index: {files} files, {done} processed, {waiting} waiting, {failed} failed, {ghosts} missing files")
EOF

[ "$fails" -eq 0 ] && printf '\nAll checks passed.\n' || printf '\n%s checks failed.\n' "$fails"
exit "$fails"
