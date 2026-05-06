# -*- coding: utf-8 -*-
"""Matplotlib 中文字体配置（容器内需安装 Noto CJK 等字体包）。"""


def configure_matplotlib_fonts() -> None:
    """设置 sans-serif 优先顺序，避免中文标题/图例/坐标轴显示为方框。"""
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = [
        "Noto Sans CJK SC",
        "Noto Sans CJK JP",
        "Noto Serif CJK SC",
        "Noto Sans CJK TC",
        "WenQuanYi Zen Hei",
        "WenQuanYi Micro Hei",
        "SimHei",
        "Microsoft YaHei",
        "SimSun",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False
