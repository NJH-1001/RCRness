"""Create an audited source kit from Git's tracked files only."""
import pathlib
import subprocess
import sys
import zipfile

root = pathlib.Path(__file__).resolve().parents[1]
output = pathlib.Path(sys.argv[1]).resolve()
paths = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z']).decode().split('\0')
forbidden = {'.nes', '.bin', '.sav', '.srm', '.state', '.exe', '.dll', '.pdb', '.obj', '.zip', '.png', '.wav'}
output.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
    for name in paths:
        if not name or name == 'nesrecomp':
            continue
        path = pathlib.PurePosixPath(name)
        if path.suffix.lower() in forbidden or any(
            part in {'generated', 'private', 'captures', 'savestates', 'ghidra'}
            or part.startswith(('build', 'dist-', 'sprite_trace_')) for part in path.parts[:-1]
        ):
            raise SystemExit(f'Forbidden public source: {name}')
        archive.write(root / name, 'RCRness-source/' + name)
print(output)
