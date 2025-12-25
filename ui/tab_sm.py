"""
SM Özet Sekmesi
===============
Satış Müdürü bazlı özet.
"""

import streamlit as st
import pandas as pd
from typing import Optional


def format_currency(value: float) -> str:
    """Para formatı."""
    if abs(value) >= 1_000_000:
        return f"{value/1_000_000:.1f}M"
    elif abs(value) >= 1_000:
        return f"{value/1_000:.0f}K"
    return f"{value:,.0f}"


def render_sm_tab(
    scored_df: pd.DataFrame,
    raw_df: Optional[pd.DataFrame] = None,
    selected_sm: Optional[str] = None
) -> None:
    """
    SM Özet sekmesini render et.

    Args:
        scored_df: Risk skorlu mağaza özeti
        raw_df: Ham veri (opsiyonel)
        selected_sm: Seçili SM (opsiyonel, filtre için)
    """
    if scored_df.empty:
        st.warning("Veri bulunamadı.")
        return

    # SM filtresi uygulanmışsa bilgi göster
    if selected_sm:
        st.info(f"👔 {selected_sm} - Mağaza Özeti")

    # Özet metrikler
    toplam_satis = scored_df['satis'].sum() if 'satis' in scored_df.columns else 0
    toplam_fark = scored_df['fark'].sum() if 'fark' in scored_df.columns else 0
    toplam_fire = scored_df['fire'].sum() if 'fire' in scored_df.columns else 0
    toplam_acik = toplam_fark + toplam_fire

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Toplam Satış", f"₺{format_currency(toplam_satis)}")
    with col2:
        fark_pct = (toplam_fark / toplam_satis * 100) if toplam_satis > 0 else 0
        st.metric("Fark", f"₺{format_currency(toplam_fark)}", f"%{fark_pct:.2f}")
    with col3:
        fire_pct = (toplam_fire / toplam_satis * 100) if toplam_satis > 0 else 0
        st.metric("Fire", f"₺{format_currency(toplam_fire)}", f"%{fire_pct:.2f}")
    with col4:
        acik_pct = (toplam_acik / toplam_satis * 100) if toplam_satis > 0 else 0
        st.metric("Toplam Açık", f"₺{format_currency(toplam_acik)}", f"%{acik_pct:.2f}")

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

    # Sekmeler
    tabs = st.tabs(["📋 Sıralama", "🔴 Kritik", "🟠 Riskli", "📥 İndir"])

    with tabs[0]:
        st.subheader("Mağaza Sıralaması")

        display_cols = ['magaza_kodu', 'magaza_tanim', 'satis', 'fark', 'fire', 'acik_pct', 'risk_puan', 'risk_emoji']
        existing_cols = [c for c in display_cols if c in scored_df.columns]

        if existing_cols:
            display_df = scored_df[existing_cols].copy()
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.dataframe(scored_df, use_container_width=True, hide_index=True)

    with tabs[1]:
        st.subheader("Kritik Mağazalar")
        if 'risk_puan' in scored_df.columns:
            kritik_df = scored_df[scored_df['risk_puan'] >= 60]
            if len(kritik_df) > 0:
                st.dataframe(kritik_df, use_container_width=True, hide_index=True)
            else:
                st.success("Kritik mağaza yok!")
        else:
            st.info("Risk puanı hesaplanmadı.")

    with tabs[2]:
        st.subheader("Riskli Mağazalar")
        if 'risk_puan' in scored_df.columns:
            riskli_df = scored_df[(scored_df['risk_puan'] >= 40) & (scored_df['risk_puan'] < 60)]
            if len(riskli_df) > 0:
                st.dataframe(riskli_df, use_container_width=True, hide_index=True)
            else:
                st.success("Riskli mağaza yok!")
        else:
            st.info("Risk puanı hesaplanmadı.")

    with tabs[3]:
        st.subheader("Rapor İndir")
        st.info("Excel raporu indirmek için aşağıdaki butonu kullanın.")

        # Excel export
        if not scored_df.empty:
            from io import BytesIO

            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                scored_df.to_excel(writer, sheet_name='Özet', index=False)
            output.seek(0)

            st.download_button(
                label="📥 Excel İndir",
                data=output.getvalue(),
                file_name="sm_ozet_rapor.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
