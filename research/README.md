# Penelitian XAUUSD: trend pullback

Rancangan dikunci di [PLAN.md](PLAN.md) sebelum hasil kandidat diperiksa. EA terpisah ada di [`Experts/TrendPullbackXAU`](../Experts/TrendPullbackXAU/). Tujuannya menguji hipotesis, bukan menjanjikan win rate 80%.

## Jenis bukti

1. Laporan Exness pengguna berisi order/deal strategi momentum lama. Laporan itu berguna untuk melihat biaya dan hasil strategi lama, **bukan** pengganti seluruh candle/tick untuk strategi baru.
2. Upaya awal memakai Dukascopy menghasilkan contoh candle, tetapi akses rentang panjang terganggu HTTP 503/timeout. `download_exness.py` mengambil arsip tick **publik Exness XAUUSD tanpa suffix**, memvalidasi urutan waktu/quote, lalu mengagregasi candle M1 BID dan ASK. Peralihan sumber dicatat sebelum melihat hasil; ini bukan perubahan aturan untuk mempercantik kinerja.
   Raw `.bi5`/ZIP, data turunan, hash dan metadata disimpan di `.hoplite/artifacts/xau-research/` yang tidak masuk Git. Exness menyebut arsip ini **indikatif** dan server tidak dapat dipilih; data bukan jaminan identik dengan server MT5Trial7 atau tipe akun pengguna.
3. `backtest_pullback.py` menguji aturan pada candle M1, bukan native tick. Hasilnya disebut **simulasi/proxy OHLC**, tidak boleh dilabeli backtest MT5 real ticks.

## Menjalankan simulator

Memerlukan Python 3.10+ (standard library). Unduh data publik dengan:

```sh
python3 research/download_exness.py --start 2024-12 --end 2026-09 --workers 3
```

Periksa bahwa **semua** bulan diminta berstatus `verified` dalam `exness/metadata.json`, lalu jalankan:

```sh
python3 research/backtest_pullback.py \
  .hoplite/artifacts/xau-research/exness/xauusd_m1_bid_ask_*_utc.csv \
  --out .hoplite/artifacts/xau-research/exness/simulation
```

Hanya masukkan file yang tercatat berhasil dalam metadata pengunduhan. Jangan menggunakan CSV lama dari percobaan sebelumnya yang gagal, mengisi data hilang dengan angka buatan, atau menganggap semua HTTP error adalah hari libur. Cakupan hasil harus menyebut periode yang benar-benar tersedia.

Status `verified` berarti **struktur arsip berhasil diperiksa**: CRC ZIP, header CSV, urutan waktu UTC dalam bulan yang diminta, harga/quote valid, dan SHA256. Itu bukan bukti independen bahwa penyedia tidak kehilangan tick atau sesi di sumbernya. Downloader menyimpan rentang tick pertama/terakhir dan jumlah data tiap bulan agar batas ini terlihat; hasil tetap bersifat indikatif.

Script melaporkan 2025 H1, 2025 H2, Januari–Mei 2026, dan Juni–Agustus 2026 secara terpisah, tanpa pencarian parameter. Jika tidak ada data suatu periode, hasil ditandai `available: false`, bukan dianggap nol transaksi/impas. Jika hanya ada sebagian periode, `observed_start`, `observed_last_minute`, dan metadata cakupan harus ditinjau; hasil parsial bukan hasil seluruh periode.

### Asumsi konservatif

- Sinyal M5 dan filter M15 hanya membaca bar yang sudah berakhir; tidak ada indikator dari candle masa depan.
- Agregasi mengikuti quote yang benar-benar ada: menit tanpa tick tidak dibuatkan candle. Satu bar M5/M15 boleh berisi kurang dari 5/15 candle M1 jika pada sebagian menit tidak ada tick, seperti bar berbasis tick MT5. Ini berbeda dari kehilangan file sumber; arsip bulanan harus lengkap dan lolos validasi sebelum hasil seluruh periode dinyatakan tersedia.
- ATR memakai SMA true range seperti contoh MetaQuotes, bukan Wilder smoothing. EMA memakai alpha 2/(N+1) dengan warmup terpisah.
- Entry memakai Ask untuk BUY, Bid untuk SELL, ditambah slippage merugikan. SL/TP BUY diuji terhadap Bid; SELL terhadap Ask.
- Jika dalam satu menit SL dan TP sama-sama tersentuh, dicatat sebagai ambigu dan **SL dianggap lebih dulu**. Urutan aslinya tidak diketahui dari OHLC.
- Gap melewati SL dieksekusi pada quote pembukaan yang lebih buruk; gap TP tidak diberi keuntungan harga ekstra.
- Komisi asumsi USD 0,04 round-trip pada 0,01 lot; slippage skenario dasar 0,05 per entry/exit market atau SL, skenario stres 0,15. TP diisi pada target tanpa slippage positif. Angka ini bukan tarif universal broker.
- Kontrak asumsi 100 oz/lot, akun USD, lot 0,01. Ini **tidak** mensimulasikan margin, stop-out, batas stop/freeze, partial fill, rejection atau latency broker.
- Batas waktu posisi 60 menit; saat tidak ada data/quote, keluar pada quote berikutnya. Jumlah posisi yang melewati hari UTC atau bertahan >60 menit dilaporkan. Swap tidak dimodelkan sehingga hasil dapat terlalu optimistis untuk posisi tersebut.
- Penyesuaian TP memakai harga entry setelah slippage dan dianggap berhasil dalam proxy. MT5 bisa menolak penyesuaian atau menutup posisi sebelum koreksi berhasil.
- Posisi terakhir ditutup pada akhir segmen dan ditandai `end_of_period`. Setiap segmen mulai tanpa posisi; indikator tetap memakai histori sebelumnya.
- Drawdown yang dihitung adalah drawdown akumulasi hasil **transaksi tertutup**, bukan equity drawdown tick-by-tick.
- Candle M1 tidak mengungkap detik tick pertama. Proxy hanya mencoba entry jika menit pertama bar M5 tersedia; batas kesiapan data 30 detik EA tidak dapat direplikasi persis.

Karena batas-batas ini, hasil proxy tidak cukup untuk penggunaan live. Langkah berikutnya tetap compile dan Strategy Tester MT5 dengan real ticks broker yang akan dipakai, diikuti validasi di periode yang belum dipakai menyesuaikan aturan.

## Pengujian kode riset

```sh
python3 -m unittest discover -s tests -p 'test_pullback_research.py' -v
```

Cakupan meliputi indikator, UTC, deteksi sinyal, lookahead/future mutation, OHLC dan quote yang invalid, spread relatif SL, exit Bid/Ask, gap, benturan SL/TP, timeout, komisi, satu posisi, serta data periode yang tidak tersedia. Pengujian ini memvalidasi implementasi model, bukan kemampuan menghasilkan profit.
