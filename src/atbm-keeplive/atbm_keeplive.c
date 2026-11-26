#include <arpa/inet.h>
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

struct keeplive_cfg {
	uint32_t ip;
	uint16_t port;
	char payload[0x42];
	uint32_t payload_len;
} __attribute__((packed));

typedef void (*init_fn)(void);
typedef int (*send_fn)(int, void *, int, void *, int, int);

int main(int argc, char **argv)
{
	const char *ip = argc > 1 ? argv[1] : "192.168.2.127";
	int port = argc > 2 ? atoi(argv[2]) : 5001;
	const char *payload = argc > 3 ? argv[3] : "wakeup";
	struct keeplive_cfg cfg;
	void *h;
	init_fn init;
	send_fn send;
	int ret;

	if (strlen(payload) >= sizeof(cfg.payload)) {
		fprintf(stderr, "payload too long\n");
		return 1;
	}

	h = dlopen("librtos.so", RTLD_NOW);
	if (!h) {
		fprintf(stderr, "dlopen: %s\n", dlerror());
		return 1;
	}
	init = (init_fn)dlsym(h, "rtos_cmd_init");
	send = (send_fn)dlsym(h, "rtos_cmd_send");
	if (!init || !send) {
		fprintf(stderr, "dlsym: %s\n", dlerror());
		return 1;
	}

	memset(&cfg, 0, sizeof(cfg));
	cfg.ip = inet_addr(ip);
	cfg.port = (uint16_t)port;
	strcpy(cfg.payload, payload);
	cfg.payload_len = strlen(payload);

	init();
	usleep(200000);
	ret = send(4, &cfg, sizeof(cfg), NULL, 0, 3000);
	printf("cmd4 ip=%s port=%d payload=%s ret=%d\n", ip, port, payload, ret);
	return ret < 0 ? 1 : 0;
}
