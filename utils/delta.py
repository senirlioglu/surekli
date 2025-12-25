"""
Delta Hesaplama Modülü
Sürekli Envanter Analizi - Envanter Dönemleri Arası Fark Hesaplama

Mantık:
- Her hafta Pazartesi yeni envanter dosyası yüklenir
- Aynı mağaza+ürün+dönem+envanter_sayısı varsa: ATLA
- Yeni envanter_sayısı varsa: Önceki envanterden delta hesapla
- Yeni dönem başladığında: Herşey sıfırdan başlar
"""

from datetime import datetime


def normalize_envanter_donemi(donem_str):
    """
    Envanter dönemini normalize et (tutarlı format için)
    Örnek: "2025-12", "Aralık 2025", "12/2025" → "2025-12"
    """
    if not donem_str:
        return None

    donem_str = str(donem_str).strip()

    # Zaten YYYY-MM formatındaysa
    if len(donem_str) == 7 and donem_str[4] == '-':
        return donem_str

    # Diğer formatları dene
    try:
        # "12/2025" veya "12.2025" formatı
        for sep in ['/', '.', '-']:
            if sep in donem_str:
                parts = donem_str.split(sep)
                if len(parts) == 2:
                    if len(parts[0]) == 4:  # YYYY-MM
                        return f"{parts[0]}-{parts[1].zfill(2)}"
                    elif len(parts[1]) == 4:  # MM-YYYY
                        return f"{parts[1]}-{parts[0].zfill(2)}"
    except:
        pass

    return donem_str  # Olduğu gibi döndür


def get_existing_records(supabase_client, magaza_kodlari, envanter_donemi):
    """
    Supabase'den mevcut kayıtları getir

    Returns:
        dict: {(magaza_kodu, barkod, envanter_sayisi): record_data}
    """
    if not magaza_kodlari:
        return {}

    try:
        # Dönem için tüm kayıtları çek
        response = supabase_client.table('surekli_envanter_v2').select(
            'magaza_kodu, barkod, envanter_donemi, envanter_sayisi, fark_miktari, fark_kumulatif'
        ).eq('envanter_donemi', envanter_donemi).in_('magaza_kodu', list(magaza_kodlari)).execute()

        records = {}
        for row in response.data:
            key = (
                str(row.get('magaza_kodu', '')),
                str(row.get('barkod', '')),
                int(row.get('envanter_sayisi', 0))
            )
            records[key] = row

        return records
    except Exception as e:
        print(f"Supabase okuma hatası: {e}")
        return {}


def get_previous_inventory(existing_records, magaza_kodu, barkod, current_envanter_sayisi):
    """
    Aynı dönemde bir önceki envanter sayısının verisini getir

    Args:
        existing_records: Mevcut kayıtlar dict'i
        magaza_kodu: Mağaza kodu
        barkod: Ürün barkodu
        current_envanter_sayisi: Şu anki envanter sayısı

    Returns:
        dict veya None: Önceki envanter verisi
    """
    # current_envanter_sayisi'ndan küçük en büyük envanter_sayisi'nı bul
    previous = None
    max_previous_sayisi = 0

    for (m, b, e), record in existing_records.items():
        if m == str(magaza_kodu) and b == str(barkod) and e < current_envanter_sayisi:
            if e > max_previous_sayisi:
                max_previous_sayisi = e
                previous = record

    return previous


def calculate_delta(current_kumulatif, previous_record):
    """
    Delta (fark) hesapla

    Args:
        current_kumulatif: Excel'den gelen kümülatif değer
        previous_record: Önceki envanter kaydı (dict veya None)

    Returns:
        float: Delta değeri
    """
    if previous_record is None:
        # İlk envanter, delta = kümülatif
        return current_kumulatif

    previous_kumulatif = previous_record.get('fark_kumulatif', 0) or 0
    return current_kumulatif - previous_kumulatif


def should_skip_record(existing_records, magaza_kodu, barkod, envanter_sayisi):
    """
    Bu kayıt atlanmalı mı? (Zaten var mı?)

    Returns:
        bool: True = atla, False = işle
    """
    key = (str(magaza_kodu), str(barkod), int(envanter_sayisi))
    return key in existing_records


def process_inventory_data(df, existing_records, column_mapping):
    """
    Envanter verisini işle ve delta hesapla

    Args:
        df: Pandas DataFrame (Excel'den)
        existing_records: Mevcut Supabase kayıtları
        column_mapping: Sütun adları mapping'i

    Returns:
        list: İşlenmiş ve eklenecek kayıtlar
        dict: İstatistikler (atlanan, eklenen, vs.)
    """
    col_magaza = column_mapping.get('magaza_kodu', 'Mağaza Kodu')
    col_barkod = column_mapping.get('barkod', 'Malzeme Kodu')
    col_envanter_donemi = column_mapping.get('envanter_donemi', 'Envanter Dönemi')
    col_envanter_sayisi = column_mapping.get('envanter_sayisi', 'Envanter Sayisi')
    col_fark_miktari = column_mapping.get('fark_miktari', 'Fark Miktarı')

    records_to_insert = []
    stats = {
        'total': len(df),
        'skipped': 0,
        'new': 0,
        'with_previous': 0
    }

    for _, row in df.iterrows():
        magaza_kodu = str(row.get(col_magaza, '')).strip()
        barkod = str(row.get(col_barkod, '')).strip().replace('.0', '')
        envanter_donemi = normalize_envanter_donemi(row.get(col_envanter_donemi, ''))

        try:
            envanter_sayisi = int(float(row.get(col_envanter_sayisi, 0)))
        except:
            envanter_sayisi = 0

        try:
            fark_kumulatif = float(row.get(col_fark_miktari, 0))
        except:
            fark_kumulatif = 0

        # Zaten var mı kontrol et
        if should_skip_record(existing_records, magaza_kodu, barkod, envanter_sayisi):
            stats['skipped'] += 1
            continue

        # Önceki envanteri bul
        previous = get_previous_inventory(existing_records, magaza_kodu, barkod, envanter_sayisi)

        # Delta hesapla
        fark_delta = calculate_delta(fark_kumulatif, previous)

        if previous:
            stats['with_previous'] += 1
        else:
            stats['new'] += 1

        # Kayıt oluştur
        record = {
            'magaza_kodu': magaza_kodu,
            'barkod': barkod,
            'envanter_donemi': envanter_donemi,
            'envanter_sayisi': envanter_sayisi,
            'fark_kumulatif': fark_kumulatif,
            'fark_miktari': fark_delta,  # Delta değeri
            # Diğer alanlar row'dan eklenecek
        }

        records_to_insert.append((row, record))

    return records_to_insert, stats


def get_delta_summary(records_with_delta):
    """
    Delta özeti oluştur

    Returns:
        dict: Özet istatistikler
    """
    if not records_with_delta:
        return {
            'count': 0,
            'total_delta': 0,
            'avg_delta': 0,
            'max_delta': 0,
            'min_delta': 0
        }

    deltas = [r[1].get('fark_miktari', 0) for r in records_with_delta]

    return {
        'count': len(deltas),
        'total_delta': sum(deltas),
        'avg_delta': sum(deltas) / len(deltas) if deltas else 0,
        'max_delta': max(deltas),
        'min_delta': min(deltas)
    }
