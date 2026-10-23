/* River City Ransom USA E9C387EC: world-space presentation and visibility.
 * All graphics are read from the verified owner ROM at runtime. No ROM data
 * or generated assets are part of this source file. See docs/WIDESCREEN.md. */
#include "rcr_widescreen.h"
#include "nes_runtime.h"
#include "nes_video.h"
#include "mapper.h"
#include "mod_function_hooks.h"
#include "mod_savestate.h"
#include "debug_server.h"
#include <SDL.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ROOMS 35
#define OBJECTS 7
#define TILES_PER_OBJECT 128
#define MAX_PAGES 5
#define PRG_SIZE 0x20000
#define CHR_SIZE 0x20000
typedef struct { int16_t x, y; uint8_t tile, attr; } Sprite;
typedef struct {
    int16_t x, wy;
    uint32_t order;
    uint8_t type, anim, variant, flags, held_by, held_state, held_kind, room, valid;
} Source;
typedef struct {
    Sprite tiles[TILES_PER_OBJECT];
    Source source;
    uint16_t count;
    uint32_t order;
    uint8_t room;
} Packet;
typedef struct {
    Packet shadow[OBJECTS], present[OBJECTS];
    uint32_t sequence;
    uint8_t room;
} ActorState;
static ActorState s_actors;
static uint8_t s_rom[PRG_SIZE + CHR_SIZE];
static int s_ready, s_enabled = 1;
static NesAspectMode s_aspect = NES_ASPECT_FIT;
static int s_room = -1, s_pages, s_left, s_right, s_view, s_camera;
static uint8_t s_tiles[MAX_PAGES * 32][30];
static uint8_t s_attributes[MAX_PAGES * 32][30];
static uint8_t s_page_palette[MAX_PAGES], s_page_chr[MAX_PAGES];
static uint8_t s_opaque[NES_MAX_RENDER_WIDTH * 240];
static uint64_t s_wide_frames, s_decode_errors, s_collision_reads, s_activation_reads, s_spawn_reads;
static unsigned s_terrain_pixels,s_terrain_diffs;

static int camera(void) { return (g_ram[0xdc] | (g_ram[0xdd] << 8)) - g_ram[0x3b]; }
static int world_x(int obj) { return (int16_t)(g_ram[0x83+obj] | (g_ram[0x8c+obj] << 8)); }
static int gameplay(void) {
    return s_ready && g_ram[0x42] < ROOMS && g_ram[0x41] == 0 &&
           g_ram[0x40] && (g_ram[0x48] & 0x80) && !(g_ram[0x3e] & 0x40) &&
           !(g_ram[0x36] & 0x40);
}
static int pause_panel(void) {
    /* The native full-submenu palettes use $0C in buffer $0110; the world
     * palettes restore $0F on return. Unlike
     * gameplay flags, this covers level/status/help as well as inventory
     * and passwords, and derives correctly from guest RAM on state load. */
    return (g_ram[0x3f]&0x20) && g_ram[0x110]==0x0c;
}
static uint8_t prg(int bank, unsigned addr) {
    if (addr >= 0xc000 && addr <= 0xffff) return s_rom[0x1c000 + addr - 0xc000];
    if (bank >= 0 && bank < 8 && addr >= 0x8000 && addr < 0xc000)
        return s_rom[bank * 0x4000 + addr - 0x8000];
    return 0;
}
static unsigned word(int bank, unsigned addr) { return prg(bank, addr) | (prg(bank, addr+1) << 8); }

/* The scrolling-room directory is fixed-bank C599, three bytes per room.
 * C602..C704 contains seven-byte page descriptors. C230 streams twenty rows
 * of tiles, C41C streams the attributes; both reference owner-ROM bank 0..3.
 * The remaining rooms are authored single-screen compositions, not repeated
 * scenery. They retain their native frame, centered in the adaptive viewport. */
