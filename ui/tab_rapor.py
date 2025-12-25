"""
Rapor Sekmesi
=============
Excel rapor indirme.
"""

import streamlit as st
import pandas as pd
from io import BytesIO
from typing import Optional, Dict, Any


def render_rapor_tab(
    scored_df: pd.DataFrame,
    raw_df: Optional[pd.DataFrame] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Rapor sekmesini render et.

    Args:
        scored_df: Risk skorlu mağaza özeti
        raw_df: Ham veri (opsiyonel)
        metadata: Yükleme istatistikleri (opsiyonel)
    """
    st.subheader("📥 Rapor İndir")

    if scored_df.empty:
        st.warning("İndirilecek veri yok.")
        return

    # Metadata göster
    if metadata:
        st.markdown("**Veri Özeti:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Ham Satır", f"{metadata.get('raw_rows', 0):,}")
        with col2:
            st.metric("Mağaza Sayısı", f"{metadata.get('scored_rows', 0):,}")
        with col3:
            st.metric("Yükleme Süresi", f"{metadata.get('total_time', 0):.2f}s")

    st.markdown("---")

    # Rapor türü seçimi
    rapor_turu = st.radio(
        "Rapor Türü",
        ["Mağaza Özeti", "Detaylı Rapor", "Tüm Veriler"],
        horizontal=True
    )

    # Excel oluştur
    output = BytesIO()

    try:
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            if rapor_turu == "Mağaza Özeti":
                scored_df.to_excel(writer, sheet_name='Mağaza Özeti', index=False)

            elif rapor_turu == "Detaylı Rapor":
                scored_df.to_excel(writer, sheet_name='Mağaza Özeti', index=False)

                # Risk dağılımı sayfası
                if 'risk_puan' in scored_df.columns:
                    risk_dist = pd.DataFrame({
                        'Seviye': ['KRİTİK', 'RİSKLİ', 'DİKKAT', 'TEMİZ'],
                        'Sayı': [
                            len(scored_df[scored_df['risk_puan'] >= 60]),
                            len(scored_df[(scored_df['risk_puan'] >= 40) & (scored_df['risk_puan'] < 60)]),
                            len(scored_df[(scored_df['risk_puan'] >= 20) & (scored_df['risk_puan'] < 40)]),
                            len(scored_df[scored_df['risk_puan'] < 20])
                        ]
                    })
                    risk_dist.to_excel(writer, sheet_name='Risk Dağılımı', index=False)

            elif rapor_turu == "Tüm Veriler":
                scored_df.to_excel(writer, sheet_name='Mağaza Özeti', index=False)
                if raw_df is not None and not raw_df.empty:
                    # Ham veri çok büyükse ilk 50K satır
                    if len(raw_df) > 50000:
                        raw_df.head(50000).to_excel(writer, sheet_name='Ham Veri (İlk 50K)', index=False)
                        st.warning(f"Ham veri {len(raw_df):,} satır. İlk 50,000 satır dahil edildi.")
                    else:
                        raw_df.to_excel(writer, sheet_name='Ham Veri', index=False)

        output.seek(0)

        # İndirme butonu
        st.download_button(
            label=f"📥 {rapor_turu} İndir",
            data=output.getvalue(),
            file_name=f"surekli_envanter_{rapor_turu.lower().replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    except Exception as e:
        st.error(f"Rapor oluşturma hatası: {e}")
