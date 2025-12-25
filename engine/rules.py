"""
Risk Kuralları
==============
Risk hesaplama kuralları ve eşik değerleri.
"""

from dataclasses import dataclass
from typing import Callable, Optional, Dict, Any


@dataclass
class RiskRule:
    """Bir risk kuralı tanımı."""
    name: str
    max_points: int
    description: str
    evaluate: Callable[[Dict[str, Any]], int]


def rule_toplam_oran(data: Dict[str, Any], weights: Dict) -> int:
    """
    Toplam açık oranı kuralı.
    Kayıp oranı bölge ortalamasına göre değerlendirilir.
    """
    kayip_oran = data.get('toplam_pct', 0)
    bolge_ort = data.get('bolge_kayip_oran', 1)

    if bolge_ort > 0:
        ratio = abs(kayip_oran) / abs(bolge_ort)
    else:
        ratio = abs(kayip_oran)

    w = weights.get('toplam_oran', {})

    if ratio >= w.get('high', {}).get('threshold', 2.0):
        return w.get('high', {}).get('points', 40)
    elif ratio >= w.get('medium', {}).get('threshold', 1.5):
        return w.get('medium', {}).get('points', 25)
    elif ratio >= w.get('low', {}).get('threshold', 1.0):
        return w.get('low', {}).get('points', 15)
    return 0


def rule_ic_hirsizlik(data: Dict[str, Any], weights: Dict) -> int:
    """
    İç hırsızlık kuralı.
    Şüpheli ürün sayısına göre puan.
    """
    count = data.get('ic_hirsizlik_count', 0)
    w = weights.get('ic_hirsizlik', {})

    if count >= w.get('high', {}).get('threshold', 50):
        return w.get('high', {}).get('points', 30)
    elif count >= w.get('medium', {}).get('threshold', 30):
        return w.get('medium', {}).get('points', 20)
    elif count >= w.get('low', {}).get('threshold', 15):
        return w.get('low', {}).get('points', 10)
    return 0


def rule_sigara(data: Dict[str, Any], weights: Dict) -> int:
    """
    Sigara açığı kuralı.
    Her sigara kritik.
    """
    count = data.get('sigara_count', 0)
    w = weights.get('sigara', {})

    if count > w.get('high', {}).get('threshold', 5):
        return w.get('high', {}).get('points', 35)
    elif count > w.get('low', {}).get('threshold', 0):
        return min(count * 4, w.get('high', {}).get('points', 35))
    return 0


def rule_kronik(data: Dict[str, Any], weights: Dict) -> int:
    """
    Kronik açık kuralı.
    İki dönem üst üste açık varsa.
    """
    count = data.get('kronik_count', 0)
    w = weights.get('kronik', {})

    if count >= w.get('high', {}).get('threshold', 100):
        return w.get('high', {}).get('points', 15)
    elif count >= w.get('low', {}).get('threshold', 50):
        return w.get('low', {}).get('points', 10)
    return 0


def rule_fire_manipulasyon(data: Dict[str, Any], weights: Dict) -> int:
    """
    Fire manipülasyonu kuralı.
    Fire var ama açık da artıyorsa.
    """
    count = data.get('fire_manip_count', 0)
    w = weights.get('fire_manipulasyon', {})

    if count >= w.get('high', {}).get('threshold', 10):
        return w.get('high', {}).get('points', 20)
    elif count >= w.get('low', {}).get('threshold', 5):
        return w.get('low', {}).get('points', 10)
    return 0


def rule_kasa_10tl(data: Dict[str, Any], weights: Dict) -> int:
    """
    10 TL altı ürün kuralı.
    Kasa önü ürünlerinde fazla açık şüpheli.
    """
    count = abs(data.get('kasa_adet', 0))
    w = weights.get('kasa_10tl', {})

    if count > w.get('high', {}).get('threshold', 20):
        return w.get('high', {}).get('points', 15)
    elif count > w.get('low', {}).get('threshold', 10):
        return w.get('low', {}).get('points', 10)
    return 0


# Tüm kurallar listesi
RISK_RULES = [
    RiskRule(
        name="toplam_oran",
        max_points=40,
        description="Kayıp oranı (bölge ortalamasına göre)",
        evaluate=rule_toplam_oran
    ),
    RiskRule(
        name="ic_hirsizlik",
        max_points=30,
        description="İç hırsızlık şüphesi",
        evaluate=rule_ic_hirsizlik
    ),
    RiskRule(
        name="sigara",
        max_points=35,
        description="Sigara açığı",
        evaluate=rule_sigara
    ),
    RiskRule(
        name="kronik",
        max_points=15,
        description="Kronik açık",
        evaluate=rule_kronik
    ),
    RiskRule(
        name="fire_manipulasyon",
        max_points=20,
        description="Fire manipülasyonu",
        evaluate=rule_fire_manipulasyon
    ),
    RiskRule(
        name="kasa_10tl",
        max_points=15,
        description="10 TL altı ürünler",
        evaluate=rule_kasa_10tl
    )
]
