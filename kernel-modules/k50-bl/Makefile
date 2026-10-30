# K50 亮度桥接模块：外部模块，编在用同一 .config 构建当前运行内核的树里
# 构建（在 WSL 里以 root 跑，树内文件是 root 所有）：
#   make -C /home/luis/work/k50-ccci ARCH=arm64 LLVM=1 M=$(pwd) modules
obj-m := k50_bl.o
KDIR  ?= /home/luis/work/k50-ccci

all:
	$(MAKE) -C $(KDIR) ARCH=arm64 LLVM=1 M=$(CURDIR) modules

clean:
	$(MAKE) -C $(KDIR) ARCH=arm64 LLVM=1 M=$(CURDIR) clean

.PHONY: all clean
