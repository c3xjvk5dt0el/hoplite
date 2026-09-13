# Hasil penelitian win rate tinggi — target belum tercapai

**Keputusan: 0 dari 36 konfigurasi lolos kriteria pengembangan. Tidak ada strategi di penelitian ini yang layak diklaim menghasilkan USD 20/hari atau USD 100/minggu pada lot 0,01. Jangan gunakan hasil ini sebagai dasar trading uang riil.**

## Win rate tinggi belum cukup

Win rate pengembangan tertinggi adalah **60.85%** dari 212 transaksi, kandidat `bands_2.5_stop0.75_rr0.60`. Hasil bersih sepanjang 2025 hanya **USD +4.35**, profit factor 1.0127; pada slippage stres menjadi **USD -22.52**. Ini statistik pemilihan pada data pengembangan, bukan performa masa depan.

[Semua 36 konfigurasi, dua skenario biaya, hasil kedua semester, dan alasan gagal](candidate_scores.csv) dipublikasikan; bukan hanya kandidat yang terlihat bagus.

## Pembanding yang dikunci, bukan kandidat yang lolos

Fallback `sweep_24_stop1.25_rr1.00` dipilih oleh skor pengembangan yang sudah ditetapkan. Ini berbeda dari kandidat dengan win rate tertinggi di atas. Ia tidak lolos gate; hasil validasi/final tidak digunakan untuk mengganti identitas atau parameter. EA eksperimennya adalah [SweepReclaimXAU](../../Experts/SweepReclaimXAU/README.md), default tidak mengizinkan akun riil.

| Periode / model | Trade dasar | Win rate dasar | Net dasar (USD) | PF dasar | Rata-rata minggu lengkap (USD) | Net stres (USD) |
|---|---:|---:|---:|---:|---:|---:|
| 2025 / proxy M1 | 271 | 51.29% | +1.73 | 1.0031 | -0.19 | -20.87 |
| Jan–Mei 2026 / proxy M1 | 106 | 45.28% | -103.44 | 0.7600 | -4.93 | -123.90 |
| Jun–Agu 2026 / proxy M1 | 84 | 48.81% | -37.05 | 0.8533 | -3.35 | -44.99 |
| Jun–Agu 2026 / **urutan tick asli** | 84 | 48.81% | -40.37 | 0.8423 | -3.61 | -48.41 |

Replay membaca **21,270,986 tick** dari tiga arsip bulanan. Ini replay buatan sendiri atas quote publik, **bukan backtest MT5**, dan tidak mereproduksi broker/latency/rejection/stop-out.

## Apakah target harian/mingguan tercapai?

Untuk pemeriksaan tick Juni–Agustus 2026:

| Ukuran | Biaya dasar | Biaya stres |
|---|---:|---:|
| Hari >= USD 20 / seluruh weekday | 0/66 (0.0%) | 0/66 (0.0%) |
| Minggu lengkap >= USD 100 | 0/13 (0.0%) | 0/13 (0.0%) |
| Minggu merugi | 9/13 | 9/13 |
| Median minggu lengkap, USD | -3.94 | -4.24 |
| Minggu lengkap terburuk, USD | -39.54 | -32.80 |
| Closed-trade drawdown maksimum, USD | 89.03 | 86.10 |
| Rentetan minggu rugi maksimum | 6 | 6 |
| Transaksi melewati tanggal UTC | 0 | 0 |
| Exit sesudah batas 45 menit | 0 | 0 |

Hari libur/tanpa transaksi tetap dihitung sebagai weekday nol; minggu parsial tidak dipakai untuk persentase target. Semua P/L, termasuk minggu parsial, tetap masuk net total. Drawdown di atas bukan equity/floating drawdown.

### Semua minggu pemeriksaan tick

| Minggu ISO | Status | Net dasar (USD) | Net stres (USD) |
|---|---|---:|---:|
| 2026-W23 | lengkap | +6.74 | +6.24 |
| 2026-W24 | lengkap | -5.86 | -6.16 |
| 2026-W25 | lengkap | -8.66 | -9.26 |
| 2026-W26 | lengkap | -1.79 | -3.20 |
| 2026-W27 | lengkap | -2.55 | -3.05 |
| 2026-W28 | lengkap | -39.54 | -32.80 |
| 2026-W29 | lengkap | -13.96 | -14.46 |
| 2026-W30 | lengkap | +12.48 | +12.48 |
| 2026-W31 | lengkap | +20.88 | +20.77 |
| 2026-W32 | lengkap | -16.32 | -17.02 |
| 2026-W33 | lengkap | -9.43 | -10.23 |
| 2026-W34 | lengkap | +15.09 | +6.13 |
| 2026-W35 | lengkap | -3.94 | -4.24 |
| 2026-W36 | parsial | +6.50 | +6.40 |

## Batas kesimpulan dan verifikasi

- Data 2025–Agustus 2026 sudah digunakan dalam penelitian pullback terdahulu. Pemisahan waktu di sini bukan out-of-sample baru yang sepenuhnya independen.
- Data Exness publik bersifat indikatif; tidak dijamin sama dengan akun/server pengguna. Hash/CRC membuktikan integritas/struktur file, bukan kelengkapan feed upstream.
- Lot tetap 0,01, kontrak 100 oz/lot dan akun USD; komisi USD 0,04 round-trip, slippage 0,05 dasar atau 0,15 stres. Swap, margin, rejection, latency dan stop/freeze broker tidak dimodelkan.
- Core logika diuji dengan C++/Python, termasuk lookahead, quote Bid/Ask, risiko harian, target nol-hari, lock, dan urutan tick. Ini bukan compile MQL5 atau Strategy Tester; MT5/MetaEditor belum tersedia.
- Audit provenance/pelaporan tidak dipakai untuk memperbaiki kinerja: 76 CSV transaksi dari pengulangan tiga fase identik dengan percobaan pertama. Tidak ada konfigurasi tambahan atau penggantian kandidat setelah hasil final.
- Hasil ini tidak membuktikan semua strategi emas pasti gagal. Kesimpulan terbatas: kandidat yang diteliti **belum memenuhi permintaan win rate tinggi yang tahan biaya dan target pendapatan tersebut**.

[Metode, asumsi dan reproduksi](README.md) · [Protokol](PLAN.md) · [Hasil terstruktur dan provenance](results.json)
