# Momentum Candle XAU — Expert Advisor MT5

EA untuk **XAUUSD M5 atau M15**, berdasarkan indikator Pine Script “Momentum Candle Sekolah Trading”. Ini adalah **rancangan awal untuk diuji di demo**, bukan strategi yang sudah terbukti menguntungkan. Tidak ada martingale, grid, averaging, atau penambahan posisi saat rugi.

**Versi 1.02: lot tetap 0,01** (`InpFixedLots`), bukan persen balance/equity. Nilai hanya berubah jika input lot diubah manual. Aturan sinyal, entry, SL, TP dan expiry tetap sama; perubahan lot bukan perbaikan win rate.

## File dan pemasangan

1. Di MT5 pilih **File → Open Data Folder**.
2. Unduh **satu file saja**, [`MomentumCandleXAU.mq5`](Experts/MomentumCandleXAU/MomentumCandleXAU.mq5), melalui tombol **Download raw file** di GitHub. Simpan di `MQL5/Experts/` atau subfolder `MomentumCandleXAU/`. Jangan menyimpan halaman HTML GitHub sebagai `.mq5`.
3. Buka file tersebut di **MetaEditor milik MetaTrader 5**, bukan MT4 atau Pine Editor, lalu tekan **F7**. Versi 1.02 tetap memuat semua fungsi strategi dalam satu file; file pendukung versi lama tidak diperlukan. `Trade\Trade.mqh` adalah library standar bawaan MT5, bukan file tambahan yang perlu diunduh dari proyek ini. Saat mengganti versi, reset Inputs dan pastikan `InpFixedLots = 0.01`; parameter persen risiko versi lama sudah dihapus. Pending/posisi yang sudah ada tidak diubah ukurannya oleh upgrade: tunggu selesai atau batalkan pending lama sebelum menguji versi baru.
4. Jalankan dahulu di **Strategy Tester/demo**, bukan akun live. Aktifkan Algo Trading jika digunakan pada chart demo.
5. Pasang hanya **satu instance EA per simbol per akun**: pilih M5 **atau** M15. EA menolak order baru jika sudah ada posisi/order pada simbol tersebut, termasuk transaksi manual/EA lain. Pemeriksaan ini bukan kunci atomik antar-EA; jangan jalankan dua instance bersamaan.

EA menerima simbol dengan awalan `XAUUSD` seperti `XAUUSDm`, atau simbol yang melaporkan base currency `XAU` dan profit currency `USD`. Nama `GOLD` bisa bekerja jika metadata broker sesuai. EA menolak TF selain M5/M15 dan mensyaratkan chart Bid, pending stop, SL/TP, serta kedaluwarsa order bertipe `ORDER_TIME_SPECIFIED` di server broker. Tidak ada fallback ke pending tanpa batas waktu.

Jika masih gagal compile, kirim **5 pesan error pertama beserta nomor baris** dari tab Errors MetaEditor, serta versi/build MT5. Banyak error dapat merupakan efek berantai dari satu kesalahan awal; penyebab pastinya tidak dapat ditetapkan tanpa pesan tersebut. Bila yang tidak ditemukan adalah `Trade\Trade.mqh`, periksa instalasi/library standar MT5.

## Rekomendasi aturan awal

**Mulai evaluasi dari M15**, lalu bandingkan M5 dengan periode dan biaya yang sama. M15 merupakan titik awal untuk mengurangi frekuensi sinyal, bukan klaim bahwa hasilnya lebih baik.

| Komponen | Aturan default |
|---|---|
| Candle sinyal | Hanya candle yang sudah tutup, bukan candle berjalan |
| Minimum body | M5: 35 pip; M15: 45 pip |
| Definisi pip emas | 1 pip = 0,10 perubahan harga; body minimum 3,50 / 4,50 |
| Wick | Jumlah wick atas+bawah maksimal 30% high−low |
| Mode wick | Agresif; pilihan konservatif mengikuti persis arah wick Pine asli |
| Trend | Close candle sinyal di atas EMA H1 50 untuk buy; di bawah untuk sell |
| EMA | Nilai candle H1 terakhir yang **sudah tutup**, bukan H1 berjalan |
| Filter lonjakan | Lewati candle dengan high−low > 2,5 × ATR(14) TF chart |
| Buy Stop | High sinyal + 0,10 × ATR + spread saat pemasangan |
| Sell Stop | Low sinyal − 0,10 × ATR |
| SL buy | Low sinyal − 0,15 × ATR |
| SL sell | High sinyal + 0,15 × ATR + spread saat pemasangan |
| TP | 2 × jarak entry–SL dari harga entry yang direncanakan |
| Batas umur pending | 3 periode candle setelah candle sinyal selesai; M5: 15 menit, M15: 45 menit |
| Lot | Tetap **0,01 lot** per order (`InpFixedLots`), tanpa sizing dari modal |
| Validasi volume | Harus sesuai minimum, maksimum dan step broker; tidak dinaikkan/diturunkan otomatis |
| Batas spread | 0,50 dalam satuan harga XAUUSD, **bukan 0,50 point** |

