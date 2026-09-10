#!/usr/bin/env python3
"""Reproducible amd64 Debian bundle with a pinned, verified upstream CLI."""
import gzip
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.0.0'
CLI_VERSION = '0.58.0'
ASSET = f'CodexBarCLI-v{CLI_VERSION}-linux-musl-x86_64.tar.gz'
DIGEST = 'c2bc606e6300626d5b2f9ec1948f4ed151a850db97837bd54efa6fdb2b230205'

def copy(source, target, executable=False):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    target.chmod(0o755 if executable else 0o644)

def build():
    os.umask(0o022)
    if subprocess.check_output(["dpkg", "--print-architecture"], text=True).strip() != "amd64":
        raise SystemExit("Build the amd64 release on an amd64 Debian/Ubuntu host.")
    cache = ROOT / '.cache'
    cache.mkdir(exist_ok=True)
    archive = cache / ASSET
    if not archive.exists():
        with urllib.request.urlopen(f'https://github.com/steipete/CodexBar/releases/download/v{CLI_VERSION}/{ASSET}') as response, archive.open('wb') as out:
            shutil.copyfileobj(response, out)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != DIGEST:
        raise SystemExit('Upstream CLI checksum mismatch; remove the cached archive and retry.')
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='codexbar-deb-') as scratch:
        stage = Path(scratch) / 'package'
        lib = stage / 'usr/lib/codexbar-linux'
        lib.mkdir(parents=True)
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                relative = Path(member.name)
                if member.issym() and member.name == 'codexbar' and member.linkname == 'CodexBarCLI':
                    continue
                if relative.is_absolute() or '..' in relative.parts or member.issym() or member.islnk():
                    raise SystemExit('Unsafe archive member')
                if member.isfile():
                    target = lib / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with tar.extractfile(member) as source, target.open('wb') as out:
                        shutil.copyfileobj(source, out)
                    target.chmod(0o755 if relative.name == 'CodexBarCLI' else 0o644)
        binary = next(lib.rglob('CodexBarCLI'))
        (lib / 'codexbar-cli').symlink_to(binary.relative_to(lib))
        for name in ['codexbar-popup.py','codexbar-tray.py','codexbar_paths.py','codexbar.sh','codexbar-popup-launch.sh','codexbar-tray.svg']:
            copy(ROOT/name,lib/name,name.endswith('.sh') or name in ['codexbar-popup.py','codexbar-tray.py'])
        subprocess.run(['cc','-shared','-fPIC','-O2','-s','-o',str(lib/'cert_redirect.so'),str(ROOT/'cert_redirect.c'),'-ldl'],check=True)
        copy(ROOT/'packaging/codexbar-linux',stage/'usr/bin/codexbar-linux',True)
        copy(ROOT/'packaging/codexbar-linux.desktop',stage/'usr/share/applications/codexbar-linux.desktop')
        copy(ROOT/'packaging/codexbar-linux-autostart.desktop',stage/'etc/xdg/autostart/codexbar-linux.desktop')
        copy(ROOT/'packaging/codexbar-linux.service',stage/'usr/lib/systemd/user/codexbar-linux.service')
        copy(ROOT/'codexbar-tray.svg',stage/'usr/share/icons/hicolor/scalable/apps/codexbar-linux.svg')
        for icon in (ROOT/'assets/providers').glob('*'):
            if icon.is_file(): copy(icon,stage/'usr/share/codexbar-linux/icons'/icon.name)
        copy(ROOT/'assets/fonts/Inter.ttf',stage/'usr/share/fonts/truetype/codexbar-linux/Inter.ttf')
        docs = stage/'usr/share/doc/codexbar-linux'
        for src,name in [(ROOT/'LICENSE','copyright'),(ROOT/'packaging/LICENSE-CodexBar','LICENSE-CodexBar'),(ROOT/'assets/fonts/OFL.txt','LICENSE-Inter'),(ROOT/'README.md','README.md')]:
            copy(src,docs/name)
        copy(ROOT/'VALIDATION.md',docs/'VALIDATION.md')
        copy(ROOT/'assets/linux-preview.png',docs/'assets/linux-preview.png')
        (docs/'changelog.gz').write_bytes(gzip.compress(f'codexbar-linux ({VERSION}) stable; urgency=medium\n\n  * Native GTK3 X11 tray and remaining-quota bars.\n\n -- Aiden Lyu <noreply@github.com>  Thu, 10 Sep 2026 12:00:00 +0000\n'.encode(),mtime=0))
        man = stage/'usr/share/man/man1/codexbar-linux.1.gz'
        man.parent.mkdir(parents=True)
        man.write_bytes(gzip.compress((ROOT/'packaging/codexbar-linux.1').read_bytes(),mtime=0))
        copy(ROOT/'packaging/lintian-overrides',stage/'usr/share/lintian/overrides/codexbar-linux')
        control = stage/'DEBIAN'
        control.mkdir()
        (control/'conffiles').write_text('/etc/xdg/autostart/codexbar-linux.desktop\n')
        size = sum(p.stat().st_size for p in stage.rglob('*') if p.is_file())//1024
        (control/'control').write_text(f'''Package: codexbar-linux
Version: {VERSION}
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Aiden Lyu <noreply@github.com>
Installed-Size: {size}
Depends: libc6 (>= 2.34), python3 (>= 3.10), python3-gi, python3-gi-cairo, python3-cairo, gir1.2-gtk-3.0, librsvg2-common, jq, xdg-utils, ca-certificates
Recommends: gnome-shell-extension-appindicator
Homepage: https://github.com/AidenLyu/CodexBar-Linux
Description: Native Linux desktop tray for AI coding usage
 GTK3 and GDK frontend based on steipete/CodexBar and
 Marouan-chak/codexbar-waybar. Includes CodexBar CLI {CLI_VERSION}.
 Colored quota bars show remaining usage; white indicates consumed usage.
 Requires an X11 desktop with a tray host. GNOME Xorg is validated.
''')
        # Normalize metadata; dpkg owns all files as root regardless of build user.
        epoch = int(os.environ.get('SOURCE_DATE_EPOCH','1789041600'))
        for path in stage.rglob('*'):
            if path.is_dir(): path.chmod(0o755)
            if not path.is_symlink(): os.utime(path,(epoch,epoch))
        out = dist/f'codexbar-linux_{VERSION}_amd64.deb'
        subprocess.run(['dpkg-deb','--root-owner-group','-Zxz','-z6','--build',str(stage),str(out)],check=True,
            env=dict(os.environ,SOURCE_DATE_EPOCH=str(epoch)))
        digest = hashlib.sha256(out.read_bytes()).hexdigest()
        (dist/'SHA256SUMS').write_text(f'{digest}  {out.name}\n')
        print(out)

if __name__ == '__main__': build()
