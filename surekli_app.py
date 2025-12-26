import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime, timedelta
import json
import os
import sys

# Modül yolunu ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.risk import (
    hesapla_birim_risk, get_risk_seviyesi,
    hesapla_birim_risk_v2, tespit_supheli_urun
)

# ==================== SAYFA AYARI ====================
st.set_page_config(
    page_title="Sürekli Envanter Analizi",
    layout="wide",
    page_icon="📦"
)

# ==================== CSS STİLLERİ ====================
st.markdown("""
<style>
    /* Risk kutuları */
    .risk-kritik {
        background: linear-gradient(135deg, #ff4444, #cc0000);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 1.2em;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .risk-riskli {
        background: linear-gradient(135deg, #ff8c00, #ff6600);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 1.2em;
    }
    .risk-dikkat {
        background: linear-gradient(135deg, #ffd700, #ffcc00);
        color: #333;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 1.2em;
    }
    .risk-temiz {
        background: linear-gradient(135deg, #00cc66, #009944);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 1.2em;
    }

    /* Sidebar stil */
    .sidebar-header {
        font-size: 1.5em;
        font-weight: bold;
        margin-bottom: 20px;
        color: #1e3c72;
    }

    /* Metrik kartları */
    div[data-testid="stMetric"] {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #1e3c72;
    }

    /* Tab stilleri */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        border-radius: 8px 8px 0 0;
    }
</style>
""", unsafe_allow_html=True)

# ==================== LOADER IMPORT ====================
from engine.loader import (
    fetch_periods, fetch_sms, fetch_data_for_periods,
    fetch_ic_hirsizlik_data, fetch_envanter_serisi,
    create_client_for_write, TABLE_NAME
)

# Bağlantı kontrolü (sidebar)
try:
    _test_periods = fetch_periods()
    if _test_periods:
        st.sidebar.success("✅ Supabase bağlandı")
    else:
        st.sidebar.warning("⚠️ Supabase veri bulunamadı")
except Exception as e:
    st.sidebar.error(f"❌ Supabase hata: {e}")

# ==================== SESSION STATE ====================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'user_sm' not in st.session_state:
    st.session_state.user_sm = None

# ==================== KULLANICI YETKİLERİ ====================
# Rol ve SM eşleştirmeleri
USER_ROLES = {
    "ziya": {"role": "gm", "sm": None},
    "kuklaci": {"role": "gm", "sm": None},
    "sm1": {"role": "sm", "sm": "ALİ AKÇAY"},
    "sm2": {"role": "sm", "sm": "ŞADAN YURDAKUL"},
    "sm3": {"role": "sm", "sm": "VELİ GÖK"},
    "sm4": {"role": "sm", "sm": "GİZEM TOSUN"},
    "sma": {"role": "asistan", "sm": None},
}

def get_users():
    """Secrets'tan kullanıcı bilgilerini al"""
    users = {}
    try:
        # Secrets'tan [users] bölümünü oku
        if "users" in st.secrets:
            for username, password in st.secrets["users"].items():
                role_info = USER_ROLES.get(username, {"role": "user", "sm": None})
                users[username] = {
                    "password": password,
                    "role": role_info["role"],
                    "sm": role_info["sm"]
                }
    except Exception as e:
        st.error(f"Kullanıcı bilgileri okunamadı: {e}")
    return users

USERS = get_users()

# ==================== GİRİŞ SİSTEMİ ====================
def login():
    st.markdown("## 📦 Sürekli Envanter Analizi")
    st.markdown("*Haftalık Et-Tavuk, Ekmek, Meyve/Sebze Takibi*")
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 🔐 Giriş Yap")
        username = st.text_input("Kullanıcı Adı", key="login_user")
        password = st.text_input("Şifre", type="password", key="login_pass")

        if st.button("Giriş", width="stretch"):
            if username in USERS and USERS[username]["password"] == password:
                st.session_state.logged_in = True
                st.session_state.user = username
                st.session_state.user_role = USERS[username]["role"]
                st.session_state.user_sm = USERS[username]["sm"]
                st.rerun()
            else:
                st.error("Hatalı kullanıcı adı veya şifre!")

# ==================== YARDIMCI FONKSİYONLAR ====================
def format_currency(value):
    """Para formatı"""
    if abs(value) >= 1_000_000:
        return f"{value/1_000_000:.1f}M"
    elif abs(value) >= 1_000:
        return f"{value/1_000:.0f}K"
    return f"{value:,.0f}"

def get_risk_level(puan):
    """Risk seviyesi belirle"""
    if puan >= 60:
        return "🔴 KRİTİK", "kritik"
    elif puan >= 40:
        return "🟠 RİSKLİ", "riskli"
    elif puan >= 20:
        return "🟡 DİKKAT", "dikkat"
    return "🟢 TEMİZ", "temiz"

# ==================== SUPABASE VERİ FONKSİYONLARI ====================

TABLE_NAME = "surekli_envanter_v2"

# Excel -> Supabase sütun eşleştirmesi
COLUMN_MAPPING = {
    'Envanter Dönemi': 'envanter_donemi',
    'Envanter Tarihi': 'envanter_tarihi',
    'Envanter Başlangıç Tarihi': 'envanter_baslangic_tarihi',
    'Depolama Koşulu Grubu': 'depolama_kosulu_grubu',
    'Depolama Koşulu': 'depolama_kosulu',
    'Bölge Kodu': 'bolge_kodu',
    'Bölge': 'bolge',
    'Mağaza Kodu': 'magaza_kodu',
    'Mağaza Tanım': 'magaza_tanim',
    'Satış Müdürü': 'satis_muduru',
    'Bölge Sorumlusu': 'bolge_sorumlusu',
    'Ürün Grubu Kodu': 'urun_grubu_kodu',
    'Ürün Grubu Tanımı': 'urun_grubu_tanimi',
    'Mal Grubu Kodu': 'mal_grubu_kodu',
    'Mal Grubu Tanımı': 'mal_grubu_tanimi',
    'Malzeme Kodu': 'malzeme_kodu',
    'Malzeme Tanımı': 'malzeme_tanimi',
    'Satış Fiyatı': 'satis_fiyati',
    'Envanter Sayisi': 'envanter_sayisi',
    # Kümülatif alanlar (16 alan) - Excel'den gelen toplam değerler
    'Sayım Miktarı': 'sayim_miktari_kum',
    'Sayım Tutarı': 'sayim_tutari_kum',
    'Kaydi Miktar': 'kaydi_miktar_kum',
    'Kaydi Tutar': 'kaydi_tutar_kum',
    'Fark Miktarı': 'fark_miktari_kum',
    'Fark Tutarı': 'fark_tutari_kum',
    'Fire Miktarı': 'fire_miktari_kum',
    'Fire Tutarı': 'fire_tutari_kum',
    'Fark+Fire+Kısmi Envanter Miktarı': 'fark_fire_kismi_miktari_kum',
    'Fark+Fire+Kısmi Envanter Tutarı': 'fark_fire_kismi_tutari_kum',
    'Satış Miktarı': 'satis_miktari_kum',
    'Satış Hasılatı': 'satis_hasilati_kum',
    'İade Miktarı': 'iade_miktari_kum',
    'İade Tutarı': 'iade_tutari_kum',
    'İptal Satır Miktarı': 'iptal_satir_miktari_kum',
    'İptal Satır Tutarı': 'iptal_satir_tutari_kum',
    # Kümülatif takibi gerekmeyen alanlar (doğrudan kaydet)
    'İptal Fişteki Miktar': 'iptal_fisteki_miktar',
    'İptal Fiş Tutarı': 'iptal_fis_tutari',
    'İptal GP Miktarı': 'iptal_gp_miktari',
    'İptal GP TUTARI': 'iptal_gp_tutari',
}

# Delta hesaplanacak kümülatif alanlar (16 alan): (kümülatif_sütun, delta_sütun)
KUMULATIF_ALANLAR = [
    ('sayim_miktari_kum', 'sayim_miktari'),
    ('sayim_tutari_kum', 'sayim_tutari'),
    ('kaydi_miktar_kum', 'kaydi_miktar'),
    ('kaydi_tutar_kum', 'kaydi_tutar'),
    ('fark_miktari_kum', 'fark_miktari'),
    ('fark_tutari_kum', 'fark_tutari'),
    ('fire_miktari_kum', 'fire_miktari'),
    ('fire_tutari_kum', 'fire_tutari'),
    ('fark_fire_kismi_miktari_kum', 'fark_fire_kismi_miktari'),
    ('fark_fire_kismi_tutari_kum', 'fark_fire_kismi_tutari'),
    ('satis_miktari_kum', 'satis_miktari'),
    ('satis_hasilati_kum', 'satis_hasilati'),
    ('iade_miktari_kum', 'iade_miktari'),
    ('iade_tutari_kum', 'iade_tutari'),
    ('iptal_satir_miktari_kum', 'iptal_satir_miktari'),
    ('iptal_satir_tutari_kum', 'iptal_satir_tutari'),
]

def save_to_supabase(df):
    """
    Excel verisini Supabase'e kaydet (delta hesaplamalı)

    Mantık:
    - Aynı mağaza+ürün+dönem+envanter_sayısı varsa: ATLA
    - Yeni envanter_sayısı varsa: Delta hesapla ve EKLE
    - Yeni dönemde: İlk kayıt olarak ekle (delta = kümülatif)

    Unique key: magaza_kodu + malzeme_kodu + envanter_donemi + envanter_sayisi
    """
    supabase = create_client_for_write()
    if supabase is None:
        return 0, 0, 0, "Supabase bağlantısı yok"

    try:
        # Yükleme tarihi
        yukleme_tarihi = datetime.now().strftime('%Y-%m-%d')

        # 1. Önce tüm kayıtları hazırla
        all_records = []
        magaza_set = set()
        donem_set = set()

        for _, row in df.iterrows():
            record = {}
            for excel_col, db_col in COLUMN_MAPPING.items():
                if excel_col in row.index:
                    val = row[excel_col]
                    if pd.isna(val):
                        val = None
                    elif isinstance(val, pd.Timestamp):
                        val = val.strftime('%Y-%m-%d')
                    elif isinstance(val, (np.integer, np.int64)):
                        val = int(val)
                    elif isinstance(val, (np.floating, np.float64)):
                        val = float(val) if not np.isnan(val) else None
                    elif isinstance(val, str):
                        val = val.strip()
                        import re
                        if re.match(r'^-?\d+,\d+$', val):
                            try:
                                val = float(val.replace(',', '.'))
                            except:
                                pass
                    record[db_col] = val

            record['yukleme_tarihi'] = yukleme_tarihi
            all_records.append(record)

            # Mağaza ve dönem setlerini topla
            if record.get('magaza_kodu'):
                magaza_set.add(str(record['magaza_kodu']))
            if record.get('envanter_donemi'):
                donem_set.add(str(record['envanter_donemi']))

        # 2. Mevcut kayıtları çek (karşılaştırma için)
        # Tüm kümülatif alanları çek
        kum_fields = ','.join([kum for kum, _ in KUMULATIF_ALANLAR])
        select_fields = f'magaza_kodu,malzeme_kodu,envanter_sayisi,{kum_fields}'

        existing_records = {}
        for donem in donem_set:
            try:
                result = supabase.table(TABLE_NAME).select(
                    select_fields
                ).eq('envanter_donemi', donem).in_('magaza_kodu', list(magaza_set)).execute()

                if result.data:
                    for r in result.data:
                        key = (
                            str(r.get('magaza_kodu', '')),
                            str(r.get('malzeme_kodu', '')),
                            str(donem),
                            int(r.get('envanter_sayisi', 0))
                        )
                        existing_records[key] = r
            except Exception as e:
                st.warning(f"Mevcut kayıt çekme hatası: {str(e)[:50]}")

        # 3. Kayıtları filtrele ve delta hesapla
        records_to_insert = []
        skipped = 0

        for record in all_records:
            magaza = str(record.get('magaza_kodu', ''))
            malzeme = str(record.get('malzeme_kodu', ''))
            donem = str(record.get('envanter_donemi', ''))
            try:
                envanter_sayisi = int(record.get('envanter_sayisi', 0))
            except:
                envanter_sayisi = 0

            key = (magaza, malzeme, donem, envanter_sayisi)

            # Zaten varsa atla
            if key in existing_records:
                skipped += 1
                continue

            # Önceki envanteri bul (aynı dönemde, daha küçük envanter_sayisi)
            previous_record = None
            for prev_sayisi in range(envanter_sayisi - 1, 0, -1):
                prev_key = (magaza, malzeme, donem, prev_sayisi)
                if prev_key in existing_records:
                    previous_record = existing_records[prev_key]
                    break

            # TÜM kümülatif alanlar için delta hesapla
            for kum_field, delta_field in KUMULATIF_ALANLAR:
                current_kum = record.get(kum_field, 0) or 0
                previous_kum = 0
                if previous_record:
                    previous_kum = previous_record.get(kum_field, 0) or 0
                record[delta_field] = current_kum - previous_kum

            records_to_insert.append(record)

            # Bu kaydı da existing'e ekle (sonraki kayıtlar için)
            existing_records[key] = {kum: record.get(kum, 0) for kum, _ in KUMULATIF_ALANLAR}

        # 4. Yeni kayıtları ekle (insert, upsert değil)
        batch_size = 500
        inserted = 0

        for i in range(0, len(records_to_insert), batch_size):
            batch = records_to_insert[i:i+batch_size]
            try:
                # Upsert kullan ama sadece yeni kayıtlar gidecek
                result = supabase.table(TABLE_NAME).upsert(
                    batch,
                    on_conflict='magaza_kodu,malzeme_kodu,envanter_donemi,envanter_sayisi'
                ).execute()
                inserted += len(result.data) if result.data else 0
            except Exception as e:
                st.warning(f"Batch {i//batch_size + 1} hatası: {str(e)[:100]}")

        return inserted, skipped, len(all_records), "OK"

    except Exception as e:
        return 0, 0, 0, f"Hata: {str(e)}"

def get_mevcut_envanter_sayilari(magaza_kodlari, envanter_donemi):
    """
    Belirli mağazalar için mevcut envanter sayılarını getir
    Karşılaştırma için kullanılır
    """
    supabase = create_client_for_write()
    if supabase is None:
        return {}

    try:
        result = supabase.table(TABLE_NAME).select(
            'magaza_kodu,malzeme_kodu,envanter_sayisi'
        ).eq(
            'envanter_donemi', str(envanter_donemi)
        ).in_(
            'magaza_kodu', magaza_kodlari
        ).execute()

        # Dict: (magaza_kodu, malzeme_kodu) -> max(envanter_sayisi)
        mevcut = {}
        if result.data:
            for r in result.data:
                key = (r['magaza_kodu'], r['malzeme_kodu'])
                if key not in mevcut or r['envanter_sayisi'] > mevcut[key]:
                    mevcut[key] = r['envanter_sayisi']

        return mevcut

    except Exception as e:
        st.error(f"Veri çekme hatası: {e}")
        return {}


