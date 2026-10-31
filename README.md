# k50-boot — Redmi K50（rubens / MT6895）mainline 内核与 boot 镜像

用 GitHub Actions 编 K50 的 mainline 内核，并（可选）打成一个可以直接
`fastboot flash boot_a` 的 `boot.img`。

设计原则只有一条：**仓库里不放任何厂商二进制**。内核和 ramdisk 在同一个
boot 镜像里，而那份 ramdisk 装的是小米/MTK 的固件（1.4 MB），不能公开再分发 ——
所以基线镜像由你自己提供，本仓库只负责"替换内核段、其余逐字节不动"。

> rootfs（Debian 13 + GNOME）在另一个仓库：[k50-rootfs](../k50-rootfs)

---

## 1. 用它

### 1.1 只想拿现成产物

`Releases` 里 `ci-*` 标签的最新一个，资产说明：

| 文件 | 是什么 |
|---|---|
| `boot.img` | 可直接刷的 boot 镜像（**仅当构建时提供了基线镜像**才会出现） |
| `Image` / `Image.gz` | 未压缩 / 压缩后的内核 |
| `mt6895-xiaomi-rubens.dtb` | 设备树 |
| `kernel.config` | 本次实际用的内核配置 |
| `*.ko` | 外部模块（默认只有 `k50_bl.ko`，面板背光） |
| `BUILD.txt` | 本次构建的全部参数（源码提交、补丁、工具链、sha256） |
| `SHA256SUMS.txt` | 校验和 |

> 这些 Release 是**别人的**基线镜像编出来的内核。内核段本身与设备无关，
> 但你若要把 `boot.img` 刷到自己的机器上，那个 `boot.img` 里的 ramdisk 是
> 发布者的；稳妥做法是照 1.2 自己 fork 编一份。

### 1.2 自己 fork 编（推荐）

**① fork** 本仓库到你的账号。

**② 准备基线镜像**（二选一）

- 把你自己设备的 `boot_a` dump 出来，放到 `base/boot.img`
  （怎么 dump、怎么校验见 [`base/README.md`](base/README.md)）；
- 或者什么都不提交，跑 workflow 时在 `base_url` 里填一个能直接下载到
  你那份镜像的链接。

**③ 跑 workflow**

`Actions → build-kernel → Run workflow`，填：

| 输入 | 说明 |
|---|---|
| `pack_boot` | `auto`（有基线就打）/ `yes`（必须打）/ `no`（只出内核产物） |
| `base_url` | 可选，基线镜像直链 |
| `kernel_ref` | 可选，覆盖 `config/config` 里的分支/commit |
| `config_source` | `auto` / `repo`（用仓库自带 defconfig）/ `stock`（用你上传的设备配置） |
| `publish_release` | 是否发 Release（否则只留 artifact） |
| `tag_suffix` | 可选，给 tag 加后缀，便于区分试验 |

也可以改 `config/config` 后 `git push`：动到 `config/` `patches/` `scripts/`
`kernel-modules/` 就会自动重编。每周一还有一次定时构建跟上游分支。

**④ 下载** `Releases` 或 `Actions` 里的 artifact。

---

## 2. 目录结构

```
config/config                     构建开关（内核来源、版本后缀、模块、是否打包 boot）
patches/0003                      带进内核树的 arch/arm64/configs/k50-rubens_defconfig（= 真机配置的 savedefconfig）
config/stock_defconfig            可选：放你自己的 /proc/config.gz 解压结果（优先于上面那个）
config/extra.config               可选：defconfig 之后再合并的内核配置片段（默认全注释）
base/README.md                    基线镜像放哪、怎么 dump（base/boot.img 不进 git）
patches/0001..0004                四个必需补丁（见 §4）
patches/optional/                 默认不打的可选补丁
scripts/k50-pack-boot.py          MTK boot v4 打包器（只换内核段，带自检）
kernel-modules/k50-bl/            外部模块：面板背光接进 Linux backlight 类
.github/workflows/build-kernel.yml CI 本体
```

## 3. `config/config`

