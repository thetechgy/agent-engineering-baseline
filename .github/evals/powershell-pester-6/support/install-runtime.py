"""Build-time acquisition of reviewed fixture inputs; never runs during a trial."""

import hashlib
from pathlib import Path
import subprocess
import tarfile
import tempfile
from urllib.request import urlopen
import zipfile


INPUTS = (
    ('https://github.com/PowerShell/PowerShell/releases/download/v7.6.6/powershell-7.6.6-linux-x64.tar.gz',
     'ddbc4a2d113bbd46d283cfedcbcd117a70caefd7673f41f2b4e0000badf103bc', 'powershell.tar.gz'),
    ('https://www.powershellgallery.com/api/v2/package/Pester/6.2.0',
     'e6ac7418d4f12500269aaca58ae56cf1caafbbf1afa2cec334e289d1cf50a239', 'pester.nupkg'),
)


def main():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for url, expected, name in INPUTS:
            archive = root / name
            with urlopen(url, timeout=60) as response, archive.open('xb') as output:
                if not response.url.startswith('https://'):
                    raise ValueError('Non-HTTPS fixture input')
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() != expected:
                raise ValueError('Fixture input digest mismatch')
        runtime = Path('/opt/microsoft/powershell/7')
        runtime.mkdir(parents=True)
        with tarfile.open(root / 'powershell.tar.gz') as archive:
            archive.extractall(runtime, filter='data')
        (runtime / 'pwsh').chmod(0o755)
        module = Path('/opt/pester/Modules/Pester/6.2.0')
        module.mkdir(parents=True)
        with zipfile.ZipFile(root / 'pester.nupkg') as archive:
            for name in archive.namelist():
                path = Path(name)
                if path.is_absolute() or '..' in path.parts or '\\' in name:
                    raise ValueError('Unsafe fixture archive')
            archive.extractall(module)
        subprocess.run([str(runtime / 'pwsh'), '-NoLogo', '-NoProfile', '-NonInteractive', '-Command',
                        "if ($PSVersionTable.PSVersion.ToString() -cne '7.6.6') { throw 'runtime' }; "
                        "Import-Module /opt/pester/Modules/Pester/6.2.0/Pester.psd1 -RequiredVersion 6.2.0 -ErrorAction Stop; "
                        "if ((Get-Module Pester).Version.ToString() -cne '6.2.0') { throw 'module' }"],
                       check=True, timeout=30)


if __name__ == '__main__':
    main()
