"""
GM Özet Sekmesi
===============
Bölge geneli dashboard.
"""

import streamlit as st
import pandas as pd
from typing import Optional


def format_currency(value: float) -> str:
    """Para formatı: 1.5M, 150K, 1,500"""
    if abs(value) >= 1_000_000:
        return f"{value/1_000_000:.1f}M"
    elif abs(value) >= 1_000:
        return f"{value/1_000:.0f}K"
    return f"{value:,.0f}"


def render_gm_tab(
    scored_df: pd.DataFrame,
    raw_df: Optional[pd.DataFrame] = None
) -> None:
    """
    GM Özet sekmesini render et.

    Args:
        scored_df: Risk skorlu mağaza özeti
        raw_df: Ham veri (opsiyonel, kategori kırılımı için)
    """
    if scored_df.empty:
        st.warning("Veri bulunamadı. Lütfen dönem seçin.")
        return

    # Özet metrikler
    magaza_sayisi = len(scored_df)
    toplam_fark = scored_df['fark'].sum() if 'fark' in scored_df.columns else 0
    toplam_fire = scored_df['fire'].sum() if 'fire' in scored_df.columns else 0
    toplam_satis = scored_df['satis'].sum() if 'satis' in scored_df.columns else 0
    toplam_acik = toplam_fark + toplam_fire

    # Oranlar
    fark_oran = (toplam_fark / toplam_satis * 100) if toplam_satis != 0 else 0
    fire_oran = (toplam_fire / toplam_satis * 100) if toplam_satis != 0 else 0
    acik_oran = (toplam_acik / toplam_satis * 100) if toplam_satis != 0 else 0

    st.subheader(f"Bölge Özeti - {magaza_sayisi} Mağaza")

    # Metrik kartları
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Satış", f"₺{format_currency(toplam_satis)}")

    with col2:
        st.metric("Fark", f"₺{format_currency(toplam_fark)}", f"%{fark_oran:.2f}")

    with col3:
        st.metric("Fire", f"₺{format_currency(toplam_fire)}", f"%{fire_oran:.2f}")

    with col4:
        st.metric("Toplam Açık", f"₺{format_currency(toplam_acik)}", f"%{acik_oran:.2f}")

    st.markdown("---")

    # Risk dağılımı
    st.subheader("Risk Dağılımı")

    if 'risk_puan' in scored_df.columns:
        kritik = len(scored_df[scored_df['risk_puan'] >= 60])
        riskli = len(scored_df[(scored_df['risk_puan'] >= 40) & (scored_df['risk_puan'] < 60)])
        dikkat = len(scored_df[(scored_df['risk_puan'] >= 20) & (scored_df['risk_puan'] < 40)])
        temiz = len(scored_df[scored_df['risk_puan'] < 20])
    else:
        kritik = riskli = dikkat = temiz = 0

    r1, r2, r3, r4 = st.columns(4)
    r1.markdown(f'<div class="risk-kritik">🔴 KRİTİK: {kritik}</div>', unsafe_allow_html=True)
    r2.markdown(f'<div class="risk-riskli">🟠 RİSKLİ: {riskli}</div>', unsafe_allow_html=True)
    r3.markdown(f'<div class="risk-dikkat">🟡 DİKKAT: {dikkat}</div>', unsafe_allow_html=True)
    r4.markdown(f'<div class="risk-temiz">🟢 TEMİZ: {temiz}</div>', unsafe_allow_html=True)

    st.markdown("---")

    # Mağaza sıralaması
    st.subheader("Mağaza Sıralaması (Risk Puanına Göre)")

    display_cols = ['magaza_kodu', 'magaza_tanim', 'satis', 'fark', 'fire', 'acik', 'acik_pct', 'risk_puan', 'risk_emoji']
    existing_cols = [c for c in display_cols if c in scored_df.columns]

    if existing_cols:
        display_df = scored_df[existing_cols].copy()
        display_df.columns = ['Kod', 'Mağaza', 'Satış', 'Fark', 'Fire', 'Açık', 'Açık%', 'Puan', 'Risk'][:len(existing_cols)]

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.dataframe(scored_df, use_container_width=True, hide_index=True)