static void decode_room(void) {
    s_room = g_ram[0x42]; s_pages = 0; s_left = 0; s_right = 256;
    memset(s_tiles, 0, sizeof s_tiles);
    memset(s_attributes, 0, sizeof s_attributes);
    unsigned directory = 0xc599 + s_room * 3;
    if (!(prg(7, directory+2) & 0x80)) return;
    unsigned first = word(7, directory), end = 0xc705;
    for (int room=0; room<ROOMS; room++) {
        unsigned p = word(7, 0xc599+room*3);
        if (p > first && p < end) end=p;
    }
    if (first < 0xc602 || end <= first || (end-first)%7) { s_decode_errors++; return; }
    s_pages = (int)((end-first)/7);
    if (s_pages > MAX_PAGES) { s_pages=0; s_decode_errors++; return; }
    /* The final corridor has four authored pages and a duplicate fifth page
     * for the native column stream's lookahead. The original right wall stops
     * Alex at X=1015. Cache capacity must not become another visible room. */
    if (s_room==0x20 && s_pages==5 &&
        !memcmp(s_rom+0x1c000+first-0xc000+21,
                s_rom+0x1c000+first-0xc000+28,7)) s_pages=4;
    for (int p=0; p<s_pages; p++) {
        unsigned desc = first+p*7;
        unsigned rows = word(7,desc), attrs = word(7,desc+2);
        int bank = prg(7,desc+6)&3;
        s_page_palette[p] = prg(7,desc+4);
        s_page_chr[p] = prg(7,desc+5);
        for (int y=4; y<24; y++) {
            unsigned row = word(bank,rows+y*2);
            if (row < 0x8000 || row > 0xbfe0 || attrs < 0x8000 || attrs > 0xbfc0) {
                s_pages=0; s_decode_errors++; return;
            }
            for (int x=0; x<32; x++) {
                s_tiles[p*32+x][y] = prg(bank,row+x);
                uint8_t a = prg(bank,attrs+(y/4)*8+x/4);
                s_attributes[p*32+x][y] = (a >> (((y&2)*2)+(x&2))) & 3;
            }
        }
    }
    s_right = s_pages*256;
}
static int view_left(int cam, int width) {
    int left = cam-(width-256)/2;
    if (s_right-s_left <= width) return s_left-(width-(s_right-s_left))/2;
    if (left < s_left) left=s_left;
    if (left > s_right-width) left=s_right-width;
    return left;
}
static uint32_t bg_pixel(int wx, int y, int *opaque) {
    *opaque=0;
    if (wx < s_left || wx >= s_right || y<32 || y>=192) return 0xff000000u;
    int p=wx/256, tile=s_tiles[wx/8][y/8], pal=s_attributes[wx/8][y/8];
    unsigned offset = PRG_SIZE+(s_page_chr[p]&0xfe)*1024+tile*16+(y&7);
    if (offset+8 >= sizeof s_rom) return 0xff000000u;
    int shift=7-(wx&7);
    int pixel=((s_rom[offset]>>shift)&1)|(((s_rom[offset+8]>>shift)&1)<<1);
    *opaque=pixel!=0;
    int color;
    if (s_page_palette[p] == g_ram[0x518]) color=g_ppu_pal[pixel ? pal*4+pixel : 0];
    else {
        unsigned palette=word(7,0xe6f1+s_page_palette[p]*2);
        color=prg(7,palette+(pixel ? pal*4+pixel : 0));
        if ((g_ram[0x3e]&2) && g_ram[0x692]<4 && color!=0x0f) {
            int brightness=g_ram[0x692]*16;
            if ((color&0x30)>=brightness) color=(color&15)|brightness;
        }
    }
    return g_nes_palette[color&63];
}

/* Decode ED0E..EF88's metasprite bytecode, including its linked streams,
 * per-character palettes, held objects and alternate face tiles. Signed world
 * coordinates replace only the final 8-bit screen clip. Guest RAM, OAM and
 * timing are untouched. Packets are promoted at the same DMA as native OAM. */
