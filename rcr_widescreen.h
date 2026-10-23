#pragma once
#include <stdint.h>
void rcr_ws_init(const char *rom_path);
int rcr_ws_arg(const char *key, const char *value);
void rcr_ws_frame(void);
void rcr_ws_dma(void);
uint8_t rcr_ws_read(uint16_t pc, uint16_t addr, uint8_t value);
int rcr_ws_debug(const char *cmd, int id, const char *json);
