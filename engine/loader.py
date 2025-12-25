"""
Veri Yükleme Modülü - KURAL 0: Supabase = DATA SOURCE
=======================================================
- Supabase client fonksiyon içinde yaşar, dışarı sızmaz
- Return edilen şey: list, dict veya pandas DataFrame
- ASLA client veya response objesi return edilmez
"""

import pandas as pd
from typing import Optional, List, Tuple
import os


TABLE_NAME = "surekli_envanter_v2"


def create_client_for_write():
    """
    Supabase client oluştur - FONKSİYON İÇİNDE YAŞAR.
    Her çağrıda yeni client, cache edilmez.
    """
    try:
        from supabase import create_client

        # Önce streamlit secrets dene, sonra env vars
        url = None
        key = None

        try:
            import streamlit as st
            url = st.secrets.get("SUPABASE_URL", "")
            key = st.secrets.get("SUPABASE_KEY", "")
        except:
            pass

        if not url or not key:
            url = os.environ.get("SUPABASE_URL", "")
            key = os.environ.get("SUPABASE_KEY", "")

        if url and key:
            return create_client(url, key)
        return None
    except Exception:
        return None


def fetch_periods() -> List[str]:
    """
    Dönemleri getir - PURE DATA döner.
    Cache'lenebilir çünkü sadece list döner.
    """
    client = create_client_for_write()
    if client is None:
        return []

    try:
        result = client.table(TABLE_NAME).select('envanter_donemi').execute()
        if result.data:
            donemler = list(set(r['envanter_donemi'] for r in result.data if r['envanter_donemi']))
            return sorted(donemler, reverse=True)
    except Exception:
        pass
    return []


def fetch_sms() -> List[str]:
    """
    SM listesini getir - PURE DATA döner.
    Cache'lenebilir çünkü sadece list döner.
    """
    client = create_client_for_write()
    if client is None:
        return ["ALİ AKÇAY", "ŞADAN YURDAKUL", "VELİ GÖK", "GİZEM TOSUN"]

    try:
        result = client.table(TABLE_NAME).select('satis_muduru').execute()
        if result.data:
            sms = list(set(r['satis_muduru'] for r in result.data if r['satis_muduru']))
            return sorted(sms)
    except Exception:
        pass
    return ["ALİ AKÇAY", "ŞADAN YURDAKUL", "VELİ GÖK", "GİZEM TOSUN"]


def fetch_data_for_periods(
    donemler: List[str],
    satis_muduru: Optional[str] = None,
    columns: str = '*'
) -> List[dict]:
    """
    Dönemler için veri çek - PURE DATA (list of dict) döner.
    Cache'lenebilir çünkü sadece list döner.

    Args:
        donemler: Envanter dönemleri
        satis_muduru: Opsiyonel SM filtresi
        columns: Çekilecek kolonlar

    Returns:
        List[dict]: Ham veri listesi
    """
    client = create_client_for_write()
    if client is None or not donemler:
        return []

    all_data = []
    batch_size = 1000  # Daha büyük batch = daha az sorgu

    for donem in donemler:
        offset = 0
        retry_count = 0
        max_retries = 3

        while True:
            try:
                query = client.table(TABLE_NAME).select(columns).eq('envanter_donemi', donem)

                if satis_muduru:
                    query = query.eq('satis_muduru', satis_muduru)

                result = query.limit(batch_size).offset(offset).execute()

                if result.data:
                    all_data.extend(result.data)
                    if len(result.data) < batch_size:
                        break
                    offset += batch_size
                    retry_count = 0
                else:
                    break
            except Exception:
                retry_count += 1
                if retry_count >= max_retries:
                    break
                import time
                time.sleep(0.5)
                continue

    return all_data


def fetch_ic_hirsizlik_data(donemler: List[str]) -> List[dict]:
    """
    İç hırsızlık analizi için veri çek - PURE DATA döner.
    """
    columns = 'magaza_kodu,magaza_tanim,satis_muduru,bolge_sorumlusu,malzeme_kodu,malzeme_tanimi,iptal_satir_miktari,fark_miktari,satis_fiyati,fark_tutari,yukleme_tarihi'
    return fetch_data_for_periods(donemler, columns=columns)


# ==================== BACKWARD COMPATIBILITY ALIASES ====================
# bootstrap.py bu eski isimleri kullanıyor
def load_raw_data(client, donemler: List[str], satis_muduru: Optional[str] = None, batch_size: int = 1000) -> pd.DataFrame:
    """Backward compatibility - bootstrap.py için"""
    columns = '*'
    all_data = fetch_data_for_periods(donemler, satis_muduru, columns)
    if all_data:
        return pd.DataFrame(all_data)
    return pd.DataFrame()


def load_periods(client) -> List[str]:
    """Backward compatibility - bootstrap.py için"""
    return fetch_periods()


def load_sms(client) -> List[str]:
    """Backward compatibility - bootstrap.py için"""
    return fetch_sms()


def fetch_envanter_serisi(magaza_kodu: str, malzeme_kodu: str) -> List[dict]:
    """
    Mağaza+ürün için envanter serisini getir - PURE DATA döner.
    """
    client = create_client_for_write()
    if client is None:
        return []

    try:
        result = client.table(TABLE_NAME).select(
            'envanter_sayisi,sayim_miktari,fark_tutari,fire_tutari,envanter_donemi'
        ).eq('magaza_kodu', magaza_kodu).eq('malzeme_kodu', malzeme_kodu).order(
            'envanter_sayisi', desc=False
        ).execute()

        if result.data:
            return result.data
    except Exception:
        pass
    return []
