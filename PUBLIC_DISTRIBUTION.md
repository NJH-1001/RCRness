# Public distribution boundary

RCRness is designed for clean-source distribution. A public repository or
release may contain the handwritten project source, configuration, build
scripts, documentation, and the pinned NESRecomp framework dependency.

It must not contain:

- a River City Ransom ROM or extracted PRG/CHR data;
- `generated/rcr_full.c`, `generated/rcr_dispatch.c`, or other generated game
  code;
- a playable RCRness executable, object file, or symbol file, because the
  playable executable statically contains generated game code;
- saves, screenshots, video/audio captures, traces, or diagnostic dumps;
- Ghidra projects, extracted binaries, or analysis databases;
- user-specific paths, launcher configuration, credentials, or private logs.

Users build privately from their own legally obtained ROM with
`setup-and-build.ps1` (hash-verified portable toolchain setup) or `build.ps1`
(existing compatible toolchain). The repository's public package script creates
a ROM-free Windows x86-64 source and build kit; it deliberately does not package
the locally built game.

Public releases may additionally contain `RCRness-Setup.exe`, the independently
written setup host built from `bootstrap/RCRnessSetup.cs`. The setup host embeds
only the audited clean source kit, validates the user's ROM locally, and invokes
the private local build. It is not a playable title executable and contains no
ROM-derived or generated game code.

Linux and macOS releases may contain the separately written
`bootstrap/setup_unix.py` setup host packaged as a native executable/app. It
embeds only the audited source kit, checks the user's local ROM hash and runs
the private local build. Native CI compilation uses original synthetic test
input solely in temporary build directories. Neither that test executable nor
any private playable executable is attached to a release. Platform setup
archives and source kits are the only public build artifacts.
