# Penelitian kandidat win rate tinggi — lot tetap 0,01

**Tujuan penelitian, bukan janji pendapatan:** mencari kandidat XAUUSD M5 yang tahan biaya, lalu mengukur target USD 20/hari dan USD 100/minggu. Lihat [hasil dan keputusan](RESULTS.md), [semua 36 skor kandidat](candidate_scores.csv), serta [protokol](PLAN.md).

EA lama tidak diganti. Implementasi pembanding terpisah tersedia di [SweepReclaimXAU](../../Experts/SweepReclaimXAU/README.md); ini bukan strategi yang sudah lolos untuk uang riil.

## Apa yang dibandingkan?

Tiga keluarga aturan: pemulihan RSI2 searah tren, Bollinger re-entry saat ranging, dan sweep/reclaim searah tren. Setiap keluarga memakai dua kondisi entry, dua minimum jarak SL, dan tiga rasio TP/SL: total **36 konfigurasi**, bukan 36 pengujian statistik independen. Rumus lengkap dan aturan pemilihan sudah ditetapkan di PLAN sebelum hasil pertama dilihat.

Semua menggunakan lot tetap 0,01, kontrak asumsi 100 oz/lot, akun USD, satu posisi, maksimal 12 entry sehari, SL maksimal 15,00 unit harga dan 2,5 ATR, sesi Senin–Jumat 07:00–18:00 UTC, serta timeout 45 menit. Budget entry USD 25/hari memeriksa kerugian calon SL setelah hasil hari itu, bukan mengubah lot. **Budget ini tidak menjamin kerugian harian berhenti tepat di USD 25 saat gap/slippage.** Tidak ada martingale, grid, averaging, atau membiarkan kerugian terbuka di luar laporan.

0,01 lot pada kontrak tersebut setara 1 oz: pergerakan bersih harga emas USD 1 menghasilkan sekitar USD 1 sebelum biaya. Maka target USD 20 membutuhkan akumulasi pergerakan yang benar-benar berhasil ditangkap sebesar sekitar USD 20 setelah biaya, bukan sekadar pasar bergerak USD 20.

## Pemisahan periode

- **2025:** pengembangan/seleksi atas 36 kandidat, dengan Desember 2024 untuk warmup.
- **Januari–Mei 2026:** hanya kandidat yang dipilih aturan pengembangan; mengunci satu identitas sebelum fase berikutnya.
- **Juni–Agustus 2026:** pemeriksaan historis atas identitas yang sudah terkunci, tanpa mengganti kandidat sesudah melihat hasil.
- **Replay tick Juni–Agustus 2026:** identitas dan rentang final harus cocok dengan lock dan fingerprint model. Bukan pencarian kandidat kedua.

Jika tidak ada yang memenuhi ambang pengembangan, kandidat fallback hanya pembanding deskriptif. Skor tertinggi di antara kandidat gagal **tidak** berarti kandidat tersebut menguntungkan atau memiliki win rate tinggi.

Semua periode ini sudah pernah diperiksa untuk EA pullback berbeda dalam penelitian sebelumnya. Ini **data historis yang digunakan kembali**, bukan data out-of-sample murni atau bukti performa masa depan. Tidak ada tuning ulang setelah hasil final, mengganti BUY/SELL berdasarkan periode menang, atau membuang bulan merugi.

## Data dan eksekusi

Sumber: 21 arsip tick publik Exness XAUUSD, Desember 2024–Agustus 2026, dengan total 147.524.553 tick dan 616.216 candle M1 Bid/Ask. Data bersifat **indikatif**, tidak dapat dipilih berdasarkan server akun, dan tidak dijamin identik dengan Exness-MT5Trial7. `verified` berarti validasi struktur/CRC/schema/quote/urutan waktu, bukan bukti independen bahwa penyedia tidak kehilangan tick/sesi.

Studi memverifikasi hash metadata, CSV dan ZIP, jumlah M1 dan kepemilikan timestamp tiap bulan; periode yang kehilangan file bulanan ditolak, tidak dianggap nol profit. Namun integritas file tidak membuktikan kelengkapan feed upstream. Data mentah tidak dimasukkan ke Git.

