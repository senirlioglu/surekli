"""
Sürekli Envanter Analizi - Ana Uygulama
=======================================
Modüler mimari: engine + ui

Veri akışı:
1. Supabase'den veri 1 kez yüklenir (cached)
2. Risk skorları 1 kez hesaplanır (cached)
3. Sekmeler hazır dataframe'i filtreler, hesaplama YAPMAZ

Dosya boyutu hedefi: 150-250 satır
"""

import streamlit as st
import pandas as pd
import os
import sys

# Modül yolunu ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Engine ve UI modülleri
from engine.bootstrap import build_dataset_with_raw, get_periods, get_sms
from engine.loader import get_supabase_client
from engine.scorer import get_risk_level
from ui.tab_gm import render_gm_tab
from ui.tab_sm import render_sm_tab
from ui.tab_bs import render_bs_tab
from ui.tab_magaza import render_magaza_tab
from ui.tab_rapor import render_rapor_tab
from ui.tab_debug import render_debug_tab

# ==================== SAYFA AYARI ====================
st.set_page_config(
    page_title="Sürekli Envanter Analizi",
    layout="wide",
    page_icon="📦"
)

# ==================== CSS STİLLERİ ====================
st.markdown("""
<style>
    .risk-kritik { background: linear-gradient(135deg, #ff4444, #cc0000); color: white; padding: 15px; border-radius: 10px; text-align: center; font-weight: bold; }
    .risk-riskli { background: linear-gradient(135deg, #ff8c00, #ff6600); color: white; padding: 15px; border-radius: 10px; text-align: center; font-weight: bold; }
    .risk-dikkat { background: linear-gradient(135deg, #ffd700, #ffcc00); color: #333; padding: 15px; border-radius: 10px; text-align: center; font-weight: bold; }
    .risk-temiz { background: linear-gradient(135deg, #00cc66, #009944); color: white; padding: 15px; border-radius: 10px; text-align: center; font-weight: bold; }
    @media (max-width: 768px) { .stMetric { font-size: 0.8rem; } }
</style>
""", unsafe_allow_html=True)

# ==================== SUPABASE BAĞLANTISI ====================
@st.cache_resource
def get_client():
    """Supabase client - cached."""
    try:
        from supabase import create_client
        url = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
        key = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", ""))
        if url and key:
            return create_client(url, key)
    except Exception as e:
        st.sidebar.error(f"Supabase bağlantı hatası: {e}")
    return None

# ==================== KULLANICI YÖNETİMİ ====================
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
    """Kullanıcıları secrets'tan al."""
    users = {}
    try:
        if "users" in st.secrets:
            for username, password in st.secrets["users"].items():
                role_info = USER_ROLES.get(username, {"role": "user", "sm": None})
                users[username] = {"password": password, **role_info}
    except:
        pass
    return users

USERS = get_users()

# ==================== SESSION STATE ====================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'user_sm' not in st.session_state:
    st.session_state.user_sm = None

# ==================== GİRİŞ EKRANI ====================
def login():
    st.markdown("## 📦 Sürekli Envanter Analizi")
    st.markdown("*Haftalık Et-Tavuk, Ekmek, Meyve/Sebze Takibi*")
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 🔐 Giriş Yap")
        username = st.text_input("Kullanıcı Adı")
        password = st.text_input("Şifre", type="password")

        if st.button("Giriş", use_container_width=True):
            if username in USERS and USERS[username]["password"] == password:
                st.session_state.logged_in = True
                st.session_state.user = username
                st.session_state.user_role = USERS[username]["role"]
                st.session_state.user_sm = USERS[username].get("sm")
                st.rerun()
            else:
                st.error("Hatalı kullanıcı adı veya şifre!")

# Giriş kontrolü
if not st.session_state.logged_in:
    login()
    st.stop()

