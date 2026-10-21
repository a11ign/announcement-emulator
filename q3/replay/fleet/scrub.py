"""Take every network address out of what an Ansible play or a status listing printed, before it is kept (A11-165).

    ... | python scrub.py [inventory.yml]

The addresses of the boxes (from the inventory, when given) become the box's name; the page server's and the control plane's become `capture-host` and `control-plane` (given as CAPTURE_HOST and CONTROL_HOST);
any other IPv4 literal becomes `<address>`. A version number of three parts or fewer is not an address and is kept."""
import sys, os, re
IPV4 = re.compile(r'(?<![\w.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\w]|\.\d)')


def names_by_address(inventory_path):
    import yaml
    with open(inventory_path) as f: inv = yaml.safe_load(f)
    hosts = inv['all']['children']['a11y_workers']['hosts']
    return {h['ansible_host']: name for name, h in hosts.items() if h.get('ansible_host')}


def scrub(text, names):
    return IPV4.sub(lambda m: names.get(m.group(0), '<address>'), text)


if __name__ == '__main__':
    names = names_by_address(sys.argv[1]) if len(sys.argv) > 1 else {}
    for key, name in (('CAPTURE_HOST', 'capture-host'), ('CONTROL_HOST', 'control-plane')):
        if os.environ.get(key): names[os.environ[key]] = name
    sys.stdout.write(scrub(sys.stdin.read(), names))
