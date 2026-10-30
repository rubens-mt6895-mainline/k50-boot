#!/usr/bin/env python3
"""k50-pack-boot.py —— 把新编译的 Image 塞进 K50（rubens / MT6895）的 boot_a 镜像。

机型事实（2026-10 在真机 + boot_a 备份上实测确认）
-------------------------------------------------
* boot_a 分区 = /dev/sdc43，67108864 字节（64 MiB）。
* 镜像格式 = MTK boot image v4（0x0 处 magic "ANDROID!"，header_version@40 = 4）。
* 头部长度 4096；kernel 段从 0x1000 开始，长度 = u32@8（kernel_size）；
  ramdisk 段起始 = align_up(0x1000 + kernel_size, 4096)（LK 就是这么推的；
  头部里没有 ramdisk 便宜量字段，page_size@1580 = 0）。
* u32@12（ramdisk_size）是坏的/不可信的：真值流会延伸进后面的零填充区。

做法（"Option B" 最小差分，唯一在真机上验证过能正常开机的做法）
---------------------------------------------------------------
* 4096 字节头部 **一个字节都不改**（kernel_size@8 保持原值）。
* 新的 Image.gz 写在 0x1000，用 0 填充到与原来完全相同的内核段长度；
  于是 ramdisk 偏移不变，从 rampdisk 段开始到文件尾 **逐字节复制原镜像**。
* 结果：输出与原镜像的差异只落在 [0x1000, 0x1000 + kernel_size) 之内。

为什么不用别的方式：docs/project_memory.md 记着——重新生成 ramdisk 导致过
6 次刷机翻车（"过 DRM 后静默重启/反复重启"）；挪动 ramdisk 偏移的风险来源相同。

用法：
  python3 k50-pack-boot.py --base boot_a.img --image Image --out boot_k50.img
  python3 k50-pack-boot.py --base boot_a.img --image Image --verify-only

刷机（自己负责，先备份！）：
  dd if=/dev/sdc43 of=boot_before.img bs=1M     # 备份
  dd if=boot_k50.img of=/dev/sdc43 bs=1M        # 刷入
"""
import argparse
import gzip
import hashlib
import struct
import sys
import zlib
from pathlib import Path

PAGE = 4096          # MTK boot image 头部页
HDR = 4096


def align_up(x: int, a: int) -> int:
    return (x + a - 1) // a * a


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class Report:
    def __init__(self) -> None:
        self.fails: list[str] = []

    def check(self, cond: bool, msg: str) -> bool:
        print(("  [ok]   " if cond else "  [FAIL] ") + msg)
        if not cond:
            self.fails.append(msg)
        return cond

    def info(self, msg: str) -> None:
        print("         " + msg)

    @property
    def ok(self) -> bool:
        return not self.fails


