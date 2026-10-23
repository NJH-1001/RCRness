# Verification status

## Local adaptive-renderer validation

- Exact owner ROM SHA-256 matches the supported USA revision.
- Widescreen-off boot/gameplay checkpoints match the original project build.
- All 73 ROM-derived entrance records covering all 35 rooms load with zero
  dispatch misses and zero metasprite decoder errors.
- Every sampled scrolling-room background comparison matches all 38,400 native
  playfield pixels. Fixed rooms keep the complete native frame and sprites.
- Nine aspect/resize cases pass, including real hidden SDL windows with CRT
  enabled and disabled.
- Native right-edge movement stops at X=1015 in the top school corridor;
  its duplicate fifth streaming page is excluded from the wide camera bounds.
- Current-build save/load replay matches the resulting PNG and RAM exactly.
  Repeated entrance restores exercise the upstream native-tail reset fix.
- A protected-player punch test at world X=400 with camera X=0 retains enemy
  health in stock mode and reduces health to zero in the enhanced wide view.
- The defeated enemy's coin awards its original money reward, followed by a
  replacement wave from the original gang spawner. A pending actor at X=400
  retains its pending visibility state in stock mode and becomes visible in
  the wide view; that test supplies the pending prerequisite explicitly.

Entrance loading is not full gameplay completion. Traversal/progression gates
were bypassed for the entrance audit. See [WIDESCREEN.md](docs/WIDESCREEN.md)
for the implementation, scripts and remaining unverified cases.

## Verified

- Ghidra MCP connected to the fixed 8 KiB bank before analysis.
- ROM identity: mapper 4, 8 x 16 KiB PRG, 16 x 8 KiB CHR, no trainer.
- Vectors: NMI `$FF4F`, RESET `$FF76`, IRQ `$F1D9`.
- RESET initializes hardware and transfers to the main loop at `$F223`.
- RelWithDebInfo x86-64 Windows build completes with Clang/Ninja.
- The executable validates and loads the user-owned ROM, initializes MMC3,
  SDL audio, TCP debugging, and an Xbox One Controller.
- A scripted run reaches the game mode menu, options, intro, and live gameplay.
- The live gameplay frame was compared with Mesen 0.9.9 at the same scripted
  input point; character, HUD, background, palette, and MMC3 split agree.
- Recomp-vs-recomp determinism passes across 2,370 frames.
- WASD plus J/K keyboard bindings load from `keybinds.ini`.
- A connected Xbox One Controller is assigned to P1 with the clean-install
  defaults; physical pads are assigned densely to gamepad-enabled players.
- The two-player mode reaches live gameplay with both Alex and Ryan present.
  Source-level routing confirms SDL pad 1 feeds NES port 1 and SDL pad 2 feeds
  NES port 2 with the clean-install `{ gamepad, gamepad }` defaults; a physical
  two-controller check remains for the user machine.
- Controller enumeration now retains SDL joystick devices that are not present
  in the bundled game-controller mapping database instead of silently rejecting
  them. Mapped Xbox/PlayStation/Switch devices use SDL HIDAPI; raw devices use a
  generic axes/buttons/hat path with the current official PowerA Switch face
  ordering recognized by vendor ID. Hotplug add/remove events are deduplicated
  across SDL's joystick and game-controller event families.
- Native-pixel and 4:3 presentation are selectable; 4:3 uses a 320x240 logical
  canvas over the unchanged 256x240 framebuffer.
- A matched 15-second audio probe produced 660,412 source samples at the exact
  44.1 kHz/60.0988 Hz cadence. All 900 bridge events reported zero underruns,
  overflow drops, and stretch events; worst frame-edge delta improved from
  2,354 to 1,510 PCM units versus the interrupted-turn capture.
- Two matched eight-second menu probes after correcting triangle-DAC hold
  behavior had no APU or repeatable bridge transitions above 3,000 PCM units.
  The APU maximum fell from 7,680 to 2,925 and the triangle-channel maximum
  fell from 31,161 to 2,185; all 480 bridge events again reported zero
  underruns, overflow drops, and stretch events.
