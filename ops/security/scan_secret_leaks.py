#!/usr/bin/env python3
"""Report secret matches in deployed artifacts without printing values."""

import os
from pathlib import Path


ENV_FILE = Path('/etc/scissors/backend.env')
ROOTS = [
    Path('/home/scissors/current'),
    Path('/home/scissors/static'),
    Path('/home/scissors/media'),
    Path('/home/scissors/releases'),
]
SECRET_NAMES = {
    'DATABASE_URL', 'SECRET_KEY', 'YCLIENTS_PARTNER_TOKEN', 'YCLIENTS_USER_TOKEN',
    'REWIO_API_KEY', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_WEBHOOK_SECRET', 'SMTP_PASSWORD',
}


def secrets_to_find():
    found = {}
    for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
        name, _, raw = line.partition('=')
        if name in SECRET_NAMES:
            value = raw.strip().strip('"\'').encode()
            if len(value) >= 8:
                found[name] = value
    for key_name in ('WEB_PUSH_VAPID_PRIVATE_KEY',):
        for line in Path('/etc/scissors/vapid.env').read_text(encoding='utf-8').splitlines():
            name, _, raw = line.partition('=')
            if name == key_name:
                value = raw.strip().strip('"\'').encode()
                if len(value) >= 8:
                    found[key_name] = value
    return found


def scan_file(path, needles):
    overlap = max(map(len, needles.values())) - 1
    with path.open('rb') as source:
        tail = b''
        while chunk := source.read(1024 * 1024):
            data = tail + chunk
            for name, value in needles.items():
                if value in data:
                    yield name
            tail = data[-overlap:]


def main():
    needles = secrets_to_find()
    matches = []
    for root in ROOTS:
        for directory, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [name for name in dirs if name not in {'.venv', 'node_modules', '__pycache__'}]
            for name in files:
                path = Path(directory) / name
                if path.is_symlink() or not path.is_file():
                    continue
                for secret_name in set(scan_file(path, needles)):
                    matches.append((secret_name, str(path)))
    for name, path in matches:
        print(f'MATCH {name} {path}')
    print(f'SECRET_MATCHES={len(matches)}')


if __name__ == '__main__':
    main()
