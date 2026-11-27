# Cross-compile for the vendor MIPS/uClibc userland (matches the stock rootfs).
# Default prefix; override with CROSS=.../mips-linux-uclibc-
CROSS ?= /root/a1-work/sdk/toolchain/mips-gcc540-uclibc0.9.33.2-64bit-r3.3.0.smaller/bin/mips-linux-uclibc-
CC    := $(CROSS)gcc
CFLAGS ?= -O2 -Wall -Wextra
LDFLAGS ?= -ldl

all: zrt-wake-prov

zrt-wake-prov: zrt-wake-prov.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -f zrt-wake-prov

.PHONY: all clean
