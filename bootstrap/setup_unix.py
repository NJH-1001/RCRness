"""ROM-free Linux/macOS setup host. Packaged on each OS with PyInstaller."""
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import zipfile

VERSION = '0.1.5'
ROM_HASH = 'b95f8def04c0012604b7cc68cf4ed8f49b2dfe4beda6182051de4b2423bea7b1'
PAYLOAD = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'source-kit.zip'


def audit_payload():
    with zipfile.ZipFile(PAYLOAD) as archive:
        names = archive.namelist()
        assert 'RCRness-source/build.sh' in names
        assert 'RCRness-source/engine-patches/adaptive-renderer.patch' in names
        for name in names:
            path = Path(name)
            assert not path.is_absolute() and '..' not in path.parts
            assert path.suffix.lower() not in {'.nes', '.bin', '.exe', '.dll', '.sav', '.srm', '.state', '.obj', '.pdb'}
            assert not set(path.parts) & {'generated', 'captures', 'private', 'ghidra'}


def data_root():
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/RCRness'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'RCRness'


def source_root():
    digest = hashlib.sha256(PAYLOAD.read_bytes()).hexdigest()[:12]
    return data_root() / ('source-v' + VERSION + '-' + digest) / 'RCRness-source'


def previous_build():
    candidates = list(data_root().glob('source-v*/RCRness-source/build-public/RCRness'))
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def run(command, log, cwd=None):
    log('$ ' + ' '.join(map(str, command)) + '\n')
    with subprocess.Popen(list(map(str, command)), cwd=cwd, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, errors='replace') as proc:
        for line in proc.stdout:
            log(line)
        if proc.wait():
            raise RuntimeError('Command failed. See the build log above.')


def dependencies(log):
    missing = [tool for tool in ('git', 'cmake', 'ninja', 'cc') if not shutil.which(tool)]
    if sys.platform == 'darwin':
        if subprocess.run(['xcode-select', '-p'], capture_output=True).returncode:
            subprocess.run(['xcode-select', '--install'])
            raise RuntimeError('Complete Apple Command Line Tools installation, then click Rebuild.')
        if not shutil.which('brew'):
            raise RuntimeError('Install Homebrew from https://brew.sh, then reopen Setup. It supplies CMake, Ninja and SDL2.')
        # Finder does not inherit the interactive shell PATH.
        run(['brew', 'install', 'cmake', 'ninja', 'sdl2'], log)
    elif shutil.which('apt-get'):
        sdl = subprocess.run(['dpkg-query', '-W', '-f=${Status}', 'libsdl2-dev'], capture_output=True, text=True)
        if missing or 'install ok installed' not in sdl.stdout:
            if not shutil.which('pkexec'):
                raise RuntimeError('Install dependencies in a terminal: sudo apt-get install build-essential git cmake ninja-build libsdl2-dev')
            run(['pkexec', 'apt-get', 'update'], log)
            run(['pkexec', 'apt-get', 'install', '-y', 'build-essential', 'git', 'cmake', 'ninja-build', 'libsdl2-dev'], log)
    elif missing:
        raise RuntimeError('Install a C compiler, Git, CMake, Ninja and SDL2 development files using your distribution package manager.')


def build(rom, log):
    rom = Path(rom).expanduser().resolve()
    if hashlib.sha256(rom.read_bytes()).hexdigest() != ROM_HASH:
        raise ValueError('Unsupported ROM. Select the original River City Ransom (USA) revision listed in README.md.')
    audit_payload()
    root = source_root()
    root.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(PAYLOAD) as archive:
        archive.extractall(root.parent)
    dependencies(log)
    run(['bash', root / 'build.sh', rom], log, cwd=root)
    (root / 'last-rom.json').write_text(json.dumps(str(rom)))
    return root / 'build-public/RCRness'


def play(executable):
    remembered = executable.parent.parent / 'last-rom.json'
    args = [str(executable)]
    if remembered.exists():
        args.append(json.loads(remembered.read_text()))
    subprocess.Popen(args, cwd=executable.parent, start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    if '--self-test' in sys.argv:
        audit_payload()
        print('ROM-free source payload verified; setup ' + VERSION)
        return
    # Homebrew locations for both Apple Silicon and Intel; keep existing PATH.
    os.environ['PATH'] = '/opt/homebrew/bin:/usr/local/bin:' + os.environ.get('PATH', '')
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext
    window = tk.Tk()
    window.title('RCRness Setup ' + VERSION)
    window.geometry('740x470')
    tk.Label(window, text='Build privately from your River City Ransom (USA) ROM.\n'
             'Linux may request permission to install build tools. macOS requires Homebrew.').pack(pady=12)
    buttons = tk.Frame(window)
    buttons.pack()
    events = queue.Queue()
    output = scrolledtext.ScrolledText(window, wrap=tk.WORD)
    output.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
    busy = False

    def worker(rom):
        try:
            events.put(('built', build(rom, lambda line: events.put(('log', line)))))
        except Exception as error:
            events.put(('error', str(error)))

    def rebuild():
        nonlocal busy
        if busy:
            return
        rom = filedialog.askopenfilename(title='Select River City Ransom (USA)', filetypes=[('NES ROM', '*.nes'), ('All files', '*')])
        if not rom:
            return
        busy = True
        rebuild_button.config(state=tk.DISABLED)
        play_button.config(state=tk.DISABLED)
        threading.Thread(target=worker, args=(rom,), daemon=True).start()

    def play_previous():
        executable = previous_build()
        if executable:
            play(executable)

    play_button = tk.Button(buttons, text='Play Previous Build', command=play_previous,
                            state=tk.NORMAL if previous_build() else tk.DISABLED)
    play_button.pack(side=tk.LEFT, padx=8)
    rebuild_button = tk.Button(buttons, text='Rebuild' if previous_build() else 'Choose ROM and Build', command=rebuild)
    rebuild_button.pack(side=tk.LEFT, padx=8)

    def poll():
        nonlocal busy
        while not events.empty():
            kind, value = events.get()
            if kind == 'log':
                output.insert(tk.END, value)
                output.see(tk.END)
            else:
                busy = False
                rebuild_button.config(state=tk.NORMAL, text='Rebuild')
                play_button.config(state=tk.NORMAL if previous_build() else tk.DISABLED)
                if kind == 'error':
                    messagebox.showerror('Build did not complete', value)
                else:
                    play(value)
        window.after(100, poll)

    def close():
        if busy:
            messagebox.showinfo('Build running', 'Wait for the build to finish before closing Setup.')
        else:
            window.destroy()

    window.protocol('WM_DELETE_WINDOW', close)
    poll()
    window.mainloop()


if __name__ == '__main__':
    main()