static void decode_packet(Packet *out) {
    const Source *src=&out->source;
    out->count=0; out->room=src->room; out->order=src->order;
    if (!src->valid) return;
    int type=src->type, anim=src->anim;
    if ((anim&0x7f)==0x7f || type>=0x40) return;
    unsigned table=word(3,0x8000+type*2), ptr=word(3,table+(anim&0x7f)*2);
    unsigned back=0, back_index=0, index=0;
    int flip=(anim&0x80)!=0;
    int wy=src->wy;
    for (int guard=0; guard<512; guard++) {
        if (ptr<0x8000 || ptr>0xbfff || index>255) break;
        int count=prg(3,ptr+index++), attr=0;
        unsigned attr_ptr=0;
        if (!count) return;
        if (count==0xff) {
            unsigned next=word(3,ptr+index); index+=2;
            back=ptr; back_index=index; ptr=next; index=0; continue;
        }
        if (count==0xfc) {
            if ((src->flags&0x40) &&
                (src->held_by>=4 || (src->held_state&0x7f)==0x15)) {
                unsigned list=ptr+index;
                back=word(3,list); back_index=0;
                ptr=word(3,list+2+2*(src->held_kind%5));
            } else ptr=word(3,ptr+index);
            index=0; continue;
        }
        if (count==0xfd) {
            count=prg(3,ptr+index++);
            unsigned list=ptr+index;
            int variant=src->variant;
            if (variant>2) variant=2;
            attr_ptr=word(3,list+2+variant*2);
            ptr=word(3,list); index=0;
        } else if (count==0xfe) {
            count=prg(3,ptr+index++);
            attr_ptr=word(3,ptr+index); index+=2;
        } else attr=prg(3,ptr+index++);
        unsigned tiles=word(3,ptr+index), offsets=word(3,ptr+index+2); index+=4;
        if (attr&0x80) attr=prg(7,0xef89+type);
        for (int n=0; n<count; n++) {
            if (out->count==TILES_PER_OBJECT) { s_decode_errors++; return; }
            int tile=prg(3,tiles+n);
            if (tile>=0x60 && tile<0x68 && type<8)
                tile=prg(7,0xef99+(tile-0x60)*5+src->variant);
            int dx=(int8_t)prg(3,offsets+n*2), dy=(int8_t)prg(3,offsets+n*2+1);
            Sprite *s=&out->tiles[out->count++];
            s->x=(int16_t)(src->x+(flip ? -dx-1 : dx)-4);
            s->y=(int16_t)(237-wy-dy);
            s->tile=(uint8_t)tile;
            s->attr=(uint8_t)((attr_ptr ? prg(3,attr_ptr+n) : attr)^(flip?0x40:0));
        }
        if (back) { ptr=back; index=back_index; back=0; }
    }
    out->count=0; s_decode_errors++;
}
static void capture_object(int obj) {
    if (obj<0 || obj>=OBJECTS) return;
    Source *src=&s_actors.shadow[obj].source;
    memset(src,0,sizeof *src);
    src->x=(int16_t)world_x(obj);
    src->wy=(int16_t)((g_ram[0x9e+obj] | (g_ram[0xa7+obj]<<8))+
                      (g_ram[0xb9+obj] | (g_ram[0xc2+obj]<<8)));
    src->order=++s_actors.sequence;
    src->type=g_ram[0xcb+obj]; src->anim=g_ram[0xd3+obj];
    src->variant=g_ram[0x48+obj]&0x7f; src->flags=g_ram[0x56+obj];
    src->held_by=g_ram[0x3b7+obj]; src->held_kind=g_ram[0x3b0+obj];
    if (src->held_by<OBJECTS) src->held_state=g_ram[0x4f+src->held_by];
    src->room=g_ram[0x42]; src->valid=1;
    decode_packet(&s_actors.shadow[obj]);
}
static int observe_sprite(uint16_t addr) {
    (void)addr;
    if (s_enabled && gameplay() && !pause_panel()) capture_object(g_ram[0x47]);
    return 0;
}
static int suppress_sprite(int slot, int x, int y, void *user) {
    (void)slot; (void)x; (void)user;
    return s_enabled && s_pages>0 && s_room==g_ram[0x42] &&
           ppu_renderer_in_custom_native_pass() && gameplay() &&
           !pause_panel() &&
           (!g_ram[0x3f] || (y>=32 && y<192));
}
void rcr_ws_dma(void) {
    if (!s_ready || !s_enabled || pause_panel()) return;
    if (s_actors.room != g_ram[0x42]) {
        memset(&s_actors,0,sizeof s_actors); s_actors.room=g_ram[0x42];
    }
    for (int obj=0; obj<OBJECTS; obj++) {
        if (!(g_ram[0x48+obj]&0x80)) {
            s_actors.shadow[obj].count=0; s_actors.shadow[obj].source.valid=0;
        }
        s_actors.present[obj]=s_actors.shadow[obj];
    }
}
static void draw_packet(uint32_t *out, int width, const Packet *packet) {
    if (packet->room != g_ram[0x42]) return;
    for (int n=0; n<packet->count; n++) {
        const Sprite *s=&packet->tiles[n];
        for (int y=0; y<8; y++) {
            int py=s->y+y;
            if (py<32 || py>=192) continue;
            int row=(s->attr&0x80)?7-y:y;
            int offset=0x1000+s->tile*16+row;
            for (int x=0; x<8; x++) {
                int px=s->x-s_view+x;
                if (px<0 || px>=width) continue;
                int bit=(s->attr&0x40)?x:7-x;
                int c=((g_chr_ram[offset]>>bit)&1)|(((g_chr_ram[offset+8]>>bit)&1)<<1);
                if (!c || ((s->attr&0x20)&&s_opaque[py*width+px])) continue;
                out[py*width+px]=g_nes_palette[g_ppu_pal[0x10+(s->attr&3)*4+c]&63];
            }
        }
    }
}
static int render(uint32_t *out, int width, int height, int native_x0,
                  const uint32_t *native, void *user) {
    (void)height; (void)user;
    if (!s_enabled || !s_ready) return 0;
    if (pause_panel()) {
        /* Full pause submenus replace the world with a flat panel. Extend
         * its blank right border across the viewport; keep native text and
         * cursor pixels centered at their original size. */
        for (int y=0; y<240; y++) {
            for (int x=0; x<width; x++) out[y*width+x]=native[y*256+255];
            memcpy(out+y*width+native_x0,native+y*256,256*sizeof(uint32_t));
        }
        s_wide_frames++;
        return 1;
    }
    if (!gameplay()) return 0;
    if (s_room!=g_ram[0x42]) decode_room();
    if (!s_pages) return 0;
    s_camera=camera(); s_view=view_left(s_camera,width);
    for (int y=0; y<240; y++) for (int x=0; x<width; x++) {
        int opaque;
        out[y*width+x]=bg_pixel(s_view+x,y,&opaque);
        s_opaque[y*width+x]=(uint8_t)opaque;
    }
    int play_x0=s_camera-s_view;
    s_terrain_pixels=s_terrain_diffs=0;
    if (!(g_ram[0x3e]&2) && !g_ram[0x3f] && !g_ram[0x36])
        for (int y=32; y<192; y++) for (int x=8; x<248; x++) {
            int opaque; uint32_t color=bg_pixel(s_camera+x,y,&opaque);
            s_terrain_pixels++;
            if (color!=native[y*256+x]) s_terrain_diffs++;
        }
    /* Native background remains authoritative for live door/text edits and
     * split-screen scroll. HUD and pause/menu panels stay screen centered. */
    /* The NES's left-eight-pixel background mask is a hardware edge, not a
     * seam in the world. Keep the decoded background there inside a wide view. */
    for (int y=32; y<192; y++) for (int x=8; x<256; x++) {
        int px=play_x0+x;
        if (px>=0 && px<width) {
            out[y*width+px]=native[y*256+x];
            s_opaque[y*width+px]=(uint8_t)ppu_renderer_background_opaque(x,y);
        }
    }
    {
        int order[OBJECTS];
        for (int i=0; i<OBJECTS; i++) order[i]=i;
        for (int i=0; i<OBJECTS; i++) for (int j=i+1; j<OBJECTS; j++)
            if (s_actors.present[order[j]].order<s_actors.present[order[i]].order) {
                int t=order[i]; order[i]=order[j]; order[j]=t;
            }
        for (int i=0; i<OBJECTS; i++) draw_packet(out,width,&s_actors.present[order[i]]);
    }
    for (int y=0; y<32; y++)
        memcpy(out+y*width+native_x0,native+y*256,256*sizeof(uint32_t));
    for (int y=192; y<240; y++)
        memcpy(out+y*width+native_x0,native+y*256,256*sizeof(uint32_t));
    s_wide_frames++;
    return 1;
}

