# -*- coding: utf-8 -*-
"""
批量去除文件名中的 "(JML)" 之类后缀 —— 核心引擎。

特点：
  * 纯标准库，无界面依赖，可单独测试
  * 兼容全角/半角括号、大小写、括号内外空格、重复出现的后缀
  * 后缀既可能在扩展名前 "IMG_001 (JML).jpg"，也可能在整个文件名末尾
  * 目标已存在 / 多个文件改名后重名 —— 一律跳过，绝不覆盖
  * 超长路径自动启用 Windows 长路径前缀
  * 每次执行生成 CSV 日志，可完整撤销
"""

import os
import re
import csv
from datetime import datetime

DEFAULT_TAG = "(JML)"

MEDIA_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp",
    ".heic", ".heif", ".raw", ".cr2", ".cr3", ".nef", ".arw", ".dng",
    ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".m4v", ".mpg",
    ".mpeg", ".3gp", ".webm", ".ts", ".mts", ".m2ts", ".mp3", ".wav", ".m4a",
}

LOG_FIELDS = ["时间", "结果", "原文件名", "新文件名", "原完整路径", "新完整路径", "说明"]


def build_pattern(tag, ignore_case=True):
    """把用户填写的后缀文本编译成宽松匹配的正则。"""
    if not tag or not tag.strip():
        tag = DEFAULT_TAG
    parts = []
    for ch in tag.strip():
        if ch in "(（":
            parts.append("[（(]")
        elif ch in ")）":
            parts.append("[)）]")
        elif ch.isspace():
            parts.append(r"\s*")
        else:
            parts.append(re.escape(ch))
    flags = re.IGNORECASE if ignore_case else 0
    # 每个字符之间允许任意空格，因此 "(JML)" 也能匹配 "( JML )"
    return re.compile(r"\s*" + r"\s*".join(parts) + r"\s*", flags)


def tidy(s):
    """清理删除后缀后残留的多余空格、点和分隔符。"""
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"[ \t]+\.", ".", s)
    return s.strip().rstrip(" _-").strip()


def compute_new_name(filename, pattern):
    """返回新文件名；若文件名不含该后缀则返回 None。"""
    stem, ext = os.path.splitext(filename)
    base = tidy(stem)
    # 用一个空格替换后缀，再由 tidy 收敛多余空格，避免把 "A (JML) - 副本" 挤成 "A- 副本"
    new_stem = tidy(pattern.sub(" ", stem))
    if new_stem != base:
        return (new_stem + ext) if new_stem else None

    # 兼容后缀写在整个文件名末尾的情况，例如 "IMG.jpg (JML)"
    whole_old = tidy(filename)
    whole_new = tidy(pattern.sub(" ", filename))
    if whole_new and whole_new != whole_old and not whole_new.startswith("."):
        return whole_new
    return None


def long_path(p):
    r"""转换为 Windows 长路径格式（\\?\ 前缀），突破 260 字符限制。"""
    p = os.path.abspath(p)
    if p.startswith("\\\\?\\"):
        return p
    if p.startswith("\\\\"):
        return "\\\\?\\UNC\\" + p[2:]
    return "\\\\?\\" + p.replace("/", "\\")


def do_rename(src, dst):
    """执行重命名；普通方式失败时自动用长路径方式重试。"""
    try:
        os.rename(src, dst)
    except OSError:
        os.rename(long_path(src), long_path(dst))


def path_exists(p):
    try:
        return os.path.exists(p)
    except (OSError, ValueError):
        try:
            return os.path.exists(long_path(p))
        except Exception:
            return False