Semua angka di atas merupakan parameter awal, belum hasil optimasi/backtest. ATR menggunakan candle sinyal yang sudah tutup. Buffer minimum adalah satu tick; harga dibulatkan keluar sesuai tick size broker. Karena chart menggunakan Bid tetapi buy dipicu Ask dan SL sell dipicu Ask, spread ditambahkan pada entry buy dan SL sell. Spread bisa berubah setelah order ditempatkan.

Entry terlambat tidak dikejar menggunakan market order. Jika pada saat evaluasi harga sudah melewati entry, jarak minimal broker tidak terpenuhi, data tidak siap dalam 30 detik pertama candle baru, spread terlalu besar, volume tidak valid, atau margin tidak cukup, sinyal dilewati. EA menunggu candle berikutnya setelah baru dipasang/restart; sinyal sebelum jeda sesi juga dilewati.

Konsolidasi opsional: body dari masing-masing N candle sebelumnya harus **lebih kecil** dari body sinyal, bukan filter sideways/range. Default nonaktif. Mode wick konservatif mempertahankan logika Pine: bullish `lowerWick < upperWick`, bearish kebalikannya; ini **bukan** pola rejection-wick yang biasanya memiliki ekor panjang di arah berlawanan.

### Contoh entry, SL, dan TP — bukan harga rekomendasi saat ini

Misalkan candle bullish memiliki open **3000**, close **3005,50**, high **3006**, low **2999**, ATR **5**, spread **0,30**, tick size **0,01**, dan lolos filter EMA:

- Buy Stop = 3006 + 0,50 + 0,30 = **3006,80**.
- SL = 2999 − 0,75 = **2998,25**.
- Jarak risiko = **8,55**; TP = 3006,80 + 2 × 8,55 = **3023,90**.
- Jika contract size broker 100 oz/lot, 0,01 lot berisiko sekitar **USD 8,55**, sebelum komisi/slippage.
- Pada equity USD 1.000 maupun USD 10.000, volume tetap **0,01 lot** dan estimasi kerugian contoh ini tetap USD 8,55, jika margin mencukupi. Persentase risiko terhadap modal berbeda: sekitar 0,855% versus 0,0855%. Jarak SL berbeda akan menghasilkan nominal risiko berbeda meski lot tetap.

TP/SL tetap; tidak ada breakeven, trailing stop, atau close saat sinyal berlawanan. Sinyal baru diabaikan selama ada exposure. Tidak ada batas durasi posisi setelah terisi; swap dapat berlaku.

## Risiko dan batas operasional

- `OrderCalcProfit` hanya mengestimasi kerugian ke SL untuk Journal dalam **mata uang akun**, bukan menentukan volume. Estimasi belum memasukkan komisi, swap, atau slippage. Parameter persen risiko, maksimum lot untuk sizing, dan cadangan biaya per lot versi lama sudah dihapus.
- **Tidak ada batas kerugian berupa persen modal.** Lot 0,01 bukan berarti selalu aman untuk modal berapa pun. Gap, slippage, swap dan biaya dapat menaikkan kerugian aktual. RR 1:2 adalah rasio harga rencana, bukan rasio hasil bersih yang dijamin.
- EA tetap mensyaratkan estimasi margin order tidak melebihi 90% free margin. Modal/leverage dan ketentuan broker tetap berpengaruh pada kemampuan entry dan stop-out. Jika lot input tidak sesuai min/max/step broker, EA gagal inisialisasi dengan pesan jelas, bukan menaikkan lot agar diterima. Volume diperiksa kembali sebelum setiap order.
- Batas spread diperiksa saat **pemasangan** order, bukan jaminan spread saat terpicu. EA tidak memiliki filter berita, batas rugi harian, ataupun filter jam trading.
- Hindari menguji live di sekitar NFP, CPI, FOMC dan rollover tanpa evaluasi khusus. Menonaktifkan Algo Trading/melepas EA **tidak membatalkan pending order dan tidak menutup posisi**. Batalkan pending secara manual jika tidak ingin terpicu saat berita.
- Pending memiliki expiry server, dan SL/TP dikirim bersama order. Keduanya tetap mengikuti aturan eksekusi broker ketika terminal offline. Pending yang sudah terisi tidak lagi tunduk pada expiry.
- Bila order ditolak/hasilnya tidak terkonfirmasi, EA mencatat retcode dan **tidak otomatis mengirim ulang** untuk menghindari duplikasi. Lihat tab Experts/Journal jika tidak ada transaksi.
- Tidak ada retry untuk sinyal yang gagal pemeriksaan spread/margin/trading permission. Hanya kegagalan kesiapan data yang dicoba ulang dalam jendela awal candle.

## Backtest yang perlu dilakukan di MT5

**Belum ada backtest MT5 yang dijalankan atau laporan performa yang diverifikasi dalam workspace ini; file `.ex5` juga belum dikompilasi di sini.** Workspace Linux tempat kode dibuat tidak menyediakan MT5/MetaEditor maupun data tick broker. Uji logika di bawah bukan backtest dan tidak memverifikasi API/perilaku terminal MQL5.

