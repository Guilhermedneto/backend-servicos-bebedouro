"""Testa o fluxo de planos (dev, sem Stripe: planos pagos ativam na hora)."""

import base64
import os
import random
import sys

import httpx

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000/api")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin12345")
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
client = httpx.Client(timeout=30.0)
rid = os.urandom(3).hex()
n = 0


def step(msg):
    global n
    n += 1
    print(f"[{n:02d}] {msg}")


def expect(cond, msg):
    if not cond:
        print(f"FALHOU: {msg}")
        sys.exit(1)


def auth(t):
    return {"Authorization": f"Bearer {t}"}


def random_cpf():
    d = [random.randint(0, 9) for _ in range(9)]
    for pos in (9, 10):
        s = sum(d[i] * (pos + 1 - i) for i in range(pos))
        v = (s * 10) % 11
        d.append(0 if v == 10 else v)
    return "".join(map(str, d))


r = client.post(f"{BASE}/auth/login", json={"email": "admin@servicosbebedouro.com.br", "password": ADMIN_PASSWORD})
admin = auth(r.json()["accessToken"])
r = client.post(f"{BASE}/admin/categories", json={"name": f"Cat {rid}"}, headers=admin)
cat = r.json()["id"]

step("Catálogo público de planos")
r = client.get(f"{BASE}/plans")
plans = r.json()
expect(plans["free"]["photoLimit"] == 0, "free 0 fotos")
expect(plans["essential"]["photoLimit"] == 5, "essential 5 fotos")
expect(plans["premium"]["photoLimit"] == 10, "premium 10 fotos")
expect(plans["essential"]["pricing"]["monthly"]["amount"] == 1800, "essential mensal 1800")
expect(plans["premium"]["pricing"]["annual"]["installment"] == 2000, "premium anual 12x2000")


def register(plan, cycle):
    email = f"prov-{plan}-{rid}@teste.com"
    body = {
        "name": f"Prov {plan} {rid}",
        "document": random_cpf(),
        "categoryIds": [cat],
        "bairro": "Centro",
        "rua": "Rua X",
        "numero": "1",
        "whatsapp": "17999998888",
        "description": f"Serviços {plan}.",
        "email": email,
        "password": "senha12345",
        "plan": plan,
        "billingCycle": cycle,
    }
    r = client.post(f"{BASE}/auth/register-provider", json=body)
    expect(r.status_code == 201, f"cadastro {plan}: {r.status_code} {r.text}")
    pid = r.json()["id"]
    r2 = client.post(f"{BASE}/auth/login", json={"email": email, "password": "senha12345"})
    return pid, auth(r2.json()["accessToken"])


step("Cadastro premium sem billingCycle para 422")
r = client.post(
    f"{BASE}/auth/register-provider",
    json={
        "name": "x", "document": random_cpf(), "categoryIds": [cat], "bairro": "C", "rua": "R",
        "numero": "1", "whatsapp": "17999998888", "description": "d",
        "email": f"nocycle-{rid}@teste.com", "password": "senha12345", "plan": "premium",
    },
)
expect(r.status_code == 422, f"premium sem ciclo: {r.status_code}")

step("Cadastra free, essential(mensal), premium(anual) — pagos ativam na hora (dev)")
free_id, free_tok = register("free", None)
ess_id, ess_tok = register("essential", "monthly")
prem_id, prem_tok = register("premium", "annual")

step("Free: subscriptionStatus active; upload de foto bloqueado (PHOTOS_NOT_ALLOWED)")
r = client.get(f"{BASE}/providers/me", headers=free_tok)
expect(r.json()["subscriptionStatus"] == "active" and r.json()["photoLimit"] == 0, f"free me: {r.json()}")
r = client.post(f"{BASE}/providers/me/photos", files={"file": ("a.png", PNG, "image/png")}, headers=free_tok)
expect(r.status_code == 422 and r.json()["error"]["code"] == "PHOTOS_NOT_ALLOWED", f"free foto: {r.status_code} {r.text}")

step("Essential: 5 fotos ok, 6ª barra")
for i in range(5):
    r = client.post(f"{BASE}/providers/me/photos", files={"file": (f"{i}.png", PNG, "image/png")}, headers=ess_tok)
    expect(r.status_code == 201, f"ess foto {i}: {r.text}")
r = client.post(f"{BASE}/providers/me/photos", files={"file": ("6.png", PNG, "image/png")}, headers=ess_tok)
expect(r.status_code == 422 and r.json()["error"]["code"] == "PHOTO_LIMIT_REACHED", f"ess 6ª: {r.text}")

