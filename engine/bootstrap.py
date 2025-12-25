"""
Bootstrap Modülü
================
Tek noktadan veri yükleme ve skorlama.
Streamlit'e bağımlı DEĞİL (pure function).
"""

import pandas as pd
from typing import List, Optional, Dict, Any, Tuple
import time

from .loader import load_raw_data, load_periods, load_sms
from .scorer import calculate_magaza_scores, tespit_supheli_urun, get_risk_level
from .weights import load_weights


def build_dataset(
    client,
    donemler: List[str],
    satis_muduru: Optional[str] = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Veri yükle ve risk skorlarını hesapla.

    Bu fonksiyon Streamlit'e bağımlı DEĞİL.
    Cache decorator'ları app.py'de wrapper ile uygulanmalı.

    Args:
        client: Supabase client
        donemler: Envanter dönemleri
        satis_muduru: Opsiyonel SM filtresi

    Returns:
        Tuple: (scored_df, metadata)
        - scored_df: Risk skorlu mağaza özeti
        - metadata: Yükleme istatistikleri
    """
    start_time = time.perf_counter()

    # 1. Ham veri yükle
    load_start = time.perf_counter()
    raw_df = load_raw_data(client, donemler, satis_muduru)
    load_time = time.perf_counter() - load_start

    if raw_df.empty:
        return pd.DataFrame(), {
            'raw_rows': 0,
            'scored_rows': 0,
            'load_time': load_time,
            'score_time': 0,
            'total_time': time.perf_counter() - start_time
        }

    # 2. Ağırlıkları yükle
    weights = load_weights()

    # 3. Risk skorlarını hesapla
    score_start = time.perf_counter()
    scored_df = calculate_magaza_scores(raw_df, weights.get('risk_weights', {}))
    score_time = time.perf_counter() - score_start

    total_time = time.perf_counter() - start_time

    metadata = {
        'raw_rows': len(raw_df),
        'scored_rows': len(scored_df),
        'load_time': load_time,
        'score_time': score_time,
        'total_time': total_time,
        'donemler': donemler,
        'satis_muduru': satis_muduru
    }

    return scored_df, metadata


def build_dataset_with_raw(
    client,
    donemler: List[str],
    satis_muduru: Optional[str] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Veri yükle, ham veriyi de döndür (detay ekranları için).

    Returns:
        Tuple: (raw_df, scored_df, metadata)
    """
    start_time = time.perf_counter()

    # 1. Ham veri yükle
    load_start = time.perf_counter()
    raw_df = load_raw_data(client, donemler, satis_muduru)
    load_time = time.perf_counter() - load_start

    if raw_df.empty:
        return pd.DataFrame(), pd.DataFrame(), {
            'raw_rows': 0,
            'scored_rows': 0,
            'load_time': load_time,
            'score_time': 0,
            'total_time': time.perf_counter() - start_time
        }

    # 2. Ağırlıkları yükle
    weights = load_weights()

    # 3. Risk skorlarını hesapla
    score_start = time.perf_counter()
    scored_df = calculate_magaza_scores(raw_df, weights.get('risk_weights', {}))
    score_time = time.perf_counter() - score_start

    total_time = time.perf_counter() - start_time

    metadata = {
        'raw_rows': len(raw_df),
        'scored_rows': len(scored_df),
        'load_time': load_time,
        'score_time': score_time,
        'total_time': total_time,
        'donemler': donemler,
        'satis_muduru': satis_muduru
    }

    return raw_df, scored_df, metadata


# Yardımcı fonksiyonlar (re-export)
def get_periods(client) -> List[str]:
    """Mevcut dönemleri getir."""
    return load_periods(client)


def get_sms(client) -> List[str]:
    """Mevcut SM listesini getir."""
    return load_sms(client)
