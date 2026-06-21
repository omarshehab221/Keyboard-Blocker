#!/usr/bin/env python3
"""
Keyboard Disable/Enable – Final version with file logging.
Usage:
    python keyboard_control.py off [--all]     # disable first keyboard (or all with --all)
    python keyboard_control.py on  [--all]     # re-enable
All output is written both to the console and to keyboard_control.log
"""

import sys
import platform
import subprocess
import ctypes
from ctypes import wintypes
import os
import traceback
from datetime import datetime

# ----------------------------------------------------------------------
# File logging
# ----------------------------------------------------------------------
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "keyboard_control.log")

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ----------------------------------------------------------------------
# Elevation
# ----------------------------------------------------------------------
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except AttributeError:
        return False

def elevate():
    """Re-launch the script with administrator privileges (UAC prompt)."""
    script = os.path.abspath(sys.argv[0])
    params = subprocess.list2cmdline([script] + sys.argv[1:])
    log("[*] Requesting administrator privileges...")
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    if ret <= 32:
        log(f"[ERROR] ShellExecuteW failed with code {ret}.")
        input("Press Enter to exit...")
        sys.exit(1)
    sys.exit(0)

# ----------------------------------------------------------------------
# Windows API constants and structures
# ----------------------------------------------------------------------
DIGCF_PRESENT = 0x00000002
DIGCF_ALLCLASSES = 0x00000004
DIF_PROPERTYCHANGE = 0x00000012
DICS_DISABLE = 1
DICS_ENABLE = 2
CM_PROB_DISABLED = 22
SPDRP_DEVICEDESC = 0x00000000
SPDRP_HARDWAREID = 0x00000001

class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", ctypes.c_char * 16),
        ("DevInst", wintypes.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]

class SP_CLASSINSTALL_HEADER(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InstallFunction", wintypes.DWORD),
    ]

class SP_PROPCHANGE_PARAMS(ctypes.Structure):
    _fields_ = [
        ("ClassInstallHeader", SP_CLASSINSTALL_HEADER),
        ("StateChange", wintypes.DWORD),
        ("Scope", wintypes.DWORD),
        ("HwProfile", wintypes.DWORD),
    ]

# Load DLLs
setupapi = ctypes.windll.setupapi
cfgmgr32 = ctypes.windll.cfgmgr32

# SetupAPI function prototypes (with corrected buffer type)
SetupDiGetClassDevs = setupapi.SetupDiGetClassDevsW
SetupDiGetClassDevs.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
SetupDiGetClassDevs.restype = wintypes.HANDLE

SetupDiEnumDeviceInfo = setupapi.SetupDiEnumDeviceInfo
SetupDiEnumDeviceInfo.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(SP_DEVINFO_DATA)]
SetupDiEnumDeviceInfo.restype = wintypes.BOOL

# FIX: PropertyBuffer must be LPWSTR for the W-version, not LPBYTE.
SetupDiGetDeviceRegistryProperty = setupapi.SetupDiGetDeviceRegistryPropertyW
SetupDiGetDeviceRegistryProperty.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(SP_DEVINFO_DATA), wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD)
]
SetupDiGetDeviceRegistryProperty.restype = wintypes.BOOL

SetupDiSetClassInstallParams = setupapi.SetupDiSetClassInstallParamsW
SetupDiSetClassInstallParams.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(SP_DEVINFO_DATA),
    ctypes.POINTER(SP_PROPCHANGE_PARAMS), wintypes.DWORD
]
SetupDiSetClassInstallParams.restype = wintypes.BOOL

SetupDiCallClassInstaller = setupapi.SetupDiCallClassInstaller
SetupDiCallClassInstaller.argtypes = [wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(SP_DEVINFO_DATA)]
SetupDiCallClassInstaller.restype = wintypes.BOOL

SetupDiDestroyDeviceInfoList = setupapi.SetupDiDestroyDeviceInfoList
SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL

# cfgmgr32
CM_Get_DevNode_Status = cfgmgr32.CM_Get_DevNode_Status
CM_Get_DevNode_Status.argtypes = [
    ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
    wintypes.DWORD, wintypes.DWORD
]
CM_Get_DevNode_Status.restype = wintypes.DWORD

CM_Disable_DevNode = cfgmgr32.CM_Disable_DevNode
CM_Disable_DevNode.argtypes = [wintypes.DWORD, wintypes.DWORD]
CM_Disable_DevNode.restype = wintypes.DWORD

CM_Enable_DevNode = cfgmgr32.CM_Enable_DevNode
CM_Enable_DevNode.argtypes = [wintypes.DWORD, wintypes.DWORD]
CM_Enable_DevNode.restype = wintypes.DWORD

