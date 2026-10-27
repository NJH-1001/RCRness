"""Private shop-transition regression using a current-build gameplay snapshot.

Sets the original game's shop-entry request flag and shop index, bypassing
walking/progression prerequisites. Does not establish purchases or completion.
Requires a trace build; never distribute the ROM, states, or captured output.
"""
import argparse
import json
from pathlib import Path
from validate_widescreen import Session


def run(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    game = Session(args.exe.resolve(), args.rom.resolve(), args.state.resolve(), output)
    result = {'scope': 'Original shop-entry dispatcher; traversal prerequisites bypassed'}
    try:
        game.cmd('set_input', buttons='00')
        game.advance(12)
        game.write(0x686, args.shop)
        # Ghidra bank2 $8BB0 checks $36 bit 6 in one-player mode.
        game.write(0x36, game.ram(0x36, 1)[0] | 0x40)
        game.write(0x37, game.ram(0x37, 1)[0] | 0x40)
        result['checkpoints'] = []
        for index in range(10):
            game.advance(60)
            result['checkpoints'].append({'frame': game.cmd('frame')['frame'],
                'shop_state': game.ram(0x686, 16).hex(),
                'image': game.shot(f'shop-{index:02d}')})
        result['dispatch'] = game.cmd('dispatch_miss_info')
        result['interpreter'] = game.cmd('interpreter_stats')
        result['registers'] = game.cmd('get_registers')
        assert result['dispatch']['total_misses'] == 0, result['dispatch']
        assert result['interpreter']['watchdog_trips'] == 0, result['interpreter']
        # Navigate the native prompt and let its state machine continue.
        for buttons in ('01', '02', '80', '40'):
            game.cmd('set_input', buttons=buttons)
            game.advance(6)
            game.cmd('set_input', buttons='00')
            game.advance(90)
        result['final_frame'] = game.cmd('frame')['frame']
        result['final_image'] = game.shot('shop-final')
        result['final_dispatch'] = game.cmd('dispatch_miss_info')
        assert result['final_dispatch']['total_misses'] == 0, result['final_dispatch']
    finally:
        (output / 'results.json').write_text(json.dumps(result, indent=2))
        game.close()
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('exe', 'rom', 'state', 'output'):
        parser.add_argument('--' + flag, type=Path, required=True)
    parser.add_argument('--shop', type=int, default=0)
    run(parser.parse_args())
