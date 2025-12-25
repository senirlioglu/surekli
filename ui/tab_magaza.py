"""
Mağaza Detay Sekmesi
====================
Tek mağaza detaylı analizi.
"""

import streamlit as st
import pandas as pd
from typing import Optional, List


def format_currency(value: float) -> str:
    """Para formatı."""
    if abs(value) >= 1_000_000:
        return f"{value/1_000_000:.1f}M"
    elif abs(value) >= 1_000:
        return f"{value/1_000:.0f}K"
    return f"{value:,.0f}"


def render_magaza_tab(
    raw_df: pd.DataFrame,
    magaza_listesi: Optional[List[str]] = None
) -> None:
    """
    Mağaza detay sekmesini render et.

    Args:
        raw_df: Ham envanter verisi
        magaza_listesi: Opsiyonel mağaza listesi (dropdown için)
    """
    if raw_df.empty:
        st.warning("Veri bulunamadı.")
        return

    # Mağaza seçimi
    if magaza_listesi is None:
        if 'magaza_kodu' in raw_df.columns:
            magaza_listesi = sorted(raw_df['magaza_kodu'].unique().tolist())
        else:
            magaza_listesi = []

    if not magaza_listesi:
        st.warning("Mağaza listesi boş.")
        return

    # Mağaza adlarını da göster
    if 'magaza_tanim' in raw_df.columns:
        magaza_options = []
        for kod in magaza_listesi:
            tanim = raw_df[raw_df['magaza_kodu'] == kod]['magaza_tanim'].iloc[0] if len(raw_df[raw_df['magaza_kodu'] == kod]) > 0 else ""
            magaza_options.append(f"{kod} - {tanim}")
    else:
        magaza_options = magaza_listesi

    selected_option = st.selectbox("Mağaza Seçin", ["Seçiniz..."] + magaza_options)

    if selected_option == "Seçiniz...":
        st.info("Detay görmek için bir mağaza seçin.")
        return

    # Seçilen mağaza kodunu çıkar
    selected_magaza = selected_option.split(" - ")[0] if " - " in selected_option else selected_option

    # Mağaza verisini filtrele
    magaza_df = raw_df[raw_df['magaza_kodu'] == selected_magaza]

    if magaza_df.empty:
        st.warning(f"{selected_magaza} için veri bulunamadı.")
        return

    # Mağaza bilgisi
    magaza_tanim = magaza_df['magaza_tanim'].iloc[0] if 'magaza_tanim' in magaza_df.columns else ""
    st.subheader(f"🏪 {selected_magaza} - {magaza_tanim}")

    # Özet metrikler
    toplam_satis = magaza_df['satis_hasilati'].sum() if 'satis_hasilati' in magaza_df.columns else 0
    toplam_fark = magaza_df['fark_tutari'].sum() if 'fark_tutari' in magaza_df.columns else 0
    toplam_fire = magaza_df['fire_tutari'].sum() if 'fire_tutari' in magaza_df.columns else 0

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Satış", f"₺{format_currency(toplam_satis)}")
    with col2:
        fark_pct = (toplam_fark / toplam_satis * 100) if toplam_satis > 0 else 0
        st.metric("Fark", f"₺{format_currency(toplam_fark)}", f"%{fark_pct:.2f}")
    with col3:
        fire_pct = (toplam_fire / toplam_satis * 100) if toplam_satis > 0 else 0
        st.metric("Fire", f"₺{format_currency(toplam_fire)}", f"%{fire_pct:.2f}")
    with col4:
        urun_sayisi = len(magaza_df)
        st.metric("Ürün Sayısı", f"{urun_sayisi:,}")

    st.markdown("---")

    # Ürün listesi
    st.subheader("Ürün Listesi")

    display_cols = ['malzeme_kodu', 'malzeme_tanimi', 'satis_fiyati', 'fark_miktari', 'fark_tutari', 'fire_miktari', 'fire_tutari']
    existing_cols = [c for c in display_cols if c in magaza_df.columns]

    if existing_cols:
        display_df = magaza_df[existing_cols].copy()
        display_df.columns = ['Kod', 'Ürün', 'Fiyat', 'Fark Mkt', 'Fark TL', 'Fire Mkt', 'Fire TL'][:len(existing_cols)]

        # En yüksek açık veren ürünler üstte
        if 'Fark TL' in display_df.columns:
            display_df = display_df.sort_values('Fark TL', ascending=True)

        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.dataframe(magaza_df, use_container_width=True, hide_index=True)
