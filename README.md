# Momentum Candle XAU — Expert Advisor MT5

## Penelitian lanjutan: win rate tinggi dan target USD 100/minggu

**[Hasil 36 konfigurasi strategi](research/high_win/RESULTS.md): belum ada yang lolos kriteria ketahanan biaya, dan target USD 20/hari atau USD 100/minggu pada lot 0,01 belum terbukti.** Win rate pengembangan tertinggi 60,85% hanya menghasilkan sekitar USD 4,35 sepanjang 2025 dan merugi pada biaya stres. Ini bukan strategi pendapatan tetap.

EA pembanding **[`SweepReclaimXAU.mq5`](Experts/SweepReclaimXAU/SweepReclaimXAU.mq5)** tetap disediakan untuk eksperimen/tester, bukan sebagai kandidat yang lolos. Default akun riil diblokir. Pemeriksaan khusus atas **21.270.986 tick publik** Juni–Agustus 2026 menghasilkan net **−USD 40,37**, bukan target tersebut. Replay kustom ini bukan Strategy Tester MT5; native compile belum tersedia. [Aturan dan pemasangan](Experts/SweepReclaimXAU/README.md) · [Metode dan reproduksi](research/high_win/README.md).

Semua EA sebelumnya di bawah tetap dipertahankan; jangan jalankan beberapa EA pada simbol yang sama.

## Kandidat baru: Trend Pullback XAU

EA eksperimen terpisah tersedia di **[`TrendPullbackXAU.mq5`](Experts/TrendPullbackXAU/TrendPullbackXAU.mq5)**: satu file, XAUUSD **M5**, filter tren M15, entry market setelah pullback, lot tetap **0,01**, RR **1:1,5**, dan timeout default **60 menit**. [Panduan pemasangan dan aturan](Experts/TrendPullbackXAU/README.md) · [Metode riset candle historis](research/README.md).

Ini kandidat untuk diuji, **bukan strategi yang telah terbukti lebih baik atau memiliki win rate 80%**. Jangan jalankan bersama EA momentum pada simbol yang sama. Versi momentum di bawah tetap dipertahankan tanpa perubahan.

**[Hasil penelitian](research/RESULTS.md):** proxy OHLC dari arsip publik Exness menghasilkan win rate **42,39%** dan hampir impas sebelum swap pada asumsi dasar; skenario slippage lebih buruk merugi. Kandidat ini **belum layak live** dan belum dikompilasi/backtest melalui MT5 di workspace ini.

**Versi 1.03: langsung entry market setelah candle momentum tutup, RR default 1:1, lot tetap 0,01.** Khusus XAUUSD M5/M15, berdasarkan indikator Pine “Momentum Candle Sekolah Trading”. Tidak ada lagi Buy Stop/Sell Stop atau syarat breakout. Ini perubahan aturan untuk diuji, **bukan klaim peningkatan win rate atau profit**.

## Satu file dan pemasangan

1. Di MT5 pilih **File → Open Data Folder**.
2. Unduh [`MomentumCandleXAU.mq5`](Experts/MomentumCandleXAU/MomentumCandleXAU.mq5) melalui **Download raw file**, lalu simpan di `MQL5/Experts/` atau subfolder `MomentumCandleXAU/`. Jangan menyimpan halaman HTML GitHub sebagai `.mq5`.
3. Buka file di **MetaEditor MT5**, bukan MT4 atau Pine Editor; tekan **F7**. Tidak memerlukan file pendukung proyek. `Trade\Trade.mqh` adalah library standar bawaan MT5.
4. Ganti EA lama, reset Inputs, lalu pastikan **`InpRewardRisk = 1.0`** dan **`InpFixedLots = 0.01`**. Preset lama bisa menyimpan RR 2; file baru tidak menimpa input tersimpan. Catat dan masukkan ulang pengaturan filter lama jika ingin perbandingan yang hanya mengubah entry/RR.
5. Jalankan di Strategy Tester/demo terlebih dahulu. Aktifkan Algo Trading untuk chart demo. Gunakan satu instance per simbol per akun.