- Two 600-frame headless smoke runs matched at every 100-frame hash checkpoint
  and reported zero dispatch misses after the input/audio/aspect changes.
- Ghidra confirms RCR's metasprite routine checks the OAM cursor at `$052D`
  (`$ED1B`) and rejects another object below `$08`; each emitted tile subtracts
  four at `$EF59-$EF5F` and allocation stops at the reserved `$04` boundary.
  The diagnostic build observes only the exact `$08 -> $04` store at `$EF5F`
  and then writes one local screenshot/save-state pair at a safe frame boundary.
  A 600-frame smoke run with the observer enabled retained the established
  hashes and reported zero dispatch misses.
- The wrong-tile diagnostic retains a three-second, 180-frame framebuffer ring
  and dumps it on `Ctrl+Shift+C`. Its debug-command validation produced all 180
  consecutively numbered PNGs, a 180-line manifest, and a non-empty save state;
  the temporary validation capture was removed afterward.
- A user gameplay trace isolated the apparent wrong-tile artifact to individual
  shadow-OAM entries ending a frame with the game's clipped value `Y=$F8`.
  Write attribution identified `$EF3F` as the writer and `$F290` as the verified
  next-build boundary. The selectable sprite-flicker reduction mode now repairs
  only a transient four-byte entry in the page `$02` DMA presentation snapshot;
  coherent entries pass through from the current DMA without delay. Guest RAM,
  timing, and generated code remain unchanged.
- A later 180-frame gameplay trace found two additional isolated partial pages
  at frames 7849 and 7890. Both contained an `Y=$F8` entry for exactly one frame
  and reverted on the next frame, while unused entries remained `Y=$F0`.
  Snapshot promotion now rejects any page that still contains the verified
  transient `$F8` marker and retains the preceding coherent page for that frame.
- Replaying frames 850-879 from the captured save state with the option enabled
  changed exactly the five previously corrupted frame hashes (851, 853, 857,
  872, and 876) to the intact neighboring-frame hash `2d807115`; all 25 already
  intact frames retained their original hashes. The established 600-frame boot
  smoke hashes also remain unchanged with zero dispatch misses.
- A moving-gameplay replay exposed the former whole-page snapshot as one game
  update behind authentic DMA on 29 consecutive rendered frames. With per-entry
  DMA repair, all 29 filtered hashes match authentic sprite timing exactly. The
  known-corruption replay still changes exactly the same five `$F8` frames to
  `2d807115`, and both replays report zero dispatch misses.
- The RelWithDebInfo build and established 600-frame smoke hashes remain clean
  after the mapped-controller/raw-joystick dual path. The sandbox device session
  enumerated the Xbox One Controller through SDL's standardized mapping; the
  user's PowerA Switch 2 hardware remains the required physical P2 check.
- The public setup path now uses pinned, SHA-256-verified portable LLVM-MinGW
  20260616, CMake 4.4.2, and Ninja 1.13.2 archives instead of the Visual Studio
  C++ workload. A clean end-to-end setup build produced a native x86-64 PE with
  no LLVM runtime DLL dependency. Two 600-frame smoke runs matched the
  established hashes at every 100-frame checkpoint and reported zero dispatch
  misses.
- Reopening setup after a completed build detects the newest private
  `%LOCALAPPDATA%\RCRness\source-v*\build-public\RCRness.exe` and offers separate
  Play Previous Build and Rebuild actions. Play launches without invoking any
  build tool; successful rebuilds remember only the local ROM path for later
  launches, without copying ROM data.