# ==================== VERİ YÜKLEME (CACHED) ====================
@st.cache_data(ttl=600, show_spinner=False)
def load_data_cached(donemler_tuple, satis_muduru=None):
    """
    Veri yükle ve skorla - CACHED.
    donemler_tuple: Cache key için tuple olmalı.
    """
    client = get_client()
    if client is None:
        return pd.DataFrame(), pd.DataFrame(), {}

    donemler = list(donemler_tuple)
    raw_df, scored_df, metadata = build_dataset_with_raw(client, donemler, satis_muduru)
    return raw_df, scored_df, metadata

@st.cache_data(ttl=300)
def get_periods_cached():
    """Dönemleri getir - CACHED."""
    client = get_client()
    return get_periods(client) if client else []

@st.cache_data(ttl=300)
def get_sms_cached():
    """SM listesini getir - CACHED."""
    client = get_client()
    return get_sms(client) if client else []

# ==================== ANA UYGULAMA ====================
def main():
    # Sidebar
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.user}")
        st.markdown(f"*{st.session_state.user_role.upper()}*")
        st.markdown("---")

        # Menü
        is_gm = st.session_state.user_role == "gm"
        if is_gm:
            menu_options = ["🌍 GM Özet", "👔 SM Özet", "📋 BS Özet", "🏪 Mağaza Detay", "📥 Rapor", "🔧 Debug"]
        else:
            menu_options = ["👔 SM Özet", "📋 BS Özet", "🏪 Mağaza Detay", "📥 Rapor"]

        analysis_mode = st.radio("Analiz Modu", menu_options, label_visibility="collapsed")

        st.markdown("---")

        # Dönem seçimi
        available_periods = get_periods_cached()
        selected_periods = st.multiselect(
            "📅 Dönem",
            available_periods,
            default=available_periods[:1] if available_periods else []
        )

        # SM seçimi (GM için)
        selected_sm = None
        if is_gm and analysis_mode == "👔 SM Özet":
            available_sms = get_sms_cached()
            sm_options = ["📊 TÜMÜ"] + available_sms
            sm_selection = st.selectbox("👔 SM", sm_options)
            if sm_selection != "📊 TÜMÜ":
                selected_sm = sm_selection
        elif st.session_state.user_sm:
            selected_sm = st.session_state.user_sm

        st.markdown("---")
        if st.button("🚪 Çıkış", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.rerun()

    # Dönem seçilmemişse uyar
    if not selected_periods:
        st.warning("Lütfen en az bir dönem seçin.")
        st.stop()

    # Veri yükle (1 kez, cached)
    with st.spinner("📊 Veriler yükleniyor..."):
        raw_df, scored_df, metadata = load_data_cached(
            tuple(selected_periods),
            selected_sm
        )

    # Debug bilgisi (opsiyonel)
    if metadata:
        st.sidebar.caption(f"📊 {metadata.get('raw_rows', 0):,} satır | ⏱️ {metadata.get('total_time', 0):.2f}s")

    # Seçilen moda göre render
    if analysis_mode == "🌍 GM Özet":
        st.title("🌍 GM Özet - Bölge Dashboard")
        render_gm_tab(scored_df, raw_df)

    elif analysis_mode == "👔 SM Özet":
        st.title("👔 SM Özet")
        render_sm_tab(scored_df, raw_df, selected_sm)

    elif analysis_mode == "📋 BS Özet":
        st.title("📋 BS Özet")
        render_bs_tab(scored_df, raw_df)

    elif analysis_mode == "🏪 Mağaza Detay":
        st.title("🏪 Mağaza Detay")
        render_magaza_tab(raw_df)

    elif analysis_mode == "📥 Rapor":
        st.title("📥 Rapor İndir")
        render_rapor_tab(scored_df, raw_df, metadata)

    elif analysis_mode == "🔧 Debug":
        st.title("🔧 Debug / Performans")
        render_debug_tab(raw_df, scored_df, metadata)


# Entry point
if __name__ == "__main__":
    main()
else:
    main()
