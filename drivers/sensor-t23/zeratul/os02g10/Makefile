CROSS_COMPILE ?= /root/a1-work/sdk/toolchain/mips-gcc540-uclibc0.9.33.2-64bit-r3.3.0.smaller/bin/mips-linux-uclibc-
export ARCH=mips
export CROSS_COMPILE

TARGET=os02g10
KDIR := /root/a1-work/sdk/kernel/kernel
MODULE_NAME := sensor_$(TARGET)_t23
EXTRA_CFLAGS += -I$(PWD)/../include

all: modules
.PHONY: modules clean
$(MODULE_NAME)-objs := $(TARGET).o
obj-m := $(MODULE_NAME).o
modules:
	@$(MAKE) -C $(KDIR) M=$(shell pwd) $@
clean:
	@rm -rf *.o *~ .depend .*.cmd *.mod.c .tmp_versions *.ko *.symvers modules.order
release:
	cp $(TARGET).o $(KDIR)/arch/mips/xburst/lib/isp-t23/$(TARGET).hex
