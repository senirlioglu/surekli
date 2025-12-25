"""
Risk Hesaplama Modülü
Sürekli Envanter Analizi - Risk Puanlama Sistemi
"""

# ==================== RİSK KRİTERLERİ ====================
# Her kriter max 20 puan
# Toplam max puan: kriter sayısı * 20

def hesapla_pozitif_acik_riski(acik):
    """
    Kriter: Pozitif Açık Kontrolü
    Açık normalde negatif olmalı (kayıp). Pozitif açık anormal.

    Pozitif açık = 20 puan (maksimum risk)
    """
    if acik > 0:
        return 20
    return 0


def hesapla_bolge_ortalama_ustu_riski(birim_oran, bolge_oran):
    """
    Kriter 1: Bölge Ortalama Üstü Oran

    Birim (SM/BS/Mağaza) açık oranını bölge ortalamasıyla karşılaştırır.
    Oran = Toplam Açık / Toplam Satış (negatif değer)

    Katsayı = birim_oran / bolge_oran
    (Her iki oran da negatif olduğundan, daha kötü olan daha büyük katsayı verir)

    Puanlama:
    - 2.00x ve üzeri: 20 puan
    - 1.50x - 2.00x: 10 puan
    - 1.25x - 1.50x: 5 puan
    - 1.25x altı: 0 puan
    """
    # Bölge oranı 0 ise karşılaştırma yapılamaz
    if bolge_oran == 0:
        return 0

    # Her iki oran da negatif olmalı
    # Daha negatif = daha kötü
    # Katsayı hesapla (mutlak değerlerle)
    if bolge_oran == 0 or birim_oran == 0:
        katsayi = 0
    else:
        # Negatif değerler için: -10 / -5 = 2 (2 kat daha kötü)
        katsayi = abs(birim_oran) / abs(bolge_oran)

    if katsayi >= 2.0:
        return 20
    elif katsayi >= 1.5:
        return 10
    elif katsayi >= 1.25:
        return 5
    return 0


def hesapla_toplam_risk(acik, birim_oran, bolge_oran):
    """
    Tüm kriterleri hesapla ve topla
    Şimdilik: Kriter 1 (Bölge Ortalama Üstü) + Pozitif Açık
    """
    puan = 0
    detay = {}

    # Pozitif açık kontrolü
    pozitif_puan = hesapla_pozitif_acik_riski(acik)
    puan += pozitif_puan
    detay['pozitif_acik'] = pozitif_puan

    # Bölge ortalama üstü
    bolge_puan = hesapla_bolge_ortalama_ustu_riski(birim_oran, bolge_oran)
    puan += bolge_puan
    detay['bolge_ortalama_ustu'] = bolge_puan

    return puan, detay


def get_risk_seviyesi(puan):
    """
    Toplam puana göre risk seviyesi belirle
    """
    if puan >= 60:
        return "KRİTİK", "kritik", "🔴"
    elif puan >= 40:
        return "RİSKLİ", "riskli", "🟠"
    elif puan >= 20:
        return "DİKKAT", "dikkat", "🟡"
    return "TEMİZ", "temiz", "🟢"


def hesapla_birim_risk(birim_data, bolge_toplam_acik, bolge_toplam_satis):
    """
    Bir birim (SM/BS/Mağaza) için risk hesapla

    birim_data: dict with keys: acik, satis
    bolge_toplam_acik: Bölge toplam açık
    bolge_toplam_satis: Bölge toplam satış

    Returns: dict with puan, detay, seviye, emoji
    """
    acik = birim_data.get('acik', 0)
    satis = birim_data.get('satis', 0)

    # Oranları hesapla
    birim_oran = (acik / satis * 100) if satis != 0 else 0
    bolge_oran = (bolge_toplam_acik / bolge_toplam_satis * 100) if bolge_toplam_satis != 0 else 0

    # Risk puanı hesapla
    puan, detay = hesapla_toplam_risk(acik, birim_oran, bolge_oran)

    # Seviye belirle
    seviye, css_class, emoji = get_risk_seviyesi(puan)

    return {
        'puan': puan,
        'detay': detay,
        'seviye': seviye,
        'css_class': css_class,
        'emoji': emoji,
        'birim_oran': birim_oran,
        'bolge_oran': bolge_oran,
        'katsayi': abs(birim_oran) / abs(bolge_oran) if bolge_oran != 0 else 0
    }
