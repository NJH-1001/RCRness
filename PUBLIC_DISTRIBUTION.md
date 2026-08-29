# Public distribution boundary

RCRness is designed for clean-source distribution. A public repository or
release may contain the handwritten project source, configuration, build
scripts, documentation, and the pinned NESRecomp framework dependency.

It must not contain:

- a River City Ransom ROM or extracted PRG/CHR data;
- `generated/rcr_full.c`, `generated/rcr_dispatch.c`, or other generated game
  code;
- a playable RCRness executable, object file, or symbol file, because the
  executable statically contains generated game code;
- saves, screenshots, video/audio captures, traces, or diagnostic dumps;
- Ghidra projects, extracted binaries, or analysis databases;
- user-specific paths, launcher configuration, credentials, or private logs.

Users build privately from their own legally obtained ROM with `build.ps1`.
The repository's public package script creates a ROM-free Windows x86-64 source
and build kit; it deliberately does not package the locally built game.
