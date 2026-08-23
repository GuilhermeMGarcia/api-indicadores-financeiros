import time
from typing import Any, Optional


class TTLCache:
    """
    Cache simples em memória com expiração por tempo (TTL).

    Observação: em ambiente serverless (Vercel), cada instância da função
    pode nascer "fria" (cold start) e começar com o cache vazio. Este cache
    só é efetivo enquanto a mesma instância continua ativa atendendo
    chamadas seguidas — o que reduz bastante o scraping no dia a dia, mas
    não garante 100% de acerto em todo cenário de tráfego.
    """

    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if not entry:
            return None

        timestamp, value = entry
        if time.time() - timestamp > self.ttl_seconds:
            del self._store[key]
            return None

        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)