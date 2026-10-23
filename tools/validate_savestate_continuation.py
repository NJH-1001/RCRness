"""Private save-state continuation regression; never package its output."""
import argparse
import hashlib
import json
from pathlib import Path
from validate_widescreen import Session


def snapshot(game):
    ram = b''.join(game.ram(i, 256) for i in range(0, 2048, 256))
    (game.output / 'final.ram').write_bytes(ram)
    return {'ram_sha256': hashlib.sha256(ram).hexdigest(),
            'image_sha256': game.shot('final'),
            'frame': game.cmd('frame')['frame'],
            'dispatch': game.cmd('dispatch_miss_info'),
            'interpreter': game.cmd('interpreter_stats')}


def run(args):
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    for capture_frame in (1400, 1983):
        folder = args.output / str(capture_frame)
        folder.mkdir(exist_ok=True)
        state = folder.resolve() / 'checkpoint.state'
        game = Session(args.exe.resolve(), args.rom.resolve(), None, folder.resolve())
        try:
            # Same unmodified controller sequence used by the gameplay audit.
            for delay in (300, 600, 180, 300):
                target = game.cmd('frame')['frame'] + delay
                if target >= capture_frame:
                    game.advance(capture_frame - game.cmd('frame')['frame'])
                    break
                game.advance(delay)
                game.cmd('set_input', buttons='10')
                game.advance(3)
                game.cmd('set_input', buttons='00')
            if game.cmd('frame')['frame'] < capture_frame:
                game.advance(capture_frame - game.cmd('frame')['frame'])
            game.cmd('save_state', path=str(state))
            for _ in range(args.frames // 300): game.advance(300)
            baseline = snapshot(game)
        finally:
            game.close()
        replay = folder / 'replay'
        replay.mkdir(exist_ok=True)
        game = Session(args.exe.resolve(), args.rom.resolve(), state, replay.resolve())
        try:
            for _ in range(args.frames // 300): game.advance(300)
            restored = snapshot(game)
            assert baseline['frame'] == restored['frame'], (baseline, restored)
        finally:
            game.close()
        for log in folder.rglob('runtime.stderr.log'):
            assert 'WATCHDOG' not in log.read_text(errors='replace'), str(log)
        results.append(dict(capture_frame=capture_frame, baseline=baseline, restored=restored))
        print(f'Frame {capture_frame}: {args.frames} frames completed; image match={baseline["image_sha256"] == restored["image_sha256"]}', flush=True)
    (args.output / 'results.json').write_text(json.dumps(results, indent=2))
    for case in results:
        assert case['baseline']['ram_sha256'] == case['restored']['ram_sha256'], case
        assert case['baseline']['image_sha256'] == case['restored']['image_sha256'], case


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('exe', 'rom', 'output'): parser.add_argument('--' + flag, type=Path, required=True)
    parser.add_argument('--frames', type=int, default=6000)
    options = parser.parse_args()
    assert options.frames >= 6000 and options.frames % 300 == 0
    run(options)
