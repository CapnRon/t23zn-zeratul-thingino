CROSS_COMPILE ?= $(TC)
export ARCH = mips
export CROSS_COMPILE

TARGET ?= os02g10
KDIR   ?= $(KERNEL_DIR)
MODULE_NAME := sensor_$(TARGET)_t23
EXTRA_CFLAGS += -I$(PWD)/../include

ifeq ($(strip $(KDIR)),)
$(error KDIR is not set: pass KDIR=/path/to/zeratul-kernel or KERNEL_DIR=...)
endif
ifeq ($(strip $(CROSS_COMPILE)),)
$(error CROSS_COMPILE is not set: pass CROSS_COMPILE=/path/to/toolchain-prefix or TC=...)
endif

all: modules
.PHONY: modules clean release

$(MODULE_NAME)-objs := $(TARGET).o
obj-m := $(MODULE_NAME).o

modules:
	@$(MAKE) -C $(KDIR) M=$(shell pwd) $@

clean:
	@rm -rf *.o *~ .depend .*.cmd *.mod.c .tmp_versions *.ko *.symvers modules.order

release:
	cp $(TARGET).o $(KDIR)/arch/mips/xburst/lib/isp-t23/$(TARGET).hex
	@echo "installed $(KDIR)/arch/mips/xburst/lib/isp-t23/$(TARGET).hex"
