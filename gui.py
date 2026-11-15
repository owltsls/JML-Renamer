# -*- coding: utf-8 -*-
"""
照片文件名 "(JML)" 后缀批量清理工具 —— 完全本地的 Windows 原生窗口版。

* 不启动网页服务、不打开浏览器、不联网
* 文件夹选择对话框以主窗口为 owner（模态置顶，不会藏在后面）
* 也支持把文件夹直接拖进窗口 / 手动粘贴路径 / 拖到 EXE 图标上启动
* 核心改名逻辑复用已验证的 engine.py
"""

import os
import sys
import time
import threading
import traceback
import ctypes
from ctypes import wintypes
from datetime import datetime

import engine

# ---------------------------------------------------------------------------
# Win32 类型与函数原型
# ---------------------------------------------------------------------------
HWND = ctypes.c_void_p
HINSTANCE = ctypes.c_void_p
HICON = ctypes.c_void_p
HCURSOR = ctypes.c_void_p
HBRUSH = ctypes.c_void_p
UINT = ctypes.c_uint
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, UINT, WPARAM, LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", UINT), ("style", UINT), ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
        ("hInstance", HINSTANCE), ("hIcon", HICON), ("hCursor", HCURSOR),
        ("hbrBackground", HBRUSH), ("lpszMenuName", ctypes.c_wchar_p),
        ("lpszClassName", ctypes.c_wchar_p), ("hIconSm", HICON),
    ]


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", HWND), ("message", UINT), ("wParam", WPARAM),
                ("lParam", LPARAM), ("time", wintypes.DWORD),
                ("pt", POINT), ("lPrivate", wintypes.DWORD)]


class BROWSEINFOW(ctypes.Structure):
    _fields_ = [
        ("hwndOwner", HWND), ("pidlRoot", ctypes.c_void_p),
        ("pszDisplayName", ctypes.c_void_p), ("lpszTitle", ctypes.c_wchar_p),
        ("ulFlags", UINT), ("lpfn", ctypes.c_void_p),
        ("lParam", LPARAM), ("iImage", ctypes.c_int),
    ]


class INITCOMMONCONTROLSEX(ctypes.Structure):
    _fields_ = [("dwSize", UINT), ("dwICC", UINT)]


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
gdi32 = ctypes.windll.gdi32
shell32 = ctypes.windll.shell32
comctl32 = ctypes.windll.comctl32
ole32 = ctypes.windll.ole32