uint8_t rcr_ws_read(uint16_t pc, uint16_t addr, uint8_t value) {
    if (!s_enabled || !gameplay() || g_render_width<=256 || (addr!=0xdc && addr!=0xdd)) return value;
    if (s_room!=g_ram[0x42]) decode_room();
    if (!s_pages) return value;
    int origin=0,handled=0;
    if (g_current_bank==4 && (pc==0x82d6 || pc==0x82de)) {
        /* Hitboxes are translated into a common local frame per object pair,
         * so their 16-bit world positions work outside the old screen too.
         * The original boxes, attack rules and collision tests still run. */
        int obj=g_ram[0x1a];
        if (obj>=OBJECTS) return value;
        origin=world_x(obj)-64;
        /* The guest rejects an unsigned subtraction borrow before accepting
         * its local X. A negative origin wraps to $FFFF and clips Alex at
         * the room's left edge despite an otherwise valid local position. */
        if (origin<0) origin=0;
        handled=1; s_collision_reads++;
    } else if (g_current_bank==4 && (pc==0xb4af || pc==0xb4b5 || pc==0xbc19 || pc==0xbc1f)) {
        int obj=g_cpu.X;
        if (obj>=OBJECTS) return value;
        int wx=world_x(obj), left=view_left(camera(),g_render_width);
        origin=wx-((wx>=left+16 && wx<left+g_render_width-16)?128:512);
        handled=1;
        if (pc==0xb4af || pc==0xb4b5) s_activation_reads++; else s_spawn_reads++;
    }
    if (!handled) return value;
    return (uint8_t)((uint16_t)origin>>(addr==0xdd?8:0));
}
static void apply(void) {
    if (!s_ready) return;
    nes_video_set_aspect_mode(s_enabled?s_aspect:NES_ASPECT_STOCK);
    ppu_renderer_set_custom_render(s_enabled?render:NULL,NULL);
    nes_mod_set_function_hook_enabled("rcr.widescreen.metasprite",s_enabled);
}
int rcr_ws_arg(const char *key, const char *value) {
    if (strcmp(key,"--widescreen") || !value) return 0;
    NesAspectMode mode;
    if (!nes_video_aspect_from_name(value,&mode)) return 0;
    s_enabled=mode!=NES_ASPECT_STOCK;
    if (s_enabled) s_aspect=mode;
    apply(); return 1;
}
void rcr_ws_frame(void) {
    if (s_ready && s_room!=g_ram[0x42] && g_ram[0x42]<ROOMS) {
        decode_room();
        memset(&s_actors,0,sizeof s_actors); s_actors.room=g_ram[0x42];
    }
}
typedef struct { Source shadow[OBJECTS],present[OBJECTS]; uint32_t sequence,room; } ActorSave;
static int state_get(uint8_t *buf, int cap) {
    if (cap<(int)sizeof(ActorSave)) return -1;
    ActorSave state={0};
    state.sequence=s_actors.sequence; state.room=s_actors.room;
    for (int i=0;i<OBJECTS;i++) {
        state.shadow[i]=s_actors.shadow[i].source; state.present[i]=s_actors.present[i].source;
    }
    memcpy(buf,&state,sizeof state); return sizeof state;
}
static int state_set(const uint8_t *buf, int len) {
    if (len!=sizeof(ActorSave)) return 0;
    ActorSave state; memcpy(&state,buf,sizeof state);
    if (state.room>=ROOMS) return 0;
    for (int i=0;i<OBJECTS;i++) {
        if (state.shadow[i].valid>1 || state.present[i].valid>1 ||
            state.shadow[i].type>=0x40 || state.present[i].type>=0x40) return 0;
    }
    memset(&s_actors,0,sizeof s_actors);
    s_actors.sequence=state.sequence; s_actors.room=(uint8_t)state.room;
    for (int i=0;i<OBJECTS;i++) {
        s_actors.shadow[i].source=state.shadow[i]; s_actors.present[i].source=state.present[i];
        decode_packet(&s_actors.shadow[i]); decode_packet(&s_actors.present[i]);
    }
    /* Terrain is derived from the ROM; rebuild without clearing restored actors. */
    decode_room(); return 1;
}
void rcr_ws_init(const char *rom_path) {
    FILE *f=rom_path?fopen(rom_path,"rb"):NULL;
    if (!f) { fprintf(stderr,"[Widescreen] Cannot read owner ROM\n"); return; }
    int ok=fseek(f,16,SEEK_SET)==0 && fread(s_rom,1,sizeof s_rom,f)==sizeof s_rom;
    fclose(f);
    if (!ok) { fprintf(stderr,"[Widescreen] Incomplete owner ROM\n"); return; }
    s_ready=1;
    nes_video_on_window_resized(1280,720);
    nes_mod_register_function_entry_plugin("rcr.widescreen.metasprite",0xed0e,observe_sprite);
    nes_mod_register_savestate_hook("rcr.widescreen.actors",state_get,state_set);
    ppu_renderer_set_sprite_suppress(suppress_sprite,NULL);
    apply();
    fprintf(stderr,"[Widescreen] Enhanced world renderer: %s\n",s_enabled?nes_video_aspect_name(s_aspect):"off");
}
int rcr_ws_debug(const char *cmd, int id, const char *json) {
    (void)json;
    int w,h;
    if (sscanf(cmd,"rcr_window_%dx%d",&w,&h)==2 && w>=256 && w<=7680 && h>=240 && h<=4320) {
        SDL_Window *window=SDL_GetWindowFromID(1);
        if (window) SDL_SetWindowSize(window,w,h);
        else nes_video_on_window_resized(w,h);
        debug_server_send_fmt("{\"id\":%d,\"ok\":true,\"window\":%s}",id,window?"true":"false"); return 1;
    }
    if (!strncmp(cmd,"rcr_aspect_",11)) {
        if (!rcr_ws_arg("--widescreen",cmd+11)) return 0;
        debug_server_send_fmt("{\"id\":%d,\"ok\":true}",id); return 1;
    }
    if (strcmp(cmd,"rcr_widescreen")) return 0;
    debug_server_send_fmt("{\"id\":%d,\"ok\":true,\"width\":%d,\"room\":%d,\"pages\":%d,\"camera\":%d,\"view\":%d,\"wide_frames\":%llu,\"decode_errors\":%llu,\"collision_reads\":%llu,\"activation_reads\":%llu,\"spawn_reads\":%llu,\"sprites\":[%u,%u,%u,%u,%u,%u,%u],\"terrain_pixels\":%u,\"terrain_diffs\":%u,\"pause_panel\":%u}",
        id,g_render_width,s_room,s_pages,s_camera,s_view,(unsigned long long)s_wide_frames,
        (unsigned long long)s_decode_errors,(unsigned long long)s_collision_reads,
        (unsigned long long)s_activation_reads,(unsigned long long)s_spawn_reads,
        s_actors.present[0].count,s_actors.present[1].count,s_actors.present[2].count,
        s_actors.present[3].count,s_actors.present[4].count,s_actors.present[5].count,s_actors.present[6].count,
        s_terrain_pixels,s_terrain_diffs,(unsigned)pause_panel());
    return 1;
}