CM_Get_Device_IDW = cfgmgr32.CM_Get_Device_IDW
CM_Get_Device_IDW.argtypes = [wintypes.DWORD, wintypes.LPWSTR, wintypes.ULONG, wintypes.ULONG]
CM_Get_Device_IDW.restype = wintypes.DWORD

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def get_dev_prop(dev_info_set, dev_info_data, prop):
    buf_size = wintypes.DWORD(0)
    # First call to get required buffer size (in bytes)
    SetupDiGetDeviceRegistryProperty(dev_info_set, ctypes.byref(dev_info_data), prop,
                                     None, None, 0, ctypes.byref(buf_size))
    if buf_size.value == 0:
        return ""
    # The buffer size returned is in bytes, but we're using LPWSTR, so we need a buffer of (buf_size // 2) WCHARs.
    # However, we can simply create a unicode buffer of length buf_size.value (it will allocate that many characters,
    # but ctypes will treat it as WCHAR array, which uses 2 bytes per char. The function will write up to buf_size bytes.
    # So we pass the same buf_size value as the buffer's allocated size in bytes.
    # To be safe, we allocate a buffer of (buf_size.value // 2 + 1) characters to avoid overflow.
    char_count = buf_size.value // 2 + 1
    buf = ctypes.create_unicode_buffer(char_count)
    # The 'BufferSize' parameter is still in bytes, so we pass buf_size.value.
    if SetupDiGetDeviceRegistryProperty(dev_info_set, ctypes.byref(dev_info_data), prop,
                                        None, buf, buf_size, ctypes.byref(buf_size)):
        return buf.value
    return ""

def get_instance_id(dev_inst):
    buf = ctypes.create_unicode_buffer(256)
    if CM_Get_Device_IDW(dev_inst, buf, 255, 0) == 0:
        return buf.value
    return ""

def is_disabled(dev_inst):
    status = wintypes.DWORD()
    prob = wintypes.DWORD()
    if CM_Get_DevNode_Status(ctypes.byref(status), ctypes.byref(prob), dev_inst, 0) != 0:
        return False
    return prob.value == CM_PROB_DISABLED

def log_device(dev_info_set, dev_info_data):
    desc = get_dev_prop(dev_info_set, dev_info_data, SPDRP_DEVICEDESC)
    hwid = get_dev_prop(dev_info_set, dev_info_data, SPDRP_HARDWAREID)
    inst_id = get_instance_id(dev_info_data.DevInst)
    disabled = is_disabled(dev_info_data.DevInst)
    log(f"  Description: {desc}")
    log(f"  Hardware ID: {hwid}")
    log(f"  Instance ID: {inst_id}")
    log(f"  Currently disabled: {disabled}")
    return inst_id, desc

def method1_propertychange(dev_info_set, dev_info_data, enable):
    state = DICS_ENABLE if enable else DICS_DISABLE
    params = SP_PROPCHANGE_PARAMS()
    params.ClassInstallHeader.cbSize = ctypes.sizeof(SP_CLASSINSTALL_HEADER)
    params.ClassInstallHeader.InstallFunction = DIF_PROPERTYCHANGE
    params.StateChange = state
    params.Scope = 1
    params.HwProfile = 0
    if SetupDiSetClassInstallParams(dev_info_set, ctypes.byref(dev_info_data), ctypes.byref(params), ctypes.sizeof(params)):
        if SetupDiCallClassInstaller(DIF_PROPERTYCHANGE, dev_info_set, ctypes.byref(dev_info_data)):
            return True
        else:
            log(f"    Method 1: SetupDiCallClassInstaller failed, err={ctypes.get_last_error()}")
    else:
        log(f"    Method 1: SetupDiSetClassInstallParams failed, err={ctypes.get_last_error()}")
    return False

def method2_cm(dev_inst, enable):
    func = CM_Enable_DevNode if enable else CM_Disable_DevNode
    res = func(dev_inst, 0)
    if res == 0:
        return True
    log(f"    Method 2: CM_*_DevNode failed, error={res}")
    return False

def method3_powershell(instance_id, enable):
    if not instance_id:
        log("    Method 3: No instance ID, skipping PowerShell")
        return False
    cmd = (f'Enable-PnpDevice -InstanceId "{instance_id}" -Confirm:$false -ErrorAction Stop' if enable
           else f'Disable-PnpDevice -InstanceId "{instance_id}" -Confirm:$false -ErrorAction Stop')
    try:
        proc = subprocess.run(
            ['powershell', '-NoProfile', '-Command', cmd],
            capture_output=True, text=True, timeout=30
        )
        if proc.returncode == 0:
            return True
        else:
            log(f"    Method 3: PowerShell error: {proc.stderr.strip() or proc.stdout.strip()}")
    except Exception as e:
        log(f"    Method 3: PowerShell exception: {e}")
    return False

