# k50-boot — Redmi K50（rubens / MT6895）mainline 内核与 boot 镜像

[![build-kernel](https://github.com/rubens-mt6895-mainline/k50-boot/actions/workflows/build-kernel.yml/badge.svg)](https://github.com/rubens-mt6895-mainline/k50-boot/actions/workflows/build-kernel.yml)
[![release](https://img.shields.io/github/v/release/rubens-mt6895-mainline/k50-boot?include_prereleases)](https://github.com/rubens-mt6895-mainline/k50-boot/releases)
[![downloads](https://img.shields.io/github/downloads/rubens-mt6895-mainline/k50-boot/total)](https://github.com/rubens-mt6895-mainline/k50-boot/releases)

为 Redmi K50 编译 mainline 内核。
全在 GitHub Actions 上跑，产物发 Release。

**仓库里不放任何厂商二进制。** 内核和 ramdisk 在同一个 boot 镜像里，那份 ramdisk 装的是
小米/MTK 的固件（1.4 MB），不应该也不能公开再分发，所以基线镜像需要你自己提供，这个仓库只干一件事：
换掉内核段，其余字节一个都不动。

rootfs（Debian 13 + GNOME）在 [k50-rootfs](https://github.com/rubens-mt6895-mainline/k50-rootfs)。

## 下载

下载[Releases](https://github.com/rubens-mt6895-mainline/k50-boot/releases) 里 `ci-*` 最新的release：

| 文件 | 是什么 |
|---|---|
| `boot.img` | 可以直接刷的 boot 镜像（**只有构建时给了基线镜像才会出现**） |
| `Image` / `Image.gz` | 未压缩 / 压缩的内核 |
| `mt6895-xiaomi-rubens.dtb` | 设备树 |
| `kernel.config` | 这次实际用的内核配置 |
| `*.ko` | 外部模块（默认只有 `k50_bl.ko`，面板背光亮度） |
| `BUILD.txt` | 这次构建的全部参数（源码提交、补丁、工具链、sha256） |
| `SHA256SUMS.txt` | 校验和 |

内核段与设备无关，但 `boot.img` 里的 ramdisk 是**发布者的**。要把它刷到自己机器上，
正确的做法还是照下面自己编一份。

## 自己编

**① fork** 到您的账号。

**② 准备基线镜像**，二选一：

- 把自己设备的 `boot_a` dump 出来，放在 `base/boot.img`（怎么 dump、怎么校验见
  [`base/README.md`](base/README.md)）；
- 或者什么都不放，跑 workflow 时在 `base_url` 填一个能下到你手机boot镜像的直链。

**③ 跑 workflow**：`Actions → build-kernel → Run workflow`

| 输入 | 说明 |
|---|---|
| `pack_boot` | `auto`（有基线就打）/ `yes`（必须打）/ `no`（只出内核产物） |
| `base_url` | 可选，基线镜像直链 |
| `kernel_ref` | 可选，覆盖 `config/config` 里的分支或 commit |
| `config_source` | `auto` / `repo`（用仓库里的 defconfig）/ `stock`（用你上传的设备配置） |
| `publish_release` | 要不要发 Release（不要就只留 artifact） |
| `tag_suffix` | 可选，给 tag 加后缀，好区分试验 |

改 `config/config` 后直接 `git push` 也行：动到 `config/` `patches/` `scripts/`
`kernel-modules/` 就会自动重编，每周一还跟一次上游分支。

**④ 下载** Release 或 Actions 里的 artifact。

## 目录

```
config/config                     构建开关（内核来源、版本后缀、模块、要不要打包 boot）
patches/0001                      带进内核树的 arch/arm64/configs/k50-rubens_defconfig（真机配置的 savedefconfig）
patches/0002                      板级 DTS（Redmi K50 / rubens）
config/stock_defconfig            可选：你自己 /proc/config.gz 解压出来的配置（优先于上面那个）
config/extra.config               可选：defconfig 之后再合并的配置片段（默认全注释）
base/README.md                    基线镜像放哪、怎么 dump（base/boot.img 不进 git）
patches/optional/                 默认不打的可选补丁（见「补丁」一节）
scripts/k50-pack-boot.py          MTK boot v4 打包器（只换内核段，带自检）
kernel-modules/k50-bl/            外部模块：把面板背光接进 Linux backlight 类
.github/workflows/build-kernel.yml CI 本体
```

## config/config

| 键 | 默认 | 说明 |
|---|---|---|
| `kernel_repo` | 上游仓库 | 可以指定自己的 fork（比如加了自用补丁） |
| `kernel_ref` | `7.2-mt6895-xiaomi-rubens` | 分支名或 commit SHA 都行 |
| `localversion` | `-k50-ci` | 拼进内核版本号和 vermagic；**要沿用设备 `/root` 下现成的 `.ko`，就得留空且源码一致** |
| `config_source` | `auto` | `auto` / `repo` / `stock` |
| `modules` | `k50-bl` | 逗号分隔的外部模块，留空不编 |
| `optional_patches` | `false` | 打不打 `patches/optional/` 里的补丁 |
| `trim_debug_info` | `false` | 设 `true` 会关掉 `DEBUG_INFO`：`vmlinux` 从 569 MB 掉到 71 MB、编得快，**但 gzip 后的内核反而大 164 KB，超出厂商内核段上限，`boot.img` 打不出来**，所以默认 `false`；踩坑细节见常见问题 |
| `pack_boot` | `auto` | `auto` / `yes` / `no` |
| `keep_releases` | `10` | `ci-*` Release 保留几个，旧的自动删 |

`config/extra.config` 只要存在，workflow 就在 defconfig 之后用
`scripts/kconfig/merge_config.sh -m` 合进来（再跑一次 `olddefconfig`），加零散选项不用改补丁里的
defconfig。默认内容全是注释，等于没生效。例子：rootfs 的镜像模式想吃 zstd 压缩的 squashfs，
就在这开 `CONFIG_SQUASHFS_ZSTD=y`（实测 gzip 1.94 GB、zstd 1.80 GB，差 7%，不开也够用）。

想用设备自己的配置（非标准改动推荐这么干）：

```bash
adb shell 'cat /proc/config.gz' | gunzip > config/stock_defconfig
```

`config_source=auto` 会自动优先用它。

## 补丁

| 补丁 | 用途 |
|---|---|
| `0001` | `arm64: configs` — 加 `k50-rubens_defconfig` |
| `0002` | `arm64: dts: mediatek` — Redmi K50（rubens）DTS |

两个 l11a 面板修复（LK 点亮的面板在 DRM core 同步状态、熄屏只发 DCS 命令不动电源域）已经进了
内核分支 `7.2-mt6895-xiaomi-rubens`（`bc95db8659e3`），不再拿补丁重复带一遍：以前这里是
0001、0002 两份面板补丁，上游合了以后删掉，剩下的两个重新编号成 0001、0002。

补丁是幂等的：上游已经合过，workflow 检测到"反向能打上"就跳过。
`patches/optional/0001` 是 `mtk-spmi-keys` 电源键按住的去抖（400 ms），跟息屏无关，默认不打。

## 刷机

```bash
# fastboot（先确认机器是否解锁，资料是否备份）
fastboot flash boot_a boot.img
fastboot reboot
```

## 常见问题

<details>
<summary><b>为什么不直接给 <code>boot.img</code>，非要我自备内核？</b></summary>

内核和 ramdisk 在同一个镜像里，头部没有偏移字段。要么把厂商 ramdisk 放进仓库（不能再分发的
二进制），要么你提供。

</details>

<details>
<summary><b>编一次多久？</b></summary>

默认跑在原生 arm64 runner（`ubuntu-24.04-arm`）上，冷编一小时上下，有 ccache 之后 10～20 分钟。
仓库是公开的，所以这个 runner 直接能用；私有仓库拿不到，Run workflow 时把 `runner` 换成
`ubuntu-24.04` 走交叉编译，慢不少。缓存按 `kernel_ref` 分桶，换分支就得重新冷编。

</details>

<details>
<summary><b>为什么树内构建，不用 <code>O=build</code>？</b></summary>

坑在厂商 Kbuild 里，不在 workflow 里：`drivers/misc/mediatek/btif/common/Makefile` 写的是
`ccflags-y += -I$(srctree)/$(src)/inc`，而 Kbuild 的 `$(src)` 本来就带 srctree 前缀。`O=` 构建时
`srctree` 是相对路径 `..`，展开成 `-I../../drivers/...`，多退了一级，于是 `mtk_btif.c`、
`btif_dma_plat.c` 直接 `fatal error: 'btif_pub.h' file not found`，整树编译 exit 2。树内构建
（也正好是真机内核的构建方式）没这问题。另外 `Image` 和 `dtb` 分两次 `make` 调用，免得两个
子 make 抢 `.config`（`make[6]: *** [Makefile:892: .config] Error 1`）。

实测：同一份源码树内构建时，`drivers/misc/mediatek/btif/common/` 下四个对象（`mtk_btif.o`、
`mtk_btif_exp.o`、`btif_dma_plat.o`、`btif_plat.o`）全编出来，`O=build` 那次在三个文件上直接 fatal。

</details>

<details>
<summary><b>打补丁为什么用 <code>git apply</code>，不用 <code>--index</code>？</b></summary>

后面所有步骤都只读工作区，用不上索引；`--index` 还要求工作区和索引逐条严格匹配，树是从别处
整拷贝或快照过来的时候（索引里的 stat 缓存不是它自己写的），第二份补丁就
`error: <file>: does not match index` 直接失败——我本地复跑时撞过。普通 `apply` 只看工作区
内容，稳。幂等还是靠 `apply --reverse --check`。

</details>

<details>
<summary><b><code>trim_debug_info=true</code> 真的把 <code>DEBUG_INFO</code> 关掉了吗？</b></summary>

踩过，现在真关了，而且会断言。`CONFIG_DEBUG_INFO` 在 `lib/Kconfig.debug` 里是**没有 prompt**
的 bool，真正有 prompt 的是它下面那个 choice 的成员（`DEBUG_INFO_NONE` /
`DEBUG_INFO_DWARF_TOOLCHAIN_DEFAULT` / `..._DWARF4` / `..._DWARF5`）。所以只写
`scripts/config -d DEBUG_INFO` 没用：`olddefconfig` 看到还生效的 choice 成员，又把 `DEBUG_INFO`
select 回 `y`（本地实测就是这样：步骤打印"已关闭 DEBUG_INFO"，`.config` 里还是
`CONFIG_DEBUG_INFO=y`）。workflow 现在把 choice 成员全关、只留 `DEBUG_INFO_NONE`，
`olddefconfig` 之后 `grep '^CONFIG_DEBUG_INFO=y'` 断言，没关掉就 `::error::` 失败，不再嘴上关掉。

</details>

<details>
<summary><b>关掉 <code>DEBUG_INFO</code> 会影响 <code>Image</code> 吗？会，这是第二个坑。</b></summary>

`arch/arm64/boot/Makefile` 里 `OBJCOPYFLAGS_Image := -O binary -R .note -R .note.gnu.build-id -R .comment -S`
看着像 `-S` 已经把调试段剥了（`Image` 尺寸确实一样：**52,894,208 字节，两份都是**），但内容不同：
逐字节比有 **24,251,244 字节不一样**（`vmlinux` 一个 70 MB、一个 569 MB），`gzip -9 -n` 之后
**从 19,932,644 涨到 20,097,258（+164,614）**。

后果很直接：Option B 的硬上限是头里的 `kernel_size` = 19,945,390 字节，"trim 过"的内核塞不进去
（打包器自己压出 20,097,258，超 151,868，直接拒绝打包），不 trim 的塞得进，但余量只有几 KB。
所以**要出 `boot.img` 就必须 `trim_debug_info=false`**（默认已经是 `false`），`true` 只适合
"只要内核产物、不打包"的场合。它省的是编译时间和磁盘，不省产物。

</details>

<details>
<summary><b><code>Image.gz</code> 比原内核段大了怎么办？</b></summary>

默认拒绝打包、结束。挪 ramdisk 偏移是有过 6 次翻车记录的路径；要缩内核就先看 `vmlinux`/`Image`
的构成，别乱动跟启动相关的配置项。非要在本地试，就加 `--allow-shift`（workflow 塞不进时会自动
带上，并在 `BUILD.txt` 里标"ramdisk 已后移"）。

</details>

<details>
<summary><b>余量很小，心里要有数。</b></summary>

这套配置编出来的 `Image` 是 52,894,208 字节，gzip 之后在 19,93x,xxx 量级，上限 19,945,390——
余量只有几 KB。注意这里有两个 gzip：workflow 另外出的 `Image.gz` 走 `gzip -9 -n`，而**打包器用
自己的 zlib 再压一遍**，两者能差几十 KB，判定能不能塞下的是打包器那份。内核再长一点点，下次
构建就开始拒绝打包。

实测：树内构建出来的 `Image` 跑 `scripts/k50-pack-boot.py`，六个检查全过，输出 67,108,864 字节的
`boot.img`（跟基线同尺寸、头部逐字节不变、ramdisk 区原样复制）。

</details>

<details>
<summary><b>刷完相机/指纹/基带模块加载不了？</b></summary>

`vermagic` 变了。把 `localversion` 留空，用跟那些 `.ko` 相同的源码重编；或者干脆用这个仓库
重编它们（`modules=` 加上对应目录）。

</details>

<details>
<summary><b>外部模块报 <code>No rule to make target 'xxx.ko', needed by '__modfinal'</code>？</b></summary>

只编 `Image` 不会生成 `scripts/module.lds`（`modules_prepare` 里才有），外部模块链接就这么炸。
workflow 的「编译外部模块」先跑了 `make ... LOCALVERSION=<同内核> modules_prepare`，手工复现别漏。
同理，`modules_prepare` 的 `LOCALVERSION` 必须跟编 `Image` 时一致，否则
`include/generated/utsrelease.h` 被改写成别的版本号，模块 `vermagic` 对不上，`insmod` 报
`Invalid module format`。workflow 编完模块会用 `modinfo -F vermagic` 跟
`include/config/kernel.release` 逐字比，不一致直接失败。

</details>

<details>
<summary><b>编出来的内核启动不了？</b></summary>

先看 `BUILD.txt` 里的源码提交和补丁列表，确认 `boot.img` 是不是"Option B"（没写 shift）。
回滚 `boot_a`，把 `config/stock_defconfig`（自己设备的配置）传上去重编。

</details>

<details>
<summary><b>workflow 本身有没有低级错误？</b></summary>

仅通过了 `actionlint`（含 shellcheck），0 告警：

```bash
# 装一次（Linux / WSL）
V=$(curl -fsSL https://api.github.com/repos/rhysd/actionlint/releases/latest \
      | sed -n 's/.*"tag_name": "\([^"]*\)".*/\1/p' | head -1)
curl -fsSL -o /tmp/al.tgz \
  "https://github.com/rhysd/actionlint/releases/download/$V/actionlint_${V#v}_linux_amd64.tar.gz"
sudo tar -xzf /tmp/al.tgz -C /usr/local/bin actionlint
actionlint .github/workflows/build-kernel.yml
```

改 workflow 先跑 actionlint 再推；`run:` 里的 shell 抽出来 `bash -n` 干跑一遍，省得在 Actions
里试错浪费一次完整构建。

</details>

## 许可

`patches/` 跟随上游内核 GPL-2.0；`kernel-modules/k50-bl/` 是 GPL-2.0；
脚本和文档 MIT。
