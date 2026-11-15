"""HTTP sağlık yoklamasını sonlandırılabilir bir alt süreçte çalıştırır."""

from http.client import HTTPException
from pathlib import Path
import subprocess
import sys
from urllib.error import HTTPError
from urllib.request import urlopen


def http_status(url: str, timeout: float) -> int:
    """DNS, yönlendirmeler ve yanıt başlıkları için ortak süre sınırı uygular.

    Soket zaman aşımı her veri parçasında yeniden başlayabilir. Ayrı süreç,
    bu durumda da süre dolunca öldürülür ve kapanması beklenir; arka planda
    açık istek veya iş parçacığı bırakılmaz. Süreç oluşturma ve sonlandırma
    için işletim sisteminin gerektirdiği kısa süre ayrıca geçebilir.
    """
    if timeout <= 0:
        raise TimeoutError("HTTP sağlık kontrolü zaman aşımı")
    try:
        result = subprocess.run(
            [sys.executable, "-I", str(Path(__file__).resolve()), url, str(timeout)],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError("HTTP sağlık kontrolü zaman aşımı") from exc
    if result.returncode:
        raise OSError(f"HTTP sağlık kontrolü başarısız: {result.stderr.strip()}")
    return int(result.stdout.strip())


def _probe(url: str, timeout: float) -> int:
    """Alt süreçte yalnızca HTTP durumunu okur; yanıt gövdesini indirmez."""
    try:
        with urlopen(url, timeout=timeout) as response:
            return response.status
    except HTTPError as exc:
        # 4xx ve 5xx durumları da çağırana iletilir; bağlantı kapatılır.
        with exc:
            return exc.code


if __name__ == "__main__":
    try:
        print(_probe(sys.argv[1], float(sys.argv[2])))
    except (OSError, HTTPException, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