def attempt_change(dev_info_set, dev_info_data, enable):
    action = "enable" if enable else "disable"
    log(f"  Attempting to {action}...")
    instance_id, _ = log_device(dev_info_set, dev_info_data)

    # Method 1
    if method1_propertychange(dev_info_set, dev_info_data, enable):
        if is_disabled(dev_info_data.DevInst) != enable:
            log("  -> Method 1 succeeded.")
            return True
        else:
            log("  -> Method 1 reported success but state unchanged. Trying Method 2...")
    else:
        log("  -> Method 1 failed, trying Method 2...")

    # Method 2
    if method2_cm(dev_info_data.DevInst, enable):
        if is_disabled(dev_info_data.DevInst) != enable:
            log("  -> Method 2 succeeded.")
            return True
        else:
            log("  -> Method 2 reported success but state unchanged. Trying Method 3...")
    else:
        log("  -> Method 2 failed, trying Method 3...")

    # Method 3
    if method3_powershell(instance_id, enable):
        if is_disabled(dev_info_data.DevInst) != enable:
            log("  -> Method 3 succeeded.")
            return True
        else:
            log("  -> Method 3 reported success but state unchanged (unusual).")
    else:
        log("  -> Method 3 failed.")

    log("  -> ALL METHODS FAILED.")
    return False

def find_keyboard_devices():
    log("[*] Scanning for keyboard devices...")
    flags = DIGCF_PRESENT | DIGCF_ALLCLASSES
    h = SetupDiGetClassDevs(None, None, None, flags)
    if h == wintypes.HANDLE(-1).value:
        log("[ERROR] SetupDiGetClassDevs failed.")
        return []

    devices = []
    dev = SP_DEVINFO_DATA()
    dev.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
    idx = 0
    while SetupDiEnumDeviceInfo(h, idx, ctypes.byref(dev)):
        desc = get_dev_prop(h, dev, SPDRP_DEVICEDESC)
        hwid = get_dev_prop(h, dev, SPDRP_HARDWAREID)
        combined = (desc + hwid).lower()
        if "keyboard" in combined:
            devices.append((h, dev))
        idx += 1
        dev = SP_DEVINFO_DATA()
        dev.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)

    if not devices:
        SetupDiDestroyDeviceInfoList(h)
        log("[!] No keyboard devices found. Is the keyboard connected?")
        return []
    log(f"[*] Found {len(devices)} keyboard device(s).")
    return devices

# ----------------------------------------------------------------------
# Main action
# ----------------------------------------------------------------------
def run_action(enable, all_devices):
    if not is_admin():
        log("[*] Not running as admin. Elevating...")
        elevate()  # This exits the current process

    devices = find_keyboard_devices()
    if not devices:
        log("[ERROR] Cannot proceed without devices.")
        input("Press Enter to exit...")
        sys.exit(1)

    if not all_devices:
        log("[*] Only the first device will be targeted. Use --all to target all.")
        devices = [devices[0]]

    success = 0
    for h, dev in devices:
        log("\n" + "=" * 60)
        try:
            if attempt_change(h, dev, enable):
                success += 1
            else:
                log("[!] Failed to change state for this device.")
        except Exception:
            log("Exception during attempt:")
            log(traceback.format_exc())

    # Cleanup
    try:
        SetupDiDestroyDeviceInfoList(devices[0][0])
    except:
        pass

    state_str = "enabled" if enable else "disabled"
    log(f"\n[SUMMARY] {success}/{len(devices)} keyboard(s) {state_str}.")
    if success == 0 and not enable:
        log("If the keyboard still works, please copy the entire keyboard_control.log file and share it for further help.")
    input("\nPress Enter to exit...")

# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    action = sys.argv[1].lower()
    if action not in ('off', 'on', 'disable', 'enable'):
        print(__doc__)
        sys.exit(1)

    enable = action in ('on', 'enable')
    all_devices = '--all' in sys.argv or '-a' in sys.argv

    if platform.system() != 'Windows':
        log("This script only supports Windows.")
        sys.exit(1)

    try:
        run_action(enable, all_devices)
    except Exception as e:
        log("FATAL ERROR:")
        log(traceback.format_exc())
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == '__main__':
    main()