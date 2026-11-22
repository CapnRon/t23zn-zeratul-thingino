#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define ATBM_IOCTL 121
#define ATBM_STATUS _IOR(ATBM_IOCTL, 2, unsigned int)

struct __attribute__((packed)) host_connect_event {
	uint8_t ssid[32];
	uint8_t ssidlen;
	uint8_t bssid[6];
	uint8_t crypto_pairwise;
	uint8_t crypto_group;
	uint8_t keymgmt;
	uint8_t bgnMode;
	uint8_t connect_flag;
	uint32_t ipaddr;
	uint32_t ipmask;
	uint32_t gwaddr;
	uint32_t dnsaddr[2];
};

struct __attribute__((packed)) status_info {
	uint32_t msgflag;
	uint8_t macaddr[6];
	uint8_t bconnect;
	uint8_t TxBAMap;
	uint8_t RxBAMap;
	uint8_t reserved[3];
	uint8_t InputbufferNum;
	uint8_t wifimode;
	uint8_t reserved1[2];
	uint32_t NumOfHwXmitedAddr;
	uint32_t firmwareVersion;
	uint32_t firmwareCap;
	struct host_connect_event con_event;
};

static void print_ip(const char *name, uint32_t v)
{
	const unsigned char *p = (const unsigned char *)&v;
	printf("%s=%u.%u.%u.%u\n", name, p[0], p[1], p[2], p[3]);
}

int main(void)
{
	static unsigned char buf[4096];
	struct status_info *st = (struct status_info *)buf;
	int fd, ret;

	_Static_assert(sizeof(struct status_info) == 96, "status_info layout");
	_Static_assert(__builtin_offsetof(struct status_info, wifimode) == 17, "wifimode offset");
	_Static_assert(__builtin_offsetof(struct status_info, bconnect) == 10, "bconnect offset");
	_Static_assert(__builtin_offsetof(struct status_info, con_event) == 32, "con_event offset");

	memset(buf, 0, sizeof(buf));
	fd = open("/dev/atbm_ioctl", O_RDWR);
	if (fd < 0) {
		perror("open /dev/atbm_ioctl");
		return 2;
	}
	ret = ioctl(fd, ATBM_STATUS, buf);
	close(fd);
	if (ret < 0) {
		perror("ioctl ATBM_STATUS");
		return 3;
	}
	printf("mode=%s\n", st->wifimode ? "AP" : "STA");
	printf("connected=%u\n", st->bconnect);
	printf("ssid=%.*s\n", st->con_event.ssidlen > 32 ? 32 : st->con_event.ssidlen, st->con_event.ssid);
	print_ip("ip", st->con_event.ipaddr);
	print_ip("mask", st->con_event.ipmask);
	print_ip("gw", st->con_event.gwaddr);
	printf("mac=%02x:%02x:%02x:%02x:%02x:%02x\n",
	       st->macaddr[0], st->macaddr[1], st->macaddr[2],
	       st->macaddr[3], st->macaddr[4], st->macaddr[5]);
	return 0;
}
