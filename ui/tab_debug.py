"""
Debug Sekmesi
=============
Performans ve veri istatistikleri.
"""

import streamlit as st
import pandas as pd
from typing import Optional, Dict, Any


def render_debug_tab(
    raw_df: pd.DataFrame,
    scored_df: pd.DataFrame,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Debug sekmesini render et.

    Args:
        raw_df: Ham veri
        scored_df: Skorlu özet
        metadata: Yükleme istatistikleri
    """
    st.subheader("🔧 Debug / Performans")

    # Veri istatistikleri
    st.markdown("### 📊 Veri İstatistikleri")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Ham Veri Satır", f"{len(raw_df):,}" if not raw_df.empty else "0")

    with col2:
        st.metric("Skorlu Mağaza", f"{len(scored_df):,}" if not scored_df.empty else "0")

    with col3:
        if not raw_df.empty and 'magaza_kodu' in raw_df.columns:
            unique_mag = raw_df['magaza_kodu'].nunique()
            st.metric("Unique Mağaza", f"{unique_mag:,}")
        else:
            st.metric("Unique Mağaza", "0")

    st.markdown("---")

    # Performans metrikleri
    if metadata:
        st.markdown("### ⏱️ Performans")

        p1, p2, p3, p4 = st.columns(4)

        with p1:
            load_time = metadata.get('load_time', 0)
            st.metric("Yükleme Süresi", f"{load_time:.3f}s")

        with p2:
            score_time = metadata.get('score_time', 0)
            st.metric("Skorlama Süresi", f"{score_time:.3f}s")

        with p3:
            total_time = metadata.get('total_time', 0)
            st.metric("Toplam Süre", f"{total_time:.3f}s")

        with p4:
            if metadata.get('raw_rows', 0) > 0 and total_time > 0:
                rows_per_sec = metadata['raw_rows'] / total_time
                st.metric("Satır/Saniye", f"{rows_per_sec:,.0f}")
            else:
                st.metric("Satır/Saniye", "-")

        st.markdown("---")

        # Metadata detayları
        st.markdown("### 📋 Metadata")
        st.json(metadata)

    st.markdown("---")

    # DataFrame bilgileri
    st.markdown("### 📑 DataFrame Bilgileri")

    tabs = st.tabs(["Ham Veri", "Skorlu Veri"])

    with tabs[0]:
        if not raw_df.empty:
            st.caption(f"Shape: {raw_df.shape}")
            st.caption(f"Columns: {list(raw_df.columns)}")
            st.caption(f"Memory: {raw_df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")

            with st.expander("İlk 10 satır"):
                st.dataframe(raw_df.head(10), use_container_width=True)
        else:
            st.info("Ham veri yok")

    with tabs[1]:
        if not scored_df.empty:
            st.caption(f"Shape: {scored_df.shape}")
            st.caption(f"Columns: {list(scored_df.columns)}")

            with st.expander("İlk 10 satır"):
                st.dataframe(scored_df.head(10), use_container_width=True)

            # Risk dağılımı
            if 'risk_puan' in scored_df.columns:
                st.markdown("**Risk Dağılımı:**")
                dist = pd.DataFrame({
                    'Seviye': ['KRİTİK (60+)', 'RİSKLİ (40-60)', 'DİKKAT (20-40)', 'TEMİZ (0-20)'],
                    'Sayı': [
                        len(scored_df[scored_df['risk_puan'] >= 60]),
                        len(scored_df[(scored_df['risk_puan'] >= 40) & (scored_df['risk_puan'] < 60)]),
                        len(scored_df[(scored_df['risk_puan'] >= 20) & (scored_df['risk_puan'] < 40)]),
                        len(scored_df[scored_df['risk_puan'] < 20])
                    ]
                })
                st.dataframe(dist, use_container_width=True, hide_index=True)
        else:
            st.info("Skorlu veri yok")

    st.markdown("---")

    # Cache temizleme
    st.markdown("### 🗑️ Cache Yönetimi")

    if st.button("🔄 Cache'i Temizle", use_container_width=True):
        st.cache_data.clear()
        st.success("Cache temizlendi! Sayfa yenilendiğinde veriler tekrar yüklenecek.")
        st.rerun()