user32.CreateWindowExW.argtypes = [UINT, ctypes.c_wchar_p, ctypes.c_wchar_p, UINT,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   HWND, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
user32.CreateWindowExW.restype = HWND
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = UINT
user32.UnregisterClassW.argtypes = [ctypes.c_wchar_p, HINSTANCE]
user32.DefWindowProcW.argtypes = [HWND, UINT, WPARAM, LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.SendMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
user32.SendMessageW.restype = LRESULT
user32.PostMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), HWND, UINT, UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.SetWindowTextW.argtypes = [HWND, ctypes.c_wchar_p]
user32.GetWindowTextW.argtypes = [HWND, ctypes.c_void_p, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetDlgItem.argtypes = [HWND, ctypes.c_int]
user32.GetDlgItem.restype = HWND
user32.MessageBoxW.argtypes = [HWND, ctypes.c_wchar_p, ctypes.c_wchar_p, UINT]
user32.MessageBoxW.restype = ctypes.c_int
user32.SetTimer.argtypes = [HWND, ctypes.c_size_t, UINT, ctypes.c_void_p]
user32.SetTimer.restype = ctypes.c_size_t
user32.KillTimer.argtypes = [HWND, ctypes.c_size_t]
user32.EnableWindow.argtypes = [HWND, wintypes.BOOL]
user32.AdjustWindowRectEx.argtypes = [ctypes.POINTER(RECT), UINT, wintypes.BOOL, UINT]
user32.LoadCursorW.argtypes = [HINSTANCE, ctypes.c_void_p]
user32.LoadCursorW.restype = HCURSOR
user32.LoadIconW.argtypes = [HINSTANCE, ctypes.c_void_p]
user32.LoadIconW.restype = HICON
user32.ShowWindow.argtypes = [HWND, ctypes.c_int]
user32.UpdateWindow.argtypes = [HWND]
user32.DestroyWindow.argtypes = [HWND]
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.GetWindow.argtypes = [HWND, UINT]
user32.GetWindow.restype = HWND
# 自定义图标 + 剪贴板
user32.LoadImageW.argtypes = [HINSTANCE, ctypes.c_wchar_p, UINT,
                              ctypes.c_int, ctypes.c_int, UINT]
user32.LoadImageW.restype = HICON
user32.OpenClipboard.argtypes = [HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL
user32.SetClipboardData.argtypes = [UINT, ctypes.c_void_p]
user32.SetClipboardData.restype = ctypes.c_void_p
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL

kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
kernel32.GetModuleHandleW.restype = HINSTANCE
kernel32.GlobalAlloc.argtypes = [UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
kernel32.GlobalFree.restype = ctypes.c_void_p
gdi32.CreateFontW.argtypes = [ctypes.c_int] * 5 + [ctypes.c_uint] * 8 + [ctypes.c_wchar_p]
gdi32.CreateFontW.restype = ctypes.c_void_p
comctl32.InitCommonControlsEx.argtypes = [ctypes.POINTER(INITCOMMONCONTROLSEX)]
shell32.SHBrowseForFolderW.argtypes = [ctypes.POINTER(BROWSEINFOW)]
shell32.SHBrowseForFolderW.restype = ctypes.c_void_p
shell32.SHGetPathFromIDListW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
shell32.DragAcceptFiles.argtypes = [HWND, wintypes.BOOL]
shell32.DragQueryFileW.argtypes = [ctypes.c_void_p, UINT, ctypes.c_void_p, UINT]
shell32.DragQueryFileW.restype = UINT
shell32.DragFinish.argtypes = [ctypes.c_void_p]
ole32.OleInitialize.argtypes = [ctypes.c_void_p]
ole32.OleUninitialize.argtypes = []
ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
WINDOW_TITLE = "照片文件名 (JML) 后缀批量清理工具"
WINDOW_CLASS = "JMLRenamerNativeWnd"

WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_TABSTOP = 0x00010000
WS_VSCROLL = 0x00200000
WS_HSCROLL = 0x00100000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_EX_CLIENTEDGE = 0x00000200
WND_STYLE = WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX

SS_LEFT = 0
BS_PUSHBUTTON = 0
BS_GROUPBOX = 0x00000007
BS_AUTOCHECKBOX = 0x00000003
ES_AUTOHSCROLL = 0x0080
ES_AUTOVSCROLL = 0x0040
ES_MULTILINE = 0x0004
ES_READONLY = 0x0800
CBS_DROPDOWNLIST = 0x00000003
CBS_HASSTRINGS = 0x00000200
PBS_SMOOTH = 0x00000001

WM_COMMAND = 0x0111
WM_TIMER = 0x0113
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_SETFONT = 0x0030
WM_DROPFILES = 0x0233
WM_USER = 0x0400
BM_GETCHECK = 0x00F0
BM_SETCHECK = 0x00F1
BM_CLICK = 0x00F5
CB_ADDSTRING = 0x0143
CB_GETCURSEL = 0x0147
CB_GETLBTEXT = 0x0148
CB_RESETCONTENT = 0x014B
CB_SETCURSEL = 0x014E
PBM_SETPOS = WM_USER + 2
PBM_SETRANGE32 = WM_USER + 6
MB_OK = 0x0
MB_OKCANCEL = 0x1
MB_ICONWARNING = 0x30
MB_ICONINFORMATION = 0x40
IDOK = 1
BST_CHECKED = 1
GW_OWNER = 4
SW_SHOW = 5
CS_HREDRAW = 0x0002
CS_VREDRAW = 0x0001
COLOR_BTNFACE = 15
DEFAULT_CHARSET = 1
BIF_RETURNONLYFSDIRS = 0x0001
BIF_EDITBOX = 0x0010
BIF_NEWDIALOGSTYLE = 0x0040

# 控件 ID
ID_FOLDER = 101
ID_BROWSE = 102
ID_TAG = 103
ID_CHK_RECURSIVE = 104
ID_CHK_IGNORECASE = 105
ID_CHK_MEDIA = 106
ID_SCAN = 107
ID_CANCEL = 108
ID_STATS = 109
ID_PROGRESS = 110
ID_STATUS = 111
ID_PREVIEW = 112
ID_APPLY = 113
ID_OPENLOGS = 114
ID_QUIT = 115
ID_LOGCOMBO = 116
ID_UNDO = 117
ID_RESULT = 118
ID_APPICON = 119
ID_AUTHOR = 120
ID_COPY_WECHAT = 121

AUTHOR_WECHAT = "TheSun_Also_Rises"

# 图标 / 剪贴板相关 Win32 常量
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040
WM_SETICON = 0x0080
ICON_SMALL, ICON_BIG = 0, 1
SS_ICON = 0x0003
STM_SETICON = 0x0170
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

# ---------------------------------------------------------------------------
# 全局状态
# ---------------------------------------------------------------------------
LOCK = threading.Lock()
CANCEL = threading.Event()
STATE = {
    "state": "idle", "busy": None,
    "message": "尚未扫描。请选择文件夹后点「扫描预览」。",
    "done": 0, "total": 0,
    "stats": {"total": 0, "matched": 0, "ready": 0, "skipped": 0},
    "sample": [], "revision": 0, "result": None,
}
SCAN = None
LOG_DIR = ""
HINST = None
FONT = None
FONT_BIG = None
HWND_MAIN = None
WND_PROC = None
H = {}
LAST_TEXT = {}
LAST_REV = -1
LAST_LOGS = ""
APP_ICON_BIG = None
APP_ICON_SMALL = None


def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def icon_candidates():
    """冻结运行时优先从 PyInstaller 解压目录读取内嵌 icon.ico。"""
    paths = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            paths.append(os.path.join(meipass, "icon.ico"))
    paths.append(os.path.join(base_dir(), "icon.ico"))
    paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico"))
    return [p for p in paths if os.path.isfile(p)]


def load_app_icons():
    """返回 (大图标, 小图标)；任一路径可用即可，失败返回 (None, None)。"""
    for p in icon_candidates():
        big = user32.LoadImageW(None, p, IMAGE_ICON, 0, 0,
                                LR_LOADFROMFILE | LR_DEFAULTSIZE)
        small = user32.LoadImageW(None, p, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
        if big or small:
            return (big or small), (small or big)
    return None, None


def copy_wechat():
    """把作者微信号写入系统剪贴板（CF_UNICODETEXT）。"""
    data = AUTHOR_WECHAT.encode("utf-16-le") + b"\x00\x00"
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not handle:
        return False
    ptr = kernel32.GlobalLock(handle)
    if not ptr:
        kernel32.GlobalFree(handle)
        return False
    ctypes.memmove(ptr, data, len(data))
    kernel32.GlobalUnlock(handle)
    if not user32.OpenClipboard(HWND_MAIN):
        kernel32.GlobalFree(handle)
        return False
    user32.EmptyClipboard()
    ok = bool(user32.SetClipboardData(CF_UNICODETEXT, handle))
    user32.CloseClipboard()
    if not ok:
        kernel32.GlobalFree(handle)
    return ok


def ensure_log_dir():
    for d in (os.path.join(base_dir(), "JML工具日志"),
              os.path.join(os.path.expanduser("~"), "Documents", "JML工具日志")):
        try:
            os.makedirs(d, exist_ok=True)
            probe = os.path.join(d, ".write_test")
            with open(probe, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(probe)
            return d
        except Exception:
            continue
    import tempfile
    return tempfile.gettempdir()


def log_error(where, text):
    try:
        d = LOG_DIR or base_dir()
        with open(os.path.join(d, "错误日志.txt"), "a", encoding="utf-8") as f:
            f.write("%s [%s]\n%s\n\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), where, text))
    except Exception:
        pass


def set_state(**kw):
    with LOCK:
        STATE.update(kw)


def progress(_stage, done, total, message):
    set_state(done=done, total=total, message=message)


def list_logs():
    try:
        names = [n for n in os.listdir(LOG_DIR)
                 if n.startswith("重命名日志_") and n.lower().endswith(".csv")]
        names.sort(reverse=True)
        return names[:30]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# 控件辅助
# ---------------------------------------------------------------------------
def send(hwnd, msg, w=0, l=0):
    return user32.SendMessageW(hwnd, msg, w, l)


def get_text(hwnd):
    buf = ctypes.create_unicode_buffer(4096)
    user32.GetWindowTextW(hwnd, ctypes.addressof(buf), 4096)
    return buf.value


def set_text(hwnd, text):
    if LAST_TEXT.get(hwnd) == text:
        return
    LAST_TEXT[hwnd] = text
    user32.SetWindowTextW(hwnd, text)


def set_check(hwnd, checked):
    send(hwnd, BM_SETCHECK, 1 if checked else 0, 0)


def is_checked(hwnd):
    return send(hwnd, BM_GETCHECK, 0, 0) == BST_CHECKED


def cb_add(hwnd, text):
    buf = ctypes.create_unicode_buffer(text)
    send(hwnd, CB_ADDSTRING, 0, ctypes.addressof(buf))


def cb_selected(hwnd):
    idx = send(hwnd, CB_GETCURSEL, 0, 0)
    if idx < 0:
        return ""
    buf = ctypes.create_unicode_buffer(512)
    send(hwnd, CB_GETLBTEXT, idx, ctypes.addressof(buf))
    return buf.value


def make_font(px, bold=False):
    return gdi32.CreateFontW(-px, 0, 0, 0, 700 if bold else 400, 0, 0, 0,
                             DEFAULT_CHARSET, 0, 0, 0, 0, "Microsoft YaHei")


def create(class_name, text, style, x, y, w, h, cid, exstyle=0, big=False):
    hwnd = user32.CreateWindowExW(
        exstyle, class_name, text, style | WS_CHILD | WS_VISIBLE,
        x, y, w, h, HWND_MAIN, ctypes.c_void_p(cid), HINST, None)
    if not hwnd:
        raise ctypes.WinError(ctypes.get_last_error())
    send(hwnd, WM_SETFONT, (FONT_BIG if big else FONT) or 0, 1)
    return hwnd


def group(text, y, h):
    return create("Button", text, BS_GROUPBOX, 12, y, 976, h, 9000 + y)


def label(text, x, y, w, h, big=False, cid=None):
    return create("Static", text, SS_LEFT, x, y, w, h,
                  cid if cid is not None else 9100 + y * 10 + x, big=big)


def button(text, x, y, w, h, cid):
    return create("Button", text, BS_PUSHBUTTON | WS_TABSTOP, x, y, w, h, cid)


def checkbox(text, x, y, w, h, cid, checked):
    hwnd = create("Button", text, BS_AUTOCHECKBOX | WS_TABSTOP, x, y, w, h, cid)
    set_check(hwnd, checked)
    return hwnd


def build_controls():
    """按固定坐标创建全部控件（客户区 1000 x 760）。"""
    # 左上角软件图标；同时窗口标题栏与 EXE 本身也使用同一图标
    if APP_ICON_BIG:
        H[ID_APPICON] = create("Static", "", SS_ICON, 22, 6, 32, 32, ID_APPICON)
        send(H[ID_APPICON], STM_SETICON, APP_ICON_BIG, 0)
        title_x, title_w = 64, 918
    else:
        title_x, title_w = 22, 960
    label(WINDOW_TITLE, title_x, 12, title_w, 28, big=True)
    label("完全本地运行 · 原生窗口 · 不联网 · 不打开任何浏览器", 22, 42, 560, 20)
    H[ID_AUTHOR] = label("作者微信：" + AUTHOR_WECHAT, 588, 42, 300, 20, cid=ID_AUTHOR)
    button("复制微信号", 898, 38, 82, 26, ID_COPY_WECHAT)

    # ① 选择文件夹
    group("① 选择照片文件夹", 66, 126)
    label("照片文件夹：", 24, 88, 100, 22)
    H[ID_FOLDER] = create("Edit", "", WS_TABSTOP | ES_AUTOHSCROLL,
                          126, 84, 700, 26, ID_FOLDER, WS_EX_CLIENTEDGE)
    H[ID_BROWSE] = button("浏览文件夹…", 838, 84, 134, 28, ID_BROWSE)
    label("也可把文件夹直接拖进本窗口；或在资源管理器按 Ctrl+L 复制路径后粘贴到上方。",
          126, 114, 846, 20)
    label("要去掉的后缀：", 24, 146, 100, 22)
    H[ID_TAG] = create("Edit", engine.DEFAULT_TAG, WS_TABSTOP | ES_AUTOHSCROLL,
                       126, 142, 110, 26, ID_TAG, WS_EX_CLIENTEDGE)
    H[ID_CHK_RECURSIVE] = checkbox("包含子文件夹", 252, 144, 140, 24, ID_CHK_RECURSIVE, True)
    H[ID_CHK_IGNORECASE] = checkbox("忽略大小写", 400, 144, 120, 24, ID_CHK_IGNORECASE, True)
    H[ID_CHK_MEDIA] = checkbox("只处理图片/视频", 528, 144, 190, 24, ID_CHK_MEDIA, False)

    # ② 扫描预览
    group("② 扫描预览（不改动任何文件）", 200, 326)
    H[ID_SCAN] = button("扫描预览", 24, 222, 180, 30, ID_SCAN)
    H[ID_CANCEL] = button("停止当前任务", 214, 222, 130, 30, ID_CANCEL)
    H[ID_STATS] = label("已扫描 0 个文件  |  含该后缀 0 个  |  可安全改名 0 个  |  跳过（冲突）0 个",
                        24, 260, 950, 22, cid=ID_STATS)
    H[ID_PROGRESS] = create("msctls_progress32", "", PBS_SMOOTH, 24, 286, 952, 18, ID_PROGRESS)
    send(H[ID_PROGRESS], PBM_SETRANGE32, 0, 100)
    H[ID_STATUS] = label("尚未扫描。", 24, 310, 952, 22, cid=ID_STATUS)
    H[ID_PREVIEW] = create(
        "Edit", "", WS_VSCROLL | WS_HSCROLL | ES_MULTILINE | ES_READONLY | ES_AUTOVSCROLL,
        24, 336, 952, 176, ID_PREVIEW, WS_EX_CLIENTEDGE)

    # ③ 执行
    group("③ 确认后执行重命名", 534, 124)
    label("⚠ 请先用小批量照片试跑并备份；改后文件名已存在时自动跳过、绝不覆盖。", 24, 554, 952, 22)
    label("每次执行都会在「JML工具日志」生成 CSV 日志（原名↔新名），可随时一键撤销还原。",
          24, 574, 952, 22)
    H[ID_APPLY] = button("开始重命名", 24, 600, 170, 30, ID_APPLY)
    H[ID_OPENLOGS] = button("打开日志文件夹", 204, 600, 160, 30, ID_OPENLOGS)
    H[ID_QUIT] = button("退出程序", 374, 600, 120, 30, ID_QUIT)
    H[ID_RESULT] = label("", 24, 634, 952, 20, cid=ID_RESULT)

    # ④ 撤销
    group("④ 撤销 / 还原上一次改名", 666, 82)
    label("日志：", 24, 690, 60, 22)
    H[ID_LOGCOMBO] = create("ComboBox", "", CBS_DROPDOWNLIST | CBS_HASSTRINGS | WS_VSCROLL,
                            88, 686, 600, 180, ID_LOGCOMBO)
    H[ID_UNDO] = button("一键撤销这次改名", 700, 686, 160, 28, ID_UNDO)
    label("日志位置：" + LOG_DIR, 24, 718, 950, 20)

    # 拖放：主窗口与两个编辑框都接受文件夹拖入
    for hwnd in (HWND_MAIN, H[ID_FOLDER], H[ID_PREVIEW]):
        shell32.DragAcceptFiles(hwnd, True)


# ---------------------------------------------------------------------------
# 文件夹选择对话框（owner = 主窗口，天然置顶）
# ---------------------------------------------------------------------------
def browse_folder():
    disp = ctypes.create_unicode_buffer(260)
    bi = BROWSEINFOW()
    bi.hwndOwner = HWND_MAIN
    bi.pidlRoot = None
    bi.pszDisplayName = ctypes.addressof(disp)
    bi.lpszTitle = "请选择要处理的照片文件夹"
    bi.ulFlags = BIF_RETURNONLYFSDIRS | BIF_EDITBOX | BIF_NEWDIALOGSTYLE
    bi.lpfn = None
    bi.lParam = 0
    bi.iImage = 0
    pidl = shell32.SHBrowseForFolderW(ctypes.byref(bi))
    if not pidl:
        return ""
    buf = ctypes.create_unicode_buffer(1024)
    shell32.SHGetPathFromIDListW(pidl, ctypes.addressof(buf))
    ole32.CoTaskMemFree(pidl)
    return buf.value


def on_drop(hdrop):
    buf = ctypes.create_unicode_buffer(1024)
    shell32.DragQueryFileW(ctypes.c_void_p(hdrop), 0, ctypes.addressof(buf), 1024)
    path = buf.value
    shell32.DragFinish(ctypes.c_void_p(hdrop))
    if os.path.isdir(path):
        set_text(H[ID_FOLDER], path)


# ---------------------------------------------------------------------------
# 后台任务（只更新 STATE，界面由定时器统一刷新）
# ---------------------------------------------------------------------------
def start_worker(name, target, args=()):
    with LOCK:
        if STATE["busy"]:
            return False
        STATE["busy"] = name
    CANCEL.clear()
    threading.Thread(target=target, args=args, daemon=True).start()
    return True


def scan_worker(data):
    global SCAN
    try:
        set_state(state="scanning", message="正在扫描文件夹…", done=0, total=0, result=None)
        res = engine.scan(data["folder"], tag=data["tag"], recursive=data["recursive"],
                          ignore_case=data["ignoreCase"], only_media=data["onlyMedia"],
                          progress=progress, cancel=CANCEL)
        SCAN = res
        sample = [{
            "old": r["old_name"], "new": r["new_name"], "status": r["status"],
            "note": r["note"] or os.path.relpath(os.path.dirname(r["old_path"]), res["folder"]),
        } for r in res["records"][:150]]
        with LOCK:
            STATE["stats"] = {"total": res["total"], "matched": res["matched"],
                              "ready": res["ready"], "skipped": res["skipped"]}
            STATE["sample"] = sample
            STATE["revision"] += 1
            STATE["state"] = "scanned"
            STATE["result"] = None
            STATE["message"] = ("扫描完成：共检查 %d 个文件，%d 个含后缀，%d 个可改名，%d 个将跳过。"
                                % (res["total"], res["matched"], res["ready"], res["skipped"]))
            STATE["done"] = res["total"]
            STATE["total"] = res["total"]
    except Exception:
        log_error("scan", traceback.format_exc())
        set_state(state="error", message="扫描失败，详情见「错误日志.txt」")
    finally:
        set_state(busy=None)


def apply_worker():
    global SCAN
    try:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(LOG_DIR, "重命名日志_%s.csv" % stamp)
        set_state(state="applying", message="正在重命名…", done=0, result=None)
        res = engine.apply(SCAN, log_path, progress=progress, cancel=CANCEL)
        with LOCK:
            STATE["result"] = {"ok": res["ok"], "fail": res["fail"],
                               "cancelled": res["cancelled"], "log_path": res["log_path"]}
            STATE["state"] = "done"
            STATE["message"] = ("执行完成：成功 %d 个，失败 %d 个%s。可在下方一键撤销。"
                                % (res["ok"], res["fail"], "（已中途停止）" if res["cancelled"] else ""))
            STATE["revision"] += 1
    except Exception:
        log_error("apply", traceback.format_exc())
        set_state(state="error", message="重命名失败，详情见「错误日志.txt」")
    finally:
        set_state(busy=None)


def undo_worker(name):
    global SCAN
    try:
        log_path = os.path.join(LOG_DIR, os.path.basename(name))
        set_state(state="undoing", message="正在还原…", done=0, result=None)
        res = engine.undo(log_path, progress=progress, cancel=CANCEL)
        SCAN = None
        with LOCK:
            STATE["result"] = {"ok": res["ok"], "fail": res["fail"],
                               "skipped": res["skipped"], "log_path": res["log_path"]}
            STATE["state"] = "undone"
            STATE["message"] = ("撤销完成：已还原 %d 个，跳过 %d 个，失败 %d 个。请重新扫描。"
                                % (res["ok"], res["skipped"], res["fail"]))
            STATE["stats"] = {"total": 0, "matched": 0, "ready": 0, "skipped": 0}
            STATE["sample"] = []
            STATE["revision"] += 1
    except Exception:
        log_error("undo", traceback.format_exc())
        set_state(state="error", message="撤销失败，详情见「错误日志.txt」")
    finally:
        set_state(busy=None)


# ---------------------------------------------------------------------------
# 界面刷新
# ---------------------------------------------------------------------------
def format_preview(sample):
    lines = [
        "序号   原文件名    →    改后文件名    [状态]   说明 / 所在文件夹",
        "-" * 118,
    ]
    if not sample:
        lines.append("（还没有扫描结果。扫描后这里会列出改名对照，最多显示前 150 条。）")
    for i, r in enumerate(sample, 1):
        lines.append("%3d.  %s   →   %s   [%s]   %s"
                     % (i, r["old"], r["new"], r["status"], r["note"]))
    return "\r\n".join(lines)


def refresh_ui():
    global LAST_REV, LAST_LOGS
    with LOCK:
        snap = {k: STATE[k] for k in ("state", "busy", "message", "done", "total",
                                      "stats", "sample", "revision", "result")}
    st = snap["stats"]
    set_text(H[ID_STATS], "已扫描 %d 个文件  |  含该后缀 %d 个  |  可安全改名 %d 个  |  跳过（冲突）%d 个"
             % (st["total"], st["matched"], st["ready"], st["skipped"]))
    set_text(H[ID_STATUS], snap["message"])

    pct = int(snap["done"] / snap["total"] * 100) if snap["total"] > 0 else 0
    send(H[ID_PROGRESS], PBM_SETPOS, min(100, max(0, pct)), 0)

    res = snap["result"]
    if res and snap["state"] == "done":
        text = ("重命名：成功 %d 个，失败 %d 个  |  日志 %s"
                % (res["ok"], res["fail"], res["log_path"] or "（写入失败）"))
    elif res and snap["state"] == "undone":
        text = ("撤销：已还原 %d 个，跳过 %d 个，失败 %d 个  |  日志 %s"
                % (res["ok"], res["skipped"], res["fail"], res["log_path"] or "（写入失败）"))
    else:
        text = ""
    set_text(H[ID_RESULT], text)

    busy = bool(snap["busy"])
    user32.EnableWindow(H[ID_SCAN], not busy)
    user32.EnableWindow(H[ID_BROWSE], not busy)
    user32.EnableWindow(H[ID_TAG], not busy)
    user32.EnableWindow(H[ID_FOLDER], not busy)
    user32.EnableWindow(H[ID_CANCEL], busy)
    user32.EnableWindow(H[ID_APPLY], (not busy) and snap["state"] == "scanned" and st["ready"] > 0)
    user32.EnableWindow(H[ID_UNDO], not busy)

    if snap["revision"] != LAST_REV:
        LAST_REV = snap["revision"]
        set_text(H[ID_PREVIEW], format_preview(snap["sample"]))

    logs = list_logs()
    key = "\n".join(logs)
    if key != LAST_LOGS:
        LAST_LOGS = key
        send(H[ID_LOGCOMBO], CB_RESETCONTENT, 0, 0)
        for n in logs:
            cb_add(H[ID_LOGCOMBO], n)
        if logs:
            send(H[ID_LOGCOMBO], CB_SETCURSEL, 0, 0)
        else:
            cb_add(H[ID_LOGCOMBO], "（暂无日志）")


# ---------------------------------------------------------------------------
# 消息处理
# ---------------------------------------------------------------------------
def confirm(hwnd, text, title="请确认"):
    return user32.MessageBoxW(hwnd, text, title, MB_OKCANCEL | MB_ICONWARNING) == IDOK


def info(hwnd, text, title="提示"):
    user32.MessageBoxW(hwnd, text, title, MB_OK | MB_ICONINFORMATION)


def on_command(cid):
    if cid == ID_BROWSE:
        path = browse_folder()
        if path:
            set_text(H[ID_FOLDER], path)

    elif cid == ID_SCAN:
        folder = get_text(H[ID_FOLDER]).strip().strip('"')
        if not os.path.isdir(folder):
            info(HWND_MAIN, "文件夹不存在或路径不正确：\n%s\n\n可点「浏览文件夹…」选择，或把文件夹拖进窗口。" % folder)
            return
        data = {
            "folder": folder,
            "tag": get_text(H[ID_TAG]).strip() or engine.DEFAULT_TAG,
            "recursive": is_checked(H[ID_CHK_RECURSIVE]),
            "ignoreCase": is_checked(H[ID_CHK_IGNORECASE]),
            "onlyMedia": is_checked(H[ID_CHK_MEDIA]),
        }
        start_worker("scan", scan_worker, (data,))

    elif cid == ID_CANCEL:
        CANCEL.set()

    elif cid == ID_APPLY:
        if SCAN is None or STATE["stats"]["ready"] <= 0:
            info(HWND_MAIN, "请先扫描，并确认有可改名的文件。")
            return
        if not confirm(HWND_MAIN,
                       "即将重命名 %d 个文件，去掉文件名中的「%s」后缀。\n\n"
                       "请确认已备份或在测试文件夹验证过，且预览结果符合预期。\n"
                       "目标文件名已存在的会自动跳过、绝不覆盖；执行后可一键撤销。"
                       % (STATE["stats"]["ready"], get_text(H[ID_TAG]).strip() or engine.DEFAULT_TAG),
                       "确认执行重命名"):
            return
        start_worker("apply", apply_worker)

    elif cid == ID_UNDO:
        name = cb_selected(H[ID_LOGCOMBO])
        if not name.startswith("重命名日志_"):
            info(HWND_MAIN, "请先选择一份重命名日志。")
            return
        if not confirm(HWND_MAIN,
                       "将按日志「%s」把文件还原为原始名称。\n若原文件名已被占用会自动跳过，不会覆盖。" % name,
                       "确认撤销"):
            return
        start_worker("undo", undo_worker, (name,))

    elif cid == ID_OPENLOGS:
        try:
            os.startfile(LOG_DIR)
        except Exception as e:
            info(HWND_MAIN, "无法打开日志文件夹：%s" % e)

    elif cid == ID_COPY_WECHAT:
        if copy_wechat():
            set_state(message="作者微信号已复制到剪贴板：%s（可直接粘贴到微信搜索）" % AUTHOR_WECHAT)
        else:
            info(HWND_MAIN, "自动复制失败，请手动记下微信号：\n%s" % AUTHOR_WECHAT)

    elif cid == ID_QUIT:
        user32.PostMessageW(HWND_MAIN, WM_CLOSE, 0, 0)


def handle_message(hwnd, msg, wparam, lparam):
    if msg == WM_COMMAND:
        on_command(wparam & 0xFFFF)
        return 0
    if msg == WM_TIMER:
        refresh_ui()
        return 0
    if msg == WM_DROPFILES:
        on_drop(wparam)
        return 0
    if msg == WM_CLOSE:
        if STATE["busy"]:
            info(hwnd, "任务正在进行中，请等它完成（或点「停止当前任务」）后再退出。")
            return 0
        user32.DestroyWindow(hwnd)
        return 0
    if msg == WM_DESTROY:
        user32.KillTimer(hwnd, 1)
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def wnd_proc_impl(hwnd, msg, wparam, lparam):
    try:
        return handle_message(hwnd, msg, wparam, lparam)
    except Exception:
        log_error("wndproc msg=%s" % msg, traceback.format_exc())
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


# ---------------------------------------------------------------------------
# 打包后自检（--selftest，不创建窗口）
# ---------------------------------------------------------------------------
def frozen_selftest():
    import shutil
    import tempfile
    lines = ["EXE 自检 " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    tmp = os.path.join(tempfile.gettempdir(), "jml_gui_exe_selftest")
    try:
        if os.path.exists(tmp):
            shutil.rmtree(tmp)
        os.makedirs(tmp)
        for n in ("A (JML).jpg", "B (JML).mp4", "A.jpg"):
            with open(os.path.join(tmp, n), "w", encoding="utf-8") as f:
                f.write("x")
        r = engine.scan(tmp)
        logp = os.path.join(tmp, "log.csv")
        a = engine.apply(r, logp)
        u = engine.undo(logp)
        lines.append("扫描：共 %d，匹配 %d，可改名 %d，跳过 %d"
                     % (r["total"], r["matched"], r["ready"], r["skipped"]))
        lines.append("改名成功 %d，撤销还原 %d" % (a["ok"], u["ok"]))
        assert r["matched"] == 2 and a["ok"] == 1 and u["ok"] == 1

        # 验证窗口类注册可用（结构体 / 回调签名正确）
        dummy = WNDPROC(lambda h, m, w, l: user32.DefWindowProcW(h, m, w, l))
        inst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW(ctypes.sizeof(WNDCLASSEXW), CS_HREDRAW | CS_VREDRAW, dummy,
                         0, 0, inst, None, None, ctypes.c_void_p(COLOR_BTNFACE + 1),
                         None, "JMLSelfTestWnd", None)
        atom = user32.RegisterClassExW(ctypes.byref(wc))
        assert atom, "RegisterClassExW 失败"
        user32.UnregisterClassW("JMLSelfTestWnd", inst)
        lines.append("原生窗口类注册测试通过")
        big, small = load_app_icons()
        lines.append("图标资源：大图标 %s / 小图标 %s"
                     % ("OK" if big else "缺失", "OK" if small else "缺失"))
        assert big and small, "icon.ico 加载失败（检查打包时是否内嵌）"
        lines.append("作者微信：%s" % AUTHOR_WECHAT)
        assert AUTHOR_WECHAT
        lines.append("结论：全部通过")
        shutil.rmtree(tmp)
    except Exception:
        lines.append("结论：失败")
        lines.append(traceback.format_exc())
    try:
        with open(os.path.join(base_dir(), "EXE自检结果.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main():
    global LOG_DIR, HINST, FONT, FONT_BIG, HWND_MAIN, WND_PROC
    global APP_ICON_BIG, APP_ICON_SMALL
    if "--selftest" in sys.argv:
        frozen_selftest()
        sys.exit(0)

    LOG_DIR = ensure_log_dir()
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass
    ole32.OleInitialize(None)
    icc = INITCOMMONCONTROLSEX(ctypes.sizeof(INITCOMMONCONTROLSEX), 0x0004)  # ICC_PROGRESS_CLASS
    comctl32.InitCommonControlsEx(ctypes.byref(icc))

    HINST = kernel32.GetModuleHandleW(None)
    FONT = make_font(14)
    FONT_BIG = make_font(18, True)
    WND_PROC = WNDPROC(wnd_proc_impl)

    APP_ICON_BIG, APP_ICON_SMALL = load_app_icons()
    default_icon = user32.LoadIconW(None, ctypes.c_void_p(32512))
    wc = WNDCLASSEXW(
        ctypes.sizeof(WNDCLASSEXW), CS_HREDRAW | CS_VREDRAW, WND_PROC,
        0, 0, HINST,
        APP_ICON_BIG or default_icon,
        user32.LoadCursorW(None, ctypes.c_void_p(32512)),
        ctypes.c_void_p(COLOR_BTNFACE + 1), None, WINDOW_CLASS,
        APP_ICON_SMALL or APP_ICON_BIG or default_icon)
    if not user32.RegisterClassExW(ctypes.byref(wc)):
        raise ctypes.WinError(ctypes.get_last_error())

    rect = RECT(0, 0, 1000, 760)
    user32.AdjustWindowRectEx(ctypes.byref(rect), WND_STYLE, False, 0)
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    HWND_MAIN = user32.CreateWindowExW(0, WINDOW_CLASS, WINDOW_TITLE, WND_STYLE,
                                       120, 50, width, height, None, None, HINST, None)
    if not HWND_MAIN:
        raise ctypes.WinError(ctypes.get_last_error())
    if APP_ICON_BIG:
        user32.SendMessageW(HWND_MAIN, WM_SETICON, ICON_BIG, APP_ICON_BIG)
    if APP_ICON_SMALL:
        user32.SendMessageW(HWND_MAIN, WM_SETICON, ICON_SMALL, APP_ICON_SMALL)

    build_controls()
    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1].strip().strip('"')):
        set_text(H[ID_FOLDER], os.path.abspath(sys.argv[1].strip().strip('"')))

    set_state(message="就绪。请选择文件夹，或直接把文件夹拖进本窗口，然后点「扫描预览」。")
    refresh_ui()
    user32.ShowWindow(HWND_MAIN, SW_SHOW)
    user32.UpdateWindow(HWND_MAIN)
    user32.SetTimer(HWND_MAIN, 1, 200, 0)

    msg = MSG()
    while True:
        ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if ret <= 0:
            break
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
    ole32.OleUninitialize()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        text = traceback.format_exc()
        log_error("main", text)
        try:
            user32.MessageBoxW(None, "程序启动失败：\n%s" % text[-600:], WINDOW_TITLE, MB_OK | MB_ICONWARNING)
        except Exception:
            pass