def main() -> int:
    ap = argparse.ArgumentParser(
        description="把新 Image 打进 K50 boot_a（只换内核段，不动头部与 ramdisk）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--base", required=True, help="基线 boot 镜像（设备里现在这份 boot_a 的备份）")
    ap.add_argument("--image", required=True, help="新编译出的 Image（未压缩）")
    ap.add_argument("--out", help="输出镜像路径（--verify-only 时不需要）")
    ap.add_argument("--verify-only", action="store_true", help="只做检查，不写文件")
    ap.add_argument(
        "--allow-shift",
        action="store_true",
        help="新内核 gzip 塞不进原内核段时，允许挪动 ramdisk 偏移（有风险，默认拒绝）",
    )
    args = ap.parse_args()

    r = Report()
    base = Path(args.base).read_bytes()
    img = Path(args.image).read_bytes()

    print("== 1. 基线镜像 ==")
    r.check(len(base) >= HDR, f"基线大小 {len(base)} 字节")
    r.check(base[:8] == b"ANDROID!", "magic = ANDROID!（MTK boot image）")
    if base[:8] != b"ANDROID!":
        return 1
    hver = struct.unpack_from("<I", base, 40)[0]
    ksize, rsize = struct.unpack_from("<II", base, 8)
    r.info(f"header_version@40 = {hver}；kernel_size@8 = {ksize}；ramdisk_size@12 = {rsize}（不可信，仅参考）")
    r.info(f"page_size@1580 = {struct.unpack_from('<I', base, 1580)[0]}（LK 约定为 0）")
    r.info(f"基线 sha256 = {sha256(base)}")

    ram_off = align_up(HDR + ksize, PAGE)
    r.check(ram_off + HDR <= len(base), f"ramdisk 段偏移 {ram_off} 在镜像内")

    print("== 2. 基线内核段能解开 ==")
    oldgz = base[HDR:HDR + ksize]
    try:
        d = zlib.decompressobj(31)
        oldimg = d.decompress(oldgz) + d.flush()
    except zlib.error as e:
        r.check(False, f"基线内核段解压失败：{e}")
        return 1
    r.info(f"原内核 Image = {len(oldimg)} 字节，sha256 = {sha256(oldimg)[:16]}…")
    r.info(f"尾部填充被忽略 {len(d.unused_data)} 字节，stream eof={d.eof}")

    print("== 3. 新内核 ==")
    r.check(len(img) > 0, f"新 Image 大小 {len(img)} 字节")
    if len(img) != len(oldimg):
        r.info(f"注意：新 Image 与旧 Image 大小不同（{len(img)} vs {len(oldimg)}）——配置变了？")
    newgz = gzip.compress(img, mtime=0)
    r.info(f"新 Image sha256 = {sha256(img)}")
    r.info(f"gzip(新 Image, mtime=0) = {len(newgz)} 字节；原内核段 = {ksize} 字节")
    r.check(zlib.decompress(newgz, 31) == img, "新 gzip 能回解成 Image")
    fits = len(newgz) <= ksize
    r.check(fits or args.allow_shift, f"新 gzip 塞得进原内核段（差 {len(newgz) - ksize:+d} 字节）")
    if not fits and not args.allow_shift:
        print("\n拒绝打包：新内核 gzip 比原内核段大。")
        print("挪动 ramdisk 偏移 = 换掉那份唯一验证过能开机的布局（docs/project_memory.md:669 记过 6 次翻车）。")
        print("要么先用 --allow-shift 明确接受风险，要么缩小内核（例如关掉 DEBUG_INFO）。")
        return 1
    if not fits:
        print("\n!! --allow-shift：ramdisk 会整体后移，风险自负（这是没验证过的路径）!!")

    print("== 4. 组装 ==")
    if fits:
        out = bytearray(base)
        out[HDR:HDR + ksize] = newgz + b"\x00" * (ksize - len(newgz))
        out = bytes(out)
        tail_ok = out[HDR + ksize:] == base[HDR + ksize:]
        r.check(len(out) == len(base), f"输出大小 {len(out)} == 基线 {len(base)}")
        r.check(out[:HDR] == base[:HDR], "头部 4096 字节逐字节不变（kernel_size 没动）")
        r.check(tail_ok, f"从 {HDR + ksize} 起到文件尾逐字节复制原镜像（{len(base) - HDR - ksize} 字节）")
    else:
        new_ksize = len(newgz)
        new_ram_off = align_up(HDR + new_ksize, PAGE)
        shift = new_ram_off - ram_off
        r.info(f"ramdisk 偏移 {ram_off} → {new_ram_off}（后移 {shift} 字节）")
        head = bytearray(base[:HDR])
        struct.pack_into("<I", head, 8, new_ksize)
        tail = base[ram_off:]
        out = bytes(head) + newgz + b"\x00" * (new_ram_off - HDR - new_ksize) + tail
        r.check(len(out) <= len(base), f"输出大小 {len(out)} <= 分区大小 {len(base)}")
        r.check(struct.unpack_from("<I", out, 8)[0] == new_ksize, "kernel_size@8 已更新为新长度")

    print("== 5. LK 视角回放：内核段解压 == Image ==")
    d2 = zlib.decompressobj(31)
    ks = struct.unpack_from("<I", out, 8)[0]
    got = d2.decompress(out[HDR:HDR + ks]) + d2.flush()
    r.check(got == img, "内核段解压结果与我们的 Image 完全一致")
    r.info(f"尾部 {len(d2.unused_data)} 字节填充被忽略，eof={d2.eof}")

    print("== 6. 差异报告 ==")
    diffs = [i for i in range(0, len(base), PAGE) if out[i:i + PAGE] != base[i:i + PAGE]]
    r.info(f"有变化的页数：{len(diffs)}；前 {diffs[:3]} 后 {diffs[-3:]}")
    if fits:
        hi = HDR + ksize
        r.check(all(HDR <= i < hi for i in diffs), "所有变化的页都落在内核段内")

    print("== 结果 ==")
    r.info(f"输出 sha256 {sha256(out)}，{len(out)} 字节")
    if args.verify_only or not args.out:
        if not args.out and not args.verify_only:
            r.info("（没给 --out，未写文件）")
    else:
        Path(args.out).write_bytes(out)
        r.info(f"已写出 {args.out}")

    print("\nRESULT: " + ("ALL CHECKS PASSED" if r.ok else f"{len(r.fails)} CHECK(S) FAILED"))
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
