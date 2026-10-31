# 许可

本仓库是混合许可，`LICENSE` 全文为 GPL-2.0，因为内容包括：

* `patches/**`：对上游 Linux 内核的改动（`k50-rubens_defconfig`、Redmi K50 板级 DTS），跟随内核，GPL-2.0。
* `kernel-modules/k50-bl/**`：背光模块，`SPDX-License-Identifier: GPL-2.0`，用内核内部符号，只能是 GPL。

其余部分（`scripts/**`、`config/**`、`.github/**`、`*.md`）以 MIT 提供：随便改、随便再分发，保留版权声明即可。
两边都沾的文件按 GPL-2.0 算。