# ==================== KOLON NORMALİZASYON ====================
def _normalize_col_name(col: str) -> str:
    """
    Kolon ismini normalize et:
    - Küçük harfe çevir
    - Türkçe karakterleri dönüştür (ı->i, ş->s, ğ->g, ü->u, ö->o, ç->c, İ->i)
    - Boşlukları _ yap
    - Baştaki/sondaki boşlukları kaldır
    """
    if not isinstance(col, str):
        return str(col).lower().strip()

    col = col.lower().strip()
    # Türkçe karakter dönüşümü
    tr_map = {
        'ı': 'i', 'İ': 'i', 'ş': 's', 'Ş': 's',
        'ğ': 'g', 'Ğ': 'g', 'ü': 'u', 'Ü': 'u',
        'ö': 'o', 'Ö': 'o', 'ç': 'c', 'Ç': 'c'
    }
    for tr, en in tr_map.items():
        col = col.replace(tr, en)
    # Boşlukları _ yap
    col = col.replace(' ', '_')
    return col


# Excel kolon isimlerini iç kolon isimlerine map'le
COLUMN_NAME_MAP = {
    # Normalize edilmiş Excel kolon isimleri -> iç kolon isimleri
    'magaza_kodu': 'magaza_kodu',
    'magaza_tanim': 'magaza_tanim',
    'satis_muduru': 'satis_muduru',
    'bolge_sorumlusu': 'bolge_sorumlusu',
    'malzeme_kodu': 'malzeme_kodu',
    'malzeme_tanimi': 'malzeme_tanimi',
    'envanter_sayisi': 'envanter_sayisi',
    'fark_tutari': 'fark_tutari',
    'fire_tutari': 'fire_tutari',
    'envanter_donemi': 'envanter_donemi',
    'satis_hasilati': 'satis_hasilati',
    'sayim_miktari': 'sayim_miktari',
    'satis_fiyati': 'satis_fiyati',
    'iptal_satir_miktari': 'iptal_satir_miktari',
    'fark_miktari': 'fark_miktari',
    'depolama_kosulu': 'depolama_kosulu',
}


def normalize_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame kolon isimlerini normalize et ve standart isimlere map'le.
    """
    if df is None or df.empty:
        return df

    # Kolon isimlerini normalize et
    new_columns = {}
    for col in df.columns:
        norm_col = _normalize_col_name(col)
        if norm_col in COLUMN_NAME_MAP:
            new_columns[col] = COLUMN_NAME_MAP[norm_col]
        else:
            new_columns[col] = norm_col

    return df.rename(columns=new_columns)


def check_required_columns(df: pd.DataFrame, required: list) -> tuple:
    """
    Gerekli kolonların varlığını kontrol et.
    Returns: (success: bool, missing: list)
    """
    if df is None or df.empty:
        return False, required

    missing = [col for col in required if col not in df.columns]
    return len(missing) == 0, missing


# ==================== KRONİK HESAPLAMA HELPER (VEKTÖREL + ÖN FİLTRELEME) ====================
def _find_kronik_fast(gm_df: pd.DataFrame, value_col: str, threshold: float):
    """
    Ardışık iki envanter sayımında (envanter_sayisi ardışık) value_col < threshold koşulunu sağlayan
    mağaza+ürünleri hızlı (vektörel) bulur.
    value_col: 'fark_tutari' veya 'fire_tutari'
    threshold: ör. -500

    Optimizasyon: Önce threshold altındaki satırları filtrele, sonra sort/shift yap.
    """
    need_cols = [
        'magaza_kodu', 'magaza_tanim',
        'satis_muduru', 'bolge_sorumlusu',
        'malzeme_kodu', 'malzeme_tanimi',
        'envanter_sayisi', value_col
    ]
    for c in need_cols:
        if c not in gm_df.columns:
            return []

    # ADIM 1: Sadece gerekli kolonları al ve tip dönüşümü yap
    base = gm_df[need_cols].copy()
    base[value_col] = pd.to_numeric(base[value_col], errors='coerce').fillna(0)
    base['envanter_sayisi'] = pd.to_numeric(base['envanter_sayisi'], errors='coerce')

    # ADIM 2: ÖN FİLTRELEME - Sadece eşik altındaki satırlar (10x-100x hızlanma)
    df = base[(base[value_col] < threshold) & (base['envanter_sayisi'].notna())].copy()
    if df.empty:
        return []

    # ADIM 3: Sort + Shift
    df = df.sort_values(['magaza_kodu', 'malzeme_kodu', 'envanter_sayisi'])

    g = df.groupby(['magaza_kodu', 'malzeme_kodu'], sort=False)
    df['_prev_val'] = g[value_col].shift(1)
    df['_prev_env'] = g['envanter_sayisi'].shift(1)

    # Ardışık envanter (n-1, n) + ikisi de eşikten kötü
    mask = (
        (df['_prev_val'] < threshold) &
        (df[value_col] < threshold) &
        (df['envanter_sayisi'] == (df['_prev_env'] + 1))
    )

    hits = df[mask].copy()
    if hits.empty:
        return []

    # Her mağaza+ürün için ilk eşleşmeyi al (kronolojik olarak)
    hits = hits.groupby(['magaza_kodu', 'malzeme_kodu'], sort=False).head(1)

    out = []
    for _, r in hits.iterrows():
        out.append({
            'magaza_kodu': str(r['magaza_kodu']),
            'magaza_adi': str(r.get('magaza_tanim') or '')[:30],
            'sm': str(r.get('satis_muduru') or ''),
            'bs': str(r.get('bolge_sorumlusu') or ''),
            'malzeme_kodu': str(r['malzeme_kodu']),
            'malzeme_adi': str(r.get('malzeme_tanimi') or '')[:40],
            'onceki_env': int(r['_prev_env']),
            'sonraki_env': int(r['envanter_sayisi']),
            'onceki_val': float(r['_prev_val']),
            'sonraki_val': float(r[value_col]),
            'toplam': float(r['_prev_val'] + r[value_col]),
        })
    return out


def detect_envanter_degisimi(df, mevcut_sayilar):
    """
    Envanter sayısı değişen ürünleri tespit et
    Yeni sayım yapılmış mağazaları bulur
    """
    degisen_magazalar = set()
    degisen_urunler = []

    for _, row in df.iterrows():
        magaza = str(row.get('Mağaza Kodu', ''))
        malzeme = str(row.get('Malzeme Kodu', ''))
        yeni_sayisi = int(row.get('Envanter Sayisi', 0) or 0)

        key = (magaza, malzeme)
        mevcut_sayisi = mevcut_sayilar.get(key, 0)

        if yeni_sayisi > mevcut_sayisi:
            degisen_magazalar.add(magaza)
            degisen_urunler.append({
                'magaza_kodu': magaza,
                'malzeme_kodu': malzeme,
                'onceki_sayisi': mevcut_sayisi,
                'yeni_sayisi': yeni_sayisi,
                'fark': yeni_sayisi - mevcut_sayisi
            })

    return list(degisen_magazalar), degisen_urunler

@st.cache_data(ttl=1800, show_spinner=False)  # 30 dk cache
def get_available_periods():
    """Mevcut dönemleri getir - PURE DATA cache"""
    return fetch_periods()

@st.cache_data(ttl=1800, show_spinner=False)  # 30 dk cache
def get_available_sms():
    """Mevcut SM listesini getir - PURE DATA cache"""
    return fetch_sms()

@st.cache_data(ttl=600, show_spinner="Veri yükleniyor...")  # 10 dk cache
def get_gm_ozet_data(donemler: tuple):
    """GM Özet için verileri getir - PURE DATA cache"""
    if not donemler:
        return None

    columns = 'magaza_kodu,magaza_tanim,satis_muduru,bolge_sorumlusu,depolama_kosulu,fark_tutari,fire_tutari,satis_hasilati,sayim_miktari,envanter_sayisi,malzeme_kodu,malzeme_tanimi,satis_fiyati'
    all_data = fetch_data_for_periods(list(donemler), columns=columns)

    if all_data:
        df = pd.DataFrame(all_data)
        if 'bolge_sorumlusu' not in df.columns:
            df['bolge_sorumlusu'] = ''
        else:
            df['bolge_sorumlusu'] = df['bolge_sorumlusu'].fillna('')
        return df
    return None

# get_onceki_envanter artık kullanılmıyor - veri zaten gm_df'de


# ==================== GOOGLE SHEETS KAMERA ENTEGRASYONU ====================
IPTAL_SHEETS_ID = '1F4Th-xZ2n0jDyayy5vayIN2j-EGUzqw5Akd8mXQVh4o'
IPTAL_SHEET_NAME = 'IptalVerisi'

@st.cache_data(ttl=300, show_spinner=False)
def get_iptal_verisi_from_sheets():
    """Google Sheets'ten iptal verisini çeker (public sheet)"""
    try:
        csv_url = f'https://docs.google.com/spreadsheets/d/{IPTAL_SHEETS_ID}/gviz/tq?tqx=out:csv&sheet={IPTAL_SHEET_NAME}'
        df = pd.read_csv(csv_url, encoding='utf-8')
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        return pd.DataFrame()


@st.cache_data(ttl=1800, show_spinner=False)  # 30 dk cache - PURE DATA
def get_envanter_serisi(magaza_kodu, malzeme_kodu):
    """Belirli mağaza+ürün için tüm envanter serisini getirir - loader'dan"""
    raw_data = fetch_envanter_serisi(magaza_kodu, malzeme_kodu)
    if not raw_data:
        return []

    # Delta hesapla
    seri = []
    onceki_kum = 0
    onceki_fark = 0
    onceki_fire = 0
    for kayit in raw_data:
        env_sayisi = kayit.get('envanter_sayisi', 0) or 0
        kumulatif = float(kayit.get('sayim_miktari', 0) or 0)
        fark_kum = float(kayit.get('fark_tutari', 0) or 0)
        fire_kum = float(kayit.get('fire_tutari', 0) or 0)
        delta = kumulatif - onceki_kum
        fark_delta = fark_kum - onceki_fark
        fire_delta = fire_kum - onceki_fire
        seri.append({
            'envanter': env_sayisi,
            'delta': delta,
            'kumulatif': kumulatif,
            'fark_tutari': fark_delta,
            'fark_kumulatif': fark_kum,
            'fire_tutari': fire_delta,
            'fire_kumulatif': fire_kum,
            'donem': kayit.get('envanter_donemi', '')
        })
        onceki_kum = kumulatif
        onceki_fark = fark_kum
        onceki_fire = fire_kum

    return seri


def get_iptal_timestamps_for_magaza(magaza_kodu, malzeme_kodlari):
    """Belirli mağaza ve ürünler için iptal timestamp bilgilerini döner"""
    df_iptal = get_iptal_verisi_from_sheets()

    if df_iptal.empty:
        return {}

    # Sütun isimleri
    col_magaza = 'Mağaza - Anahtar'
    col_malzeme = 'Malzeme - Anahtar'
    col_tarih = 'Tarih - Anahtar'
    col_saat = 'Fiş Saati'
    col_miktar = 'Miktar'
    col_islem_no = 'İşlem Numarası'

    # Sütunlar yoksa index ile dene veya benzer isim ara
    cols = df_iptal.columns.tolist()
    if col_magaza not in cols and len(cols) > 7:
        col_magaza = cols[7]
    if col_malzeme not in cols and len(cols) > 17:
        col_malzeme = cols[17]
    if col_tarih not in cols and len(cols) > 3:
        col_tarih = cols[3]
    if col_saat not in cols and len(cols) > 31:
        col_saat = cols[31]
    if col_islem_no not in cols and len(cols) > 36:
        col_islem_no = cols[36]

    # Kasa sütununu dinamik bul ("Kasa" içeren ilk sütun)
    col_kasa = None
    for c in cols:
        if 'kasa' in c.lower():
            col_kasa = c
            break

    # Kodları temizle
    def clean_code(x):
        return str(x).strip().replace('.0', '')

    df_iptal[col_magaza] = df_iptal[col_magaza].apply(clean_code)
    df_iptal[col_malzeme] = df_iptal[col_malzeme].apply(clean_code)

    # Mağaza filtrele
    magaza_str = clean_code(magaza_kodu)
    df_mag = df_iptal[df_iptal[col_magaza] == magaza_str]

    if df_mag.empty:
        return {}

    malzeme_set = set(clean_code(m) for m in malzeme_kodlari)
    result = {}

    for _, row in df_mag.iterrows():
        malzeme = clean_code(row[col_malzeme])
        if malzeme not in malzeme_set:
            continue

        tarih = row.get(col_tarih, '')
        saat = row.get(col_saat, '')
        miktar = row.get(col_miktar, 0)
        islem_no = row.get(col_islem_no, '')

        # Kasa numarasını oku ve temizle
        kasa_no = ''
        if col_kasa and col_kasa in row.index:
            kasa_no_raw = row[col_kasa]
            if pd.notna(kasa_no_raw):
                kasa_no = str(kasa_no_raw).replace('.0', '').strip()

        if malzeme not in result:
            result[malzeme] = []

        result[malzeme].append({
            'tarih': tarih,
            'saat': saat,
            'miktar': miktar,
            'islem_no': islem_no,
            'kasa_no': kasa_no
        })

    return result


def get_kamera_bilgisi(malzeme_kodu, iptal_data, kamera_limit_gun=15, yukleme_tarihi=None):
    """
    Bir ürün için kamera bilgisini döner.
    kamera_limit_gun: Referans tarihten geriye kaç gün bakılacak (default 15)
    yukleme_tarihi: Dosyanın yüklendiği tarih (None ise bugünü kullan)
    """
    # Referans tarih: yükleme tarihi veya bugün
    if yukleme_tarihi:
        try:
            if isinstance(yukleme_tarihi, str):
                referans_tarih = datetime.strptime(yukleme_tarihi, '%Y-%m-%d')
            else:
                referans_tarih = yukleme_tarihi
        except:
            referans_tarih = datetime.now()
    else:
        referans_tarih = datetime.now()

    kamera_limit = referans_tarih - timedelta(days=kamera_limit_gun)

    if malzeme_kodu not in iptal_data:
        return {'bulundu': False, 'detay': '❌ İptal kaydı yok'}

    iptaller = iptal_data[malzeme_kodu]
    son_15_gun = []

    for iptal in iptaller:
        tarih_str = str(iptal['tarih'])
        try:
            for fmt in ['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y']:
                try:
                    tarih = datetime.strptime(tarih_str.split()[0], fmt)
                    break
                except:
                    continue
            else:
                continue

            if tarih >= kamera_limit:
                son_15_gun.append({**iptal, 'tarih_dt': tarih})
        except:
            pass

    if not son_15_gun:
        return {'bulundu': False, 'detay': '❌ Son 15 günde iptal yok'}

    # Tarihe göre sırala
    son_15_gun_sorted = sorted(son_15_gun, key=lambda x: x['tarih_dt'], reverse=True)

    detaylar = []
    for iptal in son_15_gun_sorted[:3]:  # Max 3 kayıt
        tarih = iptal['tarih_dt'].strftime('%d.%m.%Y')
        saat = str(iptal.get('saat', ''))[:8]
        islem_no = str(iptal.get('islem_no', ''))

        # Kasa numarası doğrudan Sheet'ten
        kasa_no = iptal.get('kasa_no', '')
        # 0, "0", boş veya nan değilse göster
        kasa_str = f"Kasa:{kasa_no}" if kasa_no and kasa_no not in ['0', '0.0', 'nan', 'None'] else ""

        detaylar.append(f"{tarih} {saat} {kasa_str}".strip())

    return {
        'bulundu': True,
        'detay': "✅ KAMERA BAK: " + " | ".join(detaylar)
    }


