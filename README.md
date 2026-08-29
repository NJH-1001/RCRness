# RCRness

Public, ROM-free NESRecomp project for a user-owned **River City Ransom (USA)**
ROM. This repository intentionally contains no ROM, generated game code,
playable executable, save data, captures, Ghidra project, or other copyrighted
game data.

Because NESRecomp is a static recompiler, a playable `RCRness.exe` contains
code generated from the user's ROM. Public releases therefore distribute the
clean source/build kit only. Each user generates and builds the playable
executable locally from a legally obtained ROM.

Expected ROM identity:

- iNES mapper 4 (MMC3), 8 x 16 KiB PRG, 16 x 8 KiB CHR, no trainer
- SHA-256: `B95F8DEF04C0012604B7CC68CF4ED8F49B2DFE4BEDA6182051DE4B2423BEA7B1`
- Header-excluded CRC32: `E9C387EC`

## Build on Windows x86-64

The easiest path requires only 64-bit Windows 10/11, PowerShell, Windows
Package Manager (`winget`), and your legally obtained ROM. The setup wrapper
checks the machine, installs any missing Git, CMake, and Visual Studio 2022 C++
build tools from their standard WinGet packages, then runs the normal build:

```powershell
.\setup-and-build.ps1 -Rom 'C:\path\to\River City Ransom (USA).nes'
```

The Visual Studio installer may request administrator approval. If Windows asks
for a restart, restart and run the same command again; completed tool installs
will be detected and skipped. Before installing anything, the wrapper lists the
missing tools and asks permission to accept the WinGet source and package
license agreements. Automated setups can pass `-AcceptToolLicenses` to skip
that prompt.

For an existing development machine, the direct build still requires Git,
CMake 3.20+, and Visual Studio 2022 with the Desktop development with C++
workload:

```powershell
git submodule update --init --recursive
.\build.ps1 -Rom 'C:\path\to\River City Ransom (USA).nes'
```

Both paths build the recompiler, privately generate `generated/rcr_*.c`, and
build `build-public/Release/RCRness.exe`. The ROM and generated files stay
ignored and must never be committed or attached to a public release.

Xbox/SDL-compatible controllers are the clean-install P1 and P2 defaults. The
checked-in `keybinds.ini` also keeps movement on WASD and A/B on K/J as a P1
fallback; analog-stick and d-pad movement are both enabled. With two connected
pads, the first controls player 1 and the second controls player 2.

Xbox, DualShock 4, DualSense, and recognized Switch-family pads use SDL's
standardized HIDAPI/gamepad mappings. Newer or unmapped devices (including
PowerA Switch 2 models not yet present in the bundled SDL database) remain
available through a generic joystick fallback with PowerA-aware face buttons,
hat/button d-pad support, analog movement, and common +/-/Share/Options mapping.
Hotplug is supported; connect both pads before launching for deterministic P1/P2
assignment.

Display aspect ratio is selectable without changing the native framebuffer:

- Press Ctrl+F9 in game to toggle native-pixel and 4:3 presentation (persisted
  to `config.ini`).
- Or launch with `--aspect-4x3` / `--pixel-aspect` for a one-run override.
- `Aspect4x3 = 1` under `[Display]` selects 4:3 directly in `config.ini`.

Sprite-flicker reduction is enabled by default. RCR sometimes needs more than
one video frame to finish rebuilding shadow OAM; the option presents the last
completed OAM snapshot instead of a hardware-era partial update:

Snapshots that still contain the writer's transient clipped `Y=$F8` marker are
not promoted; the last coherent page remains visible until the build completes.

- Press Ctrl+F8 in game to toggle the option (persisted to `config.ini`).
- Or launch with `--reduce-sprite-flicker` / `--authentic-sprites` for a
  one-run override.
- `ReduceSpriteFlicker = 1` under `[Display]` enables it directly.

The option does not modify guest RAM, generated code, or game timing. Disable
it if an unusual scene shows a sprite lingering until the next completed game
update.

## CRT/composite presentation

The CRT/composite filter is enabled by default and runs only on the displayed
image. Its presentation is modeled after MiSTer's official JVC preset: a neutral
staggered 6x6 JVC slot mask spans multiple picture pixels instead of aligning an
RGB triad to every pixel. Mild horizontal composite bleed, warm halation, soft
rounded pixel envelopes, filtered mask scaling, and a light Gaussian bloom keep
the image organic rather than rigidly gridded. A gentle
nonlinear midtone lift keeps the filtered image bright without raising true
black. The image is aspect corrected before the phosphor mask is drawn, keeping
the mask evenly spaced and avoiding wide interference bands in 4:3 mode. Native screenshots,
diagnostics, and game state remain unchanged.

- Press Ctrl+F7 in game to toggle it (persisted to `config.ini`).
- Or launch with `--crt-filter` / `--no-crt-filter` for a one-run override.
- `CrtFilter = 1` under `[Display]` enables it directly.

An active HD texture pack takes presentation priority over the CRT filter.

The game and its audio automatically pause whenever the main game window loses
focus, then resume when it regains focus. Active netplay sessions remain live so
one unfocused peer cannot stall the other player.

## Distribution policy

Public source archives and releases must pass `package-public.ps1`. The audit
fails if it finds ROMs, generated game code, saves, captures, Ghidra databases,
or playable binaries. See `PUBLIC_DISTRIBUTION.md` for the complete boundary.
