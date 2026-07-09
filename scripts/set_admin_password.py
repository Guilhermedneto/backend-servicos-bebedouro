"""Troca a senha do administrador existente no Cosmos (usa o .env para conexão).

Uso: defina NEW_ADMIN_PASSWORD no ambiente e execute. Sessões ativas são revogadas.
"""

import os
import sys

sys.path.insert(0, ".")

from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.infrastructure.cosmos_db import init_cosmos  # noqa: E402
from app.infrastructure.repositories import CosmosUserRepository  # noqa: E402

new_password = os.environ.get("NEW_ADMIN_PASSWORD", "")
if len(new_password) < 12:
    print("Defina NEW_ADMIN_PASSWORD com pelo menos 12 caracteres.")
    sys.exit(1)

settings = get_settings()
init_cosmos(retries=3)
users = CosmosUserRepository()
admin = users.find_by_email(settings.admin_email)
if not admin:
    print(f"Admin {settings.admin_email} não encontrado.")
    sys.exit(1)

admin["passwordHash"] = hash_password(new_password)
admin["refreshJtis"] = {}
users.update(admin)
print(f"Senha do admin ({settings.admin_email}) atualizada e sessões revogadas.")
