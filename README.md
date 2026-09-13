# Momentum Candle XAU — Expert Advisor MT5

EA untuk **XAUUSD M5 atau M15**, berdasarkan indikator Pine Script “Momentum Candle Sekolah Trading”. Ini adalah **rancangan awal untuk diuji di demo**, bukan strategi yang sudah terbukti menguntungkan. Tidak ada martingale, grid, averaging, atau penambahan posisi saat rugi.

## File dan pemasangan

1. Di MT5 pilih **File → Open Data Folder**.
2. Buat folder `MQL5/Experts/MomentumCandleXAU/`, lalu salin **kedua file** berikut ke sana:
   - [`MomentumCandleXAU.mq5`](Experts/MomentumCandleXAU/MomentumCandleXAU.mq5)
   - [`MomentumCore.mqh`](Experts/MomentumCandleXAU/MomentumCore.mqh)
3. Buka `.mq5` di MetaEditor lalu tekan **F7**. File `.mqh` harus tetap di folder yang sama.
4. Jalankan dahulu di **Strategy Tester/demo**, bukan akun live. Aktifkan Algo Trading jika digunakan pada chart demo.
5. Pasang hanya **satu instance EA per simbol per akun**: pilih M5 **atau** M15. EA menolak order baru jika sudah ada posisi/order pada simbol tersebut, termasuk transaksi manual/EA lain. Pemeriksaan ini bukan kunci atomik antar-EA; jangan jalankan dua instance bersamaan.

EA menerima simbol dengan awalan `XAUUSD` seperti `XAUUSDm`, atau simbol yang melaporkan base currency `XAU` dan profit currency `USD`. Nama `GOLD` bisa bekerja jika metadata broker sesuai. EA menolak TF selain M5/M15 dan mensyaratkan chart Bid, pending stop, SL/TP, serta kedaluwarsa order bertipe `ORDER_TIME_SPECIFIED` di server broker. Tidak ada fallback ke pending tanpa batas waktu.

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
| Risiko | Target maksimum estimasi 0,5% equity/order; lot dibulatkan **turun** |
| Maksimum lot | 1,0 lot, tetap dibatasi hasil perhitungan risiko |
| Batas spread | 0,50 dalam satuan harga XAUUSD, **bukan 0,50 point** |

Semua angka di atas merupakan parameter awal, belum hasil optimasi/backtest. ATR menggunakan candle sinyal yang sudah tutup. Buffer minimum adalah satu tick; harga dibulatkan keluar sesuai tick size broker. Karena chart menggunakan Bid tetapi buy dipicu Ask dan SL sell dipicu Ask, spread ditambahkan pada entry buy dan SL sell. Spread bisa berubah setelah order ditempatkan.

Entry terlambat tidak dikejar menggunakan market order. Jika pada saat evaluasi harga sudah melewati entry, jarak minimal broker tidak terpenuhi, data tidak siap dalam 30 detik pertama candle baru, spread terlalu besar, atau minimum lot melampaui anggaran risiko, sinyal dilewati. EA menunggu candle berikutnya setelah baru dipasang/restart; sinyal sebelum jeda sesi juga dilewati.

Konsolidasi opsional: body dari masing-masing N candle sebelumnya harus **lebih kecil** dari body sinyal, bukan filter sideways/range. Default nonaktif. Mode wick konservatif mempertahankan logika Pine: bullish `lowerWick < upperWick`, bearish kebalikannya; ini **bukan** pola rejection-wick yang biasanya memiliki ekor panjang di arah berlawanan.

### Contoh entry, SL, dan TP — bukan harga rekomendasi saat ini

Misalkan candle bullish memiliki open **3000**, close **3005,50**, high **3006**, low **2999**, ATR **5**, spread **0,30**, tick size **0,01**, dan lolos filter EMA:

- Buy Stop = 3006 + 0,50 + 0,30 = **3006,80**.
- SL = 2999 − 0,75 = **2998,25**.
- Jarak risiko = **8,55**; TP = 3006,80 + 2 × 8,55 = **3023,90**.
- Jika contract size broker 100 oz/lot, 0,01 lot berisiko sekitar **USD 8,55**, sebelum komisi/slippage.
- Pada equity USD 1.000, target 0,5% hanya USD 5. Jika minimum broker 0,01 lot, EA **tidak entry**; jangan menaikkan risiko hanya untuk memaksa transaksi.

TP/SL tetap; tidak ada breakeven, trailing stop, atau close saat sinyal berlawanan. Sinyal baru diabaikan selama ada exposure. Tidak ada batas durasi posisi setelah terisi; swap dapat berlaku.

## Risiko dan batas operasional

