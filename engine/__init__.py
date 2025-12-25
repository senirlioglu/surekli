"""
Engine Modülü - Risk Hesaplama Motoru
=====================================

MEVCUT FONKSİYON HARİTASI (Aşama 0 Analizi):

Veri Yükleme:
- loader.py: Supabase'den veri çekme
  - get_supabase_client() -> Client
  - load_raw_data(donemler, sm) -> DataFrame
  - load_ic_hirsizlik_data(donemler) -> DataFrame

Konfigürasyon:
- weights.py: Risk ağırlıkları ve config
  - load_weights() -> dict
  - RISK_LEVELS, MAX_SCORE

Risk Kuralları:
- rules.py: Risk kural tanımları
  - RiskRule dataclass
  - RISK_RULES list

Skorlama:
- scorer.py: Risk hesaplama fonksiyonları
  - calculate_risk_score(row, weights) -> int
  - get_risk_level(score) -> str
  - tespit_supheli_urun(...) -> dict

Bootstrap:
- bootstrap.py: Tek noktadan veri + skor
  - build_dataset(donemler, sm) -> DataFrame (scored)
"""

from .bootstrap import build_dataset
from .scorer import calculate_risk_score, get_risk_level
from .weights import load_weights

__all__ = ['build_dataset', 'calculate_risk_score', 'get_risk_level', 'load_weights']
