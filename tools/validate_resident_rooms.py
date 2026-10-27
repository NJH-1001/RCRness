"""Private resident-background regressions; requires entrance-audit states.

No ROM, states or captured graphics may be distributed with the source.
"""
import argparse
import json
from pathlib import Path
from validate_widescreen import Session


def run(args):
    out=args.output.resolve(); out.mkdir(parents=True,exist_ok=True)
    paired=(1,4,5,8,9,10,11,15,16,18,19,20,22,27,28,34)
    single=(12,13,14,23,26,33)
    results={'rooms':[], 'movement':{}}
    game=Session(args.exe.resolve(),args.rom.resolve(),None,out)
    try:
        for room in paired+single:
            game.cmd('load_state',path=str((args.states/f'entry-{room:02d}.state').resolve()))
            game.cmd('set_input',buttons='00')
            for mode in ('16:9','32:9'):
                game.cmd('rcr_aspect_'+mode); game.advance(4)
                status=game.cmd('rcr_widescreen')
                assert status['room']==room and status['pages']==(2 if room in paired else 0),status
                assert status['decode_errors']==0,status
                if room in paired:
                    assert status['terrain_pixels']==38400 and status['terrain_diffs']==0,status
                game.shot(f'room-{room:02x}-{mode.replace(":","-")}')
                results['rooms'].append(status)
        # Same natural rightward walk, original movement/camera in both modes.
        for mode in ('off','32:9'):
            game.cmd('load_state',path=str((args.states/'entry-04.state').resolve()))
            game.cmd('rcr_aspect_'+mode);game.cmd('set_input',buttons='01')
            trace=[]
            for _ in range(5):
                game.advance(60)
                trace.append({'x':game.ram(0x83,1).hex()+game.ram(0x8c,1).hex(),
                              'camera':game.ram(0xdc,2).hex()})
            results['movement'][mode]=trace
            game.cmd('set_input',buttons='00'); game.advance(4)
            game.shot('walk-'+mode.replace(':','-'))
        assert results['movement']['off']==results['movement']['32:9'],results['movement']
        assert int.from_bytes(bytes.fromhex(results['movement']['off'][-1]['x']),'little')>256
        # Park pause must retain the wide world and restore exactly.
        game.cmd('set_input',buttons='10');game.advance(2)
        game.cmd('set_input',buttons='00');game.advance(60)
        assert game.ram(0x3f,1)[0]&0x20, 'Native Start did not pause'
        a=game.shot('pause-a');game.advance(20)
        assert game.shot('pause-b')==a
        state=out/'paused.state';game.cmd('save_state',path=str(state))
        game.advance(12);a=game.shot('replay-a')
        game.cmd('load_state',path=str(state));game.advance(12)
        assert game.shot('replay-b')==a
        results['dispatch']=game.cmd('dispatch_miss_info')
        assert results['dispatch']['total_misses']==0,results['dispatch']
        results['interpreter']=game.cmd('interpreter_stats')
        assert results['interpreter']['watchdog_trips']==0,results['interpreter']
    finally: game.close()
    (out/'results.json').write_text(json.dumps(results,indent=2))
    print('44 room/aspect cases, native movement, pause and replay passed')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('exe','rom','states','output'):p.add_argument('--'+name,type=Path,required=True)
    run(p.parse_args())
