"""
Risk Skorlama Modülü
====================
Risk puanı hesaplama fonksiyonları.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, List

from .weights import load_weights, RISK_LEVELS, MAX_SCORE
from .rules import RISK_RULES


def get_risk_level(score: int) -> Tuple[str, str, str]:
    """
    Puana göre risk seviyesi belirle.

    Args:
        score: Risk puanı (0-100)

    Returns:
        Tuple: (seviye_label, css_class, emoji)
    """
    if score >= 60:
        return "KRİTİK", "kritik", "🔴"
    elif score >= 40:
        return "RİSKLİ", "riskli", "🟠"
    elif score >= 20:
        return "DİKKAT", "dikkat", "🟡"
    return "TEMİZ", "temiz", "🟢"


def tespit_supheli_urun(
    iptal_satir_miktari: float,
    fark_miktari: float,
    satis_fiyati: float,
    min_fiyat: float = 100
) -> Dict[str, Any]:
    """
    İç hırsızlık şüphesi olan ürünü tespit et.

    Mantık: Personel ürünü satıyor, parayı alıyor, sonra satırı iptal ediyor.
    Formül: fark - iptal = 0 ise ÇOK YÜKSEK risk

    Args:
        iptal_satir_miktari: İptal edilen satır miktarı
        fark_miktari: Envanter farkı (negatif = kayıp)
        satis_fiyati: Ürün satış fiyatı
        min_fiyat: Minimum fiyat eşiği (default 100 TL)

    Returns:
        dict: {'supheli': bool, 'risk': str, 'fark': float}
    """
    # Fiyat kontrolü
    if satis_fiyati < min_fiyat:
        return {'supheli': False, 'risk': None, 'fark': None}

    # Sadece fark negatif olanlara bak (kayıp var)
    if fark_miktari >= 0:
        return {'supheli': False, 'risk': None, 'fark': None}

    # İptal yoksa şüpheli değil
    if iptal_satir_miktari == 0:
        return {'supheli': False, 'risk': None, 'fark': None}

    # Formül: fark - iptal
    sonuc = fark_miktari - iptal_satir_miktari
    fark_mutlak = abs(sonuc)

    if fark_mutlak == 0:
        return {'supheli': True, 'risk': 'ÇOK YÜKSEK', 'fark': 0}
    elif fark_mutlak <= 2:
        return {'supheli': True, 'risk': 'YÜKSEK', 'fark': fark_mutlak}
    elif fark_mutlak <= 5:
        return {'supheli': True, 'risk': 'ORTA', 'fark': fark_mutlak}
    elif fark_mutlak <= 10:
        return {'supheli': True, 'risk': 'DÜŞÜK', 'fark': fark_mutlak}

    return {'supheli': False, 'risk': None, 'fark': None}


def calculate_risk_score(
    data: Dict[str, Any],
    weights: Dict[str, Any] = None
) -> Tuple[int, Dict[str, int]]:
    """
    Bir birim için toplam risk puanı hesapla.

    Args:
        data: Hesaplama için gerekli veriler
        weights: Risk ağırlıkları (opsiyonel)

    Returns:
        Tuple: (toplam_puan, detay_dict)
    """
    if weights is None:
        weights = load_weights().get('risk_weights', {})

    total_score = 0
    details = {}

    for rule in RISK_RULES:
        score = rule.evaluate(data, weights)
        total_score += score
        details[rule.name] = score

    # Max 100
    total_score = min(MAX_SCORE, total_score)

    return total_score, details


def calculate_magaza_scores(
    df: pd.DataFrame,
    weights: Dict[str, Any] = None
) -> pd.DataFrame:
    """
    Mağaza bazlı risk skorlarını hesapla.

    Args:
        df: Ham envanter verisi
        weights: Risk ağırlıkları

    Returns:
        DataFrame: Skorlanmış mağaza özeti
    """
    if df.empty:
        return pd.DataFrame()

    if weights is None:
        weights = load_weights().get('risk_weights', {})

    # Mağaza bazlı gruplama
    magaza_ozet = df.groupby(['magaza_kodu', 'magaza_tanim']).agg({
        'fark_tutari': 'sum',
        'fire_tutari': 'sum',
        'satis_hasilati': 'sum',
        'malzeme_kodu': 'count'
    }).reset_index()

    magaza_ozet.columns = ['magaza_kodu', 'magaza_tanim', 'fark', 'fire', 'satis', 'urun_sayisi']

    # Açık hesapla
    magaza_ozet['acik'] = magaza_ozet['fark'] + magaza_ozet['fire']
    magaza_ozet['acik_pct'] = np.where(
        magaza_ozet['satis'] > 0,
        magaza_ozet['acik'] / magaza_ozet['satis'] * 100,
        0
    )

    # Bölge ortalaması
    bolge_ort = magaza_ozet['acik_pct'].mean() if len(magaza_ozet) > 0 else 1

    # Her mağaza için iç hırsızlık sayısı hesapla
    def count_ic_hirsizlik(magaza_kodu):
        mag_df = df[df['magaza_kodu'] == magaza_kodu]
        count = 0
        for _, row in mag_df.iterrows():
            result = tespit_supheli_urun(
                row.get('iptal_satir_miktari', 0) or 0,
                row.get('fark_miktari', 0) or 0,
                row.get('satis_fiyati', 0) or 0
            )
            if result['supheli']:
                count += 1
        return count

    # Risk skoru hesapla (vektörel olmayan kısım)
    scores = []
    for _, row in magaza_ozet.iterrows():
        data = {
            'toplam_pct': row['acik_pct'],
            'bolge_kayip_oran': bolge_ort,
            'ic_hirsizlik_count': count_ic_hirsizlik(row['magaza_kodu']),
            'sigara_count': 0,  # TODO: Sigara hesabı eklenecek
            'kronik_count': 0,  # TODO: Kronik hesabı eklenecek
            'fire_manip_count': 0,
            'kasa_adet': 0
        }
        score, details = calculate_risk_score(data, weights)
        scores.append(score)

    magaza_ozet['risk_puan'] = scores

    # Risk seviyesi
    magaza_ozet['risk_seviye'] = magaza_ozet['risk_puan'].apply(
        lambda x: get_risk_level(x)[0]
    )
    magaza_ozet['risk_emoji'] = magaza_ozet['risk_puan'].apply(
        lambda x: get_risk_level(x)[2]
    )

    return magaza_ozet.sort_values('risk_puan', ascending=False)
