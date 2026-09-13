"""Phase-separated, bounded strategy comparison. Never select on the final-check result."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from research.backtest_pullback import load_minutes, timestamp
from research.high_win.engine import Costs, simulate, summary
from research.high_win.signals import build_setups, candidates

PERIODS = {'develop': ('2025-01-01','2026-01-01'),
           'validate': ('2026-01-01','2026-06-01'),
           'check': ('2026-06-01','2026-09-01')}


def verified_minutes(root: Path, end: str):
    from research.high_win.replay_ticks import load_source_catalog, load_verified_minutes, _verify_sha256
    catalog=load_source_catalog(root,timestamp('2024-12-01'),timestamp(end))
    for source in catalog.setup_months:
        _verify_sha256(source.zip_path,source.zip_sha256,f'{source.month} tick ZIP')
    provenance=dict(metadata_sha256=catalog.metadata_sha256,
                    months=[dict(month=s.month,csv_sha256=s.csv_sha256,zip_sha256=s.zip_sha256)
                            for s in catalog.setup_months])
    return load_verified_minutes(catalog.setup_months),provenance


def brief(stats):
    return {k:v for k,v in stats.items() if k not in ('days','weeks')}


def robustness(record):
    stats = record['stress']
    return (stats['net_usd']/max(stats['closed_trade_max_drawdown_usd'],1), stats['profit_factor'] or 0)


def rank(records):
    return sorted(records, key=lambda r:(-robustness(r)[0],-robustness(r)[1],r['candidate']['id']))


def fallback(records):
    pool=[r for r in records if r['base']['trades']>=200]
    if not pool:
        most=max(r['base']['trades'] for r in records)
        if most==0:
            raise ValueError('No candidate traded; there is no meaningful fallback to implement')
        pool=[r for r in records if r['base']['trades']==most]
    return rank(pool)[0]


def model_fingerprint():
    paths=['research/high_win/PLAN.md','research/high_win/signals.py','research/high_win/engine.py',
           'research/high_win/study.py','research/high_win/replay_ticks.py','research/backtest_pullback.py']
    return {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}


def write_json(path, value):
    if path.exists():
        raise FileExistsError(f'Preserve completed artifact: {path}')
    temporary=path.with_suffix('.json.part')
    with temporary.open('x') as f:
        json.dump(value,f,indent=2);f.write('\n')
    temporary.replace(path)


def verified_lock(path: Path):
    lock=json.loads(path.read_text())
    validation_path=path.parent/'validate.json'
    raw=validation_path.read_bytes()
    validation=json.loads(raw)
    if lock.get('validation_sha256')!=hashlib.sha256(raw).hexdigest():
        raise ValueError('Validation artifact does not match the published selection lock')
    if lock['model']!=model_fingerprint() or validation['model']!=lock['model']:
        raise ValueError('Model changed after validation; do not reuse this selection')
    if validation.get('phase')!='validate' or validation.get('locked_candidate_id')!=lock['candidate_id']:
        raise ValueError('Candidate lock does not belong to this completed validation')
    return lock


def eligibility(record, phase):
    base, stress = record['base'], record['stress']
    failures = []
    if base['trades'] < (200 if phase=='develop' else 80): failures.append('sample_size')
    if base['win_rate_pct'] < 60: failures.append('win_rate_below_60')
    if (base['profit_factor'] or 0) < (1.15 if phase=='develop' else 1.10): failures.append('base_profit_factor')
    if phase == 'develop':
        if (stress['profit_factor'] or 0) < 1.05: failures.append('stress_profit_factor')
        if any(h['net_usd'] <= 0 for h in record['halves']['base'].values()): failures.append('negative_half_year')
        if base['positive_weeks_pct'] < 50: failures.append('positive_weeks_below_50')
    elif (stress['profit_factor'] or 0) <= 1:
        failures.append('stress_profit_factor')
    if base['closed_trade_max_drawdown_usd'] > 500: failures.append('drawdown')
    return failures


def write_trades(path, trades):
    if trades:
        if path.exists():
            raise FileExistsError(f'Preserve prior trade artifact; use a new attempt directory: {path}')
        temporary=path.with_suffix('.csv.part')
        with temporary.open('x', newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(trades[0]))
            writer.writeheader();writer.writerows(trades)
        temporary.replace(path)


def run_candidate(candidate, setups, minutes, start, end, out: Path, phase: str):
    record = {'candidate':asdict(candidate)}
    if phase == 'develop': record['halves']={}
    for name,slippage in [('base',.05),('stress',.15)]:
        result=simulate(minutes,candidate,setups,start,end,Costs(slippage=slippage))
        record[name]=brief(result['summary'])
        record[name+'_skips']=result['skips']
        write_trades(out/f'{phase}_{candidate.id}_{name}_trades.csv',result['trades'])
        if phase=='develop':
            halves={}
            for label,a,b in [('H1','2025-01-01','2025-07-01'),('H2','2025-07-01','2026-01-01')]:
                selected=[t for t in result['trades'] if a <= t['exit_time'][:10] < b]
                halves[label]=brief(summary(selected,timestamp(a),timestamp(b)))
            record['halves'][name]=halves
        if phase=='check':
            record[name+'_weeks']=result['summary']['weeks']
            record[name+'_days']=result['summary']['days']
    if phase!='check':
        record['failed_gates']=eligibility(record,phase)
        record['eligible']=not record['failed_gates']
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=PERIODS)
    parser.add_argument('--data',type=Path,default=Path('.hoplite/artifacts/xau-research/exness'))
    parser.add_argument('--out',type=Path,default=Path('.hoplite/artifacts/high-win-study'))
    args=parser.parse_args()
    out=args.out;out.mkdir(parents=True,exist_ok=True)
    destination=out/f'{args.phase}.json'
    if destination.exists():
        raise SystemExit(f'{destination} already exists; preserve prior outcomes, do not silently overwrite them.')
    universe=candidates()
    model=model_fingerprint()
    if args.phase=='develop':
        selected=universe
    elif args.phase=='validate':
        develop=json.loads((out/'develop.json').read_text())
        if develop['model']!=model:
            raise ValueError('Model changed after development; preserve outcomes and restart all phases in a new output directory')
        selected=[c for c in universe if c.id in develop['selected_ids']]
    else:
        lock=verified_lock(out/'lock.json')
        selected=[c for c in universe if c.id==lock['candidate_id']]
    if not selected:
        raise ValueError('No candidate was selected by the preceding phase')
    a,b=PERIODS[args.phase]
    minutes,provenance=verified_minutes(args.data,b)
    setups=build_setups(minutes)
    result=dict(phase=args.phase, period=[a,b], protocol_sha256=hashlib.sha256(Path('research/high_win/PLAN.md').read_bytes()).hexdigest(),
                model=model, data=provenance, candidates=[])
    for candidate in selected:
        record=run_candidate(candidate,setups[candidate.signal_key],minutes,timestamp(a),timestamp(b),out,args.phase)
        result['candidates'].append(record)
        print(json.dumps({'phase':args.phase,'id':candidate.id,'base':{k:record['base'][k] for k in ['trades','win_rate_pct','net_usd','profit_factor','average_full_week_usd','closed_trade_max_drawdown_usd']},
                          'stress_net':record['stress']['net_usd'],'eligible':record.get('eligible')}),flush=True)
    if args.phase=='develop':
        eligible=rank([r for r in result['candidates'] if r['eligible']])
        picked=[];families=set()
        for record in eligible:
            family=record['candidate']['family']
            if family not in families:
                picked.append(record['candidate']['id']);families.add(family)
        result['development_gate_passed']=bool(picked)
        result['selected_ids']=picked[:3] or [fallback(result['candidates'])['candidate']['id']]
        result['fallback_reason']=None if picked else 'No candidate met all development gates; descriptive fallback only.'
    elif args.phase=='validate':
        develop=json.loads((out/'develop.json').read_text())
        eligible=rank([r for r in result['candidates'] if r['eligible']]) if develop['development_gate_passed'] else []
        if eligible:
            winner=eligible[0]['candidate']['id']
        else:
            development_leaders=[r for r in develop['candidates'] if r['candidate']['id'] in develop['selected_ids']]
            winner=rank(development_leaders)[0]['candidate']['id']
        result['validation_gate_passed']=bool(eligible)
        result['locked_candidate_id']=winner
        pending_lock=dict(candidate_id=winner,
            development_gate_passed=develop['development_gate_passed'],validation_gate_passed=bool(eligible),
            reason='Qualified chronological selection' if eligible else 'Failed gates; development leader retained, not validated',
            protocol_sha256=result['protocol_sha256'],model=model)
    write_json(destination,result)
    if args.phase=='validate':
        pending_lock['validation_sha256']=hashlib.sha256(destination.read_bytes()).hexdigest()
        write_json(out/'lock.json',pending_lock)
    print('SAVED',destination,flush=True)
    if 'selected_ids' in result: print('SELECTED',result['selected_ids'],flush=True)
    if 'locked_candidate_id' in result: print('LOCKED',result['locked_candidate_id'],flush=True)


if __name__=='__main__':
    main()
