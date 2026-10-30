# k50-bl —— 把 L11A 面板背光接进 Linux backlight 类

## 解决的问题

`panel-l11a-38-0a-0a-dsc-cmd.c` 里背光只有一条路：probe 时
`of_parse_phandle(dev->of_node, "backlight", 0)`，设备树给了 phandle 才会
`of_find_backlight_by_node()` 并注册 `/sys/class/backlight`。rubens 的 DTS 没有
这个 phandle，于是：

- `ctx->backlight == NULL`
- 不注册 backlight 类 → `/sys/class/backlight` 空
- GNOME（gsd-power 的 udev 后端）认为"没有可用背光"，亮度滑块/快捷键全哑
- 同时 `lcm_enable()` 里那句 `backlight_update_status()` 也永远不执行

改内核 DTS + 面板驱动也能修，但那是每次重编内核都要跟着动的活。这个模块走
另一条路：注册一个标准 backlight 设备，`update_status` 调到内核已导出的
`mtkfb_set_backlight_level()`（`drivers/gpu/drm/mediatek/mediatek_v2/mtk_debug.c`，
`EXPORT_SYMBOL`），由它一路走到面板的 DCS `0x51` 写命令。

## 效果

```
/sys/class/backlight/l11a/{brightness,max_brightness,type}
   brightness 0..2047（面板是 11 位背光）
```

GNOME 侧立刻可用（gsd-power 48.x 的 udev 后端，`org.gnome.SettingsDaemon.Power.Screen`
的 `Brightness` 属性），设置面板滑块、`brightnessctl`、快捷键都能用。

## 构建

需要与目标内核**完全一致**的构建树（vermagic 必须匹配）：

```bash
make -C <内核源码> M=$PWD ARCH=arm64 LLVM=1 modules
```

如果 modpost 报一堆 undefined（`backlight_device_register`、`_printk`、`mutex_lock`、
`mtkfb_set_backlight_level`…），说明构建目录缺 `Module.symvers`：

```bash
cp <构建目录>/vmlinux.symvers <构建目录>/Module.symvers
```

（k50-boot 的 CI 工作流已经内置这一步。）

## 加载

```bash
insmod k50_bl.ko          # 或 modprobe k50_bl（装到 /lib/modules/$(uname -r)/extra/ 后）
cat /sys/class/backlight/l11a/max_brightness   # 2047
echo 400 > /sys/class/backlight/l11a/brightness
```

开机自动加载：把 `.ko` 放进 `/lib/modules/$(uname -r)/extra/`（`depmod -a`），
再写 `/etc/modules-load.d/k50-backlight.conf` 内容 `k50_bl`。k50-rootfs 仓库的
overlay 里已经带了这个 conf 和一个条件式 `k50-backlight.service`。

## 限制

- `bl_power`（FB_BLANK）没接：熄屏/亮屏由 DRM + 面板的 DCS 命令负责，不走这里
- 不处理 AOD / doze 亮度（面板驱动里那套 HBM 命令没接）
- 内核里若已有真正的 backlight 设备，两者会打架，别同时用
