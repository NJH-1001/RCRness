/* Original synthetic white-box test: no ROM or generated game code. */
#define SDL_MAIN_HANDLED
#include "../rcr_widescreen.c"
#include <assert.h>
uint8_t g_ram[0x800];
uint8_t g_chr_ram[0x2000], g_ppu_pal[0x20];
const uint32_t g_nes_palette[64]={0};
CPU6502State g_cpu;
int g_current_bank, g_render_width=426;
/* Unused host integrations are stubbed; the sprite/list/state functions
 * exercised below are the real implementation included above. */
int nes_video_aspect_from_name(const char *n,NesAspectMode *m) { (void)n;(void)m;return 0; }
void nes_video_set_aspect_mode(NesAspectMode m) { (void)m; }
void nes_video_on_window_resized(int w,int h) { (void)w;(void)h; }
const char *nes_video_aspect_name(NesAspectMode m) { (void)m;return "test"; }
int ppu_renderer_set_custom_render(NesCustomRenderFn f,void *u) { (void)f;(void)u;return 1; }
void ppu_renderer_set_sprite_suppress(PpuSpriteSuppressFn f,void *u) { (void)f;(void)u; }
int ppu_renderer_in_custom_native_pass(void) { return 0; }
int ppu_renderer_background_opaque(int x,int y) { (void)x;(void)y;return 0; }
int nes_mod_set_function_hook_enabled(const char *id,int e) { (void)id;(void)e;return 1; }
int nes_mod_register_function_entry_plugin(const char *id,uint16_t a,NESModFunctionEntryCallback f) {
    (void)id;(void)a;(void)f;return 1;
}
int nes_mod_register_savestate_hook(const char *id,NESModSavestateGet g,NESModSavestateSet s) {
    (void)id;(void)g;(void)s;return 1;
}
void debug_server_send_fmt(const char *format,...) { (void)format; }

int main(void) {
    uint8_t saved[512];
    s_ready=1; s_enabled=1;
    g_ram[0x40]=1; g_ram[0x48]=0x80; g_ram[0x4b]=0x80;
    s_actors.room=0;
    s_actors.shadow[3].count=1;
    s_actors.shadow[3].source.valid=1;
    s_actors.present[3]=s_actors.shadow[3];

    /* Beginning a list can wait on the OLD pending OAM DMA. */
    g_ram[0x6b5]=2;
    begin_sprite_list(0xefd4);
    assert(s_list_pending && s_actors.shadow[3].count==1);
    rcr_ws_dma();
    assert(s_actors.present[3].count==1);

    /* First new actor call retires old unvisited packets, at the next DMA. */
    g_ram[0x47]=0;
    observe_sprite(0xed0e);
    assert(!s_list_pending && !s_actors.shadow[3].source.valid);
    assert(s_actors.present[3].count==1);
    rcr_ws_dma();
    assert(s_actors.present[3].count==0);

    /* A completed empty guest list retires every packet too. */
    s_actors.shadow[3].count=1;
    s_actors.shadow[3].source.valid=1;
    begin_sprite_list(0xefd4);
    g_ram[0x6b5]=0;
    rcr_ws_dma();
    assert(!s_list_pending && !s_actors.present[3].count);

    /* A suspension before the first actor preserves the list phase. */
    s_list_pending=1;
    int size=state_get(saved,sizeof saved);
    assert(size>0);
    s_list_pending=0;
    assert(state_set(saved,size) && s_list_pending==1);
    /* Old v0.1.6 payloads still load without the appended phase field. */
    assert(state_set(saved,size-sizeof(uint32_t)) && !s_list_pending);
    puts("sprite-list lifecycle: PASS");
    return 0;
}
