"""
UI Modülü - Streamlit Sekmeleri
===============================

Her tab dosyası:
- Sadece filtre + gösterim yapar
- Risk hesaplaması YAPMAZ
- Veri yükleme YAPMAZ
- Hazır df alır, render(df) döndürür
"""

from .tab_gm import render_gm_tab
from .tab_sm import render_sm_tab
from .tab_bs import render_bs_tab
from .tab_magaza import render_magaza_tab
from .tab_rapor import render_rapor_tab
from .tab_debug import render_debug_tab

__all__ = [
    'render_gm_tab',
    'render_sm_tab',
    'render_bs_tab',
    'render_magaza_tab',
    'render_rapor_tab',
    'render_debug_tab'
]
