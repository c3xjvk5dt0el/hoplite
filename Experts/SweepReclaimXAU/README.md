# SweepReclaimXAU — fallback deskriptif yang gagal gate

`SweepReclaimXAU.mq5` adalah EA market-entry terpisah untuk kandidat terkunci `sweep_24_stop1.25_rr1.00`. **Tidak ada kandidat yang lolos gerbang pengembangan** pada studi ini. Karena itu file ini hanya fallback deskriptif: **bukan** strategi ber-win-rate tinggi, bukan terbukti profit, dan belum tervalidasi untuk akun riil. Ini tidak dapat dijadikan cara mendapatkan USD 20 per hari atau USD 100 per minggu.

Pada ringkasan studi kustom, kandidat ini gagal gate pengembangan; validasi dan pemeriksaan historis berikutnya juga negatif. Replay tick Juni–Agustus 2026 menghasilkan 84 transaksi, win rate 48,81%, dan net −USD 40,37 pada biaya dasar; 0 dari 13 minggu lengkap mencapai USD 100. Studi tersebut bukan kompilasi MetaEditor maupun Strategy Tester MT5. Lihat [hasil lengkap](../../research/high_win/RESULTS.md) dan [rencana riset](../../research/high_win/PLAN.md) sebelum melakukan evaluasi independen.

## Batas instalasi dan akun

1. Salin `SweepReclaimXAU.mq5` ke `MQL5/Experts/SweepReclaimXAU/`, lalu kompilasi sendiri di MetaEditor dan periksa pesan compiler.
2. Pasang hanya pada chart **XAUUSD M5**. Suffix broker dapat dipakai bila nama tetap diawali `XAUUSD` dan metadata simbol menunjukkan base `XAU`, profit `USD`.
3. EA menolak akun yang mata uangnya bukan **USD**, serta simbol dengan `SYMBOL_TRADE_CONTRACT_SIZE` selain tepat **100 oz per lot**. Pembatasan ini diperlukan agar estimasi USD dan lot 0,01 sesuai asumsi studi.
4. Default `InpAllowLiveTrading=false` membuat EA **menolak inisialisasi pada akun real**. Demo dan Strategy Tester diizinkan; mode contest/tidak dikenal ditolak. Mengubahnya ke `true` hanyalah opt-in teknis untuk real, bukan bukti keamanan atau profitabilitas.
5. Mulai pada demo dan Strategy Tester **Every tick based on real ticks** dengan spread, komisi, filling mode, dan stop level broker yang relevan. Periksa setiap order, SL/TP, dan Journal.

## Aturan kandidat default terkunci

- Sinyal selalu memakai candle M5 yang sudah tutup (`shift 1`). EA menyalin tepat **25 candle M5 tertutup yang kontigu**: candle sinyal dan 24 candle sebelumnya. Batas low/high hanya dihitung dari 24 candle sebelumnya; candle sinyal tidak ikut menjadi batasnya.
- **Buy:** low candle sinyal `<` low minimum 24 candle sebelumnya, close `>` low tersebut, candle bullish, dan lower wick `>=` body. **Sell** adalah cerminnya: high `>` high maksimum sebelumnya, close di bawahnya, candle bearish, dan upper wick `>=` body.
- Konfirmasi M15 hanya dari bar selesai: buy membutuhkan EMA20 `>` EMA50 dan EMA50 shift 1 `>` shift 4; sell adalah kebalikannya. ATR14 adalah rata-rata sederhana 14 true range M5 yang berakhir pada candle sinyal; setiap true range memakai close candle M5 sebelumnya.
  Evaluasi menunggu minimal 201 bar M15 selesai (202 termasuk bar berjalan), sama dengan warmup model penelitian.
- Harga entry adalah Ask untuk buy dan Bid untuk sell. SL buy dibulatkan turun dari `min(low sinyal − max(0.10 × ATR14, tick), Ask − 1.25 × ATR14)`. SL sell dibulatkan naik dari `max(high sinyal + max(0.10 × ATR14, tick) + spread, Bid + 1.25 × ATR14)`. Harga dibulatkan menjauh dari entry.
- Entry dilewati bila risiko kuotasi `>` `2,5 × ATR14`, `>` 15,00 satuan harga, spread `>` 0,50, atau spread `>` 10% dari risiko kuotasi. Tidak ada clipping risiko.
- TP awal dipasang bersamaan dengan order, pada RR **1:1**, lalu EA mencoba menyelaraskan TP ke harga fill aktual. `InpRewardRisk` sengaja dikunci pada `1.0`; nilai lain membuat inisialisasi gagal. Perubahan TP dapat ditolak oleh stop/freeze level broker; warning ada di Journal dan SL/TP yang telah ada tidak diubah secara paksa.
  Sampai koreksi berhasil, **RR aktual tidak dijamin 1:1**. Journal menandainya `Nonconforming TP alignment`; posisi bisa lebih dahulu exit memakai TP awal. Ini perbedaan eksekusi terhadap model yang mengasumsikan koreksi instan, bukan alasan untuk menghapus proteksi posisi.