EA tetap menolak entry saat ada posisi/order pada simbol tersebut, termasuk transaksi manual atau EA lain. Pemeriksaan ini bukan kunci atomik lintas-EA; jangan menjalankan beberapa instance sekaligus. **Pending dan posisi versi lama tidak otomatis dibatalkan/diubah.** Tunggu selesai atau batalkan pending lama sebelum pengujian baru. Penyesuaian TP hanya berlaku pada posisi dengan simbol, magic dan komentar `MomentumXAU_Market` milik versi market.

Nama simbol berawalan `XAUUSD` seperti `XAUUSDm` diterima, atau nama lain dengan metadata base `XAU` dan profit currency `USD`. Simbol `GOLD` dapat diterima jika metadatanya sesuai. Broker harus mendukung candle Bid, market order, dan SL/TP bersama order. Dukungan expiry pending tidak diperlukan lagi.

## Aturan sinyal dan entry

| Komponen | Default |
|---|---|
| Waktu sinyal | Candle terakhir yang **sudah tutup**, shift 1 |
| Entry BUY | Candle momentum bullish valid → market BUY pada Ask |
| Entry SELL | Candle momentum bearish valid → market SELL pada Bid |
| Minimum body | M5: 35 pip (harga 3,50); M15: 45 pip (harga 4,50) |
| Definisi pip emas | `InpGoldPipSize = 0.10`, tidak otomatis mengikuti jumlah digit broker |
| Wick | Total wick atas+bawah maksimal 30% high−low |
| Mode wick | Agresif; `InpConservativeWick = false` |
| Konsolidasi | Nonaktif; jika aktif, N body sebelumnya harus lebih kecil dari body sinyal |
| Filter EMA | Aktif, H1 periode 50; BUY close > EMA, SELL close < EMA |
| Nilai EMA | H1 terakhir yang sudah tutup, bukan H1 berjalan |
| Filter lonjakan | Lewati range candle > 2,5 × ATR(14) pada TF chart |
| SL BUY | Low candle sinyal − 0,15 × ATR |
| SL SELL | High candle sinyal + 0,15 × ATR + spread saat pengiriman |
| TP | Default 1 × jarak entry–SL; disesuaikan terhadap harga fill aktual |
| Volume request | `InpFixedLots = 0.01`; tidak mengikuti balance/equity |
| Batas spread | 0,50 dalam satuan harga emas, bukan 0,50 point |
| Deviation request | `InpDeviationPoints = 50` dalam point broker |

**“Langsung setelah close” berarti tick pertama candle baru saat data siap dan seluruh pemeriksaan lolos**, bukan timer yang mengeksekusi tanpa tick. Tidak menunggu harga melewati high/low candle dan tidak menunggu pullback. Setelah baru dipasang/restart, EA menunggu close berikutnya agar tidak mengejar sinyal lama.

EA mengevaluasi satu sinyal per candle. Jika indikator/history belum siap, pembacaan data dicoba ulang maksimal 30 detik dari awal bar (`InpMaxSignalDelaySeconds`). Jika filter, spread, volume, izin trading, margin atau jarak stop gagal, sinyal dilewati; tidak mengejar entry belakangan. Candle yang terpisah dari bar baru oleh jeda sesi/data juga dilewati.

Buffer SL minimal satu tick. SL dan TP dibulatkan sesuai tick size; TP dibulatkan keluar sehingga RR bisa sedikit lebih besar dari input, kurang dari satu tick selisih jarak target. Candle dan SL BUY menggunakan Bid, sedangkan SL SELL dipicu Ask, sehingga SL SELL mendapat allowance spread.

Mode wick konservatif mempertahankan rumus Pine asli: bullish `lowerWick < upperWick`, bearish `upperWick < lowerWick`. Ini bukan pola rejection dengan ekor panjang di sisi berlawanan, dan nama “konservatif” bukan jaminan akurasi lebih tinggi. Aturan body, wick, konsolidasi, EMA dan ATR tidak diubah dari versi 1.02.

## Contoh BUY — bukan rekomendasi harga saat ini