- Perhitungan menggunakan `OrderCalcProfit` dalam **mata uang akun**, bukan asumsi tick value/contract size yang sama pada semua broker. `InpRoundTripCostPerLot` dapat diisi estimasi komisi + biaya tambahan pulang-pergi per 1 lot dalam mata uang akun. Default 0 berarti biaya tambahan belum dicadangkan.
- **0,5% bukan jaminan kerugian maksimum.** Gap, slippage saat pending terisi/SL dieksekusi, swap, konversi mata uang, dan biaya yang lebih besar dari estimasi dapat menaikkan kerugian aktual. RR 1:2 adalah rasio harga rencana, bukan rasio hasil bersih yang dijamin.
- Batas spread diperiksa saat **pemasangan** order, bukan jaminan spread saat terpicu. EA tidak memiliki filter berita, batas rugi harian, ataupun filter jam trading.
- Hindari menguji live di sekitar NFP, CPI, FOMC dan rollover tanpa evaluasi khusus. Menonaktifkan Algo Trading/melepas EA **tidak membatalkan pending order dan tidak menutup posisi**. Batalkan pending secara manual jika tidak ingin terpicu saat berita.
- Pending memiliki expiry server, dan SL/TP dikirim bersama order. Keduanya tetap mengikuti aturan eksekusi broker ketika terminal offline. Pending yang sudah terisi tidak lagi tunduk pada expiry.
- Bila order ditolak/hasilnya tidak terkonfirmasi, EA mencatat retcode dan **tidak otomatis mengirim ulang** untuk menghindari duplikasi. Lihat tab Experts/Journal jika tidak ada transaksi.
- Tidak ada retry untuk sinyal yang gagal pemeriksaan spread/margin/trading permission. Hanya kegagalan kesiapan data yang dicoba ulang dalam jendela awal candle.

## Backtest yang perlu dilakukan di MT5

**Belum ada hasil backtest, win rate, profit factor, drawdown, atau file `.ex5` terkompilasi.** Workspace Linux tempat kode dibuat tidak menyediakan MT5/MetaEditor maupun data tick broker. Uji logika di bawah bukan backtest dan tidak memverifikasi API/perilaku terminal MQL5.

1. Compile di MetaEditor; periksa dan selesaikan seluruh error/warning sebelum pengujian.
2. Buka Strategy Tester (`Ctrl+R`), pilih EA, simbol XAUUSD **broker yang akan dipakai**, lalu M15. Ulangi terpisah di M5.
3. Pilih **Every tick based on real ticks**. Jangan memakai Open prices only untuk strategi pending breakout; urutan tick menentukan apakah entry, SL, atau TP tersentuh lebih dulu.
4. Gunakan minimal 12–24 bulan data yang tersedia, mencakup berbagai kondisi volatilitas; misalnya 2024–2025 untuk pengembangan dan 2026-01-01 sampai 2026-08-31 sebagai out-of-sample. Jangan optimasi ulang pada periode out-of-sample lalu tetap menyebutnya pengujian independen.
5. Samakan deposit, mata uang akun, leverage, spesifikasi kontrak, serta batas volume dengan rencana akun. Pastikan spread, komisi dan swap benar-benar tercermin dalam hasil tester. `InpRoundTripCostPerLot` hanya cadangan dalam sizing, **bukan** pengaturan biaya pada tester.
6. Lakukan visual test sejumlah transaksi: candle sinyal tutup dulu; EMA berasal dari H1 selesai; entry/SL/TP sesuai Journal; pending habis setelah 3 periode; minimum lot terlalu besar menghasilkan skip.
7. Bandingkan net profit setelah biaya, equity drawdown maksimal, jumlah trade, profit factor, expected payoff, rangkaian loss, serta konsistensi per bulan dan antara in-sample/out-of-sample. Jangan memilih hanya dari win rate. RR 2 memiliki break-even teoritis 33,3% **sebelum** biaya dan perubahan fill, bukan target win rate EA.
8. Uji sensitivitas biaya/delay dan parameter di sekitar default. Hindari memilih satu kombinasi sempit yang terlihat bagus di histori. Bila data memungkinkan, cari ratusan transaksi; sampel sedikit membatasi kesimpulan.
9. Forward-test demo beberapa minggu atau lebih sampai sampel memadai. Keputusan live perlu mempertimbangkan kemampuan menanggung kerugian, bukan hanya satu laporan backtest yang bagus.

Jika ingin hasil dianalisis lebih lanjut, kirim laporan HTML tester, input `.set`, nama broker/simbol, rentang tanggal, kualitas data, deposit/leverage, dan informasi komisi. Jangan kirim kredensial akun.

## Verifikasi lokal untuk pengembang

Jalankan `bash tests/run.sh` (memerlukan `g++`). Test mengompilasi **fungsi matematika produksi dalam `MomentumCore.mqh`** sebagai C++ dengan shim fungsi matematika MQL; tidak menggandakan implementasi strategi. Cakupan: batas body/wick, arah wick konservatif, candle invalid/doji, harga Bid/Ask, rounding tick/lot, batas risiko/minimum lot, cadangan komisi, dan 10.000 kasus acak deterministik untuk invariant harga serta risiko. EA yang memakai API terminal tetap harus dikompilasi dan diuji di MT5.

### Referensi implementasi

- [MQL5 CTrade::BuyStop — parameter expiry dan pemeriksaan retcode](https://www.mql5.com/en/docs/standardlibrary/tradeclasses/ctrade/ctradebuystop)
- [MQL5 OrderCalcProfit — estimasi dalam mata uang akun](https://www.mql5.com/en/docs/trading/ordercalcprofit)
- [MQL5 properti simbol — tick size, volume, stop level, expiration](https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants)
