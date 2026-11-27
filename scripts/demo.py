"""GSMF uçtan uca demo: UC1–UC4'ü sırayla çalıştırır (FR-1, FR-3, FR-8, FR-11).

Depo kökünden çalıştırın (veya scripts/demo.ps1 / scripts/demo.sh ile):

    python scripts/demo.py [--out results/demo] [--require-docker]

Her adım PASS, FAIL veya SKIPPED olarak raporlanır. Docker yoksa UC2 adımı
"SKIPPED: Docker not available" yazar; asla başarılı gibi gösterilmez.
--require-docker verilirse Docker olmadan UC2 başarısız sayılır.
Herhangi bir adım FAIL olursa çıkış kodu 1'dir.
"""

from __future__ import annotations

import argparse
import contextlib
import platform
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

# Depo kökünü içe aktarma yoluna ekle; kurulum yapmadan "import gsmf" çalışsın.
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gsmf.config import load_config  # noqa: E402
from gsmf.lifecycle import StackManager, isolated_stack  # noqa: E402
from gsmf.metrics import compute_metrics, load_records_csv  # noqa: E402
from gsmf.metrics import main as metrics_cli  # noqa: E402
from gsmf.models import (  # noqa: E402
    ConfigError,
    ExecutionFailure,
    PlatformKind,
    StackState,
    StorageError,
    TestbedSettings,
)
from gsmf.storage import ResultStore  # noqa: E402

# Demo girdileri (depo köküne göre).
VALID_CONFIG = REPO / "examples" / "benchmark.yaml"
INVALID_CONFIG = REPO / "examples" / "invalid-benchmark.yaml"
SAMPLE_CSV = REPO / "examples" / "sample_measurements.csv"
RUN_ID = "demo-run"


class StepFailed(Exception):
    """Bir demo adımının beklenen sonucu vermediğini bildirir."""


def banner(title: str) -> None:
    """Adım başlığını belirgin bir çizgiyle yazdırır."""
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


# ---------------------------------------------------------------------------
# UC1 — yapılandırma (FR-1)
# ---------------------------------------------------------------------------


def uc1_configure() -> str:
    """Geçerli örneğin yüklendiğini ve geçersiz örneğin reddedildiğini gösterir."""
    # Geçerli yapılandırma: hata olmadan BenchmarkConfig dönmeli.
    print(f"[UC1] valid config: {VALID_CONFIG.relative_to(REPO).as_posix()}")
    config = load_config(VALID_CONFIG)
    print(f"      accepted: title={config.title!r}, targets={[t.kind.value for t in config.targets]}, "
          f"workload_size={config.workload_size}, concurrency={config.concurrency}, "
          f"repetitions={config.repetitions}, cooldown_s={config.cooldown_s}")

    # Geçersiz yapılandırma: ConfigError ile reddedilmeli; kabul edilirse adım başarısızdır.
    print(f"[UC1] invalid config: {INVALID_CONFIG.relative_to(REPO).as_posix()} (expected rejection)")
    try:
        load_config(INVALID_CONFIG)
    except ConfigError as exc:
        print(f"      rejected as expected: ConfigError: {exc}")
        print("      no Docker stack was started")
        return "PASS"
    raise StepFailed("invalid configuration was accepted")


# ---------------------------------------------------------------------------
# UC2 — izole yığın yaşam döngüsü (FR-3)
# ---------------------------------------------------------------------------


def _docker_available() -> tuple[bool, str]:
    """Docker CLI, Docker Engine ve Compose eklentisinin kullanılabilirliğini denetler."""
    if shutil.which("docker") is None:
        return False, "docker command not found"
    # Engine çalışmıyorsa "docker info" başarısız olur; Compose ayrıca denetlenir.
    for args in (["docker", "info", "--format", "{{.ServerVersion}}"], ["docker", "compose", "version"]):
        try:
            result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", timeout=30, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            return False, f"{' '.join(args)}: {exc}"
        if result.returncode != 0:
            return False, f"{' '.join(args)}: {(result.stderr or result.stdout).strip()}"
    return True, ""