- The selectable CRT/composite path creates and presents a 768x720 native-pixel
  or 960x720 aspect-corrected filtered image from the untouched 256x240
  framebuffer. Aspect correction now happens before the phosphor mask, avoiding
  fractional mask stretching and low-frequency vertical beat bands. The former
  per-pixel RGB grille was replaced with the official MiSTer JVC preset's neutral
  6x6 staggered JVC 001 slot geometry and 100%/75% intensity ratio; filtered
  texture scaling softens the slots at fractional window sizes. Picture-pixel edge and
  corner samples are blended independently of the grille, followed by a light
  3x3 Gaussian pass; this gives isolated pixels a rounded, subtly soft profile
  while flat colors remain flat. A captured gameplay frame was
  rendered through the same production filter and visually checked for intact
  geometry/text, neutral whites, staggered JVC-style slots,
  restrained horizontal bleed, warm highlight halation, and a second-pass
  neighboring-cell bloom that softens flat-field color bands. A live
  software-renderer run exercised filtered presentation while both the mapped
  Xbox P1 and raw PowerA P2 devices were connected.
- The 4:3 CRT path now computes its 256-to-320 interpolation once per source
  pixel and reuses that cached picture for beam, glow, and neighbor samples.
  A 600-frame optimized benchmark fell from 10.39 ms/frame to 6.59 ms/frame
  (36.6%) while retaining the exact filtered-output hash `2f87e6d1`.
- Local play blocks at the frame boundary and pauses the SDL audio device while
  the main window lacks input focus, then resumes both on focus gain. Netplay is
  intentionally exempt to prevent one peer from stalling the session.

## Owner playtest: wide pause and incoming damage

- The root pause display now keeps the scrolling-room world and actor packets
  in the adaptive viewport. Native pause text/cursor pixels remain centered;
  full pause submenus extend their flat native border to the viewport edges.
- At the starting X=48, the former virtual hitbox origin was -16. The guest's
  unsigned subtraction rejected that borrow before testing Alex's hitboxes.
  Clamping the origin to zero retains the original collision/damage code.
- Replayed the same captured natural enemy attack at X=48: old widescreen
  HP 63 -> 63; corrected widescreen HP 63 -> 61; native HP 63 -> 61. Health,
  defense, attack states and success/damage flags were not written. Position
  cheats establish contact; they do not establish ordinary AI route behavior.
- Independently ran the original owner ROM in the Mesen libretro reference
  with a boot input script followed by no input. Enemy attacks reduce Alex's
  health to zero. The original game does not grant permanent AFK immunity.
- Reproducible runtime checks: `tools/validate_pause.py` and
  `tools/validate_incoming_damage.py`; private artifacts are outside Git.
- The shared runtime now records the resumed caller PC after an NMI deliberately
  pops guest JSR frames. Its old pre-interrupt FC73 wait address was inconsistent
  with the post-NMI CPU/stack snapshot and could spin with NMI disabled when a
  full pause submenu was restored. The same stack-unwind predicate used by the
  runner selects the architectural RTS continuation; ordinary snapshots retain
  their existing PC and instruction-charge semantics.
- Final runtime checks pass: seven paused geometry cases in a real hidden SDL
  window with CRT enabled; all five submenu images, exact state replay and native
  return controls; root pause state replay and resume; six incoming-hit cases at
  X=48/X=400; the existing outgoing-hit/defeat/coin/replacement-wave checks;
  73 entrances across 35 rooms and exact gameplay state replay. The final
  production boot retains every established native/off hash through frame 1100
  and reports zero dispatch misses in native and Fit modes.

## Resolved timing failure

The initial per-frame renderer invoked RCR's MMC3 IRQ handlers after NMI in one
synchronous batch. IRQ `$F1D9` therefore set RAM `$0014` again before main code
at `$EFD4` could observe the NMI's clear, stalling the palette fade at
`$003E/$0692/$0693 = $06/$FF/$00`.

Ghidra confirmed the handshake among main loop `$F223`, wait routine `$EFD4`,
fade state machine `$E343`, NMI `$F168`, and IRQ `$F1D9`. Enabling NESRecomp's
existing generic pre-NMI compositor mode restores hardware ordering: the fade
counter advances `$FF -> $00 -> $01 -> $02 -> $03 -> $04`, then gameplay appears.

No ROM poke, generated-code edit, or game-code bypass is used. The project only
selects the verified generic renderer timing mode through its public runner API.
