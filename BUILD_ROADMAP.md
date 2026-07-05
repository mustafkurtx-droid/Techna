# Techna — İnşa Yol Haritası v11 (Antigravity 2.0 için)

> Bu doküman seni (uygulayıcı ajan) yönlendirir. **Fazları sırayla, tek tek** uygula.
> Her fazda **önce davranışı tanımla (Gherkin), sonra kodu yaz**. Tüm prose Türkçe; tüm
> kod, dosya adı, Gherkin senaryosu, test VE **rapor/grafik metni İngilizce** kalır.
>
> Faz 0–27 + test-sağlamlaştırma + grafik denetimi + zaman-serisi denetimi turları BİTTİ.
> Bu dokümandaki yeni iş **Faz 28–35**: teknik analiz kapsamını 8 fazda tamamlayan
> genişleme (çoklu zaman dilimi, olay tespiti, volume profile, stochastic, fibonacci,
> donchian, MFI+anchored VWAP, mum formasyonları).

> **KAPSAM SINIRLARI (değişmez):**
> - **VARTEX'e ait, buraya eklenmez:** risk-kantifikasyonu (VaR/CVaR, koşullu vol EWMA/GARCH,
>   Sharpe/Sortino/Calmar).
> - **FUNDALYZER'a ait, buraya eklenmez:** temel analiz (P/E, EV/EBITDA, peer/sektör
>   karşılaştırması, DCF, bilanço/gelir tablosu, valuasyon).
> - Techna, Fundalyzer ve Vartex ileride birleşecek üç ayrı programdır; Techna saf teknik
>   analiz (fiyat/hacim/istatistik) tarafında kalır, diğerlerinin kapsamına taşmaz.

