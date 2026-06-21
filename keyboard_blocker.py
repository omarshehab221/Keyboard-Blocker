#!/usr/bin/env python3
"""
Temporary Keyboard Blocker – low‑level keyboard hook.
- Blocks ALL keystrokes immediately.
- Press Ctrl+Shift+Q to stop blocking and restore the keyboard.
- No reboot required.

Usage:
    python keyboard_block.py
"""

import sys
import ctypes
from ctypes import wintypes
import threading

# ----------------------------------------------------------------------
# Windows API constants and types
# ----------------------------------------------------------------------
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_KEYUP = 0x0101
WM_SYSKEYUP = 0x0105

# Virtual-Key codes
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_Q = 0x51

# Low-level keyboard hook structure
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

# Function prototypes
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SetWindowsHookExW = user32.SetWindowsHookExW
SetWindowsHookExW.argtypes = [ctypes.c_int, wintypes.HANDLE, wintypes.HINSTANCE, wintypes.DWORD]
SetWindowsHookExW.restype = wintypes.HANDLE

UnhookWindowsHookEx = user32.UnhookWindowsHookEx
UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
UnhookWindowsHookEx.restype = wintypes.BOOL

CallNextHookEx = user32.CallNextHookEx
CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, ctypes.POINTER(KBDLLHOOKSTRUCT)]
CallNextHookEx.restype = wintypes.LPARAM

GetMessageW = user32.GetMessageW
GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
GetMessageW.restype = wintypes.BOOL

TranslateMessage = user32.TranslateMessage
TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
TranslateMessage.restype = wintypes.BOOL

DispatchMessageW = user32.DispatchMessageW
DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
DispatchMessageW.restype = wintypes.LPARAM

GetModuleHandleW = kernel32.GetModuleHandleW
GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
GetModuleHandleW.restype = wintypes.HINSTANCE

# Global state for modifier tracking and exit flag
ctrl_down = False
shift_down = False
exit_flag = False
hook_handle = None

# Hook procedure
def low_level_keyboard_proc(nCode, wParam, lParam):
    global ctrl_down, shift_down, exit_flag
    if nCode >= 0:
        kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        vk = kb.vkCode

        # Track modifier keys (Ctrl, Shift) based on key down/up
        if vk in (VK_LCONTROL, VK_RCONTROL):
            if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                ctrl_down = True
            elif wParam in (WM_KEYUP, WM_SYSKEYUP):
                ctrl_down = False
        elif vk in (VK_LSHIFT, VK_RSHIFT):
            if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                shift_down = True
            elif wParam in (WM_KEYUP, WM_SYSKEYUP):
                shift_down = False

        # Check for Ctrl+Shift+Q (key down)
        if ctrl_down and shift_down and vk == VK_Q and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
            exit_flag = True
            user32.PostQuitMessage(0)
            return 1  # Still block this key, but the loop will exit and unhook

        # Block all other keystrokes
        return 1

    return CallNextHookEx(0, nCode, wParam, lParam)

# Convert the Python function to a C callable
HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, wintypes.WPARAM, ctypes.POINTER(KBDLLHOOKSTRUCT))
hook_callback = HOOKPROC(low_level_keyboard_proc)

def install_hook():
    global hook_handle
    module = GetModuleHandleW(None)
    hook_handle = SetWindowsHookExW(WH_KEYBOARD_LL, hook_callback, module, 0)
    if not hook_handle:
        print("[ERROR] Failed to install keyboard hook. Are you running as administrator?")
        sys.exit(1)
    print("[*] Keyboard hook installed. ALL keys are blocked.")
    print("[*] Press Ctrl+Shift+Q to stop blocking and restore keyboard.")

def uninstall_hook():
    global hook_handle
    if hook_handle:
        UnhookWindowsHookEx(hook_handle)
        hook_handle = None

def message_loop():
    msg = wintypes.MSG()
    while GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        TranslateMessage(ctypes.byref(msg))
        DispatchMessageW(ctypes.byref(msg))
    # After PostQuitMessage, the loop ends

# ----------------------------------------------------------------------
# Elevation (must be admin for low-level hook)
# ----------------------------------------------------------------------
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except AttributeError:
        return False

def elevate():
    import subprocess, os
    script = os.path.abspath(sys.argv[0])
    params = subprocess.list2cmdline(sys.argv)
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    if ret <= 32:
        print(f"[ERROR] Could not obtain administrator privileges (error code: {ret}).")
        sys.exit(1)
    sys.exit(0)

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    if not is_admin():
        elevate()

    install_hook()
    try:
        message_loop()
    finally:
        uninstall_hook()
        print("[*] Keyboard hook removed. Keyboard is now working again.")

if __name__ == '__main__':
    main()