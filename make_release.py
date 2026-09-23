# -*- coding: utf-8 -*-
"""
MyShortCut - 一鍵發布打包器 (Release Builder)
比照 Memo 工具規格產出 Release/version.txt 與 Release/MyShortCut.zip
"""
import os
import sys
import shutil
import zipfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RELEASE_DIR = os.path.join(BASE_DIR, 'Release')

RELEASE_FILES = [
    'MyShortCut.exe',
    'main.py',
    'updater.py',
    'version.txt',
    'start_MyShortCut.vbs',
    'build_exe.py',
    'README.md'
]

RELEASE_DIRS = [
    'core',
    'ui',
    'assets',
    'data'
]

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def get_current_version():
    ver_file = os.path.join(BASE_DIR, 'version.txt')
    if os.path.exists(ver_file):
        with open(ver_file, 'r', encoding='utf-8-sig') as f:
            return f.read().strip()
    return 'v1.20260917.01'

def build_release():
    print('=' * 50)
    print('[INFO] MyShortCut 檔案捷徑常駐工具 - 一鍵發布打包器')
    print('=' * 50)

    os.makedirs(RELEASE_DIR, exist_ok=True)
    version = get_current_version()
    print(f'[INFO] 當前版本號: {version}')

    # 1. 產出 Release/version.txt
    release_ver_path = os.path.join(RELEASE_DIR, 'version.txt')
    with open(release_ver_path, 'w', encoding='utf-8') as f:
        f.write(version)
    print(f'[DONE] 已產生版本檔: {release_ver_path} -> [{version}]')

    # 2. 打包 ZIP
    output_zip = os.path.join(RELEASE_DIR, 'MyShortCut.zip')
    if os.path.exists(output_zip):
        try:
            os.remove(output_zip)
        except Exception:
            pass

    print('[INFO] 正在打包更新/發布包 (MyShortCut.zip)...')
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 單一檔案
        for fname in RELEASE_FILES:
            fpath = os.path.join(BASE_DIR, fname)
            if os.path.exists(fpath):
                zf.write(fpath, arcname=fname)
                print(f'  + 加入檔案: {fname}')
            else:
                print(f'  - 略過 (不存在): {fname}')

        # 目錄
        for dname in RELEASE_DIRS:
            dpath = os.path.join(BASE_DIR, dname)
            if os.path.exists(dpath):
                for root, _, files in os.walk(dpath):
                    for file in files:
                        if file.endswith(('.pyc', '.tmp')) or '__pycache__' in root:
                            continue
                        full_file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_file_path, BASE_DIR)
                        zf.write(full_file_path, arcname=rel_path)
                        print(f'  + 加入目錄項: {rel_path}')

    print(f'[DONE] 發布包打包成功: {output_zip}')
    print('=' * 50)
    print('[DONE] 發布產物已備妥於 Release 資料夾:')
    print(f'   1. {release_ver_path}')
    print(f'   2. {output_zip}')
    print('=' * 50)

if __name__ == '__main__':
    build_release()