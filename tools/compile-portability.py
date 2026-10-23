"""Compile/link the real host with original synthetic 6502 input in CI.

This is a compiler portability check, not a River City Ransom gameplay test.
No commercial game data is available to CI or included in release artifacts.
"""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
work = root / 'build-portability'
work.mkdir(exist_ok=True)
rom = bytearray(b'NES\x1a' + bytes([8, 16, 0x40, 0]) + bytes(8))
rom += bytes([0xea]) * (128 * 1024) + bytes(128 * 1024)
fixed = 16 + 7 * 0x4000
rom[fixed:fixed + 4] = bytes([0x4c, 0x00, 0xc0, 0x40])
rom[fixed + 0x3ffa:fixed + 0x4000] = bytes([3, 0xc0, 0, 0xc0, 3, 0xc0])
(work / 'synthetic.nes').write_bytes(rom)
(work / 'synthetic.toml').write_text('[game]\noutput_prefix="rcr"\ndisable_ptr_scan=true\npush_all_jsr=true\n[functions]\nfixed=[0xC000,0xC003]\n')


def run(*args):
    subprocess.run(list(map(str, args)), cwd=root, check=True)


engine = root / 'nesrecomp'
patch = root / 'engine-patches/adaptive-renderer.patch'
if subprocess.run(['git', '-C', str(engine), 'apply', '--reverse', '--check', str(patch)], capture_output=True).returncode:
    run('git', '-C', engine, 'apply', patch)
run('cmake', '-S', engine / 'recompiler', '-B', work / 'recompiler', '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release')
run('cmake', '--build', work / 'recompiler', '--parallel', '2')
run(work / 'recompiler/NESRecomp', work / 'synthetic.nes', '--game', work / 'synthetic.toml')
run('cmake', '-S', root, '-B', work / 'game', '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
    '-DNESRECOMP_ENABLE_TRACE=OFF', '-DNESRECOMP_ENABLE_STACK_TRACKING=OFF', '-DNESRECOMP_ENABLE_POSTMORTEM_RINGS=OFF')
run('cmake', '--build', work / 'game', '--parallel', '2')
