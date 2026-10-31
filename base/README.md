# base/ —— boot 分区基线镜像

`base/boot.img` 就在仓库里：21,364,736 字节，
sha256 `5e4cad61e5d13139067b1c945d68fd2abdcb78cf61724ab0db70c0a459c25ce8`。
内核段是 `7.2.0-g0b8dd2e87b3d-dirty`，ramdisk 是厂商 CINIT 那份。

那 1.4 MB ramdisk 是小米/MTK 的二进制。跟着仓库一起发，口径和
[k50-firmware](https://github.com/rubens-mt6895-mainline/k50-firmware) 一样：
原样转载、不做权利主张、被投诉就删。不想让它出现在你的公开 fork 里，看最下面。

## 为什么非要一份基线

K50（rubens / MT6895）的 `boot_a` 是 MTK boot image v4：

```
[0x0000, 0x1000)  头部（kernel_size@8 决定内核段长度，page_size@1580 = 0）
[0x1000, ...)     内核段（gzip 过的 Image），长度 = kernel_size
                  ramdisk 起点 = align_up(0x1000 + kernel_size, 4096)   ← LK 这样推
                  ramdisk 段（厂商固件，约 1.4 MB gz）
尾部              零填充到分区大小
```

内核和 ramdisk 挤在同一个镜像里，头部又没有偏移字段可写。所以只能拿一份已知能开机的
`boot_a` 当基线，只换内核段、其余逐字节不动 —— `scripts/k50-pack-boot.py` 的 Option B。

反面教材：重新生成 ramdisk、或者挪 ramdisk 偏移，一共翻车过 6 次
（过 DRM 后静默重启、反复重启）。所以打包器默认拒绝挪偏移，宁可报错。

## 余量

头部 `kernel_size` 是硬上限：**19,968,647 字节**。
现在这套配置 gzip 出来 19,946,249，余量 **22,398 字节**。
内核再长一点，打包就会失败 —— 这是故意的，不是 bug。

## 换成自己机器的

```bash
dd if=/dev/sdc43 of=/root/boot_backup.img bs=1M      # K50 上 boot_a = /dev/sdc43
adb pull /root/boot_backup.img base/boot.img
```

或者以前存过备份也行：任何一份确认能开机的 `boot_a`（分区 64 MiB，dump 出来 67,108,864 字节）。

校验：

```bash
ls -l base/boot.img        # 仓库自带那份是 21,364,736 字节
head -c8 base/boot.img     # ANDROID!
sha256sum base/boot.img    # 构建日志里会再核对一次
```

## 不想提交这份文件

- 跑 workflow 时把 `base_url` 填成能直接下载到 `boot.img` 的链接，仓库里有文件就不下载；
- 或者删掉 `base/boot.img`、`pack_boot=no`，只出内核产物。

## 不打包 boot.img 也能用

```
Image      未压缩内核
Image.gz   压缩内核（可以自己塞进任何镜像格式）
*.dtb      设备树
config     本次实际用的内核配置
```

这些足够自己打包，或者单纯验证某个补丁的效果。
