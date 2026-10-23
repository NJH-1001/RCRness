"""Exercise original hit/damage logic beyond x=255 using a protected player.
Player/enemy positions and player attack stats are cheats; enemy health,
defeat flags, gang counters and rewards are never written after setup.
"""
import argparse
import json
from pathlib import Path
from validate_widescreen import Session


def run(args):
    root=args.output.resolve(); root.mkdir(parents=True,exist_ok=True)
    results={}
    for mode in ['off','32:9']:
        folder=root/mode.replace(':','-'); folder.mkdir(exist_ok=True)
        game=Session(args.exe.resolve(),args.rom.resolve(),args.state.resolve(),folder)
        try:
            game.advance(12);game.cmd('rcr_aspect_'+mode);game.advance(4)
            game.write(0x4c1,63)
            game.write(0x49f,63);game.write(0x4b7,63);game.write(0x6f,0)
            trace=[]
            for tick in range(96):
                # Keep the test outside the old camera while original attack,
                # contact, damage, knockback and death code continue to run.
                for a,v in [(0xdc,0),(0xdd,0),(0x83,0x90),(0x8c,1),
                            (0x85,0xa0),(0x8e,1),(0x9e,92),(0xa0,92),(0x4bf,63)]:
                    game.write(a,v)
                game.cmd('set_input',buttons='80' if tick%16<2 else '00')
                game.advance(1)
                trace.append({'tick':tick,'hp':game.ram(0x4c1,1)[0],
                              'player_anim':game.ram(0xd3,1)[0],
                              'enemy_state':game.ram(0x4f1,4).hex(),
                              'gang_counter':game.ram(0x4e1,1)[0]})
            game.shot('fight')
            results[mode]={'trace':trace,'status':game.cmd('rcr_widescreen'),
                           'misses':game.cmd('dispatch_miss_info')}
            health={t['hp'] for t in trace}
            assert health=={63} if mode=='off' else 0 in health,health
            assert results[mode]['misses']['total_misses']==0
            print(mode,'health',sorted(health),flush=True)
            if mode!='off':
                game.cmd('set_input',buttons='00')
                game.advance(180)
                game.shot('after-defeat')
                results[mode]['after_defeat']={'health':list(game.ram(0x4c1,2)),
                     'actors':list(game.ram(0xcb,7)),'active':list(game.ram(0x48,7)),
                     'gang_counter':game.ram(0x4e1,1)[0],
                     'status':game.cmd('rcr_widescreen')}
                game.cmd('save_state',path=str(folder/'after-defeat.state'))
                money_before=game.ram(0x4c7,3)
                count_before=game.ram(0x4e1,1)[0]
                for _ in range(120):
                    if game.ram(0xcd,1)[0]==16:
                        game.write(0x83,game.ram(0x85,1)[0]);game.write(0x8c,game.ram(0x8e,1)[0])
                        game.write(0x9e,game.ram(0xa0,1)[0]);game.write(0xb9,0)
                    game.write(0x4bf,63)
                    game.advance(1)
                game.shot('replacement-wave')
                results[mode]['replacement_wave']={
                    'money_before':money_before.hex(),'money_after':game.ram(0x4c7,3).hex(),
                    'count_before':count_before,'count_after':game.ram(0x4e1,1)[0],
                    'actor_type':game.ram(0xcd,1)[0],'status':game.cmd('rcr_widescreen')}
                assert game.ram(0x4c7,3)!=money_before,'Coin reward was not collected'
                assert game.ram(0x4e1,1)[0]>count_before,'Original replacement wave did not spawn'
            # Exercise the special actor's pending-visibility prerequisite.
            # Only the pending setup state is supplied; original code must
            # set its visible bit and any gang-script flags itself.
            game.cmd('load_state',path=str(args.state.resolve()))
            game.cmd('rcr_aspect_'+mode);game.advance(4)
            for a,v in [(0xdc,0),(0xdd,0),(0x85,0x90),(0x8e,1),(0x4f3,0x40)]:game.write(a,v)
            game.advance(4)
            pending=game.ram(0x4f3,1)[0]
            results[mode]['pending_activation']={'state':pending,'status':game.cmd('rcr_widescreen')}
            assert pending==0x40 if mode=='off' else (pending&0x20)!=0,pending
        finally:game.close()
    (root/'results.json').write_text(json.dumps(results,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ['exe','rom','state','output']:p.add_argument('--'+flag,type=Path,required=True)
    run(p.parse_args())
