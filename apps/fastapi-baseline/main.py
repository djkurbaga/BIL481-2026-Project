"""UC2 için ölçüm veya veritabanı gerektirmeyen küçük FastAPI uygulaması."""

from fastapi import FastAPI

app = FastAPI(title="GSMF FastAPI baseline")


@app.get("/health")
def health() -> dict[str, str]:
    """Yaşam döngüsü yöneticisine uygulamanın hazır olduğunu bildirir."""
    return {"status": "ok"}
