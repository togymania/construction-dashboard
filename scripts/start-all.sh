#!/usr/bin/env bash
# ==========================================
# Tek komutla backend + frontend baslat
# macOS / Linux
# ==========================================
# Kullanim: ./scripts/start-all.sh

set -e

# Trap: Ctrl+C ile kapatildiginda alt surecleri de oldur
cleanup() {
  echo ""
  echo "[INFO] Servisler durduruluyor..."
  kill $(jobs -p) 2>/dev/null || true
  exit 0
}
trap cleanup SIGINT SIGTERM

# Backend baslat
echo "[INFO] Backend baslatiliyor..."
(cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000) &
BACKEND_PID=$!

# Kisa bekle
sleep 2

# Frontend baslat
echo "[INFO] Frontend baslatiliyor..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "=========================================="
echo "  Servisler calisiyor"
echo "=========================================="
echo "  Frontend:  http://localhost:3000"
echo "  Backend:   http://localhost:8000/docs"
echo ""
echo "  Durdurmak icin: Ctrl+C"
echo "=========================================="
echo ""

# Bekle
wait $BACKEND_PID $FRONTEND_PID
