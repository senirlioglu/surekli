"""
BS Özet Sekmesi
===============
Bölge Sorumlusu bazlı özet.
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


def render_bs_tab(
    scored_df: pd.DataFrame,
    raw_df: Optional[pd.DataFrame] = None
) -> None:
    """
    BS Özet sekmesini render et.

    Args:
        scored_df: Risk skorlu mağaza özeti
        raw_df: Ham veri (BS bilgisi için gerekli)
    """
    if raw_df is None or raw_df.empty:
        st.warning("BS özeti için ham veri gerekli.")
        return

    # BS sütunu kontrolü
    if 'bolge_sorumlusu' not in raw_df.columns:
        st.warning("Veri setinde 'bolge_sorumlusu' sütunu bulunamadı.")
        return

    # Boş BS'leri filtrele
    bs_df = raw_df[raw_df['bolge_sorumlusu'].notna() & (raw_df['bolge_sorumlusu'] != '')]

    if bs_df.empty:
        st.warning("Bölge sorumlusu verisi bulunamadı.")
        return

    # BS bazlı gruplama
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

    st.subheader(f"Bölge Sorumlusu Özeti - {len(bs_ozet)} BS")

    # Her BS için expander
    for _, row in bs_ozet.iterrows():
        bs_name = row['Bölge Sorumlusu']
        acik_pct = row['Açık%']

        # Risk rengine göre emoji
        if acik_pct < -5:
            risk_emoji = "🔴"
        elif acik_pct < -2:
            risk_emoji = "🟡"
        else:
            risk_emoji = "🟢"

        expander_title = f"{risk_emoji} {bs_name} | {row['Mağaza']:.0f} mağaza | Açık: {acik_pct:.1f}%"

        with st.expander(expander_title):
            # Özet metrikler
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Satış", f"₺{format_currency(row['Satış'])}")
            with c2:
                fark_pct = (row['Fark'] / row['Satış'] * 100) if row['Satış'] > 0 else 0
                st.metric("Fark", f"₺{format_currency(row['Fark'])}", f"%{fark_pct:.2f}")
            with c3:
                fire_pct = (row['Fire'] / row['Satış'] * 100) if row['Satış'] > 0 else 0
                st.metric("Fire", f"₺{format_currency(row['Fire'])}", f"%{fire_pct:.2f}")
            with c4:
                st.metric("Açık", f"₺{format_currency(row['Açık'])}", f"%{acik_pct:.2f}")

            # Bu BS'in mağazaları
            st.markdown("**Mağazalar:**")
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

            display_df = bs_magazalar.rename(columns={
                'magaza_kodu': 'Kod',
                'magaza_tanim': 'Mağaza',
                'fark_tutari': 'Fark',
                'fire_tutari': 'Fire',
                'satis_hasilati': 'Satış'
            })[['Kod', 'Mağaza', 'Satış', 'Fark', 'Fire', 'Açık', 'Açık%']]

            st.dataframe(display_df, use_container_width=True, hide_index=True)
