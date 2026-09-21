"""TLS-контекст с российским доверенным корневым сертификатом.

Нужен для доступа к госресурсам (zakupki.gov.ru и др.), которые используют
Russian Trusted Root CA. Проверка сертификата при этом не отключается.
"""

from __future__ import annotations

import ssl
from pathlib import Path

#: Путь к вложенному сертификату (certs/ в корне проекта).
RUSSIAN_CA_PATH = Path(__file__).resolve().parent.parent.parent / "certs" / "russian_trusted_root_ca.pem"


def russian_ssl_context() -> ssl.SSLContext:
    """Стандартный контекст + российский корневой CA, если он есть."""
    context = ssl.create_default_context()
    if RUSSIAN_CA_PATH.exists():
        context.load_verify_locations(str(RUSSIAN_CA_PATH))
    return context