| 键 | 默认 | 说明 |
|---|---|---|
| `kernel_repo` | 上游仓库 | 可指向你自己的 fork（例如加了自用补丁） |
| `kernel_ref` | `7.2-mt6895-xiaomi-rubens` | 分支或 commit SHA 都行 |
| `localversion` | `-k50-ci` | 拼进内核版本号与 vermagic；**要沿用设备 `/root` 下现成 `.ko` 时留空且源码一致** |
| `config_source` | `auto` | `auto`/`repo`/`stock` |
| `modules` | `k50-bl` | 逗号分隔的外部模块，留空不编 |
| `optional_patches` | `false` | 是否打 `patches/optional/` 里的补丁 |
| `trim_debug_info` | `false` | 设为 `true` 会关掉 `DEBUG_INFO`：`vmlinux` 从 569 MB 降到 71 MB、编得快，**但 gzip 后的内核反而大 164 KB（19,932,644 → 20,097,258），会超出厂商内核段上限导致 `boot.img` 打包失败**，所以默认 `false`。另外 `CONFIG_DEBUG_INFO` 是无 prompt 的 bool，由 "Debug information" choice 的成员 select 出来，单独 `-d DEBUG_INFO` 会被 `olddefconfig` 重新 select 回来——workflow 已改成关 choice 成员并加断言，详见常见问题 |

另外有一个 `config/extra.config`：只要文件存在，工作流就会在 defconfig 之后用
`scripts/kconfig/merge_config.sh -m` 把它合并进来（再跑一次 `olddefconfig`），
用来加零散选项而不用改补丁里的 defconfig。默认内容全是注释，等于不生效。
例子：rootfs 仓的镜像模式想吃 zstd 压缩的 squashfs，就在这里打开
`CONFIG_SQUASHFS_ZSTD=y`（实测 gzip 1.94 GB vs zstd 1.80 GB，只差 7%，不开也够用）。
| `pack_boot` | `auto` | `auto`/`yes`/`no` |
| `keep_releases` | `10` | `ci-*` Release 保留数量，旧的自动删 |

想用设备自己的配置（推荐给非标准改动）：

```bash
adb shell 'cat /proc/config.gz' | gunzip > config/stock_defconfig
```

之后 `config_source=auto` 就会自动优先用它。

## 4. 补丁

| 补丁 | 干什么 |
|---|---|
| `0001` | `drm/panel: l11a` — LK 点亮的面板在 DRM core 里状态同步（probe 时置 `prepared/enabled`） |
| `0002` | `drm/panel: l11a` — 熄屏只发 DCS 命令（`0x28`/`0x51 00 00`），**不动电源域**（保住了熄屏时不断蓝牙、能再点亮） |
| `0003` | `arm64: configs` — 加 `k50-rubens_defconfig`（= 真机 `savedefconfig`，往返验证 0 差异） |
| `0004` | `arm64: dts: mediatek` — Redmi K50（rubens）板级 DTS |

补丁是幂等的：如果上游已经合了，工作流检测到"反向能打上"就跳过。
`patches/optional/0001` 是 `mtk-spmi-keys` 电源键按住的去抖（400 ms），与
息屏无关，默认不打。

## 5. 刷机与回滚

```bash
# 线上（fastboot，先确认能进 fastboot）
fastboot flash boot_a boot.img
fastboot reboot

# 设备上（更稳；K50 的 fastboot reboot 经常卡住）
dd if=/dev/sdc43 of=/root/boot_before.img bs=1M      # 备份当前 boot_a
dd if=boot.img of=/dev/sdc43 bs=1M
sync
```

回滚就是把 `boot_before.img` 刷回 `boot_a`：

```bash
dd if=/root/boot_before.img of=/dev/sdc43 bs=1M && sync
```

K50 上 `boot_a = /dev/sdc43`（64 MiB）。

## 6. 常见问题

**Q：为什么不直接给 `boot.img`，非要我自备基线？**
内核和 ramdisk 同在一个镜像，没有偏移字段。要么仓库里放厂商 ramdisk
（不能再分发的二进制），要么你提供。你提供还顺带保证"只动内核段"这个唯一
在真机上验证过能开机的差分方式。

**Q：构建一次多久？**
4 核 x86 runner 冷编译大约 1～2 小时（有 ccache 缓存后 10～20 分钟）。
有 arm64 机器的话，Run workflow 时把 `runner` 下拉框换成 `ubuntu-24.04-arm` 会快不少。
缓存按 `kernel_ref` 分桶，所以换分支会重新冷编。

