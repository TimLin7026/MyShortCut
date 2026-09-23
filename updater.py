# -*- coding: utf-8 -*-
"""
MyShortCut - 自動更新比對與下載覆蓋模組 (預留架構，比照 Memo 工具規格)
"""
import os
import sys
import re
import time
import zipfile
import shutil
import urllib.request
import urllib.error

# 預留更新伺服器位址 (前期開發預設保留，啟用時配置實際 URL)
RELEASE_BASE_URL = 'http://10.40.140.62:8888/MyShortCut'
VERSION_URL = f'{RELEASE_BASE_URL}/version.txt'
UPDATE_ZIP_URL = f'{RELEASE_BASE_URL}/MyShortCut.zip'

def parse_version_tuple(v_str):
    if not v_str:
        return (0,)
    match = re.search(r'v?([\d\.]+)', str(v_str))
    if match:
        try:
            return tuple(int(x) for x in match.group(1).split('.') if x.isdigit())
        except Exception:
            pass
    return (0,)

def get_local_version(target_dir=None):
    if target_dir is None:
        target_dir = os.path.dirname(os.path.abspath(__file__))
    ver_path = os.path.join(target_dir, 'version.txt')
    if os.path.exists(ver_path):
        try:
            with open(ver_path, 'r', encoding='utf-8-sig') as f:
                return f.read().strip()
        except Exception:
            pass
    return 'v1.20260917.01'

def safe_extract_and_overwrite(zip_path, target_dir, log_func=print):
    """
    使用 zipfile 自動解壓縮並覆蓋本地檔案，
    支援 Windows 檔案佔用時重命名為 .old 的熱更換機制。
    """
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.infolist():
            filename = member.filename.replace('\\', '/')
            if filename.startswith('/') or '..' in filename:
                continue
            
            dest_path = os.path.join(target_dir, filename)
            if member.is_dir():
                os.makedirs(dest_path, exist_ok=True)
                continue
            
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            data = zf.read(member)
            
            try:
                with open(dest_path, 'wb') as f_out:
                    f_out.write(data)
                log_func(f'  + 更新: {filename}')
            except (PermissionError, OSError):
                old_path = dest_path + f'.old_{int(time.time())}'
                try:
                    if os.path.exists(old_path):
                        os.remove(old_path)
                except Exception:
                    pass
                
                try:
                    os.rename(dest_path, old_path)
                    with open(dest_path, 'wb') as f_out:
                        f_out.write(data)
                    log_func(f'  + 熱更換 (佔用重命名): {filename}')
                except Exception as ex:
                    log_func(f'  ❌ 更新失敗 {filename}: {ex}')
                    raise

def cleanup_old_files(target_dir=None):
    """清理歷史留下的 .old 備份暫存檔"""
    if target_dir is None:
        target_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        for f in os.listdir(target_dir):
            if '.old' in f:
                full_p = os.path.join(target_dir, f)
                try:
                    if os.path.isfile(full_p):
                        os.remove(full_p)
                except Exception:
                    pass
    except Exception:
        pass

def check_and_apply_update(target_dir=None, log_func=print, timeout=3, enabled=False):
    """
    預留自動比對與更新介面
    enabled: 預設為 False，前期不執行自動下載，待上線後開啟
    """
    if not enabled:
        return False

    if target_dir is None:
        target_dir = os.path.dirname(os.path.abspath(__file__))

    cleanup_old_files(target_dir)

    local_ver_str = get_local_version(target_dir)
    log_func(f'📡 正在連線 Release 站台檢查更新... (目前本地版本: {local_ver_str})')

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) MyShortCutUpdater/1.0'}

    try:
        req = urllib.request.Request(VERSION_URL, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as res:
            remote_ver_str = res.read().decode('utf-8-sig').strip()
    except Exception as e:
        log_func(f'⚠️ 無法連線至 Release 站台 ({e})，略過更新，正常啟動。')
        return False

    remote_val = parse_version_tuple(remote_ver_str)
    local_val = parse_version_tuple(local_ver_str)

    if remote_val <= local_val:
        log_func(f'✅ 目前已是最新版本 ({local_ver_str})。')
        return False

    log_func(f'📥 發現新版本 [{remote_ver_str}] > 本地 [{local_ver_str}]！')
    log_func(f'⏳ 正在下載更新包 ({UPDATE_ZIP_URL})...')

    temp_zip_path = os.path.join(target_dir, '_temp_update.zip')
    try:
        req_dl = urllib.request.Request(UPDATE_ZIP_URL, headers=headers)
        with urllib.request.urlopen(req_dl, timeout=60) as res_dl:
            content = res_dl.read()
            if len(content) < 100:
                log_func(f'❌ 下載的更新包大小異常 ({len(content)} bytes)，略過更新。')
                return False
            with open(temp_zip_path, 'wb') as f_out:
                f_out.write(content)
    except Exception as e:
        log_func(f'❌ 下載更新包失敗: {e}，略過更新。')
        if os.path.exists(temp_zip_path):
            try: os.remove(temp_zip_path)
            except Exception: pass
        return False

    log_func('📦 正在執行自動解壓縮覆蓋更新...')
    try:
        safe_extract_and_overwrite(temp_zip_path, target_dir, log_func=log_func)

        ver_path = os.path.join(target_dir, 'version.txt')
        with open(ver_path, 'w', encoding='utf-8') as f_ver:
            f_ver.write(remote_ver_str)

        log_func(f'✨ 🌟 自動解壓縮更新完成！已成功升級至 [{remote_ver_str}]！')
        return True
    except Exception as e:
        log_func(f'❌ 執行解壓縮更新異常: {e}')
        return False
    finally:
        if os.path.exists(temp_zip_path):
            try:
                time.sleep(0.3)
                os.remove(temp_zip_path)
            except Exception:
                pass