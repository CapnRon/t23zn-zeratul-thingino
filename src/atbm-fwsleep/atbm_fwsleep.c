#include <fcntl.h>
#include <stdio.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define ATBM_IOCTL 121
#define ATBM_FW_SLEEP _IO(ATBM_IOCTL, 31)

int main(void)
{
	int fd;

	fd = open("/dev/atbm_ioctl", O_RDWR);
	if (fd < 0) {
		perror("open /dev/atbm_ioctl");
		return 1;
	}

	if (ioctl(fd, ATBM_FW_SLEEP) < 0) {
		perror("ATBM_FW_SLEEP");
		close(fd);
		return 1;
	}

	close(fd);
	return 0;
}
