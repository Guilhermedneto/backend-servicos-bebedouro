"""Cria dados de demonstração: categorias, um prestador aprovado com foto e uma avaliação.

Imprime o id do prestador criado (para testes de SSR/meta tags).
"""

import base64
import os
import sys
import uuid

import httpx

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000/api")
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

client = httpx.Client(timeout=60.0)
run_id = uuid.uuid4().hex[:6]

r = client.post(f"{BASE}/auth/login", json={"email": "admin@servicosbebedouro.com.br", "password": "admin12345"})
admin = {"Authorization": f"Bearer {r.json()['accessToken']}"}

categories = {}
for name in ("Eletricista", "Encanador"):
    r = client.post(f"{BASE}/admin/categories", json={"name": name}, headers=admin)
    if r.status_code == 201:
        categories[name] = r.json()["id"]
    else:
        r2 = client.get(f"{BASE}/admin/categories", headers=admin)
        categories[name] = next(c["id"] for c in r2.json() if c["name"] == name)

email = f"demo-{run_id}@servicosbebedouro.com.br"
r = client.post(
    f"{BASE}/auth/register-provider",
    json={
        "name": "Elétrica São José",
        "document": "529.982.247-25",
        "categoryIds": [categories["Eletricista"], categories["Encanador"]],
        "bairro": "Centro",
        "rua": "Rua Prudente de Moraes",
        "numero": "1500",
        "whatsapp": "17991234567",
        "description": "Instalações e manutenções elétricas residenciais e comerciais em Bebedouro. "
        "Atendimento rápido, orçamento sem compromisso.",
        "email": email,
        "password": "senha12345",
    },
)
if r.status_code != 201:
    print(f"erro no cadastro: {r.status_code} {r.text}")
    sys.exit(1)
provider_id = r.json()["id"]

r = client.post(f"{BASE}/auth/login", json={"email": email, "password": "senha12345"})
provider = {"Authorization": f"Bearer {r.json()['accessToken']}"}
client.post(f"{BASE}/providers/me/photos", files={"file": ("capa.png", PNG, "image/png")}, headers=provider)

client.post(f"{BASE}/admin/providers/{provider_id}/approve", headers=admin)

user_email = f"demo-user-{run_id}@teste.com"
client.post(f"{BASE}/auth/register", json={"name": "Cliente Demo", "email": user_email, "password": "senha12345"})
r = client.post(f"{BASE}/auth/login", json={"email": user_email, "password": "senha12345"})
user = {"Authorization": f"Bearer {r.json()['accessToken']}"}
client.post(
    f"{BASE}/providers/{provider_id}/reviews",
    json={"rating": 5, "comment": "Serviço excelente, chegou no horário e resolveu tudo."},
    headers=user,
)

print(provider_id)