**Q：为什么 workflow 用树内构建，不把产物放到 `build/` 目录（`O=build`）？**
因为坑不在 workflow 里，而在厂商 Kbuild 里：`drivers/misc/mediatek/btif/common/Makefile`
写的是 `ccflags-y += -I$(srctree)/$(src)/inc`，而 Kbuild 的 `$(src)` 本身已经带
srctree 前缀。`O=` 构建时 `srctree` 是相对路径 `..`，展开成 `-I../../drivers/...`
（多退了一级），于是 `mtk_btif.c`、`btif_dma_plat.c` 直接
`fatal error: 'btif_pub.h' file not found`，整树编译 exit 2。
树内构建（也正好是真机内核的构建方式）没这个问题。另外 `Image` 与 `dtb` 分两次
`make` 调用，避免两个子 make 同时抢 `.config`（`make[6]: *** [Makefile:892: .config] Error 1`）。

已验证：同一份源码树内构建时 `drivers/misc/mediatek/btif/common/` 下的 4 个对象
（`mtk_btif.o`、`mtk_btif_exp.o`、`btif_dma_plat.o`、`btif_plat.o`）全部编出来，
`O=build` 那次则在这三个文件上直接 `fatal error`。

**Q：打补丁为什么用 `git apply` 而不是 `git apply --index`？**
因为不需要索引（后面所有步骤都只读工作区），而 `--index` 会额外要求工作区与索引逐条
严格匹配：如果这棵内核树是从别处整拷贝/快照过来的（索引里的 stat 缓存不是它自己写的），
就会在第二个补丁上报 `error: <file>: does not match index` 直接失败——本地复跑时真撞到过。
普通 `apply` 只看工作区内容，稳。幂等性仍由 `apply --reverse --check` 保证
（上游把补丁合进去以后这里会自动跳过）。

**Q：`trim_debug_info=true` 真的把 `DEBUG_INFO` 关掉了吗？**
踩过坑，现在是真的关了，而且会断言。`CONFIG_DEBUG_INFO` 在 `lib/Kconfig.debug` 里是
**没有 prompt 的 bool**（"A kernel debug info option other than None has been selected
in the Debug information choice below"），真正有 prompt 的是它下面那个 choice 的成员
（`DEBUG_INFO_NONE` / `DEBUG_INFO_DWARF_TOOLCHAIN_DEFAULT` / `..._DWARF4` / `..._DWARF5`）。
所以只写 `scripts/config -d DEBUG_INFO` 是**没用的**：`make olddefconfig` 看到还生效的
choice 成员 `DEBUG_INFO_DWARF_TOOLCHAIN_DEFAULT=y`，会把它 select 的 `DEBUG_INFO` 又变回 `y`
（本地实测就是这个现象：步骤打印"已关闭 DEBUG_INFO"，`.config` 里却还是 `CONFIG_DEBUG_INFO=y`）。
workflow 现在的做法是把 choice 成员全关、只留 `DEBUG_INFO_NONE`，并在 `olddefconfig` 之后
`grep '^CONFIG_DEBUG_INFO=y'` 断言，没关掉就直接 `::error::` 失败，不再"嘴上关掉"。

**关掉 `DEBUG_INFO` 会影响 `Image` 吗？会 —— 这是本仓库踩过的第二个坑。**
`arch/arm64/boot/Makefile` 里 `OBJCOPYFLAGS_Image := -O binary -R .note -R .note.gnu.build-id -R .comment -S`
看起来 `-S` 已经把调试段剥掉了（`Image` 尺寸确实一模一样：**52,894,208 字节，两份都是**），
但实测内容并不同：把 `trim_debug_info=true` 编出来的 `Image` 和默认（带 `DEBUG_INFO`）编出来的
逐字节比，**有 24,251,244 字节不同**（`vmlinux` 一个 70 MB、一个 569 MB），
gzip(`-9 -n`, mtime=0) 之后**从 19,932,644 字节涨到 20,097,258 字节（+164,614）**。

后果很直接：Option B 的硬上限是头部里的 `kernel_size` = 19,945,390 字节，
**「trim 过」的内核塞不进去**（打包器自己压出来 20,097,258，超 +151,868，直接拒绝打包）；
不 trim 的正好塞得进（实测整链绿灯，但余量只有几 KB 量级）。
所以**要出 `boot.img` 就必须 `trim_debug_info=false`**（默认值已经改成 `false`），
`true` 只适合"只要内核产物、不打包 boot.img"的场景。它省的是编译时间与磁盘，不省产物。