1. Compile di MetaEditor; periksa dan selesaikan seluruh error/warning sebelum pengujian.
2. Buka Strategy Tester (`Ctrl+R`), pilih EA, simbol XAUUSD **broker yang akan dipakai**, lalu M15. Ulangi terpisah di M5.
3. Pilih **Every tick based on real ticks**. Jangan memakai Open prices only untuk strategi pending breakout; urutan tick menentukan apakah entry, SL, atau TP tersentuh lebih dulu.
4. Gunakan minimal 12–24 bulan data yang tersedia, mencakup berbagai kondisi volatilitas; misalnya 2024–2025 untuk pengembangan dan 2026-01-01 sampai 2026-08-31 sebagai out-of-sample. Jangan optimasi ulang pada periode out-of-sample lalu tetap menyebutnya pengujian independen.
5. Samakan deposit, mata uang akun, leverage, spesifikasi kontrak, serta batas volume dengan rencana akun. Pastikan spread, komisi dan swap benar-benar tercermin dalam hasil tester. Reset input ke versi baru dengan `InpFixedLots = 0.01`.
6. Lakukan visual test sejumlah transaksi: candle sinyal tutup dulu; EMA berasal dari H1 selesai; entry/SL/TP sesuai Journal; pending habis setelah 3 periode; setiap order memakai 0,01 lot. Bandingkan dua deposit dengan margin mencukupi: volume tidak boleh berubah. Broker minimum 0,1 atau step yang tidak menerima 0,01 harus ditolak, bukan dibulatkan naik.
7. Bandingkan net profit setelah biaya, equity drawdown maksimal, jumlah trade, profit factor, expected payoff, rangkaian loss, serta konsistensi per bulan dan antara in-sample/out-of-sample. Jangan memilih hanya dari win rate. RR 2 memiliki break-even teoritis 33,3% **sebelum** biaya dan perubahan fill, bukan target win rate EA.
8. Uji sensitivitas biaya/delay dan parameter di sekitar default. Hindari memilih satu kombinasi sempit yang terlihat bagus di histori. Bila data memungkinkan, cari ratusan transaksi; sampel sedikit membatasi kesimpulan.
9. Forward-test demo beberapa minggu atau lebih sampai sampel memadai. Keputusan live perlu mempertimbangkan kemampuan menanggung kerugian, bukan hanya satu laporan backtest yang bagus.

Jika ingin hasil dianalisis lebih lanjut, kirim laporan HTML tester, input `.set`, nama broker/simbol, rentang tanggal, kualitas data, deposit/leverage, dan informasi komisi. Jangan kirim kredensial akun.

### Jika win rate hanya 27%

Win rate tidak cukup untuk menentukan hasil tanpa rata-rata profit/loss dan biaya. Jika rata-rata menang tepat 2R dan rata-rata kalah 1R, hasil harapan adalah `0,27 × 2R − 0,73 × 1R = −0,19R` per transaksi sebelum biaya. Dengan asumsi itu, break-even memerlukan win rate di atas 33,3% sebelum biaya. R adalah satu unit risiko, bukan persen modal.

Lot tetap mengubah nominal profit/loss dan transaksi yang sebelumnya ditolak karena sizing, tetapi tidak memperbaiki kualitas sinyal. Hasil aktual perlu diperiksa melalui laporan: jumlah trade, rata-rata profit/loss, spread/komisi, drawdown, timeframe dan periode. Jangan menganggap menaikkan TP otomatis memperbaiki hasil; itu juga bisa menurunkan win rate. Belum ada analisis laporan atau backtest baru yang memverifikasi penyebab angka 27%.

## Verifikasi lokal untuk pengembang

Jalankan `bash tests/run.sh` (memerlukan `g++`). Test memeriksa bahwa EA tidak menggunakan custom include, input lot default 0,01, dan tidak ada lagi sizing equity/balance. Test mengompilasi **fungsi matematika produksi langsung dari `MomentumCandleXAU.mq5`** sebagai C++ dengan shim fungsi matematika MQL; tidak menggandakan implementasi strategi. Macro `MOMENTUM_CORE_TEST` hanya didefinisikan oleh test C++ untuk mengecualikan API terminal; jangan mendefinisikannya saat compile di MetaEditor. Cakupan: batas body/wick, arah wick konservatif, candle invalid/doji, harga Bid/Ask, rounding tick, lot tetap, penolakan volume di luar min/max/step tanpa pembulatan otomatis, dan 10.000 kasus acak deterministik untuk invariant harga serta volume. Uji risiko-persentase lama diganti karena perilaku yang diminta sekarang adalah lot tetap. EA yang memakai API terminal tetap harus dikompilasi dan diuji di MT5.

### Referensi implementasi

- [MQL5 CTrade::BuyStop — parameter expiry dan pemeriksaan retcode](https://www.mql5.com/en/docs/standardlibrary/tradeclasses/ctrade/ctradebuystop)
- [MQL5 OrderCalcProfit — estimasi dalam mata uang akun](https://www.mql5.com/en/docs/trading/ordercalcprofit)
- [MQL5 properti simbol — tick size, volume, stop level, expiration](https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants)