> **BİLEREK KAPSAM DIŞI BIRAKILANLAR (ekleme, tartışma da açma):** Williams %R, CCI, ROC,
> TRIX (RSI/Stochastic'in matematiksel klonları — korelasyonlu gösterge enflasyonu sahte
> güven üretir), Ichimoku (bilgisi MA+ADX+levels'ta zaten var), Parabolic SAR / SuperTrend
> (stop-yerleştirme araçları; "signals not advice" sınırını ihlal eder), Elliott / harmonik
> formasyonlar (deterministik değil — iki analist aynı grafikte farklı sayar).

Proje kökü: `C:\TECHNA` · Python 3.11 (global).

---

# BÖLÜM A — BAĞLAM (değişmez, önce oku)

## A.1 Değişmez ilkeler
1. **LLM sayı üretmez/yorumlamaz.** Tüm hesap numpy/pandas/scipy/statsmodels.
2. **Saf fonksiyon.** `compute_x(...) -> dict/Series`. İçinde I/O yok.
3. **Betimsel, ASLA tavsiye.** Buy/sell/hold yok, fiyat hedefi yok. Her `finding`
   `assert_no_advice()` guard'ından geçer.
4. **Offline-first, test-driven.** Golden referanslar BAĞIMSIZ/elle türetilmiş — testin
   üretim kodunu "aynalaması" (aynı kod yolunu çağırıp çıktısını dondurması) YASAK.
5. **Spec-driven.** Kod yazmadan önce `specs/*.feature`.
6. **Human-in-the-loop kapıları.** `--no-interactive` atlar.
7. **Slopsquatting.** Yeni paket = PyPI doğrula + allowlist + verify_deps.
   **Faz 28–35'in HİÇBİRİ yeni paket GEREKTİRMEZ** — hepsi saf pandas/numpy. Yeni bir
   bağımlılık ekleme ihtiyacı hissedersen DUR, tasarımın yanlıştır.
8. **I/O sözleşmesi.** `io_contract.make_result(...)`; her run `{TICKER}_result.json` yazar.
   **Öğrenilmiş ders (kalıcı kural):** `metrics` dict'i SADECE state/finding taşımaz — finding
   cümlesini üreten HAM SAYILAR da JSON'a yazılır (örn. beta değeri, %K değeri, POC fiyatı).
   Dış tüketici her sayıyı doğrulayabilmeli.
9. **RAPORLAR İNGİLİZCE.** Türkçe metin rapora/JSON'a SIZAMAZ.
10. **Data-to-text tek-kaynak ilkesi:** her modülün `finding` cümlesi `report_builder.py`'de
    TEK fonksiyonda üretilir; markdown da JSON da AYNI fonksiyonu çağırır. Kopya yazma.
11. **Konsol çıktısı ASCII:** süslü unicode (→, ✓ vb.) Windows cp1254 konsolunda çöker
    (yaşandı). `rich` panel çerçeveleri hariç düz metinde ASCII kal.
12. **Kısmi-dönem disiplini:** kısmi ay/hafta asla tam dönem gibi rapor edilmez
    (seasonality'de yaşandı ve düzeltildi — yeni resample eden her faz aynı kurala uyar).

Stil: parametrik, edge case açık, anlamlı İngilizce hata, ham traceback YOK.
Kalite: yeni/değişen dosyalar `ruff check` + `mypy --ignore-missing-imports` temiz.

## A.2 Mevcut durum (Faz 0–27 + denetim turları DONE — yeniden yapma)
```
techna.py     orchestrator (--no-interactive/--no-chart/--no-notebook/--out/--benchmark/
              --explain/--period/--force-refresh) + her koşuda provenance satırı
              ("Data: cache|network | N bars | first to last")
techna/indicators/  trend, momentum, volatility, levels(+v2), regime, divergence, baserates,
                    relative, seasonality, volume, econometrics, risk_context   (13 modül)
techna/  config.py · data_layer.py (cache staleness guard: CACHE_STALE_DAYS, gerçek network
         yolunda otomatik yenileme, başarısızsa uyarıyla bayat cache) · io_contract.py ·
         security.py · scoring.py · briefing.py · report_builder.py
tests/  184 test, offline (chart-data-fidelity + json-metrics-completeness + cache-staleness
        + seasonality kısmi-ay dahil)
deps: yfinance, pandas<3, numpy, matplotlib, rich, pytest, statsmodels, scipy
      (+dev: ruff, mypy, vulture, pytest-cov, pip-audit)
      (+notebook-authoring: ta, nbformat, nbconvert, ipykernel — runtime'a girmez)
```
17 grafik. Her koşu varsayılan olarak taşınabilir `{TICKER}_report.ipynb` üretir: her modül
için finding + HAM metrik JSON'u + `compute_*` kaynak kodu (inspect.getsource, canlı) +
`draw_*_chart` kaynak kodu + base64-gömülü grafik. `--no-notebook` ile atlanır; `nbformat`
yoksa zarifçe uyarıp devam eder.
Doğrula: `python -m pytest -q` → 184 passed · ruff temiz · `mypy techna` + `mypy techna.py`
(İKİ AYRI geçiş — isim çakışması) Success.

## A.3 Her yeni faz için ZORUNLU entegrasyon adımları (unutulursa faz bitmemiştir)
Yeni bir modül/gösterge ekleyen HER faz şunları da yapar:
1. `techna.py`'de `io_contract.make_result(...)` çağrısı: state + HAM sayılar + `finding`.
2. `report_builder.py`'de tek-kaynak `<module>_finding(...)` fonksiyonu (`assert_no_advice`).
3. Markdown raporuna İngilizce bölüm.
4. **Notebook kaydı:** `render_report_notebook()` içindeki `module_mapping`'e modül adı,
   başlık, grafik dosyaları VE `compute_*` fonksiyon referansları eklenir (fonksiyon
   REFERANSI, isim string'i değil).
5. Yeni grafik varsa: `tests/test_chart_data_fidelity.py`'ye fidelity testi (mevcut
   `capture_fig` deseni: `_save` monkeypatch → matplotlib artist verisi == girdi verisi).
6. Golden fixture testleri (elle türetilmiş referans değerler) + edge case'ler
   (kısa veri, NaN, sıfır bölme).
7. Faz 29 SONRASI fazlar: yeni state'ler `events.py`'nin olay kataloğuna eklenir (Faz 29'un
   kataloğu genişletilebilir tasarlanır — tek satırlık ekleme olmalı).
8. README (gösterge tablosu + grafik sayısı) ve STATUS.md güncellenir.

## A.4 Çalışma protokolü
1. `STATUS.md` `in_progress`. 2. **Spec önce**. 3. **pytest**. 4. ruff+mypy temiz + `pytest -q`
hepsi geçer + gerçek ticker'da dene (JSON + rapor + notebook göz ile kontrol). 5. `STATUS.md`
`done`.

---

# BÖLÜM B — FAZLAR

## FAZ 28 — Çoklu Zaman Dilimi: Haftalık Teyit (`mtf` modülü)
**Amaç:** Günlük sinyalin bağlamını veren haftalık zaman dilimi. Gerçek analist iş akışının
en büyük eksiği. **Sıfır yeni matematik** — mevcut compute fonksiyonları haftalık barlarda
yeniden kullanılır.

**Dosyalar:** `techna/indicators/mtf.py` (yeni), `techna/config.py` (+sabitler),
`specs/mtf_weekly.feature`, `tests/test_mtf.py`, `report_builder.py` (+bölüm, +grafik,
+finding fonksiyonu), `techna.py` (+modül çağrısı).

**DONDURULMUŞ resample kuralları:**
- `df.resample("W-FRI")`: Open=`first`, High=`max`, Low=`min`, Close=`last`, Volume=`sum`.
- **Kısmi son hafta DÜŞÜLÜR** (ilke 12): son günlük bar, hafta etiketinin (Cuma) gününden
  farklıysa o hafta tamamlanmamıştır → at. Deterministik kural: son haftalık barın kapsadığı
  günlük bar sayısı ile son TAM haftanın bar sayısı kıyaslanmaz (tatil oynaklığı); onun yerine
  `son günlük barın tarihi >= hafta etiketi - 2 gün` ise hafta tam sayılır (Cuma tatilse
  Perşembe kapanışı tolere edilir), değilse düşülür.
- Boş haftalar (borsa kapalı) `dropna()` ile atılır.

**DONDURULMUŞ haftalık pencereler:** SMA(10) ve SMA(40) (günlük 50/200'ün yaklaşık haftalık
karşılığı — 2y veri ≈ 104 haftalık bar, SMA40 için yeterli), RSI(14), MACD(12,26,9), ADX(14).
Hepsi MEVCUT `compute_sma/compute_rsi/compute_macd/compute_adx` fonksiyonlarıyla — yeni
gösterge kodu YAZILMAZ, sadece haftalık DataFrame'e uygulanır.

**Çıktı (`compute_weekly_context(df) -> dict`):**
`weekly_bars` (int), `weekly_trend_state` (mevcut `trend_state` ile, SMA10/SMA40 üzerinden),
`weekly_rsi` + `weekly_rsi_state`, `weekly_macd_state`, `weekly_adx` + `weekly_trend_regime`,
`alignment`: `"aligned_bullish" | "aligned_bearish" | "mixed"` — günlük trend_state ile
haftalık trend_state karşılaştırması (ikisi de up → aligned_bullish; ikisi de down →
aligned_bearish; diğer her şey → mixed).

**Grafik (18.):** `{ticker}_weekly.png` — haftalık kapanış + SMA10/SMA40 üst panel,
haftalık RSI alt panel. Fidelity testi zorunlu.

**Rapor:** yeni "## 2.5. Weekly Timeframe Context" bölümü — günlük/haftalık uyum tablosu.

**Gherkin çekirdeği:**
```
Scenario: Partial final week is excluded
  Given daily data ending on a Wednesday
  When weekly bars are computed
  Then the final week is dropped and the last weekly bar is the prior full week
Scenario: Alignment state reflects daily and weekly trend agreement
  Given an uptrend on both daily and weekly timeframes
  Then alignment is "aligned_bullish"
```

**Testler:** elle türetilmiş küçük fixture'la resample golden'ı (5 haftalık bar, OHLCV
değerleri elle hesaplanmış); kısmi-hafta düşürme testi (Çarşamba biten veri); alignment'ın
3 durumu; kısa veri (<40 hafta) fallback'i (`status="warning"`, güvenli finding).

**DoD:** A.3 listesinin tamamı + 2y gerçek ticker'da haftalık bölüm elle doğrulanır.

---

## FAZ 29 — Olay Tespiti: "Bugün Ne Değişti" (`events` modülü)
**Amaç:** Otomasyonun asıl çıktısı. Günlük koşuda "dün olmayan bugün ne oldu" sorusunun
deterministik cevabı, raporun EN ÜSTÜNDE.

**TASARIM KARARI (dondurulmuş):** Olaylar SERİ-TABANLI hesaplanır (son iki bar
karşılaştırması) — önceki koşunun JSON'uyla diff DEĞİL. Gerekçe: seri-tabanlı tespit ilk
koşuda da çalışır, state dosyası gerektirmez, out_dir'den bağımsızdır ve golden testlerle
deterministik test edilir.

**Dosyalar:** `techna/indicators/events.py` (yeni), `specs/events.feature`,
`tests/test_events.py`, `report_builder.py`, `techna.py`.

**DONDURULMUŞ olay kataloğu (v1 — sonraki fazlar genişletir):**
Her olay `{"type": str, "direction": "bullish|bearish|neutral", "detail": str}`:
1. `rsi_zone_entry` / `rsi_zone_exit`: RSI dün <70 & bugün >=70 (veya 30 tarafı, veya çıkış).
2. `macd_hist_flip`: histogram işareti dün↔bugün değişti.
3. `ma_cross_today`: mevcut `detect_cross` çıktısında son barın cross'u "none" değil.
4. `bollinger_cross`: kapanış dün bant içi & bugün üst/alt bant dışı (veya içeri dönüş).
5. `range_52w_break`: bugünkü High > önceki 52w High (dünkü bara kadar hesaplanmış — shift(1)
   ile, look-ahead yok) veya Low < önceki 52w Low.
6. `vwap_cross`: kapanış VWAP'ın dün altında & bugün üstünde (veya tersi).
7. `structural_break_recent`: tespit edilen son yapısal kırılma son 5 bar içinde.

**Katalog mimarisi:** her olay tipi tek bir küçük saf fonksiyon
(`_ev_rsi_zone(rsi) -> list[dict]`), modül sonunda `EVENT_DETECTORS` listesinde toplanır —
Faz 31/33 buraya TEK SATIR ekleyerek genişletir. `compute_events(context) -> list[dict]`
hepsini çalıştırıp birleştirir.

**Rapor:** "## 0. Today's Events" — raporun İLK bölümü. Olay yoksa dürüstçe: "No state
changes detected on the last bar." JSON: `events` modülü, `metrics = {"count": N,
"events": [...], "finding": ...}`. Grafik YOK.

**Guard:** olay `detail` cümleleri de `assert_no_advice`'tan geçer.

**Testler:** her olay tipi için sentetik seri (örn. RSI'ı 69.9→70.1 yapan fiyat dizisi elle
kurulur); olaysız gün (boş liste + doğru finding); ilk koşu/kısa veri güvenliği; look-ahead
testi: `range_52w_break` bugünün barını 52w penceresine DAHİL ETMEDEN kıyaslıyor mu.

**DoD:** A.3 + gerçek ticker'da bir gün koşup Events bölümü göz ile doğrulanır.

---

## FAZ 30 — Volume Profile (fiyata-göre-hacim)
**Amaç:** Pivot-tabanlı S/R'a bağımsız ikinci kanıt: hangi fiyat seviyesinde ne kadar işlem
olduğu. POC ve Value Area.

**Dosyalar:** `techna/indicators/volume_profile.py` (yeni), `specs/volume_profile.feature`,
`tests/test_volume_profile.py`, `config.py` (+`VP_LOOKBACK=252`, `+VP_BINS=30`,
`+VP_VALUE_AREA=0.70`), `report_builder.py`, `techna.py`.

**DONDURULMUŞ algoritma (`compute_volume_profile(df, lookback, bins, value_area) -> dict`):**
1. Son `lookback` bar alınır (daha azsa hepsi + warning).
2. Fiyat aralığı `[min(Low), max(High)]` `bins` eşit kutuya bölünür.
3. Her barın hacmi, barın `[Low, High]` aralığının kestiği kutulara **kesişim oranıyla
   orantılı** dağıtılır (tamamını tek kutuya yazmak YOK — bar birden çok kutu kapsar).
   Low==High (tek fiyat) barında hacmin tamamı o kutuya.
4. **POC** = en yüksek hacimli kutunun orta fiyatı. Eşitlikte YÜKSEK fiyatlı kutu kazanır
   (dondurulmuş tie-break).
5. **Value Area (%70):** POC kutusundan başla; her adımda POC'a bitişik-üst ve bitişik-alt
   komşulardan hacmi BÜYÜK olanı ekle (eşitlikte üst); toplam hacim >= %70 olana dek.
   VAH = alanın en üst kutu üstü, VAL = en alt kutu altı.
6. `price_vs_value_area`: `above | inside | below` (son kapanışa göre).

**Çıktı:** `{"poc": float, "vah": float, "val": float, "state": ..., "bins": [...],
"volumes": [...], "lookback_used": int}`.

**Grafik (19.):** `{ticker}_volume_profile.png` — yatay barh histogram + POC/VAH/VAL yatay
çizgileri + son kapanış işareti. Fidelity testi: barh genişlikleri == volumes dizisi.

**Golden test (elle türetilmiş):** 4 bar × 3 kutu mini fixture; kesişim-oranlı dağıtım,
POC tie-break ve VA genişlemesi ELLE hesaplanıp sabitlenir. Ayna test YASAK.

**DoD:** A.3 + Faz 29 katalog güncellemesi GEREKMEZ (VP günlük olay üretmez) + gerçek
ticker'da POC/VA'nın grafikte ve levels bulgusuyla yan yana anlamlı olduğu göz ile doğrulanır.

---

## FAZ 31 — Stochastic Oscillator (14,3,3 slow) + base-rate koşulu
**Amaç:** RSI hız ölçer, Stochastic aralık-içi konum ölçer — tek gerçekten tamamlayıcı
klasik osilatör. Mevcut base-rates altyapısına yeni koşul olarak bağlanır.

**Dosyalar:** `techna/indicators/momentum.py` (+`compute_stochastic`), `config.py`
(+`STOCH_K=14, STOCH_SMOOTH=3, STOCH_D=3, STOCH_OVERBOUGHT=80, STOCH_OVERSOLD=20`),
`specs/stochastic.feature`, `tests/test_stochastic.py`, `report_builder.py`, `techna.py`,
`events.py` (+`stoch_zone_entry` dedektörü — tek satır katalog eklemesi).

**DONDURULMUŞ matematik (slow stochastic 14,3,3):**
```
raw_k[i] = 100 * (Close[i] - LL14[i]) / (HH14[i] - LL14[i])
   LL14 = rolling min(Low, 14, min_periods=14); HH14 = rolling max(High, 14, min_periods=14)
   HH14 == LL14 (sıfır aralık) → raw_k = NaN (sıfıra bölme YASAK; test zorunlu)
slow_k = SMA(raw_k, 3)   ·   d = SMA(slow_k, 3)
```
**State'ler:** `overbought (K>=80) | oversold (K<=20) | neutral`; `kd_cross`: son barda
K, D'yi yukarı/aşağı kesti mi (`golden_kd | death_kd | none`).

**Base-rate entegrasyonu:** `techna.py`'nin baserates bloğuna `cond_stoch = slow_k >= 80`
koşulu eklenir — RSI>=70 ve Bollinger koşullarıyla AYNI desende (`conditional_stats`,
`min_sample`, `reliable` bayrağı). Rapor base-rates tablosuna satır eklenir.

**Grafik:** momentum grafiği 3 panele çıkar (RSI / Stochastic K+D + 80/20 bölgeleri / MACD).
Mevcut momentum fidelity testi genişletilir.

**Golden test:** 20 barlık elle kurulmuş OHLC fixture'ında raw_k/slow_k/d İLK üç geçerli
değeri elle hesaplanıp sabitlenir. HH==LL edge testi. NaN warm-up uzunluğu testi (14+3-1+3-1).

**DoD:** A.3 + events kataloğu genişletildi + gerçek ticker'da 3 panel göz ile doğrulanır.

---

## FAZ 32 — Fibonacci Retracement + dürüst seviye-saygı testi
**Amaç:** Fib seviyelerini çiz AMA folklor olarak değil: bu hissede bu seviyelerin tarihsel
olarak gerçekten "tutup tutmadığını" mevcut base-rates disipliniyle ampirik raporla.

**Dosyalar:** `techna/indicators/fibonacci.py` (yeni), `config.py` (+`FIB_LOOKBACK=252`,
`+FIB_LEVELS=[0.236,0.382,0.5,0.618,0.786]`, `+FIB_TOUCH_ATR_MULT=0.25`),
`specs/fibonacci.feature`, `tests/test_fibonacci.py`, `report_builder.py`, `techna.py`.

**DONDURULMUŞ swing tanımı:** son `FIB_LOOKBACK` bar içinde `swing_high = max(High)`,
`swing_low = min(Low)`. Yön: swing_high'ın barı swing_low'un barından SONRAysa yukarı-swing
(retracement seviyeleri = high - level*(high-low)); önceyse aşağı-swing
(= low + level*(high-low)). Eşit tarihli olamaz; high==low (sıfır aralık) → modül
`status="warning"` + güvenli finding.

**DONDURULMUŞ dokunma/saygı testi (`fib_level_respect(df, levels, atr) -> list[dict]`):**
- "Dokunma" = barın `[Low, High]` aralığı `level ± FIB_TOUCH_ATR_MULT * ATR14[o bar]`
  bandını kesiyor VE önceki bar bandın DIŞINDA (her bar yeniden sayılmaz — banda GİRİŞ sayılır).
- Her giriş için mevcut `forward_return(close, 10)` değeri alınır; seviye başına
  `conditional_stats` (n, mean, win_rate, reliable) — mevcut min_sample disipliniyle.
- Çıktı dürüst: n küçükse `reliable: false` ve rapor bunu açıkça söyler
  ("insufficient touches to judge").

**Grafik (20.):** `{ticker}_fibonacci.png` — fiyat + swing high/low işaretleri + 5 seviye
yatay çizgi (etikette seviye oranı + fiyat). Fidelity testi.

**Rapor:** seviye tablosu + her seviyenin ampirik dokunma istatistiği. Finding örneği:
"Price is between the 0.382 (X) and 0.5 (Y) retracement levels of the 252-bar swing;
historical touch statistics are unreliable (n=3)."

**Testler:** elle kurulmuş üçgen swing fixture'ında 5 seviyenin fiyatları elle hesaplanır;
yön tespiti (yukarı/aşağı swing); banda giriş sayacı (aynı bandda kalan ardışık barlar tek
giriş); sıfır-aralık edge.

**DoD:** A.3 + gerçek ticker'da seviyelerin grafikle tutarlılığı göz ile doğrulanır.

---

## FAZ 33 — Donchian Kanalları (20/55) + nesnel kırılma state'i
**Amaç:** 52w mantığının genellemesi: nesnel, tarihsiz breakout tanımı (Turtle 20/55
konvansiyonu). Base-rate koşulu + olay dedektörü.

**Dosyalar:** `techna/indicators/donchian.py` (yeni), `config.py` (+`DONCHIAN_FAST=20,
DONCHIAN_SLOW=55`), `specs/donchian.feature`, `tests/test_donchian.py`, `report_builder.py`,
`techna.py`, `events.py` (+`donchian_breakout` dedektörü).

**DONDURULMUŞ matematik (look-ahead YASAK — test zorunlu):**
```
upper_n[i] = rolling max(High, n).shift(1)[i]   # BUGÜNÜN barı HARİÇ
lower_n[i] = rolling min(Low, n).shift(1)[i]
mid_n = (upper_n + lower_n) / 2
breakout_up_today   = High[son] > upper_n[son]
breakout_down_today = Low[son]  < lower_n[son]
channel_position = (Close - lower_n) / (upper_n - lower_n)   # 0..1; upper==lower → NaN
```
n=20 ve n=55 için ayrı ayrı. State: `breakout_up_20/55 | breakout_down_20/55 |
inside_channel` (55 önceliklidir: hem 20 hem 55 kırıldıysa 55 raporlanır).

**Base-rate entegrasyonu:** `cond_donchian55 = Close > upper_55` (shift'li seri — koşul
anında look-ahead yok) base-rates tablosuna eklenir.

**Grafik (21.):** `{ticker}_donchian.png` — fiyat + 20 (ince) ve 55 (kalın) kanalları.
Fidelity testi.

**Testler:** elle kurulmuş 10-bar fixture'da upper/lower İLK değerleri elle; shift(1)
look-ahead testi (bugünkü yeni zirve kendi kanalını YÜKSELTMEZ — kırılma sayılır);
upper==lower edge; events dedektör testi.

**DoD:** A.3 + events kataloğu genişletildi + base-rates satırı + göz doğrulaması.

---

## FAZ 34 — MFI(14) + Anchored VWAP (hacim ailesinin tamamlanması)
**Amaç:** MFI = hacim-ağırlıklı momentum (momentum↔volume köprüsü); Anchored VWAP =
belirli olaydan bu yana ortalama maliyet çizgisi. İkisi de mevcut volume modülünü genişletir.

**Dosyalar:** `techna/indicators/volume.py` (+`compute_mfi`, `+compute_anchored_vwap`),
`config.py` (+`MFI_PERIOD=14, MFI_OVERBOUGHT=80, MFI_OVERSOLD=20`),
`specs/mfi_avwap.feature`, `tests/test_mfi_avwap.py`, `report_builder.py`, `techna.py`.

**DONDURULMUŞ MFI matematiği:**
```
TP = (High+Low+Close)/3;  RMF = TP * Volume
pos_flow[i] = RMF[i] eğer TP[i] > TP[i-1], yoksa 0   (TP[i]==TP[i-1] → HER İKİSİ 0)
neg_flow[i] = RMF[i] eğer TP[i] < TP[i-1], yoksa 0
MFI = 100 - 100 / (1 + rolling_sum(pos,14) / rolling_sum(neg,14))
   rolling_sum(neg,14) == 0 → MFI = 100.0 (sıfıra bölme yasak; test zorunlu)
```
State: `overbought (>=80) | oversold (<=20) | neutral`.

**DONDURULMUŞ Anchored VWAP:** `AVWAP[i] = cumsum(TP*V)[anchor..i] / cumsum(V)[anchor..i]`.
ÜÇ sabit anchor: (1) 52w düşük tarihi, (2) 52w yüksek tarihi, (3) içinde bulunulan yılın ilk
barı. Her biri için son kapanışın üstünde/altında state'i. Anchor bulunamazsa (kısa veri)
o anchor atlanır + warning.

**Grafik:** mevcut volume grafiği genişler — üst panele 3 AVWAP çizgisi (etiketli), MFI
için yeni alt panel (80/20 bölgeleriyle). Volume fidelity testi genişletilir.

**Testler:** 6 barlık elle MFI fixture'ı (pos/neg flow elle toplanır); neg==0 → MFI=100
edge; TP eşitliği edge; AVWAP elle 4-bar fixture'ı; anchor-yok fallback.

**DoD:** A.3 + gerçek ticker'da AVWAP çizgilerinin anchor noktalarından başladığı göz ile.

---

## FAZ 35 — Mum Formasyonları (seçilmiş 5) + formasyon başına base-rate
**Amaç:** Formasyon hayvanat bahçesi DEĞİL — 5 net tanımlı formasyon + her birinin bu
hissedeki ampirik geçmiş performansı ("bu formasyon bu hissede gerçekten bir şey ifade
ediyor mu" — dürüst cevap).

**Dosyalar:** `techna/indicators/candles.py` (yeni), `config.py` (+eşikler),
`specs/candle_patterns.feature`, `tests/test_candle_patterns.py`, `report_builder.py`,
`techna.py`, `events.py` (+`candle_pattern_today` dedektörü).

**DONDURULMUŞ tanımlar** (body=|C-O|, range=H-L, upper=H-max(O,C), lower=min(O,C)-L;
range==0 → hiçbir formasyon eşleşmez):
1. `doji`: body <= 0.10 * range.
2. `hammer`: lower >= 2.0*body VE upper <= 0.30*body VE body > 0 VE son 10 barın kapanış
   eğimi negatif (düşüş bağlamı — bağlamsız hammer anlamsızdır; eğim `np.polyfit` ile).
3. `shooting_star`: hammer'ın aynası (upper >= 2*body, lower <= 0.3*body, yükseliş bağlamı).
4. `bullish_engulfing`: dünkü body kırmızı (C<O), bugünkü yeşil (C>O), bugünün body'si
   dünün body'sini TAM kapsar (O_today <= C_yest VE C_today >= O_yest), body_today > 0.
5. `bearish_engulfing`: aynası.

**Base-rate:** her formasyon için tüm tarihte eşleşen barlar bulunur, `forward_return(close,
10)` + `conditional_stats` — formasyon başına n / mean / win_rate / reliable. Rapor tablo
halinde; n küçükse "unreliable" açıkça yazılır.

**Grafik:** yeni grafik YOK — mevcut candlestick grafiğinde son 90 bar içindeki eşleşmeler
işaretlenir (marker + kısaltma etiketi). Candles fidelity testi genişletilir (marker
pozisyonları == eşleşen bar indeksleri).

**Testler:** her formasyon için elle kurulmuş 2-3 barlık OHLC örneği (pozitif VE negatif
örnek — "neredeyse hammer ama upper shadow uzun" gibi); range==0 edge; bağlam eğimi testi
(aynı mum, yükseliş bağlamında hammer DEĞİL); base-rate entegrasyon testi.

**DoD:** A.3 + events dedektörü + gerçek ticker'da işaretli mum grafiği göz ile doğrulanır.

---

# BÖLÜM C — Global Definition of Done (Faz 35 sonrası)
- `python -m pytest -q` tamamı geçer (offline, deterministik). Hiçbir LLM sayısı, hiçbir tavsiye.
- 13 → 19+ modül; 17 → 21 grafik; her yeni modül notebook'ta finding + ham metrik + kaynak
  kodu + grafik zinciriyle görünür.
- Events bölümü raporun en üstünde; katalog Faz 31/33/35 dedektörlerini içerir.
- Base-rates tablosu 2 → 5+ koşul (RSI, Bollinger, Stochastic, Donchian55, formasyonlar).
- Yeni bağımlılık YOK (8 fazın hiçbirinde). Kapsam sınırları ihlal edilmedi.
- ruff temiz · mypy 2-geçiş Success · chart-fidelity testleri tüm yeni grafikleri kapsıyor.
- README gösterge/grafik envanteri güncel · STATUS.md her faz için ayrı narrative içeriyor.
- Final test sayısı + süre raporlanır; gerçek ticker'da tam koşu (rapor+JSON+notebook+21
  grafik) göz ile doğrulanır.
