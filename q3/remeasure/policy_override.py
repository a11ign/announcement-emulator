"""The `-e @file` that turns browser history off on a box through control's own policy play, without changing control (A11-155).

    python policy_override.py <control>/ansible/roles/worker/defaults/main.yml > override.yml
    python policy_override.py <control>/ansible/roles/worker/defaults/main.yml --restore > restore.yml

An extra var REPLACES the role's whole `worker_edge_policy` list, so the file restates every entry the checkout declares and adds
`SavingBrowserHistoryDisabled=1`. Read at the commit the control plane runs, so the override cannot drift from what the fleet is.

`--restore` writes the same list with `SavingBrowserHistoryDisabled=0`: the fleet's own policy play only sets values and never deletes one, so putting a box back through the playbook route
means setting history to the browser's default (saved) and reading that value back. The registry value stays present, as 0."""
import sys, yaml

NAME = 'SavingBrowserHistoryDisabled'


def override(defaults_text, history=1):
    policy = yaml.safe_load(defaults_text)['worker_edge_policy']
    if any(e['name'] == NAME for e in policy): sys.exit(f'{NAME} is already declared in worker_edge_policy: nothing to override')
    return {'worker_edge_policy': [dict(e) for e in policy] + [{'name': NAME, 'value': history}]}


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and sys.argv[2] != '--restore'): sys.exit(__doc__)
    with open(sys.argv[1]) as f: yaml.safe_dump(override(f.read(), history=0 if len(sys.argv) == 3 else 1), sys.stdout, sort_keys=False)
