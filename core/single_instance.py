# -*- coding: utf-8 -*-
"""
MyShortCut - 單一實例管理與 IPC 通訊模組 (支援重複點擊喚醒與版本更新智慧接管)
"""
import socket
import threading
import json
import time
import sys
from typing import Callable, Optional

DEFAULT_PORT = 48991
LOCALHOST = "127.0.0.1"

class SingleInstanceManager:
    def __init__(self, version: str, on_show_request: Optional[Callable] = None, on_exit_request: Optional[Callable] = None):
        self.version = version
        self.on_show_request = on_show_request
        self.on_exit_request = on_exit_request
        self.server_sock = None
        self.is_running = False

    def check_and_bind(self, force_replace: bool = False) -> bool:
        """
        檢查是否已有既有實例在運行。
        若有既有實例：
          - 若同版本且未強制替換：通知舊實例顯示視窗，返回 False (代表當前新實例應退出)
          - 若不同版本或強制替換：通知舊實例關閉退出，等待釋放後由本實例接管，返回 True
        若無既有實例：
          - 啟動監聽服務，返回 True
        """
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.settimeout(1.5)
        try:
            client_sock.connect((LOCALHOST, DEFAULT_PORT))
            # 連線成功，代表已有執行中的實例
            # 1. 詢問舊實例版本
            req = {"cmd": "check_version", "version": self.version}
            client_sock.sendall(json.dumps(req).encode("utf-8"))
            resp_data = client_sock.recv(1024)
            resp = json.loads(resp_data.decode("utf-8"))
            old_version = resp.get("version", "")

            # 2. 判斷是否為版本更新或強制替換
            if not force_replace and old_version == self.version:
                # 同版本純重複啟動：通知既有實例彈出視窗
                print(f"[INFO] 偵測到已有同版本 ({old_version}) MyShortCut 在運行，喚醒主視窗...")
                try:
                    show_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    show_sock.settimeout(1.0)
                    show_sock.connect((LOCALHOST, DEFAULT_PORT))
                    show_sock.sendall(json.dumps({"cmd": "show"}).encode("utf-8"))
                    show_sock.close()
                except Exception:
                    pass
                client_sock.close()
                return False  # 當前實例退出

            else:
                # 版本更新或強制替換：通知舊實例退出接管
                print(f"[INFO] 偵測到舊版本 ({old_version}) 正在運行，正在通知舊實例退出以進行新版 ({self.version}) 接管...")
                try:
                    exit_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    exit_sock.settimeout(1.0)
                    exit_sock.connect((LOCALHOST, DEFAULT_PORT))
                    exit_sock.sendall(json.dumps({"cmd": "exit"}).encode("utf-8"))
                    exit_sock.close()
                except Exception:
                    pass
                client_sock.close()
                time.sleep(1.0)  # 等待舊實例釋放 Socket 與清理托盤
        except Exception:
            # 連線失敗表示無既有實例運行
            try:
                client_sock.close()
            except Exception:
                pass

        # 啟動本實例的監聽伺服器
        return self._start_server()

    def _start_server(self) -> bool:
        try:
            self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_sock.bind((LOCALHOST, DEFAULT_PORT))
            self.server_sock.listen(5)
            self.is_running = True
            threading.Thread(target=self._listen_loop, daemon=True).start()
            return True
        except Exception as e:
            print(f"[WARN] 啟動單一實例監聽失敗: {e}")
            return True

    def _listen_loop(self):
        while self.is_running and self.server_sock:
            try:
                conn, _ = self.server_sock.accept()
                threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
            except Exception:
                break

    def _handle_client(self, conn: socket.socket):
        try:
            conn.settimeout(2.0)
            data = conn.recv(1024)
            if data:
                msg = json.loads(data.decode("utf-8"))
                cmd = msg.get("cmd")
                if cmd == "check_version":
                    resp = {"version": self.version}
                    conn.sendall(json.dumps(resp).encode("utf-8"))
                elif cmd == "show":
                    if self.on_show_request:
                        self.on_show_request()
                elif cmd == "exit":
                    if self.on_exit_request:
                        self.on_exit_request()
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def stop(self):
        self.is_running = False
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
