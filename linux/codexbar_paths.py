"""Shared relocatable paths for the native Linux frontend."""
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_HOME = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
CACHE = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'codexbar-waybar'
STATE_PATH = CONFIG_HOME / 'codexbar-waybar/state.json'
legacy = Path.home() / '.codexbar/config.json'
CONFIG_PATH = Path(os.environ.get('CODEXBAR_CONFIG', legacy if legacy.exists() else CONFIG_HOME / 'codexbar/config.json'))
CODEXBAR = os.environ.get('CODEXBAR_BIN') or next((str(p) for p in [ROOT / 'codexbar-cli', Path.home() / '.local/bin/codexbar'] if p.is_file()), shutil.which('codexbar') or 'codexbar')
ICONS_DIR = next((p for p in [ROOT / 'assets/providers', Path('/usr/share/codexbar-linux/icons'), Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'codexbar-waybar/icons'] if p.is_dir()), ROOT / 'assets/providers')


def read_json(path, expected, fallback):
    import json
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, expected) else fallback
    except (OSError, ValueError):
        return fallback


def write_json(path, value):
    """Atomically persist private configuration and account usage."""
    import json
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, tmp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
