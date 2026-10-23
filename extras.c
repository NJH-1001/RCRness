#include "extras.h"
#include "config.h"
#include "mod_savestate.h"
#include "nes_runtime.h"
#include "ppu_dot.h"
#include "rcr_widescreen.h"
#include "debug_server.h"

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
 * progress, so the hardware-era mid-update DMA can expose an entry with the
 * verified transient clipped value Y=$F8. Repair only that entry in the DMA
 * presentation snapshot; every coherent entry must pass through immediately
 * so moving sprites remain synchronized with the scrolling background. Guest
 * RAM and game timing remain untouched. */
static uint8_t s_completed_oam[0x100];
static int     s_completed_oam_valid = 0;

static void repair_transient_oam_entries(uint8_t oam[0x100]) {
    /* A first snapshot must be wholly coherent because there is no preceding
     * value with which to repair a transient entry. Until then, retain the
     * authentic DMA contents rather than inventing a replacement. */
    if (!s_completed_oam_valid) {
        for (int slot = 0; slot < 64; slot++) {
            if (oam[slot * 4] == 0xF8)
                return;
        }
        memcpy(s_completed_oam, oam, sizeof(s_completed_oam));
        s_completed_oam_valid = 1;
        return;
    }

    /* RCR initializes unused entries to Y=$F0 and uses Y=$F8 only while an
     * entry is being clipped/replaced. Repair just that four-byte entry from
     * the preceding coherent state instead of delaying unrelated sprites. */
    for (int slot = 0; slot < 64; slot++) {
        size_t offset = (size_t)slot * 4;
        if (oam[offset] == 0xF8)
            memcpy(oam + offset, s_completed_oam + offset, 4);
        else
            memcpy(s_completed_oam + offset, oam + offset, 4);
    }
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
    return "River City Ransom";
}

void game_on_init(void) {
    /* RCR's MMC3 IRQ handshake must run before its vblank NMI clears the
     * completion flag. This established renderer mode preserves that ordering
     * while retaining the stable per-frame compositor. */
    ppu_dot_set_pre_nmi_render_enabled(1);
    rcr_ws_init(g_rom_path_for_extras);
    debug_server_init(0);
    if (!nes_mod_register_savestate_hook("rcr.completed-oam",
                                         completed_oam_state_get,
                                         completed_oam_state_set))
        fprintf(stderr, "[Sprite] Could not register completed-OAM save state\n");
}

void game_on_frame(uint64_t frame_count) {
    g_watchdog_frame = (uint32_t)frame_count;
    rcr_ws_frame();
}

void game_post_nmi(uint64_t frame_count) {
    (void)frame_count;
}

int game_handle_arg(const char *key, const char *val) {
    return rcr_ws_arg(key, val);
}

const char *game_arg_usage(void) { return "--widescreen fit|16:9|21:9|32:9|off (experimental)"; }

uint32_t game_get_expected_crc32(void) {
    /* CRC32 of PRG+CHR data; the 16-byte iNES header is excluded. */
    return 0xE9C387ECu;
}

int game_dispatch_override(uint16_t addr) {
    (void)addr;
    return 0;
}

uint8_t game_ram_read_hook(uint16_t pc, uint16_t addr, uint8_t val) {
    return rcr_ws_read(pc, addr, val);
}

void game_oam_dma_filter(uint8_t page, uint8_t oam[0x100]) {
    if (page == 0x02 && g_nes_config.reduce_sprite_flicker)
        repair_transient_oam_entries(oam);
    if (page == 0x02) rcr_ws_dma();
}

void game_run_nmi(void) { func_NMI(); }
void game_run_main(void) { func_RESET(); }

void game_post_render(uint32_t *framebuf) { (void)framebuf; }
void game_fill_frame_record(void *record) { (void)record; }

int game_handle_debug_cmd(const char *cmd, int id, const char *json) {
    return rcr_ws_debug(cmd, id, json);
}
