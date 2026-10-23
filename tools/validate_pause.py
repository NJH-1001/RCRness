"""Check wide pause scenes/panels, live paused resizing and state replay.

Requires the verified owner ROM, a trace build and a current-build gameplay
state in a scrolling room. Every test window is hidden and audio is muted.
Inspect the saved screenshots to verify native UI text/cursor placement.
"""
import argparse
import json
import math
from pathlib import Path
from validate_widescreen import Session


def press(game, buttons, frames=6):
    # Explicit release prevents physical keyboard input from entering this test.
    game.cmd('set_input', buttons=f'{buttons:02x}')
    game.advance(frames)
    game.cmd('set_input', buttons='00')
    game.advance(6)


def run(args):
    output=args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    game=Session(args.exe.resolve(),args.rom.resolve(),args.state.resolve(),output,
                 window=args.window,crt=args.crt)
    results={'geometry':[], 'menus':[], 'save_load':{}}
    try:
        game.cmd('set_input', buttons='00');game.advance(12)
        base=output/'gameplay.state';game.cmd('save_state',path=str(base))
        for mode,width in [('16:9',426),('21:9',560),('32:9',854)]:
            game.cmd('load_state',path=str(base));game.cmd('set_input',buttons='00')
            game.cmd('rcr_aspect_'+mode);game.advance(4)
            press(game,0x10);game.advance(60)
            assert game.ram(0x3f,1)[0]&0x20, 'Native Start did not pause'
            first=game.cmd('rcr_widescreen');game.advance(12)
            last=game.cmd('rcr_widescreen')
            assert last['width']==width,last
            assert last['pause_panel']==0,last
            assert last['wide_frames']>first['wide_frames'],last
            last.update(mode=mode, image_sha256=game.shot('pause-'+mode.replace(':','-')))
            results['geometry'].append(last)
        paused=output/'paused.state';game.cmd('save_state',path=str(paused))
        game.advance(40);image_a=game.shot('paused-replay-a');ram_a=game.ram(0,256)
        game.cmd('load_state',path=str(paused));game.advance(40)
        image_b=game.shot('paused-replay-b');ram_b=game.ram(0,256)
        assert image_a==image_b and ram_a==ram_b
        results['save_load']={'image_equal':True,'ram_equal':True,'sha256':image_a}
        for menu in range(5):
            game.cmd('load_state',path=str(paused));game.cmd('set_input',buttons='00')
            for _ in range(8):
                current=game.ram(0x6d0,1)[0]
                if current==menu: break
                press(game,2 if current>menu else 1)
            assert game.ram(0x6d0,1)[0]==menu, 'Native menu navigation failed'
            press(game,0x80);game.advance(180)
            before=game.cmd('rcr_widescreen')['wide_frames'];game.advance(12)
            status=game.cmd('rcr_widescreen')
            assert status['wide_frames']>before,status
            assert status['pause_panel']==1,status
            status.update(menu=menu,flags=game.ram(0x35,16).hex(),
                          image_sha256=game.shot(f'menu-{menu}'))
            panel_state=output/f'menu-{menu}.state'
            game.cmd('save_state',path=str(panel_state))
            game.advance(12);panel_a=game.shot(f'menu-{menu}-replay-a')
            game.cmd('load_state',path=str(panel_state));game.advance(12)
            panel_b=game.shot(f'menu-{menu}-replay-b')
            assert game.cmd('rcr_widescreen')['pause_panel']==1
            assert panel_a==panel_b,(menu,panel_a,panel_b)
            status['state_replay_equal']=True
            # Native panels use different controls to confirm/cancel/return.
            for button in [0x40,0x10,0x80,0x20]:
                press(game,button,12);game.advance(120)
                if not game.cmd('rcr_widescreen')['pause_panel']: break
            assert game.cmd('rcr_widescreen')['pause_panel']==0, 'Native submenu did not return'
            assert game.ram(0x40,1)[0], 'Native submenu did not return to gameplay mode'
            status['returned']=True
            game.shot(f'menu-{menu}-return')
            results['menus'].append(status)
        game.cmd('load_state',path=str(paused));game.cmd('set_input',buttons='00')
        game.cmd('rcr_aspect_fit')
        for w,h in [(1280,720),(2560,1080),(1920,540),(720,1280)]:
            response=game.cmd(f'rcr_window_{w}x{h}');game.advance(12)
            status=game.cmd('rcr_widescreen')
            expected=2*math.floor(240*max(256/240,min(w/h,32/9))/2+.5)
            assert status['width']==expected,status
            status.update(window=[w,h],actual_window=response['window'],
                          image_sha256=game.shot(f'paused-fit-{w}x{h}'))
            results['geometry'].append(status)
        game.cmd('rcr_window_1280x720');game.advance(6)
        press(game,0x10);game.advance(48)
        assert not(game.ram(0x3f,1)[0]&0x20), 'Native Start did not resume'
        results['resumed']=game.cmd('rcr_widescreen')
        assert results['resumed']['width']==426
        game.shot('resumed')
        results['dispatch']=game.cmd('dispatch_miss_info')
        assert results['dispatch']['total_misses']==0
    finally: game.close()
    (output/'results.json').write_text(json.dumps(results,indent=2))
    print(json.dumps({'geometry':len(results['geometry']),'menus':len(results['menus']),
                      'save_load':results['save_load'],'output':str(output)},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['exe','rom','state','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--window',action='store_true')
    parser.add_argument('--crt',action='store_true')
    run(parser.parse_args())
