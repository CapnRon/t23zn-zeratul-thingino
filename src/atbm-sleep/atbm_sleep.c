#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define ATBM_PS_SET 0x80017900UL
#define ATBM_PRIV_IOCTL_7926 0x20007926UL
#define ATBM_PRIV_IOCTL_791F 0x2000791FUL

struct powersave_mode {
	uint32_t status;
	uint32_t flags;
	uint8_t powersave_mode;
	uint8_t powerave_level;
	uint16_t fastsleep_time;
};

int main(void)
{
	int fd, ret = 0;
	struct powersave_mode ps;

	fd = open("/dev/atbm_ioctl", O_RDWR);
	if (fd < 0) {
		perror("open /dev/atbm_ioctl");
		return 1;
	}

	memset(&ps, 0, sizeof(ps));
	ps.powersave_mode = 2;
	ps.powerave_level = 1;

	if (ioctl(fd, ATBM_PS_SET, &ps) < 0) {
		perror("ATBM_PS_SET");
		ret = 1;
	} else {
		ioctl(fd, ATBM_PRIV_IOCTL_7926, 0);
		ioctl(fd, ATBM_PRIV_IOCTL_791F, 0);
	}

	close(fd);
	return ret;
}
