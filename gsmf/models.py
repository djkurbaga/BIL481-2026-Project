"""GSMF paylaşılan veri modelleri.

Bu modül, dört kullanım senaryosunun (UC1–UC4) ortak sözleşmesini tanımlar.
Tüm ekip üyeleri yapılandırma, yaşam döngüsü, metrik ve depolama modüllerini
buradaki sınıflara göre geliştirir. Alan adları ve birimleri değiştirilmeden
önce ekipçe karar verilmelidir.

Birim kuralı: alan adının sonundaki ek birimi belirtir
(``_j`` = joule, ``_s`` = saniye, ``_w`` = watt, ``_js`` = joule·saniye).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

# ---------------------------------------------------------------------------
# Birim etiketleri (FR-8: birimler sonuçlarla birlikte kaydedilmelidir)
# ---------------------------------------------------------------------------

#: Görev başına enerji birimi (joule / tamamlanan kullanıcı görevi).
UNIT_ENERGY_PER_TASK = "J/task"
#: Enerji-Gecikme Çarpımı (EDP) birimi (joule × saniye).
UNIT_EDP = "J·s"
#: Enerji birimi.
UNIT_ENERGY = "J"
#: Süre birimi.
UNIT_DURATION = "s"


# ---------------------------------------------------------------------------
# Sayımlar (enum)
# ---------------------------------------------------------------------------


class PlatformKind(str, Enum):
    """Desteklenen hedef platform türleri.

    FR-1 gereği yapılandırmada bu listede olmayan bir hedef reddedilir.
    """

    BUDIBASE = "budibase"
    APPSMITH = "appsmith"
    FASTAPI = "fastapi"


class StackState(str, Enum):
    """Bir hedef Docker yığınının yaşam döngüsü durumları (UC2, FR-3).

    Geçişler: STARTING → HEALTHY → RUNNING → STOPPING → STOPPED.
    Başlatma, sağlık kontrolü veya kapatma hatasında yığın FAILED olur.
    """

    STARTING = "starting"
    HEALTHY = "healthy"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class RepetitionStatus(str, Enum):
    """Bir tekrarın (repetition) sonuç durumu.

    - VALID: ölçüm kullanılabilir; metrikler hesaplanır.
    - INVALID: ölçüm alındı ama kullanılamaz (ör. negatif net enerji,
      sıfır tamamlanan görev, okunamayan sayaç) — FR-7.
    - FAILED: yürütme hatası (ör. yığın başlatılamadı, k6 başarısız) — FR-3/FR-6.
    """

    VALID = "valid"
    INVALID = "invalid"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Yapılandırma modelleri (UC1, FR-1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TargetPlatform:
    """Test edilen tek bir platform yığınının tanımı.

    Alanlar:
        kind: Platform türü (Budibase, Appsmith veya FastAPI).
        compose_file: Yığını başlatan Docker Compose dosyasının yolu.
        base_url: Hedef uygulamanın temel adresi (k6 bu adrese istek atar).
        health_url: Sağlık kontrolü için yoklanan adres.
        health_timeout_s: Sağlık kontrolünün geçmesi için en fazla bekleme süresi (s).
    """

    kind: PlatformKind
    compose_file: Path
    base_url: str
    health_url: str
    health_timeout_s: float = 120.0


@dataclass(frozen=True)
class BenchmarkConfig:
    """Doğrulanmış kıyaslama (benchmark) yapılandırması (FR-1).

    Bu nesne yalnızca ``gsmf.config.load_config`` tarafından, doğrulama
    başarılı olduktan sonra üretilmelidir.

    Alanlar:
        title: Deney grubunun okunabilir adı.
        targets: Sırayla ölçülecek hedef platformlar.
        workload_size: Her tekrarda çalıştırılacak kullanıcı görevi sayısı (pozitif tam sayı).
        concurrency: k6 eş zamanlı sanal kullanıcı sayısı (pozitif tam sayı).
        repetitions: Hedef başına tekrar sayısı (pozitif tam sayı).
        cooldown_s: Tekrarlar ve platform geçişleri arası bekleme süresi (negatif olamaz).
        load_generator_host: k6'nın çalıştığı ayrı makinenin adresi.
        grid_carbon_intensity: Şebeke karbon yoğunluğu (gCO2eq/kWh); SCI için, isteğe bağlı.
    """

    title: str
    targets: tuple[TargetPlatform, ...]
    workload_size: int
    concurrency: int
    repetitions: int
    cooldown_s: float
    load_generator_host: str
    grid_carbon_intensity: float | None = None


@dataclass(frozen=True)
class TestbedSettings:
    """Ölçüm makinesinin (testbed) kaydedilen ayarları (FR-2, FR-11).

    Alanlar:
        hostname: Testbed makinesinin adı.
        cpu_governor: Uygulanan CPU frekans yöneticisi (ör. "performance").
        turbo_boost_disabled: Turbo Boost kapalı mı?
        rapl_domains: Örneklenen RAPL alanları (ör. ("package-0", "dram")).
    """

    # pytest bu sınıfı "Test" önekinden dolayı test sınıfı sanmasın.
    __test__ = False

    hostname: str
    cpu_governor: str
    turbo_boost_disabled: bool
    rapl_domains: tuple[str, ...]


# ---------------------------------------------------------------------------
# Ölçüm ve metrik modelleri (UC3, UC4)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RepetitionRecord:
    """Tek bir tekrarın ham ölçüm kaydı (FR-4, FR-7, FR-11).

    Kayıt değişmezdir (frozen): FR-11 gereği saklanan ölçülen değerler daha
    sonraki hesaplamalarla değiştirilmez. Başarısız/geçersiz tekrarlarda
    ölçüm alanları ``None`` olabilir; durum ve sebep her zaman doldurulur.

    Alanlar:
        run_id: Kıyaslama çalıştırmasının kimliği.
        target: Ölçülen platform türü.
        repetition_index: Hedef içindeki tekrar sırası (1'den başlar).
        status: Tekrarın durumu (VALID / INVALID / FAILED).
        reason: INVALID veya FAILED ise açıklayıcı sebep; VALID ise None.
        idle_power_w: Ortalama boşta güç (W).
        gross_energy_j: İş yükü aralığındaki brüt RAPL enerjisi (J).
        duration_s: Ölçülen iş yükü aralığı süresi (s).
        net_energy_j: Net enerji = brüt − boşta güç × süre (J).
        completed_tasks: Tamamen başarılı kullanıcı görevi sayısı.
        workload_errors: k6 tarafından bildirilen hata sayısı.
        started_at: Tekrarın başlangıç zamanı.
    """

    run_id: str
    target: PlatformKind
    repetition_index: int
    status: RepetitionStatus
    reason: str | None = None
    idle_power_w: float | None = None
    gross_energy_j: float | None = None
    duration_s: float | None = None
    net_energy_j: float | None = None
    completed_tasks: int | None = None
    workload_errors: int = 0
    started_at: datetime | None = None


@dataclass(frozen=True)
class EfficiencyMetrics:
    """Geçerli bir tekrar için hesaplanan verimlilik metrikleri (FR-8).

    Alanlar:
        run_id: Kaynağı olan çalıştırmanın kimliği.
        target: Platform türü.
        repetition_index: Kaynağı olan tekrarın sırası.
        net_energy_j: Hesapta kullanılan net enerji (J).
        duration_s: Hesapta kullanılan süre (s).
        completed_tasks: Hesapta kullanılan tamamlanan görev sayısı.
        energy_per_task_j: Görev başına enerji = net enerji / görev sayısı (J/task).
        edp_js: Enerji-Gecikme Çarpımı = net enerji × süre (J·s).
        energy_per_task_unit: Görev başına enerjinin birimi.
        edp_unit: EDP birimi.
    """

    run_id: str
    target: PlatformKind
    repetition_index: int
    net_energy_j: float
    duration_s: float
    completed_tasks: int
    energy_per_task_j: float
    edp_js: float
    energy_per_task_unit: str = field(default=UNIT_ENERGY_PER_TASK)
    edp_unit: str = field(default=UNIT_EDP)


# ---------------------------------------------------------------------------
# Hata türleri
# ---------------------------------------------------------------------------


class GSMFError(Exception):
    """Tüm GSMF hatalarının temel sınıfı."""


class ConfigError(GSMFError):
    """Geçersiz veya eksik yapılandırma (UC1, FR-1)."""


class ExecutionFailure(GSMFError):
    """Yığın başlatma, sağlık kontrolü veya kapatma hatası (UC2, FR-3)."""


class StorageError(GSMFError):
    """SQLite kaydetme veya CSV dışa aktarma hatası (UC4, FR-11)."""
