# 🔍 Envanter Risk Analizi Sistemi

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://envanter-risk.streamlit.app)

Perakende envanter denetimi, iç/dış hırsızlık, kasa davranışı ve stok manipülasyonu analiz sistemi.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## 🎯 Ne İşe Yarar?

Bu uygulama, perakende mağazalarının envanter verilerini analiz ederek:
- 🔴 **İç hırsızlık** şüpheli durumları tespit eder
- 🟣 **Fire manipülasyonu** yapılan ürünleri bulur
- 🔵 **Kod karışıklığı** olan ürün ailelerini ayırır
- 🟠 **Kronik açık** veren ürünleri listeler
- 📊 Her mağaza için detaylı Excel raporu üretir

## 📦 Kurulum

### Yerel Kurulum

```bash
# Repo'yu klonla
git clone https://github.com/KULLANICI_ADI/envanter-risk-analizi.git
cd envanter-risk-analizi

# Bağımlılıkları yükle
pip install -r requirements.txt

# Uygulamayı çalıştır
streamlit run app.py
```

### 🌐 Streamlit Cloud'da Çalıştır

1. Bu repo'yu fork'la
2. [share.streamlit.io](https://share.streamlit.io) adresine git
3. GitHub hesabınla giriş yap
4. "New app" → Fork'ladığın repo'yu seç → Deploy!

## 🖥️ Demo

Uygulamayı canlı dene: **[envanter-risk.streamlit.app](https://envanter-risk.streamlit.app)**

## 📐 Temel Matematik Kuralları

| # | Durum | Formül | Sonuç |
|---|-------|--------|-------|
| 1 | ✅ Dengelenmiş | `Fark + Kısmi = -Önceki` | SORUN YOK |
| 2 | ⚠️ Kayıtsız Açık | `Fark + Kısmi + Önceki < 0` | AÇIK VAR |
| 3 | 🔴 İç Hırsızlık | `|Toplam| ≈ İptal` VE `Oran 1-5` | YÜKSEK RİSK |
| 4 | 🟣 Fire Manipülasyonu | `Fire > 0` AMA `Fark + Kısmi > 0` | FAZLA FİRE |
| 5 | 🔵 Kod Karışıklığı | `Aile Toplamı ≈ 0` | HIRSIZLIK DEĞİL |

## ⚠️ Kritik Kurallar

### İç Hırsızlık Tespiti
```
ORAN = |Fark + Kısmi + Önceki| / İptal Satır Miktarı

- Oran 1-5 arası → İç Hırsızlık ŞÜPHESİ
- Oran > 5 → İç Hırsızlık DEĞİL (orantısız)
```

**Örnek:** 1 iptal ama 30 açık = Oran 30 = **İç hırsızlık DEĞİL!**

### Aile/Kod Karışıklığı Analizi
Aynı **Mal Grubu** + Aynı **Marka** + Benzer isim = **Aile**

- Aile toplamı ≈ 0 → **Kod karışıklığı, hırsızlık DEĞİL**
- Benzer ürünlerde (renk, koku, ml farkı) kodlar karışabilir

### Fire Manipülasyonu
- Fire yüksek AMA Fark + Kısmi > 0 → **Fazladan fire giriliyor**

## 📊 Çıktılar

Her mağaza için ayrı Excel raporu:
1. **ÖZET** - Genel metrikler ve risk değerlendirmesi
2. **EN RİSKLİ 20 ÜRÜN** - En yüksek kayıplı ürünler
3. **KRONİK ÜRÜNLER** - Tekrarlayan sorunlu ürünler
4. **İÇ HIRSIZLIK DETAY** - Matematik eşitliği sağlayanlar
5. **AİLE ANALİZİ** - Kod karışıklığı tespiti
6. **FİRE MANİPÜLASYONU** - Şüpheli fire kayıtları

## 🏪 Çoklu Mağaza Desteği

- Veri içinde `Mağaza Kodu` sütunu varsa otomatik algılanır
- Her mağaza için ayrı rapor oluşturulur
- Tüm raporlar tek ZIP dosyasında indirilir

## 📋 Gerekli Sütunlar

| Sütun | Açıklama |
|-------|----------|
| Mağaza Kodu | Mağaza tanımlayıcı |
| Malzeme Kodu | SKU/Barkod |
| Malzeme Adı | Ürün adı |
| Mal Grubu | Kategori |
| Marka | Ürün markası (aile analizi için) |
| Fark Miktarı/Tutarı | Kaydi - Sayım |
| Kısmi Env. Miktarı/Tutarı | Dönem içi düzeltmeler |
| Önceki Fark Miktarı/Tutarı | Önceki dönem |
| İptal Satır Miktarı/Tutarı | Kasa iptalleri |
| Fire Miktarı/Tutarı | Kayıtlı fire |
| Satış Miktarı/Tutarı | Dönem satışları |

## 🚦 Risk Seviyeleri

| Seviye | Açık/Satış | İç Hırsızlık |
|--------|------------|--------------|
| 🔴 KRİTİK | > %2 | > 50 ürün |
| 🟠 RİSKLİ | > %1.5 | > 30 ürün |
| 🟡 DİKKAT | > %1 | > 15 ürün |
| 🟢 TEMİZ | < %1 | < 15 ürün |

## ⛔ Altın Kural

> **Matematik desteklemiyorsa SUÇLAMA YAPMA!**
> 
> Kurallar sağlanıyorsa net ve çekinmeden raporla.

## 📸 Ekran Görüntüleri

<details>
<summary>Görmek için tıkla</summary>

### Ana Ekran
Veri yükledikten sonra otomatik analiz başlar.

### Risk Özeti
Mağaza bazlı risk seviyesi ve metrikler.

### En Riskli Ürünler
Detaylı gerekçe ve aksiyon önerileri.

</details>

## 🤝 Katkıda Bulunma

1. Fork'la
2. Feature branch oluştur (`git checkout -b feature/YeniOzellik`)
3. Commit'le (`git commit -m 'Yeni özellik eklendi'`)
4. Push'la (`git push origin feature/YeniOzellik`)
5. Pull Request aç

## 📄 Lisans

MIT License - Detaylar için [LICENSE](LICENSE) dosyasına bakın.

## 👨‍💻 Geliştirici

**A101 Bölge Müdürlüğü** - Envanter Analiz Ekibi

---

⭐ Bu projeyi beğendiysen yıldız vermeyi unutma!
