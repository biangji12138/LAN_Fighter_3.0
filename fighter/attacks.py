"""Data-driven attacks. All durations use integer simulation frames (60 Hz).
Normal attacks keep their original damage values; supers may be overridden per character.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Attack:
    name: str
    damage: int
    startup: int
    active: int
    recovery: int
    reach: float
    hit_height: float
    push: float
    # Hit-stun frames the victim stays held after a clean hit.
    stun: int
    energy: int = 0
    launch: float = 0.0
    # Multi-hit moves deal ``damage // hits`` per hit on a fixed frame cadence.
    hits: int = 1
    hit_interval: int = 4
    # Per-move block-stun, so block advantage is tuned like MK frame data.
    block_stun: int = 0
    # Frames after a connect (hit or block) where the rest of the recovery
    # may be cancelled into another attack. 0 = the move always commits.
    cancel: int = 0

    @property
    def total(self):
        return self.startup + self.active + self.recovery

    @property
    def hit_advantage(self):
        """Attacker frame advantage when the first active frame connects.

        The simulation holds the attacker for ``active + recovery`` ticks after
        the contact frame, so the advantage is hit-stun minus that span.
        """
        return self.stun - self.active - self.recovery

    @property
    def block_advantage(self):
        """Attacker frame advantage when the first active frame is blocked."""
        return self.block_stun - self.active - self.recovery

ATTACKS = {
    'punch':       Attack('punch',        9,  4,  7,  8, 105,  90, 10, stun=23, block_stun=14, cancel=7),
    'kick':        Attack('kick',        15,  8,  9, 13, 139,  78, 17, stun=28, block_stun=18, cancel=7),
    'low_kick':    Attack('low_kick',    12,  9,  9, 14, 120,  45, 14, stun=26, block_stun=15, cancel=6),
    'jump_punch':  Attack('jump_punch',  11,  5,  7, 12, 115, 100, 12, stun=21, block_stun=13, cancel=5),
    'crouch_punch': Attack('crouch_punch', 8,  5,  6, 10, 100,  55, 10, stun=20, block_stun=12,
                           cancel=5),
    'grab':        Attack('grab',        12,  6,  4, 16,  78, 105,  0, stun=72),
    'projectile':  Attack('projectile',   0, 10,  1, 13,   0,   0,  0, stun=0),
    'crouch_projectile': Attack('crouch_projectile', 0, 10, 1, 15, 0, 0, 0, stun=0),
    'super':       Attack('super',      340, 14,  8, 26, 170, 110, 34, stun=34, block_stun=22,
                          energy=100, launch=320),
    # Buff stance: no hitbox, it only arms the next few attacks (see characters.py).
    'flame_buff':  Attack('flame_buff',   0, 12,  6, 16,   0,   0,  0, stun=0),
    # Delayed spell: no hitbox either, it queues the falling bolt (yellow cape).
    'lightning_strike': Attack('lightning_strike', 0, 8, 4, 12, 0, 0, 0, stun=0),
}