- **Proxy M1:** indikator dari Bid M5/M15 yang sudah selesai. Entry long pada Ask, short pada Bid. Exit long menggunakan Bid, short menggunakan Ask. SL diprioritaskan ketika satu menit menyentuh SL dan TP.
- **Replay tick:** menggunakan urutan quote asli dalam ZIP, termasuk urutan beberapa tick dalam detik yang sama; tidak memakai aturan SL-first OHLC. SL diisi pada quote pemicu yang sebenarnya ditambah slippage, TP pada target tanpa perbaikan harga saat gap.
- **Clock:** mengikuti `TimeCurrent()`/`POSITION_TIME` MT5 yang berupa detik utuh. Batas entry `now - bar_open <= 30` inklusif pada detik utuh; bukan klaim presisi milidetik. CSV transaksi juga beresolusi detik. Urutan tick asli tetap dipertahankan, tidak digabung per detik. Proxy M1 tidak mengetahui detik tick pertama, sedangkan replay menerapkan guard tersebut.
- **Biaya:** USD 0,04 round-trip; slippage merugikan 0,05 unit harga per entry/exit market atau SL, dan stres 0,15. Spread dari pasangan quote sumber, bukan spread nol.
- **Tetap disederhanakan:** fill/koreksi TP instan; tanpa latency, partial fill, rejection, stop/freeze broker, margin/stop-out, atau swap. Count posisi melewati tanggal UTC/timeout tersedia. Posisi pada akhir periode ditutup eksplisit, bukan disembunyikan.

Replay ini **bukan MetaTrader Strategy Tester**, meskipun sumbernya tick asli. MT5/MetaEditor tidak tersedia untuk compile atau backtest native di workspace ini.

## Cara membaca target

Win rate dihitung dari transaksi dengan **net profit positif setelah komisi**, bukan sekadar menyentuh TP. Hasil harian memakai tanggal UTC saat exit; semua Senin–Jumat dalam periode masuk denominator, termasuk libur dan hari tanpa transaksi. Hasil akhir pekan, bila ada, dilaporkan terpisah.

Mingguan memakai ISO week Senin–Minggu. Rata-rata dan persentase target USD 100 hanya menggunakan minggu kalender lengkap; minggu batas yang parsial tetap diberi ID/status dan profitnya tetap masuk net total. Jadi net total dibagi jumlah minggu lengkap belum tentu sama dengan rata-rata minggu lengkap. Laporan mencakup hari/minggu mencapai target, minggu merugi, minggu terburuk, serta rentetan rugi.

Drawdown yang dilaporkan adalah **closed-trade balance drawdown**, bukan floating/equity drawdown tick-by-tick. Lot kecil dan win rate tinggi tidak otomatis membuat risiko kecil atau expectancy positif.

## Reproduksi

Python 3.10+ standard library dan `g++` untuk tes core C++; tanpa library trading atau koneksi akun broker.

```sh
python3 research/download_exness.py --start 2024-12 --end 2026-09 --workers 3

out=.hoplite/artifacts/high-win-study-reproduction
python3 -m research.high_win.study develop --out "$out"
python3 -m research.high_win.study validate --out "$out"
python3 -m research.high_win.study check --out "$out"

python3 -m research.high_win.replay_ticks \
  --lock "$out/lock.json" \
  --candidate sweep_24_stop1.25_rr1.00 \
  --start 2026-06-01 --end 2026-09-01 \
  --out "$out/tick-check"

python3 -m research.high_win.report --input "$out"
bash tests/run.sh
```

Gunakan direktori output baru; hasil selesai tidak boleh ditimpa diam-diam. Kandidat contoh di atas adalah fallback terkunci dari penelitian ini, **bukan rekomendasi live**. Jika data/kode berubah dan pemilihan menghasilkan identitas lain, jangan mengubah parameter sampai kembali terlihat bagus: catat penelitian baru dan perlakukan validasi lama sebagai data yang sudah terpakai.

Fingerprint meliputi protokol, seleksi, engine, indikator/agregasi yang diimpor, dan adapter replay. `validate.json` dipublikasikan lebih dulu, baru lock yang mengikat hash validasi; replay CLI menolak kandidat/rentang/model yang tidak cocok. Perbaikan audit pelaporan/provenance dilakukan dengan mengulang semua fase tanpa mengubah aturan trading: **76 CSV transaksi identik byte-per-byte** dengan percobaan pertama yang tetap disimpan.

Tes kode hanya memverifikasi implementasi dan guard. Tes tersebut tidak membuktikan kemampuan menghasilkan profit.
