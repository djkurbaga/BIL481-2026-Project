# GSMF uçtan uca demo (Windows). Depo kökünden çalıştırın:
#   powershell -ExecutionPolicy Bypass -File scripts/demo.ps1
# Ek argümanlar scripts/demo.py'ye aktarılır (ör. --out results/demo).

# Hata olursa betiği durdur.
$ErrorActionPreference = "Stop"

# Çalışma dizinini depo köküne al; betik nereden çağrılırsa çağrılsın aynı yollar kullanılsın.
Set-Location (Join-Path $PSScriptRoot "..")

# Python çıktısı UTF-8 olsun (ç, ş, · gibi karakterler bozulmasın).
$env:PYTHONIOENCODING = "utf-8"

# PYTHON ortam değişkeni verilmişse onu, yoksa "python" komutunu kullan.
$python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

# Demoyu çalıştır ve çıkış kodunu aynen döndür (FAIL varsa 1).
& $python scripts/demo.py @args
exit $LASTEXITCODE
