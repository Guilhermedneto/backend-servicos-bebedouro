"""Verifica o lote de 12 itens (scroll infinito): cria 13 prestadores aprovados e pagina."""

import random
import sys
import uuid

import httpx

BASE = "http://127.0.0.1:8000/api"
run_id = uuid.uuid4().hex[:8]
client = httpx.Client(timeout=60.0)


def expect(condition: bool, message: str):
    if not condition:
        print(f"FALHOU: {message}")
        sys.exit(1)


def random_cpf() -> str:
    digits = [random.randint(0, 9) for _ in range(9)]
    for position in (9, 10):
        total = sum(digits[i] * (position + 1 - i) for i in range(position))
        digit = (total * 10) % 11
        digits.append(0 if digit == 10 else digit)
    return "".join(map(str, digits))


r = client.post(f"{BASE}/auth/login", json={"email": "admin@servicosbebedouro.com.br", "password": "admin12345"})
admin = {"Authorization": f"Bearer {r.json()['accessToken']}"}

r = client.post(f"{BASE}/admin/categories", json={"name": f"Pedreiro {run_id}"}, headers=admin)
category_id = r.json()["id"]

print(f"Criando 13 prestadores ({run_id})...")
for i in range(13):
    r = client.post(
        f"{BASE}/auth/register-provider",
        json={
            "name": f"Prestador {run_id} nº {i:02d}",
            "document": random_cpf(),
            "categoryIds": [category_id],
            "bairro": f"Bairro {run_id}",
            "rua": "Rua Teste",
            "numero": str(i + 1),
            "whatsapp": "17999998888",
            "description": "Serviços de teste de paginação.",
            "email": f"pag-{run_id}-{i}@teste.com",
            "password": "senha12345",
        },
    )
    expect(r.status_code == 201, f"cadastro {i}: {r.status_code} {r.text}")
    provider_id = r.json()["id"]
    r = client.post(f"{BASE}/admin/providers/{provider_id}/approve", headers=admin)
    expect(r.status_code == 200, f"aprovação {i}: {r.status_code}")

r = client.get(f"{BASE}/providers", params={"search": run_id, "page": 1})
data = r.json()
expect(len(data["items"]) == 12, f"página 1 deveria ter 12 itens, tem {len(data['items'])}")
expect(data["total"] == 13 and data["hasMore"] is True, f"total/hasMore: {data['total']}/{data['hasMore']}")

r = client.get(f"{BASE}/providers", params={"search": run_id, "page": 2})
data2 = r.json()
expect(len(data2["items"]) == 1 and data2["hasMore"] is False, f"página 2: {len(data2['items'])}/{data2['hasMore']}")

ids_p1 = {i["id"] for i in data["items"]}
ids_p2 = {i["id"] for i in data2["items"]}
expect(not ids_p1 & ids_p2, "itens repetidos entre páginas")

r = client.get(f"{BASE}/providers", params={"search": run_id, "sort": "recent"})
names = [i["name"] for i in r.json()["items"]]
expect(names == sorted(names, reverse=True), f"ordenação por mais recentes: {names[:3]}...")

print("Limpando prestadores de teste...")
r = client.get(f"{BASE}/admin/providers", headers=admin)
for p in r.json():
    if run_id in p["name"]:
        client.delete(f"{BASE}/admin/providers/{p['id']}", headers=admin)
client.delete(f"{BASE}/admin/categories/{category_id}", headers=admin)

print("PAGINACAO OK — lotes de 12, hasMore e ordenação verificados.")
