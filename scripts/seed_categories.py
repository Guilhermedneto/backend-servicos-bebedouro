"""Cadastra o conjunto padrão de categorias via API admin. Idempotente: pula as já existentes."""

import os
import sys

import httpx

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000/api")

CATEGORIES = [
    "Advogado",
    "Arquiteto",
    "Azulejista",
    "Babá",
    "Buffet / Garçom freelancer",
    "Cabeleireiro(a)",
    "Chaveiro",
    "Contador",
    "Costureiro(a) / Alfaiate",
    "Cozinheiro / Chef particular",
    "Cuidador de idosos",
    "Dedetizador",
    "Desentupidor",
    "Designer gráfico",
    "Diarista / Faxineiro(a)",
    "DJ / Sonorizador",
    "Dog walker / Adestrador de animais",
    "Eletricista",
    "Encanador",
    "Esteticista",
    "Fotógrafo",
    "Gesseiro",
    "Instalador de alarmes e câmeras",
    "Instalador de ar-condicionado",
    "Jardineiro",
    "Manicure / Pedicure",
    "Maquiador(a)",
    "Marceneiro",
    "Massagista",
    "Mecânico",
    "Motorista / Mototaxista",
    "Nutricionista",
    "Organizador(a) de eventos",
    "Pedreiro",
    "Personal trainer",
    "Pintor",
    "Pintor de veículos / Funileiro",
    "Podólogo",
    "Porteiro / Zelador",
    "Professor particular / Tutor",
    "Psicólogo",
    "Salão de Beleza",
    "Segurança / Vigilante",
    "Serralheiro",
    "Soldador",
    "Tapeceiro",
    "Técnico em informática",
    "Técnico em refrigeração",
    "Veterinário domiciliar",
    "Vidraceiro",
]

client = httpx.Client(timeout=30.0)
r = client.post(
    f"{BASE}/auth/login",
    json={"email": "admin@servicosbebedouro.com.br", "password": "admin12345"},
)
if r.status_code != 200:
    print(f"login admin falhou: {r.status_code} {r.text}")
    sys.exit(1)
admin = {"Authorization": f"Bearer {r.json()['accessToken']}"}

created, skipped = 0, 0
for name in CATEGORIES:
    r = client.post(f"{BASE}/admin/categories", json={"name": name}, headers=admin)
    if r.status_code == 201:
        created += 1
    elif r.status_code == 409:
        skipped += 1
    else:
        print(f"erro em '{name}': {r.status_code} {r.text}")
        sys.exit(1)

print(f"Categorias: {created} criadas, {skipped} já existiam ({len(CATEGORIES)} no total).")
