"""
Risk Hesaplama Modülü
Sürekli Envanter Analizi - Risk Puanlama Sistemi
"""

# ==================== RİSK KRİTERLERİ ====================
# Kriter 1: Bölge Ortalama Üstü - max 20 puan
# Kriter 2: İç Hırsızlık - max 12 puan
# Pozitif Açık Kontrolü - 20 puan (anormal durum)

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


# ==================== KRİTER 2: İÇ HIRSIZLIK ====================

def tespit_supheli_urun(iptal_satir_miktari, fark_miktari, satis_fiyati, min_fiyat=100):
    """
    İç hırsızlık şüphesi olan ürünü tespit et.

    Mantık: Personel ürünü satıyor, parayı alıyor, sonra satırı iptal ediyor.
    Formül: fark - iptal = 0 ise ÇOK YÜKSEK risk

    Örnek: fark = -5, iptal = -4 → fark - iptal = -1 → 0'a yakın = YÜKSEK

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
    # fark = -5, iptal = -4 → sonuc = -5 - (-4) = -1
    # fark = -5, iptal = -5 → sonuc = -5 - (-5) = 0 (tam eşleşme)
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


def hesapla_ic_hirsizlik_riski(supheli_urun_sayisi):
    """
    Kriter 2: İç Hırsızlık Riski

    Bir birimde (SM/BS/Mağaza) kaç şüpheli ürün varsa ona göre puan.
    Max puan: 12

    Puanlama:
    - > 10 şüpheli ürün: 12 puan
    - 6-10 şüpheli ürün: 8 puan
    - 3-5 şüpheli ürün: 4 puan
    - 1-2 şüpheli ürün: 2 puan
    - 0: 0 puan
    """
    if supheli_urun_sayisi > 10:
        return 12
    elif supheli_urun_sayisi >= 6:
        return 8
    elif supheli_urun_sayisi >= 3:
        return 4
    elif supheli_urun_sayisi >= 1:
        return 2
    return 0


def hesapla_toplam_risk_v2(acik, birim_oran, bolge_oran, ic_hirsizlik_sayisi=0):
    """
    Tüm kriterleri hesapla ve topla (v2 - iç hırsızlık dahil)

    Kriterler:
    - Pozitif Açık: 20 puan (anormal)
    - Bölge Ortalama Üstü: max 20 puan
    - İç Hırsızlık: max 12 puan
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

    # İç hırsızlık
    ic_puan = hesapla_ic_hirsizlik_riski(ic_hirsizlik_sayisi)
    puan += ic_puan
    detay['ic_hirsizlik'] = ic_puan
    detay['ic_hirsizlik_sayisi'] = ic_hirsizlik_sayisi

    return puan, detay


def hesapla_birim_risk_v2(birim_data, bolge_toplam_acik, bolge_toplam_satis, ic_hirsizlik_sayisi=0):
    """
    Bir birim (SM/BS/Mağaza) için risk hesapla (v2 - iç hırsızlık dahil)

    birim_data: dict with keys: acik, satis
    bolge_toplam_acik: Bölge toplam açık
    bolge_toplam_satis: Bölge toplam satış
    ic_hirsizlik_sayisi: Bu birimdeki şüpheli ürün sayısı

    Returns: dict with puan, detay, seviye, emoji
    """
    acik = birim_data.get('acik', 0)
    satis = birim_data.get('satis', 0)

    # Oranları hesapla
    birim_oran = (acik / satis * 100) if satis != 0 else 0
    bolge_oran = (bolge_toplam_acik / bolge_toplam_satis * 100) if bolge_toplam_satis != 0 else 0

    # Risk puanı hesapla (v2)
    puan, detay = hesapla_toplam_risk_v2(acik, birim_oran, bolge_oran, ic_hirsizlik_sayisi)

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