def scan(folder, tag=DEFAULT_TAG, recursive=True, ignore_case=True,
         only_media=False, progress=None, cancel=None):
    """扫描文件夹，返回所有待处理记录（不修改任何文件）。"""
    folder = os.path.abspath(folder)
    if not os.path.isdir(folder):
        raise ValueError("文件夹不存在，或不是一个文件夹：%s" % folder)

    pattern = build_pattern(tag, ignore_case)
    records = []
    seen_targets = {}
    total = 0
    matched = 0

    def report(msg):
        if progress:
            progress("scan", total, 0, msg)

    for dirpath, dirnames, filenames in os.walk(folder, onerror=lambda e: None):
        if cancel is not None and cancel.is_set():
            break
        if not recursive:
            dirnames[:] = []
        for name in filenames:
            if cancel is not None and cancel.is_set():
                break
            total += 1
            if total % 500 == 0:
                report("正在扫描…已检查 %d 个文件" % total)
            new_name = compute_new_name(name, pattern)
            if not new_name:
                continue
            # 用改后文件名的扩展名判断，避免 "IMG.jpg (JML)" 这类文件被误过滤
            if only_media and os.path.splitext(new_name)[1].lower() not in MEDIA_EXTS:
                continue
            matched += 1
            old_path = os.path.join(dirpath, name)
            new_path = os.path.join(dirpath, new_name)
            key = os.path.normcase(os.path.abspath(new_path))

            status = "可改名"
            note = ""
            if new_name == name:
                status, note = "跳过", "新旧文件名相同"
            elif key in seen_targets:
                status, note = "跳过", "目标名与另一个待改名文件重复：" + os.path.basename(seen_targets[key])
            elif path_exists(new_path) and os.path.normcase(os.path.abspath(new_path)) != os.path.normcase(os.path.abspath(old_path)):
                status, note = "跳过", "目标文件已存在，为安全起见不覆盖"
            elif len(new_name) > 240:
                status, note = "跳过", "新文件名过长"
            else:
                seen_targets[key] = old_path

            records.append({
                "old_path": old_path,
                "new_path": new_path,
                "old_name": name,
                "new_name": new_name,
                "status": status,
                "note": note,
                "result": "",
            })

    ready = sum(1 for r in records if r["status"] == "可改名")
    return {
        "folder": folder,
        "tag": tag,
        "total": total,
        "matched": matched,
        "ready": ready,
        "skipped": matched - ready,
        "cancelled": bool(cancel is not None and cancel.is_set()),
        "records": records,
    }


def write_log(log_path, rows):
    with open(log_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(LOG_FIELDS)
        w.writerows(rows)


def apply(scan_result, log_path, progress=None, cancel=None):
    """按扫描结果执行重命名，写 CSV 日志。"""
    records = [r for r in scan_result["records"] if r["status"] == "可改名"]
    rows = []
    ok = 0
    fail = 0
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    count = len(records)

    for i, r in enumerate(records):
        if cancel is not None and cancel.is_set():
            break
        note = ""
        try:
            do_rename(r["old_path"], r["new_path"])
            result = "成功"
            ok += 1
        except Exception as e:
            result = "失败"
            note = str(e)
            fail += 1
        r["result"] = result
        rows.append([stamp, result, r["old_name"], r["new_name"],
                     r["old_path"], r["new_path"], note])
        if progress and (i % 20 == 0 or i + 1 == count):
            progress("apply", i + 1, count, "正在重命名 %d / %d …" % (i + 1, count))

    # 把被跳过的文件也写进日志，便于事后核对
    for r in scan_result["records"]:
        if r["status"] != "可改名":
            rows.append([stamp, "跳过", r["old_name"], r["new_name"],
                         r["old_path"], r["new_path"], r["note"]])

    try:
        write_log(log_path, rows)
        saved = log_path
    except Exception:
        saved = ""

    return {
        "ok": ok,
        "fail": fail,
        "cancelled": bool(cancel is not None and cancel.is_set()),
        "log_path": saved,
        "rows": rows,
    }


def read_log(log_path):
    """读取日志中所有成功改名的记录，用于撤销。"""
    items = []
    with open(log_path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("结果") == "成功" and row.get("原完整路径") and row.get("新完整路径"):
                items.append((row["原完整路径"], row["新完整路径"]))
    return items


def undo(log_path, progress=None, cancel=None):
    """把一次重命名完整还原。"""
    items = read_log(log_path)
    rows = []
    ok = 0
    fail = 0
    skipped = 0
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    count = len(items)

    for i, (old_path, new_path) in enumerate(items):
        if cancel is not None and cancel.is_set():
            break
        note = ""
        if not path_exists(new_path):
            result, note, skipped = "跳过", "改名后的文件已不存在", skipped + 1
        elif path_exists(old_path) and os.path.normcase(os.path.abspath(old_path)) != os.path.normcase(os.path.abspath(new_path)):
            result, note, skipped = "跳过", "原文件名已被占用，避免覆盖", skipped + 1
        else:
            try:
                do_rename(new_path, old_path)
                result, ok = "已还原", ok + 1
            except Exception as e:
                result, note, fail = "失败", str(e), fail + 1
        rows.append([stamp, result, os.path.basename(new_path), os.path.basename(old_path),
                     new_path, old_path, note])
        if progress and (i % 20 == 0 or i + 1 == count):
            progress("undo", i + 1, count, "正在还原 %d / %d …" % (i + 1, count))

    out = os.path.join(os.path.dirname(log_path),
                       "撤销日志_%s.csv" % datetime.now().strftime("%Y%m%d_%H%M%S"))
    try:
        write_log(out, rows)
    except Exception:
        out = ""
    return {"ok": ok, "fail": fail, "skipped": skipped, "log_path": out}
