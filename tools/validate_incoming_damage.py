"""Exercise natural enemy damage to idle Alex at the left edge and wide margin.

Capture a natural idle-player hit from a fresh boot, without RAM writes.
Replay that same left-edge hit in native and wide views, then translate every
actor into the wide margin. Only the translated replay writes positions;
health, defense, attack states and damage flags are never written.
Requires a trace build and the exact owner ROM. Optional --state starts from a
current-build gameplay snapshot; --hit-state replays an already captured hit.
All processes are hidden and muted. Snapshots and images remain private.
"""
import argparse
import hashlib
import json
from pathlib import Path
from validate_widescreen import Session


def player_x(game):
    return int.from_bytes(game.ram(0x83,1)+game.ram(0x8c,1),'little')


def boot_to_gameplay(game):
    # Original menus, using controller input only; no progression/state pokes.
    for delay in (300,600,180,300):
        game.advance(delay)
        game.cmd('set_input',buttons='10');game.advance(3)
        game.cmd('set_input',buttons='00')
    game.advance(600)


def run(args):
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    capture=output/'capture';capture.mkdir(exist_ok=True)
    if hashlib.sha256(args.rom.read_bytes()).hexdigest()!='b95f8def04c0012604b7cc68cf4ed8f49b2dfe4beda6182051de4b2423bea7b1':
        raise ValueError('Exact USA ROM required')
    trace=[]
    hit_state=args.hit_state.resolve() if args.hit_state else capture/'before-hit.state'
    results={'setup':'Natural idle-player capture; position writes only in translated replay',
             'capture':trace,'cases':[]}
    if not args.hit_state:
        state=args.state.resolve() if args.state else None
        game=Session(args.exe.resolve(),args.rom.resolve(),state,capture)
        try:
            game.cmd('rcr_aspect_16:9');game.cmd('set_input',buttons='00')
            if state is None: boot_to_gameplay(game)
            initial_hp=game.ram(0x4bf,1)[0]
            assert initial_hp>0, 'Snapshot must be initialized gameplay'
            assert player_x(game)==48, 'Capture requires Alex at starting X=48'
            for tick in range(args.max_frames//4):
                # Save BEFORE advancing, so every replay starts before the hit.
                before_x=player_x(game)
                game.cmd('save_state',path=str(hit_state))
                game.advance(4);hp=game.ram(0x4bf,1)[0]
                trace.append({'elapsed':(tick+1)*4,'player_x_before':before_x,
                              'player_x_after':player_x(game),'hp':hp})
                if hp<initial_hp:
                    assert before_x==48, 'Attack must start at the left edge'
                    game.shot('damage')
                    results['natural_hit']={'frame':game.cmd('frame')['frame'],
                        'hp_before':initial_hp,'hp_after':hp,
                        'dispatch':game.cmd('dispatch_miss_info')}
                    assert results['natural_hit']['dispatch']['total_misses']==0
                    break
            else: raise AssertionError('No natural left-edge hit within the capture window')
        finally: game.close()
    initial_hp=None;expected_hp=None
    for mode,shift in [('off',0),('16:9',0),('21:9',0),('32:9',0),('off',352),('32:9',352)]:
        folder=output/(mode.replace(':','-')+f'-shift-{shift}');folder.mkdir(exist_ok=True)
        game=Session(args.exe.resolve(),args.rom.resolve(),hit_state,folder)
        try:
            game.cmd('rcr_aspect_'+mode);game.cmd('set_input',buttons='00')
            assert player_x(game)==48, 'Captured hit must start at X=48'
            if shift:
                for obj in range(7):
                    x=int.from_bytes(game.ram(0x83+obj,1)+game.ram(0x8c+obj,1),'little')+shift
                    game.write(0x83+obj,x&255);game.write(0x8c+obj,(x>>8)&255)
            before=game.ram(0x4bf,1)[0];actual_x=player_x(game)
            game.advance(4);after=game.ram(0x4bf,1)[0]
            if initial_hp is None:
                initial_hp=before;expected_hp=after
                assert 0<after<before, 'Captured attack must damage Alex in native mode'
                if 'natural_hit' in results:
                    assert (before,after)==(results['natural_hit']['hp_before'],
                                            results['natural_hit']['hp_after'])
            expected=initial_hp if mode=='off' and shift else expected_hp
            assert before==initial_hp and after==expected,(mode,shift,before,after,expected)
            assert actual_x==48+shift,actual_x
            result={'mode':mode,'player_x':actual_x,'hp_before':before,'hp_after':after,
                    'image_sha256':game.shot('hit'),'status':game.cmd('rcr_widescreen'),
                    'dispatch':game.cmd('dispatch_miss_info')}
            assert result['dispatch']['total_misses']==0
            assert result['status']['width']=={'off':256,'16:9':426,'21:9':560,'32:9':854}[mode]
            results['cases'].append(result)
            print(mode,'X',48+shift,'HP',before,'->',after,flush=True)
        finally:game.close()
    (output/'results.json').write_text(json.dumps(results,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['exe','rom','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--state',type=Path,help='Optional current-build starting-gameplay state')
    parser.add_argument('--hit-state',type=Path,help='Private snapshot immediately before a known natural left-edge hit')
    parser.add_argument('--max-frames',type=int,default=6000,help='Fresh capture timeout in video frames')
    run(parser.parse_args())
