/*
 * zrt-wake-prov — provision the ATBM6461 MCU keepalive from Thingino.
 *
 * Sends RTOS cmd 0x3f (keeplive_set_config2) with the 0x50-byte struct:
 *   +0x00 device_id[32]
 *   +0x20 device_mode[32]
 *   +0x40 vendor_code[4]
 *   +0x44 ip (u32, network order)
 *   +0x48 port (u16, host order)
 *
 * Identity is read (in order) from:
 *   env ZRT_DEVICE_ID / ZRT_VENDOR_CODE / ZRT_DEVICE_MODE
 *   /tmp/usr_params   (stock vendor)
 *   /proc/cmdline     (tag blob: device_id=...;vendor_code=...;device_mode=...)
 *
 * Usage: zrt-wake-prov [dashboard-ip] [dashboard-port]
 */

#include <arpa/inet.h>
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CFG2_SIZE 0x50

struct __attribute__((packed)) keeplive_cfg2 {
    char device_id[32];
    char device_mode[32];
    char vendor_code[4];
    uint32_t ip;
    uint16_t port;
    uint8_t pad[6];
};

typedef int (*init_fn)(void);
typedef int (*send_fn)(int, void *, int, void *, int, int);

static int get_kv(const char *buf, const char *key, char *out, size_t n)
{
    const char *p = buf;
    size_t klen = strlen(key);
    while ((p = strstr(p, key)) != NULL) {
        if ((p == buf || p[-1] == ';' || p[-1] == ' ' || p[-1] == '\n') &&
            p[klen] == '=') {
            p += klen + 1;
            size_t i = 0;
            while (*p && *p != ';' && *p != '\n' && *p != '\r' && i + 1 < n)
                out[i++] = *p++;
            out[i] = '\0';
            return 0;
        }
        p += klen;
    }
    return -1;
}

static int read_file(const char *path, char *dst, size_t n)
{
    FILE *f = fopen(path, "rb");
    if (!f)
        return -1;
    size_t r = fread(dst, 1, n - 1, f);
    fclose(f);
    dst[r] = '\0';
    return 0;
}

static void find_identity(const char *key_env, const char *key_kv,
                          char *out, size_t n)
{
    const char *env = getenv(key_env);
    if (env && *env) {
        snprintf(out, n, "%s", env);
        return;
    }
    static char cmdline[4096];
    static char params[4096];
    static int loaded = 0;
    if (!loaded) {
        read_file("/proc/cmdline", cmdline, sizeof(cmdline));
        read_file("/tmp/usr_params", params, sizeof(params));
        loaded = 1;
    }
    if (get_kv(params, key_kv, out, n) == 0 && *out)
        return;
    if (get_kv(cmdline, key_kv, out, n) == 0 && *out)
        return;
    out[0] = '\0';
}

int main(int argc, char **argv)
{
    const char *server = argc > 1 ? argv[1] : "192.168.2.127";
    int port = argc > 2 ? atoi(argv[2]) : 12911;

    struct keeplive_cfg2 cfg;
    memset(&cfg, 0, sizeof(cfg));

    find_identity("ZRT_DEVICE_ID", "device_id", cfg.device_id, sizeof(cfg.device_id));
    find_identity("ZRT_DEVICE_MODE", "device_mode", cfg.device_mode, sizeof(cfg.device_mode));
    find_identity("ZRT_VENDOR_CODE", "vendor_code", cfg.vendor_code, sizeof(cfg.vendor_code));

    if (!cfg.device_id[0]) {
        fprintf(stderr, "zrt-wake-prov: device_id not found\n");
        return 2;
    }
    cfg.ip = inet_addr(server);
    if (cfg.ip == (uint32_t)-1) {
        fprintf(stderr, "zrt-wake-prov: bad server ip '%s'\n", server);
        return 2;
    }
    cfg.port = (uint16_t)port;

    void *h = dlopen("librtos.so", RTLD_NOW);
    if (!h)
        h = dlopen("/usr/lib/librtos.so", RTLD_NOW);
    if (!h) {
        fprintf(stderr, "zrt-wake-prov: dlopen librtos.so: %s\n", dlerror());
        return 3;
    }
    init_fn init = (init_fn)dlsym(h, "rtos_cmd_init");
    send_fn send = (send_fn)dlsym(h, "rtos_cmd_send");
    if (!send) {
        fprintf(stderr, "zrt-wake-prov: dlsym rtos_cmd_send failed\n");
        return 3;
    }
    if (init)
        init();

    int ret = send(0x3f, &cfg, CFG2_SIZE, NULL, 0, 3000);
    printf("cmd3f ip=%s port=%d did=%s mode=%s code=%s ret=%d\n",
           server, port, cfg.device_id, cfg.device_mode, cfg.vendor_code, ret);
    return ret < 0 ? 4 : 0;
}
