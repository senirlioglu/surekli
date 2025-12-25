"""
Risk Ağırlıkları ve Konfigürasyon
=================================
weights.json dosyasından ağırlık okuma.
"""

import json
import os
from typing import Dict, Any

# Varsayılan değerler
DEFAULT_WEIGHTS = {
    "risk_weights": {
        "toplam_oran": {
            "high": {"threshold": 2.0, "points": 40},
            "medium": {"threshold": 1.5, "points": 25},
            "low": {"threshold": 1.0, "points": 15}
        },
        "ic_hirsizlik": {
            "high": {"threshold": 50, "points": 30},
            "medium": {"threshold": 30, "points": 20},
            "low": {"threshold": 15, "points": 10}
        },
        "sigara": {
            "high": {"threshold": 5, "points": 35},
            "low": {"threshold": 0, "points": 20}
        },
        "kronik": {
            "high": {"threshold": 100, "points": 15},
            "low": {"threshold": 50, "points": 10}
        },
        "fire_manipulasyon": {
            "high": {"threshold": 10, "points": 20},
            "low": {"threshold": 5, "points": 10}
        },
        "kasa_10tl": {
            "high": {"threshold": 20, "points": 15},
            "low": {"threshold": 10, "points": 10}
        }
    },
    "risk_levels": {
        "kritik": 60,
        "riskli": 40,
        "dikkat": 20
    },
    "max_risk_score": 100
}

# Risk seviyeleri
RISK_LEVELS = {
    "kritik": {"min": 60, "emoji": "🔴", "label": "KRİTİK"},
    "riskli": {"min": 40, "emoji": "🟠", "label": "RİSKLİ"},
    "dikkat": {"min": 20, "emoji": "🟡", "label": "DİKKAT"},
    "temiz": {"min": 0, "emoji": "🟢", "label": "TEMİZ"}
}

MAX_SCORE = 100


def load_weights(config_path: str = None) -> Dict[str, Any]:
    """
    Risk ağırlıklarını config dosyasından yükle.

    Args:
        config_path: weights.json dosya yolu (opsiyonel)

    Returns:
        dict: Risk ağırlıkları
    """
    if config_path is None:
        # Varsayılan yollar
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '..', 'weights.json'),
            os.path.join(os.path.dirname(__file__), 'weights.json'),
            'weights.json',
            '/mount/src/envanter-risk-analizi/weights.json'
        ]
    else:
        possible_paths = [config_path]

    for path in possible_paths:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            continue

    return DEFAULT_WEIGHTS


def get_risk_thresholds() -> Dict[str, int]:
    """Risk seviye eşiklerini döndür."""
    weights = load_weights()
    return weights.get("risk_levels", DEFAULT_WEIGHTS["risk_levels"])
