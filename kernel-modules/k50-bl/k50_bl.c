// SPDX-License-Identifier: GPL-2.0
/*
 * k50_bl.c — 把 K50（MT6895 / l11a_38_0a_0a_dsc_cmd 面板）的 DCS 0x51 亮度
 * 暴露成标准 /sys/class/backlight 设备，让 GNOME 的亮度滑块/亮度键能直接控制。
 *
 * 背景：本内核的该面板驱动只保留 DCS 亮度通道（lcm_setbacklight_cmdq），
 * probe 里用 of_parse_phandle(dev->of_node, "backlight", 0) 找 backlight 节点，
 * rubens 的 dts 没有这个 phandle ⇒ ctx->backlight == NULL ⇒ 不注册
 * backlight_class 设备 ⇒ /sys/class/backlight 空 ⇒ GNOME 认为没有背光可调。
 *
 * MTK 已把同一条 DCS 路径导出为 mtkfb_set_backlight_level()
 * （drivers/gpu/drm/mediatek/mediatek_v2/mtk_debug.c，EXPORT_SYMBOL），
 * 只在 /sys/kernel/debug/mtkfb 的 "backlight:<n>" 里可用，普通用户态拿不到
 * 标准接口。本模块把它包成一个 backlight 设备，从而无需修改内核镜像、
 * 无需重新刷 boot_a —— 设备端 insmod 即可生效。
 *
 * 加载：insmod k50_bl.ko   → 出现 /sys/class/backlight/l11a/（0..2047）
 * 卸载：rmmod k50_bl
 *
 * 走 mtkfb_set_backlight_level() 而不是自己发 DCS 的原因：该函数最终进入
 * lcm_setbacklight_cmdq()，会同步更新面板驱动记忆的 bl_tb0，
 * 于是熄屏唤醒后 lcm_panel_init() 里的 "restore brightness" 用的正是
 * GNOME 设的值，不会跳回默认亮度。
 */
#include <linux/backlight.h>
#include <linux/err.h>
#include <linux/fb.h>
#include <linux/init.h>
#include <linux/module.h>
#include <linux/string.h>

#define K50_BL_MAX	2047	/* 11 bit: 0x7FF */
#define K50_BL_DEFAULT	K50_BL_MAX

/* mtk_debug.c: EXPORT_SYMBOL(mtkfb_set_backlight_level) —— crtc0 → 面板 DCS 0x51 */
extern int mtkfb_set_backlight_level(unsigned int level);

static int k50_bl_update_status(struct backlight_device *bl)
{
	int level = bl->props.brightness;

	/* 熄屏/AOD：下发 0。面板此时已被 lcm_unprepare 断电，这一步是双保险 */
	if (bl->props.power != FB_BLANK_UNBLANK ||
	    (bl->props.state & (BL_CORE_SUSPENDED | BL_CORE_FBBLANK)))
		level = 0;

	mtkfb_set_backlight_level(level);
	return 0;
}

static const struct backlight_ops k50_bl_ops = {
	.update_status = k50_bl_update_status,
};

static struct backlight_device *k50_bl;

static int __init k50_bl_init(void)
{
	struct backlight_properties props;

	memset(&props, 0, sizeof(props));
	props.type = BACKLIGHT_RAW;
	props.max_brightness = K50_BL_MAX;
	props.brightness = K50_BL_DEFAULT;
	props.power = FB_BLANK_UNBLANK;

	k50_bl = backlight_device_register("l11a", NULL, NULL,
					   &k50_bl_ops, &props);
	if (IS_ERR(k50_bl)) {
		pr_err("k50_bl: backlight_device_register failed: %ld\n",
		       PTR_ERR(k50_bl));
		return PTR_ERR(k50_bl);
	}

	backlight_update_status(k50_bl);
	pr_info("k50_bl: /sys/class/backlight/l11a ready (0..%d)\n",
		K50_BL_MAX);
	return 0;
}

static void __exit k50_bl_exit(void)
{
	backlight_device_unregister(k50_bl);
	pr_info("k50_bl: unloaded\n");
}

module_init(k50_bl_init);
module_exit(k50_bl_exit);

MODULE_AUTHOR("Luis / DSH");
MODULE_DESCRIPTION("K50 l11a panel DCS backlight as /sys/class/backlight device");
MODULE_LICENSE("GPL");