## Sesi, posisi, dan batas risiko

- Entry hanya Senin–Jumat, `07:00 <= UTC < 18:00`; maksimum satu percobaan sinyal untuk tiap bar M5 baru dan hanya pada 30 detik pertama. Saat attach/restart, EA menunggu candle berikutnya—tidak mengejar sinyal lama.
- `InpBrokerUtcOffsetMinutes=0` berarti timestamp broker dianggap UTC. Untuk broker yang clock server-nya berbeda, set offset broker terhadap UTC secara manual (misalnya `120` untuk broker UTC+2). Offset tidak diinfer otomatis. **DST historis harus diubah manual** saat backtest/replay melewati pergantian DST; offset yang salah mengubah sesi dan hari anggaran.
- Maksimum 12 **order pembuka** per hari UTC. Partial fill dari order pembuka yang sama dihitung sekali melalui `DEAL_ORDER`.
- Sebelum entry, EA membaca history hingga timestamp broker saat ini (bukan akhir hari masa depan), hanya untuk simbol dan magic EA, lalu menjumlahkan `DEAL_PROFIT + DEAL_SWAP + DEAL_COMMISSION + DEAL_FEE`. Bila history tidak tersedia atau tidak lengkap, entry diblokir.
- Estimasi kerugian stop memakai `OrderCalcProfit`, adverse slippage 0,05 pada entry dan 0,05 pada exit SL, lalu komisi round-trip estimasi USD 0,04. Entry ditolak bila net hari ini dikurangi estimasi tersebut menjadi kurang dari USD -25. Ini **bukan** batas rugi yang dijamin: gap, slippage, swap, komisi aktual, dan eksekusi broker dapat melampauinya. Tidak ada daily-profit stop.
  Angka slippage/komisi tersebut hanya estimasi untuk gate, bukan pengaturan biaya broker. Budget dihitung untuk EA+simbol ini terhadap awal hari, bukan batas drawdown dari puncak profit harian atau kerugian semua strategi di akun.
- Lot tetap dikunci pada `InpFixedLots=0.01` dan tidak memakai equity sizing. Nilai lain atau lot yang tidak cocok persis dengan minimum/maksimum/step broker membuat EA menolak berjalan, bukan membulatkan lot. Bila ada posisi atau order apa pun pada simbol, EA tidak membuka posisi lain. EA hanya mengelola posisi miliknya yang cocok dengan simbol, `InpMagic=26091330` (default), dan komentar `SweepReclaimXAU`. Ada reserve free margin 10%.
  Pemeriksaan eksposur bukan lock atomik lintas-EA: gunakan satu instance saja per simbol/akun.
  Magic harus positif dan tidak melebihi `LONG_MAX` MT5; ID history yang invalid diblokir, bukan diubah menjadi ID unsigned.
- Tidak ada martingale, grid, averaging, trailing/breakeven, atau pending order. Timeout default `InpMaxHoldMinutes=45` mencoba close pada tick pertama yang tersedia setelah batas waktu; SL/TP server tetap aktif bila close gagal atau tidak ada tick.

Permintaan timeout close yang hasilnya belum pasti tidak dikirim ulang otomatis. EA menunggu status order final dan merekonsiliasi volume deal close dengan volume posisi tersisa; jangan restart EA untuk memaksa retry ketika hasil broker belum jelas.

Konfigurasi kandidat untuk lot dan RR dikunci pada 0,01 dan 1:1. Input sesi serta batas waktu ada untuk kebutuhan operasional/backtest, tetapi nilai selain defaultnya **tidak diteliti** dan tidak boleh disebut sebagai kandidat tervalidasi. `InpBrokerUtcOffsetMinutes` perlu disesuaikan dengan clock broker untuk merepresentasikan aturan UTC yang sama.

## Batas verifikasi repository

`tests/sweep_reclaim_test.cpp` mengompilasi helper matematika produksi dengan C++ lokal dan memeriksa batas sweep, aturan candle, SL/floor/cap, Bid/Ask, RR, sesi UTC, anggaran, timeout, lot, dan guard real-account. Tes itu **bukan** kompilasi MetaEditor dan bukan backtest MT5. MetaEditor tidak tersedia dalam lingkungan repository ini; belum ada klaim bahwa file ini telah dikompilasi secara native di MT5.
