"""Export the completed failed-gate study without discarding adverse outcomes."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from research.high_win.study import verified_lock


def money(value):
    return f'{value:+,.2f}'


def export(root: Path, destination: Path):
    stages={phase:json.loads((root/f'{phase}.json').read_text()) for phase in ('develop','validate','check')}
    lock=verified_lock(root/'lock.json')
    tick=json.loads((root/'tick-check/results.json').read_text())
    if tick['candidate']['id']!=lock['candidate_id']:
        raise ValueError('Tick result does not belong to the locked candidate')
    if [tick['requested_period']['start'],tick['requested_period']['end']]!=stages['check']['period']:
        raise ValueError('Tick result does not cover the complete final-check period')
    if tick['source']['metadata']['sha256']!=stages['check']['data']['metadata_sha256']:
        raise ValueError('Tick and OHLC study used different source manifests')
    development=stages['develop']['candidates']
    if len(development)!=36 or any(record['eligible'] for record in development):
        raise ValueError('This report template describes the 36-candidate failed-gate study; do not mislabel a different outcome')
    highest=max(development,key=lambda r:r['base']['win_rate_pct'])
    chosen=[]
    for phase in stages:
        matches=[r for r in stages[phase]['candidates'] if r['candidate']['id']==lock['candidate_id']]
        if len(matches)!=1:
            raise ValueError(f'Locked candidate absent/duplicated in {phase}')
        chosen.append(matches[0])
    rows=[]
    for record in development:
        row=dict(record['candidate'])
        for scenario in ('base','stress'):
            for metric in ('trades','win_rate_pct','net_usd','profit_factor','closed_trade_max_drawdown_usd',
                           'average_full_week_usd','worst_full_week_usd','positive_weeks_pct','losing_weeks',
                           'days_at_least_20','days_at_least_20_pct','weeks_at_least_100','weeks_at_least_100_pct'):
                row[f'{scenario}_{metric}']=record[scenario][metric]
            for half in ('H1','H2'):
                row[f'{scenario}_{half}_net_usd']=record['halves'][scenario][half]['net_usd']
        row['eligible']=record['eligible']
        row['failed_gates']='|'.join(record['failed_gates'])
        rows.append(row)
    destination.mkdir(parents=True,exist_ok=True)
    with (destination/'candidate_scores.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    artifact_paths=[root/f'{phase}.json' for phase in stages]+[root/'lock.json',root/'tick-check/results.json']
    result=dict(objective='USD 20 per UTC weekday / USD 100 per complete ISO week, fixed 0.01 lot; not a guarantee',
                verdict='No candidate passed the development gate. Income objective not established. Not qualified for live use.',
                candidate_count=len(development),development_eligible=sum(r['eligible'] for r in development),
                highest_development_win_rate_candidate=highest,selection=lock,
                periods={phase:dict(period=stages[phase]['period'],candidate=record)
                         for phase,record in zip(stages,chosen)},
                native_tick_check=tick,
                source=stages['check']['data'],
                artifacts={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in artifact_paths})
    audit=root/'audit_parity.json'
    if audit.exists():
        audit_result=json.loads(audit.read_text())
        result['audited_rerun']=dict(identical_trade_files=audit_result['identical_trade_files'],
                                     audit_sha256=hashlib.sha256(audit.read_bytes()).hexdigest())
    (destination/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    b,s=highest['base'],highest['stress']
    lines=[
        '# Hasil penelitian win rate tinggi — target belum tercapai',
        '',
        '**Keputusan: 0 dari 36 konfigurasi lolos kriteria pengembangan. Tidak ada strategi di penelitian ini yang layak diklaim menghasilkan USD 20/hari atau USD 100/minggu pada lot 0,01. Jangan gunakan hasil ini sebagai dasar trading uang riil.**',
        '',
        '## Win rate tinggi belum cukup',
        '',
        f'Win rate pengembangan tertinggi adalah **{b["win_rate_pct"]:.2f}%** dari {b["trades"]} transaksi, kandidat `{highest["candidate"]["id"]}`. Hasil bersih sepanjang 2025 hanya **USD {money(b["net_usd"])}**, profit factor {b["profit_factor"]:.4f}; pada slippage stres menjadi **USD {money(s["net_usd"])}**. Ini statistik pemilihan pada data pengembangan, bukan performa masa depan.',
        '',
        '[Semua 36 konfigurasi, dua skenario biaya, hasil kedua semester, dan alasan gagal](candidate_scores.csv) dipublikasikan; bukan hanya kandidat yang terlihat bagus.',
        '',
        '## Pembanding yang dikunci, bukan kandidat yang lolos',
        '',
        f'Fallback `{lock["candidate_id"]}` dipilih oleh skor pengembangan yang sudah ditetapkan. Ini berbeda dari kandidat dengan win rate tertinggi di atas. Ia tidak lolos gate; hasil validasi/final tidak digunakan untuk mengganti identitas atau parameter. EA eksperimennya adalah [SweepReclaimXAU](../../Experts/SweepReclaimXAU/README.md), default tidak mengizinkan akun riil.',
        '',
        '| Periode / model | Trade dasar | Win rate dasar | Net dasar (USD) | PF dasar | Rata-rata minggu lengkap (USD) | Net stres (USD) |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ]
    labels=['2025 / proxy M1','Jan–Mei 2026 / proxy M1','Jun–Agu 2026 / proxy M1']
    for label,record in zip(labels,chosen):
        a,z=record['base'],record['stress']
        lines.append(f'| {label} | {a["trades"]} | {a["win_rate_pct"]:.2f}% | {money(a["net_usd"])} | {a["profit_factor"]:.4f} | {money(a["average_full_week_usd"])} | {money(z["net_usd"])} |')
    native=tick['scenarios']
    a,z=native['base']['metrics'],native['stress']['metrics']
    lines.append(f'| Jun–Agu 2026 / **urutan tick asli** | {a["trades"]} | {a["win_rate_pct"]:.2f}% | {money(a["net_usd"])} | {a["profit_factor"]:.4f} | {money(a["average_full_week_usd"])} | {money(z["net_usd"])} |')
    lines += [
        '',
        f'Replay membaca **{tick["tick_replay"]["ticks_read"]:,} tick** dari tiga arsip bulanan. Ini replay buatan sendiri atas quote publik, **bukan backtest MT5**, dan tidak mereproduksi broker/latency/rejection/stop-out.',
        '',
        '## Apakah target harian/mingguan tercapai?',
        '',
        'Untuk pemeriksaan tick Juni–Agustus 2026:',
        '',
        '| Ukuran | Biaya dasar | Biaya stres |',
        '|---|---:|---:|',
        f'| Hari >= USD 20 / seluruh weekday | {a["days_at_least_20"]}/{a["weekday_count"]} ({a["days_at_least_20_pct"]:.1f}%) | {z["days_at_least_20"]}/{z["weekday_count"]} ({z["days_at_least_20_pct"]:.1f}%) |',
        f'| Minggu lengkap >= USD 100 | {a["weeks_at_least_100"]}/{a["full_week_count"]} ({a["weeks_at_least_100_pct"]:.1f}%) | {z["weeks_at_least_100"]}/{z["full_week_count"]} ({z["weeks_at_least_100_pct"]:.1f}%) |',
        f'| Minggu merugi | {a["losing_weeks"]}/{a["full_week_count"]} | {z["losing_weeks"]}/{z["full_week_count"]} |',
        f'| Median minggu lengkap, USD | {money(a["median_full_week_usd"])} | {money(z["median_full_week_usd"])} |',
        f'| Minggu lengkap terburuk, USD | {money(a["worst_full_week_usd"])} | {money(z["worst_full_week_usd"])} |',
        f'| Closed-trade drawdown maksimum, USD | {a["closed_trade_max_drawdown_usd"]:.2f} | {z["closed_trade_max_drawdown_usd"]:.2f} |',
        f'| Rentetan minggu rugi maksimum | {a["max_consecutive_losing_weeks"]} | {z["max_consecutive_losing_weeks"]} |',
        f'| Transaksi melewati tanggal UTC | {a["cross_utc_date_trades"]} | {z["cross_utc_date_trades"]} |',
        f'| Exit sesudah batas 45 menit | {a["exits_after_45_minutes"]} | {z["exits_after_45_minutes"]} |',
        '',
        'Hari libur/tanpa transaksi tetap dihitung sebagai weekday nol; minggu parsial tidak dipakai untuk persentase target. Semua P/L, termasuk minggu parsial, tetap masuk net total. Drawdown di atas bukan equity/floating drawdown.',
        '',
        '### Semua minggu pemeriksaan tick',
        '',
        '| Minggu ISO | Status | Net dasar (USD) | Net stres (USD) |',
        '|---|---|---:|---:|',
    ]
    for key,week in a['weeks'].items():
        lines.append(f'| {key} | {"lengkap" if week["complete"] else "parsial"} | {money(week["net_usd"])} | {money(z["weeks"][key]["net_usd"])} |')
    lines += [
        '',
        '## Batas kesimpulan dan verifikasi',
        '',
        '- Data 2025–Agustus 2026 sudah digunakan dalam penelitian pullback terdahulu. Pemisahan waktu di sini bukan out-of-sample baru yang sepenuhnya independen.',
        '- Data Exness publik bersifat indikatif; tidak dijamin sama dengan akun/server pengguna. Hash/CRC membuktikan integritas/struktur file, bukan kelengkapan feed upstream.',
        '- Lot tetap 0,01, kontrak 100 oz/lot dan akun USD; komisi USD 0,04 round-trip, slippage 0,05 dasar atau 0,15 stres. Swap, margin, rejection, latency dan stop/freeze broker tidak dimodelkan.',
        '- Core logika diuji dengan C++/Python, termasuk lookahead, quote Bid/Ask, risiko harian, target nol-hari, lock, dan urutan tick. Ini bukan compile MQL5 atau Strategy Tester; MT5/MetaEditor belum tersedia.',
        '- Audit provenance/pelaporan tidak dipakai untuk memperbaiki kinerja: 76 CSV transaksi dari pengulangan tiga fase identik dengan percobaan pertama. Tidak ada konfigurasi tambahan atau penggantian kandidat setelah hasil final.',
        '- Hasil ini tidak membuktikan semua strategi emas pasti gagal. Kesimpulan terbatas: kandidat yang diteliti **belum memenuhi permintaan win rate tinggi yang tahan biaya dan target pendapatan tersebut**.',
        '',
        '[Metode, asumsi dan reproduksi](README.md) · [Protokol](PLAN.md) · [Hasil terstruktur dan provenance](results.json)',
        '',
    ]
    (destination/'RESULTS.md').write_text('\n'.join(lines))
    print(json.dumps({'candidate':lock['candidate_id'],'native_net':a['net_usd'],
                      'native_win_rate':a['win_rate_pct'],'target_weeks':a['weeks_at_least_100']},indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=Path('research/high_win'))
    args=parser.parse_args();export(args.input,args.out)


if __name__=='__main__': main()
