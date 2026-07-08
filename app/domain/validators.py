import re
import unicodedata

from app.core.errors import ValidationFailedError

FIXED_CITY = "Bebedouro"


def normalize_text(value: str) -> str:
    """Minúsculas e sem acentos — usado para busca e ordenação alfabética pt-BR."""
    decomposed = unicodedata.normalize("NFD", value.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _validate_cpf(cpf: str) -> bool:
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for position in (9, 10):
        total = sum(int(cpf[i]) * (position + 1 - i) for i in range(position))
        digit = (total * 10) % 11
        if digit == 10:
            digit = 0
        if digit != int(cpf[position]):
            return False
    return True


def _validate_cnpj(cnpj: str) -> bool:
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    weights_first = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights_second = [6] + weights_first
    for weights, position in ((weights_first, 12), (weights_second, 13)):
        total = sum(int(cnpj[i]) * weights[i] for i in range(position))
        digit = total % 11
        digit = 0 if digit < 2 else 11 - digit
        if digit != int(cnpj[position]):
            return False
    return True


def validate_document(document: str) -> tuple[str, str]:
    """Returns (normalized_digits, type) where type is 'cpf' or 'cnpj'."""
    digits = _only_digits(document)
    if len(digits) == 11:
        if not _validate_cpf(digits):
            raise ValidationFailedError(
                "CPF inválido: dígitos verificadores não conferem.",
                code="INVALID_DOCUMENT",
                details={"field": "document"},
            )
        return digits, "cpf"
    if len(digits) == 14:
        if not _validate_cnpj(digits):
            raise ValidationFailedError(
                "CNPJ inválido: dígitos verificadores não conferem.",
                code="INVALID_DOCUMENT",
                details={"field": "document"},
            )
        return digits, "cnpj"
    raise ValidationFailedError(
        "Documento inválido: informe um CPF (11 dígitos) ou CNPJ (14 dígitos).",
        code="INVALID_DOCUMENT",
        details={"field": "document"},
    )


def validate_whatsapp(number: str) -> str:
    digits = _only_digits(number)
    if len(digits) == 13 and digits.startswith("55"):
        digits = digits[2:]
    if len(digits) not in (10, 11) or not (11 <= int(digits[:2]) <= 99):
        raise ValidationFailedError(
            "WhatsApp inválido: informe DDD + número (10 ou 11 dígitos).",
            code="INVALID_WHATSAPP",
            details={"field": "whatsapp"},
        )
    return digits


def mask_document(digits: str, doc_type: str) -> str:
    if doc_type == "cpf":
        return f"***.{digits[3:6]}.{digits[6:9]}-**"
    return f"**.{digits[2:5]}.{digits[5:8]}/****-**"
