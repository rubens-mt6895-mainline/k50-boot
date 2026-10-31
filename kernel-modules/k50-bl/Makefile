# K50 亮度桥接模块：外部模块，编进「构建当前运行内核」所用的同一份内核源码树
# 构建（内核树与其 .config 必须与运行内核对应，见 k50-boot 仓库的 kernel_ref / defconfig）：
#   make ARCH=arm64 LLVM=1 -C <内核源码树> M=<本目录> modules
obj-m := k50_bl.o
KDIR  ?= /lib/modules/$(shell uname -r)/build

all:
	$(MAKE) -C $(KDIR) ARCH=arm64 LLVM=1 M=$(CURDIR) modules

clean:
	$(MAKE) -C $(KDIR) ARCH=arm64 LLVM=1 M=$(CURDIR) clean

.PHONY: all clean
