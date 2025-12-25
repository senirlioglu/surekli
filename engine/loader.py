"""
Veri Yükleme Modülü
===================
Supabase'den veri çekme fonksiyonları.
Streamlit'e bağımlı DEĞİL (pure function).
"""

import pandas as pd
from typing import Optional, List
import os


def get_supabase_client():
    """
    Supabase client oluştur.
    NOT: Bu fonksiyon Streamlit secrets'a erişmez,
    environment variables veya parametre bekler.
    """
    try:
        from supabase import create_client, Client

        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")

        if url and key:
            return create_client(url, key)
        return None
    except Exception:
        return None


def load_raw_data(
    client,
    donemler: List[str],
    satis_muduru: Optional[str] = None,
    batch_size: int = 500
) -> pd.DataFrame:
    """
    Supabase'den ham veri çek.

    Args:
        client: Supabase client
        donemler: Envanter dönemleri listesi
        satis_muduru: Opsiyonel SM filtresi
        batch_size: Batch boyutu

    Returns:
        DataFrame: Ham envanter verisi
    """
    if client is None or not donemler:
        return pd.DataFrame()

    TABLE_NAME = "surekli_envanter_v2"

    all_data = []

    for donem in donemler:
        offset = 0
        while True:
            try:
                query = client.table(TABLE_NAME).select(
                    'magaza_kodu,magaza_tanim,satis_muduru,bolge_sorumlusu,'
                    'depolama_kosulu,fark_tutari,fire_tutari,satis_hasilati,'
                    'sayim_miktari,envanter_sayisi,malzeme_kodu,malzeme_tanimi,'
                    'satis_fiyati,iptal_satir_miktari,fark_miktari,yukleme_tarihi,'
                    'envanter_donemi'
                ).eq('envanter_donemi', donem)

                if satis_muduru:
                    query = query.eq('satis_muduru', satis_muduru)

                query = query.limit(batch_size).offset(offset)
                result = query.execute()

                if result.data:
                    all_data.extend(result.data)
                    if len(result.data) < batch_size:
                        break
                    offset += batch_size
                else:
                    break
            except Exception:
                break

    if all_data:
        return pd.DataFrame(all_data)
    return pd.DataFrame()


def load_periods(client) -> List[str]:
    """Mevcut dönemleri getir."""
    if client is None:
        return []

    try:
        result = client.table("surekli_envanter_v2").select('envanter_donemi').execute()
        if result.data:
            donemler = list(set(r['envanter_donemi'] for r in result.data if r['envanter_donemi']))
            return sorted(donemler, reverse=True)
    except Exception:
        pass
    return []


def load_sms(client) -> List[str]:
    """Mevcut SM listesini getir."""
    if client is None:
        return ["ALİ AKÇAY", "ŞADAN YURDAKUL", "VELİ GÖK", "GİZEM TOSUN"]

    try:
        result = client.table("surekli_envanter_v2").select('satis_muduru').execute()
        if result.data:
            sms = list(set(r['satis_muduru'] for r in result.data if r['satis_muduru']))
            return sorted(sms)
    except Exception:
        pass
    return ["ALİ AKÇAY", "ŞADAN YURDAKUL", "VELİ GÖK", "GİZEM TOSUN"]