**Q：`Image.gz` 比原内核段大了会怎样？**
默认**拒绝打包**并结束。挪 ramdisk 偏移是有过 6 次翻车记录的路径；要么缩小内核，
要么在本地明确 `--allow-shift`（workflow 会在塞不进时自动带这个参数，并在 `BUILD.txt`
里标注"ramdisk 已后移"）。

**别拿 `trim_debug_info=true` 当"缩小内核"的办法**：实测它会让 gzip 后的内核**变大 164 KB**
（见上一问），正好把 boot.img 挤出可打包范围。

**余量很小，心里要有数**：本仓库这套配置编出来的 `Image` 是 52,894,208 字节，
gzip 之后在 19,93x,xxx 量级，而 Option B 的硬上限是 19,945,390 字节 —— **余量只有几 KB**。
注意这里有两个 gzip：workflow 会另外出一个 `Image.gz` 产物（`gzip -9 -n`），
而**打包器用自己的 zlib 重新压一遍**，两者能差几十 KB，
判定能不能塞下的是打包器那一份。也就是说内核只要再长一点点，
下一次构建就会开始拒绝打包（那时要么本地 `--allow-shift`，要么调整配置）。
真要省空间就先看 `vmlinux`/`Image` 的构成，别乱动 `.config` 里与启动相关的项。

已验证：用上面那份树内构建出来的 `Image` 跑 `scripts/k50-pack-boot.py`，六个检查全过，
输出 67,108,864 字节的 `boot.img`（与基线同尺寸、头部逐字节不变、ramdisk 区原样复制）。

**Q：刷完相机/指纹/基带模块加载不了。**
`vermagic` 变了。把 `localversion` 留空并用与那些 `.ko` 相同的源码重新编，
或者用本仓库重编它们（`modules=` 加上对应目录）。

**Q：外部模块这一步报 `No rule to make target 'xxx.ko', needed by '__modfinal'`。**
只编 `Image` 时不会生成 `scripts/module.lds`（它在 `modules_prepare` 里才出现），
外部模块链接就会这样炸。workflow 的「编译外部模块」里已经先跑
`make ... LOCALVERSION=<同内核> modules_prepare` 了 —— 手工复现时别漏这一步。
同理：`modules_prepare` 的 `LOCALVERSION` 必须与编 `Image` 时**一致**，否则
`include/generated/utsrelease.h` 会被改写成别的版本号，模块 `vermagic` 与内核不一致
（`insmod` 报 `Invalid module format`）。workflow 里编完模块会用 `modinfo -F vermagic`
跟 `include/config/kernel.release` 逐字对比，不一致直接失败。

**Q：编出来的内核启动不了。**
看 `BUILD.txt` 里的源码提交和补丁列表，先确认 `boot.img` 的打包方式是不是
"Option B"（没写 shift）。回滚 `boot_a` 后把 `config/stock_defconfig`（你自己
设备的配置）传上去重编。

**Q：workflow 本身有没有低级错误？**
本仓库的 `build-kernel.yml` 过了 `actionlint`（含 shellcheck）0 告警：

```bash
# 装一次（Linux / WSL）
V=$(curl -fsSL https://api.github.com/repos/rhysd/actionlint/releases/latest \
      | sed -n 's/.*"tag_name": "\([^"]*\)".*/\1/p' | head -1)
curl -fsSL -o /tmp/al.tgz \
  "https://github.com/rhysd/actionlint/releases/download/$V/actionlint_${V#v}_linux_amd64.tar.gz"
sudo tar -xzf /tmp/al.tgz -C /usr/local/bin actionlint
# 检查
actionlint .github/workflows/build-kernel.yml
```

另外 `tools/run-steps.py` 能把指定的 `run:` 块**真的在本机跑起来**（带 `${{ }}` 展开
与 `GITHUB_ENV`/`GITHUB_OUTPUT` 语义）：改动 workflow 后，先跑一遍要动的 step 再推。

---

## 许可

内核补丁（`patches/`）遵循 GPL-2.0（与上游内核一致）；本仓库脚本与文档为 MIT。
仓库**不含**任何厂商二进制。
