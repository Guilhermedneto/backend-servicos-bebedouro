"""Testa a busca com IA.

1. Grafo LangGraph com LLM falsa (sem credenciais Azure): interpret → retrieve → answer.
2. Endpoint /api/search/ai sem credenciais deve responder 503 com código AI_SEARCH_UNAVAILABLE.
"""

import sys

import httpx

sys.path.insert(0, ".")

from app.infrastructure.ai_search import LangGraphAiSearchService, SearchIntent  # noqa: E402
from app.infrastructure.cosmos_db import init_cosmos  # noqa: E402
from app.infrastructure.repositories import (  # noqa: E402
    CosmosCategoryRepository,
    CosmosProviderRepository,
)


def expect(condition: bool, message: str):
    if not condition:
        print(f"FALHOU: {message}")
        sys.exit(1)


class _FakeStructured:
    def invoke(self, prompt):
        return SearchIntent(
            search_terms=["eletrica"], category_names=["Eletricista"], sort="rating"
        )


class FakeLLM:
    def with_structured_output(self, model):
        return _FakeStructured()


print("[1] Grafo LangGraph com LLM falsa")
init_cosmos(retries=3)
service = LangGraphAiSearchService(
    CosmosProviderRepository(), CosmosCategoryRepository(), llm=FakeLLM()
)
result = service.search("preciso de alguém para arrumar a parte elétrica da minha casa no centro")
expect(len(result["providers"]) >= 1, f"nenhum prestador recuperado: {result}")
names = [p["name"] for p in result["providers"]]
expect(any("Elétrica" in n for n in names), f"prestador demo não recuperado: {names}")
expect(result["answer"] == "Olha o que eu encontrei pra você", f"resposta inesperada: {result['answer']}")
print(f"    OK — {len(result['providers'])} prestador(es), resposta: {result['answer'][:60]}...")

print("[2] Endpoint sem credenciais Azure responde 503")
r = httpx.post("http://127.0.0.1:8000/api/search/ai", json={"question": "quem conserta chuveiro?"}, timeout=30)
expect(r.status_code == 503, f"esperava 503, veio {r.status_code}: {r.text}")
expect(r.json()["error"]["code"] == "AI_SEARCH_UNAVAILABLE", r.text)
print("    OK — 503 AI_SEARCH_UNAVAILABLE")

print("[3] Pergunta curta demais responde 422")
r = httpx.post("http://127.0.0.1:8000/api/search/ai", json={"question": "oi"}, timeout=30)
expect(r.status_code == 422, f"esperava 422, veio {r.status_code}")
print("    OK — 422")

print("\nAI SEARCH TEST OK")
