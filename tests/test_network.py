"""Smoke test with two real TCP connections (run: python -m unittest discover -s tests)."""
import queue
import socket
import time
import unittest

from fighter.network import RoomServer, RoomClient


def wait_until(predicate, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate(): return True
        time.sleep(.025)
    return False


def open_room():
    """Start a server and connect host (slot 0) plus guest (slot 1)."""
    bind = socket.socket()
    bind.bind(("127.0.0.1", 0))
    port = bind.getsockname()[1]
    bind.close()
    server = RoomServer(port)
    c1, c2 = RoomClient(), RoomClient()
    server.start()
    c1.connect("127.0.0.1", port, "房主")
    wait_until(lambda: c1.slot == 0)
    c2.connect("127.0.0.1", port, "客机")
    wait_until(lambda: c2.slot == 1 and len(server.peers) == 2)
    return server, c1, c2


def collect_room_chars(clients, found):
    """Drain room broadcasts and remember the latest character per slot."""
    for client in clients:
        while True:
            try:
                message = client.events.get_nowait()
            except queue.Empty:
                break
            if message.get("type") == "room":
                for player in message.get("players", []):
                    found[player["slot"]] = player.get("char", "")
    return found


class TestLobby(unittest.TestCase):
    def test_two_clients_join_ready_and_play(self):
        # Obtain a free local port; a very small race remains between allocation and bind.
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        server = RoomServer(port)
        c1, c2 = RoomClient(), RoomClient()
        try:
            server.start()
            c1.connect("127.0.0.1", port, "房主")
            self.assertTrue(wait_until(lambda: c1.slot == 0))
            c2.connect("127.0.0.1", port, "客机")
            self.assertTrue(wait_until(lambda: c2.slot == 1))
            self.assertTrue(wait_until(lambda: len(server.peers) == 2))
            c1.send({"type": "ready", "value": True})
            c2.send({"type": "ready", "value": True})
            self.assertTrue(wait_until(lambda: len(server.peers) == 2 and all(p.ready for p in server.peers.values())))
            c1.send({"type": "start"})
            self.assertTrue(wait_until(lambda: server.phase == "game"))
            with server.lock:
                server.combat.countdown = 0.   # skip the pre-round countdown
            c1.send({"type": "input", "right": True})
            old_x = server.fighters[0]["x"]
            self.assertTrue(wait_until(lambda: server.fighters[0]["x"] > old_x))
        finally:
            c1.close(); c2.close(); server.stop()

    def test_each_client_picks_its_own_character(self):
        bind = socket.socket()
        bind.bind(("127.0.0.1", 0))
        port = bind.getsockname()[1]
        bind.close()
        server = RoomServer(port)
        c1, c2 = RoomClient(), RoomClient()
        try:
            server.start()
            c1.connect("127.0.0.1", port, "房主")
            c2.connect("127.0.0.1", port, "客机")
            self.assertTrue(wait_until(lambda: c1.slot == 0 and c2.slot == 1))
            self.assertTrue(wait_until(lambda: len(server.peers) == 2))
            # Each client only changes its own slot's character.
            c1.send({"type": "char", "char": "blue_headband"})
            c2.send({"type": "char", "char": "red_scarf"})
            self.assertTrue(wait_until(lambda: server.peers[0].char == "blue_headband"
                                       and server.peers[1].char == "red_scarf"))
            c1.send({"type": "ready", "value": True})
            c2.send({"type": "ready", "value": True})
            self.assertTrue(wait_until(lambda: all(p.ready for p in server.peers.values())))
            c1.send({"type": "start"})
            self.assertTrue(wait_until(lambda: server.phase == "game"))
            with server.lock:
                self.assertEqual(server.combat.fighters[0]["char_id"], "blue_headband")
                self.assertEqual(server.combat.fighters[1]["char_id"], "red_scarf")
                self.assertEqual(server.combat.fighters[0]["projectile_config"]["damage"], 11)
                self.assertEqual(server.combat.fighters[1]["projectile_config"]["damage"], 14)
        finally:
            c1.close(); c2.close(); server.stop()

    def test_room_defaults_and_ownership(self):
        server, c1, c2 = open_room()
        try:
            self.assertEqual(server.peers[0].char, "red_scarf")
            self.assertEqual(server.peers[1].char, "blue_headband")
            c1.send({"type": "char", "char": "blue_headband"})
            self.assertTrue(wait_until(lambda: server.peers[0].char == "blue_headband"))
            # A guest may only change its own slot, never the host's pick.
            c2.send({"type": "char", "char": "red_scarf"})
            self.assertTrue(wait_until(lambda: server.peers[1].char == "red_scarf"))
            self.assertEqual(server.peers[0].char, "blue_headband")
        finally:
            c1.close(); c2.close(); server.stop()

    def test_room_snapshot_publishes_characters(self):
        server, c1, c2 = open_room()
        found = {}
        try:
            self.assertTrue(wait_until(lambda: collect_room_chars((c1, c2), found)
                                       == {0: "red_scarf", 1: "blue_headband"}))
            c2.send({"type": "char", "char": "red_scarf"})
            self.assertTrue(wait_until(lambda: collect_room_chars((c1, c2), found)
                                       .get(1) == "red_scarf"))
            self.assertEqual(found[0], "red_scarf")
        finally:
            c1.close(); c2.close(); server.stop()

    def test_unknown_character_is_ignored(self):
        server, c1, c2 = open_room()
        try:
            c1.send({"type": "char", "char": "not_a_character"})
            # A following ready proves the invalid message was processed first.
            c1.send({"type": "ready", "value": True})
            self.assertTrue(wait_until(lambda: server.peers[0].ready))
            self.assertEqual(server.peers[0].char, "red_scarf")
        finally:
            c1.close(); c2.close(); server.stop()

    def test_character_change_after_ready_applies_on_start(self):
        server, c1, c2 = open_room()
        try:
            c1.send({"type": "char", "char": "blue_headband"})
            c1.send({"type": "ready", "value": True})
            c2.send({"type": "char", "char": "red_scarf"})
            c2.send({"type": "ready", "value": True})
            self.assertTrue(wait_until(lambda: all(p.ready for p in server.peers.values())))
            self.assertEqual(server.peers[0].char, "blue_headband")
            self.assertEqual(server.peers[1].char, "red_scarf")
            c1.send({"type": "start"})
            self.assertTrue(wait_until(lambda: server.phase == "game"))
            with server.lock:
                self.assertEqual(server.combat.fighters[0]["char_id"], "blue_headband")
                self.assertEqual(server.combat.fighters[1]["char_id"], "red_scarf")
        finally:
            c1.close(); c2.close(); server.stop()


if __name__ == "__main__": unittest.main()


class TestCombatOverNetwork(unittest.TestCase):
    def test_server_sends_combat_snapshots_and_round_win(self):
        bind = socket.socket()
        bind.bind(("127.0.0.1", 0))
        port = bind.getsockname()[1]
        bind.close()
        server = RoomServer(port)
        a, b = RoomClient(), RoomClient()
        try:
            server.start()
            a.connect("127.0.0.1", port, "A")
            b.connect("127.0.0.1", port, "B")
            self.assertTrue(wait_until(lambda: a.slot == 0 and b.slot == 1))
            a.send({"type": "ready", "value": True})
            b.send({"type": "ready", "value": True})
            self.assertTrue(wait_until(lambda: len(server.peers) == 2 and all(x.ready for x in server.peers.values())))
            a.send({"type": "start"})
            self.assertTrue(wait_until(lambda: server.phase == "game"))
            with server.lock:
                server.combat.countdown = 0.   # skip the pre-round countdown
                server.combat.fighters[0]["x"] = 400
                server.combat.fighters[1]["x"] = 480
            a.send({"type": "input", "punch": True})
            self.assertTrue(wait_until(lambda: server.combat.fighters[1]["hp"] == 800 - 9))
            self.assertTrue(wait_until(lambda: any(ev.get("type") == "combat" and ev.get("event") == "hit" for ev in list(b.events.queue))))
            with server.lock:
                server.combat.finish_round(0)
                self.assertEqual(server.combat.scores, [1, 0])
                self.assertEqual(server.combat.phase, "round_end")
            self.assertTrue(wait_until(lambda: any(ev.get("type") == "state" and ev.get("scores") == [1, 0] for ev in list(a.events.queue))))
        finally:
            a.close(); b.close(); server.stop()
