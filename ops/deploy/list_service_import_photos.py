#!/usr/bin/env python3
"""Print the source photos required by the Django service-image import."""

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'scissors-backend'
SOURCE = ROOT / 'scissors-frontend' / 'tilda_assets'
sys.path.insert(0, str(BACKEND))

from services.tilda_images import CATEGORY_IMAGES  # noqa: E402


manifest = json.loads((BACKEND / 'services' / 'tilda_service_images.json')
                      .read_text(encoding='utf-8'))
assets = {entry['asset'] for entry in manifest['images']}
assets.update(CATEGORY_IMAGES.values())

missing = sorted(asset for asset in assets if not (SOURCE / asset).is_file())
if missing:
    print(f'Missing {len(missing)} required source photos under {SOURCE}', file=sys.stderr)
    for asset in missing:
        print(asset, file=sys.stderr)
    raise SystemExit(1)

for asset in sorted(assets):
    print(asset)
