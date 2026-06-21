#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# test-stop.sh – Wechsel von rigbridge-test → rigbridge (Produktion)
#
# Was dieses Skript tut:
#   1. Stoppt und entfernt den rigbridge-test-Container + Image (optional)
#   2. Startet den rigbridge-Container wieder
#
# Verwendung:
#   ./docker/test-stop.sh
#   ./docker/test-stop.sh --keep-image   → Test-Image nicht löschen
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROD_CONTAINER="rigbridge"
TEST_CONTAINER="rigbridge-test"
KEEP_IMAGE=false

for arg in "$@"; do
    case "$arg" in
        --keep-image) KEEP_IMAGE=true ;;
    esac
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  RigBridge Test-Modus beenden"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd "$REPO_DIR"

# ── 1. Test-Container stoppen und entfernen ─────────────────────────────────
if docker ps -aq --filter name="^${TEST_CONTAINER}$" | grep -q .; then
    echo "▶ Stoppe und entferne $TEST_CONTAINER ..."
    docker compose -f docker-compose.test.yml down --remove-orphans
    echo "  ✓ $TEST_CONTAINER entfernt"
else
    echo "  ℹ $TEST_CONTAINER existiert nicht – nichts zu stoppen"
fi

# ── 2. Test-Image optional entfernen ────────────────────────────────────────
if [ "$KEEP_IMAGE" = false ]; then
    if docker image inspect rigbridge:test &>/dev/null; then
        echo "▶ Entferne rigbridge:test Image ..."
        docker rmi rigbridge:test 2>/dev/null || true
        echo "  ✓ rigbridge:test entfernt"
    fi
else
    echo "  ℹ rigbridge:test Image bleibt erhalten (--keep-image)"
fi

# ── 3. Produktiven Container wieder starten ─────────────────────────────────
if docker ps -q --filter name="^${PROD_CONTAINER}$" | grep -q .; then
    echo "  ℹ $PROD_CONTAINER läuft bereits"
elif docker ps -aq --filter name="^${PROD_CONTAINER}$" | grep -q .; then
    echo "▶ Starte $PROD_CONTAINER wieder ..."
    docker start "$PROD_CONTAINER"
    echo "  ✓ $PROD_CONTAINER gestartet"
else
    echo "  ⚠ $PROD_CONTAINER-Container nicht gefunden."
    echo "    Starte manuell mit: docker compose up -d"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Zurück zur Produktion!"

PROD_PORT=$(docker inspect "$PROD_CONTAINER" \
    --format '{{range $p, $conf := .NetworkSettings.Ports}}{{(index $conf 0).HostPort}}{{end}}' 2>/dev/null || echo "8080")
PROD_IP=$(docker inspect "$PROD_CONTAINER" \
    --format '{{range $p, $conf := .NetworkSettings.Ports}}{{(index $conf 0).HostIp}}{{end}}' 2>/dev/null || echo "127.0.0.1")

echo "  Web-UI:  http://${PROD_IP}:${PROD_PORT}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
