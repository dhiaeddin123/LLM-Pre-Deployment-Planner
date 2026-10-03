from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOYMENT = ROOT / 'deployment'
VALIDATION = ROOT / 'validation'


def load_planner_module():
    planner_path = DEPLOYMENT / 'deployment_planner.py'
    spec = importlib.util.spec_from_file_location('deployment_planner', planner_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


dp = load_planner_module()


def load_json(path: Path):
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def summarize_applications() -> dict:
    summary = {}
    for app_name in ['smart_surveillance', 'smart_agriculture_iot', 'crop_monitoring']:
        plan = load_json(DEPLOYMENT / 'output' / f'{app_name}.json')
        baselines = plan.get('baselines', {})
        summary[app_name] = {
            'planner': plan.get('objective', {}).get('score'),
            'all_local': baselines.get('all_local', {}).get('score'),
            'cloud_only': baselines.get('cloud_only', {}).get('score'),
            'greedy': baselines.get('greedy_first_fit', {}).get('score'),
            'all_local_feasible': baselines.get('all_local', {}).get('feasible'),
            'cloud_only_feasible': baselines.get('cloud_only', {}).get('feasible'),
            'greedy_feasible': baselines.get('greedy_first_fit', {}).get('feasible'),
            'search_method': plan.get('search', {}).get('method'),
            'configurations': plan.get('search', {}).get('configurations_evaluated'),
        }
    return summary


def summarize_validation() -> dict:
    summary = {}
    for app_name in ['smart_surveillance', 'smart_agriculture_iot', 'crop_monitoring']:
        result = load_json(VALIDATION / 'output' / f'{app_name}.json')
        sc = result.get('summary', {})
        summary[app_name] = {
            'valid': sc.get('valid'),
            'checks': sc.get('checks'),
            'passed': sc.get('passed'),
            'errors': sc.get('errors'),
            'warnings': sc.get('warnings'),
        }
    return summary


def evaluate_policy_variants() -> list[dict]:
    base_policy = load_json(DEPLOYMENT / 'sla_policy.json')
    app_name = 'smart_surveillance'

    cases = [
        ('Default', {}),
        ('Load-balance weight 0 / 20', {'objective_weights': {'load_imbalance': 0.0}}),
        ('Load-balance weight 0 / 20', {'objective_weights': {'load_imbalance': 20.0}}),
        ('Strict assumptions', {'strict_assumptions': True}),
        ('Hard availability', {'availability_mode': 'hard'}),
        ('Score-driven replication', {'replication_policy': 'score_driven'}),
        ('Partitioned persistence', {'persistent_replication': 'partitioned'}),
        ('theta=0.6', {'utilization_target': 0.6}),
        ('theta=0.95', {'utilization_target': 0.95}),
    ]

    rows = []
    for label, overrides in cases:
        infra = dp.Infrastructure(load_json(DEPLOYMENT / 'infrastructure.json'))
        policy = copy.deepcopy(base_policy)
        pl = policy['planning']
        if 'objective_weights' in overrides:
            policy['objective']['weights'].update(overrides['objective_weights'])
        for field in ('strict_assumptions', 'availability_mode', 'replication_policy', 'persistent_replication', 'utilization_target'):
            if field in overrides:
                pl[field] = overrides[field]

        app = dp.Application(app_name, infra, policy)
        plan = dp.plan_app(app, infra, policy)
        rows.append({
            'setting': label,
            'feasible': plan['status'] == 'feasible',
            'score': plan.get('objective', {}).get('score'),
            'units_moved_vs_default': None,
        })

    default_score = next(r['score'] for r in rows if r['setting'] == 'Default')
    for row in rows:
        if row['setting'] == 'Default':
            row['units_moved_vs_default'] = 0
        elif row['score'] is not None:
            row['units_moved_vs_default'] = 'n/a'
    return rows


def main() -> None:
    app_summary = summarize_applications()
    val_summary = summarize_validation()
    print('APPLICATION SUMMARY')
    for app_name, row in app_summary.items():
        print(app_name, row)
    print('\nVALIDATION SUMMARY')
    for app_name, row in val_summary.items():
        print(app_name, row)

    print('\nSENSITIVITY SUMMARY')
    for row in evaluate_policy_variants():
        print(row)


if __name__ == '__main__':
    main()