# ==================== İÇ HIRSIZLIK VERİ FONKSİYONLARI ====================
@st.cache_data(ttl=600, show_spinner=False)  # 10 dk cache
def get_ic_hirsizlik_data(donemler: tuple):
    """İç hırsızlık analizi için ürün bazlı veri çeker - loader'dan"""
    if not donemler:
        return None

    all_data = fetch_ic_hirsizlik_data(list(donemler))
    if all_data:
        return pd.DataFrame(all_data)
    return None


def prepare_ic_counts_vectorized(ic_df: pd.DataFrame) -> dict:
    """
    İç hırsızlık şüpheli sayılarını VEKTÖREL hesapla.
    O(n*m) yerine O(n) - dramatik hız artışı.

    Returns:
        dict with 'by_magaza', 'by_sm', 'by_bs' Series (index=birim, value=count)
    """
    if ic_df is None or ic_df.empty:
        return {'by_magaza': pd.Series(dtype=int), 'by_sm': pd.Series(dtype=int), 'by_bs': pd.Series(dtype=int)}

    # Gerekli kolonları numeric yap
    iptal = pd.to_numeric(ic_df.get('iptal_satir_miktari', 0), errors='coerce').fillna(0)
    fark = pd.to_numeric(ic_df.get('fark_miktari', 0), errors='coerce').fillna(0)
    fiyat = pd.to_numeric(ic_df.get('satis_fiyati', 0), errors='coerce').fillna(0)

    # Şüpheli koşulları (vektörel)
    # 1. fiyat >= 100
    # 2. fark < 0 (kayıp)
    # 3. iptal > 0
    # 4. abs(fark - iptal) <= 10
    sonuc = (fark - iptal).abs()
    supheli_mask = (fiyat >= 100) & (fark < 0) & (iptal > 0) & (sonuc <= 10)

    # Sadece şüphelileri al
    supheli_df = ic_df[supheli_mask]

    # Groupby ile sayımlar (tek seferde)
    result = {
        'by_magaza': supheli_df.groupby('magaza_kodu').size() if 'magaza_kodu' in supheli_df.columns else pd.Series(dtype=int),
        'by_sm': supheli_df.groupby('satis_muduru').size() if 'satis_muduru' in supheli_df.columns else pd.Series(dtype=int),
        'by_bs': supheli_df.groupby('bolge_sorumlusu').size() if 'bolge_sorumlusu' in supheli_df.columns else pd.Series(dtype=int),
        'supheli_df': supheli_df  # Detay için sakla
    }
    return result


def hesapla_ic_hirsizlik_sayisi(df, birim_col, birim_value):
    """
    Belirli bir birim (SM/BS/Mağaza) için şüpheli ürün sayısını hesapla.
    """
    if df is None or df.empty:
        return 0, []

    birim_df = df[df[birim_col] == birim_value]
    supheli_urunler = []

    for _, row in birim_df.iterrows():
        iptal = row.get('iptal_satir_miktari', 0) or 0
        fark = row.get('fark_miktari', 0) or 0
        fiyat = row.get('satis_fiyati', 0) or 0

        sonuc = tespit_supheli_urun(iptal, fark, fiyat)
        if sonuc['supheli']:
            supheli_urunler.append({
                'malzeme_kodu': row.get('malzeme_kodu', ''),
                'malzeme_tanimi': row.get('malzeme_tanimi', ''),
                'magaza_kodu': row.get('magaza_kodu', ''),
                'satis_fiyati': fiyat,
                'iptal_miktari': iptal,
                'fark_miktari': fark,
                'risk': sonuc['risk'],
                'fark_tutari': row.get('fark_tutari', 0) or 0,
                'yukleme_tarihi': row.get('yukleme_tarihi', None)
            })

    return len(supheli_urunler), supheli_urunler


