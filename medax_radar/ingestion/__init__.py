"""Адаптеры источников данных."""

from .base import SourceAdapter, RawRecord
from .sample import SampleAdapter
from .roszdravnadzor import RoszdravnadzorAdapter
from .fns import FnsAdapter
from .zakupki import ZakupkiAdapter
from .competitor import CompetitorAdapter

# Реестр источников: ключ совпадает с config/sources.json -> sources.<key>
ADAPTERS: dict[str, type[SourceAdapter]] = {
    "roszdravnadzor_licenses": RoszdravnadzorAdapter,
    "fns_companies": FnsAdapter,
    "zakupki_tenders": ZakupkiAdapter,
    "competitor_sites": CompetitorAdapter,
}


def available_adapters() -> dict[str, type[SourceAdapter]]:
    return dict(ADAPTERS)


__all__ = [
    "SourceAdapter",
    "RawRecord",
    "SampleAdapter",
    "RoszdravnadzorAdapter",
    "FnsAdapter",
    "ZakupkiAdapter",
    "CompetitorAdapter",
    "ADAPTERS",
    "available_adapters",
]
