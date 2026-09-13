# TrendPullbackXAU

EA kandidat **market entry** untuk `XAUUSD` pada chart **M5**. Ini bukan janji win rate 80% dan harus diuji pada data tick broker, spread, komisi, serta periode out-of-sample sebelum dipakai pada akun riil.

## Instalasi

1. Salin `TrendPullbackXAU.mq5` ke `MQL5/Experts/TrendPullbackXAU/` lalu kompilasi di MetaEditor.
2. Pasang hanya pada chart XAUUSD M5 (suffix broker didukung, misalnya `XAUUSDm`).
3. Reset Inputs, pastikan `InpFixedLots=0.01`, `InpRewardRisk=1.5` dan `InpMaxHoldMinutes=60`. Preset lama tidak otomatis berubah mengikuti default source. Aktifkan Algo Trading pada demo; EA menolak lot yang tidak persis kompatibel dengan minimum/step broker.
4. Mulai dari demo/Strategy Tester dengan **Every tick based on real ticks**, menggunakan kondisi akun dan spread broker yang relevan.

## Aturan default yang dibekukan

- Sinyal hanya dari candle M5 yang sudah tutup (`shift 1`):
  - **Buy:** low menyentuh/di bawah EMA20, close di atas EMA20, dan close > open.
  - **Sell:** high menyentuh/di atas EMA20, close di bawah EMA20, dan close < open.
- Konfirmasi tren memakai M15 **yang sudah selesai**: EMA20 > EMA50 dan EMA50 shift 1 > EMA50 shift 4 untuk buy; kebalikannya untuk sell.
- Stop memakai tiga candle M5 tertutup yang kontigu, termasuk candle sinyal:
  - buy = low terendah − `0.10 × ATR14`;
  - sell = high tertinggi + `0.10 × ATR14` + spread saat kuotasi.
  Buffer minimal satu tick; harga stop dibulatkan ke luar. TP awal terpasang bersama order, lalu EA mencoba menyelaraskannya ke RR `1.5` dari harga fill aktual. Stop/freeze level atau perubahan harga bisa menolak koreksi tersebut; periksa Journal.
- Entry ditolak bila spread lebih dari `0.50` satuan harga **atau** lebih dari 10% jarak entry-ke-SL. Tidak ada filter sesi/news, martingale, atau pending order.
- Bila ada posisi atau pending order apa pun pada simbol yang sama, EA tidak membuka posisi baru.
- Setelah dipasang/restart, EA menunggu close berikutnya. Data sinyal hanya dicoba selama 30 detik pertama candle baru; sinyal yang terlambat dilewati.

## Exit 60 menit

`InpMaxHoldMinutes=60` mencoba menutup hanya posisi dengan simbol, magic, dan komentar `TrendPullbackXAU` milik EA pada tick pertama yang tersedia saat/setelah **60 menit** dari waktu open. Input `0` menonaktifkan batas waktu ini. Tidak ada jaminan exit tepat saat 60 menit ketika pasar/tick tidak tersedia, trading dinonaktifkan, terminal terputus, atau broker menolak permintaan. SL/TP tetap terpasang di server; timeout dan koreksi TP memerlukan EA aktif. Jika broker mengubah komentar posisi, pengelolaan otomatis posisi tersebut tidak berjalan.

Gunakan satu instance per simbol/akun. Pemeriksaan exposure bukan penguncian atomik lintas-EA, dan transaksi manual pada akun netting dapat bercampur dengan posisi EA. Jangan memakai simbol yang sama untuk beberapa strategi sekaligus. Lot tetap 0,01 **bukan** batas risiko dolar atau persentase modal; SL yang lebih lebar berisiko lebih besar.

Close yang masih diproses tidak dikirim ulang. Setelah hasil order tercatat final, sisa posisi diperiksa sebelum percobaan close berikutnya. Timeout dengan hasil tidak pasti/tanpa ID order memblokir pengiriman ulang otomatis selama EA aktif; periksa posisi dan Journal sebelum melakukan tindakan manual/restart. Status internal permintaan yang belum teridentifikasi tidak bertahan setelah EA dilepas, jadi jangan restart untuk memaksa retry saat hasil broker belum jelas.

## Batas validasi MT5

Tes C++ lokal memeriksa rumus sinyal, swing stop, kuotasi Bid/Ask, TP, spread, lot, dan batas waktu. Tes tersebut **bukan** kompilasi MetaEditor atau backtest MT5. Kompilasi, izin trading, mode filling broker, stop/freeze level, dan hasil Strategy Tester tetap perlu divalidasi di terminal MT5 Anda.

[Hasil penelitian historis](../../research/RESULTS.md) menunjukkan kandidat mendekati impas sebelum swap dan merugi pada skenario slippage lebih buruk. **Jangan gunakan di akun riil.**
