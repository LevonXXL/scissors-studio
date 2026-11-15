#!/usr/bin/env python3
"""Keep code-only snapshots for Scissors deployments and rollbacks."""

import argparse
import datetime as dt
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid


ROOT = Path('/home/scissors-deploy/releases')
PROJECTS = {
    'backend': (Path('/opt/scissors-backend'), ['.venv', 'media', 'staticfiles']),
    'frontend': (Path('/opt/scissors-frontend'), ['node_modules']),
}
COMMON_EXCLUDES = ['.env', '.env.*', '*.pem', '*.key', '__pycache__', '*.pyc', '*.log']
SNAPSHOT_RE = re.compile(r'^(backend|frontend)-\d{8}T\d{6}-[0-9a-f]{8}$')


def rsync(source: Path, destination: Path, extra_excludes: list[str], link_dest=None) -> None:
    command = ['rsync', '-a', '--delete']
    if link_dest is not None:
        command.append(f'--link-dest={link_dest}')
    command += [f'--exclude={item}' for item in COMMON_EXCLUDES]
    command += [f'--exclude=/{item}' for item in extra_excludes]
    command += [f'{source}/', f'{destination}/']
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['snapshot', 'restore', 'list'])
    parser.add_argument('project', choices=PROJECTS)
    parser.add_argument('snapshot_id', nargs='?')
    args = parser.parse_args()

    os.umask(0o077)
    app_dir, extra_excludes = PROJECTS[args.project]
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)

    if args.action == 'list':
        for path in sorted(ROOT.glob(f'{args.project}-*')):
            if path.is_dir() and SNAPSHOT_RE.fullmatch(path.name):
                print(path.name)
        return

    if args.action == 'snapshot':
        previous = sorted(path for path in ROOT.glob(f'{args.project}-*')
                          if path.is_dir() and not path.is_symlink()
                          and SNAPSHOT_RE.fullmatch(path.name))
        name = f'{args.project}-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}'
        destination = ROOT / name
        destination.mkdir(mode=0o700)
        rsync(app_dir, destination, extra_excludes,
              link_dest=previous[-1] if previous else None)
        for old in previous[:-2]:
            shutil.rmtree(old)
        print(name)
        return

    if not args.snapshot_id or not SNAPSHOT_RE.fullmatch(args.snapshot_id):
        parser.error('Specify a valid snapshot ID')
    if not args.snapshot_id.startswith(f'{args.project}-'):
        parser.error('Snapshot belongs to another project')
    source = ROOT / args.snapshot_id
    if not source.is_dir() or source.is_symlink():
        parser.error('Snapshot does not exist')
    rsync(source, app_dir, extra_excludes)
    print(f'Restored {args.snapshot_id}')


if __name__ == '__main__':
    main()
