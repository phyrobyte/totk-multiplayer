/*
 * TOTK Multiplayer — thin memory-pipe sysmodule (SKELETON)
 * -------------------------------------------------------
 * Runs in the background under Atmosphere alongside TOTK. Its ONLY jobs:
 *   1. read a region of the game's RAM,
 *   2. send it to the PC over UDP as a wire-protocol v0 RAW_REGION packet,
 *   3. receive packets from the PC and write the "ghost" data back into RAM.
 *
 * All logic lives on the PC. This file stays tiny and rarely changes.
 *
 * STATUS: skeleton. Compiles later with devkitPro + libnx. The memory read/write
 * calls are stubbed with TODOs — they get wired to Atmosphere's dmnt:cht service
 * (ReadCheatProcessMemory / WriteCheatProcessMemory) once the console is modded and
 * addresses are confirmed. Packet layout MUST stay byte-identical to
 * pc-tools/protocol.py and config/protocol.md.
 */
#include <string.h>
#include <switch.h>

// ---- wire protocol v0 (mirror of pc-tools/protocol.py) ----
#define TOTK_MAGIC      "TOTK"
#define TOTK_PROTO_VER  0
#define MSG_RAW_REGION  1
#define MSG_STRUCTURED  2
#define MSG_TAG         3

#define PC_HOST   "192.168.1.100"   // TODO: PC/server IP
#define PC_PORT   9917
#define PLAYER_ID 1

// The player memory block to stream. Filled from addresses.1.2.1.json in Phase 2.
#define REGION_BASE 0x0            // TODO: resolve via pointer chain (ASLR-safe)
#define REGION_SIZE 128            // TODO: match addresses.1.2.1.json region.size

#pragma pack(push, 1)
typedef struct {
    char     magic[4];
    uint8_t  proto_ver;
    uint8_t  msg_type;
    uint8_t  player_id;
    uint8_t  flags;
    uint32_t seq;
    double   t_send;
    uint32_t region_off;
    uint16_t length;
} totk_header_t;      // 26 bytes, matches struct.Struct("<4sBBBBIdIH")
#pragma pack(pop)

// ---- memory access stubs (wire to dmnt:cht later) ----
static Result read_game_memory(uint64_t addr, void *out, size_t len) {
    // TODO: dmntchtReadCheatProcessMemory(addr, out, len) after attaching to TOTK.
    memset(out, 0, len);
    return 0;
}

static Result write_game_memory(uint64_t addr, const void *in, size_t len) {
    // TODO: dmntchtWriteCheatProcessMemory(addr, in, len). Validate ranges first
    // (never poke garbage — see ROADMAP robustness rule #6).
    (void)addr; (void)in; (void)len;
    return 0;
}

// ---- networking ----
static int udp_open(struct sockaddr_in *dst) {
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) return -1;
    memset(dst, 0, sizeof(*dst));
    dst->sin_family = AF_INET;
    dst->sin_port = htons(PC_PORT);
    dst->sin_addr.s_addr = inet_addr(PC_HOST);
    return fd;
}

static void send_region(int fd, struct sockaddr_in *dst, uint32_t seq,
                        const uint8_t *region, uint16_t size) {
    uint8_t pkt[sizeof(totk_header_t) + REGION_SIZE];
    totk_header_t *h = (totk_header_t *)pkt;
    memcpy(h->magic, TOTK_MAGIC, 4);
    h->proto_ver = TOTK_PROTO_VER;
    h->msg_type  = MSG_RAW_REGION;
    h->player_id = PLAYER_ID;
    h->flags     = 0;
    h->seq       = seq;
    h->t_send    = 0.0;              // TODO: monotonic seconds
    h->region_off = REGION_BASE;
    h->length    = size;
    memcpy(pkt + sizeof(totk_header_t), region, size);
    sendto(fd, pkt, sizeof(totk_header_t) + size, 0,
           (struct sockaddr *)dst, sizeof(*dst));
}

// ---- main loop ----
int main(int argc, char **argv) {
    (void)argc; (void)argv;
    socketInitializeDefault();

    struct sockaddr_in dst;
    int fd = udp_open(&dst);

    uint8_t region[REGION_SIZE];
    uint32_t seq = 0;

    while (true) {
        // 1. read the player block out of TOTK's RAM
        read_game_memory(REGION_BASE, region, REGION_SIZE);

        // 2. ship it to the PC
        if (fd >= 0) send_region(fd, &dst, seq++, region, REGION_SIZE);

        // 3. TODO: recv ghost packets from PC and write_game_memory() into a
        //    hijacked actor slot (Phase 3/4).

        svcSleepThread(16'000'000ULL);   // ~60 Hz
    }

    socketExit();
    return 0;
}