# ==================== ANA UYGULAMA ====================
def main_app():
    # Sidebar
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.user}")
        st.markdown(f"*{st.session_state.user_role.upper()}*")
        st.markdown("---")

        # Menü seçenekleri - role göre
        if st.session_state.user_role == "gm":
            menu_options = ["🌍 GM Özet", "👔 SM Özet", "📥 Excel Yükle"]
        elif st.session_state.user_role == "sm":
            menu_options = ["👔 SM Özet", "📥 Excel Yükle"]
        elif st.session_state.user_role == "asistan":
            menu_options = ["👔 SM Özet", "📥 Excel Yükle"]
        else:
            menu_options = ["🌍 GM Özet", "👔 SM Özet", "📥 Excel Yükle"]

        analysis_mode = st.radio("📊 Analiz Modu", menu_options, label_visibility="collapsed")

        st.markdown("---")
        if st.button("🚪 Çıkış", width="stretch"):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.rerun()

    # ==================== SM ÖZET MODU ====================
    if analysis_mode == "👔 SM Özet":
        st.subheader("👔 SM Özet")

        # Kullanıcı -> SM eşleştirmesi
        current_user = st.session_state.user
        user_sm = st.session_state.user_sm
        is_gm = st.session_state.user_role == "gm"

        # SM ve Dönem seçimi
        col_sm, col_donem = st.columns([1, 1])

        available_sms = get_available_sms()
        available_periods = get_available_periods()

        with col_sm:
            if is_gm:
                sm_options = ["📊 TÜMÜ (Bölge)"] + available_sms
                selected_sm_option = st.selectbox("👔 Satış Müdürü", sm_options)

                if selected_sm_option == "📊 TÜMÜ (Bölge)":
                    selected_sm = None
                    display_sm = "Bölge"
                else:
                    selected_sm = selected_sm_option
                    display_sm = selected_sm
            elif user_sm:
                selected_sm = user_sm
                display_sm = user_sm
                st.selectbox("👔 Satış Müdürü", [user_sm], disabled=True)
            else:
                selected_sm = st.selectbox("👔 Satış Müdürü", available_sms)
                display_sm = selected_sm

        with col_donem:
            selected_periods = st.multiselect("📅 Dönem", available_periods, default=available_periods[:1] if available_periods else [])

        if selected_periods:
            st.markdown("---")
            st.subheader(f"📊 {display_sm} - Özet")

            # Üst metrikler
            st.markdown("### 💰 Özet Metrikler")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("💰 Toplam Satış", "0 TL", "Veri bekleniyor")
            with col2:
                st.metric("📉 Fark", "0 TL", "%0.00")
            with col3:
                st.metric("🔥 Fire", "0 TL", "%0.00")
            with col4:
                st.metric("📊 Toplam", "0 TL", "%0.00")

            # Risk dağılımı
            st.markdown("### 📊 Risk Dağılımı")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown('<div class="risk-kritik">🔴 KRİTİK: 0</div>', unsafe_allow_html=True)
            with col2:
                st.markdown('<div class="risk-riskli">🟠 RİSKLİ: 0</div>', unsafe_allow_html=True)
            with col3:
                st.markdown('<div class="risk-dikkat">🟡 DİKKAT: 0</div>', unsafe_allow_html=True)
            with col4:
                st.markdown('<div class="risk-temiz">🟢 TEMİZ: 0</div>', unsafe_allow_html=True)

            # BS Özeti
            st.markdown("### 👔 BS Özeti")
            st.info("📥 Veri yüklendikten sonra BS özeti görüntülenecek")

            # Sekmeler
            st.markdown("---")
            tabs = st.tabs(["📋 Sıralama", "🔴 Kritik", "🟠 Riskli", "🔍 Mağaza Detay", "📥 İndir"])

            with tabs[0]:
                st.subheader("📋 Mağaza Sıralaması (Risk Puanına Göre)")
                st.info("📥 Veri yüklendikten sonra mağaza sıralaması görüntülenecek")

            with tabs[1]:
                st.subheader("🔴 Kritik Mağazalar")
                st.success("Kritik mağaza yok! 🎉")

            with tabs[2]:
                st.subheader("🟠 Riskli Mağazalar")
                st.success("Riskli mağaza yok! 🎉")

            with tabs[3]:
                st.subheader("🔍 Mağaza Detay Görünümü")
                st.info("Bir mağaza seçerek detayları görüntüleyebilirsiniz.")

                mag_options = ["Mağaza seçin..."]
                selected_mag = st.selectbox("📍 Mağaza Seçin", mag_options)

                if st.button("🔍 Detayları Getir"):
                    st.warning("Önce veri yükleyin")

            with tabs[4]:
                st.subheader("📥 Rapor İndir")
                st.info("📥 Veri yüklendikten sonra Excel raporu indirebilirsiniz")

    # ==================== GM ÖZET MODU ====================
    elif analysis_mode == "🌍 GM Özet":
        st.subheader("🌍 GM Özet - Bölge Dashboard")

        # Dönem seçimi
        available_periods = get_available_periods()

        if available_periods:
            selected_periods = st.multiselect("📅 Dönem Seçin", available_periods, default=available_periods[:1])
        else:
            selected_periods = []
            st.warning("Henüz veri yüklenmemiş. SM'ler Excel yükledikçe veriler burada görünecek.")

        if selected_periods:
            # Veriyi çek (tuple for cache)
            gm_df = get_gm_ozet_data(tuple(selected_periods))

            if gm_df is not None and len(gm_df) > 0:
                # ========== TÜM HESAPLAMALARI CACHE'LE ==========
                period_key = tuple(selected_periods)

                if st.session_state.get("gm_cache_key") != period_key:
                    st.session_state["gm_cache_key"] = period_key

                    # Kolon isimlerini normalize et (1 kez)
                    gm_df = normalize_dataframe_columns(gm_df)
                    st.session_state["gm_df_normalized"] = gm_df

                    # Temel istatistikler (1 kez)
                    st.session_state["magaza_sayisi"] = gm_df['magaza_kodu'].nunique()
                    st.session_state["toplam_fark"] = gm_df['fark_tutari'].sum() if 'fark_tutari' in gm_df.columns else 0
                    st.session_state["toplam_fire"] = gm_df['fire_tutari'].sum() if 'fire_tutari' in gm_df.columns else 0
                    st.session_state["toplam_satis"] = gm_df['satis_hasilati'].sum() if 'satis_hasilati' in gm_df.columns else 0

                # Cache'den oku
                gm_df = st.session_state.get("gm_df_normalized", gm_df)
                magaza_sayisi = st.session_state.get("magaza_sayisi", 0)
                toplam_fark = st.session_state.get("toplam_fark", 0)
                toplam_fire = st.session_state.get("toplam_fire", 0)
                toplam_satis = st.session_state.get("toplam_satis", 0)
                toplam_acik = toplam_fark + toplam_fire

                # Gerekli kolonları kontrol et
                required_cols = ['magaza_kodu', 'malzeme_kodu', 'envanter_sayisi', 'fark_tutari', 'fire_tutari']
                cols_ok, missing_cols = check_required_columns(gm_df, required_cols)
                if not cols_ok:
                    st.error(f"❌ Gerekli kolonlar eksik: {', '.join(missing_cols)}")
                    st.write("Mevcut kolonlar:", list(gm_df.columns))
                    st.stop()

                st.caption(f"📊 {len(gm_df)} satır veri çekildi")

                # Oran hesapla (cache'den gelen değerlerle)
                fark_oran = (toplam_fark / toplam_satis * 100) if toplam_satis != 0 else 0
                fire_oran = (toplam_fire / toplam_satis * 100) if toplam_satis != 0 else 0
                acik_oran = (toplam_acik / toplam_satis * 100) if toplam_satis != 0 else 0

                st.markdown("---")
                st.subheader(f"📊 Bölge Özeti - {magaza_sayisi} Mağaza")

                # Kategori bazlı hesapla
                kat_data = {}
                if 'depolama_kosulu' in gm_df.columns:
                    kat_ozet = gm_df.groupby('depolama_kosulu').agg({
                        'fark_tutari': 'sum',
                        'fire_tutari': 'sum',
                        'satis_hasilati': 'sum'
                    }).reset_index()

                    for _, row in kat_ozet.iterrows():
                        kat = str(row['depolama_kosulu'] or '').upper()
                        satis = row['satis_hasilati']
                        fark = row['fark_tutari']
                        fire = row['fire_tutari']
                        acik = fark + fire

                        # Emoji belirle
                        if 'ET' in kat or 'TAVUK' in kat:
                            emoji = '🐓'
                        elif 'MEYVE' in kat or 'SEBZE' in kat:
                            emoji = '🥦'
                        elif 'EKMEK' in kat:
                            emoji = '🥖'
                        else:
                            emoji = '📦'

                        kat_data[emoji] = {
                            'satis': satis,
                            'fark': fark,
                            'fire': fire,
                            'acik': acik,
                            'fark_pct': (fark / satis * 100) if satis != 0 else 0,
                            'fire_pct': (fire / satis * 100) if satis != 0 else 0,
                            'acik_pct': (acik / satis * 100) if satis != 0 else 0
                        }

                # Kısa format fonksiyonu
                def format_k(val):
                    if abs(val) >= 1000000:
                        return f"{val/1000000:.1f}M"
                    elif abs(val) >= 1000:
                        return f"{val/1000:.0f}K"
                    return f"{val:.0f}"

                # Kategori satırı oluştur
                def kat_line(field):
                    parts = []
                    for emoji in ['🐓', '🥦', '🥖']:
                        if emoji in kat_data:
                            val = kat_data[emoji][field]
                            pct = kat_data[emoji][f'{field}_pct']
                            parts.append(f"{emoji}: ₺{format_k(val)} | {pct:.2f}%")
                    return " ".join(parts)

                # Üst metrikler
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("💰 Satış", f"₺{toplam_satis:,.0f}")
                    if kat_data:
                        satis_parts = " ".join([f"{e}: ₺{format_k(kat_data[e]['satis'])}" for e in ['🐓', '🥦', '🥖'] if e in kat_data])
                        st.caption(satis_parts)

                with col2:
                    st.metric("📉 Fark", f"₺{toplam_fark:,.0f}", f"%{fark_oran:.2f}")
                    if kat_data:
                        st.caption(kat_line('fark'))

                with col3:
                    st.metric("🔥 Fire", f"₺{toplam_fire:,.0f}", f"%{fire_oran:.2f}")
                    if kat_data:
                        st.caption(kat_line('fire'))

                with col4:
                    st.metric("📊 Toplam Açık", f"₺{toplam_acik:,.0f}", f"%{acik_oran:.2f}")
                    if kat_data:
                        st.caption(kat_line('acik'))

            else:
                st.warning("Seçili dönem için veri bulunamadı.")
                gm_df = None
                magaza_sayisi = 0
                toplam_fark = 0
                toplam_fire = 0
                toplam_acik = 0

            # Risk dağılımı
            st.markdown("### 📊 Risk Dağılımı")
            r1, r2, r3, r4 = st.columns(4)
            r1.markdown('<div class="risk-kritik">🔴 KRİTİK: 0</div>', unsafe_allow_html=True)
            r2.markdown('<div class="risk-riskli">🟠 RİSKLİ: 0</div>', unsafe_allow_html=True)
            r3.markdown('<div class="risk-dikkat">🟡 DİKKAT: 0</div>', unsafe_allow_html=True)
            r4.markdown('<div class="risk-temiz">🟢 TEMİZ: 0</div>', unsafe_allow_html=True)

            # Sekmeler
            tabs = st.tabs(["👔 SM Özet", "📋 BS Özet", "🏪 Mağazalar", "📊 Top 10 Açık", "🔴 Riskler"])

            with tabs[0]:
                st.subheader("👔 Satış Müdürü Bazlı Özet")

                if gm_df is not None and len(gm_df) > 0 and 'satis_muduru' in gm_df.columns:
                    # SM özet cache kontrolü
                    if st.session_state.get("sm_ozet_cache_key") != period_key:
                        # SM bazlı grupla (1 kez)
                        sm_ozet = gm_df.groupby('satis_muduru').agg({
                            'magaza_kodu': 'nunique',
                            'fark_tutari': 'sum',
                            'fire_tutari': 'sum',
                            'satis_hasilati': 'sum'
                        }).reset_index()
                        sm_ozet.columns = ['Satış Müdürü', 'Mağaza', 'Fark', 'Fire', 'Satış']
                        sm_ozet['Açık'] = sm_ozet['Fark'] + sm_ozet['Fire']
                        sm_ozet['Açık%'] = (sm_ozet['Açık'] / sm_ozet['Satış'] * 100).round(2)
                        sm_ozet = sm_ozet.sort_values('Açık', ascending=True)

                        # SM + Kategori bazlı açık oranları hesapla
                        sm_kat_oranlar = {}
                        if 'depolama_kosulu' in gm_df.columns:
                            sm_kat_df = gm_df.groupby(['satis_muduru', 'depolama_kosulu']).agg({
                                'fark_tutari': 'sum', 'fire_tutari': 'sum', 'satis_hasilati': 'sum'
                            }).reset_index()

                            for _, r in sm_kat_df.iterrows():
                                sm = r['satis_muduru']
                                k = str(r['depolama_kosulu'] or '').upper()
                                s = r['satis_hasilati']
                                acik = r['fark_tutari'] + r['fire_tutari']
                                oran = (acik / s * 100) if s else 0

                                if 'ET' in k or 'TAVUK' in k: e = '🐓'
                                elif 'MEYVE' in k or 'SEBZE' in k: e = '🥦'
                                elif 'EKMEK' in k: e = '🥖'
                                else: continue

                                if sm not in sm_kat_oranlar:
                                    sm_kat_oranlar[sm] = {}
                                sm_kat_oranlar[sm][e] = oran

                        # Cache'e kaydet
                        st.session_state["sm_ozet_cache_key"] = period_key
                        st.session_state["sm_ozet_df"] = sm_ozet
                        st.session_state["sm_kat_oranlar"] = sm_kat_oranlar

                    # Cache'den oku
                    sm_ozet = st.session_state.get("sm_ozet_df")
                    sm_kat_oranlar = st.session_state.get("sm_kat_oranlar", {})

                    # Her kategori için en iyi/kötü bul
                    kat_worst = {}
                    kat_best = {}
                    for e in ['🐓', '🥦', '🥖']:
                        vals = [(sm, sm_kat_oranlar[sm].get(e, 0)) for sm in sm_kat_oranlar if e in sm_kat_oranlar[sm]]
                        if vals:
                            kat_worst[e] = min(vals, key=lambda x: x[1])[0]
                            kat_best[e] = max(vals, key=lambda x: x[1])[0]

                    # Her SM için tıklanabilir expander (renkli kategori oranları başlıkta)
                    for _, row in sm_ozet.iterrows():
                        sm_name = row['Satış Müdürü']
                        acik_pct = row['Açık%']

                        # Kategori oranlarını renkli emoji ile göster
                        kat_parts = []
                        if sm_name in sm_kat_oranlar:
                            for e in ['🐓', '🥦', '🥖']:
                                if e in sm_kat_oranlar[sm_name]:
                                    oran = sm_kat_oranlar[sm_name][e]
                                    if kat_worst.get(e) == sm_name:
                                        kat_parts.append(f"🔴{e}{oran:.1f}")
                                    elif kat_best.get(e) == sm_name:
                                        kat_parts.append(f"🟢{e}{oran:.1f}")
                                    else:
                                        kat_parts.append(f"{e}{oran:.1f}")

                        kat_str = " ".join(kat_parts) if kat_parts else ""
                        expander_title = f"👔 {sm_name} | {row['Mağaza']} mğz | {kat_str} | Açık: {acik_pct:.1f}%"

                        with st.expander(expander_title):
                            # Bu SM'in verilerini al
                            sm_df = gm_df[gm_df['satis_muduru'] == sm_name]

                            # SM kategori kırılımı
                            sm_kat = {}
                            if 'depolama_kosulu' in sm_df.columns:
                                for _, kr in sm_df.groupby('depolama_kosulu').agg({
                                    'fark_tutari': 'sum', 'fire_tutari': 'sum', 'satis_hasilati': 'sum'
                                }).reset_index().iterrows():
                                    k = str(kr['depolama_kosulu'] or '').upper()
                                    s = kr['satis_hasilati']
                                    if 'ET' in k or 'TAVUK' in k: e = '🐓'
                                    elif 'MEYVE' in k or 'SEBZE' in k: e = '🥦'
                                    elif 'EKMEK' in k: e = '🥖'
                                    else: e = '📦'
                                    sm_kat[e] = {
                                        'satis': s, 'fark': kr['fark_tutari'], 'fire': kr['fire_tutari'],
                                        'acik': kr['fark_tutari'] + kr['fire_tutari'],
                                        'fark_pct': (kr['fark_tutari']/s*100) if s else 0,
                                        'fire_pct': (kr['fire_tutari']/s*100) if s else 0,
                                        'acik_pct': ((kr['fark_tutari']+kr['fire_tutari'])/s*100) if s else 0
                                    }

                            def sm_kat_line(fld):
                                return " ".join([f"{e}: ₺{format_k(sm_kat[e][fld])} | {sm_kat[e][f'{fld}_pct']:.1f}%" for e in ['🐓','🥦','🥖'] if e in sm_kat])

                            # Özet metrikler
                            c1, c2, c3, c4 = st.columns(4)
                            with c1:
                                st.metric("Satış", f"₺{row['Satış']:,.0f}")
                                if sm_kat:
                                    st.caption(" ".join([f"{e}: ₺{format_k(sm_kat[e]['satis'])}" for e in ['🐓','🥦','🥖'] if e in sm_kat]))
                            with c2:
                                st.metric("Fark", f"₺{row['Fark']:,.0f}", f"{row['Fark']/row['Satış']*100:.2f}%")
                                if sm_kat:
                                    st.caption(sm_kat_line('fark'))
                            with c3:
                                st.metric("Fire", f"₺{row['Fire']:,.0f}", f"{row['Fire']/row['Satış']*100:.2f}%")
                                if sm_kat:
                                    st.caption(sm_kat_line('fire'))
                            with c4:
                                st.metric("Açık", f"₺{row['Açık']:,.0f}", f"{acik_pct:.2f}%")
                                if sm_kat:
                                    st.caption(sm_kat_line('acik'))

                            # Bu SM'in mağazaları
                            st.markdown("**🏪 Mağazalar**")
                            sm_magazalar = gm_df[gm_df['satis_muduru'] == sm_name].groupby(
                                ['magaza_kodu', 'magaza_tanim']
                            ).agg({
                                'fark_tutari': 'sum',
                                'fire_tutari': 'sum',
                                'satis_hasilati': 'sum'
                            }).reset_index()
                            sm_magazalar['Açık'] = sm_magazalar['fark_tutari'] + sm_magazalar['fire_tutari']
                            sm_magazalar = sm_magazalar.sort_values('Açık', ascending=True)

                            st.dataframe(
                                sm_magazalar.rename(columns={
                                    'magaza_kodu': 'Kod',
                                    'magaza_tanim': 'Mağaza',
                                    'fark_tutari': 'Fark',
                                    'fire_tutari': 'Fire',
                                    'satis_hasilati': 'Satış'
                                })[['Kod', 'Mağaza', 'Satış', 'Fark', 'Fire', 'Açık']],
                                width="stretch",
                                hide_index=True
                            )
                else:
                    st.info("📥 Veri bulunamadı")

            with tabs[1]:
                st.subheader("📋 Bölge Sorumlusu Bazlı Özet")

                # BS verisi kontrolü - boş olmayan BS'leri filtrele
                bs_var = False
                if gm_df is not None and len(gm_df) > 0 and 'bolge_sorumlusu' in gm_df.columns:
                    # Boş olmayan BS'ler
                    bs_df = gm_df[gm_df['bolge_sorumlusu'].notna() & (gm_df['bolge_sorumlusu'] != '')]
                    if len(bs_df) > 0:
                        bs_var = True

                if bs_var:
                    # BS bazlı grupla - sadece dolu olanları
                    bs_ozet = bs_df.groupby('bolge_sorumlusu').agg({
                        'magaza_kodu': 'nunique',
                        'fark_tutari': 'sum',
                        'fire_tutari': 'sum',
                        'satis_hasilati': 'sum'
                    }).reset_index()
                    bs_ozet.columns = ['Bölge Sorumlusu', 'Mağaza', 'Fark', 'Fire', 'Satış']
                    bs_ozet['Açık'] = bs_ozet['Fark'] + bs_ozet['Fire']
                    bs_ozet['Açık%'] = (bs_ozet['Açık'] / bs_ozet['Satış'] * 100).round(2)
                    bs_ozet = bs_ozet.sort_values('Açık', ascending=True)

                    # BS + Kategori bazlı açık oranları hesapla
                    bs_kat_oranlar = {}
                    if 'depolama_kosulu' in bs_df.columns:
                        bs_kat_df = bs_df.groupby(['bolge_sorumlusu', 'depolama_kosulu']).agg({
                            'fark_tutari': 'sum', 'fire_tutari': 'sum', 'satis_hasilati': 'sum'
                        }).reset_index()

                        for _, r in bs_kat_df.iterrows():
                            bs = r['bolge_sorumlusu']
                            k = str(r['depolama_kosulu'] or '').upper()
                            s = r['satis_hasilati']
                            acik = r['fark_tutari'] + r['fire_tutari']
                            oran = (acik / s * 100) if s else 0

                            if 'ET' in k or 'TAVUK' in k: e = '🐓'
                            elif 'MEYVE' in k or 'SEBZE' in k: e = '🥦'
                            elif 'EKMEK' in k: e = '🥖'
                            else: continue

                            if bs not in bs_kat_oranlar:
                                bs_kat_oranlar[bs] = {}
                            bs_kat_oranlar[bs][e] = oran

                    # Her kategori için en iyi/kötü BS bul
                    bs_kat_worst = {}
                    bs_kat_best = {}
                    for e in ['🐓', '🥦', '🥖']:
                        vals = [(bs, bs_kat_oranlar[bs].get(e, 0)) for bs in bs_kat_oranlar if e in bs_kat_oranlar[bs]]
                        if vals:
                            bs_kat_worst[e] = min(vals, key=lambda x: x[1])[0]  # En negatif = en kötü
                            bs_kat_best[e] = max(vals, key=lambda x: x[1])[0]   # En az negatif = en iyi

                    # Her BS için tıklanabilir expander
                    for _, row in bs_ozet.iterrows():
                        bs_name = row['Bölge Sorumlusu']
                        if not bs_name:
                            continue
                        acik_pct = row['Açık%']

                        # Kategori oranlarını renkli emoji ile göster
                        kat_parts = []
                        if bs_name in bs_kat_oranlar:
                            for e in ['🐓', '🥦', '🥖']:
                                if e in bs_kat_oranlar[bs_name]:
                                    oran = bs_kat_oranlar[bs_name][e]
                                    if bs_kat_worst.get(e) == bs_name:
                                        kat_parts.append(f"🔴{e}{oran:.1f}")
                                    elif bs_kat_best.get(e) == bs_name:
                                        kat_parts.append(f"🟢{e}{oran:.1f}")
                                    else:
                                        kat_parts.append(f"{e}{oran:.1f}")

                        kat_str = " ".join(kat_parts) if kat_parts else ""
                        expander_title = f"📋 {bs_name} | {row['Mağaza']:.0f} mğz | {kat_str} | Açık: {acik_pct:.1f}%"

                        with st.expander(expander_title):
                            # Bu BS'in mağazaları
                            bs_magazalar = bs_df[bs_df['bolge_sorumlusu'] == bs_name].groupby(
                                ['magaza_kodu', 'magaza_tanim']
                            ).agg({
                                'fark_tutari': 'sum',
                                'fire_tutari': 'sum',
                                'satis_hasilati': 'sum'
                            }).reset_index()
                            bs_magazalar['Açık'] = bs_magazalar['fark_tutari'] + bs_magazalar['fire_tutari']
                            bs_magazalar['Açık%'] = (bs_magazalar['Açık'] / bs_magazalar['satis_hasilati'] * 100).round(2)
                            bs_magazalar = bs_magazalar.sort_values('Açık', ascending=True)

                            # Özet satırı
                            st.caption(f"💰 Satış: ₺{row['Satış']:,.0f} | 📉 Fark: ₺{row['Fark']:,.0f} | 🔥 Fire: ₺{row['Fire']:,.0f}")

                            # Mağaza listesi - her mağaza için kategori kırılımı
                            for _, mag in bs_magazalar.iterrows():
                                mag_kodu = mag['magaza_kodu']
                                mag_tanim = mag['magaza_tanim']

                                # Bu mağazanın kategori kırılımını hesapla
                                mag_df = bs_df[bs_df['magaza_kodu'] == mag_kodu]
                                mag_kat = {}
                                if 'depolama_kosulu' in mag_df.columns:
                                    for _, kr in mag_df.groupby('depolama_kosulu').agg({
                                        'fark_tutari': 'sum', 'fire_tutari': 'sum', 'satis_hasilati': 'sum'
                                    }).reset_index().iterrows():
                                        k = str(kr['depolama_kosulu'] or '').upper()
                                        s = kr['satis_hasilati']
                                        if 'ET' in k or 'TAVUK' in k: e = '🐓'
                                        elif 'MEYVE' in k or 'SEBZE' in k: e = '🥦'
                                        elif 'EKMEK' in k: e = '🥖'
                                        else: continue
                                        acik_kat = kr['fark_tutari'] + kr['fire_tutari']
                                        mag_kat[e] = {
                                            'satis': s, 'fark': kr['fark_tutari'], 'fire': kr['fire_tutari'],
                                            'acik': acik_kat,
                                            'fark_pct': (kr['fark_tutari'] / s * 100) if s else 0,
                                            'fire_pct': (kr['fire_tutari'] / s * 100) if s else 0,
                                            'acik_pct': (acik_kat / s * 100) if s else 0
                                        }

                                # Kategori oranlarını renkli göster (en kötü kırmızı, en iyi yeşil)
                                kat_parts = []
                                for e in ['🐓', '🥦', '🥖']:
                                    if e in mag_kat:
                                        oran = mag_kat[e]['acik_pct']
                                        # Renk: < -5 kırmızı, -2 ile -5 arası sarı, > -2 yeşil
                                        if oran < -5:
                                            kat_parts.append(f"🔴{e}{oran:.1f}%")
                                        elif oran < -2:
                                            kat_parts.append(f"🟡{e}{oran:.1f}%")
                                        else:
                                            kat_parts.append(f"🟢{e}{oran:.1f}%")
                                kat_str = " ".join(kat_parts) if kat_parts else ""

                                # Risk seviyesine göre emoji
                                acik_pct = mag['Açık%']
                                if acik_pct < -5:
                                    acik_emoji = "🔴"
                                elif acik_pct < -2:
                                    acik_emoji = "🟡"
                                else:
                                    acik_emoji = "🟢"

                                mag_title = f"{acik_emoji} **{mag_kodu}** {mag_tanim} | {kat_str} | Açık: {acik_pct:.1f}%"

                                with st.expander(mag_title):
                                    # Özet metrikler - oranlarla birlikte
                                    satis = mag['satis_hasilati']
                                    fark = mag['fark_tutari']
                                    fire = mag['fire_tutari']
                                    acik = mag['Açık']

                                    fark_oran = (fark / satis * 100) if satis else 0
                                    fire_oran = (fire / satis * 100) if satis else 0

                                    c1, c2, c3, c4 = st.columns(4)
                                    with c1:
                                        st.metric("💰 Satış", f"₺{satis:,.0f}")
                                    with c2:
                                        st.metric("📉 Fark", f"₺{fark:,.0f}", f"%{fark_oran:.2f}")
                                    with c3:
                                        st.metric("🔥 Fire", f"₺{fire:,.0f}", f"%{fire_oran:.2f}")
                                    with c4:
                                        st.metric("📊 Açık", f"₺{acik:,.0f}", f"%{acik_pct:.2f}")

                                    # Kategori detayları - tablo formatında
                                    if mag_kat:
                                        st.markdown("---")
                                        st.markdown("**📦 Kategori Bazlı Detay:**")

                                        # Kategori tablosu için veri hazırla
                                        kat_rows = []
                                        kat_names = {'🐓': 'Et-Tavuk', '🥦': 'Meyve-Sebze', '🥖': 'Ekmek'}
                                        for e in ['🐓', '🥦', '🥖']:
                                            if e in mag_kat:
                                                d = mag_kat[e]
                                                kat_rows.append({
                                                    'Kategori': f"{e} {kat_names.get(e, '')}",
                                                    'Satış': f"₺{d['satis']:,.0f}",
                                                    'Fark': f"₺{d['fark']:,.0f}",
                                                    'Fark%': f"%{d['fark_pct']:.2f}",
                                                    'Fire': f"₺{d['fire']:,.0f}",
                                                    'Fire%': f"%{d['fire_pct']:.2f}",
                                                    'Açık': f"₺{d['acik']:,.0f}",
                                                    'Açık%': f"%{d['acik_pct']:.2f}"
                                                })

                                        if kat_rows:
                                            kat_df = pd.DataFrame(kat_rows)
                                            st.dataframe(kat_df, width="stretch", hide_index=True)

                                        # Her kategori için mini özet kutuları
                                        st.markdown("**📊 Kategori Oranları:**")
                                        kat_cols = st.columns(len(mag_kat))
                                        for idx, e in enumerate(['🐓', '🥦', '🥖']):
                                            if e in mag_kat and idx < len(kat_cols):
                                                with kat_cols[idx]:
                                                    d = mag_kat[e]
                                                    oran = d['acik_pct']
                                                    if oran < -5:
                                                        renk_class = "risk-kritik"
                                                    elif oran < -2:
                                                        renk_class = "risk-dikkat"
                                                    else:
                                                        renk_class = "risk-temiz"
                                                    st.markdown(f'<div class="{renk_class}">{e} {kat_names.get(e, "")}<br>%{oran:.1f}</div>', unsafe_allow_html=True)
                else:
                    st.warning("⚠️ Bölge Sorumlusu verisi bulunamadı")
                    st.markdown("""
                    **Olası sebepler:**
                    - Excel dosyasında "Bölge Sorumlusu" sütunu boş olabilir
                    - Supabase'de `bolge_sorumlusu` alanı NULL olabilir

                    **Çözüm:** Excel dosyasına "Bölge Sorumlusu" sütununu doldurup tekrar yükleyin.
                    """)

            with tabs[2]:
                st.subheader("🏪 Mağaza Bazlı Özet")

                if gm_df is not None and len(gm_df) > 0:
                    # Mağaza bazlı grupla
                    mag_ozet = gm_df.groupby(['magaza_kodu', 'magaza_tanim']).agg({
                        'fark_tutari': 'sum',
                        'fire_tutari': 'sum',
                        'satis_hasilati': 'sum'
                    }).reset_index()
                    mag_ozet['Toplam Açık'] = mag_ozet['fark_tutari'] + mag_ozet['fire_tutari']
                    mag_ozet = mag_ozet.sort_values('Toplam Açık', ascending=True)

                    st.dataframe(
                        mag_ozet.rename(columns={
                            'magaza_kodu': 'Mağaza Kodu',
                            'magaza_tanim': 'Mağaza',
                            'fark_tutari': 'Fark',
                            'fire_tutari': 'Fire',
                            'satis_hasilati': 'Satış',
                            'Toplam Açık': 'Toplam Açık'
                        }),
                        width="stretch",
                        hide_index=True
                    )
                else:
                    st.info("📥 Veri bulunamadı")

            with tabs[3]:
                st.subheader("📊 En Yüksek Açık - Top 10 Mağaza")

                if gm_df is not None and len(gm_df) > 0:
                    # Mağaza bazlı grupla ve top 10
                    mag_top = gm_df.groupby(['magaza_kodu', 'magaza_tanim']).agg({
                        'fark_tutari': 'sum',
                        'fire_tutari': 'sum'
                    }).reset_index()
                    mag_top['Toplam Açık'] = mag_top['fark_tutari'] + mag_top['fire_tutari']
                    mag_top = mag_top.nsmallest(10, 'Toplam Açık')  # En düşük (en negatif) 10

                    for i, row in mag_top.iterrows():
                        st.write(f"**{row['magaza_kodu']}** - {row['magaza_tanim']}: ₺{row['Toplam Açık']:,.0f}")
                else:
                    st.info("📥 Veri bulunamadı")

            with tabs[4]:
                st.subheader("🔴 Risk Değerlendirme")

                if gm_df is not None and len(gm_df) > 0:
                    # İç hırsızlık verisi çek (ürün bazlı, tuple for cache)
                    ic_df = get_ic_hirsizlik_data(tuple(selected_periods))

                    # ==================== TÜM HESAPLAMALARI CACHE'LE ====================
                    period_key = tuple(selected_periods)

                    # Dönem değişmediyse cache'den al
                    if st.session_state.get("risk_cache_key") != period_key:
                        st.session_state["risk_cache_key"] = period_key

                        # Bölge toplamları
                        bolge_toplam_satis = gm_df['satis_hasilati'].sum()
                        bolge_toplam_fark = gm_df['fark_tutari'].sum()
                        bolge_toplam_fire = gm_df['fire_tutari'].sum()
                        bolge_toplam_acik = bolge_toplam_fark + bolge_toplam_fire
                        bolge_acik_oran = (bolge_toplam_acik / bolge_toplam_satis * 100) if bolge_toplam_satis else 0

                        st.session_state["bolge_toplam_satis"] = bolge_toplam_satis
                        st.session_state["bolge_toplam_acik"] = bolge_toplam_acik
                        st.session_state["bolge_acik_oran"] = bolge_acik_oran

                        # İç hırsızlık sayılarını VEKTÖREL hesapla (1 kez, O(n))
                        ic_counts = prepare_ic_counts_vectorized(ic_df)
                        ic_by_sm = ic_counts['by_sm']
                        ic_by_bs = ic_counts['by_bs']
                        ic_by_mag = ic_counts['by_magaza']

                        # SM verileri
                        sm_riskler = []
                        if 'satis_muduru' in gm_df.columns:
                            sm_risk_df = gm_df.groupby('satis_muduru').agg({
                                'fark_tutari': 'sum', 'fire_tutari': 'sum',
                                'satis_hasilati': 'sum', 'magaza_kodu': 'nunique'
                            }).reset_index()
                            for _, row in sm_risk_df.iterrows():
                                sm_acik = row['fark_tutari'] + row['fire_tutari']
                                sm_name = row['satis_muduru']
                                ic_sayisi = int(ic_by_sm.get(sm_name, 0))  # Hızlı lookup
                                risk = hesapla_birim_risk_v2({'acik': sm_acik, 'satis': row['satis_hasilati']}, bolge_toplam_acik, bolge_toplam_satis, ic_sayisi)
                                sm_riskler.append({
                                    'SM': sm_name, 'Mağaza': row['magaza_kodu'],
                                    'Satış': row['satis_hasilati'], 'Açık': sm_acik,
                                    'Açık%': risk['birim_oran'], 'Katsayı': risk['katsayi'],
                                    'Puan': risk['puan'], 'Seviye': risk['seviye'],
                                    'emoji': risk['emoji'], 'detay': risk['detay'],
                                    'ic_sayisi': ic_sayisi
                                })

                        # BS verileri
                        bs_riskler = []
                        if 'bolge_sorumlusu' in gm_df.columns:
                            bs_df_risk = gm_df[gm_df['bolge_sorumlusu'].notna() & (gm_df['bolge_sorumlusu'] != '')]
                            if len(bs_df_risk) > 0:
                                bs_risk_df = bs_df_risk.groupby('bolge_sorumlusu').agg({
                                    'fark_tutari': 'sum', 'fire_tutari': 'sum',
                                    'satis_hasilati': 'sum', 'magaza_kodu': 'nunique'
                                }).reset_index()
                                for _, row in bs_risk_df.iterrows():
                                    bs_acik = row['fark_tutari'] + row['fire_tutari']
                                    bs_name = row['bolge_sorumlusu']
                                    ic_sayisi = int(ic_by_bs.get(bs_name, 0))  # Hızlı lookup
                                    risk = hesapla_birim_risk_v2({'acik': bs_acik, 'satis': row['satis_hasilati']}, bolge_toplam_acik, bolge_toplam_satis, ic_sayisi)
                                    bs_riskler.append({
                                        'BS': bs_name, 'Mağaza': row['magaza_kodu'],
                                        'Satış': row['satis_hasilati'], 'Açık': bs_acik,
                                        'Açık%': risk['birim_oran'], 'Katsayı': risk['katsayi'],
                                        'Puan': risk['puan'], 'Seviye': risk['seviye'],
                                        'emoji': risk['emoji'], 'detay': risk['detay'],
                                        'ic_sayisi': ic_sayisi
                                    })

                        # Mağaza verileri
                        mag_riskler = []
                        mag_risk_df = gm_df.groupby(['magaza_kodu', 'magaza_tanim']).agg({
                            'fark_tutari': 'sum', 'fire_tutari': 'sum', 'satis_hasilati': 'sum'
                        }).reset_index()
                        for _, row in mag_risk_df.iterrows():
                            mag_acik = row['fark_tutari'] + row['fire_tutari']
                            mag_kodu = row['magaza_kodu']
                            ic_sayisi = int(ic_by_mag.get(mag_kodu, 0))  # Hızlı lookup
                            risk = hesapla_birim_risk_v2({'acik': mag_acik, 'satis': row['satis_hasilati']}, bolge_toplam_acik, bolge_toplam_satis, ic_sayisi)
                            mag_riskler.append({
                                'Kod': mag_kodu, 'Mağaza': row['magaza_tanim'],
                                'Satış': row['satis_hasilati'], 'Açık': mag_acik,
                                'Açık%': risk['birim_oran'], 'Katsayı': risk['katsayi'],
                                'Puan': risk['puan'], 'Seviye': risk['seviye'],
                                'emoji': risk['emoji'], 'detay': risk['detay'],
                                'ic_sayisi': ic_sayisi
                            })

                        # Cache'e kaydet
                        st.session_state["sm_riskler"] = sm_riskler
                        st.session_state["bs_riskler"] = bs_riskler
                        st.session_state["mag_riskler"] = mag_riskler

                    # Cache'den oku
                    sm_riskler = st.session_state.get("sm_riskler", [])
                    bs_riskler = st.session_state.get("bs_riskler", [])
                    mag_riskler = st.session_state.get("mag_riskler", [])
                    bolge_toplam_satis = st.session_state.get("bolge_toplam_satis", 0)
                    bolge_toplam_acik = st.session_state.get("bolge_toplam_acik", 0)
                    bolge_acik_oran = st.session_state.get("bolge_acik_oran", 0)

                    # Bölge özet bilgisi
                    st.markdown(f"**📊 Bölge Referans Değerleri:** Açık Oranı: **%{bolge_acik_oran:.2f}** | Satış: ₺{bolge_toplam_satis:,.0f} | Açık: ₺{bolge_toplam_acik:,.0f}")
                    st.markdown("---")

                    # ==================== ANA SEKMELER: RİSK TİPİ ====================
                    risk_type_tabs = st.tabs(["📊 Açık Oranı", "🔓 İç Hırsızlık", "🔢 Yüksek Sayım", "📉 Kronik Açık", "🔥 Kronik Fire"])

                    # ==================== AÇIK ORANI SEKMESİ ====================
                    with risk_type_tabs[0]:
                        acik_sub_tabs = st.tabs(["👔 SM", "📋 BS", "🏪 Mağaza"])

                        # ----- SM -----
                        with acik_sub_tabs[0]:
                            if sm_riskler:
                                sm_sorted = sorted(sm_riskler, key=lambda x: x['Puan'], reverse=True)
                                for sm in sm_sorted:
                                    with st.expander(f"{sm['emoji']} **{sm['SM']}** | Puan: {sm['Puan']} | {sm['Seviye']} | Açık: %{sm['Açık%']:.2f}"):
                                        c1, c2, c3, c4 = st.columns(4)
                                        with c1: st.metric("Mağaza", sm['Mağaza'])
                                        with c2: st.metric("Satış", f"₺{sm['Satış']:,.0f}")
                                        with c3: st.metric("Açık", f"₺{sm['Açık']:,.0f}")
                                        with c4: st.metric("Katsayı", f"{sm['Katsayı']:.2f}x")
                                        detay = sm['detay']
                                        if detay.get('pozitif_acik', 0) > 0: st.warning(f"⚠️ Pozitif Açık: +{detay['pozitif_acik']} puan")
                                        if detay.get('bolge_ortalama_ustu', 0) > 0: st.info(f"📊 Bölge Ort. Üstü: +{detay['bolge_ortalama_ustu']} puan")
                            else:
                                st.warning("SM verisi bulunamadı")

                        # ----- BS -----
                        with acik_sub_tabs[1]:
                            if bs_riskler:
                                bs_sorted = sorted(bs_riskler, key=lambda x: x['Puan'], reverse=True)
                                for bs in bs_sorted:
                                    with st.expander(f"{bs['emoji']} **{bs['BS']}** | Puan: {bs['Puan']} | {bs['Seviye']} | Açık: %{bs['Açık%']:.2f}"):
                                        c1, c2, c3, c4 = st.columns(4)
                                        with c1: st.metric("Mağaza", bs['Mağaza'])
                                        with c2: st.metric("Satış", f"₺{bs['Satış']:,.0f}")
                                        with c3: st.metric("Açık", f"₺{bs['Açık']:,.0f}")
                                        with c4: st.metric("Katsayı", f"{bs['Katsayı']:.2f}x")
                                        detay = bs['detay']
                                        if detay.get('pozitif_acik', 0) > 0: st.warning(f"⚠️ Pozitif Açık: +{detay['pozitif_acik']} puan")
                                        if detay.get('bolge_ortalama_ustu', 0) > 0: st.info(f"📊 Bölge Ort. Üstü: +{detay['bolge_ortalama_ustu']} puan")
                            else:
                                st.warning("BS verisi bulunamadı")

                        # ----- Mağaza -----
                        with acik_sub_tabs[2]:
                            mag_sorted = sorted(mag_riskler, key=lambda x: x['Puan'], reverse=True)
                            riskli = [m for m in mag_sorted if m['Puan'] > 0]
                            if riskli:
                                st.info(f"🔴 {len(riskli)} mağazada risk tespit edildi")
                                for mag in riskli[:25]:
                                    with st.expander(f"{mag['emoji']} **{mag['Kod']}** {mag['Mağaza']} | Puan: {mag['Puan']} | Açık: %{mag['Açık%']:.2f}"):
                                        c1, c2, c3, c4 = st.columns(4)
                                        with c1: st.metric("Satış", f"₺{mag['Satış']:,.0f}")
                                        with c2: st.metric("Açık", f"₺{mag['Açık']:,.0f}")
                                        with c3: st.metric("Katsayı", f"{mag['Katsayı']:.2f}x")
                                        with c4: st.metric("Risk Puanı", mag['Puan'])
                                        detay = mag['detay']
                                        if detay.get('pozitif_acik', 0) > 0: st.warning(f"⚠️ Pozitif Açık: +{detay['pozitif_acik']} puan")
                                        if detay.get('bolge_ortalama_ustu', 0) > 0: st.info(f"📊 Bölge Ort. Üstü: +{detay['bolge_ortalama_ustu']} puan")
                                if len(riskli) > 25: st.caption(f"... ve {len(riskli) - 25} mağaza daha")
                            else:
                                st.success("🟢 Riskli mağaza bulunamadı!")

                    # ==================== İÇ HIRSIZLIK SEKMESİ ====================
                    with risk_type_tabs[1]:
                        st.caption("Formül: fark - iptal = 0 → ÇOK YÜKSEK | Sadece fark < 0 ve fiyat ≥ 100 TL ürünler")
                        ic_sub_tabs = st.tabs(["👔 SM", "📋 BS", "🏪 Mağaza"])

                        # ----- SM İç Hırsızlık -----
                        with ic_sub_tabs[0]:
                            ic_sm = [s for s in sm_riskler if s['ic_sayisi'] > 0]
                            ic_sm_sorted = sorted(ic_sm, key=lambda x: x['ic_sayisi'], reverse=True)
                            if ic_sm_sorted:
                                st.error(f"🔓 {len(ic_sm_sorted)} SM'de iç hırsızlık şüphesi")
                                for sm in ic_sm_sorted:
                                    with st.expander(f"🔓 **{sm['SM']}** | {sm['ic_sayisi']} şüpheli ürün | {sm['Mağaza']} mağaza"):
                                        c1, c2, c3 = st.columns(3)
                                        with c1: st.metric("Şüpheli Ürün", sm['ic_sayisi'])
                                        with c2: st.metric("İç Hırsızlık Puanı", sm['detay'].get('ic_hirsizlik', 0))
                                        with c3: st.metric("Toplam Risk", sm['Puan'])
                                        if sm.get('ic_urunler'):
                                            for urun in sm.get('ic_urunler', [])[:15]:
                                                renk = "🔴" if urun['risk'] == 'ÇOK YÜKSEK' else "🟠" if urun['risk'] == 'YÜKSEK' else "🟡"
                                                st.write(f"{renk} **{urun['malzeme_kodu']}** - {urun['malzeme_tanimi'][:35]} | Mğz: {urun['magaza_kodu']}")
                                                st.caption(f"  ₺{urun['satis_fiyati']:.0f} | İptal: {urun['iptal_miktari']} | Fark: {urun['fark_miktari']}")
                            else:
                                st.success("🟢 İç hırsızlık şüphesi olan SM bulunamadı!")

                        # ----- BS İç Hırsızlık -----
                        with ic_sub_tabs[1]:
                            ic_bs = [b for b in bs_riskler if b['ic_sayisi'] > 0]
                            ic_bs_sorted = sorted(ic_bs, key=lambda x: x['ic_sayisi'], reverse=True)
                            if ic_bs_sorted:
                                st.error(f"🔓 {len(ic_bs_sorted)} BS'de iç hırsızlık şüphesi")
                                for bs in ic_bs_sorted:
                                    with st.expander(f"🔓 **{bs['BS']}** | {bs['ic_sayisi']} şüpheli ürün | {bs['Mağaza']} mağaza"):
                                        c1, c2, c3 = st.columns(3)
                                        with c1: st.metric("Şüpheli Ürün", bs['ic_sayisi'])
                                        with c2: st.metric("İç Hırsızlık Puanı", bs['detay'].get('ic_hirsizlik', 0))
                                        with c3: st.metric("Toplam Risk", bs['Puan'])
                                        if bs.get('ic_urunler'):
                                            for urun in bs.get('ic_urunler', [])[:15]:
                                                renk = "🔴" if urun['risk'] == 'ÇOK YÜKSEK' else "🟠" if urun['risk'] == 'YÜKSEK' else "🟡"
                                                st.write(f"{renk} **{urun['malzeme_kodu']}** - {urun['malzeme_tanimi'][:35]} | Mğz: {urun['magaza_kodu']}")
                                                st.caption(f"  ₺{urun['satis_fiyati']:.0f} | İptal: {urun['iptal_miktari']} | Fark: {urun['fark_miktari']}")
                            else:
                                st.success("🟢 İç hırsızlık şüphesi olan BS bulunamadı!")

                        # ----- Mağaza İç Hırsızlık -----
                        with ic_sub_tabs[2]:
                            ic_mag = [m for m in mag_riskler if m['ic_sayisi'] > 0]
                            ic_mag_sorted = sorted(ic_mag, key=lambda x: x['ic_sayisi'], reverse=True)
                            if ic_mag_sorted:
                                st.error(f"🔓 {len(ic_mag_sorted)} mağazada iç hırsızlık şüphesi")
                                for mag in ic_mag_sorted[:30]:
                                    with st.expander(f"🔓 **{mag['Kod']}** {mag['Mağaza']} | {mag['ic_sayisi']} şüpheli ürün"):
                                        c1, c2, c3 = st.columns(3)
                                        with c1: st.metric("Şüpheli Ürün", mag['ic_sayisi'])
                                        with c2: st.metric("İç Hırsızlık Puanı", mag['detay'].get('ic_hirsizlik', 0))
                                        with c3: st.metric("Toplam Risk", mag['Puan'])
                                        if mag.get('ic_urunler'):
                                            st.markdown("**Şüpheli Ürünler + Kamera:**")
                                            malzeme_kodlari = [u['malzeme_kodu'] for u in mag.get('ic_urunler', [])]
                                            iptal_data = get_iptal_timestamps_for_magaza(mag['Kod'], malzeme_kodlari)
                                            for urun in mag.get('ic_urunler', [])[:15]:
                                                kamera = get_kamera_bilgisi(str(urun['malzeme_kodu']), iptal_data, 15, urun.get('yukleme_tarihi'))
                                                renk = "🔴" if urun['risk'] == 'ÇOK YÜKSEK' else "🟠" if urun['risk'] == 'YÜKSEK' else "🟡"
                                                st.write(f"{renk} **{urun['malzeme_kodu']}** - {urun['malzeme_tanimi'][:35]}")
                                                st.caption(f"  ₺{urun['satis_fiyati']:.0f} | İptal: {urun['iptal_miktari']} | Fark: {urun['fark_miktari']} | {kamera['detay']}")
                                if len(ic_mag_sorted) > 30: st.caption(f"... ve {len(ic_mag_sorted) - 30} mağaza daha")
                            else:
                                st.success("🟢 İç hırsızlık şüphesi olan mağaza bulunamadı!")

                    # ==================== YÜKSEK SAYIM SEKMESİ ====================
                    with risk_type_tabs[2]:
                        st.caption("Son envanterde 50+ sayım yapan mağazalar | Yüksek sayım = potansiyel manipülasyon")

                        # Yüksek sayım yapan ürünleri bul (sayim_miktari >= 50)
                        YUKSEK_SAYIM_ESIK = 50

                        # HIZLI pandas yöntemi - vektörel filtreleme
                        yuksek_sayim_urunler = []
                        if 'sayim_miktari' in gm_df.columns:
                            # Pandas ile hızlı filtreleme
                            ys_df = gm_df[gm_df['sayim_miktari'].fillna(0).astype(float) >= YUKSEK_SAYIM_ESIK].copy()
                            # Duplicate'ları kaldır (mağaza+ürün bazında ilk kaydı al)
                            ys_df = ys_df.drop_duplicates(subset=['magaza_kodu', 'malzeme_kodu'], keep='first')

                            # DataFrame'den listeye dönüştür
                            for _, row in ys_df.iterrows():
                                yuksek_sayim_urunler.append({
                                    'magaza_kodu': str(row.get('magaza_kodu', '')),
                                    'magaza_adi': str(row.get('magaza_tanim', ''))[:30] if row.get('magaza_tanim') else '',
                                    'sm': str(row.get('satis_muduru', '')),
                                    'bs': str(row.get('bolge_sorumlusu', '')),
                                    'malzeme_kodu': str(row.get('malzeme_kodu', '')),
                                    'malzeme_adi': str(row.get('malzeme_tanimi', ''))[:40] if row.get('malzeme_tanimi') else '',
                                    'sayim_miktari': float(row.get('sayim_miktari', 0) or 0),
                                    'envanter_sayisi': int(row.get('envanter_sayisi', 0) or 0),
                                    'satis_fiyati': float(row.get('satis_fiyati', 0) or 0)
                                })

                        ys_sub_tabs = st.tabs(["👔 SM", "📋 BS", "🏪 Mağaza"])

                        # ----- SM Yüksek Sayım -----
                        with ys_sub_tabs[0]:
                            if yuksek_sayim_urunler:
                                # SM bazında grupla
                                sm_yuksek = {}
                                for u in yuksek_sayim_urunler:
                                    sm = u['sm']
                                    if sm not in sm_yuksek:
                                        sm_yuksek[sm] = {'urunler': [], 'magazalar': set()}
                                    sm_yuksek[sm]['urunler'].append(u)
                                    sm_yuksek[sm]['magazalar'].add(u['magaza_kodu'])

                                sm_sorted = sorted(sm_yuksek.items(), key=lambda x: len(x[1]['urunler']), reverse=True)
                                st.error(f"🔢 {len(sm_sorted)} SM'de yüksek sayım tespit edildi")

                                for sm_adi, data in sm_sorted:
                                    with st.expander(f"🔢 **{sm_adi}** | {len(data['urunler'])} ürün | {len(data['magazalar'])} mağaza"):
                                        for urun in sorted(data['urunler'], key=lambda x: x['sayim_miktari'], reverse=True)[:20]:
                                            seri = get_envanter_serisi(urun['magaza_kodu'], urun['malzeme_kodu'])
                                            if seri and len(seri) > 1:
                                                son = seri[-1]
                                                fark_str = f":red[**₺{abs(son['fark_tutari']):,.0f}**]" if son['fark_tutari'] != 0 else "₺0"
                                                seri_str = " → ".join([f"{s['envanter']}.:{s['delta']:.0f}" for s in seri])
                                                st.write(f"**{urun['magaza_kodu']}** {urun['magaza_adi'][:20]} | {urun['malzeme_kodu']} - {urun['malzeme_adi']}")
                                                st.markdown(f"  📊 Son: **{son['delta']:.0f}** | Seri: {seri_str} | Fark: {fark_str}")
                                            elif seri and len(seri) == 1:
                                                fark_str = f":red[**₺{abs(seri[0]['fark_tutari']):,.0f}**]" if seri[0]['fark_tutari'] != 0 else "₺0"
                                                st.write(f"**{urun['magaza_kodu']}** {urun['magaza_adi'][:20]} | {urun['malzeme_kodu']} - {urun['malzeme_adi']}")
                                                st.markdown(f"  📊 {seri[0]['envanter']}. Sayım: {seri[0]['kumulatif']:.0f} | Fark: {fark_str}")
                                            else:
                                                st.write(f"**{urun['magaza_kodu']}** {urun['magaza_adi'][:20]} | {urun['malzeme_kodu']} - {urun['malzeme_adi']}")
                                                st.caption(f"  Sayım: {urun['sayim_miktari']:.0f} | Envanter: {urun['envanter_sayisi']} | ₺{urun['satis_fiyati']:.0f}")
                            else:
                                st.success(f"🟢 {YUKSEK_SAYIM_ESIK}+ sayım yapan ürün bulunamadı!")

                        # ----- BS Yüksek Sayım -----
                        with ys_sub_tabs[1]:
                            if yuksek_sayim_urunler:
                                # BS bazında grupla
                                bs_yuksek = {}
                                for u in yuksek_sayim_urunler:
                                    bs = u['bs']
                                    if bs not in bs_yuksek:
                                        bs_yuksek[bs] = {'urunler': [], 'magazalar': set()}
                                    bs_yuksek[bs]['urunler'].append(u)
                                    bs_yuksek[bs]['magazalar'].add(u['magaza_kodu'])

                                bs_sorted = sorted(bs_yuksek.items(), key=lambda x: len(x[1]['urunler']), reverse=True)
                                st.error(f"🔢 {len(bs_sorted)} BS'de yüksek sayım tespit edildi")

                                for bs_adi, data in bs_sorted:
                                    with st.expander(f"🔢 **{bs_adi}** | {len(data['urunler'])} ürün | {len(data['magazalar'])} mağaza"):
                                        for urun in sorted(data['urunler'], key=lambda x: x['sayim_miktari'], reverse=True)[:20]:
                                            seri = get_envanter_serisi(urun['magaza_kodu'], urun['malzeme_kodu'])
                                            if seri and len(seri) > 1:
                                                son = seri[-1]
                                                fark_str = f":red[**₺{abs(son['fark_tutari']):,.0f}**]" if son['fark_tutari'] != 0 else "₺0"
                                                seri_str = " → ".join([f"{s['envanter']}.:{s['delta']:.0f}" for s in seri])
                                                st.write(f"**{urun['magaza_kodu']}** {urun['magaza_adi'][:20]} | {urun['malzeme_kodu']} - {urun['malzeme_adi']}")
                                                st.markdown(f"  📊 Son: **{son['delta']:.0f}** | Seri: {seri_str} | Fark: {fark_str}")
                                            elif seri and len(seri) == 1:
                                                fark_str = f":red[**₺{abs(seri[0]['fark_tutari']):,.0f}**]" if seri[0]['fark_tutari'] != 0 else "₺0"
                                                st.write(f"**{urun['magaza_kodu']}** {urun['magaza_adi'][:20]} | {urun['malzeme_kodu']} - {urun['malzeme_adi']}")
                                                st.markdown(f"  📊 {seri[0]['envanter']}. Sayım: {seri[0]['kumulatif']:.0f} | Fark: {fark_str}")
                                            else:
                                                st.write(f"**{urun['magaza_kodu']}** {urun['magaza_adi'][:20]} | {urun['malzeme_kodu']} - {urun['malzeme_adi']}")
                                                st.caption(f"  Sayım: {urun['sayim_miktari']:.0f} | Envanter: {urun['envanter_sayisi']} | ₺{urun['satis_fiyati']:.0f}")
                            else:
                                st.success(f"🟢 {YUKSEK_SAYIM_ESIK}+ sayım yapan ürün bulunamadı!")

                        # ----- Mağaza Yüksek Sayım -----
                        with ys_sub_tabs[2]:
                            if yuksek_sayim_urunler:
                                # Mağaza bazında grupla
                                mag_yuksek = {}
                                for u in yuksek_sayim_urunler:
                                    mag = u['magaza_kodu']
                                    if mag not in mag_yuksek:
                                        mag_yuksek[mag] = {'adi': u['magaza_adi'], 'sm': u['sm'], 'bs': u['bs'], 'urunler': []}
                                    mag_yuksek[mag]['urunler'].append(u)

                                mag_sorted = sorted(mag_yuksek.items(), key=lambda x: len(x[1]['urunler']), reverse=True)
                                st.error(f"🔢 {len(mag_sorted)} mağazada yüksek sayım tespit edildi")

                                for mag_kodu, data in mag_sorted[:30]:
                                    with st.expander(f"🔢 **{mag_kodu}** {data['adi'][:25]} | {len(data['urunler'])} ürün | SM: {data['sm']} | BS: {data['bs']}"):
                                        for urun in sorted(data['urunler'], key=lambda x: x['sayim_miktari'], reverse=True)[:15]:
                                            # Envanter serisini getir (lazy loading - expander açılınca, cache'li)
                                            seri = get_envanter_serisi(urun['magaza_kodu'], urun['malzeme_kodu'])
                                            if seri and len(seri) > 1:
                                                son = seri[-1]
                                                fark_str = f":red[**₺{abs(son['fark_tutari']):,.0f}**]" if son['fark_tutari'] != 0 else "₺0"
                                                st.write(f"**{urun['malzeme_kodu']}** - {urun['malzeme_adi']}")
                                                # Seri detayı
                                                seri_str = " → ".join([f"{s['envanter']}.:{s['delta']:.0f}" for s in seri])
                                                st.markdown(f"  📊 Son: **{son['delta']:.0f}** | Seri: {seri_str} | Fark: {fark_str}")
                                            elif seri and len(seri) == 1:
                                                # İlk kayıt - delta yok
                                                fark_str = f":red[**₺{abs(seri[0]['fark_tutari']):,.0f}**]" if seri[0]['fark_tutari'] != 0 else "₺0"
                                                st.write(f"**{urun['malzeme_kodu']}** - {urun['malzeme_adi']}")
                                                st.markdown(f"  📊 {seri[0]['envanter']}. Sayım: {seri[0]['kumulatif']:.0f} (ilk kayıt) | Fark: {fark_str}")
                                            else:
                                                # Seri bulunamadı
                                                st.write(f"**{urun['malzeme_kodu']}** - {urun['malzeme_adi']}")
                                                st.caption(f"  Sayım: {urun['sayim_miktari']:.0f} | Envanter: {urun['envanter_sayisi']} | ₺{urun['satis_fiyati']:.0f}")
                                if len(mag_sorted) > 30: st.caption(f"... ve {len(mag_sorted) - 30} mağaza daha")
                            else:
                                st.success(f"🟢 {YUKSEK_SAYIM_ESIK}+ sayım yapan mağaza bulunamadı!")

                    # ==================== KRONİK AÇIK SEKMESİ ====================
                    with risk_type_tabs[3]:
                        st.caption("Kural: Ardışık 2 envanter sayımında fark_tutari < -500 TL")

                        # DEBUG: Veri kontrolü - HER ZAMAN AÇIK
                        st.info(f"📊 gm_df: {gm_df.shape if gm_df is not None else 'None'}")
                        if gm_df is not None:
                            required = ['magaza_kodu', 'malzeme_kodu', 'envanter_sayisi', 'fark_tutari', 'satis_muduru']
                            missing = [c for c in required if c not in gm_df.columns]
                            if missing:
                                st.error(f"❌ Eksik kolonlar: {missing}")
                                st.write(f"Mevcut kolonlar: {list(gm_df.columns)}")
                            else:
                                st.success("✅ Tüm gerekli kolonlar mevcut")
                        else:
                            st.error("❌ gm_df is None!")

                        KRONIK_ESIK = -500

                        # Session state cache - dönem değişirse sıfırla
                        period_key = tuple(selected_periods)
                        if st.session_state.get("kronik_acik_period_key") != period_key:
                            st.session_state["kronik_acik_period_key"] = period_key
                            st.session_state["kronik_acik_urunler"] = None

                        # Butonla hesaplama tetikle
                        if st.button("📉 Kronik Açık Hesapla", key="btn_kronik_acik"):
                            try:
                                # DEBUG: Fonksiyon öncesi kontrol
                                need_cols = ['magaza_kodu', 'magaza_tanim', 'satis_muduru', 'bolge_sorumlusu',
                                             'malzeme_kodu', 'malzeme_tanimi', 'envanter_sayisi', 'fark_tutari']
                                missing_in_func = [c for c in need_cols if c not in gm_df.columns]
                                if missing_in_func:
                                    st.error(f"❌ _find_kronik_fast için eksik kolonlar: {missing_in_func}")
                                    st.write(f"Mevcut: {list(gm_df.columns)}")
                                    st.session_state["kronik_acik_urunler"] = []
                                else:
                                    with st.spinner("Hesaplanıyor..."):
                                        result = _find_kronik_fast(gm_df, "fark_tutari", KRONIK_ESIK)
                                        st.session_state["kronik_acik_urunler"] = result
                                        st.success(f"✅ Hesaplandı: {len(result)} kronik ürün bulundu")
                            except Exception as e:
                                st.error("Kronik Açık hesaplama hatası:")
                                st.exception(e)
                                st.session_state["kronik_acik_urunler"] = []

                        kronik_acik_urunler = st.session_state.get("kronik_acik_urunler")

                        if kronik_acik_urunler is None:
                            st.info("📉 Kronik Açık hesaplamak için yukarıdaki butona tıklayın.")
                        else:
                            kronik_sub_tabs = st.tabs(["👔 SM", "📋 BS", "🏪 Mağaza"])

                            # ----- SM Kronik Açık -----
                            with kronik_sub_tabs[0]:
                                if kronik_acik_urunler:
                                    sm_kronik = {}
                                    for u in kronik_acik_urunler:
                                        sm = u['sm']
                                        if sm not in sm_kronik:
                                            sm_kronik[sm] = {'urunler': [], 'magazalar': set(), 'toplam': 0}
                                        sm_kronik[sm]['urunler'].append(u)
                                        sm_kronik[sm]['magazalar'].add(u['magaza_kodu'])
                                        sm_kronik[sm]['toplam'] += u['toplam']

                                    sm_sorted = sorted(sm_kronik.items(), key=lambda x: x[1]['toplam'])
                                    st.error(f"📉 {len(sm_sorted)} SM'de kronik açık tespit edildi")

                                    for sm_adi, data in sm_sorted:
                                        renk = "🔴" if data['toplam'] < -5000 else "🟠" if data['toplam'] < -2000 else "🟡"
                                        with st.expander(f"{renk} **{sm_adi}** | {len(data['urunler'])} ürün | {len(data['magazalar'])} mağaza | Toplam: ₺{data['toplam']:,.0f}"):
                                            for urun in sorted(data['urunler'], key=lambda x: x['toplam'])[:20]:
                                                st.write(f"**{urun['magaza_kodu']}** {urun['magaza_adi'][:20]} | {urun['malzeme_kodu']} - {urun['malzeme_adi']}")
                                                st.markdown(f"  📉 {urun['onceki_env']}.Env: :red[**₺{urun['onceki_val']:,.0f}**] → {urun['sonraki_env']}.Env: :red[**₺{urun['sonraki_val']:,.0f}**] | Toplam: :red[**₺{urun['toplam']:,.0f}**]")
                                else:
                                    st.success("🟢 Kronik açık bulunamadı!")

                            # ----- BS Kronik Açık -----
                            with kronik_sub_tabs[1]:
                                if kronik_acik_urunler:
                                    bs_kronik = {}
                                    for u in kronik_acik_urunler:
                                        bs = u['bs']
                                        if bs not in bs_kronik:
                                            bs_kronik[bs] = {'urunler': [], 'magazalar': set(), 'toplam': 0}
                                        bs_kronik[bs]['urunler'].append(u)
                                        bs_kronik[bs]['magazalar'].add(u['magaza_kodu'])
                                        bs_kronik[bs]['toplam'] += u['toplam']

                                    bs_sorted = sorted(bs_kronik.items(), key=lambda x: x[1]['toplam'])
                                    st.error(f"📉 {len(bs_sorted)} BS'de kronik açık tespit edildi")

                                    for bs_adi, data in bs_sorted:
                                        renk = "🔴" if data['toplam'] < -5000 else "🟠" if data['toplam'] < -2000 else "🟡"
                                        with st.expander(f"{renk} **{bs_adi}** | {len(data['urunler'])} ürün | {len(data['magazalar'])} mağaza | Toplam: ₺{data['toplam']:,.0f}"):
                                            for urun in sorted(data['urunler'], key=lambda x: x['toplam'])[:20]:
                                                st.write(f"**{urun['magaza_kodu']}** {urun['magaza_adi'][:20]} | {urun['malzeme_kodu']} - {urun['malzeme_adi']}")
                                                st.markdown(f"  📉 {urun['onceki_env']}.Env: :red[**₺{urun['onceki_val']:,.0f}**] → {urun['sonraki_env']}.Env: :red[**₺{urun['sonraki_val']:,.0f}**] | Toplam: :red[**₺{urun['toplam']:,.0f}**]")
                                else:
                                    st.success("🟢 Kronik açık bulunamadı!")

                            # ----- Mağaza Kronik Açık -----
                            with kronik_sub_tabs[2]:
                                if kronik_acik_urunler:
                                    mag_kronik = {}
                                    for u in kronik_acik_urunler:
                                        mag = u['magaza_kodu']
                                        if mag not in mag_kronik:
                                            mag_kronik[mag] = {'adi': u['magaza_adi'], 'sm': u['sm'], 'bs': u['bs'], 'urunler': [], 'toplam': 0}
                                        mag_kronik[mag]['urunler'].append(u)
                                        mag_kronik[mag]['toplam'] += u['toplam']

                                    mag_sorted = sorted(mag_kronik.items(), key=lambda x: x[1]['toplam'])
                                    st.error(f"📉 {len(mag_sorted)} mağazada kronik açık tespit edildi")

                                    for mag_kodu, data in mag_sorted[:30]:
                                        renk = "🔴" if data['toplam'] < -3000 else "🟠" if data['toplam'] < -1000 else "🟡"
                                        with st.expander(f"{renk} **{mag_kodu}** {data['adi'][:25]} | {len(data['urunler'])} ürün | Toplam: ₺{data['toplam']:,.0f}"):
                                            for urun in sorted(data['urunler'], key=lambda x: x['toplam'])[:15]:
                                                st.write(f"**{urun['malzeme_kodu']}** - {urun['malzeme_adi']}")
                                                st.markdown(f"  📉 {urun['onceki_env']}.Env: :red[**₺{urun['onceki_val']:,.0f}**] → {urun['sonraki_env']}.Env: :red[**₺{urun['sonraki_val']:,.0f}**] | Toplam: :red[**₺{urun['toplam']:,.0f}**]")
                                    if len(mag_sorted) > 30: st.caption(f"... ve {len(mag_sorted) - 30} mağaza daha")
                                else:
                                    st.success("🟢 Kronik açık bulunamadı!")

                    # ==================== KRONİK FİRE SEKMESİ ====================
                    with risk_type_tabs[4]:
                        st.caption("Kural: Ardışık 2 envanter sayımında fire_tutari < -500 TL")

                        # DEBUG: Veri kontrolü - HER ZAMAN AÇIK
                        st.info(f"📊 gm_df: {gm_df.shape if gm_df is not None else 'None'}")
                        if gm_df is not None:
                            required = ['magaza_kodu', 'malzeme_kodu', 'envanter_sayisi', 'fire_tutari', 'satis_muduru']
                            missing = [c for c in required if c not in gm_df.columns]
                            if missing:
                                st.error(f"❌ Eksik kolonlar: {missing}")
                                st.write(f"Mevcut kolonlar: {list(gm_df.columns)}")
                            else:
                                st.success("✅ Tüm gerekli kolonlar mevcut")
                        else:
                            st.error("❌ gm_df is None!")

                        KRONIK_FIRE_ESIK = -500

                        # Session state cache - dönem değişirse sıfırla
                        period_key = tuple(selected_periods)
                        if st.session_state.get("kronik_fire_period_key") != period_key:
                            st.session_state["kronik_fire_period_key"] = period_key
                            st.session_state["kronik_fire_urunler"] = None

                        # Butonla hesaplama tetikle
                        if st.button("🔥 Kronik Fire Hesapla", key="btn_kronik_fire"):
                            try:
                                with st.spinner("Hesaplanıyor..."):
                                    st.session_state["kronik_fire_urunler"] = _find_kronik_fast(gm_df, "fire_tutari", KRONIK_FIRE_ESIK)
                            except Exception as e:
                                st.error("Kronik Fire hesaplama hatası:")
                                st.exception(e)
                                st.session_state["kronik_fire_urunler"] = []

                        kronik_fire_urunler = st.session_state.get("kronik_fire_urunler")

                        if kronik_fire_urunler is None:
                            st.info("🔥 Kronik Fire hesaplamak için yukarıdaki butona tıklayın.")
                        else:
                            fire_sub_tabs = st.tabs(["👔 SM", "📋 BS", "🏪 Mağaza"])

                            # ----- SM Kronik Fire -----
                            with fire_sub_tabs[0]:
                                if kronik_fire_urunler:
                                    sm_fire = {}
                                    for u in kronik_fire_urunler:
                                        sm = u['sm']
                                        if sm not in sm_fire:
                                            sm_fire[sm] = {'urunler': [], 'magazalar': set(), 'toplam': 0}
                                        sm_fire[sm]['urunler'].append(u)
                                        sm_fire[sm]['magazalar'].add(u['magaza_kodu'])
                                        sm_fire[sm]['toplam'] += u['toplam']

                                    sm_sorted = sorted(sm_fire.items(), key=lambda x: x[1]['toplam'])
                                    st.error(f"🔥 {len(sm_sorted)} SM'de kronik fire tespit edildi")

                                    for sm_adi, data in sm_sorted:
                                        renk = "🔴" if data['toplam'] < -5000 else "🟠" if data['toplam'] < -2000 else "🟡"
                                        with st.expander(f"{renk} **{sm_adi}** | {len(data['urunler'])} ürün | {len(data['magazalar'])} mağaza | Toplam: ₺{data['toplam']:,.0f}"):
                                            for urun in sorted(data['urunler'], key=lambda x: x['toplam'])[:20]:
                                                st.write(f"**{urun['magaza_kodu']}** {urun['magaza_adi'][:20]} | {urun['malzeme_kodu']} - {urun['malzeme_adi']}")
                                                st.markdown(f"  🔥 {urun['onceki_env']}.Env: :red[**₺{urun['onceki_val']:,.0f}**] → {urun['sonraki_env']}.Env: :red[**₺{urun['sonraki_val']:,.0f}**] | Toplam: :red[**₺{urun['toplam']:,.0f}**]")
                                else:
                                    st.success("🟢 Kronik fire bulunamadı!")

                            # ----- BS Kronik Fire -----
                            with fire_sub_tabs[1]:
                                if kronik_fire_urunler:
                                    bs_fire = {}
                                    for u in kronik_fire_urunler:
                                        bs = u['bs']
                                        if bs not in bs_fire:
                                            bs_fire[bs] = {'urunler': [], 'magazalar': set(), 'toplam': 0}
                                        bs_fire[bs]['urunler'].append(u)
                                        bs_fire[bs]['magazalar'].add(u['magaza_kodu'])
                                        bs_fire[bs]['toplam'] += u['toplam']

                                    bs_sorted = sorted(bs_fire.items(), key=lambda x: x[1]['toplam'])
                                    st.error(f"🔥 {len(bs_sorted)} BS'de kronik fire tespit edildi")

                                    for bs_adi, data in bs_sorted:
                                        renk = "🔴" if data['toplam'] < -5000 else "🟠" if data['toplam'] < -2000 else "🟡"
                                        with st.expander(f"{renk} **{bs_adi}** | {len(data['urunler'])} ürün | {len(data['magazalar'])} mağaza | Toplam: ₺{data['toplam']:,.0f}"):
                                            for urun in sorted(data['urunler'], key=lambda x: x['toplam'])[:20]:
                                                st.write(f"**{urun['magaza_kodu']}** {urun['magaza_adi'][:20]} | {urun['malzeme_kodu']} - {urun['malzeme_adi']}")
                                                st.markdown(f"  🔥 {urun['onceki_env']}.Env: :red[**₺{urun['onceki_val']:,.0f}**] → {urun['sonraki_env']}.Env: :red[**₺{urun['sonraki_val']:,.0f}**] | Toplam: :red[**₺{urun['toplam']:,.0f}**]")
                                else:
                                    st.success("🟢 Kronik fire bulunamadı!")

                            # ----- Mağaza Kronik Fire -----
                            with fire_sub_tabs[2]:
                                if kronik_fire_urunler:
                                    mag_fire = {}
                                    for u in kronik_fire_urunler:
                                        mag = u['magaza_kodu']
                                        if mag not in mag_fire:
                                            mag_fire[mag] = {'adi': u['magaza_adi'], 'sm': u['sm'], 'bs': u['bs'], 'urunler': [], 'toplam': 0}
                                        mag_fire[mag]['urunler'].append(u)
                                        mag_fire[mag]['toplam'] += u['toplam']

                                    mag_sorted = sorted(mag_fire.items(), key=lambda x: x[1]['toplam'])
                                    st.error(f"🔥 {len(mag_sorted)} mağazada kronik fire tespit edildi")

                                    for mag_kodu, data in mag_sorted[:30]:
                                        renk = "🔴" if data['toplam'] < -3000 else "🟠" if data['toplam'] < -1000 else "🟡"
                                        with st.expander(f"{renk} **{mag_kodu}** {data['adi'][:25]} | {len(data['urunler'])} ürün | Toplam: ₺{data['toplam']:,.0f}"):
                                            for urun in sorted(data['urunler'], key=lambda x: x['toplam'])[:15]:
                                                st.write(f"**{urun['malzeme_kodu']}** - {urun['malzeme_adi']}")
                                                st.markdown(f"  🔥 {urun['onceki_env']}.Env: :red[**₺{urun['onceki_val']:,.0f}**] → {urun['sonraki_env']}.Env: :red[**₺{urun['sonraki_val']:,.0f}**] | Toplam: :red[**₺{urun['toplam']:,.0f}**]")
                                    if len(mag_sorted) > 30: st.caption(f"... ve {len(mag_sorted) - 30} mağaza daha")
                                else:
                                    st.success("🟢 Kronik fire bulunamadı!")

                else:
                    st.info("📥 Veri bulunamadı")

    # ==================== EXCEL YÜKLE MODU ====================
    elif analysis_mode == "📥 Excel Yükle":
        st.subheader("📥 Excel Dosyası Yükle")

        st.markdown("""
        **Yüklenecek dosya formatı:**
        - Sürekli envanter Excel dosyası
        - Et-Tavuk, Ekmek veya Meyve/Sebze kategorileri

        **İşlem akışı:**
        Dosya yükle → Değişim tespit → Analiz → Kaydet
        """)

        uploaded_file = st.file_uploader(
            "Dosya seçin (CSV veya Excel)",
            type=['csv', 'xlsx', 'xls'],
            help="Sürekli envanter verisi içeren CSV veya Excel dosyası"
        )

        if uploaded_file:
            try:
                # Dosya tipine göre oku
                file_name = uploaded_file.name.lower()

                if file_name.endswith('.csv'):
                    # CSV oku - önce noktalı virgül, sonra virgül, sonra tab dene
                    df = pd.read_csv(uploaded_file, sep=';', decimal=',')
                    if len(df.columns) <= 1:
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, sep=',', decimal='.')
                    if len(df.columns) <= 1:
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, sep='\t', decimal=',')
                    st.success(f"✅ {len(df)} satır, {len(df.columns)} sütun yüklendi (CSV)")
                else:
                    # Excel oku
                    xl = pd.ExcelFile(uploaded_file)
                    sheet_names = xl.sheet_names

                    # En çok sütunu olan sayfayı bul
                    best_sheet = None
                    max_cols = 0

                    for sheet in sheet_names:
                        temp_df = pd.read_excel(uploaded_file, sheet_name=sheet, nrows=5)
                        if len(temp_df.columns) > max_cols:
                            max_cols = len(temp_df.columns)
                            best_sheet = sheet

                    df = pd.read_excel(uploaded_file, sheet_name=best_sheet)
                    st.success(f"✅ {len(df)} satır, {len(df.columns)} sütun yüklendi ({best_sheet})")

                # Sütunları göster
                with st.expander("📋 Sütunlar"):
                    st.write(df.columns.tolist())
                    # Bölge Sorumlusu kontrolü
                    if 'Bölge Sorumlusu' in df.columns:
                        bs_values = df['Bölge Sorumlusu'].dropna().unique()
                        st.success(f"✅ Bölge Sorumlusu sütunu var - {len(bs_values)} farklı değer")
                        if len(bs_values) > 0:
                            st.write(f"Örnek değerler: {list(bs_values[:5])}")
                    else:
                        st.warning("⚠️ 'Bölge Sorumlusu' sütunu bulunamadı!")
                        # Benzer sütun ara
                        benzer = [c for c in df.columns if 'bolge' in c.lower() or 'sorumlu' in c.lower()]
                        if benzer:
                            st.info(f"Benzer sütunlar: {benzer}")

                # Önizleme
                with st.expander("👁️ Veri Önizleme"):
                    st.dataframe(df.head(20), width="stretch")

                # Gerekli sütunlar kontrolü
                gerekli_sutunlar = ['Mağaza Kodu', 'Malzeme Kodu', 'Envanter Dönemi', 'Envanter Sayisi']
                eksik_sutunlar = [s for s in gerekli_sutunlar if s not in df.columns]

                if eksik_sutunlar:
                    st.error(f"❌ Eksik sütunlar: {', '.join(eksik_sutunlar)}")
                else:
                    # Otomatik işlem - buton yok
                    if create_client_for_write():
                        # Excel'den mağaza kodları ve dönem al
                        magaza_kodlari = df['Mağaza Kodu'].astype(str).unique().tolist()
                        envanter_donemi = df['Envanter Dönemi'].iloc[0] if 'Envanter Dönemi' in df.columns else None

                        mevcut_sayilar = get_mevcut_envanter_sayilari(magaza_kodlari, envanter_donemi)

                        # Değişim tespit et
                        degisen_magazalar, degisen_urunler = detect_envanter_degisimi(df, mevcut_sayilar)

                        st.markdown("---")
                        st.markdown("### 📊 Değişim Analizi")

                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("📦 Toplam Satır", len(df))
                        with col2:
                            toplam_magaza = df['Mağaza Kodu'].nunique()
                            st.metric("🏪 Toplam Mağaza", toplam_magaza)
                        with col3:
                            st.metric("🔄 Yeni Sayım Yapan", len(degisen_magazalar))
                        with col4:
                            degismeyen = toplam_magaza - len(degisen_magazalar)
                            st.metric("⏸️ Değişmeyen", degismeyen)

                        if degisen_magazalar:
                            st.success(f"✅ {len(degisen_magazalar)} mağazada yeni sayım tespit edildi!")

                            # Değişen mağazaların listesi
                            with st.expander("🏪 Yeni Sayım Yapan Mağazalar"):
                                for mag in sorted(degisen_magazalar):
                                    mag_df = df[df['Mağaza Kodu'] == mag]
                                    if not mag_df.empty:
                                        envanter_sayisi = mag_df['Envanter Sayisi'].iloc[0]
                                        st.write(f"• {mag} - Envanter Sayısı: {envanter_sayisi}")

                            # Değişen mağazaların verilerini filtrele
                            degisen_df = df[df['Mağaza Kodu'].isin(degisen_magazalar)]
                            st.session_state['degisen_df'] = degisen_df
                            st.session_state['tam_df'] = df

                            # Değişen mağaza analizi
                            st.markdown("---")
                            st.markdown("### 📈 Değişen Mağazalar Özet")

                            toplam_fark = 0
                            toplam_fire = 0

                            col1, col2, col3 = st.columns(3)

                            with col1:
                                if 'Fark Tutarı' in degisen_df.columns:
                                    toplam_fark = pd.to_numeric(degisen_df['Fark Tutarı'], errors='coerce').sum()
                                st.metric("💰 Fark Tutarı", f"₺{toplam_fark:,.2f}")

                            with col2:
                                if 'Fire Tutarı' in degisen_df.columns:
                                    toplam_fire = pd.to_numeric(degisen_df['Fire Tutarı'], errors='coerce').sum()
                                st.metric("🔥 Fire Tutarı", f"₺{toplam_fire:,.2f}")

                            with col3:
                                toplam_acik = toplam_fark + toplam_fire
                                st.metric("📊 Toplam Açık", f"₺{toplam_acik:,.2f}")

                        else:
                            st.info("ℹ️ Yeni sayım yapan mağaza bulunamadı. Tüm veriler zaten güncel.")
                            st.session_state['degisen_df'] = None
                            st.session_state['tam_df'] = df

                        # Otomatik kaydet - sadece bir kere
                        st.markdown("---")
                        file_key = f"saved_{uploaded_file.name}_{len(df)}"
                        if file_key not in st.session_state:
                            eklenen, atlanan, toplam, mesaj = save_to_supabase(df)
                            if mesaj == "OK":
                                st.session_state[file_key] = True
                                if eklenen > 0:
                                    st.success(f"💾 {eklenen} yeni kayıt eklendi (delta hesaplandı)")
                                if atlanan > 0:
                                    st.info(f"⏭️ {atlanan} kayıt zaten mevcut (atlandı)")
                                if eklenen == 0 and atlanan > 0:
                                    st.warning("📋 Tüm kayıtlar zaten veritabanında mevcut.")
                            elif mesaj != "OK":
                                st.error(f"❌ Kayıt hatası: {mesaj}")
                        else:
                            st.info("💾 Veriler zaten kaydedildi.")
                    else:
                        st.warning("⚠️ Supabase bağlantısı yok.")
                        st.session_state['degisen_df'] = df
                        st.session_state['tam_df'] = df

            except Exception as e:
                st.error(f"Dosya okunamadı: {e}")
                import traceback
                st.error(traceback.format_exc())

# ==================== UYGULAMA BAŞLAT ====================
# Geçici: Giriş ekranı devre dışı - doğrudan uygulamaya gir
st.session_state.logged_in = True
st.session_state.username = "test"
st.session_state.user_role = "gm"
st.session_state.user_sm = None
main_app()
