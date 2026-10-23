"""Audit downloaded setup/source assets and write SHA256SUMS.txt."""
import hashlib
from pathlib import Path, PurePosixPath
import struct
import sys
import tarfile
import zipfile

root = Path(sys.argv[1]).resolve()
files = sorted(path for path in root.rglob('*') if path.is_file() and path.suffix in {'.zip', '.exe', '.gz'})
assert len(files) == 8, [path.name for path in files]
assert len({path.name for path in files}) == len(files)
checksums = []
for path in files:
    if path.name.endswith('-source.zip'):
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                item = PurePosixPath(name)
                assert not item.is_absolute() and '..' not in item.parts, name
                assert not set(item.parts) & {'generated', 'captures', 'private', 'ghidra', 'savestates'}, name
                assert item.suffix.lower() not in {'.nes', '.bin', '.exe', '.dll', '.obj', '.pdb', '.sav', '.state', '.srm', '.png', '.wav'}, name
            assert any(name.endswith('/prepare-engine.ps1') for name in archive.namelist())
            assert any(name.endswith('/build.sh') for name in archive.namelist())
    elif path.suffix == '.exe':
        data = path.read_bytes()
        assert data[:2] == b'MZ'
        offset = struct.unpack_from('<I', data, 0x3c)[0]
        assert data[offset:offset+4] == b'PE\0\0'
        assert struct.unpack_from('<H', data, offset + 4)[0] == 0x8664
    elif path.suffix == '.gz':
        with tarfile.open(path) as archive:
            members = archive.getmembers()
            assert [member.name for member in members] == ['RCRness-Setup']
            assert members[0].mode & 0o111
            data = archive.extractfile(members[0]).read(20)
            assert data[:5] == b'\x7fELF\x02' and struct.unpack_from('<H', data, 18)[0] == 62
    else:
        with zipfile.ZipFile(path) as archive:
            binary = 'RCRness-Setup.app/Contents/MacOS/RCRness-Setup'
            info = archive.getinfo(binary)
            assert (info.external_attr >> 16) & 0o111
            data = archive.read(binary)[:8]
            assert data[:4] == bytes.fromhex('cffaedfe')
            expected_cpu = 0x100000c if 'arm64' in path.name else 0x1000007
            assert struct.unpack_from('<I', data, 4)[0] == expected_cpu
            assert not any('generated/rcr_' in name or name.lower().endswith(('.nes', '.sav', '.state')) for name in archive.namelist())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    checksums.append(f'{digest}  {path.name}')
    print('PASS', path.name)
(root / 'SHA256SUMS.txt').write_text('\n'.join(checksums) + '\n', encoding='utf-8')
