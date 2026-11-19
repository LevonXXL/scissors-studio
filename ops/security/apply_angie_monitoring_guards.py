#!/usr/bin/env python3
"""Add exact 404 guards for local health endpoints to Scissors Angie vhosts."""

import argparse
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


VHOSTS = {
    'scissors-frontend.conf': {'scissors.group', 'www.scissors.group', 'studio.scissors.group'},
    'scissors-api.conf': {'api.studio.scissors.group'},
    'scissors-admin.conf': {'admin.studio.scissors.group'},
}
def server_blocks(contents):
    for match in re.finditer(r'(?m)^server\s*\{', contents):
        depth = 0
        for index in range(match.end() - 1, len(contents)):
            if contents[index] == '{':
                depth += 1
            elif contents[index] == '}':
                depth -= 1
                if depth == 0:
                    yield match.start(), index + 1
                    break
        else:
            raise ValueError('Unclosed Angie server block')


def add_guards(block):
    lines = block.splitlines(keepends=True)
    depth = 0
    output = []
    changed = False
    inserted = False
    has_health = 'location = /health/' in block
    has_ready = 'location = /ready/' in block

    def missing_guards(indent):
        nonlocal has_health, has_ready, changed
        rules = ''
        if not has_health:
            rules += f'{indent}location = /health/ {{ return 404; }}\n'
            has_health = changed = True
        if not has_ready:
            rules += f'{indent}location = /ready/  {{ return 404; }}\n'
            has_ready = changed = True
        return rules

    for line in lines:
        if depth == 1:
            redirect = re.match(r'^(\s*)return\s+(30[12])\s+([^;]+);\s*$', line)
            if redirect:
                indent, status, target = redirect.groups()
                output.append(
                    missing_guards(indent)
                    + f'{indent}location / {{ return {status} {target}; }}\n'
                )
                inserted = changed = True
                depth += line.count('{') - line.count('}')
                continue

        output.append(line)
        if re.match(r'^\s*server_name\s+', line) and not inserted:
            rules = missing_guards(re.match(r'^(\s*)', line).group(1))
            if rules:
                output.append(rules)
                inserted = True
        depth += line.count('{') - line.count('}')

    if not inserted and not (has_health and has_ready):
        raise ValueError('Could not place monitoring guards in an Angie server block')
    return ''.join(output), changed


def patch_file(path, hosts, dry_run=False):
    original = path.read_text()
    blocks = list(server_blocks(original))
    changed_count = 0
    contents = original
    for start, end in reversed(blocks):
        block = contents[start:end]
        server_name = re.search(r'(?m)^\s*server_name\s+([^;]+);', block)
        if not server_name:
            continue
        configured_hosts = set(server_name.group(1).split())
        if not (configured_hosts & hosts):
            continue
        patched, changed = add_guards(block)
        if changed:
            contents = contents[:start] + patched + contents[end:]
            changed_count += 1

    if changed_count and not dry_run:
        backup = path.with_name(
            f'{path.name}.pre-monitoring-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}'
        )
        shutil.copy2(path, backup)
        path.write_text(contents)
        shutil.copystat(backup, path)
    return changed_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-dir', type=Path, default=Path('/etc/angie/http.d'))
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    for filename, hosts in VHOSTS.items():
        path = args.config_dir / filename
        if not path.is_file():
            raise SystemExit(f'Missing expected Angie vhost: {path}')
        changed = patch_file(path, hosts, dry_run=args.dry_run)
        print(f'{filename}: ' + ('updated' if changed else 'already guarded'))


if __name__ == '__main__':
    main()
