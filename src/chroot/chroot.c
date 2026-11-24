#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
	if (argc < 3) {
		fprintf(stderr, "usage: chroot NEWROOT COMMAND [ARG...]\n");
		return 2;
	}
	if (chroot(argv[1]) != 0) {
		perror("chroot");
		return 1;
	}
	if (chdir("/") != 0) {
		perror("chdir");
		return 1;
	}
	execv(argv[2], &argv[2]);
	perror("execv");
	return 1;
}
