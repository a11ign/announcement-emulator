"""The `-e @file` that turns browser history off on a box through control's own policy play, without changing control (A11-155).

    python policy_override.py <control>/ansible/roles/worker/defaults/main.yml > override.yml

An extra var REPLACES the role's whole `worker_edge_policy` list, so the file restates every entry the checkout declares and adds
`SavingBrowserHistoryDisabled=1`. Read at the commit the control plane runs, so the override cannot drift from what the fleet is."""
import sys, yaml

NAME = 'SavingBrowserHistoryDisabled'


def override(defaults_text):
    policy = yaml.safe_load(defaults_text)['worker_edge_policy']
    if any(e['name'] == NAME for e in policy): sys.exit(f'{NAME} is already declared in worker_edge_policy: nothing to override')
    return {'worker_edge_policy': [dict(e) for e in policy] + [{'name': NAME, 'value': 1}]}


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    with open(sys.argv[1]) as f: yaml.safe_dump(override(f.read()), sys.stdout, sort_keys=False)
