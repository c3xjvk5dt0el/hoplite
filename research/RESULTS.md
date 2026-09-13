# Hasil penelitian Trend Pullback XAU

**Keputusan: belum layak untuk akun live. Kandidat ini tidak menunjukkan win rate 80% maupun keunggulan bersih yang kuat.** EA tetap disediakan sebagai alat Strategy Tester/demo; hasil yang lemah tidak ditutupi dengan mengganti parameter setelah pengujian.

## Data dan metode

- Sumber: [arsip tick publik Exness](https://www.exness.com/tick-history/), simbol `XAUUSD` tanpa suffix. [Exness menjelaskan](https://get.exness.help/hc/en-us/articles/360021547851-Tick-history) bahwa server arsip tidak bisa dipilih; data ini tidak dijamin identik dengan MT5Trial7 atau tipe akun pengguna.
- 21 arsip bulanan Desember 2024–Agustus 2026: **147.524.553 tick**, menjadi **616.216 candle M1 Bid/Ask**. Desember 2024 hanya untuk pemanasan indikator; periode evaluasi Januari 2025–Agustus 2026.
- Pemeriksaan mencakup CRC ZIP, header, timestamp UTC berurutan dan sesuai bulan, quote positif/tidak silang, serta SHA256. Ini validasi **struktur arsip**, bukan bukti independen kelengkapan feed dari penyedia.
- Aturan dan dua skenario biaya ditetapkan sebelum melihat hasil, seperti dicatat dalam [PLAN.md](PLAN.md). Peralihan Dukascopy ke Exness disebabkan kendala akses, bukan pemilihan hasil terbaik.
- Pengujian merupakan **proxy OHLC M1**, bukan replay native-tick dan bukan Strategy Tester MT5. Data tick diagregasi terlebih dahulu; urutan intramenit tidak digunakan. Detail keterbatasan ada di [README riset](README.md).

## Hasil dasar: lot 0,01, RR 1:1,5, timeout 60 menit

Asumsi kontrak 100 oz/lot dan akun USD. Spread berasal dari quote Bid/Ask arsip. Komisi asumsi USD 0,04 round-trip, slippage merugikan 0,05 satuan harga pada entry/exit market atau SL; TP di target. **Swap belum dimodelkan.**

| Periode | Transaksi | Menang bersih | Profit factor | Hasil USD sebelum swap |
|---|---:|---:|---:|---:|
| Jan–Jun 2025 | 1.625 | 41,66% | 0,9780 | −71,89 |
| Jul–Des 2025 | 1.730 | 43,76% | 1,0016 | +6,80 |
| Jan–Mei 2026 | 1.444 | 42,18% | 1,0181 | +129,70 |
| Jun–Agu 2026 | 896 | 41,41% | 0,9887 | −35,96 |
| **Gabungan** | **5.695** | **42,39%** | **1,0016** | **+28,67** |

Total dihitung dari hasil transaksi sebelum pembulatan masing-masing baris. Menang berarti P/L setelah komisi positif, bukan sekadar TP tersentuh.

- Rata-rata transaksi hanya **+USD 0,005** sebelum swap. Profit factor 1,0016 pada asumsi dasar tidak memberi bantalan biaya yang berarti.
- Hasil bergantung pada sedikit periode baik: Januari 2026 menghasilkan sekitar **+USD 680,88**, sedangkan gabungan 19 bulan lainnya sekitar **−USD 652,21**. Ini pemeriksaan konsistensi, bukan alasan menghapus bulan rugi dari hasil utama.
- **1.495 transaksi (26,25%)** ditutup oleh batas waktu, sehingga payoff aktual tidak selalu mengikuti RR target 1:1,5.
- Terdapat **133 transaksi lintas tanggal UTC** dan **132 exit setelah lebih dari 60 menit**, termasuk saat quote/pasar tidak tersedia. Hitungan lintas tanggal bukan perhitungan swap broker; biaya menginap tetap perlu diuji di MT5.
- Drawdown kumulatif hasil transaksi tertutup **USD 969,33**, bukan equity drawdown tick-by-tick. Kerugian beruntun maksimum 15 transaksi.
- Ada 0 menit dengan SL dan TP keduanya tersentuh menurut OHLC. Ini tidak menghapus perbedaan eksekusi, slippage, batas stop/freeze, kesiapan indikator atau latensi broker.

## Uji slippage lebih buruk

Hanya asumsi slippage dinaikkan dari 0,05 menjadi 0,15; aturan sinyal, RR dan filter tidak dituning.

| Periode | Hasil USD sebelum swap |
|---|---:|
| Jan–Jun 2025 | −408,57 |
| Jul–Des 2025 | −339,33 |
| Jan–Mei 2026 | −88,54 |
| Jun–Agu 2026 | −212,62 |
| **Gabungan** | **−1.049,06** |

Gabungan stres: 5.673 transaksi, win rate **41,05%**, profit factor **0,9439**. Jumlah transaksi berubah karena TP memakai harga entry setelah slippage; waktu keluar/tersedianya posisi untuk sinyal berikutnya dapat berubah.

## Kesimpulan dari candle dan transaksi

Filter tren M15 dan reclaim EMA20 M5 belum cukup menghasilkan keuntungan yang tahan terhadap biaya dalam data ini. Contoh transaksi ketiga pada 2 Januari 2025 memperlihatkan BUY pullback yang valid tetapi tidak mencapai TP: posisi keluar setelah 60 menit dengan rugi sekitar USD 1,39. Contoh itu ilustrasi mekanisme, bukan bukti semua pullback gagal; keputusan berasal dari keseluruhan periode dan uji biaya.

**Tidak ada dasar untuk menyebut kandidat ini lebih baik dari EA lama secara pasti.** Feed, rentang waktu, eksekusi dan model pengujian tidak identik dengan laporan MT5 pengguna. Mengecilkan TP agar persentase menang naik juga tidak otomatis memperbaiki expectancy.

## Verifikasi dan reproduksi

- [`results.json`](results.json) menyimpan hasil terstruktur, asumsi, rincian per arah/bulan, jumlah tick/candle dan SHA256 arsip/CSV. Tidak memuat laporan akun pengguna atau tick mentah.
- `bash tests/run.sh` menguji rumus asli kedua `.mq5` melalui C++ serta indikator, no-lookahead, parsing, biaya dan exit simulator melalui Python.
- Peninjauan independen menghitung ulang hasil dari CSV dan mencocokkan hash 21 arsip. Tidak ada parameter strategi yang dipilih berdasarkan hasil terbaik.
- **Belum dikompilasi di MetaEditor atau dijalankan di Strategy Tester MT5.** Keterbatasan ini tidak digantikan oleh tes C++/Python.
- Jika ingin memeriksa EA, gunakan [file satuan dan panduan MT5](../Experts/TrendPullbackXAU/README.md), reset Inputs dan real ticks broker. Jangan gunakan uang riil berdasarkan hasil riset ini. Periode yang sudah diperiksa di sini tidak lagi boleh disebut data baru yang belum disentuh untuk pemilihan strategi selanjutnya.
