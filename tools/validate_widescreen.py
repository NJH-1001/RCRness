"""Private runtime audit. Requires a current-build gameplay state, never ships ROM data.

TEMP/TMP are redirected to the selected private output directory.
Every game process is hidden and uses dummy audio.
The entrance audit bypasses traversal/progression prerequisites; it does NOT
establish boss defeat, secret-shop access or end-to-end completion.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import time


class Session:
    def __init__(self, exe, rom, state, output, window=False, crt=False):
        self.output=output
        self.seq=0
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1',0))
            port=reservation.getsockname()[1]
        env=os.environ.copy()
        env.update(TEMP=str(output),TMP=str(output),SDL_AUDIODRIVER='dummy',
                   NESRECOMP_DOT_PPU='0',NESRECOMP_START_PAUSED='1',
                   NESRECOMP_DEBUG_PORT=str(port),NESRECOMP_TEST_HIDDEN='1')
        if not window: env['SDL_VIDEODRIVER']='dummy'
        self.out=(output/'runtime.stdout.log').open('w')
        self.err=(output/'runtime.stderr.log').open('w')
        args=[str(exe),str(rom),'--crt-filter' if crt else '--no-crt-filter']
        if state is not None: args+=['--loadstate',str(state)]
        if not window: args+=['--smoke','1000000']
        self.process=subprocess.Popen(args,cwd=output,env=env,stdout=self.out,
            stderr=self.err,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        for _ in range(200):
            try:
                self.socket=socket.create_connection(('127.0.0.1',port),timeout=1)
                break
            except OSError:
                if self.process.poll() is not None: raise RuntimeError('Game exited during startup')
                time.sleep(.05)
        else: raise TimeoutError('Debug connection')
        self.socket.settimeout(30)
        self.file=self.socket.makefile('rb')

    def cmd(self,name,**fields):
        self.seq+=1
        self.socket.sendall((json.dumps(dict(cmd=name,id=self.seq,**fields))+'\n').encode())
        while True:
            line=self.file.readline()
            if not line: raise RuntimeError('Debug connection closed')
            result=json.loads(line)
            if result.get('id')==self.seq:
                if not result.get('ok'): raise RuntimeError(result)
                return result

    def advance(self,count):
        target=self.cmd('frame')['frame']+count
        self.cmd('run_to_frame',frame=target)
        deadline=time.monotonic()+45
        while self.cmd('frame')['frame']<target:
            if time.monotonic()>deadline: raise TimeoutError(f'Frame {target}')
            time.sleep(.01)
        return target

    def write(self,addr,value): self.cmd('write_ram',addr=hex(addr),val=hex(value))
    def ram(self,addr,count): return bytes.fromhex(self.cmd('read_ram',addr=hex(addr),len=count)['hex'])
    def shot(self,name):
        path=self.output/(name+'.png')
        self.cmd('screenshot',path=str(path))
        return hashlib.sha256(path.read_bytes()).hexdigest()
    def close(self):
        try:
            if self.process.poll() is None:
                try: self.cmd('quit')
                except OSError: pass
                self.process.wait(timeout=10)
        finally:
            if self.process.poll() is None:
                self.process.terminate(); self.process.wait(timeout=10)
            self.out.close(); self.err.close()


def run(args):
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    rom=args.rom.read_bytes()
    if hashlib.sha256(rom).hexdigest()!='b95f8def04c0012604b7cc68cf4ed8f49b2dfe4beda6182051de4b2423bea7b1':
        raise ValueError('Exact USA ROM required')
    def rb(a): return rom[16+0x4000+a-0x8000]
    # A43D: 73 five-byte entrance records, followed by camera/player data.
    entrances=[rb(0xa43d+i*5) for i in range(73)]
    assert set(entrances)==set(range(35))
    result={'scope':'Entrance loading/render/AI audit; prerequisites bypassed',
            'geometry':[],'entrances':[],'save_load':{},'checks':[]}
    game=Session(args.exe.resolve(),args.rom.resolve(),args.state.resolve(),output,args.window,args.crt)
    try:
        game.advance(12)
        base=output/'base.state'
        game.cmd('save_state',path=str(base))
        for mode,width in [('16:9',426),('21:9',560),('32:9',854),('off',256)]:
            game.cmd('rcr_aspect_'+mode)
            game.advance(4)
            status=game.cmd('rcr_widescreen')
            assert status['width']==width,status
            status['mode']=mode
            status['image_sha256']=game.shot('aspect-'+mode.replace(':','-'))
            result['geometry'].append(status)
        game.cmd('rcr_aspect_fit')
        for w,h in [(1280,720),(2560,1080),(1920,540),(720,1280),(1000,600)]:
            response=game.cmd(f'rcr_window_{w}x{h}')
            game.advance(5)
            status=game.cmd('rcr_widescreen')
            expected=2*math.floor(240*max(256/240,min(w/h,32/9))/2+.5)
            assert status['width']==expected,(w,h,status,expected)
            status.update(window=[w,h],actual_window=response['window'])
            status['image_sha256']=game.shot(f'fit-{w}x{h}')
            result['geometry'].append(status)
        if not args.window:
            game.cmd('rcr_aspect_32:9')
            for entry,room in enumerate(entrances):
                game.cmd('load_state',path=str(base))
                game.write(0x46,entry)
                game.write(0x36,0x80);game.write(0x37,0x80);game.write(0x3e,4)
                trace=[]
                for tick in range(24):
                    game.advance(12)
                    flags=game.ram(0x35,0x0e)
                    trace.append({'elapsed':(tick+1)*12,'room':flags[13],
                                  'transition':flags[1],'fade':flags[9]})
                    if flags[13]==room and not flags[1] and not(flags[9]&2): break
                status=game.cmd('rcr_widescreen')
                ram=game.ram(0x35,0x26)
                status.update(entry=entry,expected_room=room,actual_room=ram[0x42-0x35],
                              active=list(game.ram(0x48,7)),trace=trace)
                status['room_load']='passed' if any(t['room']==room for t in trace) else 'failed'
                assert status['room_load']=='passed',status
                assert status['decode_errors']==0,status
                status['image_sha256']=game.shot(f'entry-{entry:02d}-room-{room:02x}')
                before=game.ram(0x83,27)
                game.advance(36)
                after=game.ram(0x83,27)
                status['actor_positions_changed']=before!=after
                game.cmd('save_state',path=str(output/f'entry-{entry:02d}.state'))
                result['entrances'].append(status)
                if entry%10==0: print(f'Audited entrance {entry}/72, room {room:02x}',flush=True)
                (output/'results.json').write_text(json.dumps(result,indent=2))
            game.cmd('load_state',path=str(base))
            game.advance(20)
            replay=output/'replay.state'
            game.cmd('save_state',path=str(replay))
            game.advance(40); first=game.shot('replay-a'); ram_a=game.ram(0,256)
            game.cmd('load_state',path=str(replay))
            game.advance(40); second=game.shot('replay-b'); ram_b=game.ram(0,256)
            assert first==second and ram_a==ram_b,(first,second)
            result['save_load']={'image_equal':True,'ram_equal':True,'sha256':first}
        result['final']=game.cmd('rcr_widescreen')
        result['dispatch']=game.cmd('dispatch_miss_info')
    finally: game.close()
    (output/'results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'entrances':len(result['entrances']),'geometry':len(result['geometry']),
                      'save_load':result['save_load'],'output':str(output)},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ['exe','rom','state','output']: p.add_argument('--'+flag,type=Path,required=True)
    p.add_argument('--window',action='store_true',help='Exercise an actual hidden SDL window and resizes')
    p.add_argument('--crt',action='store_true',help='Exercise CRT texture resizing as well')
    run(p.parse_args())
