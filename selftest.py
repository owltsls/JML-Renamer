# -*- coding: utf-8 -*-
"""核心引擎自测：在临时样本文件夹里跑一遍 扫描 → 改名 → 撤销，不触碰任何真实照片。"""
import os
import sys
import shutil
import tempfile

import engine

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_selftest_photos")

SAMPLES = [
    ("IMG_0001 (JML).jpg", "IMG_0001.jpg", "可改名"),
    ("IMG_0002(JML).JPG", "IMG_0002.JPG", "可改名"),
    ("VID_0003 (jml).mp4", "VID_0003.mp4", "可改名"),
    ("IMG_0004 (JML) (JML).png", "IMG_0004.png", "可改名"),
    ("IMG_0005（JML）.jpg", "IMG_0005.jpg", "可改名"),
    ("IMG_0006.jpg (JML)", "IMG_0006.jpg", "可改名"),
    ("正常照片.jpg", None, None),
    ("no_tag (ABC).jpg", None, None),
    ("IMG_0007 (JML).jpg", "IMG_0007.jpg", "跳过"),     # 目标已存在
    ("IMG_0007.jpg", None, None),
    ("IMG_0010 (JML) - 副本.jpg", "IMG_0010 - 副本.jpg", "可改名"),
    ("sub/DSC_0008 (JML).jpg", "DSC_0008.jpg", "可改名"),
    ("sub/deep/DSC_0009 ( JML ).jpg", "DSC_0009.jpg", "可改名"),
]


def make_files():
    if os.path.exists(ROOT):
        shutil.rmtree(ROOT)
    for rel, _new, _status in SAMPLES:
        path = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("sample")
    # 额外普通文件，用来验证不会被误伤
    with open(os.path.join(ROOT, "sub", "keep_me.txt"), "w", encoding="utf-8") as f:
        f.write("sample")


def check(label, cond, detail=""):
    if not cond:
        raise AssertionError("%s 失败：%s" % (label, detail))
    print("  [OK] " + label)


def main():
    make_files()
    try:
        print("== 1. 扫描（含子文件夹）==")
        res = engine.scan(ROOT, "(JML)", recursive=True)
        check("扫描文件总数 >= 14", res["total"] >= 14, str(res["total"]))
        check("匹配到 10 个含后缀文件", res["matched"] == 10, str(res["matched"]))
        check("可改名 9 个", res["ready"] == 9, str(res["ready"]))
        check("冲突跳过 1 个", res["skipped"] == 1, str(res["skipped"]))

        by_old = {r["old_name"]: r for r in res["records"]}
        for rel, new_name, status in SAMPLES:
            name = os.path.basename(rel)
            if new_name is None:
                check("不含后缀的文件被忽略：%s" % name, name not in by_old)
            else:
                r = by_old.get(name)
                check("改名结果 %s -> %s" % (name, new_name),
                      r is not None and r["new_name"] == new_name,
                      str(r["new_name"]) if r else "未找到")
                check("状态 %s：%s" % (name, status), r["status"] == status, str(r["status"]))

        print("== 2. 不递归时只处理顶层 ==")
        res2 = engine.scan(ROOT, "(JML)", recursive=False)
        check("顶层匹配 8 个", res2["matched"] == 8, str(res2["matched"]))

        print("== 3. 只处理图片/视频格式 ==")
        res3 = engine.scan(ROOT, "(JML)", only_media=True)
        check("扩展名过滤生效", res3["matched"] == 10, str(res3["matched"]))

        print("== 4. 执行重命名 ==")
        log = os.path.join(ROOT, "_重命名日志.csv")
        applied = engine.apply(res, log)
        check("成功 9 个", applied["ok"] == 9, str(applied["ok"]))
        check("失败 0 个", applied["fail"] == 0, str(applied["fail"]))
        check("日志已生成", os.path.isfile(log))
        for rel, new_name, status in SAMPLES:
            old = os.path.join(ROOT, rel)
            new = os.path.join(os.path.dirname(old), new_name) if new_name else None
            if status == "可改名":
                check("已改名并保留原文件：%s" % rel, os.path.isfile(new) and not os.path.exists(old))
            elif status == "跳过":
                check("冲突文件未被覆盖：%s" % rel, os.path.isfile(old))
        check("无关文件未被动过", os.path.isfile(os.path.join(ROOT, "正常照片.jpg")))

        print("== 5. 一键撤销 ==")
        undone = engine.undo(log)
        check("还原 9 个", undone["ok"] == 9, str(undone["ok"]))
        check("还原失败 0 个", undone["fail"] == 0, str(undone["fail"]))
        for rel, _new, status in SAMPLES:
            if status == "可改名":
                check("已还原：%s" % rel, os.path.isfile(os.path.join(ROOT, rel)))
        print("\n全部自测通过。")
    finally:
        if os.path.exists(ROOT):
            shutil.rmtree(ROOT)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("自测失败：%s" % e)
        raise
