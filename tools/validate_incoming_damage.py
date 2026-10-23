"""Exercise natural enemy damage to idle Alex at the left edge and wide margin.

Positions are controlled prerequisites; player health, defense, damage flags
and enemy attack states are never written. The original AI chooses attacks.
The captured left-edge hit is replayed in native and wide views, then shifted
with every actor into the wide margin. Requires a trace build and a private
current-build starting-gameplay state. All processes are hidden and muted.
"""
import argparse
import json
from pathlib import Path
from validate_widescreen import Session


def run(args):
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    capture=output/'capture';capture.mkdir(exist_ok=True)
    game=Session(args.exe.resolve(),args.rom.resolve(),args.state.resolve(),capture)
    trace=[];hit_state=capture/'before-hit.state'
    try:
        game.cmd('rcr_aspect_16:9');game.cmd('set_input',buttons='00')
        initial_hp=game.ram(0x4bf,1)[0]
        assert initial_hp>0
        for tick in range(240):
            anim=game.ram(0xd5,1)[0]
            px=64+(-16 if anim&128 else 16)
            for addr,value in [(0x85,64),(0x8e,0),(0xa0,92),(0xbb,0),
                               (0x83,px),(0x8c,0),(0x9e,92),(0xb9,0)]:
                game.write(addr,value)
            game.cmd('save_state',path=str(hit_state))
            game.advance(4);hp=game.ram(0x4bf,1)[0]
            trace.append({'elapsed':(tick+1)*4,'player_x':px,'hp':hp,'enemy_anim':anim})
            if hp<initial_hp:
                assert px<64, 'Hit did not exercise the left-edge clipping regression'
                game.shot('damage');break
        else: raise AssertionError('No natural enemy hit reached idle Alex')
        expected_hp=hp
    finally: game.close()
    results={'setup':'Position cheats only; original AI, attacks and damage',
             'capture':trace,'cases':[]}
    for mode,shift in [('off',0),('16:9',0),('21:9',0),('32:9',0),('off',352),('32:9',352)]:
        folder=output/(mode.replace(':','-')+f'-shift-{shift}');folder.mkdir(exist_ok=True)
        game=Session(args.exe.resolve(),args.rom.resolve(),hit_state,folder)
        try:
            game.cmd('rcr_aspect_'+mode);game.cmd('set_input',buttons='00')
            if shift:
                for obj in range(7):
                    x=int.from_bytes(game.ram(0x83+obj,1)+game.ram(0x8c+obj,1),'little')+shift
                    game.write(0x83+obj,x&255);game.write(0x8c+obj,(x>>8)&255)
            before=game.ram(0x4bf,1)[0];game.advance(4);after=game.ram(0x4bf,1)[0]
            expected=initial_hp if mode=='off' and shift else expected_hp
            assert before==initial_hp and after==expected,(mode,shift,before,after,expected)
            result={'mode':mode,'player_x':48+shift,'hp_before':before,'hp_after':after,
                    'image_sha256':game.shot('hit'),'status':game.cmd('rcr_widescreen'),
                    'dispatch':game.cmd('dispatch_miss_info')}
            assert result['dispatch']['total_misses']==0
            results['cases'].append(result)
            print(mode,'X',48+shift,'HP',before,'->',after,flush=True)
        finally:game.close()
    (output/'results.json').write_text(json.dumps(results,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['exe','rom','state','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    run(parser.parse_args())
