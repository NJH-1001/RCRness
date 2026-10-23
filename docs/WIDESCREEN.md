# Enhanced renderer and adaptive widescreen

The default is **Fit to window**. Resizing the game window changes the actual
rendered world width, from 256 columns in a narrow window to 854 at 32:9.
The initial window is approximately 16:9. Fit uses fractional presentation
scaling when necessary so the picture fills the available aspect.

```powershell
.\RCRness.exe 'River City Ransom (USA).nes' --widescreen fit
.\RCRness.exe 'River City Ransom (USA).nes' --widescreen 16:9
.\RCRness.exe 'River City Ransom (USA).nes' --widescreen 21:9
.\RCRness.exe 'River City Ransom (USA).nes' --widescreen 32:9
.\RCRness.exe 'River City Ransom (USA).nes' --widescreen off
```

The thirteen scrolling rooms use the same NESRecomp custom-compositor and
live-resizing API used by Super Mario Bros. Their camera stops at the authored
room edges. Rooms narrower than the viewport are centered. The twenty-two
authored single-screen rooms, shops, title and other non-gameplay screens keep
their native composition; neighboring nametable data is never repeated to
fill those margins. The status bar and text remain centered and readable.
Pausing a scrolling room retains the wide world and frozen actors behind the
centered pause controls. Full pause panels (including belongings, status/help
and passwords) extend their native flat background across the viewport while
keeping text and cursors at their original size. Resizing while paused works.
The game identifies these panels through its native pause-palette buffer;
the mode is derived from guest RAM again after loading a state.
The final school corridor excludes its duplicate lookahead page from the
camera bounds; native movement confirms its right wall at player X=1015.

The existing CRT filter, controller routing, pre-NMI timing and sprite-flicker
repair remain available. The CRT filter can be toggled with Ctrl+F7 or disabled
with `--no-crt-filter`. The enhanced renderer uses the per-frame compositor;
the experimental dot-PPU is not a compatible renderer override.

## World and object handling

The verified USA ROM owns every tile and sprite. The host decodes the original
scrolling-room directory at `$C599`, seven-byte page descriptors and their row
and attribute tables into a world cache. Each page retains its original CHR
and palette selection. The native pass remains authoritative for live visible
door/text edits, IRQ splits and other transient background changes. Its
hardware left-eight-pixel mask cannot create a seam inside the wider world.

The original `$ED0E` metasprite routine is observed before its OAM budget and
8-bit clipping checks. A bounded host decoder handles linked graphics streams,
character palettes, face variants and held objects in signed world coordinates.
Complete sprite packets are promoted at the same page-$02 DMA as native OAM.
The native source pass suppresses those sprites so each actor is drawn once.
Draw order and behind-background priority follow the original packet data.
The original guest routine still runs with its original timing and writes.

Screen-dependent guest reads are scoped to verified call sites:

- `$82D6/$82DE`, bank 4: hitboxes use a common local origin for each object
  pair, retaining the original attack, damage, pickup and collision routines.
  The origin is clamped to zero near the left wall: an unsigned subtraction
  borrow otherwise rejects Alex's hitboxes at his starting X=48.
- `$B4AF/$B4B5`, bank 4: special actor activation follows the displayed view.
- `$BC19/$BC1F`, bank 4: authored replacement-wave positions are evaluated
  against the displayed view when the native spawner chooses a candidate.

No extra logical enemies are invented. The original two enemy slots, gang and
boss prerequisites, spawn tables, terrain collisions and room transitions
remain in control. If an entire room fits on screen, its authored spawn
entrances can be visible; the finite original spawn table still governs them.
Weapons and coins use the same full-sprite path as people. Guest coordinates
and native in-game progress are not shifted or rewritten by presentation.

Current-build states serialize the compact source of both shadow and displayed
sprite packets. The packets are reconstructed on load, and the terrain is
derived again from the ROM. Aspect selection remains a presentation setting.
States from other builds are disposable; no backward compatibility is promised.

## Reproducible dependency and build

`NESRECOMP_COMMIT` and the gitlink keep the upstream dependency fetchable.
`prepare-engine.ps1` applies `engine-patches/adaptive-renderer.patch` to that
revision, or verifies that it is already applied. It refuses partial/conflicting
changes. `build.ps1` calls it automatically. The patch includes the original
SMB renderer API backports (`36e02ce`, `86e0a8b`), integration with the RCR fork's
CRT/focus/timing fixes, scoped zero-page read-hook support and the upstream
save-state tail-ancestry reset (`4e4a133`). It contains no game ROM data.
The state continuation also follows an NMI's deliberate guest-stack unwind:
a post-NMI snapshot resumes its caller, preserving full-submenu save/load.

With Visual Studio 2022 C++ tools and CMake installed:

```powershell
.\build.ps1 -Rom '.\roms\River City Ransom (USA).nes' `
    -BuildDirectory '.\build-enhanced' -UseVisualStudio
```

The executable is `build-enhanced/Release/RCRness.exe`. Omit
`-UseVisualStudio` for the original LLVM-MinGW/Ninja toolchain path. Add
`-Trace` for the TCP diagnostics required by the runtime audit scripts.
Builds use a `temp` directory inside the selected build directory. Original
ROM SHA-256 is checked before private code generation.

## Validation and limits

The automated entrance audit derives all 73 entrance records from the actual
USA ROM table at `$A43D`, covering all 35 rooms. Teleports invoke the original
entrance dispatcher; traversal and progression prerequisites are bypassed.
This establishes loading/rendering coverage, not a completed game or every
room's combat mechanics.

Run `tools/validate_widescreen.py --help`, `tools/validate_wide_combat.py
--help`, `tools/validate_pause.py --help` and
`tools/validate_incoming_damage.py --help` for the private runtime checks.
They require a trace build, the owner
ROM and a current-build gameplay state. Output remains outside source control;
game processes are hidden and audio output is muted with a dummy device.

Validated: all 73 entrance loads, 35-room graphics coverage, pixel-identical
native terrain comparisons in scrolling rooms, complete sprites beyond the
old edges, nine geometry cases, actual hidden-window resizing with CRT both
enabled and disabled, and identical current-build save/load replay images and
RAM. The controlled combat test places a protected player and enemy beyond
the old screen and exercises the original punch/damage/defeat code. The stock
comparison retains enemy health; the wide-view comparison defeats the enemy.
Coin collection awards the original money reward and allows the original
replacement wave to spawn. A separate pending-actor test confirms that
visibility activation follows the wider viewport; its prerequisite state is
supplied explicitly, so it does not establish boss-unlock behavior.

The owner-reported left-edge damage regression was reproduced with a captured
natural enemy attack and unchanged health/defense: the former wide origin
retained 63 HP, while the corrected origin and native mode both reduced it to
61 HP over the same four frames at X=48. The incoming-damage audit controls
positions only, leaves native enemy AI/attack/damage flags in charge, and
replays this hit at the left edge and in the expanded view. A separate Mesen
reference run of the unmodified owner ROM confirms that an idle starting Alex
can take enemy damage and die.

Unverified: full progression through every boss and ending, all shop purchases
and secret-shop prerequisites, physical two-controller play, and network play.
Changing viewport-driven activation/spawn behavior is not qualified for an
existing netplay simulation profile.
