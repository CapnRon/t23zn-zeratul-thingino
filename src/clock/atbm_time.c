#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/time.h>
#include <unistd.h>

#define ATBM_IOCTL 121
#define ATBM_TIME _IOR(ATBM_IOCTL, 35, unsigned int)

struct time_info {
	int tm_sec;
	int tm_min;
	int tm_hour;
	int tm_mday;
	int tm_mon;
	int tm_year;
	int tm_wday;
	int tm_yday;
	int tm_isdst;
};

struct time_info_req {
	unsigned int status;
	struct time_info time;
};

static long long days_from_civil(int y, unsigned m, unsigned d)
{
	y -= m <= 2;
	long long era = (y >= 0 ? y : y - 399) / 400;
	unsigned yoe = (unsigned)(y - era * 400);
	unsigned doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
	unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
	return era * 146097LL + (long long)doe - 719468;
}

int main(int argc, char **argv)
{
	int fd, set_clock = 0;
	long offset = 8 * 3600;
	struct time_info_req t;
	struct timeval tv;
	long long epoch;
	int opt;

	while ((opt = getopt(argc, argv, "so:")) != -1) {
		switch (opt) {
		case 's':
			set_clock = 1;
			break;
		case 'o':
			offset = strtol(optarg, NULL, 10);
			break;
		default:
			fprintf(stderr, "usage: %s [-s] [-o mcu_utc_offset_seconds]\n", argv[0]);
			return 2;
		}
	}

	memset(&t, 0, sizeof(t));
	fd = open("/dev/atbm_ioctl", O_RDWR);
	if (fd < 0) {
		perror("open /dev/atbm_ioctl");
		return 1;
	}
	if (ioctl(fd, ATBM_TIME, &t) != 0) {
		perror("ioctl ATBM_TIME");
		close(fd);
		return 1;
	}
	close(fd);

	printf("mcu=%04d-%02d-%02dT%02d:%02d:%02d status=%u offset=%ld\n",
	       t.time.tm_year + 1900, t.time.tm_mon + 1, t.time.tm_mday,
	       t.time.tm_hour, t.time.tm_min, t.time.tm_sec, t.status, offset);
	if (t.status != 0)
		return 1;

	epoch = days_from_civil(t.time.tm_year + 1900, t.time.tm_mon + 1,
				t.time.tm_mday) * 86400LL
		+ t.time.tm_hour * 3600LL + t.time.tm_min * 60LL + t.time.tm_sec
		- offset;

	if (set_clock) {
		tv.tv_sec = (time_t)epoch;
		tv.tv_usec = 0;
		if (settimeofday(&tv, NULL) != 0) {
			perror("settimeofday");
			return 1;
		}
		printf("utc=%lld\n", epoch);
	}
	return 0;
}
