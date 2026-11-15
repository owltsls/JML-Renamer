# -*- coding: utf-8 -*-
"""生成软件图标。

设计含义：
  蓝色圆角底  → 完全本地、原生桌面程序
  叠放的照片  → 批量照片 / 视频文件
  文件名条上被划掉的 JML → 去掉文件名后缀
  右下橙色 × 徽章        → 清除、清理完成

输出：
  icon.ico                 多尺寸 Windows 图标（EXE 图标 + 窗口标题栏图标）
  icon.png                 512px 预览图
  screenshots/icon_app.png 展示页用的预览图
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE = os.path.dirname(os.path.abspath(__file__))
DESIGN = 512
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def pick_font(px):
    for p in ("C:/Windows/Fonts/arialbd.ttf",
              "C:/Windows/Fonts/segoeuib.ttf",
              "C:/Windows/Fonts/msyhbd.ttc"):
        if os.path.exists(p):
            return ImageFont.truetype(p, max(8, px))
    return ImageFont.load_default()


def draw_icon(size, detail=None):
    """按设计稿 512 坐标系绘制，4 倍超采样后缩到目标尺寸。"""
    if detail is None:
        detail = size >= 48
    S = size * 4
    k = S / DESIGN
    P = lambda v: int(round(v * k))
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # 底部柔和投影
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((P(66), P(430), P(446), P(500)), fill=(9, 28, 58, 105))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(max(1, P(18)))))

    # 蓝色渐变圆角底
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (P(18), P(14), P(494), P(490)), radius=P(112), fill=255)
    grad = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    top, bottom = (60, 138, 220), (22, 63, 122)
    y0, y1 = P(14), P(490)
    for y in range(y0, y1):
        t = (y - y0) / max(1, y1 - y0)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,)
        gd.line([(0, y), (S, y)], fill=c)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((P(18), P(14), P(494), P(490)), radius=P(112),
                        outline=(255, 255, 255, 75), width=max(1, P(3)))

    # 后面一张略微倾斜的照片卡（叠放 = 批量）
    back = Image.new("RGBA", (P(300), P(260)), (0, 0, 0, 0))
    bd = ImageDraw.Draw(back)
    bd.rounded_rectangle((0, 0, P(300) - 1, P(260) - 1), radius=P(18),
                         fill=(255, 255, 255, 205))
    back = back.rotate(-10, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(back, (P(70), P(100)))
    d = ImageDraw.Draw(img)

    # 前面主照片卡
    d.rounded_rectangle((P(126), P(96), P(410), P(392)), radius=P(22),
                        fill=(255, 255, 255, 255),
                        outline=(206, 220, 238, 255), width=max(1, P(2)))

    # 照片内容（天空 / 太阳 / 山），用圆角遮罩限制范围
    photo = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    pd = ImageDraw.Draw(photo)
    pd.rounded_rectangle((P(142), P(112), P(394), P(322)), radius=P(12),
                         fill=(225, 240, 255, 255))
    pd.ellipse((P(300), P(128), P(360), P(188)), fill=(255, 181, 69, 255))
    pd.polygon([(P(142), P(322)), (P(226), P(196)), (P(286), P(272)),
                (P(338), P(214)), (P(394), P(322))], fill=(47, 111, 181, 255))
    pd.polygon([(P(142), P(322)), (P(226), P(196)), (P(252), P(230)),
                (P(196), P(322))], fill=(91, 152, 211, 255))
    pmask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(pmask).rounded_rectangle(
        (P(142), P(112), P(394), P(322)), radius=P(12), fill=255)
    img.paste(photo, (0, 0), pmask)
    d = ImageDraw.Draw(img)

    # 文件名条：模拟 "xxx (JML).jpg" 中的后缀被划掉
    d.rounded_rectangle((P(142), P(330), P(394), P(374)), radius=P(10),
                        fill=(236, 241, 247, 255))
    if detail:
        d.text((P(158), P(336)), "JML", font=pick_font(P(28)), fill=(88, 104, 126, 255))
        # 斜线正穿过 JML 文字，明确表达「划掉这个后缀」
        d.line([(P(150), P(358)), (P(262), P(340))], fill=(226, 78, 70, 255),
               width=max(2, P(9)))
        # 斜线两端圆润一点
        for cx, cy in ((150, 358), (262, 340)):
            d.ellipse((P(cx - 4.5), P(cy - 4.5), P(cx + 4.5), P(cy + 4.5)),
                      fill=(226, 78, 70, 255))

    # 右下角橙色清除徽章
    d.ellipse((P(350), P(330), P(474), P(454)), fill=(255, 138, 61, 255),
              outline=(255, 255, 255, 255), width=max(1, P(8)))
    lw = max(2, P(13))
    for a, b in (((386, 366), (438, 418)), ((438, 366), (386, 418))):
        d.line([(P(a[0]), P(a[1])), (P(b[0]), P(b[1]))],
               fill=(255, 255, 255, 255), width=lw)
        for cx, cy in (a, b):
            r = lw / 2
            d.ellipse((P(cx - r / k), P(cy - r / k), P(cx + r / k), P(cy + r / k)),
                      fill=(255, 255, 255, 255))

    return img.resize((size, size), Image.LANCZOS)


def main():
    # 每个尺寸单独绘制（小尺寸自动省略文字细节），再交给 Pillow 写成
    # Windows 原生 BMP(DIB) 编码的 ICO —— 打包工具与 Win32 API 兼容性最好。
    frames = {s: draw_icon(s) for s in ICO_SIZES}
    ico = os.path.join(BASE, "icon.ico")
    frames[256].save(
        ico, format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=[frames[s] for s in ICO_SIZES if s != 256],
        bitmap_format="bmp")
    preview = draw_icon(512, detail=True)
    preview.save(os.path.join(BASE, "icon.png"))
    shots = os.path.join(BASE, "screenshots")
    os.makedirs(shots, exist_ok=True)
    preview.save(os.path.join(shots, "icon_app.png"))

    # 各尺寸 1:1 并排预览，固定列宽避免标签重叠
    gap = 10
    cols = [max(120, s) + 18 for s in ICO_SIZES]
    W = sum(cols) + gap * (len(ICO_SIZES) + 1)
    H = 256 + 100
    strip = Image.new("RGB", (W, H), (245, 247, 251))
    sd = ImageDraw.Draw(strip)
    label_font = pick_font(19)
    x = gap
    for i, size in enumerate(ICO_SIZES):
        cx = x + cols[i] // 2
        im = frames[size]
        strip.paste(im, (cx - size // 2, 46 + (256 - size) // 2), im)
        t = "%d px" % size
        box = sd.textbbox((0, 0), t, font=label_font)
        sd.text((cx - (box[2] - box[0]) // 2, 316), t,
                font=label_font, fill=(48, 66, 92))
        x += cols[i] + gap
    strip.save(os.path.join(shots, "icon_sizes.png"))

    # 用 PIL 反读校验
    check = Image.open(ico)
    print("icon.ico 尺寸列表:", sorted(check.ico.sizes()) if hasattr(check, "ico") else "内嵌 PNG")
    print("icon.ico 大小: %.1f KB" % (os.path.getsize(ico) / 1024))
    print("icon.png:", preview.size)
    print("已生成 ICO 尺寸:", ICO_SIZES)


if __name__ == "__main__":
    main()
