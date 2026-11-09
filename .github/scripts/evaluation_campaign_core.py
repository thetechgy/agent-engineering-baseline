"""Shared ordering, bounded scheduling, accounting and consolidated rendering.

Callbacks own task/runtime observations. This module has no task or CLI imports.
"""
from decimal import Decimal
import math


def require(value, message):
    if not value:
        raise ValueError(message)


def schedule(cases, variants, trials):
    require(cases and len(set(cases)) == len(cases), 'Duplicate or empty cases')
    require(len(variants) >= 2 and len(set(variants)) == len(variants), 'Duplicate or insufficient variants')
    require(type(trials) is int and 0 < trials <= 100, 'Unsupported trial limit')
    rows = []
    for trial in range(1, trials + 1):
        ordered = cases if trial % 2 else tuple(reversed(cases))
        for case in ordered:
            offset = (trial + cases.index(case) + 1) % len(variants)
            order = variants[offset:] + variants[:offset]
            for variant in order:
                rows.append({'position': len(rows) + 1, 'case': case, 'trial': trial, 'variant': variant})
    require(len(rows) <= 1000, 'Campaign attempt limit')
    return rows


def accounting(rows):
    total = Decimal('0')
    for row in rows:
        if row['state'] == 'unlaunched':
            continue
        usage = row.get('usage')
        require(type(usage) is dict and type(usage.get('estimated_usd')) in (int, float)
                and math.isfinite(usage['estimated_usd']) and usage['estimated_usd'] >= 0,
                'Unknown usage; scheduling stopped')
        total += Decimal(str(usage['estimated_usd']))
    return float(total)


def drive(ledger, attempt, *, save, resources, baseline, threshold, before_attempt=lambda row: None):
    """One scheduler, no retries/resume. Persist every transition before launch."""
    rows = ledger['entries']
    ledger['state'] = 'running'; save()
    try:
        for row in rows:
            total = accounting(rows)
            if total >= threshold:
                ledger['stop_reason'] = 'estimated_usage_threshold'; break
            if resources() != baseline:
                ledger['stop_reason'] = 'cleanup_failure'; break
            before_attempt(row)
            row.update(state='launching', estimated_usd_before=total); save()
            reason = attempt(row, total)
            save()
            if reason:
                ledger['stop_reason'] = reason
            if ledger.get('stop_reason'):
                break
        ledger['state'] = 'stopped' if ledger.get('stop_reason') else 'completed'
    except BaseException as error:
        ledger.update(state='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', failure=type(error).__name__)
        for row in rows:
            if row['state'] == 'launching':
                row['state'] = ledger['state']
        raise
    finally:
        save()
    return ledger


def render(inputs, destination):
    """Existing admission, analysis and renderer; reproduce from public inputs only."""
    import skill_analysis as analysis
    import skill_report as report
    import skill_reports as reports
    captured = analysis.capture_inputs(inputs)
    reports.write_json(destination / 'analysis/analysis.json', analysis.validate_analysis(None, captured))
    report.generate(inputs, destination / 'analysis/analysis.json', destination / 'consolidated')
    report.generate(inputs, destination / 'analysis/analysis.json', destination / 'reproduced')
    require((destination / 'consolidated/report.html').read_bytes() ==
            (destination / 'reproduced/report.html').read_bytes(), 'Public-only report reproduction failed')
    return captured


def aggregates(root, *, skill, carrier):
    """Pinned Harbor stats over exact persisted trials. The ledger retains pending slots.

    This collector envelope is derived data; original per-trial evidence is intact.
    """
    import uuid
    import json
    import skill_reports as reports
    from harbor.models.job.result import JobResult, JobStats
    from harbor.models.trial.result import TrialResult
    from datetime import datetime, timezone
    for arm in ('with_skill', 'without_skill'):
        job = root / 'jobs' / f'{skill}-{carrier}-{"with" if arm == "with_skill" else "without"}'
        trials = [TrialResult.model_validate(reports.read_json(p)) for p in sorted(job.glob('*/result.json'))]
        if not trials: continue
        value = JobResult(id=uuid.uuid5(uuid.NAMESPACE_URL, str(job)), started_at=min((t.started_at for t in trials), default=datetime.now(timezone.utc)),
                          finished_at=max((t.finished_at for t in trials if t.finished_at), default=None), n_total_trials=len(trials),
                          stats=JobStats.from_trial_results(trials, n_total_trials=len(trials)), trial_results=trials)
        reports.write_json(job / 'result.json', json.loads(value.model_dump_json()))

