# base/ —— 放你自己设备的 boot_a 基线镜像

`boot.img` 不进 git（见 `.gitignore`）：它是你设备的厂商镜像，里面那 1.4 MB
ramdisk 装的是小米/MTK 的厂商固件二进制，不该被公开再分发。

## 为什么需要它

K50（rubens / MT6895）的 `boot_a` 是 MTK boot image v4：

```
[0x0000, 0x1000)  头部（kernel_size@8 决定内核段长度，page_size@1580 = 0）
[0x1000, ...)     内核段（gzip 过的 Image），长度 = kernel_size
                  ramdisk 起点 = align_up(0x1000 + kernel_size, 4096)   ← LK 这样推
                  ramdisk 段（厂商固件，约 1.4 MB gz）
尾部              零填充到 64 MiB
```

也就是说**内核和 ramdisk 在同一个镜像里**，没有偏移字段可写。所以要让新内核
能被 LK 正确引导，只能：拿一份**已知能正常开机**的 `boot_a` 当基线，只替换
内核段、其余逐字节不动（`scripts/k50-pack-boot.py` 干的就是这件事，写在
Option B 里）。

反面教材（真的翻过车）：重新生成 ramdisk、或挪动 ramdisk 偏移，一共导致过
6 次"过 DRM 后静默重启/反复重启"。所以打包器默认拒绝挪偏移。

## 怎么拿到 boot_a

### 方式 1：从设备 dump（需要 root）

```bash
adb shell su -c 'dd if=/dev/block/by-name/boot_a of=/sdcard/boot.img'
adb pull /sdcard/boot.img base/boot.img
```

或者直接在设备上：

```bash
dd if=/dev/sdc43 of=/root/boot_backup.img bs=1M      # K50 上 boot_a = /dev/sdc43
```

### 方式 2：用以前存的备份

任何一份**确认能开机**的 `boot_a` 备份都行（64 MiB / 67,108,864 字节）。

## 校验

```bash
ls -l base/boot.img            # 应为 67108864 字节
head -c8 base/boot.img         # 应打印 ANDROID!
sha256sum base/boot.img        # 记下来，构建日志里会再核对一次
```

## 我不想把它放进公开 fork

两条路，任选：

**A. 不提交文件，构建时给链接**（推荐）

在仓库页面 `Actions → build-kernel → Run workflow`，把 `base_url` 填成任意一个
能直接下载到你那份 `boot.img` 的链接（你自己的私有 Release 资产、
对象存储的临时直链等）。工作流会先下载再打包。

**B. 提交进你的 fork**

```bash
git add -f base/boot.img       # 被 .gitignore 挡着，要 -f
git commit -m "add my boot_a baseline"
git push
```

只有在你能接受这份厂商 ramdisk 出现在自己公开 fork 里时才这么做。

## 不提供 boot.img 也能用

`pack_boot=no`，或没有基线文件时，工作流照样产出：

```
Image      未压缩内核
Image.gz   压缩内核（可自己塞进任何镜像格式）
*.dtb      设备树
config     本次实际使用的内核配置
```

这些足够你自己打包，或用来验证某个补丁的效果。
