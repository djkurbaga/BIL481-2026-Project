"""pytest ortak ayarları: depo kökünü içe aktarma yoluna ekler (``import gsmf`` için)."""

import sys
from pathlib import Path

# Testler kurulum yapılmadan depo kökünden çalıştırılabilsin diye kökü sys.path'e ekle.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
