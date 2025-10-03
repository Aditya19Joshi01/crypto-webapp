import os

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://crypto:crypto@postgres:5432/cryptodb"
)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "3"))  # seconds
SYMBOLS = [
    "bitcoin",
    "ethereum",
    "cusd",
]  # coinGecko ids: bitcoin, ethereum; cusd mocked
