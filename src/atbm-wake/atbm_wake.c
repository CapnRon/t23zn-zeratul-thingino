#include <arpa/inet.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define ATBM_IOCTL 121
#define ATBM_WKUP_EVENT _IOW(ATBM_IOCTL, 40, unsigned int)
#define ATBM_NETPATTERN_ADD _IOW(ATBM_IOCTL, 41, unsigned int)
#define ATBM_NETPATTERN_DEL _IOW(ATBM_IOCTL, 42, unsigned int)
#define ATBM_SET_WK_SSID _IOW(ATBM_IOCTL, 47, unsigned int)
#define ATBM_CLR_WK_SSID _IOW(ATBM_IOCTL, 48, unsigned int)

enum {
	WAKEUP_IO = 0,
	WAKEUP_NETWORK,
	WAKEUP_CONNECT,
	WAKEUP_KEEPALIVE,
	WAKEUP_TCP_NETPATTERN,
	WAKEUP_UDP_NETPATTERN,
	WAKEUP_WK_SSID,
	WAKEUP_MAGIC_PKT,
};

struct netpattern_req {
	uint32_t status;
	uint32_t netpattern_index;
	uint8_t netpattern_data[64];
	uint32_t netpattern_len;
	uint32_t src_ipaddr;
	uint16_t src_port;
	uint8_t protocol;
	uint8_t reserved[1];
};

struct wakeup_ssid_req {
	uint32_t status;
	uint8_t ssid[32];
	uint8_t ssid_len;
	uint8_t reserved[3];
};

static int open_dev(void)
{
	int fd = open("/dev/atbm_ioctl", O_RDWR);
	if (fd < 0)
		perror("open /dev/atbm_ioctl");
	return fd;
}

static int cmd_add(int fd, int idx, const char *ip, int port,
		   const char *proto, const char *pattern)
{
	struct netpattern_req r;
	size_t len = strlen(pattern);

	if (idx < 0 || idx >= 4 || len > 63)
		return -1;
	memset(&r, 0, sizeof(r));
	r.netpattern_index = idx;
	r.src_ipaddr = inet_addr(ip);
	if (r.src_ipaddr == 0xffffffff)
		return -1;
	r.src_port = port;
	r.protocol = strcmp(proto, "TCP") == 0 ? 1 : 0;
	r.netpattern_len = len;
	memcpy(r.netpattern_data, pattern, len);
	if (ioctl(fd, ATBM_NETPATTERN_ADD, &r) < 0) {
		perror("ATBM_NETPATTERN_ADD");
		return -1;
	}
	return 0;
}

static int cmd_del(int fd, int idx)
{
	struct netpattern_req r;
	memset(&r, 0, sizeof(r));
	r.netpattern_index = idx;
	if (ioctl(fd, ATBM_NETPATTERN_DEL, &r) < 0) {
		perror("ATBM_NETPATTERN_DEL");
		return -1;
	}
	return 0;
}

static int cmd_event(int fd, unsigned int event)
{
	if (ioctl(fd, ATBM_WKUP_EVENT, event) < 0) {
		perror("ATBM_WKUP_EVENT");
		return -1;
	}
	return 0;
}

static int cmd_ssid(int fd, int set, const char *ssid)
{
	struct wakeup_ssid_req r;
	size_t len = strlen(ssid);
	if (len > 32)
		return -1;
	memset(&r, 0, sizeof(r));
	r.ssid_len = len;
	memcpy(r.ssid, ssid, len);
	if (ioctl(fd, set ? ATBM_SET_WK_SSID : ATBM_CLR_WK_SSID, &r) < 0) {
		perror(set ? "ATBM_SET_WK_SSID" : "ATBM_CLR_WK_SSID");
		return -1;
	}
	return 0;
}

static void usage(const char *p)
{
	fprintf(stderr,
		"usage: %s arm [pattern]\n"
		"       %s disarm\n"
		"       %s event TCP|UDP|MAGIC|SSID|NONE\n"
		"       %s add <index> <ip> <port> <TCP|UDP> <pattern>\n"
		"       %s del <index>\n"
		"       %s ssid <ssid>\n"
		"       %s clear-ssid <ssid>\n", p,p,p,p,p,p,p);
}

int main(int argc, char **argv)
{
	int fd, rc = 0;
	if (argc < 2) { usage(argv[0]); return 2; }
	fd = open_dev();
	if (fd < 0) return 1;

	if (strcmp(argv[1], "arm") == 0) {
		const char *pattern = argc > 2 ? argv[2] : "GET /";
		if (cmd_add(fd, 0, "0.0.0.0", 0, "TCP", pattern) < 0)
			rc = 1;
		else if (cmd_event(fd, WAKEUP_TCP_NETPATTERN) < 0)
			rc = 1;
	} else if (strcmp(argv[1], "disarm") == 0) {
		cmd_event(fd, 0);
		cmd_del(fd, 0);
	} else if (strcmp(argv[1], "event") == 0 && argc > 2) {
		unsigned int e = 0;
		if (strcmp(argv[2], "TCP") == 0) e = WAKEUP_TCP_NETPATTERN;
		else if (strcmp(argv[2], "UDP") == 0) e = WAKEUP_UDP_NETPATTERN;
		else if (strcmp(argv[2], "MAGIC") == 0) e = WAKEUP_MAGIC_PKT;
		else if (strcmp(argv[2], "SSID") == 0) e = WAKEUP_WK_SSID;
		else if (strcmp(argv[2], "NONE") == 0) e = 0;
		else { usage(argv[0]); close(fd); return 2; }
		rc = cmd_event(fd, e) < 0;
	} else if (strcmp(argv[1], "add") == 0 && argc == 7) {
		rc = cmd_add(fd, atoi(argv[2]), argv[3], atoi(argv[4]),
			     argv[5], argv[6]) < 0;
	} else if (strcmp(argv[1], "del") == 0 && argc > 2) {
		rc = cmd_del(fd, atoi(argv[2])) < 0;
	} else if (strcmp(argv[1], "ssid") == 0 && argc > 2) {
		rc = cmd_ssid(fd, 1, argv[2]) < 0;
	} else if (strcmp(argv[1], "clear-ssid") == 0 && argc > 2) {
		rc = cmd_ssid(fd, 0, argv[2]) < 0;
	} else {
		usage(argv[0]);
		rc = 2;
	}
	close(fd);
	return rc;
}
