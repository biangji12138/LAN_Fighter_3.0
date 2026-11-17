"""LAN room protocol: newline-delimited JSON over TCP.

The host runs a RoomServer locally and also joins it as a client. The server
owns room state and the tiny demonstration arena simulation.
"""
from __future__ import annotations

import json
import queue
import socket
import threading
import time
from dataclasses import dataclass, field
from .combat import Combat, ROUND_COUNTDOWN
from .characters import CHARACTERS

PROTOCOL_VERSION = 4
MAX_PACKET = 4096
MAX_BUFFER = 8192


def send_json(sock: socket.socket, payload: dict, lock: threading.Lock | None = None) -> None:
    data = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(data) > MAX_PACKET:
        raise ValueError("packet too large")
    if lock is None:
        sock.sendall(data)
    else:
        with lock:
            sock.sendall(data)


@dataclass
class Peer:
    conn: socket.socket
    slot: int
    nick: str
    ready: bool = False
    char: str = "red_scarf"
    send_lock: threading.Lock = field(default_factory=threading.Lock)


class RoomServer:
    def __init__(self, port: int, map_id: str = "dojo"):
        self.port = port
        # 房主选择的地图随快照下发给客户端，双方渲染同一张舞台。
        self.map_id = map_id
        self.sock: socket.socket | None = None
        self.alive = threading.Event()
        self.lock = threading.RLock()
        self.peers: dict[int, Peer] = {}
        self.phase = "lobby"
        self.combat = Combat(map_id)
        self.fighters = self.combat.fighters
        self.inputs = {0: {}, 1: {}}
        self.last_state = 0.0
        self.result_since = 0.0
        self.threads: list[threading.Thread] = []

    def start(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", self.port))
        self.sock.listen(4)
        self.sock.settimeout(0.3)
        self.alive.set()
        for fn in (self._accept_loop, self._tick_loop):
            t = threading.Thread(target=fn, daemon=True)
            t.start()
            self.threads.append(t)

    def stop(self) -> None:
        self.alive.clear()
        if self.sock:
            try: self.sock.close()
            except OSError: pass
        with self.lock:
            for p in list(self.peers.values()):
                try: p.conn.shutdown(socket.SHUT_RDWR)
                except OSError: pass
                try: p.conn.close()
                except OSError: pass
            self.peers.clear()

    def _accept_loop(self):
        # Snapshot once: self.sock may be replaced or cleared by stop() while
        # this thread is still running.
        sock = self.sock
        if sock is None:
            return
        while self.alive.is_set():
            try:
                conn, _ = sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            conn.settimeout(0.5)
            threading.Thread(target=self._peer_loop, args=(conn,), daemon=True).start()

    def _peer_loop(self, conn: socket.socket):
        peer = None
        buffer = b""
        try:
            # Clients must introduce themselves first.
            deadline = time.monotonic() + 7
            while self.alive.is_set() and time.monotonic() < deadline and b"\n" not in buffer:
                try: chunk = conn.recv(1024)
                except socket.timeout: continue
                if not chunk: return
                buffer += chunk
                if len(buffer) > MAX_BUFFER: return
            if b"\n" not in buffer: return
            first, buffer = buffer.split(b"\n", 1)
            hello = json.loads(first)
            if not isinstance(hello, dict) or hello.get("type") != "hello": return
            if hello.get("protocol") != PROTOCOL_VERSION:
                send_json(conn, {"type": "error", "message": "游戏版本不一致，请双方都使用 LAN Fighter 3.0"})
                return
            nick = str(hello.get("nick", "玩家"))[:12].strip() or "玩家"
            with self.lock:
                if self.phase != "lobby" or len(self.peers) == 2:
                    send_json(conn, {"type": "error", "message": "房间已满或对战已经开始"})
                    return
                slot = next(i for i in (0, 1) if i not in self.peers)
                peer = Peer(conn, slot, nick,
                            char="red_scarf" if slot == 0 else "blue_headband")
                self.peers[slot] = peer
                send_json(conn, {"type": "welcome", "slot": slot, "port": self.port}, peer.send_lock)
                self._snapshot()
            while self.alive.is_set():
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if not line: continue
                    try: msg = json.loads(line)
                    except (ValueError, UnicodeDecodeError): continue
                    if isinstance(msg, dict): self._handle(peer, msg)
                try: chunk = conn.recv(2048)
                except socket.timeout: continue
                if not chunk: break
                buffer += chunk
                if len(buffer) > MAX_BUFFER: break
        except (OSError, UnicodeDecodeError, ValueError):
            pass
        finally:
            if peer:
                with self.lock:
                    if self.peers.get(peer.slot) is peer:
                        del self.peers[peer.slot]
                        self.inputs[peer.slot] = {}
                        if self.phase != "lobby": self.phase = "lobby"
                        for p in self.peers.values(): p.ready = False
                        self._snapshot()
            try: conn.close()
            except OSError: pass

    def _broadcast(self, data: dict):
        # Called with self.lock held; failed writes are discarded by the read loop.
        for p in list(self.peers.values()):
            try: send_json(p.conn, data, p.send_lock)
            except OSError: pass

    def _snapshot(self):
        self._broadcast({"type": "room", "phase": self.phase, "players": [
            {"slot": p.slot, "nick": p.nick, "ready": p.ready, "char": p.char}
            for p in sorted(self.peers.values(), key=lambda item: item.slot)
        ]})

    def _handle(self, peer: Peer, msg: dict):
        kind = msg.get("type")
        with self.lock:
            if self.peers.get(peer.slot) is not peer: return
            if kind == "ready" and self.phase == "lobby":
                peer.ready = bool(msg.get("value", False))
                self._snapshot()
            elif kind == "char" and self.phase == "lobby" and msg.get("char") in CHARACTERS:
                # Each client may only pick the character for its own slot.
                peer.char = msg["char"]
                self._snapshot()
            elif kind == "start" and self.phase == "lobby" and peer.slot == 0:
                if len(self.peers) == 2 and all(p.ready for p in self.peers.values()):
                    self.phase = "game"
                    self.combat = Combat(self.map_id)
                    self.combat.countdown = ROUND_COUNTDOWN
                    for i, chosen in enumerate((self.peers[0], self.peers[1])):
                        self.combat.set_loadout(i, CHARACTERS[chosen.char])
                    self.fighters = self.combat.fighters
                    self.inputs = {0: {}, 1: {}}
                    self._snapshot()
            elif kind == "input" and self.phase == "game":
                self.inputs[peer.slot] = {k: bool(msg.get(k)) for k in ("left", "right", "down", "guard", "jump", "punch", "kick", "projectile", "grab")}

    def _tick_loop(self):
        previous = time.monotonic()
        while self.alive.is_set():
            now = time.monotonic()
            dt = min(now - previous, 0.05)
            previous = now
            with self.lock:
                if self.phase == "game" and len(self.peers) == 2:
                    events = self.combat.step(dt, [self.inputs[0], self.inputs[1]])
                    self.fighters = self.combat.fighters
                    for event in events:
                        self._broadcast(event)
                    if now - self.last_state >= 1 / 25 or events:
                        self.last_state = now
                        self._broadcast(self.combat.snapshot())
                    if self.combat.phase == "match_end" and self.combat.pause_left <= 0:
                        self.phase = "lobby"
                        for peer in self.peers.values():
                            peer.ready = False
                        self.inputs = {0: {}, 1: {}}
                        self._snapshot()
            time.sleep(1 / 60)


class RoomClient:
    def __init__(self):
        self.sock: socket.socket | None = None
        self.alive = threading.Event()
        self.events: queue.Queue[dict] = queue.Queue()
        self.send_lock = threading.Lock()
        self.slot: int | None = None

    def connect(self, ip: str, port: int, nick: str) -> None:
        sock = socket.create_connection((ip, port), timeout=3)
        sock.settimeout(0.5)
        self.sock = sock
        self.alive.set()
        send_json(sock, {"type": "hello", "nick": nick, "protocol": PROTOCOL_VERSION}, self.send_lock)
        threading.Thread(target=self._read_loop, daemon=True).start()

    def send(self, message: dict) -> None:
        if not self.sock or not self.alive.is_set(): return
        try: send_json(self.sock, message, self.send_lock)
        except OSError: self.close()

    def _read_loop(self):
        buf = b""
        # Hold a local reference: close() sets self.sock to None, and reading
        # self.sock inside the loop would race with it (AttributeError on None).
        sock = self.sock
        try:
            while self.alive.is_set() and sock is not None:
                try: chunk = sock.recv(4096)
                except socket.timeout: continue
                if not chunk: break
                buf += chunk
                if len(buf) > MAX_BUFFER: break
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try: msg = json.loads(line)
                    except (ValueError, UnicodeDecodeError): continue
                    if not isinstance(msg, dict): continue
                    if msg.get("type") == "welcome": self.slot = msg.get("slot")
                    self.events.put(msg)
        except OSError:
            pass
        finally:
            if self.alive.is_set(): self.events.put({"type": "disconnected"})
            self.alive.clear()

    def close(self):
        self.alive.clear()
        if self.sock:
            try: self.sock.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            try: self.sock.close()
            except OSError: pass
            self.sock = None
