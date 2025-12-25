import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime
import json
import os

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

# ==================== SUPABASE BAĞLANTISI ====================
supabase = None
try:
    from supabase import create_client, Client
    SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", ""))

    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        st.sidebar.success("✅ Supabase bağlandı")
    else:
        st.sidebar.warning("⚠️ Supabase secrets eksik")
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

        if st.button("Giriş", use_container_width=True):
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
    'Sayım Miktarı': 'sayim_miktari',
    'Sayım Tutarı': 'sayim_tutari',
    'Kaydi Miktar': 'kaydi_miktar',
    'Kaydi Tutar': 'kaydi_tutar',
    'Fark Miktarı': 'fark_miktari',
    'Fark Tutarı': 'fark_tutari',
    'Fire Miktarı': 'fire_miktari',
    'Fire Tutarı': 'fire_tutari',
    'Fark+Fire+Kısmi Envanter Miktarı': 'fark_fire_kismi_miktari',
    'Fark+Fire+Kısmi Envanter Tutarı': 'fark_fire_kismi_tutari',
    'Satış Miktarı': 'satis_miktari',
    'Satış Hasılatı': 'satis_hasilati',
    'İade Miktarı': 'iade_miktari',
    'İade Tutarı': 'iade_tutari',
    'İptal Fişteki Miktar': 'iptal_fisteki_miktar',
    'İptal Fiş Tutarı': 'iptal_fis_tutari',
    'İptal GP Miktarı': 'iptal_gp_miktari',
    'İptal GP TUTARI': 'iptal_gp_tutari',
    'İptal Satır Miktarı': 'iptal_satir_miktari',
    'İptal Satır Tutarı': 'iptal_satir_tutari',
}

def save_to_supabase(df):
    """
    Excel verisini Supabase'e kaydet (upsert)
    Unique key: magaza_kodu + malzeme_kodu + envanter_donemi + envanter_sayisi
    """
    if supabase is None:
        return 0, 0, "Supabase bağlantısı yok"

    try:
        records = []
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
                        # Türkçe ondalık formatındaki sayıları çevir (ör: "0,0" -> 0.0)
                        import re
                        if re.match(r'^-?\d+,\d+$', val):
                            try:
                                val = float(val.replace(',', '.'))
                            except:
                                pass
                    record[db_col] = val
            records.append(record)

        # Batch upsert
        batch_size = 500
        inserted = 0
        updated = 0

        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            try:
                result = supabase.table(TABLE_NAME).upsert(
                    batch,
                    on_conflict='magaza_kodu,malzeme_kodu,envanter_donemi,envanter_sayisi'
                ).execute()
                inserted += len(result.data) if result.data else 0
            except Exception as e:
                st.warning(f"Batch {i//batch_size + 1} hatası: {str(e)[:100]}")

        return inserted, updated, "OK"

    except Exception as e:
        return 0, 0, f"Hata: {str(e)}"

def get_mevcut_envanter_sayilari(magaza_kodlari, envanter_donemi):
    """
    Belirli mağazalar için mevcut envanter sayılarını getir
    Karşılaştırma için kullanılır
    """
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

@st.cache_data(ttl=300)
def get_available_periods():
    """Mevcut dönemleri getir - Supabase'den"""
    if supabase is None:
        return []
    try:
        result = supabase.table(TABLE_NAME).select('envanter_donemi').execute()
        if result.data:
            donemler = list(set(r['envanter_donemi'] for r in result.data if r['envanter_donemi']))
            return sorted(donemler, reverse=True)
        return []
    except:
        return []

@st.cache_data(ttl=300)
def get_available_sms():
    """Mevcut SM listesini getir - Supabase'den"""
    if supabase is None:
        return ["ALİ AKÇAY", "ŞADAN YURDAKUL", "VELİ GÖK", "GİZEM TOSUN"]
    try:
        result = supabase.table(TABLE_NAME).select('satis_muduru').execute()
        if result.data:
            sms = list(set(r['satis_muduru'] for r in result.data if r['satis_muduru']))
            return sorted(sms)
        return []
    except:
        return ["ALİ AKÇAY", "ŞADAN YURDAKUL", "VELİ GÖK", "GİZEM TOSUN"]

def get_gm_ozet_data(donemler):
    """GM Özet için verileri getir - retry mekanizmalı"""
    if supabase is None or not donemler:
        return None

    import time
    max_retries = 3

    try:
        # Seçili dönemlerdeki tüm verileri çek
        all_data = []
        batch_size = 500  # Daha küçük batch ile daha stabil

        for donem in donemler:
            offset = 0
            retry_count = 0
            while True:
                try:
                    result = supabase.table(TABLE_NAME).select(
                        'magaza_kodu,magaza_tanim,satis_muduru,bolge_sorumlusu,depolama_kosulu,fark_tutari,fire_tutari,satis_hasilati'
                    ).eq(
                        'envanter_donemi', donem
                    ).limit(batch_size).offset(offset).execute()

                    if result.data:
                        all_data.extend(result.data)
                        if len(result.data) < batch_size:
                            break
                        offset += batch_size
                        retry_count = 0  # Başarılı, retry sayısını sıfırla
                    else:
                        break
                except Exception as batch_err:
                    retry_count += 1
                    if retry_count >= max_retries:
                        st.warning(f"⚠️ Dönem {donem} için veri çekilemedi: {str(batch_err)[:50]}")
                        break
                    time.sleep(1)  # 1 saniye bekle ve tekrar dene
                    continue

        if all_data:
            df = pd.DataFrame(all_data)
            # bolge_sorumlusu yoksa veya hepsi null ise boş string ekle
            if 'bolge_sorumlusu' not in df.columns:
                df['bolge_sorumlusu'] = ''
            else:
                df['bolge_sorumlusu'] = df['bolge_sorumlusu'].fillna('')
            return df
        return None
    except Exception as e:
        st.error(f"Veri çekme hatası: {e}")
        return None

