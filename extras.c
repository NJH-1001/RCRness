#include "extras.h"
#include "config.h"
#include "mod_savestate.h"
#include "nes_runtime.h"
#include "ppu_dot.h"

#include <stddef.h>
#include <stdio.h>
#include <string.h>

extern void func_RESET(void);
extern void func_NMI(void);

/* Shared runner/debug-server state expected by the current game hook ABI. */
const char *g_rom_path_for_extras = NULL;
int g_watchdog_triggered = 0;
uint32_t g_watchdog_frame = 0;
const char *g_watchdog_stack_dump = NULL;

/* RCR can take more than one video frame to finish a gameplay update. Its
 * metasprite builder writes directly into shadow OAM while that update is in
 * progress, so the hardware-era mid-update DMA exposes transient clipped
 * entries (Y=$F8) as one-frame holes. $F290 is the verified boundary where
 * the game resets its OAM cursor before beginning the next complete build.
 * Preserve the just-finished shadow page there and present only completed OAM
 * snapshots. Guest RAM and game timing remain untouched. */
static uint8_t s_completed_oam[0x100];
static int     s_completed_oam_valid = 0;

static int shadow_oam_is_complete(void) {
    /* RCR initializes unused entries to Y=$F0.  Its metasprite writer uses
     * Y=$F8 only while clipping/replacing an entry, so a page that still has
     * an $F8 Y byte at the next-build boundary is not safe to present yet.
     * Keep the preceding completed page until the following coherent build. */
    for (int slot = 0; slot < 64; slot++) {
        if (g_ram[0x0200 + slot * 4] == 0xF8)
            return 0;
    }
    return 1;
}

static int completed_oam_state_get(uint8_t *buf, int cap) {
    if (cap < 0x101) return -1;
    buf[0] = (uint8_t)(s_completed_oam_valid != 0);
    memcpy(buf + 1, s_completed_oam, sizeof(s_completed_oam));
    return 0x101;
}

static int completed_oam_state_set(const uint8_t *buf, int len) {
    if (len != 0x101) return 0;
    s_completed_oam_valid = buf[0] != 0;
    memcpy(s_completed_oam, buf + 1, sizeof(s_completed_oam));
    return 1;
}

const char *game_get_name(void) {
    return "River City Ransom (USA) - RCRness";
}

void game_on_init(void) {
    /* RCR's MMC3 IRQ handshake must run before its vblank NMI clears the
     * completion flag. This established renderer mode preserves that ordering
     * while retaining the stable per-frame compositor. */
    ppu_dot_set_pre_nmi_render_enabled(1);
    if (!nes_mod_register_savestate_hook("rcr.completed-oam",
                                         completed_oam_state_get,
                                         completed_oam_state_set))
        fprintf(stderr, "[Sprite] Could not register completed-OAM save state\n");
}

void game_on_frame(uint64_t frame_count) {
    g_watchdog_frame = (uint32_t)frame_count;
}

void game_post_nmi(uint64_t frame_count) {
    (void)frame_count;
}

int game_handle_arg(const char *key, const char *val) {
    (void)key;
    (void)val;
    return 0;
}

const char *game_arg_usage(void) { return NULL; }

uint32_t game_get_expected_crc32(void) {
    /* CRC32 of PRG+CHR data; the 16-byte iNES header is excluded. */
    return 0xE9C387ECu;
}

int game_dispatch_override(uint16_t addr) {
    (void)addr;
    return 0;
}

uint8_t game_ram_read_hook(uint16_t pc, uint16_t addr, uint8_t val) {
    (void)pc;
    (void)addr;
    return val;
}

void game_ram_write_observer(uint16_t pc, uint16_t addr,
                             uint8_t old_val, uint8_t new_val) {
    (void)old_val;
    if (pc == 0xF290 && addr == 0x052D && new_val == 0xFC &&
        shadow_oam_is_complete()) {
        memcpy(s_completed_oam, g_ram + 0x0200, sizeof(s_completed_oam));
        s_completed_oam_valid = 1;
    }
}

void game_oam_dma_filter(uint8_t page, uint8_t oam[0x100]) {
    if (page == 0x02 && s_completed_oam_valid &&
        g_nes_config.reduce_sprite_flicker)
        memcpy(oam, s_completed_oam, sizeof(s_completed_oam));
}

void game_run_nmi(void) { func_NMI(); }
void game_run_main(void) { func_RESET(); }

void game_post_render(uint32_t *framebuf) { (void)framebuf; }
void game_fill_frame_record(void *record) { (void)record; }

int game_handle_debug_cmd(const char *cmd, int id, const char *json) {
    (void)cmd;
    (void)id;
    (void)json;
    return 0;
}
