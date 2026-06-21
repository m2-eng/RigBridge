#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# test-start.sh – Wechsel von rigbridge → rigbridge-test
#
# Was dieses Skript tut:
#   1. Stoppt den laufenden rigbridge-Container (ohne ihn zu entfernen)
#   2. Baut das rigbridge:test-Image aus dem aktuellen Quellcode
#   3. Startet rigbridge-test auf Port TEST_PORT (Standard: 8081)
#
# Was dieses Skript NICHT tut:
#   - Das rigbridge-Image oder den rigbridge-Container verändern
#   - config.json aus dem produktiven Pfad überschreiben
#
# Verwendung:
#   ./docker/test-start.sh [test-port] [bind-address]
#
# Beispiele:
#   ./docker/test-start.sh            → Port 8081, localhost
#   ./docker/test-start.sh 8082       → Port 8082, localhost
#   ./docker/test-start.sh 8081 0.0.0.0  → auch aus dem Netzwerk erreichbar
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_PORT="${1:-8081}"
BIND_ADDRESS="${2:-127.0.0.1}"
PROD_CONTAINER="rigbridge"
TEST_CONTAINER="rigbridge-test"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  RigBridge Test-Modus starten"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Repo:         $REPO_DIR"
echo "  Test-Port:    $BIND_ADDRESS:$TEST_PORT"
echo ""

cd "$REPO_DIR"

# ── 1. Produktiven Container stoppen (nicht entfernen) ──────────────────────
if docker ps -q --filter name="^${PROD_CONTAINER}$" | grep -q .; then
    echo "▶ Stoppe $PROD_CONTAINER ..."
    docker stop "$PROD_CONTAINER"
    echo "  ✓ $PROD_CONTAINER gestoppt (Image und Container bleiben erhalten)"
else
    echo "  ℹ $PROD_CONTAINER läuft nicht – nichts zu stoppen"
fi

# ── 2. Eventuell laufenden Test-Container aufräumen ─────────────────────────
if docker ps -q --filter name="^${TEST_CONTAINER}$" | grep -q .; then
    echo "▶ Stoppe laufenden $TEST_CONTAINER ..."
    docker compose -f docker-compose.test.yml down --remove-orphans
fi

# ── 3. Test-Image bauen ─────────────────────────────────────────────────────
echo ""
echo "▶ Baue rigbridge:test Image aus aktuellem Quellcode ..."
docker compose -f docker-compose.test.yml build --no-cache
echo "  ✓ Image rigbridge:test gebaut"

# ── 4. Test-Container starten ───────────────────────────────────────────────
echo ""
echo "▶ Starte $TEST_CONTAINER auf Port $BIND_ADDRESS:$TEST_PORT ..."
TEST_PORT="$TEST_PORT" BIND_ADDRESS="$BIND_ADDRESS" \
    docker compose -f docker-compose.test.yml up -d

# ── 5. Warten auf Health-Check ──────────────────────────────────────────────
echo ""
echo "▶ Warte auf Health-Check ..."
MAX_WAIT=60
ELAPSED=0
until docker inspect --format='{{.State.Health.Status}}' "$TEST_CONTAINER" 2>/dev/null | grep -q "healthy"; do
    sleep 3
    ELAPSED=$((ELAPSED + 3))
    if [ "$ELAPSED" -ge "$MAX_WAIT" ]; then
        echo "  ⚠ Health-Check Timeout – Container läuft möglicherweise trotzdem"
        break
    fi
    echo "  … warte ($ELAPSED/${MAX_WAIT}s)"
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ rigbridge-test läuft!"
echo "  Web-UI:  http://${BIND_ADDRESS}:${TEST_PORT}"
echo "  API:     http://${BIND_ADDRESS}:${TEST_PORT}/api/docs"
echo "  Health:  http://${BIND_ADDRESS}:${TEST_PORT}/health"
echo ""
echo "  Logs:    docker logs -f $TEST_CONTAINER"
echo "  Stop:    ./docker/test-stop.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