step("Premium: até 10 fotos")
for i in range(10):
    r = client.post(f"{BASE}/providers/me/photos", files={"file": (f"{i}.png", PNG, "image/png")}, headers=prem_tok)
    expect(r.status_code == 201, f"prem foto {i}: {r.text}")
r = client.post(f"{BASE}/providers/me/photos", files={"file": ("11.png", PNG, "image/png")}, headers=prem_tok)
expect(r.status_code == 422, f"prem 11ª deveria barrar: {r.status_code}")

step("Admin aprova os três")
for pid in (free_id, ess_id, prem_id):
    r = client.post(f"{BASE}/admin/providers/{pid}/approve", headers=admin)
    expect(r.status_code == 200, f"aprovar {pid}: {r.text}")

step("Perfil público do FREE: sem fotos, sem whatsapp, sem descrição")
r = client.get(f"{BASE}/providers/{free_id}")
p = r.json()
expect(p["plan"] == "free" and p["photos"] == [] and p["whatsapp"] is None and p["description"] is None, f"free público: {p}")
expect(p["address"]["bairro"] == "Centro" and "coordinates" in p, "free mantém nome/endereço")

step("Perfil público do PREMIUM: isPremium true, fotos presentes")
r = client.get(f"{BASE}/providers/{prem_id}")
p = r.json()
expect(p["isPremium"] is True and len(p["photos"]) == 10 and p["whatsapp"], f"premium público: {p['isPremium']}")

step("Card do free na listagem: sem coverUrl e sem whatsapp")
r = client.get(f"{BASE}/providers", params={"search": rid})
cards = {c["id"]: c for c in r.json()["items"]}
expect(free_id in cards, "free aparece na listagem")
expect(cards[free_id]["coverUrl"] is None and cards[free_id]["whatsapp"] is None, f"card free: {cards[free_id]}")

step("Premium aparece PRIMEIRO na listagem (ordenação premium-first)")
ordered = [c["id"] for c in r.json()["items"]]
expect(ordered[0] == prem_id, f"premium não veio primeiro: {ordered}")

step("Endpoint de destaques retorna o premium")
r = client.get(f"{BASE}/providers/featured")
expect(any(c["id"] == prem_id for c in r.json()), "premium nos destaques")
expect(all(c["isPremium"] for c in r.json()), "destaques só premium")

step("Avaliar prestador FREE é bloqueado (403 REVIEWS_NOT_ALLOWED)")
r = client.post(f"{BASE}/auth/register", json={"name": "User", "email": f"u-{rid}@teste.com", "password": "senha12345"})
r = client.post(f"{BASE}/auth/login", json={"email": f"u-{rid}@teste.com", "password": "senha12345"})
utok = auth(r.json()["accessToken"])
r = client.post(f"{BASE}/providers/{free_id}/reviews", json={"rating": 5, "comment": "bom"}, headers=utok)
expect(r.status_code == 403 and r.json()["error"]["code"] == "REVIEWS_NOT_ALLOWED", f"review free: {r.status_code} {r.text}")
r = client.post(f"{BASE}/providers/{prem_id}/reviews", json={"rating": 5, "comment": "excelente"}, headers=utok)
expect(r.status_code == 201, f"review premium: {r.text}")

step("Downgrade premium→free: apaga fotos, vira free, sai dos destaques")
r = client.put(f"{BASE}/providers/me/plan", json={"plan": "free", "billingCycle": None}, headers=prem_tok)
expect(r.status_code == 200 and r.json()["plan"] == "free", f"downgrade: {r.text}")
r = client.get(f"{BASE}/providers/me", headers=prem_tok)
expect(r.json()["photos"] == [] and r.json()["photoLimit"] == 0, f"fotos apagadas: {r.json().get('photoLimit')}")
r = client.get(f"{BASE}/providers/featured")
expect(not any(c["id"] == prem_id for c in r.json()), "ex-premium saiu dos destaques")

step("Upgrade free→essential (dev ativa na hora)")
r = client.put(f"{BASE}/providers/me/plan", json={"plan": "essential", "billingCycle": "annual"}, headers=free_tok)
expect(r.status_code == 200 and r.json()["subscriptionStatus"] == "active", f"upgrade: {r.text}")
r = client.get(f"{BASE}/providers/me", headers=free_tok)
expect(r.json()["photoLimit"] == 5 and r.json()["plan"] == "essential", f"após upgrade: {r.json()}")

step("Admin vê plano na listagem de prestadores")
r = client.get(f"{BASE}/admin/providers", headers=admin)
by_id = {p["id"]: p for p in r.json()}
expect(by_id[ess_id]["plan"] == "essential", f"admin plano: {by_id[ess_id].get('plan')}")

print(f"\nPLANS TEST OK — {n} passos verificados.")