def get_onceki_envanter(magaza_kodu, malzeme_kodu, envanter_donemi, envanter_sayisi):
    """Bir önceki envanter sayısındaki kaydı getir"""
    if supabase is None or envanter_sayisi <= 1:
        return None

    try:
        result = supabase.table(TABLE_NAME).select('*').eq(
            'magaza_kodu', magaza_kodu
        ).eq(
            'malzeme_kodu', malzeme_kodu
        ).eq(
            'envanter_donemi', envanter_donemi
        ).eq(
            'envanter_sayisi', envanter_sayisi - 1
        ).execute()

        if result.data:
            return result.data[0]
        return None
    except:
        return None

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
        if st.button("🚪 Çıkış", use_container_width=True):
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
            # Veriyi çek
            gm_df = get_gm_ozet_data(selected_periods)

            if gm_df is not None and len(gm_df) > 0:
                st.caption(f"📊 {len(gm_df)} satır veri çekildi")

                magaza_sayisi = gm_df['magaza_kodu'].nunique()
                toplam_fark = gm_df['fark_tutari'].sum() if 'fark_tutari' in gm_df.columns else 0
                toplam_fire = gm_df['fire_tutari'].sum() if 'fire_tutari' in gm_df.columns else 0
                toplam_satis = gm_df['satis_hasilati'].sum() if 'satis_hasilati' in gm_df.columns else 0
                toplam_acik = toplam_fark + toplam_fire

                # Oran hesapla
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
            tabs = st.tabs(["👔 SM Özet", "📋 BS Özet", "🏪 Mağazalar", "📊 Top 10 Açık"])

            with tabs[0]:
                st.subheader("👔 Satış Müdürü Bazlı Özet")

                if gm_df is not None and len(gm_df) > 0 and 'satis_muduru' in gm_df.columns:
                    # SM bazlı grupla
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

                    # Her kategori için en iyi/kötü bul
                    kat_worst = {}
                    kat_best = {}
                    for e in ['🐓', '🥦', '🥖']:
                        vals = [(sm, sm_kat_oranlar[sm].get(e, 0)) for sm in sm_kat_oranlar if e in sm_kat_oranlar[sm]]
                        if vals:
                            kat_worst[e] = min(vals, key=lambda x: x[1])[0]  # En negatif = en kötü
                            kat_best[e] = max(vals, key=lambda x: x[1])[0]   # En az negatif = en iyi

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
                                use_container_width=True,
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
                                            'acik_pct': (acik_kat / s * 100) if s else 0
                                        }

                                # Kategori oranlarını string yap
                                kat_parts = [f"{e}{mag_kat[e]['acik_pct']:.1f}" for e in ['🐓', '🥦', '🥖'] if e in mag_kat]
                                kat_str = " ".join(kat_parts) if kat_parts else ""

                                acik_emoji = "🔴" if mag['Açık%'] < -5 else "🟡" if mag['Açık%'] < -2 else "🟢"
                                mag_title = f"{acik_emoji} **{mag_kodu}** {mag_tanim} | {kat_str} | Açık: {mag['Açık%']:.1f}%"

                                with st.expander(mag_title):
                                    # Özet metrikler
                                    c1, c2, c3, c4 = st.columns(4)
                                    with c1:
                                        st.metric("💰 Satış", f"₺{mag['satis_hasilati']:,.0f}")
                                    with c2:
                                        st.metric("📉 Fark", f"₺{mag['fark_tutari']:,.0f}")
                                    with c3:
                                        st.metric("🔥 Fire", f"₺{mag['fire_tutari']:,.0f}")
                                    with c4:
                                        st.metric("📊 Açık", f"₺{mag['Açık']:,.0f}")

                                    # Kategori detayları
                                    if mag_kat:
                                        st.markdown("**Kategori Kırılımı:**")
                                        for e in ['🐓', '🥦', '🥖']:
                                            if e in mag_kat:
                                                d = mag_kat[e]
                                                st.write(f"{e} Satış: ₺{d['satis']:,.0f} | Fark: ₺{d['fark']:,.0f} | Fire: ₺{d['fire']:,.0f} | Açık: %{d['acik_pct']:.1f}")
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
                        use_container_width=True,
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
                    st.dataframe(df.head(20), use_container_width=True)

                # Gerekli sütunlar kontrolü
                gerekli_sutunlar = ['Mağaza Kodu', 'Malzeme Kodu', 'Envanter Dönemi', 'Envanter Sayisi']
                eksik_sutunlar = [s for s in gerekli_sutunlar if s not in df.columns]

                if eksik_sutunlar:
                    st.error(f"❌ Eksik sütunlar: {', '.join(eksik_sutunlar)}")
                else:
                    # Otomatik işlem - buton yok
                    if supabase:
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
                            basarili, _, mesaj = save_to_supabase(df)
                            if mesaj == "OK" and basarili > 0:
                                st.session_state[file_key] = True
                                st.success(f"💾 {basarili} kayıt veritabanına kaydedildi!")
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