Candle sinyal sudah tutup: open 3000, close 3005,50, high 3006, low 2999. ATR 5, tick size 0,01, quote setelah close Bid 3005,50 / Ask 3005,80, dan semua filter lolos:

- **Market BUY** dengan quote entry 3005,80; tidak menunggu high 3006 ditembus.
- SL = 2999 − 0,75 = **2998,25**.
- Risiko jarak = 3005,80 − 2998,25 = **7,55**.
- TP awal = 3005,80 + 7,55 = **3013,35**.
- Jika fill aktual 3005,90, SL tetap 2998,25; target disesuaikan menjadi **3013,55**, bukan memakai close candle atau quote lama.
- Dengan kontrak 100 oz/lot, request 0,01 lot, dan fill 3005,80, estimasi kerugian ke SL sekitar USD 7,55 sebelum biaya. Kontrak broker/mata uang akun lain bisa berbeda.

## Harga fill dan proteksi posisi

SL dan TP awal **dikirim bersama market order**, berdasarkan quote sebelum pengiriman. EA tidak sengaja membuka posisi tanpa stop untuk mengejar RR yang presisi. Setelah posisi terlihat, TP dihitung ulang memakai `POSITION_PRICE_OPEN` aktual (termasuk harga rata-rata jika terjadi partial fills) dan SL posisi yang sama.

Penyesuaian dilakukan segera setelah respons order dan pada tick berikutnya, maksimal sekali per detik waktu server. Hanya TP yang diubah; SL tidak dilebarkan. Jika sudah sesuai, tidak ada request modifikasi. Jika stop/freeze level, izin trading atau server menghalangi perubahan, EA mempertahankan SL/TP yang sedang berlaku, mencatat peringatan Journal, dan mencoba penyesuaian lagi pada tick selanjutnya. **RR aktual dapat sementara/tetap berbeda jika penyesuaian belum berhasil atau posisi sudah ditutup terlebih dahulu.** Broker harus mempertahankan komentar posisi `MomentumXAU_Market` agar EA mengenalinya untuk penyesuaian; jika komentar diubah broker, SL/TP awal tetap berlaku tanpa koreksi fill otomatis.

Tidak ada trailing stop, breakeven, averaging, martingale, atau close saat sinyal berlawanan. Jangan mengubah SL/TP secara manual sambil EA mengelola targetnya. Tidak ada batas durasi posisi atau filter berita/jam trading; posisi dapat melewati rollover/weekend.

## Batas risiko dan eksekusi

- **Lot tetap bukan risiko uang tetap.** SL yang lebih jauh menghasilkan kerugian nominal lebih besar. Tidak ada batas kerugian berupa persen modal atau batas rugi harian. Modal tetap harus cukup untuk margin dan menanggung kerugian.
- Volume harus sesuai min/max/step broker. Jika 0,01 tidak didukung, EA gagal inisialisasi dengan pesan jelas, bukan menaikkan/menurunkan lot. Volume diperiksa ulang sebelum pengiriman.
- `OrderCalcProfit` hanya memperkirakan kerugian ke SL dalam mata uang akun untuk Journal, bukan menentukan volume. Komisi, swap dan slippage belum termasuk estimasi.
- Estimasi margin harus tidak melebihi 90% free margin. SL/TP harus memenuhi jarak broker terhadap **Bid untuk BUY, Ask untuk SELL**, bukan hanya terhadap harga entry.
- Filling policy mengikuti broker (`SetTypeFillingBySymbol`, FOK dipilih jika tersedia). Jika broker hanya mendukung partial fill, volume terisi bisa lebih kecil daripada request; EA tidak menambah order untuk mengejar sisanya.
- Respons order diperiksa melalui retcode. Requote, rejection, timeout atau hasil tidak pasti tidak memicu pengiriman ulang. Respons accepted/partial tidak dianggap bukti fill penuh; posisi aktual yang terlihat menjadi dasar TP. Periksa Experts/Journal.
- Deviation bukan jaminan batas slippage pada semua execution mode; pada Market Execution broker dapat mengabaikannya. Gap, spread dan fill dapat membuat hasil berbeda dari rencana 1:1.
- Menonaktifkan Algo Trading/melepas EA tidak menutup posisi. Stop/target yang sudah diterima server tetap mengikuti aturan broker; penyesuaian TP membutuhkan EA aktif. Hindari penggunaan live sebelum validasi.

