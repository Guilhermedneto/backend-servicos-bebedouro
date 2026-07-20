"""Smoke test E2E da API contra o ambiente local (Cosmos emulator + Azurite).

Uso: python scripts/smoke_test.py <caminho-do-log-do-backend>
O log é usado para extrair o link de recuperação de senha e conferir o e-mail de aprovação
(modo dev: e-mails são logados em vez de enviados).
"""

import base64
import os
import re
import sys
import uuid

import httpx

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000/api")
LOG_PATH = sys.argv[1] if len(sys.argv) > 1 else None
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@servicosbebedouro.com.br")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
if not ADMIN_PASSWORD:
    print("Defina ADMIN_PASSWORD no ambiente para executar este script.")
    sys.exit(1)

# 1x1 PNG válido
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

run_id = uuid.uuid4().hex[:8]
client = httpx.Client(timeout=30.0)
step_count = 0


def step(name: str):
    global step_count
    step_count += 1
    print(f"[{step_count:02d}] {name}")


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def expect(condition: bool, message: str):
    if not condition:
        print(f"FALHOU: {message}")
        sys.exit(1)


# ---------- Admin: login e categoria ----------
step("Login do admin")
r = client.post(f"{BASE}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
expect(r.status_code == 200, f"login admin: {r.status_code} {r.text}")
admin_token = r.json()["accessToken"]

step("Admin cria categoria 'Eletricista'")
r = client.post(f"{BASE}/admin/categories", json={"name": f"Eletricista {run_id}"}, headers=auth(admin_token))
expect(r.status_code == 201, f"criar categoria: {r.status_code} {r.text}")
category_id = r.json()["id"]

step("Rota admin sem token retorna 401 / com role errada 403 (verificado adiante)")
r = client.get(f"{BASE}/admin/dashboard")
expect(r.status_code == 401, f"admin sem token: {r.status_code}")

# ---------- Cadastro de prestador ----------
step("Cadastro de prestador com CPF inválido retorna 422")
provider_email = f"prestador-{run_id}@teste.com"
payload = {
    "name": f"Eletricista João {run_id}",
    "document": "111.111.111-12",  # dígito verificador inválido
    "categoryIds": [category_id],
    "bairro": "Centro",
    "rua": "Rua Prudente de Moraes",
    "numero": "100",
    "whatsapp": "(17) 99999-8888",
    "description": "Instalações elétricas residenciais e comerciais.",
    "email": provider_email,
    "password": "senha12345",
    "plan": "essential",
    "billingCycle": "monthly",
}
r = client.post(f"{BASE}/auth/register-provider", json={**payload})
expect(r.status_code == 422, f"cpf inválido: {r.status_code} {r.text}")
expect(r.json()["error"]["code"] == "INVALID_DOCUMENT", f"código de erro: {r.text}")

step("Cadastro com mais de 4 categorias retorna 422")
r = client.post(
    f"{BASE}/auth/register-provider",
    json={**payload, "document": "529.982.247-25", "categoryIds": ["a", "b", "c", "d", "e"]},
)
expect(r.status_code == 422, f"5 categorias: {r.status_code} {r.text}")

step("Cadastro de prestador com CPF válido retorna 201 (status pendente)")
payload["document"] = "529.982.247-25"  # CPF com dígitos verificadores válidos
r = client.post(f"{BASE}/auth/register-provider", json=payload)
expect(r.status_code == 201, f"cadastro prestador: {r.status_code} {r.text}")
provider_id = r.json()["id"]
expect(r.json()["status"] == "pending", f"status inicial: {r.text}")

step("Cadastro com e-mail duplicado retorna 409")
r = client.post(f"{BASE}/auth/register", json={"name": "Outro", "email": provider_email, "password": "senha12345"})
expect(r.status_code == 409, f"email duplicado: {r.status_code} {r.text}")

step("Prestador pendente não aparece na listagem pública e perfil retorna 404")
r = client.get(f"{BASE}/providers", params={"search": run_id})
expect(r.status_code == 200 and r.json()["total"] == 0, f"listagem com pendente: {r.text}")
r = client.get(f"{BASE}/providers/{provider_id}")
expect(r.status_code == 404, f"perfil pendente: {r.status_code}")

# ---------- Fotos ----------
step("Prestador (pendente) faz login e envia 5 fotos")
r = client.post(f"{BASE}/auth/login", json={"email": provider_email, "password": "senha12345"})
expect(r.status_code == 200, f"login prestador: {r.status_code} {r.text}")
provider_token = r.json()["accessToken"]

photo_ids = []
for i in range(5):
    r = client.post(
        f"{BASE}/providers/me/photos",
        files={"file": (f"foto{i}.png", PNG, "image/png")},
        headers=auth(provider_token),
    )
    expect(r.status_code == 201, f"upload foto {i}: {r.status_code} {r.text}")
    photo_ids.append(r.json()["id"])

step("6ª foto é rejeitada com 422")
r = client.post(
    f"{BASE}/providers/me/photos",
    files={"file": ("foto6.png", PNG, "image/png")},
    headers=auth(provider_token),
)
expect(r.status_code == 422, f"6ª foto: {r.status_code} {r.text}")
expect(r.json()["error"]["code"] == "PHOTO_LIMIT_REACHED", r.text)

step("Arquivo não-imagem é rejeitado com 422")
r = client.post(
    f"{BASE}/providers/me/photos",
    files={"file": ("nota.txt", b"texto", "text/plain")},
    headers=auth(provider_token),
)
expect(r.status_code == 422, f"arquivo inválido: {r.status_code}")

step("Definir foto 3 como capa e excluir a capa — foto restante vira capa")
r = client.put(f"{BASE}/providers/me/photos/{photo_ids[2]}/cover", headers=auth(provider_token))
expect(r.status_code == 200, f"set cover: {r.status_code} {r.text}")
r = client.delete(f"{BASE}/providers/me/photos/{photo_ids[2]}", headers=auth(provider_token))
expect(r.status_code == 204, f"delete cover: {r.status_code}")
r = client.get(f"{BASE}/providers/me", headers=auth(provider_token))
photos = r.json()["photos"]
expect(len(photos) == 4 and any(p["isCover"] for p in photos), f"capa reatribuída: {r.text}")
expect(r.json()["documentMasked"].startswith("***."), f"documento mascarado: {r.json()['documentMasked']}")

step("Foto de capa acessível publicamente no Azurite")
cover_url = next(p["url"] for p in photos if p["isCover"])
r = httpx.get(cover_url, timeout=10.0)
expect(r.status_code == 200 and r.content == PNG, f"blob público: {r.status_code}")

# ---------- Aprovação ----------
step("Admin vê prestador pendente e aprova (e-mail de aprovação logado)")
r = client.get(f"{BASE}/admin/providers", params={"status": "pending"}, headers=auth(admin_token))
expect(any(p["id"] == provider_id for p in r.json()), "prestador na lista de pendentes")
r = client.post(f"{BASE}/admin/providers/{provider_id}/approve", headers=auth(admin_token))
expect(r.status_code == 200 and r.json()["status"] == "active", f"aprovar: {r.text}")

step("Prestador aprovado aparece na listagem, busca e perfil público")
r = client.get(f"{BASE}/providers", params={"search": run_id})
expect(r.json()["total"] == 1, f"listagem pós-aprovação: {r.text}")
card = r.json()["items"][0]
expect(card["coverUrl"] is not None and card["bairro"] == "Centro", f"card: {card}")
r = client.get(f"{BASE}/providers", params={"search": "centro"})
expect(any(i["id"] == provider_id for i in r.json()["items"]), "busca por bairro")
r = client.get(f"{BASE}/providers", params={"categoryId": category_id})
expect(any(i["id"] == provider_id for i in r.json()["items"]), "filtro por categoria")
for sort in ("rating", "reviews", "recent"):
    r = client.get(f"{BASE}/providers", params={"sort": sort})
    expect(r.status_code == 200, f"ordenação {sort}: {r.status_code}")
r = client.get(f"{BASE}/providers/{provider_id}")
expect(r.status_code == 200, f"perfil público: {r.status_code}")

# ---------- Avaliações ----------
step("Usuário comum se cadastra e faz login")
user_email = f"usuario-{run_id}@teste.com"
r = client.post(f"{BASE}/auth/register", json={"name": "Maria Silva", "email": user_email, "password": "senha12345"})
expect(r.status_code == 201, f"cadastro usuário: {r.status_code} {r.text}")
r = client.post(f"{BASE}/auth/login", json={"email": user_email, "password": "senha12345"})
user_token = r.json()["accessToken"]
user_refresh = r.json()["refreshToken"]
user_id = r.json()["user"]["id"]

step("Visitante não autenticado não pode avaliar (401)")
r = client.post(f"{BASE}/providers/{provider_id}/reviews", json={"rating": 5, "comment": "Ótimo!"})
expect(r.status_code == 401, f"avaliar sem login: {r.status_code}")

step("Prestador não pode avaliar (403)")
r = client.post(
    f"{BASE}/providers/{provider_id}/reviews",
    json={"rating": 5, "comment": "Auto elogio"},
    headers=auth(provider_token),
)
expect(r.status_code == 403, f"prestador avaliando: {r.status_code}")

step("Usuário avalia com 4 estrelas; média e total atualizam")
r = client.post(
    f"{BASE}/providers/{provider_id}/reviews",
    json={"rating": 4, "comment": "Muito bom, recomendo."},
    headers=auth(user_token),
)
expect(r.status_code == 201, f"criar avaliação: {r.status_code} {r.text}")
expect(r.json()["userName"] == "Maria Silva" and r.json()["createdAt"], "comentário com nome e data")
r = client.get(f"{BASE}/providers/{provider_id}")
expect(r.json()["ratingAvg"] == 4.0 and r.json()["ratingCount"] == 1, f"média: {r.text}")

step("Nota fora de 1–5 retorna 422")
r = client.post(
    f"{BASE}/providers/{provider_id}/reviews", json={"rating": 6, "comment": "x"}, headers=auth(user_token)
)
expect(r.status_code in (409, 422) and r.status_code == 422, f"nota inválida: {r.status_code}")

step("Segunda avaliação do mesmo usuário retorna 409")
r = client.post(
    f"{BASE}/providers/{provider_id}/reviews",
    json={"rating": 5, "comment": "De novo"},
    headers=auth(user_token),
)
expect(r.status_code == 409, f"avaliação duplicada: {r.status_code} {r.text}")

step("Usuário edita a própria avaliação para 5 estrelas")
r = client.put(
    f"{BASE}/providers/{provider_id}/reviews/me",
    json={"rating": 5, "comment": "Excelente, atualizado!"},
    headers=auth(user_token),
)
expect(r.status_code == 200, f"editar avaliação: {r.status_code} {r.text}")
r = client.get(f"{BASE}/providers/{provider_id}")
expect(r.json()["ratingAvg"] == 5.0 and r.json()["ratingCount"] == 1, f"média pós-edição: {r.text}")

step("Listagem pública de avaliações exibe nome e data")
r = client.get(f"{BASE}/providers/{provider_id}/reviews")
expect(len(r.json()) == 1 and r.json()[0]["userName"] == "Maria Silva", f"reviews: {r.text}")

step("Usuário exclui a própria avaliação; média zera")
r = client.delete(f"{BASE}/providers/{provider_id}/reviews/me", headers=auth(user_token))
expect(r.status_code == 204, f"excluir avaliação: {r.status_code}")
r = client.get(f"{BASE}/providers/{provider_id}")
expect(r.json()["ratingCount"] == 0, f"contagem pós-exclusão: {r.text}")

step("Usuário reavalia (para testes de admin)")
r = client.post(
    f"{BASE}/providers/{provider_id}/reviews",
    json={"rating": 3, "comment": "Comentário para moderação."},
    headers=auth(user_token),
)
review_id = r.json()["id"]

# ---------- Refresh / logout ----------
step("Refresh token rotaciona e o antigo é revogado")
r = client.post(f"{BASE}/auth/refresh", json={"refreshToken": user_refresh})
expect(r.status_code == 200, f"refresh: {r.status_code} {r.text}")
new_refresh = r.json()["refreshToken"]
r = client.post(f"{BASE}/auth/refresh", json={"refreshToken": user_refresh})
expect(r.status_code == 401, f"refresh reutilizado: {r.status_code}")
r = client.post(f"{BASE}/auth/logout", json={"refreshToken": new_refresh})
expect(r.status_code == 204, f"logout: {r.status_code}")
r = client.post(f"{BASE}/auth/refresh", json={"refreshToken": new_refresh})
expect(r.status_code == 401, f"refresh pós-logout: {r.status_code}")

# ---------- Recuperação de senha ----------
step("Fluxo de recuperação de senha (token extraído do log dev)")
r = client.post(f"{BASE}/auth/forgot-password", json={"email": user_email})
expect(r.status_code == 202, f"forgot: {r.status_code}")
r = client.post(f"{BASE}/auth/forgot-password", json={"email": "nao-existe@teste.com"})
expect(r.status_code == 202, "resposta genérica para e-mail inexistente")

expect(LOG_PATH is not None, "caminho do log do backend não informado")
log_text = open(LOG_PATH, encoding="utf-8", errors="ignore").read()
tokens = re.findall(r"redefinir-senha\?token=([A-Za-z0-9_\-]+)", log_text)
expect(len(tokens) >= 1, "link de recuperação não encontrado no log")
reset_token = tokens[-1]

r = client.post(f"{BASE}/auth/reset-password", json={"token": reset_token, "newPassword": "novasenha123"})
expect(r.status_code == 204, f"reset: {r.status_code} {r.text}")
r = client.post(f"{BASE}/auth/reset-password", json={"token": reset_token, "newPassword": "outrasenha123"})
expect(r.status_code == 400, f"token reutilizado: {r.status_code}")
r = client.post(f"{BASE}/auth/login", json={"email": user_email, "password": "senha12345"})
expect(r.status_code == 401, "senha antiga deixou de funcionar")
r = client.post(f"{BASE}/auth/login", json={"email": user_email, "password": "novasenha123"})
expect(r.status_code == 200, f"login com nova senha: {r.status_code}")
user_token = r.json()["accessToken"]

step("E-mail de aprovação registrado no log (modo dev)")
expect("Cadastro aprovado" in log_text, "e-mail de aprovação não encontrado no log")

# ---------- CPF criptografado no banco ----------
step("CPF/CNPJ armazenado criptografado no Cosmos")
sys.path.insert(0, ".")
from app.infrastructure.cosmos_db import init_cosmos, get_container, PROVIDERS  # noqa: E402

init_cosmos(retries=3)
doc = get_container(PROVIDERS).read_item(item=provider_id, partition_key=provider_id)
expect("document" not in doc, "campo 'document' em texto claro não deve existir")
expect(doc["documentEncrypted"].startswith("gAAAA"), f"documentEncrypted não parece Fernet: {doc['documentEncrypted'][:12]}")
expect("52998224725" not in str(doc), "CPF em texto claro encontrado no documento!")

# ---------- Admin: dashboard, moderação, categorias, usuários ----------
step("Dashboard do admin com os 4 totais")
r = client.get(f"{BASE}/admin/dashboard", headers=auth(admin_token))
d = r.json()
expect(
    d["totalUsers"] >= 1 and d["activeProviders"] >= 1 and d["pendingProviders"] >= 0 and d["totalReviews"] >= 1,
    f"dashboard: {d}",
)

step("Usuário comum recebe 403 em rota admin")
r = client.get(f"{BASE}/admin/dashboard", headers=auth(user_token))
expect(r.status_code == 403, f"user em rota admin: {r.status_code}")

step("Admin remove comentário")
r = client.delete(f"{BASE}/admin/reviews/{provider_id}/{review_id}", headers=auth(admin_token))
expect(r.status_code == 204, f"admin remove review: {r.status_code}")
r = client.get(f"{BASE}/providers/{provider_id}")
expect(r.json()["ratingCount"] == 0, "média recalculada após moderação")

step("Categoria em uso não pode ser removida (409); desativação funciona")
r = client.delete(f"{BASE}/admin/categories/{category_id}", headers=auth(admin_token))
expect(r.status_code == 409, f"categoria em uso: {r.status_code} {r.text}")
r = client.put(
    f"{BASE}/admin/categories/{category_id}",
    json={"name": f"Eletricista {run_id}", "active": False},
    headers=auth(admin_token),
)
expect(r.status_code == 200, f"desativar categoria: {r.status_code}")
r = client.get(f"{BASE}/categories")
expect(not any(c["id"] == category_id for c in r.json()), "categoria desativada fora do dropdown")

step("Admin desativa usuário — login passa a ser bloqueado")
r = client.post(f"{BASE}/admin/users/{user_id}/deactivate", headers=auth(admin_token))
expect(r.status_code == 200, f"desativar usuário: {r.status_code}")
r = client.post(f"{BASE}/auth/login", json={"email": user_email, "password": "novasenha123"})
expect(r.status_code == 403, f"login desativado: {r.status_code}")

step("Admin remove usuário e avaliações associadas")
r = client.delete(f"{BASE}/admin/users/{user_id}", headers=auth(admin_token))
expect(r.status_code == 204, f"remover usuário: {r.status_code}")

step("Admin desativa prestador — some da listagem e perfil vira 404")
r = client.post(f"{BASE}/admin/providers/{provider_id}/deactivate", headers=auth(admin_token))
expect(r.status_code == 200, f"desativar prestador: {r.status_code}")
r = client.get(f"{BASE}/providers/{provider_id}")
expect(r.status_code == 404, f"perfil desativado: {r.status_code}")

step("Prestador desativado ainda consegue logar e ver o próprio perfil")
r = client.post(f"{BASE}/auth/login", json={"email": provider_email, "password": "senha12345"})
expect(r.status_code == 200 and r.json()["user"]["providerStatus"] == "deactivated", f"login desativado: {r.text}")

step("Admin remove prestador — perfil, fotos e conta somem")
r = client.delete(f"{BASE}/admin/providers/{provider_id}", headers=auth(admin_token))
expect(r.status_code == 204, f"remover prestador: {r.status_code}")
r = httpx.get(cover_url, timeout=10.0)
expect(r.status_code == 404, f"blob removido: {r.status_code}")
r = client.post(f"{BASE}/auth/login", json={"email": provider_email, "password": "senha12345"})
expect(r.status_code == 401, "conta do prestador removida")

step("Categoria sem uso pode ser removida")
r = client.delete(f"{BASE}/admin/categories/{category_id}", headers=auth(admin_token))
expect(r.status_code == 204, f"remover categoria: {r.status_code}")

print(f"\nSMOKE TEST OK — {step_count} passos verificados.")