def uc2_lifecycle(*, require_docker: bool = False) -> str:
    """FastAPI baseline yığınını başlatır, sağlığını bekler, durdurur ve kapanışı doğrular."""
    available, reason = _docker_available()
    if not available:
        if require_docker:
            raise StepFailed(f"Docker not available: {reason}")
        # Docker yoksa sahte bir başarı üretmeden adımı atla.
        print("[UC2] SKIPPED: Docker not available")
        print(f"      reason: {reason}")
        return "SKIPPED"

    target = load_config(VALID_CONFIG).targets[0]
    # Temizlik başka bir demo veya elle başlatılmış baseline yığınını etkilemesin.
    project = f"gsmf-a3-demo-{uuid4().hex}"
    compose_command = ("docker", "compose", "--project-name", project)
    print(f"[UC2] project={project}, compose_file={target.compose_file}", flush=True)

    # İmajı önceden oluştur; derleme süresi sağlık zaman aşımına sayılmasın.
    # Docker çıktısı UTF-8'dir; Windows'un varsayılan kod sayfasıyla okunursa çöker.
    build = subprocess.run(
        [*compose_command, "-f", str(target.compose_file), "build"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=900, check=False,
    )
    if build.returncode != 0:
        raise StepFailed(f"image build failed: {(build.stderr or build.stdout).strip()}")

    manager = StackManager(compose_command)
    print(f"[UC2] start: {target.kind.value}, health_url={target.health_url}, "
          f"timeout={target.health_timeout_s} s")
    try:
        # isolated_stack: up -d → sağlık kontrolü → (iş yükü) → down + doğrulama.
        with isolated_stack(manager, target):
            print(f"      state after health check: {manager.state.value}")
            manager.mark_running()
            print(f"      state during workload gate: {manager.state.value}")
    except ExecutionFailure as exc:
        raise StepFailed(f"ExecutionFailure: {exc} (state={manager.state.value})") from exc
    print(f"      state after stop: {manager.state.value}")
    if manager.state is not StackState.STOPPED:
        raise StepFailed(f"shutdown not confirmed (state={manager.state.value})")
    print("      shutdown confirmed: no containers left (docker compose ps --all --quiet is empty)")
    return "PASS"


# ---------------------------------------------------------------------------
# UC3 — verimlilik metrikleri (FR-8)
# ---------------------------------------------------------------------------


def uc3_metrics() -> str:
    """Örnek CSV'den görev başına enerji ve EDP tablosunu yazdırır."""
    print("[UC3] input: examples/sample_measurements.csv")
    print("      ILLUSTRATIVE SAMPLE DATA - NOT REAL MEASUREMENTS")
    print()
    # gsmf.metrics komut satırı aracını aynen çağır (python -m gsmf.metrics ile aynı çıktı).
    exit_code = metrics_cli([str(SAMPLE_CSV)])
    if exit_code != 0:
        raise StepFailed(f"gsmf.metrics exited with {exit_code}")
    return "PASS"


# ---------------------------------------------------------------------------
# UC4 — kalıcı saklama ve dışa aktarma (FR-11)
# ---------------------------------------------------------------------------


def uc4_persist(out_dir: Path) -> str:
    """Bir çalıştırmayı SQLite'a kaydeder, değişmezliği sınar ve CSV'leri dışa aktarır."""
    out_dir.mkdir(parents=True, exist_ok=True)
    db_path = out_dir / "gsmf-demo.db"
    # Demo her çalıştığında temiz başlasın: yalnızca kendi ürettiği dosyaları siler.
    for old in (db_path, out_dir / f"raw_{RUN_ID}.csv", out_dir / f"aggregates_{RUN_ID}.csv"):
        old.unlink(missing_ok=True)

    config = load_config(VALID_CONFIG)
    store = ResultStore(db_path)
    store.initialize_schema()
    # Testbed değerleri demo yer tutucularıdır; FR-2 ön koşul denetimi henüz uygulanmadı.
    testbed = TestbedSettings(
        hostname="demo-host",
        cpu_governor="not-checked (demo; FR-2 not implemented)",
        turbo_boost_disabled=False,
        rapl_domains=(),
    )
    store.save_run(RUN_ID, config, {PlatformKind.FASTAPI: "baseline-0.1.0"}, testbed)
    print(f"[UC4] database: {db_path.relative_to(REPO).as_posix() if db_path.is_relative_to(REPO) else db_path}")
    print("      testbed settings are demo placeholders (FR-2 prerequisite checks are not implemented)")

    # Yapılandırmada yalnızca fastapi hedefi var; bu yüzden yalnız fastapi kayıtları saklanır.
    records = [r for r in load_records_csv(SAMPLE_CSV) if r.target is PlatformKind.FASTAPI]
    for record in records:
        store.save_repetition(record)
    stored = store.load_repetitions(RUN_ID)
    print(f"      stored repetitions: {len(stored)} "
          f"({', '.join(f'#{r.repetition_index} {r.status.value}' for r in stored)})")
    metrics = compute_metrics(stored)
    store.save_metrics(metrics)
    print(f"      stored metrics: {len(metrics)} (valid repetitions only)")

    # FR-11: aynı kaydı ikinci kez eklemek reddedilmeli.
    try:
        store.save_repetition(stored[0])
    except StorageError as exc:
        print(f"      duplicate insert rejected as expected: {exc}")
    else:
        raise StepFailed("duplicate repetition was accepted")

    # FR-11: doğrudan SQL ile değer değiştirme tetikleyici tarafından reddedilmeli.
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        try:
            with conn:
                conn.execute("UPDATE repetitions SET net_energy_j = 0")
        except sqlite3.DatabaseError as exc:
            print(f"      direct UPDATE rejected as expected: {exc}")
        else:
            raise StepFailed("direct UPDATE of a stored value was accepted")

    raw = store.export_raw_csv(RUN_ID, out_dir)
    aggregates = store.export_aggregates_csv(RUN_ID, out_dir)
    for path in (raw, aggregates):
        shown = path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path)
        print()
        print(f"      exported: {shown}")
        print(path.read_text(encoding="utf-8").rstrip())
    return "PASS"


