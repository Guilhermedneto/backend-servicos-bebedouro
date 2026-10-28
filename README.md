# Servicos Bebedouro — Backend

API do guia de prestadores de servico de Bebedouro-SP. O prestador se cadastra,
escolhe um plano e aparece na busca; quem procura filtra por categoria, texto e
proximidade.

O front-end fica em
[frontend-servicos-bebedouro](https://github.com/Guilhermedneto/frontend-servicos-bebedouro).

## Stack

| Camada | Tecnologia |
|---|---|
| API | Python / FastAPI |
| Dados | Azure Cosmos DB |
| Busca | Azure AI Search |
| Fotos | Azure Blob Storage |
| Geocodificacao | Nominatim (OpenStreetMap) |
| Cobranca | Stripe (assinatura recorrente) |
| E-mail | servico proprio em `infrastructure/email.py` |

## Arquitetura

O projeto segue **clean architecture**, com as dependencias apontando para
dentro:

```
app/
  domain/           # regra de negocio pura, sem dependencia externa
    entities.py       # Role, ProviderStatus, BusinessType
    plans.py          # planos, ciclo de cobranca, limites por plano
    trial.py          # periodo de teste
    validators.py
  application/      # casos de uso
    commands/         # o que escreve
    queries/          # o que le
    interfaces.py     # as portas que a infraestrutura implementa
  infrastructure/   # os adaptadores: cosmos, blob, ai_search, stripe, nominatim
  presentation/     # FastAPI: routers, schemas, deps
```

O ganho pratico: `domain/plans.py` nao importa Stripe. Trocar de gateway mexe em
`infrastructure/stripe_service.py` e em nada mais.

## Planos

| Plano | Fotos |
|---|---|
| `free` | 0 |
| `essential` | 5 |
| `premium` | ver `PLAN_PHOTO_LIMITS` |

Estados de assinatura: `active` (sempre, no free), `pending_payment` (pago,
esperando o Stripe confirmar) e `canceled` (volta a exibir como free). O estado
intermediario existe porque a confirmacao do Stripe e assincrona — sem ele, o
prestador pagaria e continuaria aparecendo como gratuito ate o webhook chegar.

## Rodar local

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
cp .env.example .env     # preencha as credenciais
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

Documentacao interativa em `/docs`.

## Rotas

`auth`, `providers`, `categories`, `search`, `plans`, `stripe` (webhooks),
`admin`.
