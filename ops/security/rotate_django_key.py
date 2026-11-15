#!/usr/bin/env python3
"""Rotate the production Django key without writing its value to output."""

import grp
import os
from pathlib import Path
import secrets
import tempfile


ENV_FILE = Path('/etc/scissors/backend.env')


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run as root')
    lines = ENV_FILE.read_text(encoding='utf-8').splitlines(keepends=True)
    matches = [index for index, line in enumerate(lines) if line.startswith('SECRET_KEY=')]
    if len(matches) != 1:
        raise SystemExit('Expected exactly one SECRET_KEY assignment')
    lines[matches[0]] = f'SECRET_KEY={secrets.token_urlsafe(64)}\n'
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', dir=ENV_FILE.parent,
            prefix='.backend-env-', delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.writelines(lines)
            temporary.flush()
            os.fsync(temporary.fileno())
            os.fchmod(temporary.fileno(), 0o640)
            os.fchown(temporary.fileno(), 0, grp.getgrnam('scissors-backend').gr_gid)
        os.replace(temporary_path, ENV_FILE)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    print('Django key rotated')


if __name__ == '__main__':
    main()