# ---------------------------------------------------------------------------
# Ana akış
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Dört adımı çalıştırır, özet tablo yazar ve çıkış kodunu döndürür."""
    parser = argparse.ArgumentParser(description="GSMF end-to-end demo for UC1-UC4")
    parser.add_argument("--out", type=Path, default=REPO / "results" / "demo",
                        help="directory for the UC4 SQLite database and exported CSVs "
                             "(default: results/demo)")
    parser.add_argument("--require-docker", action="store_true",
                        help="fail UC2 if Docker Engine or Compose is unavailable")
    args = parser.parse_args(argv)
    out_dir = args.out if args.out.is_absolute() else (Path.cwd() / args.out)

    # Logların her ortamda aynı kodlamayla yazılması için UTF-8 kullan.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.version_info < (3, 11):
        print(f"error: Python 3.11+ required, found {platform.python_version()}", file=sys.stderr)
        return 1

    print(f"GSMF demo — Python {platform.python_version()} on {platform.system()} {platform.release()}")

    steps: list[tuple[str, Callable[[], str]]] = [
        ("UC1 Configure benchmark (FR-1)", uc1_configure),
        ("UC2 Manage isolated stack lifecycle (FR-3)",
         lambda: uc2_lifecycle(require_docker=args.require_docker)),
        ("UC3 Compute efficiency metrics (FR-8)", uc3_metrics),
        ("UC4 Persist and export results (FR-11)", lambda: uc4_persist(out_dir)),
    ]
    results: list[tuple[str, str]] = []
    # Bir adım başarısız olsa da diğerleri çalışsın; sonuçlar sonda özetlenir.
    for title, step in steps:
        banner(title)
        try:
            outcome = step()
        except (StepFailed, ConfigError, ExecutionFailure, StorageError, OSError,
                subprocess.SubprocessError) as exc:
            print(f"      FAIL: {exc}")
            outcome = "FAIL"
        results.append((title, outcome))

    banner("Summary")
    for title, outcome in results:
        print(f"{outcome:<8} {title}")
    failed = sum(outcome == "FAIL" for _, outcome in results)
    skipped = sum(outcome == "SKIPPED" for _, outcome in results)
    print(f"\n{len(results) - failed - skipped} passed, {failed} failed, {skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
