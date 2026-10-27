# Verification status

## v0.1.6 shop-entry hotfix verification (2026-10-26)

- Only gameplay/config change from v0.1.5: add `bank2 = [0x8C7E]` under
  `[functions]` in `game.toml`. No engine patch, controller, rendering, damage,
  or generated-code hand edits. Setup version is bumped to 0.1.6.
- Ghidra confirms bank 2 uses the recompiler's 16-KiB numbering. At `$8C75`
  the shop loop pushes `$8C7D`, then jumps indirectly through `$002A`;
  the handler's return continuation is `$8C7E`. That continuation begins with
  `INC $052B` followed by the shop-loop helper calls.
- The v0.1.5 private build reproduced the freeze on the original shop-entry
  request: fallback at `$8C7E` hit the watchdog at `$FC73`, then paused.
- Regenerated from the supported owner ROM using the amended config, then
  compiled the private Windows trace build. The new dispatcher explicitly
  maps `$8C7E`, bank 2, to `func_8C7E_b2`.
- `tools/validate_shop_entry.py` triggers the original shop-entry dispatcher
  from a gameplay snapshot, bypassing traversal prerequisites. Shop indices
  0, 1, 5, 10 and 23 each ran 600 frames at the native menu, then another
  384 frames with input; zero dispatch misses and watchdog trips. Screenshots
  show book, cafe, sushi and mystery-shop menus. This is not a purchase,
  learned-move, boss-progression, password or full-completion certification.
- All six incoming-damage comparisons passed again (HP 63 -> 61 except the
  expected clipped native X=400 case, which remains 63).
- The reporter independently reports finishing the game, including shops,
  bosses, restaurants, moves and passwords; that is user feedback, not a
  local full-game completion test.
- Existing save-state long-replay differences documented for v0.1.5 remain.
- Existing installations must run the new setup and choose **Rebuild** once.
  **Play Previous Build** deliberately preserves the previously compiled game.

## v0.1.5 release verification (2026-10-23)

- **Watchdog repaired; remaining save-state mismatch accepted for release:** a regression
  test reproduced the cumulative instruction-cap failure (three failed checks
  before the fix). The isolated engine now renews that budget at completed
  frame boundaries: all 75 interpreter checks pass, including 4.1 million
  progressing instructions and a no-progress loop that still trips the guard.
  Real-game saves captured at frames 1400 and 1983 both advance another 6000
  frames with zero watchdog trips and zero dispatch misses. However, the new
  uninterrupted-versus-restored comparison fails RAM equality for both saves;
  the pre-game save also has a small visible pixel difference at the final
  checkpoint (a roughly 5x5-pixel patch near the lower death-message text).
  The gameplay save's final image matches. Do not treat absence of the
  watchdog as proof of exact continuation restoration. The owner explicitly
  authorized publication with this known limitation on 2026-10-23.
  Private evidence is under `build-release-validation/watchdog-regression-2`;
  the reproducible audit is `tools/validate_savestate_continuation.py`.
- Synced the merged adaptive-widescreen work at `967f6a2`.
- Built privately from clean pinned engine `a546dfef` plus the checked-in
  renderer patch. The separate shared engine's PS1 edits were preserved.
- Corrected C token spacing (`0x9e + obj`) required by LLVM-MinGW.
- Windows native/off and Fit boot tests ran 1,100 frames with zero dispatch
  misses. Native frame hashes match the v0.1.4 regression checkpoints.
- A private scripted Windows run reached live widescreen gameplay. A gameplay
  snapshot at frame 1983 passed all 73 entrance loads, nine world geometry
  cases, seven hidden-window CRT pause/resize cases and all five submenus.
  Gameplay and pause state replay produced identical images and RAM.
- The outgoing combat test passed original damage/defeat, coin rewards,
  replacement waves and pending actor activation in the expanded viewport.
- **Incoming-damage check resolved:** the old test moved Alex to X=48 or X=80
  according to enemy facing and repeatedly repositioned an enemy. Its setup
  could either capture the wrong side or prevent a natural approach. The new
  default test boots using controller input, leaves all RAM untouched during
  capture, and records a natural idle-player hit at frame 3564 from a snapshot
  at frame 3560. Alex is at X=48 and HP changes 63 -> 61 in native, 16:9, 21:9
  and 32:9 replay. Translating all actors by +352 gives X=400: HP remains 63
  in native view (clipped contact), but drops to 61 in 32:9. Every case has
  zero dispatch misses. No attacks, health, defense or damage flags are poked.
- The negative control temporarily removed the existing `origin<0` clamp:
  native still damaged Alex, while 16:9 incorrectly retained 63 HP and the test
  failed. Restoring the clamp passed. Game source is unchanged from the
  candidate; only the test setup and documentation required correction.
- An attempted snapshot at frame 1400 was still before player initialization
  (HP=0); restoring it hit the interpreter watchdog at `$FC73`. Gameplay and
  pause snapshots passed, but pre-game transition snapshot restoration is not
  qualified. A long run resumed from the frame-1983 snapshot also reached a
  fallback watchdog at `$F2CE` after frame 3159. Fresh-boot native and wide
  capture reached frame 3564 successfully. Long resumed sessions remain a
  former save-state limitation. The completed-frame watchdog repair described
  above removes that failure; exact long replay equivalence remains unqualified.
- Native GitHub runners compiled and linked the Linux x86-64, macOS Intel and
  macOS Apple Silicon hosts with original synthetic test input. Each packaged
  setup passed its embedded ROM-free payload audit. Real-ROM gameplay and
  physical controller tests on Linux/macOS remain unverified.
- The audit tools now accept a private output directory on any drive instead
  of requiring contributor-specific F:/G: volumes.
- Public release assets contain setup applications and tracked source only.
  No playable title binaries, ROMs, generated game code or private test data
  are included. The incoming-damage check and cumulative watchdog failure are
  resolved; the owner accepted the remaining long-replay mismatch for release.

## Experimental adaptive widescreen mod: local validation

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
