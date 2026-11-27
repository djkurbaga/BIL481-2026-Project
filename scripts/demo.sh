#!/usr/bin/env bash
# GSMF uçtan uca demo (Linux). Depo kökünden çalıştırın:
#   bash scripts/demo.sh
# Ek argümanlar scripts/demo.py'ye aktarılır (ör. --out results/demo).

# Hata, tanımsız değişken veya boru hattı hatasında dur.
set -euo pipefail

# Çalışma dizinini depo köküne al; betik nereden çağrılırsa çağrılsın aynı yollar kullanılsın.
cd "$(dirname "$0")/.."

# Python çıktısı UTF-8 olsun.
export PYTHONIOENCODING=utf-8

# PYTHON verilmişse onu kullan; yoksa python3, o da yoksa python.
PYTHON_BIN="${PYTHON:-}"
if [ -z "$PYTHON_BIN" ]; then
  if command -v python3 >/dev/null 2>&1; then PYTHON_BIN=python3; else PYTHON_BIN=python; fi
fi

# Demoyu çalıştır; çıkış kodu demo.py'ninkiyle aynıdır (FAIL varsa 1).
exec "$PYTHON_BIN" scripts/demo.py "$@"