## Backtest versi baru

**Belum ada kompilasi MetaEditor atau backtest MT5 versi 1.03 di workspace ini.** Lingkungan Linux ini tidak menyediakan MT5/MetaEditor atau tick broker. Hasil backtest versi breakout sebelumnya tidak membuktikan hasil mode market 1:1.

1. Compile di MetaEditor; jika gagal, kirim 5 error pertama beserta nomor baris dan build MT5. Jangan lanjut live jika ada error.
2. Pilih EA, XAUUSD broker yang sama, dan M5 atau M15. Gunakan **Every tick based on real ticks**.
3. Reset input, pastikan RR 1 dan lot 0,01, lalu masukkan ulang filter yang ingin dibandingkan. Samakan deposit, leverage, biaya, TF dan periode dengan baseline. Versi 1.02 di histori Git tetap menjadi baseline breakout RR 2.
4. Visual-test BUY dan SELL: hanya setelah candle tutup, entry langsung tanpa pending/high-low breakout, SL di luar candle sinyal, TP sesuai fill aktual, tidak ada entry kedua pada candle yang sama.
5. Periksa Journal dan deal volume; uji slippage/stop-level, restart EA, order ditolak, spread tinggi, margin kurang, serta broker yang tidak mendukung 0,01. Periksa pesan penyesuaian TP, jangan hanya tanda pada chart.
6. Bandingkan net profit setelah biaya, profit factor, equity drawdown, average profit/loss, jumlah transaksi, serta hasil per arah dan bulan. Untuk nominal rata-rata menang/kalah yang sebanding, titik impas teoritis RR 1:1 adalah **50% kemenangan sebelum biaya**; biaya menaikkan ambang yang diperlukan.
7. Validasi di periode lain yang tidak dipakai memilih aturan, kemudian forward-test demo. Mengubah entry dan RR sekaligus menguji kombinasi baru, bukan membuktikan pengaruh salah satunya secara terpisah. Jika perlu, uji market RR 2 juga untuk membedakan efek entry dan RR.

## Verifikasi lokal untuk pengembang

Jalankan `bash tests/run.sh` (memerlukan `g++`). Pengujian memastikan hanya library bawaan MT5 yang di-include, lot default 0,01 tanpa sizing equity/balance, RR default 1, market Buy/Sell dengan SL/TP awal, serta tidak ada lagi pending breakout atau expiry.

Test C++ mengompilasi fungsi matematika produksi langsung dari `.mq5` memakai shim matematika MQL. `MOMENTUM_CORE_TEST` hanya didefinisikan oleh test; jangan mendefinisikannya di MetaEditor. Cakupan: sinyal body/wick, angka invalid, entry Ask/Bid tanpa breakout, SL buffer, target quote/actual fill, rounding tick, jarak stop/freeze dua arah, fixed lots dan min/max/step, serta 10.000 kasus acak deterministik. Test lama untuk level pending diganti karena aturan entry memang berubah. Ini **bukan kompilasi MQL5 atau pengujian terminal/broker**, dan bukan backtest performa.

### Referensi API

- [CTrade::Buy — market order dan pemeriksaan retcode/deal](https://www.mql5.com/en/docs/standardlibrary/tradeclasses/ctrade/ctradebuy)
- [SetTypeFillingBySymbol — filling policy broker](https://www.mql5.com/en/docs/standardlibrary/tradeclasses/ctrade/ctradesettypefillingbysymbol)
- [PositionModify — modifikasi SL/TP menurut ticket](https://www.mql5.com/en/docs/standardlibrary/tradeclasses/ctrade/ctradepositionmodify)
- [OrderCalcProfit — estimasi dalam mata uang akun](https://www.mql5.com/en/docs/trading/ordercalcprofit)
