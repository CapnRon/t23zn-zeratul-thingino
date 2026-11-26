#include <arpa/inet.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define ATBM_IOCTL 121
#define ATBM_SET_FILTER _IOW(ATBM_IOCTL, 3, unsigned int)
#define ATBM_GET_FILTER _IOR(ATBM_IOCTL, 4, unsigned int)
#define FILTER_F_ARP 1
#define FILTER_F_DNS 4

struct tcp_filter_info {
	unsigned int status;
	unsigned short Flags;
	unsigned char src_cnt;
	unsigned char des_cnt;
	unsigned short src_tcpport[4];
	unsigned short des_tcpport[4];
} __attribute__((packed));

int main(int argc, char **argv)
{
	struct tcp_filter_info f;
	int fd, port = 55555;

	if (argc > 1)
		port = atoi(argv[1]);

	memset(&f, 0, sizeof(f));
	f.Flags = FILTER_F_ARP | FILTER_F_DNS;
	f.des_cnt = 1;
	f.des_tcpport[0] = htons(port);

	fd = open("/dev/atbm_ioctl", O_RDWR);
	if (fd < 0) {
		perror("open /dev/atbm_ioctl");
		return 1;
	}
	if (ioctl(fd, ATBM_SET_FILTER, &f) < 0) {
		perror("ATBM_SET_FILTER");
		close(fd);
		return 1;
	}
	close(fd);
	printf("filter set dport %d\n", port);
	return 0;
}
