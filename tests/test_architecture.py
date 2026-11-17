import unittest
from fighter.input_buffer import InputBuffer
from fighter.skeleton import pose, BONES
from fighter.characters import CHARACTERS
from fighter.attacks import ATTACKS
from fighter.combat import Combat

class ArchitectureTests(unittest.TestCase):
    def test_relative_direction_and_motion(self):
        b=InputBuffer()
        for keys in ({'down':True},{'down':True,'right':True},{'right':True,'punch':True}):
            b.push(keys,1)
        self.assertTrue(b.motion(('2','3','6'),'punch'))
        self.assertFalse(b.motion(('2','3','6'),'kick'))
        other=InputBuffer()
        for keys in ({'down':True},{'down':True,'left':True},{'left':True,'punch':True}):
            other.push(keys,-1)
        self.assertTrue(other.motion(('2','3','6'),'punch'))
        other.consume()
        self.assertFalse(other.motion(('2','3','6'),'punch'))

    def test_crouch_attacks_never_stand_up_during_recovery(self):
        # While S is held the whole crouch attack must stay on the low base pose
        # instead of blending back to standing between attack frames.
        for action in ('crouch_punch', 'crouch_projectile', 'low_kick'):
            attack = ATTACKS[action]
            total = attack.startup + attack.active + attack.recovery
            for frame in range(total + 1):
                self.assertLess(pose(action, frame)['head'][1], 120, f"{action}@{frame}")

    def test_all_actions_have_complete_skeleton(self):
        for action in ('idle','run','jump','crouch','crouch_guard','guard','punch','crouch_punch','kick','low_kick',
                       'jump_punch','projectile','crouch_projectile','super','grab','hurt','downed'):
            joints=pose(action)
            self.assertEqual(set(BONES),set(joints))
        self.assertNotEqual(CHARACTERS['red_scarf']['decor'],
                            CHARACTERS['blue_headband']['decor'])

    def test_guard_reduces_damage(self):
        c=Combat()
        c.fighters[0]['x']=400; c.fighters[1]['x']=490
        for i in range(20): c.step(1/60,[{'punch':True},{'guard':True}])
        self.assertEqual(c.fighters[1]['hp'],1000-1)

    def test_projectile_needs_no_energy(self):
        c=Combat()
        c.fighters[0]['energy']=0
        c.step(1/60,[{'projectile':True},{}])
        self.assertEqual(c.fighters[0]['attack_kind'],'projectile')
        self.assertEqual(c.fighters[0]['energy'],0)

    def test_fixed_step_equivalence(self):
        a,b=Combat(),Combat()
        for _ in range(60): a.step(1/60,[{'right':True},{}])
        for _ in range(30): b.step(1/30,[{'right':True},{}])
        self.assertAlmostEqual(a.fighters[0]['x'],b.fighters[0]['x'])
        self.assertAlmostEqual(a.time_left,b.time_left)

class NegativeEdgeInputTests(unittest.TestCase):
    """Real MK negative edge: letting go of a button is itself an input."""

    def test_release_is_recorded(self):
        b = InputBuffer()
        b.push({'projectile': True}, 1)
        self.assertEqual(b.releases, frozenset())
        b.push({}, 1)
        self.assertEqual(b.releases, frozenset({'projectile'}))
        self.assertTrue(b.released_within('projectile', 0))

    def test_a_used_press_does_not_fire_again_on_release(self):
        b = InputBuffer()
        b.push({'punch': True}, 1)
        b.consume_buttons(('punch',))
        b.push({}, 1)
        self.assertEqual(b.releases, frozenset())

    def test_guard_and_jump_never_negative_edge(self):
        b = InputBuffer()
        b.push({'guard': True, 'jump': True}, 1)
        b.push({}, 1)
        self.assertEqual(b.releases, frozenset())

    def test_buffered_press_keeps_the_direction_of_that_frame(self):
        crouched = InputBuffer()
        crouched.push({'down': True, 'punch': True}, 1)
        self.assertEqual(crouched.buffered_buttons(8), frozenset({'punch'}))
        self.assertTrue(crouched.buffered_down(8))
        standing = InputBuffer()
        standing.push({'punch': True}, 1)
        self.assertFalse(standing.buffered_down(8))

class NegativeEdgeCombatTests(unittest.TestCase):
    def test_holding_a_special_then_releasing_it_fires(self):
        game = Combat()
        f = game.fighters[0]
        f['stun'] = 30 / 60      # 硬直足够长，按下沿会先超出入缓冲窗口
        game.step(1 / 60, [{'projectile': True}, {}])
        for _ in range(30):
            game.step(1 / 60, [{'projectile': True}, {}])
        self.assertEqual(f['attack_kind'], '')
        game.step(1 / 60, [{}, {}])      # 松开：这是唯一剩下的输入
        self.assertEqual(f['attack_kind'], 'projectile')

    def test_release_never_double_fires_a_normal_punch(self):
        game = Combat()
        game.fighters[0]['x'], game.fighters[1]['x'] = 400., 470.
        starts = 0
        for i in range(30):
            keys = {'punch': True} if i == 0 else {}
            for event in game.step(1 / 60, [keys, {}]):
                if event['event'] == 'punch':
                    starts += 1
        self.assertEqual(starts, 1)

if __name__=='__main__': unittest.main()
