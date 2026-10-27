"""Private regressions using the reported carried-enemy and ghost-coin saves.

Requires Pillow, a trace build and the exact owner ROM. Never distribute the
input states or output. Uses controller input only; guest RAM is not modified.
"""
import argparse
import json
from pathlib import Path
from PIL import Image
from validate_widescreen import Session


def run(args):
    root=args.output.resolve(); root.mkdir(parents=True,exist_ok=True)
    result={}
    for name,state in [('carry',args.carry_state),('coin',args.coin_state)]:
        result[name]={}
        for mode in ('off','16:9','32:9'):
            output=root/(name+'-'+mode.replace(':','-'));output.mkdir(exist_ok=True)
            game=Session(args.exe.resolve(),args.rom.resolve(),state.resolve(),output)
            try:
                game.cmd('rcr_aspect_'+mode);game.cmd('set_input',buttons='00');game.advance(4)
                game.cmd('set_input',buttons='10');game.advance(2)
                game.cmd('set_input',buttons='00');game.advance(4)
                status=game.cmd('rcr_widescreen');game.shot('resumed')
                x=int.from_bytes(game.ram(0x83,1)+game.ram(0x8c,1),'little')
                camera=int.from_bytes(game.ram(0xdc,1)+game.ram(0xdd,1),'little')-game.ram(0x3b,1)[0]
                # Compare the same world-space carried-person rectangle, not
                # viewport pixels or the ROM's unrelated scenery outside it.
                origin=camera if mode=='off' else status['view']
                image=Image.open(output/'resumed.png').convert('RGBA')
                crop=image.crop((x-origin-32,125,x-origin+32,180))
                entry={'status':status,'crop_hex':crop.tobytes().hex()}
                if name=='coin' and mode!='off':
                    assert status['sprites'][3]==0, 'Skipped coin retained a cached packet'
                # A new pause must retain this completed list across DMA and
                # a new-format state must restore its displayed image exactly.
                game.cmd('set_input',buttons='10');game.advance(2)
                game.cmd('set_input',buttons='00');game.advance(12)
                paused=game.shot('paused-a');game.advance(40)
                assert game.shot('paused-b')==paused, 'Paused sprite list changed'
                saved=output/'fixed.state';game.cmd('save_state',path=str(saved))
                game.advance(12);a=game.shot('replay-a')
                game.cmd('load_state',path=str(saved));game.advance(12)
                assert game.shot('replay-b')==a, 'Fixed sprite state replay changed'
                entry['dispatch']=game.cmd('dispatch_miss_info')
                entry['interpreter']=game.cmd('interpreter_stats')
                assert entry['dispatch']['total_misses']==0
                assert entry['interpreter']['watchdog_trips']==0
                result[name][mode]=entry
            finally:game.close()
        if name=='carry':
            reference=result[name]['off']['crop_hex']
            for mode in ('16:9','32:9'):
                assert result[name][mode]['crop_hex']==reference, 'Carried person differs from native: '+mode
        print(name+': native/wide, pause and state replay passed',flush=True)
    (root/'results.json').write_text(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('exe','rom','carry-state','coin-state','output'):
        p.add_argument('--'+flag,type=Path,required=True)
    run(p.parse_args())
