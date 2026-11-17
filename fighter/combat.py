"""LAN Fighter 3 core: 60 Hz authoritative combat. No Pygame dependency."""
import random

from .input_buffer import InputBuffer
from .attacks import ATTACKS, Attack

ARENA_LEFT, ARENA_RIGHT = 46., 974.
MOVE_SPEED, JUMP_SPEED, GRAVITY = 260., 570., 1450.
DASH_SPEED, DASH_FRAMES, BACKDASH_FRAMES = 560., 10, 8
# 雷霆嘎巴（黄披风）在大招前摇开头先冲刺一次：12 帧走完 180 像素。
DASH_SUPER_FRAMES, DASH_SUPER_STOP = 12, 60
ROUND_SECONDS, ROUND_PAUSE, MATCH_PAUSE = 65., 2.4, 7.
ROUND_COUNTDOWN = 3.
DEFAULT_HP = 1000
MAX_ENERGY = 150
# Energy only comes from dealing damage; a super hit refunds nothing. The
# fighter that takes the damage earns half of the attacker's hit payout, so
# losing a trade still builds toward a comeback super.
HIT_ENERGY_GAIN = 10
PROJECTILE_ENERGY_GAIN = 8
DAMAGE_ENERGY_GAIN = HIT_ENERGY_GAIN // 2
PROJECTILE_DAMAGE_ENERGY_GAIN = PROJECTILE_ENERGY_GAIN // 2
TICK = 1 / 60
# Hit-stun builds a stagger gauge. Enough stagger in a short window floors the
# victim; the gauge bleeds off quickly once the combo ends.
KNOCKDOWN_SECONDS = 2.
# Wake-up protection: frames of untouchability after rising from a knockdown,
# so being floored resets the exchange instead of handing out a free reset.
GETUP_INVULN_FRAMES = 18
# 110 时拳4脚4就倒，连招第5段几乎出不来。提到 165 后纯拳约7次、
# 纯脚约6次、混合连招约5~6段才倒地，与 COMBO_SCALING 的6段衰减对齐。
STAGGER_LIMIT = 165.
STAGGER_DECAY = 40.
STAGGER_HIT_CAP = 30.
# The gauge is frozen while hits keep landing and only starts bleeding after
# this many frames without a hit, so a real combo can still floor the victim.
STAGGER_HOLD_FRAMES = 25
ACTIONS = {'idle','run','jump','crouch','crouch_guard','guard','punch','crouch_punch','kick','low_kick','jump_punch','projectile','crouch_projectile','laser','super','grab','hurt','downed','flame_buff','lightning_strike','ice_shadow','tackle','shield_buff'}

# Hit-box geometry in pose units: heights measured up from the fighter's feet.
# Head centre sits at 142 with a 24 px radius, so the head top is ~166.
BODY_BOTTOM, BODY_TOP, CROUCH_TOP, NECK_HEIGHT = 4., 166., 118., 112.
BODY_HALF_WIDTH = 34.
CROUCH_PROJ_HEIGHT = 46.

# Grab super (red scarf): the opponent is pinned this far in front while the
# fists land. Four punches at full health, one more for every 15% health the
# caster has lost, capped at ten. The victim is then thrown half an arena away.
GRAB_PULL_DISTANCE = 54.
PUMMEL_DAMAGE = 40
PUMMEL_BASE_HITS = 4
PUMMEL_MAX_HITS = 10
PUMMEL_HP_STEP = .15
HALF_MAP = (ARENA_RIGHT - ARENA_LEFT) / 2
# Grab super animation cadence. The damage, punch count, throw distance and the
# 2 s knockdown are all unchanged -- these just stretch the move (Mortal Kombat
# style) so the pull-in, every punch and the final launch are readable.
GRAB_PULL_FRAMES = 22
GRAB_THROW_FRAMES = 26

# Basic attacks that can be chained into one another with single button presses.
CHAINABLE = frozenset({'punch', 'crouch_punch', 'kick', 'low_kick', 'jump_punch', 'grab'})

# Combo damage scaling: each extra hit in the same string is worth less.
COMBO_SCALING = (1., .85, .7, .55, .4, .3)
# Hits spaced further apart than this start a fresh combo at full damage.
COMBO_WINDOW = 65
# Extra pushback per combo hit, so long strings create space instead of looping.
PUSH_GROWTH = .25
# Guard pushback: a blocked melee hit shoves the attacker back this far, so a
# guarding opponent buys space and melee spam cannot stay glued in range.
GUARD_PUSHBACK = 8.

# A move that connects (hit or block) may skip the rest of its recovery into
# another attack, but only this many times before the combo must breathe.
MAX_CANCEL_CHAIN = 3

# 输入缓冲窗口（帧）：攻击键按下后的这几帧内，只要角色恢复可行动就会接上。
# 真人快打手感的关键——按键不必卡在“刚好能出招”的那一帧。
ATTACK_BUFFER_FRAMES = 8

# 蹲招宽容帧：同帧松开 S 的同时按攻击键，仍按蹲招判定（方向与按键几乎同时变化）。
CROUCH_GRACE = 4

# 收招期间的预输入队列：最多排 3 招，按输入顺序依次接上（真人快打式连打）。
# 超过这个帧数还没轮到就作废，避免很早以前的按键突然自己打出来。
QUEUE_LIMIT = 3
QUEUE_TTL = 45

# 打击停顿（帧）：命中瞬间双方一起定格，让每一击有“咬合感”。
# 用固定帧数而不是秒，本地与联机表现一致；格挡只有轻微停顿。
HITSTOP = {'punch': 2, 'crouch_punch': 2, 'jump_punch': 2,
           'kick': 3, 'low_kick': 3, 'grab': 4,
           'super': 6, 'tackle': 5, 'ice_shadow': 5, 'vapor_freeze': 4,
           'super_pummel': 3, 'projectile': 2, 'carrier': 2,
           'knife': 2, 'road_roller': 6}
HITSTOP_BLOCK = 2
HITSTOP_DEFAULT = 3

# 空中挥空取消（真人快打特色）：跳跃普通技即使没打中，进入收招时也会开一个
# 短窗口，可以直接取消成空中特殊技（当前招式表里是空中发波）。
AIR_WHIFF_CANCEL_FRAMES = 4
AIR_CANCEL_KINDS = frozenset({'projectile'})

# Attacks thrown from a crouch (or aimed low). A standing guard cannot stop
# them; only a crouching guard can. Grabs ignore every guard stance.
CROUCH_ATTACKS = frozenset({'crouch_punch', 'low_kick', 'crouch_projectile'})

# 冰千年杀（冷静的普通人的专属连招）：遁入地下消失，1 秒后瞬移至敌人脚下冲出。
# 时间轴：钻地（前摇）→ 潜行 1 秒（隐身无敌）→ 冲出（命中）→ 落地复位（后摇）。
SHADOW_BURROW = 12
SHADOW_HIDE = 60
SHADOW_EMERGE = 14
SHADOW_RECOVER = 16
SHADOW_HEIGHT = 250.   # 冲出高度，约 1.5 人身高
SHADOW_TOTAL = SHADOW_BURROW + SHADOW_HIDE + SHADOW_EMERGE + SHADOW_RECOVER

# 借过一下（上班的普通人的大招）：霸体冲锋 → 勾脖摔地。
# 阶段：前摇 → 冲锋（霸体）→ 撞击 40 → 摔地 110 → 立即起身收招。
TACKLE_WINDUP = 12
TACKLE_RUSH_SPEED = 760.
TACKLE_CONTACT_DAMAGE = 40
TACKLE_SLAM_DAMAGE = 110
TACKLE_SLAM_DELAY = 8       # 撞击后多少帧结算摔地伤害
TACKLE_RECOVER = 18         # 自己起身收招帧（敌人倒满 2 秒）
TACKLE_KNOCKDOWN = 2.
# 勾住后的纯表现节奏：双方因惯性沿冲锋方向前带的像素与抛物线腾空帧数。
TACKLE_ARC = 20
TACKLE_CARRY = 66.
# 晚高峰警告护盾数值。
SHIELD_MAX = 200
SHIELD_DURATION = 7.

# 熔岩地貌场地机关：每隔 5~15 秒在随机“两人宽”的地面区域喷出一人高的火柱。
# 先有短暂的地面预警圈，喷发瞬间对范围内站立的角色造成 20 伤害。
LAVA_MAP = 'lava'
LAVA_PILLAR_MIN_DELAY = 5.
LAVA_PILLAR_MAX_DELAY = 15.
LAVA_PILLAR_WARNING = .9
LAVA_PILLAR_DURATION = .55
LAVA_PILLAR_DAMAGE = 20
LAVA_PILLAR_HEIGHT = 170.
LAVA_PILLAR_RADIUS = 70.
LAVA_PILLAR_STUN = 10

# 冰雪溶洞场地机关：高空随机掉落一人大小的冰棱，没有预警、下落极快，
# 砸中的角色被冰冻 1 秒（期间无法行动）。
ICE_MAP = 'ice'
ICE_SHARD_MIN_DELAY = 2.4
ICE_SHARD_MAX_DELAY = 5.
ICE_SHARD_SPEED = 1500.
ICE_SHARD_RADIUS = 44.
ICE_SHARD_START = 620.
ICE_FREEZE_TIME = 1.

# 石面鬼之眼（迪奥）：按住技能键从双眼射出一道血色激光，引导期间无法移动。
# 命中立刻结算一次伤害，之后每 0.5 秒再结算一次；不累积硬直，打不倒人。
LASER_STARTUP = 12       # 起手（双眼亮起），此时还没有判定
LASER_RECOVER = 12       # 松手后的收招
LASER_INTERVAL = .5      # 同一目标的两次伤害间隔
LASER_EYE_HEIGHT = 139.  # 眼睛离地高度（略低于头顶）
# 光柱有厚度：竖直方向上下各占 LASER_HALF_THICK。蹲下时头顶只有 118，高光柱
# 若不向下加厚，蹲着就能从光柱底下钻过去，所以判定必须覆盖蹲姿。
LASER_HALF_THICK = 26.
LASER_CROUCH_EYE_HEIGHT = 112.  # 蹲着放激光时眼睛的高度
LASER_MIN_DAMAGE = 12
# 气化冷冻法（迪奥）：近身冷气触击，命中把对手原地冻结。冻结期间对手无法
# 移动 / 出招 / 跳跃；吃到第一记干净命中时，冻脆的身体额外承受「碎裂」伤害
# 并提前破冰——这 30 点是用剩余冻结时间换来的，不是白送的。
VAPOR_FREEZE = 1.5
VAPOR_SHATTER_BONUS = 30
# 命中返还一半能耗：满能量放完这一招剩 85 点，还要再攒回 100 才能搓
# S S L L；打空则实打实亏 30 点。冻结的 1.5 秒够走位，但不够白拿一次时停。
VAPOR_REFUND = 15
# 砸瓦鲁多（迪奥）：前摇结束后全场时间停止，除施法者外所有角色、投射物、
# 落雷、场地机关与回合计时器一并定格。施法者移速翻倍，且只能用 J 瞬发出拳。
TIME_STOP_DEFAULT = 7.
TIME_STOP_SPEED_MULT = 2.
TIME_STOP_PUNCH_HEIGHT = 90.
# 时停瞬发拳的纯视觉出拳帧数：把一记普通拳的完整动作压缩到这里，既看得到
# 出拳，又完全不占用攻击状态机（不影响"手速就是输出上限"）。
TIME_STOP_PUNCH_ANIM = 6
# 时停飞刀（战前掏刀，时间恢复时齐射）：时停中每 0.22 秒掏出一把，最多 8 把，
# 全部悬停在空中不动；时间恢复的瞬间一起飞出。四档高度循环分布，蹲姿判定的
# 头顶只有 118，所以蹲下会吃到 46 / 78 / 112 三把，躲不干净。
KNIFE_INTERVAL = .22
KNIFE_MAX = 8
KNIFE_DAMAGE = 6
KNIFE_SPEED = 980.
KNIFE_LIFETIME = 1.1
KNIFE_HEIGHTS = (46., 78., 112., 148.)
KNIFE_OFFSET = 36.
# 压路机（ROAD ROLLER DA!!）：时停中命中 5 拳后按 K 收尾。砸下即恢复时间，
# 自身有 26 帧收招——原著里砸完就被反击，所以这是一次有代价的终结。
ROLLER_REQUIRED_HITS = 5
ROLLER_DAMAGE = 65
ROLLER_KNOCKDOWN = 1.8
ROLLER_RECOVER = 26
# 引导招式只有起手 / 收招两段，没有单独的命中帧；它不进 ATTACKS（那张表要求
# 每招都有前摇与后摇的独立帧段），由 _tick_laser 自行驱动。
LASER_SPEC = Attack('laser', LASER_STARTUP, 0, LASER_RECOVER, 0, 0, 0, 0, stun=0)

def _smoothstep(t):
    t = max(0., min(1., t))
    return t * t * (3. - 2. * t)

def shadow_phase(f):
    """冰千年杀当前所处的阶段（'burrow' / 'hide' / 'emerge' / 'recover'）。"""
    af = f.get('action_frame', 0)
    if af < SHADOW_BURROW:
        return 'burrow'
    if af < SHADOW_BURROW + SHADOW_HIDE:
        return 'hide'
    if af < SHADOW_BURROW + SHADOW_HIDE + SHADOW_EMERGE:
        return 'emerge'
    return 'recover'

def guard_blocks(action, attack_kind):
    """Which guard stance stops which attack.

    Standing guard loses to every crouching/low attack, crouching guard stops
    everything except a grab (grabs are unblockable by design).
    """
    if attack_kind == 'grab':
        return False
    if action == 'crouch_guard':
        return True
    if action == 'guard':
        return attack_kind not in CROUCH_ATTACKS
    return False

def crouching(fighter):
    """True while the fighter is in a crouching posture (guarding or not)."""
    return fighter.get('action') in ('crouch', 'crouch_guard')

def body_span(fighter):
    """Vertical extent (bottom, top) of a fighter's hit box above the ground."""
    base = fighter.get('y', 0.)
    top = CROUCH_TOP if crouching(fighter) else BODY_TOP
    return base + BODY_BOTTOM, base + top

def fresh_fighter(x, face, projectile_config=None, hp_max=DEFAULT_HP):
    return {'x': float(x), 'y': 0., 'vy': 0., 'hp': hp_max, 'hp_max': hp_max,
            'face': face, 'cooldown': 0.,
            'action': 'idle', 'action_frame': 0, 'action_time': 0., 'attack_kind': '',
            'attack_hit': False, 'stun': 0., 'flash': 0., 'walk': 0., 'energy': 0, 'combo': 0,
            'stagger': 0., 'stagger_frame': -9999, 'last_hit_frame': -9999, 'grounded': True, 'dash_time': 0., 'dash_dir': 0,
            'air_jump': False,
            'move_speed': MOVE_SPEED, 'dash_speed': DASH_SPEED,
            'projectile_config': projectile_config or {}, 'proj_spawned': False,
            'char_id': '', 'super_spec': None, 'combo_spec': None,
            'super_radius': 0., 'super_cmd': None, 'super_motion': None, 'knocked': False,
            'invuln': 0., 'frozen': 0., 'frozen_kind': '',
            'combo_motion': None,
            'super_kind': '', 'super_distance': 0., 'super_throw': 0., 'super_area_mode': 'radius',
            'hit_count': 0, 'rush_done': False, 'pummel_hits': 0,
            'pummel_count': 0, 'pummel_frame': 0,
            'pummel_state': '', 'pull_left': 0, 'pull_from': 0., 'pull_to': 0.,
            'throw_left': 0, 'throw_from': 0., 'throw_to': 0.,
            'buff_spec': None, 'buff_charges': 0, 'super_bolt': None,
            'combo_attack': None, 'queued_attack': '', 'cancel_left': 0,
            'queued_more': [], 'queued_frame': 0, 'air_cancel_left': 0,
            'cancel_chain': 0,
            # 上班的普通人：护盾与霸体冲锋状态。
            'shield': 0, 'shield_max': 0, 'shield_timer': 0.,
            'tackle_state': '', 'tackle_contact_frame': 0,
            'tackle_slammed': False, 'super_armor': False,
            'tackle_visual': None, 'downed_style': 'curl',
            # 石面鬼之眼：激光引导的伤害间隔计时，以及是否蹲着放。
            'laser_cd': 0., 'laser_low': False,
            # 砸瓦鲁多：时停时长与瞬发拳伤害（由角色配置写入）。
            'super_time_stop': 0., 'super_punch_damage': 0,
            # 时停瞬发拳的纯视觉动画剩余帧数，以及这一拳用哪只手
            # （0 = 前手，1 = 后手；连按时交替，仿原著连打）。
            'time_punch_anim': 0, 'time_punch_side': 1,
            # 时停中的连段进度：已命中的瞬发拳数（压路机的解锁门槛）、
            # 飞刀冷却与已掏出的把数。
            'time_punch_count': 0, 'knife_cd': 0., 'knife_count': 0,
            # 大招前摇进行中标记：被打断时通知表现层掐断喊招音效。
            'time_stop_casting': False}

# Loadout fields survive between rounds (energy is handled separately).
LOADOUT_FIELDS = ('hp_max', 'char_id', 'projectile_config', 'super_spec', 'combo_spec',
                  'move_speed', 'dash_speed', 'super_radius', 'super_cmd', 'super_motion',
                  'combo_motion',
                  'super_kind', 'super_distance', 'super_throw', 'super_area_mode',
                  'buff_spec', 'super_bolt',
                  'super_time_stop', 'super_punch_damage',
                  'combo_attack')

def attack_spec(fighter, kind):
    """Per-fighter attack data, so each character can own a unique super."""
    if kind == 'laser':
        return LASER_SPEC
    if kind == 'super' and fighter.get('super_spec'):
        return fighter['super_spec']
    if kind == 'tackle' and fighter.get('super_spec'):
        return fighter['super_spec']
    if kind in ('ice_shadow', 'shield_buff', 'vapor_freeze') and fighter.get('combo_attack'):
        return fighter['combo_attack']
    return ATTACKS[kind]

# Combo fatigue: once the cancel chain is maxed, further ordinary attacks are
# tired swings -- their recovery is longer, leaving a punishable window.
FATIGUE_RECOVERY = 6
# The chain only builds through cancelable chainable normals; grabs and
# supers never fatigue.
FATIGUE_ATTACKS = CHAINABLE - {'grab'}

def attack_total(fighter, kind):
    """Effective total frames of ``kind`` for this fighter's fatigue state."""
    spec = attack_spec(fighter, kind)
    if kind in FATIGUE_ATTACKS and fighter.get('cancel_chain', 0) >= MAX_CANCEL_CHAIN:
        return spec.total + FATIGUE_RECOVERY
    return spec.total

def gain_energy(fighter, amount):
    fighter['energy'] = min(MAX_ENERGY, fighter['energy'] + amount)

def apply_damage(victim, damage):
    """统一下沉的受击入口：先扣护盾，溢出才扣血。

    返回实际扣除的血量（护盾吸收部分不计入，用于能量与展示的真实伤害）。
    所有伤害结算（近战 / 弹道 / 落雷 / 大招）都必须走这里，避免口径漂移。
    """
    if victim.get('shield', 0) > 0:
        absorbed = min(damage, victim['shield'])
        victim['shield'] -= absorbed
        damage -= absorbed
    victim['hp'] = max(0, victim['hp'] - damage)
    return damage

def has_armor(fighter):
    """霸体冲锋期间：仍受伤害，但不进硬直、不被打断、不吃击退。"""
    return bool(fighter.get('super_armor'))

class Combat:
    def __init__(self, map_id='dojo'):
        self.map_id = map_id
        self.scores = [0, 0]
        self.round = 1
        self.phase = 'game'
        self.time_left = ROUND_SECONDS
        self.countdown = 0.
        self.pause_left = 0.
        self.winner = None
        self.round_winner = None
        self.event_seq = 0
        self.frame = 0
        self.hitstop = 0
        self.accumulator = 0.
        self.inputs = [{}, {}]
        self.fighters = [fresh_fighter(210, 1), fresh_fighter(810, -1)]
        self.buffers = [InputBuffer(), InputBuffer()]
        self.projectiles = []
        # Delayed bolts of the yellow cape (warning ring, then the fall).
        self.strikes = []
        # 熔岩地貌的火柱与下一次喷发倒计时。
        self.fire_pillars = []
        self.pillar_timer = random.uniform(LAVA_PILLAR_MIN_DELAY, LAVA_PILLAR_MAX_DELAY)
        # 冰雪溶洞的落冰与下一次掉落倒计时。
        self.ice_shards = []
        self.shard_timer = random.uniform(ICE_SHARD_MIN_DELAY, ICE_SHARD_MAX_DELAY)
        self.last_hit_kind = ''
        self.training_mode = False
        # 砸瓦鲁多：剩余时停秒数与施法者槽位（-1 = 未在时停）。
        self.time_stop = 0.
        self.time_stop_owner = -1

    def start_round(self):
        # Energy and character loadouts carry over; only HP resets each round.
        carried = [(f.get('energy', 0),
                    {key: f.get(key) for key in LOADOUT_FIELDS})
                   for f in self.fighters]
        self.fighters = [fresh_fighter(210, 1), fresh_fighter(810, -1)]
        for fighter, (energy, loadout) in zip(self.fighters, carried):
            fighter.update(loadout)
            fighter['hp'] = fighter['hp_max']
            fighter['energy'] = energy
        self.buffers = [InputBuffer(), InputBuffer()]
        self.inputs = [{}, {}]
        self.time_left = ROUND_SECONDS
        self.phase, self.round_winner, self.pause_left = 'game', None, 0.
        self.countdown = ROUND_COUNTDOWN
        self.projectiles = []
        self.strikes = []
        self.fire_pillars = []
        self.pillar_timer = random.uniform(LAVA_PILLAR_MIN_DELAY, LAVA_PILLAR_MAX_DELAY)
        self.ice_shards = []
        self.shard_timer = random.uniform(ICE_SHARD_MIN_DELAY, ICE_SHARD_MAX_DELAY)
        self.last_hit_kind = ''
        self.time_stop = 0.
        self.time_stop_owner = -1

    def set_loadout(self, idx, style):
        """Apply a character definition (health / projectile / super / combo)."""
        fighter = self.fighters[idx]
        fighter['char_id'] = style['id']
        fighter['hp_max'] = int(style.get('health', DEFAULT_HP))
        fighter['hp'] = fighter['hp_max']
        fighter['projectile_config'] = dict(style.get('projectile', {}))
        fighter['super_spec'] = style.get('super')
        # combo_spec 仅作展示：剔除 attack，保持快照 JSON 可传输。
        fighter['combo_spec'] = {key: value for key, value in (style.get('combo') or {}).items()
                                 if key != 'attack'}
        fighter['super_radius'] = float(style.get('super_radius', 0.))
        fighter['super_cmd'] = style.get('super_command')
        # AI 搓招编排（纯 token 字符串，可 JSON 传输）；角色未写时留 None，
        # 由 AI 侧退化成单键 "super"。
        fighter['super_motion'] = style.get('super_motion')
        # 专属连招的 AI 搓招编排（素质三连 / 冰千年杀 / 落雷 / 护盾），角色
        # 未写时留 None，AI 侧视为没有专属技。
        fighter['combo_motion'] = style.get('combo_motion')
        fighter['super_kind'] = style.get('super_kind', '')
        fighter['super_distance'] = float(style.get('super_distance', 0.))
        fighter['super_throw'] = float(style.get('super_throw', 0.))
        # AI 大招射程模式（dash_only / dash_plus_reach / radius），新角色未写
        # 时默认 radius，与 fresh_fighter 的初始值一致。
        fighter['super_area_mode'] = style.get('super_area_mode', 'radius')
        fighter['buff_spec'] = style.get('buff')
        fighter['super_bolt'] = style.get('super_bolt')
        # 砸瓦鲁多：时停时长与瞬发拳伤害。
        fighter['super_time_stop'] = float(style.get('super_time_stop', 0.))
        fighter['super_punch_damage'] = int(style.get('super_punch_damage', 0))
        fighter['combo_attack'] = (style.get('combo') or {}).get('attack')
        fighter['move_speed'] = float(style.get('move_speed', MOVE_SPEED))
        fighter['dash_speed'] = fighter['move_speed'] * (DASH_SPEED / MOVE_SPEED)

    def snapshot(self):
        # Attack objects stay local; everything else must survive JSON transport.
        fighters = [{key: value for key, value in f.items()
                     if key not in ('super_spec', 'combo_attack')}
                    for f in self.fighters]
        return {'type':'state', 'phase':self.phase, 'fighters':fighters,
                'scores':list(self.scores), 'round':self.round, 'time_left':round(self.time_left,2),
                'round_winner':self.round_winner, 'winner':self.winner,
                'pause_left':round(self.pause_left,2), 'countdown':round(self.countdown,2),
                'frame':self.frame, 'protocol':4, 'map':self.map_id,
                'projectiles': self.projectiles, 'strikes': self.strikes,
                'fire_pillars': self.fire_pillars,
                'ice_shards': self.ice_shards,
                # 时停状态要随快照下发，客户端才能同步播放定格/计时器停摆。
                'time_stop': round(self.time_stop, 2),
                'time_stop_owner': self.time_stop_owner,
                'training_mode': self.training_mode}

    def _event(self, kind, player, **details):
        self.event_seq += 1
        return {'type':'combat', 'id':self.event_seq, 'event':kind, 'player':player, **details}

    def _apply_hitstop(self, attack, blocked=False):
        """命中停顿：按招式给固定帧数，格挡更轻，激光不打断引导。"""
        if attack == 'laser':
            return
        frames = HITSTOP_BLOCK if blocked else HITSTOP.get(attack, HITSTOP_DEFAULT)
        self.hitstop = max(self.hitstop, frames)

    @staticmethod
    def _downed_style_for(hit_kind):
        """根据终结招式选择败者倒地姿势：下段→趴着，大招/投掷/撞墙→平躺，其余→蜷缩。"""
        if hit_kind in ('crouch_punch', 'low_kick', 'crouch_projectile'):
            return 'prone'
        if hit_kind in ('super', 'grab', 'tackle', 'projectile'):
            return 'flat'
        return 'curl'

    def finish_round(self, winner):
        if self.phase != 'game': return
        self.round_winner = winner
        if winner is not None: self.scores[winner] += 1
        if max(self.scores) >= 2:
            self.winner = self.scores.index(2)
            self.phase, self.pause_left = 'match_end', MATCH_PAUSE
        else:
            self.phase, self.pause_left = 'round_end', ROUND_PAUSE
        # 败者必须倒在场上：根据终结招式选姿势；平局则两边都蜷缩。
        for idx, f in enumerate(self.fighters):
            if winner is None or idx != winner:
                if not f['knocked']:
                    self._knock_down(idx, [], style=self._downed_style_for(self.last_hit_kind))

    def step(self, dt, inputs=None):
        if inputs is not None:
            self.inputs = [dict(i) for i in inputs]
        self.accumulator += max(0., min(float(dt), .05))
        events = []
        while self.accumulator + 1e-9 >= TICK:
            self.accumulator -= TICK
            events.extend(self._tick())
        return events

    def _start_attack(self, idx, kind, events, cancel=False):
        f = self.fighters[idx]
        attack = attack_spec(f, kind)
        cost = attack.energy
        if kind in ('flame_buff', 'lightning_strike'):
            # The stance / spell bills its own energy price from the character spec.
            cost = int((f.get('buff_spec') or {}).get('energy', cost))
        if f['energy'] < cost: return False
        f['energy'] -= cost
        f['attack_kind'] = kind
        f['action'] = kind
        f['action_frame'] = 0
        if kind == 'super' and f.get('super_kind') == 'time_stop':
            # 砸瓦鲁多的喊招音效从时停生效提前到起手（前摇第一帧）播放；
            # 记下前摇进行中，若被打断会补发 time_stop_cancel 掐断音效。
            f['time_stop_casting'] = True
            events.append(self._event('time_stop_cast', idx))
        f['action_time'] = 0.
        f['attack_hit'] = False
        f['proj_spawned'] = False
        f['hit_count'] = 0
        f['rush_done'] = False
        f['pummel_hits'] = 0
        f['pummel_count'] = 0
        f['pummel_frame'] = 0
        f['pummel_state'] = ''
        f['pull_left'] = f['throw_left'] = 0
        f['pull_from'] = f['pull_to'] = f['throw_from'] = f['throw_to'] = 0.
        f['cooldown'] = attack_total(f, kind) * TICK
        f['cancel_left'] = 0
        # 新招式起手时关掉上一个空中挥空窗口，避免上一跳的窗口漏到这一招。
        f['air_cancel_left'] = 0
        if kind == 'laser':
            # 引导招式：没有前摇冷却，松手后由 LASER_RECOVER 收招。
            f['laser_cd'] = 0.
        # A cancel extends the chain; a fresh attack keeps it. The chain only
        # resets on a whiff (attack ends without connecting), on getting hit,
        # or on knockdown -- mashing buttons can never farm fresh cancels.
        f['cancel_chain'] = f['cancel_chain'] + 1 if cancel else f['cancel_chain']
        if kind == 'flame_buff':
            spec = f.get('buff_spec') or {}
            f['buff_charges'] = int(spec.get('charges', 3))
        elif kind == 'shield_buff':
            # 晚高峰警告：附加固定数值护盾并启动持续时间。
            f['shield_max'] = SHIELD_MAX
            f['shield'] = SHIELD_MAX
            f['shield_timer'] = SHIELD_DURATION
        elif kind == 'tackle':
            # 借过一下：重置霸体冲锋状态机。
            f['tackle_state'] = 'windup'
            f['tackle_contact_frame'] = 0
            f['tackle_slammed'] = False
            f['tackle_downed'] = False
            f['tackle_visual'] = None
            f['super_armor'] = False
        elif kind == 'lightning_strike':
            # The spell drops its warning ring under the opponent right away.
            self._spawn_strike(idx, self.fighters[1 - idx]['x'],
                               f.get('buff_spec') or {}, events)
        events.append(self._event(kind, idx))
        return True

    @staticmethod
    def _press_kind(f, k, presses, super_ready, specials=None, crouch=None):
        """Which attack the newly pressed buttons ask for ('' if none).

        ``presses`` 只含按下沿（普通拳脚、蹲招据此判定）；``specials`` 额外包含
        negative edge 的松开沿，只用于特殊技 / 抓取这类“指令招”。这样松键能出
        特殊技，但绝不会让一记普通拳 / 脚因为松手再打一次。
        ``crouch`` 是调用方确定的蹲姿意图（含方向缓存与宽容帧）；不传时退回当前帧。
        """
        if specials is None:
            specials = presses
        if crouch is None:
            crouch = bool(k.get('down'))
        if super_ready:
            return 'super'
        # 石面鬼之眼：技能键是引导型激光，蹲下也照常从眼睛射出。
        if 'projectile' in specials and (f.get('projectile_config') or {}).get('style') == 'laser':
            return 'laser'
        if f['grounded'] and crouch:
            if 'punch' in presses:
                return 'crouch_punch'
            if 'kick' in presses:
                return 'low_kick'
            if 'grab' in specials:
                return 'grab'
            if 'projectile' in specials:
                return 'crouch_projectile'
            return ''
        if 'punch' in presses and not f['grounded']:
            return 'jump_punch'
        for candidate in ('projectile', 'grab'):
            if candidate in specials:
                return candidate
        for candidate in ('kick', 'punch'):
            if candidate in presses:
                return candidate
        return ''

    @staticmethod
    def _kind_buttons(kind):
        """招式对应的按键：用于消费输入缓冲，防止同一次按键反复出招。"""
        if kind in ('punch', 'crouch_punch', 'jump_punch'):
            return ('punch',)
        if kind in ('kick', 'low_kick'):
            return ('kick',)
        if kind in ('projectile', 'crouch_projectile', 'laser',
                    'flame_buff', 'lightning_strike'):
            return ('projectile',)
        if kind in ('grab', 'tackle'):
            return ('grab',)
        if kind == 'ice_shadow':
            return ('punch',)
        if kind == 'shield_buff':
            return ('guard',)
        if kind == 'vapor_freeze':
            return ('guard',)
        if kind == 'super':
            return ('punch', 'kick')
        return ()

    def _clear_queue(self, f):
        """清空预输入队列（被击中 / 倒地 / 取消 / 超时）。"""
        f['queued_attack'] = ''
        f['queued_more'].clear()

    def _queue_attack(self, f, kind):
        """按输入顺序缓存攻击，最多 QUEUE_LIMIT 招。"""
        if not f['queued_attack']:
            f['queued_attack'] = kind
        elif f['queued_attack'] == kind and not f['queued_more']:
            # 同一招连点只保留一条，避免队列被重复拳脚排满。
            pass
        elif len(f['queued_more']) < QUEUE_LIMIT - 1:
            f['queued_more'].append(kind)
        f['queued_frame'] = self.frame

    def _pop_queue(self, f):
        """当前这招已经接上，把队首换成下一条预输入。"""
        f['queued_attack'] = f['queued_more'].pop(0) if f['queued_more'] else ''
        if f['queued_attack']:
            f['queued_frame'] = self.frame

    @staticmethod
    def _command_prefix(buffer, command):
        """Shared prefix parsing for charge stances and delayed spells."""
        if command == 'double_tap_up':
            return buffer.double_press('jump', window=14, recent=16)
        if command == 'double_tap_kick':
            return buffer.double_press('kick', window=14, recent=16)
        return buffer.double_down()

    def _spawn_strike(self, idx, x, spec, events):
        """Queue a delayed bolt: a warning ring, then a fall from the sky."""
        height = float(spec.get('height', 620.))
        self.strikes.append({
            'owner': idx, 'x': float(x),
            'damage': int(spec.get('damage', 0)),
            'radius': float(spec.get('radius', 60.)),
            'delay': float(spec.get('delay', 1.)),
            'air': bool(spec.get('air', False)),
            'stun': int(spec.get('stun', 14)),
            'speed': float(spec.get('speed', 2000.)),
            'top': height, 'y': height, 'target_y': 0.,
            'falling': False, 'hit': False, 'life': 0.,
        })
        events.append(self._event('strike', idx))

    def _resolve_strike(self, strike, victim, events):
        """Apply the bolt damage once it reaches the target height."""
        if victim['knocked'] or victim['invuln'] > 0:
            return
        if not strike['air'] and abs(victim['x'] - strike['x']) > strike['radius']:
            return  # the ring was telegraphed, so stepping out of it dodges the bolt
        hp_dmg = apply_damage(victim, strike['damage'])
        victim['flash'] = .15
        if not has_armor(victim):
            victim['stun'] = max(victim['stun'], strike['stun'] * TICK)
            if not strike['air']:
                victim['attack_kind'] = ''
        if hp_dmg > 0:
            gain_energy(self.fighters[strike['owner']], PROJECTILE_ENERGY_GAIN)
            gain_energy(victim, PROJECTILE_DAMAGE_ENERGY_GAIN)
        events.append(self._event('hit', strike['owner'], target=1 - strike['owner'],
                                  attack='strike', damage=strike['damage'], blocked=False))

    def _tick_map_hazards(self, events):
        """按地图推进场地机关。"""
        if self.map_id == LAVA_MAP:
            self._tick_lava(events)
        elif self.map_id == ICE_MAP:
            self._tick_ice(events)

    def _tick_lava(self, events):
        """熔岩地貌：随机区域先亮起预警圈，随后喷出一人高的火柱。"""
        self.pillar_timer -= TICK
        if self.pillar_timer <= 0:
            self.pillar_timer = random.uniform(LAVA_PILLAR_MIN_DELAY,
                                               LAVA_PILLAR_MAX_DELAY)
            pillar = {
                'x': random.uniform(ARENA_LEFT + LAVA_PILLAR_RADIUS,
                                    ARENA_RIGHT - LAVA_PILLAR_RADIUS),
                'radius': LAVA_PILLAR_RADIUS,
                'damage': LAVA_PILLAR_DAMAGE,
                'delay': LAVA_PILLAR_WARNING,
                'life': 0., 'hit': False,
            }
            self.fire_pillars.append(pillar)
            # 预警圈亮起的同一帧发出嘶鸣，玩家有时间走开。
            events.append(self._event('lava_warn', -1, x=pillar['x']))
        alive = []
        for pillar in self.fire_pillars:
            if pillar['delay'] > 0:
                pillar['delay'] = max(0., pillar['delay'] - TICK)
                if pillar['delay'] <= 0:
                    pillar['life'] = LAVA_PILLAR_DURATION
                    self._erupt_pillar(pillar, events)
                alive.append(pillar)
                continue
            pillar['life'] -= TICK
            if pillar['life'] > 0:
                alive.append(pillar)
        self.fire_pillars = alive

    def _erupt_pillar(self, pillar, events):
        """火柱喷发：命中区域内双脚未高过柱顶的角色，各结算一次伤害。"""
        events.append(self._event('lava_erupt', -1, x=pillar['x']))
        for idx, victim in enumerate(self.fighters):
            if victim['knocked'] or victim['invuln'] > 0:
                continue
            if (victim['attack_kind'] == 'ice_shadow'
                    and shadow_phase(victim) == 'hide'):
                continue
            if abs(victim['x'] - pillar['x']) > pillar['radius']:
                continue
            if victim['y'] > LAVA_PILLAR_HEIGHT:
                continue  # 跳到火柱顶端以上可以躲开
            hp_dmg = apply_damage(victim, pillar['damage'])
            victim['flash'] = .15
            if not has_armor(victim):
                victim['stun'] = max(victim['stun'], LAVA_PILLAR_STUN * TICK)
                victim['attack_kind'] = ''
                victim['cancel_left'] = 0
                victim['cancel_chain'] = 0
            if hp_dmg > 0:
                gain_energy(victim, DAMAGE_ENERGY_GAIN)
            events.append(self._event('hit', -1, target=idx, attack='lava',
                                      damage=pillar['damage'], blocked=False))

    def _tick_ice(self, events):
        """冰雪溶洞：高空随机掉落一人大小的冰棱，没有预警、下落极快。"""
        self.shard_timer -= TICK
        if self.shard_timer <= 0:
            self.shard_timer = random.uniform(ICE_SHARD_MIN_DELAY,
                                              ICE_SHARD_MAX_DELAY)
            shard = {
                'x': random.uniform(ARENA_LEFT + ICE_SHARD_RADIUS,
                                    ARENA_RIGHT - ICE_SHARD_RADIUS),
                'y': ICE_SHARD_START,
                'radius': ICE_SHARD_RADIUS,
                'hit': False,
            }
            self.ice_shards.append(shard)
            events.append(self._event('ice_fall', -1, x=shard['x']))
        alive = []
        for shard in self.ice_shards:
            prev = shard['y']
            shard['y'] = max(0., prev - ICE_SHARD_SPEED * TICK)
            if not shard['hit']:
                for idx, victim in enumerate(self.fighters):
                    if victim['knocked'] or victim['invuln'] > 0:
                        continue
                    if (victim['attack_kind'] == 'ice_shadow'
                            and shadow_phase(victim) == 'hide'):
                        continue
                    if abs(victim['x'] - shard['x']) > shard['radius']:
                        continue
                    # 冰棱这一帧扫过的高度区间要与身体区间相交（起跳可躲）。
                    if shard['y'] > victim['y'] + BODY_TOP or prev < victim['y']:
                        continue
                    self._freeze_fighter(idx, victim, events, shard['x'])
                    shard['hit'] = True
                    break
            if shard['y'] <= 0:
                events.append(self._event('ice_shatter', -1, x=shard['x']))
                continue
            alive.append(shard)
        self.ice_shards = alive

    def _freeze_fighter(self, idx, victim, events, x,
                        duration=ICE_FREEZE_TIME, kind='ice'):
        """冰冻命中：原地冻住，期间不能移动、出招或跳跃。

        ``kind`` 区分来源：'ice' 是冰雪溶洞的冰棱，'vapor' 是迪奥的气化
        冷冻法。只有 'vapor' 的冰会在挨打时碎裂（见近战命中结算）。
        """
        victim['frozen'] = duration
        victim['frozen_kind'] = kind
        victim['stun'] = max(victim['stun'], duration)
        victim['attack_kind'] = ''
        victim['cancel_left'] = 0
        victim['cancel_chain'] = 0
        self._clear_queue(victim)
        victim['flash'] = .15
        if kind == 'ice':
            events.append(self._event('ice_hit', -1, target=idx, x=x))

    def _knock_down(self, idx, events, duration=KNOCKDOWN_SECONDS, style='curl'):
        """Floor a fighter for the given duration (default 2 s).

        After the timer runs out they keep lying there (and stay untouchable)
        until their player sends any movement or attack command.
        ``style`` picks the lying pose: curl(缩着) / flat(平躺) / prone(趴着) / kneel(跪着).
        """
        f = self.fighters[idx]
        if f['knocked']: return
        if has_armor(f):
            return  # 霸体冲锋期间不会被压倒（撞墙、抓取投掷、扇形击倒均如此）
        f['knocked'] = True
        f['downed_style'] = style
        f['stun'] = max(f['stun'], duration)
        f['stagger'] = 0.
        f['attack_kind'] = ''
        f['attack_hit'] = False
        f['proj_spawned'] = False
        f['dash_time'] = 0.
        f['cancel_left'] = 0
        f['cancel_chain'] = 0
        events.append(self._event('knockdown', idx))

    def _build_stagger(self, idx, amount, events):
        """Every hit adds hit-stun to the stagger gauge; too much floors the victim."""
        f = self.fighters[idx]
        if f['knocked']: return
        f['stagger'] += min(amount, STAGGER_HIT_CAP)
        f['stagger_frame'] = self.frame
        if f['stagger'] >= STAGGER_LIMIT:
            self._knock_down(idx, events)

    def _rush_super(self, idx, events):
        """Rush super reposition: lunge forward, or flash behind the target.

        With an opponent inside ``super_distance`` the caster appears behind
        them (facing back) and the remaining slash frames cut them down. With
        nobody in range the caster simply covers the distance.
        """
        f = self.fighters[idx]
        victim = self.fighters[1 - idx]
        f['rush_done'] = True
        side = f['face']
        distance = (victim['x'] - f['x']) * side
        reach_distance = float(f.get('super_distance', 0.))
        in_range = (not victim['knocked'] and 0 <= distance <= reach_distance and
                    abs(victim['y'] - f['y']) <= 120)
        if in_range:
            behind = victim['x'] + side * 54
            if ARENA_LEFT <= behind <= ARENA_RIGHT:
                f['x'], f['face'] = behind, -side
            else:
                # Pinned against the wall: stop in front and keep slashing.
                f['x'] = max(ARENA_LEFT, min(ARENA_RIGHT, victim['x'] - side * 54))
        else:
            f['x'] = max(ARENA_LEFT, min(ARENA_RIGHT, f['x'] + side * reach_distance))
        events.append(self._event('rush', idx, behind=in_range))

    def _tick_dash_super(self, idx, f, events):
        """冲刺型大招（雷霆嘎巴）：前摇开头向前突进一次，随后照常出招。

        突进在 ``super_distance`` 内按 smoothstep 加速完成；贴身时提前停步，
        避免穿过对手导致击飞和半空落雷落空。
        """
        if f['rush_done']:
            return
        victim = self.fighters[1 - idx]
        face = f['face']
        af = f['action_frame']
        if af == 1:
            events.append(self._event('dash', idx, direction='forward'))
        gap = (victim['x'] - f['x']) * face
        if 0 < gap <= DASH_SUPER_STOP:
            f['rush_done'] = True
            return
        distance = float(f.get('super_distance', 0.)) or 180.
        t0 = _smoothstep((af - 1) / float(DASH_SUPER_FRAMES))
        t1 = _smoothstep(af / float(DASH_SUPER_FRAMES))
        f['x'] = max(ARENA_LEFT, min(ARENA_RIGHT,
                                    f['x'] + face * distance * (t1 - t0)))
        f['walk'] += .5
        if af >= DASH_SUPER_FRAMES:
            f['rush_done'] = True

    def _tick_ice_shadow(self, idx, events):
        """冰千年杀：钻地消失 → 1 秒潜行 → 瞬移至敌人脚下冲出命中 → 落地复位。"""
        f = self.fighters[idx]
        af = f['action_frame']
        f['vy'] = 0.
        phase = shadow_phase(f)
        if phase == 'burrow':
            # 前摇：快速下沉消失（潜行期间由渲染层隐藏身体）。
            t = (af + 1) / float(SHADOW_BURROW)
            f['y'] = -SHADOW_HEIGHT * _smoothstep(t)
        elif phase == 'hide':
            f['y'] = -SHADOW_HEIGHT
        elif phase == 'emerge':
            if af == SHADOW_BURROW + SHADOW_HIDE:
                self._shadow_hit(idx, events)
            t = (af - SHADOW_BURROW - SHADOW_HIDE + 1) / float(SHADOW_EMERGE)
            f['y'] = SHADOW_HEIGHT * _smoothstep(t)
        else:  # recover
            t = (af - SHADOW_BURROW - SHADOW_HIDE - SHADOW_EMERGE + 1) / float(SHADOW_RECOVER)
            f['y'] = SHADOW_HEIGHT * (1. - _smoothstep(t))

    def _shadow_hit(self, idx, events):
        """在敌人脚下钻出：瞬移至敌人当前位置，命中并小幅浮空敌人。"""
        f = self.fighters[idx]
        victim = self.fighters[1 - idx]
        spec = f['combo_attack']
        f['x'] = max(ARENA_LEFT, min(ARENA_RIGHT, victim['x']))
        f['face'] = 1 if victim['x'] >= f['x'] else -1
        if victim['knocked']:
            return
        hp_dmg = apply_damage(victim, spec.damage)
        victim['flash'] = .15
        armored = has_armor(victim)
        if not armored:
            victim['stun'] = max(victim['stun'], spec.stun * TICK)
            victim['attack_kind'] = ''
            victim['vy'] = 560.
            victim['y'] = max(victim['y'], 4.)
        if hp_dmg > 0:
            gain_energy(self.fighters[idx], HIT_ENERGY_GAIN)
            gain_energy(victim, DAMAGE_ENERGY_GAIN)
        if not armored:
            self._build_stagger(1 - idx, spec.stun, events)
        events.append(self._event('hit', idx, target=1 - idx, attack='ice_shadow',
                                  damage=spec.damage, blocked=False))

    def _tackle_hit(self, idx, damage, label, events):
        """霸体冲锋的一段伤害结算（撞击 / 摔地）。"""
        victim = self.fighters[1 - idx]
        if victim['knocked']:
            return
        apply_damage(victim, damage)
        victim['flash'] = .15
        if not has_armor(victim):
            victim['attack_kind'] = ''
            victim['stun'] = max(victim['stun'], 18 * TICK)
        # 大招命中不回能；受害者也不因大招受击回能。
        events.append(self._event('hit', idx, target=1 - idx, attack=label,
                                  damage=damage, blocked=False))

    def _tick_tackle_super(self, idx, events):
        """借过一下：半蹲蓄力 → 霸体冲锋 → 勾脖撞地 → 自己弹起收招。"""
        f = self.fighters[idx]
        victim = self.fighters[1 - idx]
        af = f['action_frame']
        face = f['face']
        state = f['tackle_state']
        if state == 'windup':
            if af >= TACKLE_WINDUP:
                f['tackle_state'] = 'rush'
                f['super_armor'] = True
                events.append(self._event('tackle_rush', idx))
            return
        if state == 'rush':
            f['x'] = max(ARENA_LEFT, min(ARENA_RIGHT,
                        f['x'] + face * TACKLE_RUSH_SPEED * TICK))
            f['walk'] += .5
            overlap = (abs(f['x'] - victim['x']) <= BODY_HALF_WIDTH * 2
                       and abs(f['y'] - victim['y']) <= 120
                       and not victim['knocked'] and victim['invuln'] <= 0)
            rushed = (af - TACKLE_WINDUP) * TACKLE_RUSH_SPEED * TICK
            reached = rushed >= float(f.get('super_distance', 0.))
            at_wall = f['x'] <= ARENA_LEFT + 1 or f['x'] >= ARENA_RIGHT - 1
            if overlap:
                f['tackle_state'] = 'slam'
                f['tackle_contact_frame'] = af
                # 勾住脖子：双方沿冲锋方向因惯性前带并腾空，走出一条抛物线。
                # 前带是真实位移；腾空高度只由渲染层读取，不参与判定。
                span = TACKLE_ARC * TICK
                f['tackle_visual'] = {'t': 0., 'span': span, 'face': face,
                                      'lift_peak': 40., 'carry': TACKLE_CARRY}
                victim['tackle_visual'] = {'t': 0., 'span': span, 'face': face,
                                           'lift_peak': 76., 'carry': TACKLE_CARRY,
                                           'trail': True}
                f['downed_style'] = 'kneel'
                self._tackle_hit(idx, TACKLE_CONTACT_DAMAGE, 'tackle_contact', events)
            elif reached or at_wall:
                f['tackle_state'] = 'recover'
                f['super_armor'] = False
            return
        if state == 'slam':
            if (not f['tackle_slammed'] and
                    af - f['tackle_contact_frame'] >= TACKLE_SLAM_DELAY):
                f['tackle_slammed'] = True
                # 摔到地上：施放者这时才跟着倒地（跪姿起身）。
                f['tackle_downed'] = True
                self._tackle_hit(idx, TACKLE_SLAM_DAMAGE, 'tackle_slam', events)
                self._knock_down(1 - idx, events, duration=TACKLE_KNOCKDOWN,
                                 style='flat')
                f['tackle_state'] = 'recover'
                f['super_armor'] = False
            return
        # recover：由主循环的 action_frame >= total 清理 attack_kind。

    @staticmethod
    def _grab_super_hits(f):
        """Punch count for the grab super: 4 at full health, +1 per 15% lost."""
        lost = 1. - f['hp'] / max(1., float(f['hp_max']))
        extra = int(lost / PUMMEL_HP_STEP + 1e-9)
        return min(PUMMEL_MAX_HITS, PUMMEL_BASE_HITS + extra)

    def _tick_grab_super(self, idx, f, events):
        """Red scarf grab super, staged like a Mortal Kombat long animation.

        The opponent is slowly dragged into the caster's front (pull), then
        held while each punch lands one a time (pummel), and finally hurled
        across half the arena (throw). Damage, punch count, throw distance and
        the knockdown are unchanged -- only the timing/presentation is longer.
        """
        if f['pummel_state'] == 'pull':
            self._tick_pull(idx, f, events)
            return
        if f['pummel_state'] == 'pummel':
            self._tick_pummel(idx, f, events)
            return
        if f['pummel_state'] == 'throw':
            self._tick_throw(idx, f, events)
            return

        spec = attack_spec(f, 'super')
        victim = self.fighters[1 - idx]
        # Still charging: wait for the first active frame before grabbing.
        if f['action_frame'] < spec.startup:
            return
        if has_armor(victim):
            return  # 霸体冲锋期间抓不住：抓取不能打断大招

        # First active frame: pull anyone inside the doubled blast radius.
        distance = (victim['x'] - f['x']) * f['face']
        reach = float(f.get('super_radius', 0.))
        if (victim['knocked'] or abs(distance) > reach or
                abs(victim['y'] - f['y']) > spec.hit_height):
            return  # nobody grabbed: the move whiffs and plays out

        target_x = max(ARENA_LEFT, min(ARENA_RIGHT,
                       f['x'] + f['face'] * GRAB_PULL_DISTANCE))
        if abs(target_x - f['x']) < GRAB_PULL_DISTANCE:
            # Pinned against the wall: shift the caster back a little.
            f['x'] = max(ARENA_LEFT, min(ARENA_RIGHT,
                        target_x - f['face'] * GRAB_PULL_DISTANCE))
            target_x = f['x'] + f['face'] * GRAB_PULL_DISTANCE

        victim['y'], victim['vy'] = 0., 0.
        victim['grounded'] = True
        victim['face'] = -f['face']
        victim['attack_kind'] = ''
        victim['dash_time'] = 0.
        f['pummel_hits'] = self._grab_super_hits(f)
        f['pummel_count'] = 0
        f['pummel_frame'] = 0
        # Enter the slow pull-in animation.
        f['pummel_state'] = 'pull'
        f['pull_from'] = victim['x']
        f['pull_to'] = target_x
        f['pull_left'] = GRAB_PULL_FRAMES
        events.append(self._event('grab_pull', idx, hits=f['pummel_hits']))

    def _tick_pull(self, idx, f, events):
        """Drag the victim smoothly from where they were into the caster's front."""
        victim = self.fighters[1 - idx]
        f['pull_left'] -= 1
        t = 1. - f['pull_left'] / float(GRAB_PULL_FRAMES)
        t = max(0., min(1., t))
        # Ease the motion so the yank reads as a clean suck-in.
        t = t * t * (3. - 2. * t)
        victim['x'] = f['pull_from'] + (f['pull_to'] - f['pull_from']) * t
        victim['stun'] = max(victim['stun'], 6 * TICK)
        victim['attack_kind'] = ''
        if f['pull_left'] <= 0:
            victim['x'] = f['pull_to']
            f['pummel_state'] = 'pummel'
            f['pummel_frame'] = f['action_frame']

    def _tick_pummel(self, idx, f, events):
        """Hold the victim and land one punch per hit_interval frames."""
        spec = attack_spec(f, 'super')
        victim = self.fighters[1 - idx]
        victim['x'] = f['pull_to']
        victim['stun'] = max(victim['stun'], 6 * TICK)
        victim['attack_kind'] = ''
        if f['pummel_count'] >= f['pummel_hits']:
            return
        if f['action_frame'] - f['pummel_frame'] < spec.hit_interval:
            return
        f['pummel_frame'] = f['action_frame']
        f['pummel_count'] += 1
        hp_dmg = apply_damage(victim, PUMMEL_DAMAGE)
        victim['flash'] = .15
        if hp_dmg > 0:
            gain_energy(victim, DAMAGE_ENERGY_GAIN)
        f['combo'] = f['combo'] + 1
        f['last_hit_frame'] = self.frame
        final = f['pummel_count'] >= f['pummel_hits']
        events.append(self._event('hit', idx, target=1 - idx,
                                  attack='super_pummel', damage=PUMMEL_DAMAGE,
                                  blocked=False, bonus=0, final=final))
        self._apply_hitstop('super_pummel')
        if final:
            # Start the launch animation: hurl the victim half an arena away.
            throw = float(f.get('super_throw', 0.)) or HALF_MAP
            f['pummel_state'] = 'throw'
            f['throw_from'] = victim['x']
            f['throw_to'] = max(ARENA_LEFT, min(ARENA_RIGHT,
                               victim['x'] + f['face'] * throw))
            f['throw_left'] = GRAB_THROW_FRAMES

    def _tick_throw(self, idx, f, events):
        """Fly the victim across the arena, then floor them for 2 seconds."""
        victim = self.fighters[1 - idx]
        f['throw_left'] -= 1
        t = 1. - f['throw_left'] / float(GRAB_THROW_FRAMES)
        t = max(0., min(1., t))
        # Quick launch that decelerates as they skid to a stop.
        t = 1. - (1. - t) * (1. - t)
        victim['x'] = f['throw_from'] + (f['throw_to'] - f['throw_from']) * t
        victim['stun'] = max(victim['stun'], 6 * TICK)
        victim['attack_kind'] = ''
        if f['throw_left'] <= 0:
            victim['x'] = f['throw_to']
            victim['y'], victim['vy'] = 0., 0.
            victim['grounded'] = True
            f['pummel_state'] = ''
            f['pummel_hits'] = 0
            events.append(self._event('throw', idx, target=1 - idx,
                                      from_x=f['throw_from']))
            self._knock_down(1 - idx, events, style='prone')

    def _spawn_projectile(self, idx, kind, events=None):
        """Fire the owner's projectile high (standing) or low (crouch shot)."""
        f = self.fighters[idx]
        cfg = f.get('projectile_config', {})
        height = NECK_HEIGHT if kind == 'projectile' else CROUCH_PROJ_HEIGHT
        self.projectiles.append({
            "x": f["x"] + f["face"] * 30,
            "y": f.get("y", 0) + height,
            "vx": f["face"] * cfg.get("speed", 420),
            "damage": cfg.get("damage", 12),
            "lifetime": cfg.get("lifetime", 0.7),
            "owner": idx,
            "attack": kind,
            "color": cfg.get("color", (255, 200, 80)),
            "size": cfg.get("size", 7),
            "style": cfg.get("style", "orb"),
            "length": cfg.get("length", 0),
            "spin": cfg.get("spin", 0.0),
            "angle": 0.0,
            "hit": False,
        })
        if events is not None:
            events.append(self._event("projectile", idx))

    def _begin_time_stop(self, idx, events):
        """砸瓦鲁多：前摇结束，全场时间停止。"""
        if self.time_stop > 0:
            return
        f = self.fighters[idx]
        # 前摇结束就进入时停，后摇帧不再播放（时停本身接管了这段演出）。
        f['attack_kind'] = ''
        f['action_frame'] = 0
        f['action_time'] = 0.
        f['proj_spawned'] = False
        f['attack_hit'] = False
        f['cooldown'] = 0.
        self._clear_queue(f)
        f['time_stop_casting'] = False
        # 每次时停重置连段进度（拳数、飞刀），压路机与新飞刀都从头开始。
        f['time_punch_count'] = 0
        f['knife_cd'] = 0.
        f['knife_count'] = 0
        self.time_stop = float(f.get('super_time_stop', 0.)) or TIME_STOP_DEFAULT
        self.time_stop_owner = idx
        events.append(self._event('time_stop', idx, duration=round(self.time_stop, 2)))

    def _end_time_stop(self, events):
        """时停结束（自然到期 / 压路机 / KO 提前结束）。"""
        owner = self.time_stop_owner
        self.time_stop = 0.
        self.time_stop_owner = -1
        # 悬停的飞刀在时间恢复的瞬间一起射出（"你以为躲开了吗？"）。
        rushed = 0
        for p in self.projectiles:
            if p.get('knife') and p.get('frozen'):
                p['frozen'] = False
                p['vx'] = self.fighters[p['owner']]['face'] * KNIFE_SPEED
                p['lifetime'] = KNIFE_LIFETIME
                rushed += 1
        if rushed:
            events.append(self._event('knife_rush', owner, count=rushed))
        events.append(self._event('time_resume', -1))

    def _time_stop_punch(self, idx, events):
        """时停中的瞬发拳：没有前后摇，只结算伤害。

        时停期间受击方不打断、不倒地、不累积硬直槽（硬直留到时停结束后再算，
        所以这里的命中完全不碰 stagger）；迪奥自己也不因这一拳涨能量。
        """
        f = self.fighters[idx]
        victim = self.fighters[1 - idx]
        # 空挥也要有出拳动作：先点亮视觉动画，再判定是否打中。
        f['time_punch_anim'] = TIME_STOP_PUNCH_ANIM
        # 连打换手：每次按 J 前后手轮换，第一拳由前手打出。
        f['time_punch_side'] = 1 - int(f.get('time_punch_side', 0))
        if victim['knocked'] or victim['invuln'] > 0:
            return
        spec = ATTACKS['punch']
        distance = (victim['x'] - f['x']) * f['face']
        if not (0 <= distance <= spec.reach and
                abs(victim['y'] - f['y']) <= TIME_STOP_PUNCH_HEIGHT):
            return
        damage = int(f.get('super_punch_damage', 0) or spec.damage)
        hp_dmg = apply_damage(victim, damage)
        # 受击方保持定格：不设 flash（否则被冻结后 flash 不会衰减，会一直发白），
        # 也不进入硬直 / 击倒，只靠 UI 的伤害数字与命中特效表现"打到了"。
        if hp_dmg > 0:
            gain_energy(victim, DAMAGE_ENERGY_GAIN)
            # 打中才算连段进度：压路机的 5 拳门槛只认真正落地的拳。
            f['time_punch_count'] = int(f.get('time_punch_count', 0)) + 1
        self.last_hit_kind = 'time_punch'
        events.append(self._event('hit', idx, target=1 - idx, attack='time_punch',
                                  damage=damage, blocked=False))
        if victim['hp'] <= 0 and not self.training_mode:
            # KO：直接结束时停并判定胜利（训练场不结算回合，交给重生逻辑）。
            self._end_time_stop(events)
            self.finish_round(idx)

    def _time_stop_knife(self, idx, events):
        """时停中掏飞刀：悬停在身前，时间恢复的瞬间齐射。

        飞刀不结算伤害（要等时间恢复），也不占攻击状态机，所以掏刀和 MUDA
        连打共用同一段时间——想齐射就得放弃这几秒的拳数。
        """
        f = self.fighters[idx]
        if f['knife_count'] >= KNIFE_MAX or f['knife_cd'] > 0:
            return
        i = f['knife_count']
        f['knife_count'] += 1
        f['knife_cd'] = KNIFE_INTERVAL
        self.projectiles.append({
            "x": f["x"] + f["face"] * (KNIFE_OFFSET + i * 5),
            "y": f.get("y", 0.) + KNIFE_HEIGHTS[i % len(KNIFE_HEIGHTS)],
            "vx": 0., "damage": KNIFE_DAMAGE, "lifetime": 0.,
            "owner": idx, "attack": "knife", "color": (228, 232, 240),
            "size": 5, "style": "knife", "length": 26, "spin": 0.,
            "angle": 0., "hit": False, "frozen": True, "knife": True,
            "face": f["face"],
        })
        events.append(self._event('knife_throw', idx, index=i))

    def _time_stop_road_roller(self, idx, events):
        """ROAD ROLLER DA!!：时停终结技。砸下即恢复时间，悬停飞刀同时齐射。"""
        f = self.fighters[idx]
        victim = self.fighters[1 - idx]
        if f['time_punch_count'] < ROLLER_REQUIRED_HITS:
            return
        f['time_punch_count'] = 0
        f['time_punch_anim'] = 0
        # 先恢复时间：飞刀齐射与压路机砸下发生在同一帧，演出最接近原著。
        self._end_time_stop(events)
        f['cooldown'] = ROLLER_RECOVER * TICK
        self.last_hit_kind = 'road_roller'
        hp_dmg = apply_damage(victim, ROLLER_DAMAGE)
        if hp_dmg > 0:
            gain_energy(victim, DAMAGE_ENERGY_GAIN)
        events.append(self._event('hit', idx, target=1 - idx, attack='road_roller',
                                  damage=ROLLER_DAMAGE, blocked=False))
        events.append(self._event('road_roller', idx, target=1 - idx))
        self._apply_hitstop('road_roller', False)
        if victim['hp'] <= 0 and not self.training_mode:
            self.finish_round(idx)
            return
        self._knock_down(1 - idx, events, duration=ROLLER_KNOCKDOWN, style='flat')

    def _spawn_ice_beam(self, idx, events):
        """气化冷冻法：向前射出一段蓝色冰束，命中把对手冻住。

        冰束是飞行道具，走投射物的判定：站立防御能挡下（只吃擦伤、不冻结），
        蹲下能从下方让过去——换来的是从贴身到近中距离都能起手。
        """
        f = self.fighters[idx]
        cfg = (f.get('combo_spec') or {}).get('beam') or {}
        length = float(cfg.get('length', 64))
        self.projectiles.append({
            "x": f["x"] + f["face"] * (30 + length * .5),
            "y": f.get("y", 0.) + NECK_HEIGHT,
            "vx": f["face"] * float(cfg.get("speed", 900.)),
            "damage": cfg.get("damage", 12),
            "lifetime": float(cfg.get("lifetime", .42)),
            "owner": idx, "attack": "ice_beam",
            "color": cfg.get("color", (128, 206, 255)),
            "size": cfg.get("size", 7),
            "style": "beam", "length": length,
            "spin": 0., "angle": 0., "hit": False,
        })
        events.append(self._event('vapor_beam', idx))

    def _tick_laser(self, idx, f, k, events):
        """石面鬼之眼：按住技能键引导激光，命中立刻结算，此后每 0.5 秒一次。"""
        if f['stun'] > 0 or f['knocked'] or not k.get('projectile'):
            # 松手 / 被打断：光柱立即收束，进入短暂收招。
            f['attack_kind'] = ''
            f['action_frame'] = 0
            f['action_time'] = 0.
            f['proj_spawned'] = False
            f['laser_cd'] = 0.
            f['laser_low'] = False
            f['cooldown'] = LASER_RECOVER * TICK
            events.append(self._event('laser_end', idx))
            return
        # 按住 S 一边蹲一边放：光柱从更低的眼睛位置射出。
        low = bool(k.get('down')) and f['grounded']
        f['laser_low'] = low
        f['action_frame'] += 1
        f['action_time'] = f['action_frame'] * TICK
        if f['action_frame'] <= LASER_STARTUP:
            return
        cfg = f.get('projectile_config') or {}
        face = f['face']
        eye_y = f.get('y', 0.) + (LASER_CROUCH_EYE_HEIGHT if low else LASER_EYE_HEIGHT)
        # 激光打到场地边界为止。
        wall = (ARENA_RIGHT - f['x']) if face > 0 else (f['x'] - ARENA_LEFT)
        length = max(0., min(float(cfg.get('length', 430.)), wall))
        victim = self.fighters[1 - idx]
        touching = True
        if victim['knocked'] or victim['invuln'] > 0:
            touching = False
        elif victim['attack_kind'] == 'ice_shadow' and shadow_phase(victim) == 'hide':
            touching = False
        if touching:
            low_y, high_y = body_span(victim)
            distance = (victim['x'] - f['x']) * face
            # 光柱是带厚度的横条：竖直方向与受击盒相交才算命中，蹲姿也包进来。
            touching = (-BODY_HALF_WIDTH * .5 <= distance <= length + BODY_HALF_WIDTH and
                        low_y <= eye_y + LASER_HALF_THICK and
                        eye_y - LASER_HALF_THICK <= high_y)
        if not touching:
            f['laser_cd'] = 0.   # 脱离光柱后重新接触立刻再吃一次伤害
            return
        if f['laser_cd'] > 0:
            f['laser_cd'] = max(0., f['laser_cd'] - TICK)
            return
        f['laser_cd'] = float(cfg.get('tick_interval', LASER_INTERVAL))
        damage = int(cfg.get('damage', LASER_MIN_DAMAGE))
        defending = (guard_blocks(victim['action'], 'projectile') and
                     victim['face'] == -face)
        dmg = max(1, damage // 5) if defending else damage
        hp_dmg = apply_damage(victim, dmg)
        victim['flash'] = .15
        # 激光不打断对手、也不累积硬直槽：它只是持续压制，靠低伤害慢慢磨，
        # 不负责把人钉在原地。
        if hp_dmg > 0:
            gain_energy(f, 4)
            gain_energy(victim, 2)
        self.last_hit_kind = 'laser'
        events.append(self._event('hit', idx, target=1 - idx, attack='laser',
                                  damage=dmg, blocked=defending))

    def _tick_match_end_freeroam(self, events):
        """match_end 阶段：胜者自由行动，败者倒地冻结，不结算任何命中。"""
        winner = self.winner
        if winner is None:
            return
        w = self.fighters[winner]
        k = self.inputs[winner]
        presses = self.buffers[winner].push(k, w['face'])
        move = int(bool(k.get('right'))) - int(bool(k.get('left')))
        w['cooldown'] = max(0., w['cooldown'] - TICK)
        w['stun'] = max(0., w['stun'] - TICK)
        w['frozen'] = max(0., w['frozen'] - TICK)
        w['flash'] = max(0., w['flash'] - TICK)
        w['invuln'] = max(0., w['invuln'] - TICK)
        # 朝向默认朝前（朝场地中央），自由行动时不强制锁定对手。
        if not w['attack_kind'] and w['stun'] <= 0 and not w['knocked']:
            if move:
                w['x'] = max(ARENA_LEFT, min(ARENA_RIGHT,
                            w['x'] + move * w['move_speed'] * TICK))
                w['walk'] += 1
                w['face'] = move
            else:
                w['walk'] = 0
        # 跳跃
        if w['stun'] <= 0 and not w['attack_kind'] and not w['knocked'] and 'jump' in presses:
            if w['y'] <= 0:
                w['vy'] = JUMP_SPEED
                w['air_jump'] = False
                events.append(self._event('jump', winner))
            elif not w['air_jump']:
                w['vy'] = JUMP_SPEED * .86
                w['air_jump'] = True
                events.append(self._event('jump', winner, air=True))
        if w['y'] > 0 or w['vy'] > 0:
            w['y'] += w['vy'] * TICK
            w['vy'] -= GRAVITY * TICK
            if w['y'] <= 0:
                w['y'], w['vy'] = 0., 0.
                w['air_jump'] = False
                events.append(self._event('land', winner))
        w['grounded'] = w['y'] <= 0
        # 普通攻击与大招空挥（不检测命中、不扣能量——展示阶段无消耗）
        kind = self._press_kind(w, k, presses, False)
        if kind and w['stun'] <= 0 and not w['knocked'] and w['cooldown'] <= 0:
            if kind in ('super', 'flame_buff', 'lightning_strike', 'ice_shadow',
                        'tackle', 'shield_buff'):
                kind = ''  # 展示阶段禁止大招/霸体/法术，避免视觉爆炸
            if kind:
                self._start_attack(winner, kind, events)
        if w['attack_kind']:
            w['action_frame'] += 1
            w['action_time'] = w['action_frame'] * TICK
            if w['action_frame'] >= attack_total(w, w['attack_kind']):
                w['attack_kind'] = ''
                w['action'] = 'idle'
                w['action_frame'] = 0
                w['action_time'] = 0.
                w['proj_spawned'] = False
                w['attack_hit'] = False
        elif w['stun'] > 0:
            w['action'] = 'hurt'
        elif w['y'] > 0 or not w['grounded']:
            w['action'] = 'jump'
        elif k.get('down'):
            w['action'] = 'crouch'
        else:
            w['action'] = 'run' if move else 'idle'
        # 败者：保持倒地姿势，动画帧推进，不响应输入
        loser = self.fighters[1 - winner]
        loser['action'] = 'downed'
        loser['action_frame'] = min(loser['action_frame'] + 1, 10**9)
        loser['flash'] = max(0., loser['flash'] - TICK)

    def _tick(self):
        if self.hitstop > 0:
            # 打击停顿：双方一起定格几帧。输入照常记录，停顿期间按的键
            # 会留在缓冲里，解冻后立刻接上。
            self.hitstop -= 1
            for i, f in enumerate(self.fighters):
                self.buffers[i].push(self.inputs[i], f['face'])
            return []
        self.frame += 1
        events = []
        # 大招前摇被打断（被打、被冻、倒地）：动作已被清空但时停尚未生效，
        # 通知表现层把已经开始播放的喊招音效掐断。
        for i, f in enumerate(self.fighters):
            if f.get('time_stop_casting') and f['attack_kind'] != 'super':
                f['time_stop_casting'] = False
                events.append(self._event('time_stop_cancel', i))
        if self.phase == 'match_end':
            # 比赛结束：胜者可自由行动（移动/跳跃/空挥），败者倒地冻结。
            # 计时器、命中检测、投射物全部跳过——这只是纯展示阶段。
            self._tick_match_end_freeroam(events)
            return events
        if self.phase != 'game':
            self.pause_left = max(0., self.pause_left - TICK)
            if self.phase == 'round_end' and self.pause_left == 0:
                self.round += 1
                self.start_round()
                events.append(self._event('round_start', -1))
            return events
        if self.countdown > 0:
            # Pre-round countdown: fighters and the round clock stay frozen.
            self.countdown = max(0., self.countdown - TICK)
            return events
        # 时停：除施法者外全场冻结，回合计时器与场地机关也一并停摆。
        if self.time_stop > 0:
            self.time_stop = max(0., self.time_stop - TICK)
            if self.time_stop <= 1e-6:
                self._end_time_stop(events)
        else:
            self.time_left = max(0., self.time_left - TICK)
            self._tick_map_hazards(events)
        for i,f in enumerate(self.fighters):
            if self.time_stop > 0 and i != self.time_stop_owner:
                continue
            opponent = self.fighters[1-i]
            if not f['attack_kind'] and f['stun'] <= 0 and not f['knocked']:
                f['face'] = 1 if opponent['x'] >= f['x'] else -1
        for i,f in enumerate(self.fighters):
            k = self.inputs[i]
            presses = self.buffers[i].push(k, f['face'])
            # negative edge：本帧未被消费的松键，特殊技 / 指令也可由它触发。
            release_edges = self.buffers[i].releases
            if self.time_stop > 0 and i != self.time_stop_owner:
                # 被定格的角色整帧不推进：姿势、受击、硬直、重力全部保持原样。
                # 输入仍照常记录（push 已执行），恢复后立刻能响应，也不会在
                # 恢复的那一帧凭空多出按下沿。
                continue
            move = int(bool(k.get('right'))) - int(bool(k.get('left')))
            # 时停期间施法者移速翻倍（冲刺同理）。
            speed_mult = (TIME_STOP_SPEED_MULT
                          if self.time_stop > 0 and i == self.time_stop_owner else 1.)
            f['cooldown'] = max(0., f['cooldown'] - TICK)
            f['knife_cd'] = max(0., f.get('knife_cd', 0.) - TICK)
            f['stun'] = max(0., f['stun'] - TICK)
            f['frozen'] = max(0., f['frozen'] - TICK)
            # 护盾持续时间倒计时；到点自动消散。
            if f.get('shield_timer', 0.) > 0:
                f['shield_timer'] = max(0., f['shield_timer'] - TICK)
                if f['shield_timer'] <= 1e-6:
                    f['shield_timer'] = 0.
                    f['shield'] = 0
                    f['shield_max'] = 0
            if f['stun'] > 0 or f['knocked']:
                # Losing control throws away any buffered attack and cancel window.
                self._clear_queue(f)
                f['cancel_left'] = 0
            elif f['queued_attack'] and self.frame - f['queued_frame'] > QUEUE_TTL:
                # 太早的预输入已经失去意义，作废掉，免得突然自己打出来。
                self._clear_queue(f)
            if f['knocked']:
                # The minimum knockdown time must elapse first; after that the
                # fighter keeps lying down until their player gives any command.
                if f['stun'] <= 0 and (move or presses or k.get('down') or k.get('guard')):
                    f['knocked'] = False
                    f['stagger'] = 0.
                    # Wake-up protection: rising fighters are untouchable for a
                    # beat so the knockdown resets the exchange -- the opponent
                    # must respect the get-up instead of re-stagging on wake.
                    f['invuln'] = GETUP_INVULN_FRAMES * TICK
                    events.append(self._event('getup', i))
            else:
                if self.frame - f['stagger_frame'] > STAGGER_HOLD_FRAMES:
                    f['stagger'] = max(0., f['stagger'] - STAGGER_DECAY * TICK)
            f['flash'] = max(0., f['flash'] - TICK)
            f['invuln'] = max(0., f['invuln'] - TICK)
            if f['attack_kind'] != 'ice_shadow' and f['y'] < 0:
                # 冰千年杀被打断（受击 / 击倒 / 熔岩等）：立即从地下复位。
                # 重力只在 y > 0 时生效，不复位的话角色会永远卡在地面以下。
                f['y'], f['vy'] = 0., 0.
                f['air_jump'] = False
                f['grounded'] = True
                events.append(self._event('land', i))
            if f['stun'] <= 0 and not f['attack_kind'] and not f['knocked'] and 'jump' in presses:
                if f['y'] <= 0:
                    f['vy'] = JUMP_SPEED
                    f['air_jump'] = False
                    events.append(self._event('jump', i))
                elif not f['air_jump']:
                    f['vy'] = JUMP_SPEED * .86
                    f['air_jump'] = True
                    events.append(self._event('jump', i, air=True))
            if f['y'] > 0 or f['vy'] > 0:
                f['y'] += f['vy'] * TICK
                f['vy'] -= GRAVITY * TICK
                if f['y'] <= 0:
                    f['y'], f['vy'] = 0., 0.
                    f['air_jump'] = False
                    events.append(self._event('land', i))
            f['grounded'] = f['y'] <= 0
            vis = f.get('tackle_visual')
            if vis:
                # 借过一下抛物线的惯性前带：x 位移真实生效，腾空高度只画不判。
                f['x'] = max(ARENA_LEFT, min(ARENA_RIGHT,
                            f['x'] + vis['face'] * TACKLE_CARRY / TACKLE_ARC))
                vis['t'] += TICK
                if vis['t'] >= vis['span']:
                    f['tackle_visual'] = None
            if f['attack_kind'] == 'laser':
                # 石面鬼之眼自己推进帧并结算命中（松开技能键才结束）。
                self._tick_laser(i, f, k, events)
            elif f['attack_kind']:
                f['action_frame'] += 1
                f['action_time'] = f['action_frame'] * TICK
                # Spawn projectile on the active frame
                if f['attack_kind'] == 'jump_punch' and not f['grounded'] and not f['attack_hit']:
                    spec = attack_spec(f, 'jump_punch')
                    if f['action_frame'] == spec.startup + spec.active:
                        # 空中普通技挥空：进入收招的瞬间开一个短取消窗。
                        f['air_cancel_left'] = AIR_WHIFF_CANCEL_FRAMES
                if f['attack_kind'] in ('projectile', 'crouch_projectile') and not f.get('proj_spawned'):
                    spec = ATTACKS[f['attack_kind']]
                    if spec.startup <= f['action_frame'] < spec.startup + spec.active:
                        f['proj_spawned'] = True
                        self._spawn_projectile(i, f['attack_kind'], events)
                if f['attack_kind'] == 'vapor_freeze' and not f.get('proj_spawned'):
                    spec = attack_spec(f, 'vapor_freeze')
                    if spec.startup <= f['action_frame'] < spec.startup + spec.active:
                        f['proj_spawned'] = True
                        self._spawn_ice_beam(i, events)
                if f['attack_kind'] == 'super' and f.get('super_kind') == 'grab_pummel':
                    self._tick_grab_super(i, f, events)
                if (f['attack_kind'] == 'super' and f.get('super_kind') == 'rush_slash'
                        and not f['rush_done']):
                    # The rush reposition happens on the first active frame so
                    # the slashes always land at the new position.
                    if f['action_frame'] >= attack_spec(f, 'super').startup:
                        self._rush_super(i, events)
                if (f['attack_kind'] == 'super' and f.get('super_kind') == 'dash_launch'
                        and not f['rush_done']):
                    # 雷霆嘎巴：冲刺发生在前摇开头，冲完才进入出招帧。
                    self._tick_dash_super(i, f, events)
                if f['attack_kind'] == 'ice_shadow':
                    self._tick_ice_shadow(i, events)
                if f['attack_kind'] == 'tackle':
                    self._tick_tackle_super(i, events)
                if (f['attack_kind'] == 'super' and f.get('super_kind') == 'time_stop'
                        and f['action_frame'] >= attack_spec(f, 'super').startup):
                    # 砸瓦鲁多：前摇走完，时间停止（会清空 attack_kind）。
                    self._begin_time_stop(i, events)
                if f['attack_kind'] and f['action_frame'] >= attack_total(f, f['attack_kind']):
                    # A move that finishes without ever connecting is a whiff:
                    # it ends the cancel chain, so the next clean hit starts a
                    # fresh string of at most MAX_CANCEL_CHAIN cancels.
                    if not f['attack_hit'] and not f.get('hit_count'):
                        f['cancel_chain'] = 0
                    f['attack_kind'] = ''
                    f['action_frame'] = 0
                    f['action_time'] = 0.
                    f['proj_spawned'] = False
            free = (not f['attack_kind'] and f['stun'] <= 0 and
                    f['cooldown'] <= 0 and not f['knocked'])
            # Super art: J and K pressed together, or within a short 6-frame window.
            # Negative edge：松键也算输入，所以 super 的按钮判定同时看按下沿与松开沿。
            punch_press = 'punch' in presses
            kick_press = 'kick' in presses
            punch_now = punch_press or 'punch' in release_edges
            kick_now = kick_press or 'kick' in release_edges
            buffer = self.buffers[i]
            command = f.get('super_cmd')
            owner_stopped = self.time_stop > 0 and i == self.time_stop_owner
            if owner_stopped:
                # 时停期间只有三个动作：J 瞬发拳（MUDA 连打）、U 掏飞刀、
                # K 压路机收尾（需先打中 5 拳）。
                if punch_press:
                    self._time_stop_punch(i, events)
                elif 'projectile' in presses:
                    self._time_stop_knife(i, events)
                elif 'kick' in presses:
                    self._time_stop_road_roller(i, events)
            # Some supers need a command prefix
            # (red: S S J K, blue / yellow: D D / A A J J).
            if command == 'double_down':
                command_ok = buffer.double_down()
            elif command == 'double_tap_punch':
                command_ok = (buffer.double_tap_recent('forward') or
                              buffer.double_tap_recent('back'))
            elif command == 'double_tap_kick':
                command_ok = buffer.double_press('kick', window=14, recent=16)
            elif command == 'double_down_dir_grab':
                # 借过一下：S S + 方向键 + I
                command_ok = buffer.double_down() and buffer.direction_tap()
            elif command == 'double_down_cast':
                # 砸瓦鲁多：S S + L L（L = 防御键，双击）。
                command_ok = buffer.double_down() and buffer.double_press('guard')
            else:
                command_ok = True
            super_ready = bool(f['grounded'] and f['stun'] <= 0 and not f['knocked'] and
                               command_ok and
                               f['energy'] >= attack_spec(f, 'super').energy)
            if super_ready and command == 'double_tap_punch':
                super_ready = punch_now and buffer.double_press('punch')
            elif super_ready and command == 'double_tap_kick':
                # K K J: the two kicks may already be a few frames old, so the
                # double press keeps a wider "recent" window than the blue one.
                super_ready = punch_now and buffer.double_press(
                    'kick', window=14, recent=16)
            elif super_ready and command == 'double_down_dir_grab':
                # 借过一下：S S + 方向键之后按抓取键 I（松键也算）。
                super_ready = 'grab' in presses or 'grab' in release_edges
            elif super_ready and command == 'double_down_cast':
                # 砸瓦鲁多：S S + L L 已在上面解析完，不再额外要求 J / K。
                pass
            elif super_ready:
                super_ready = ((punch_now or kick_now) and
                               (punch_now or buffer.pressed_within('punch', 6)
                                or buffer.released_within('punch', 6)) and
                               (kick_now or buffer.pressed_within('kick', 6)
                                or buffer.released_within('kick', 6)))
            # Whiffs always play the full move. A move that connects (hit or
            # block) opens a short cancel window: the rest of its recovery can
            # be skipped into another attack, at most MAX_CANCEL_CHAIN times.
            buff_spec = f.get('buff_spec')
            spell = bool(buff_spec and buff_spec.get('kind') == 'strike')
            buff_press = (bool(buff_spec) and not f['knocked'] and f['stun'] <= 0
                          and (f['grounded'] or spell)
                          and ('projectile' in presses or 'projectile' in release_edges)
                          and self._command_prefix(buffer, buff_spec.get('command')))
            # 输入缓冲：本帧没有新的按下沿时，回看最近几帧缓存里的攻击键。
            # 这样收招末尾 / 硬直刚结束时按下的键会立刻接上，而不是白按。
            buffered = frozenset()
            if not presses and f['stun'] <= 0 and not f['knocked']:
                buffered = buffer.buffered_buttons(ATTACK_BUFFER_FRAMES)
            # 蹲 / 站判定：有新的按下沿时看这一帧的方向（同帧松开 S 也给几帧宽容）；
            # 借用缓冲按键时，改用按键按下那一刻缓存的方向，避免“按的时候蹲着、
            # 收招结束已经站起来”被错判成站立招。
            if presses:
                crouch = bool(k.get('down')) or buffer.down_recent(CROUCH_GRACE)
            elif buffered:
                crouch = buffer.buffered_down(ATTACK_BUFFER_FRAMES)
            else:
                crouch = False
            # 特殊技也接受 negative edge 的松开沿；普通拳脚只认按下沿。
            specials = presses | buffered | release_edges
            kind = self._press_kind(f, k, presses or buffered, super_ready, specials,
                                    crouch)
            if super_ready and command == 'double_down_dir_grab':
                kind = 'tackle'
            # 专属连招：冰千年杀（S S 移动 J）/ 晚高峰警告（S S L）/
            # 气化冷冻法（A/D L L）。
            combo_attack = f.get('combo_attack')
            combo_spec = f.get('combo_spec') or {}
            combo_trigger = combo_spec.get('trigger')
            combo_ready = False
            combo_cost = 0
            combo_kind = ''
            if combo_attack:
                combo_cost = int(combo_attack.energy)
                base = (f['grounded'] and not f['knocked'] and f['stun'] <= 0
                        and f['energy'] >= combo_cost)
                if combo_trigger == 'shield':
                    # 晚高峰警告：S S 之后按防御键 L。
                    combo_ready = base and ('guard' in presses) and buffer.double_down()
                    combo_kind = 'shield_buff'
                elif combo_trigger == 'vapor':
                    # 气化冷冻法：A/D + L L。要冷却空闲，是因为 double_press 在
                    # 双按后的 6 帧内一直为真，不挡住会连发。
                    combo_ready = (base and f['cooldown'] <= 0 and not f['attack_kind'] and
                                   buffer.direction_tap() and
                                   buffer.double_press('guard'))
                    combo_kind = 'vapor_freeze'
                else:
                    # 冰千年杀：S S + 移动键 + J。
                    combo_ready = (base and punch_now
                                   and buffer.double_down() and buffer.direction_tap())
                    combo_kind = 'ice_shadow'
            if owner_stopped:
                # 时停期间除瞬发拳外，所有常规出招 / 专属连招 / 大招指令无效。
                kind = ''
                combo_ready = False
                buff_press = False
            if combo_ready and not super_ready:
                kind = combo_kind
            elif buff_press:
                kind = 'lightning_strike' if spell else 'flame_buff'
            # 场上已有自己发出的飞行道具时不能再发射第二个（同一时间只允许一发）。
            if kind in ('projectile', 'crouch_projectile') and any(
                    p['owner'] == i for p in self.projectiles):
                kind = ''
            cancel_ready = (bool(kind) and f['attack_kind'] and f['stun'] <= 0
                            and not f['knocked']
                            and f['cancel_chain'] < MAX_CANCEL_CHAIN
                            and (f['cancel_left'] > 0 or
                                 (f['air_cancel_left'] > 0 and not f['grounded']
                                  and kind in AIR_CANCEL_KINDS)))
            started = False
            if cancel_ready:
                started = self._start_attack(i, kind, events, cancel=True)
                if started or buff_press:
                    buffer.consume()
                    buffer.consume_buttons(self._kind_buttons(kind))
                    self._clear_queue(f)
            if not started:
                if kind and kind != 'laser' and not free and f['stun'] <= 0 and not f['knocked']:
                    # 引导招式不缓存：松手后再放一次会很别扭，等玩家重新按下。
                    self._queue_attack(f, kind)
                    buffer.consume_buttons(self._kind_buttons(kind))
                elif free:
                    if kind:
                        began = self._start_attack(i, kind, events)
                        if began or buff_press:
                            buffer.consume()
                        buffer.consume_buttons(self._kind_buttons(kind))
                        # 新按下的键优先出招，之前排队的预输入让位。
                        self._clear_queue(f)
                    elif f['queued_attack']:
                        queued = f['queued_attack']
                        if queued != 'super' or f['grounded']:
                            self._start_attack(i, queued, events)
                            # 队首已经接上，换成下一条预输入。
                            self._pop_queue(f)
                        else:
                            self._clear_queue(f)
            if buffered and not kind:
                # 缓冲里的按键本帧已经评估过；没能组成招式就作废，避免反复触发。
                buffer.consume_buttons(buffered)
            # --- Dash: double tap forward / back (KOF style) ---
            if (f['stun'] <= 0 and not f['attack_kind'] and f['grounded'] and
                    f['dash_time'] <= 0 and f['cooldown'] <= 0 and not f['knocked']):
                if self.buffers[i].double_tap('forward'):
                    f['dash_time'], f['dash_dir'] = DASH_FRAMES * TICK, f['face']
                    events.append(self._event('dash', i, direction='forward'))
                elif self.buffers[i].double_tap('back'):
                    f['dash_time'], f['dash_dir'] = BACKDASH_FRAMES * TICK, -f['face']
                    events.append(self._event('dash', i, direction='back'))
            if f['dash_time'] > 0:
                if f['stun'] <= 0 and not f['attack_kind'] and not f['knocked']:
                    f['x'] = max(ARENA_LEFT, min(ARENA_RIGHT,
                                f['x'] + f['dash_dir'] * f.get('dash_speed', DASH_SPEED)
                                * speed_mult * TICK))
                    f['walk'] += .55
                f['dash_time'] = max(0., f['dash_time'] - TICK)
            elif (f['stun'] <= 0 and not f['attack_kind'] and not f['knocked']
                    and move and not k.get('down')):
                f['x'] = max(ARENA_LEFT, min(ARENA_RIGHT,
                            f['x'] + move * f.get('move_speed', MOVE_SPEED)
                            * speed_mult * TICK))
                f['walk'] += .21
            if f['knocked']:
                f['action'] = 'downed'
            elif f['stun'] > 0:
                f['action'] = 'hurt'
            elif f['attack_kind']:
                # 霸体冲锋摔地后的收招：自己也倒地但立即起身，视觉用 downed。
                if f['attack_kind'] == 'tackle' and f.get('tackle_downed'):
                    f['action'] = 'downed'
                else:
                    f['action'] = f['attack_kind']
            elif f['time_punch_anim'] > 0:
                # 时停瞬发拳：只播放普通拳的姿势，不进攻击状态机、不吃前后摇，
                # 所以连续狂按 J 时每一下都能立刻再出拳。把剩余帧数换算成普通
                # 拳的动作帧（0→前摇、中段→命中、末段→收招），做出一记快拳。
                spec = ATTACKS['punch']
                span = TIME_STOP_PUNCH_ANIM
                elapsed = span - f['time_punch_anim']
                f['action_frame'] = int(elapsed * (spec.total - 1) / max(1, span - 1))
                f['action'] = 'punch'
                f['time_punch_anim'] -= 1
            elif f['y'] > 0:
                f['action'] = 'jump'
            elif f['dash_time'] > 0:
                f['action'] = 'run'
            elif k.get('down') and k.get('guard'):
                f['action'] = 'crouch_guard'
            elif k.get('down'):
                f['action'] = 'crouch'
            elif k.get('guard'):
                f['action'] = 'guard'
            elif move:
                f['action'] = 'run'
            else:
                f['action'] = 'idle'
            # The cancel window ticks down after the input phase, so a hit
            # grants its full number of frames on the following ticks.
            f['cancel_left'] = max(0, f['cancel_left'] - 1)
            f['air_cancel_left'] = max(0, f['air_cancel_left'] - 1)
        a,b = self.fighters
        # 时停期间不做互相挤开：否则会被定格的敌人会被推走，破坏"定格"。
        if (self.time_stop <= 0 and abs(a['x']-b['x']) < 48
                and abs(a['y']-b['y']) < 75):
            middle = (a['x']+b['x'])/2
            if a['x'] <= b['x']:
                a['x'],b['x'] = max(ARENA_LEFT,middle-24),min(ARENA_RIGHT,middle+24)
            else:
                a['x'],b['x'] = min(ARENA_RIGHT,middle+24),max(ARENA_LEFT,middle-24)
        # --- Projectile movement & collision ---
        # 时停：投射物 / 落雷一并定格，原样保留（时间停止了）。
        frozen_world = self.time_stop > 0
        alive = list(self.projectiles) if frozen_world else []
        for proj in (() if frozen_world else self.projectiles):
            proj["lifetime"] -= TICK
            proj["x"] += proj["vx"] * TICK
            proj["angle"] = proj.get("angle", 0.0) + proj.get("spin", 0.0) * TICK
            if proj["lifetime"] <= 0 or proj.get("hit"):
                continue
            opponent = self.fighters[1 - proj["owner"]]
            if opponent['knocked'] or opponent['invuln'] > 0:
                # A downed or just-risen fighter is untouchable; shots fly over.
                alive.append(proj)
                continue
            if (opponent['attack_kind'] == 'ice_shadow' and shadow_phase(opponent) == 'hide'):
                # 潜行中的敌人同样不可被投射物命中。
                alive.append(proj)
                continue
            attack = proj.get("attack", "projectile")
            carrier = proj.get("style") == "carrier"
            low, high = body_span(opponent)
            radius = proj.get("size", 7)
            # High shots sail over a crouching fighter (Mortal Kombat rule);
            # 推人墙是半人高实体，蹲防照样被推，所以不走这条豁免。
            if (attack in ("projectile", "ice_beam") and not carrier
                    and crouching(opponent) and opponent["grounded"]):
                alive.append(proj)
                continue
            # Body-box test: the shot connects anywhere between the feet and the
            # top of the head (head hits count the same as body hits).
            if (abs(proj["x"] - opponent["x"]) <= BODY_HALF_WIDTH + radius and
                    low - radius <= proj["y"] <= high + radius):
                defending = (guard_blocks(opponent["action"], attack) and
                             opponent["face"] == -self.fighters[proj["owner"]]["face"])
                owner = self.fighters[proj["owner"]]
                if carrier:
                    # 推人墙：不消失，推着敌人前行，每 tick_interval 结算一段伤害。
                    face = 1 if proj["vx"] >= 0 else -1
                    front_edge = proj["x"] + face * (BODY_HALF_WIDTH + radius)
                    if face > 0 and opponent["x"] < front_edge:
                        opponent["x"] = min(ARENA_RIGHT, front_edge)
                    elif face < 0 and opponent["x"] > front_edge:
                        opponent["x"] = max(ARENA_LEFT, front_edge)
                    proj["tick_cd"] = proj.get("tick_cd", 0.) - TICK
                    if proj["tick_cd"] <= 0:
                        proj["tick_cd"] = proj.get("tick_interval", 0.25)
                        dmg = max(1, proj["damage"] // 5) if defending else proj["damage"]
                        hp_dmg = apply_damage(opponent, dmg)
                        opponent["flash"] = .15
                        if not has_armor(opponent):
                            opponent["stun"] = max(opponent["stun"],
                                                   (8 if defending else 14) * TICK)
                            if not defending:
                                opponent["attack_kind"] = ""
                            self._build_stagger(1 - proj["owner"],
                                (8 if defending else 14) * (.25 if defending else 1.),
                                events)
                        if hp_dmg > 0:
                            gain_energy(owner, 4)
                            gain_energy(opponent, 2)
                        events.append(self._event("hit", proj["owner"],
                            target=1 - proj["owner"], attack="carrier",
                            damage=dmg, blocked=defending))
                        self._apply_hitstop("carrier", defending)
                    # 撞墙终结：被推到场地边缘时追加伤害并短暂倒地。
                    at_wall = (opponent["x"] <= ARENA_LEFT + 1 or
                               opponent["x"] >= ARENA_RIGHT - 1)
                    if at_wall and not proj.get("wall_done"):
                        proj["wall_done"] = True
                        apply_damage(opponent, proj.get("wall_damage", 8))
                        self._knock_down(1 - proj["owner"], events,
                                         duration=proj.get("wall_knockdown", 0.8),
                                         style='flat')
                    if ARENA_LEFT <= proj["x"] <= ARENA_RIGHT:
                        alive.append(proj)
                else:
                    dmg = max(1, proj["damage"] // 5) if defending else proj["damage"]
                    hp_dmg = apply_damage(opponent, dmg)
                    opponent["flash"] = .15
                    if not has_armor(opponent):
                        opponent["stun"] = max(opponent["stun"], (8 if defending else 14) * TICK)
                        if not defending:
                            opponent["attack_kind"] = ""
                        self._build_stagger(1 - proj["owner"],
                                            (8 if defending else 14) * (.25 if defending else 1.),
                                            events)
                    if attack == "ice_beam" and not defending and opponent['frozen'] <= 0:
                        # 命中即冻结；已经冻住的人不会被续冻，否则冰束可以一直
                        # 把 1.5 秒的冻结续下去，变成永久锁血。
                        self._freeze_fighter(1 - proj["owner"], opponent, events,
                                             opponent["x"], duration=VAPOR_FREEZE,
                                             kind='vapor')
                    if hp_dmg > 0:
                        gain_energy(owner, VAPOR_REFUND if attack == "ice_beam"
                                    else PROJECTILE_ENERGY_GAIN)
                        gain_energy(opponent, PROJECTILE_DAMAGE_ENERGY_GAIN)
                    proj["hit"] = True
                    events.append(self._event("hit", proj["owner"],
                        target=1 - proj["owner"], attack=attack,
                        damage=dmg, blocked=defending))
                    self._apply_hitstop(attack, defending)
            elif ARENA_LEFT <= proj["x"] <= ARENA_RIGHT:
                alive.append(proj)
        self.projectiles = alive
        # --- Delayed lightning strikes (warning ring, then the falling bolt) ---
        strikes = list(self.strikes) if frozen_world else []
        for strike in (() if frozen_world else self.strikes):
            victim = self.fighters[1 - strike['owner']]
            if strike['hit']:
                # Keep the bolt on screen for a short flash after the impact.
                strike['life'] -= TICK
                if strike['life'] > 0:
                    strikes.append(strike)
                continue
            if strike['delay'] > 0:
                strike['delay'] = max(0., strike['delay'] - TICK)
                strikes.append(strike)
                continue
            if strike['air']:
                # The follow-up bolt chases the airborne victim downward.
                strike['target_y'] = max(0., victim['y'])
            strike['y'] -= strike['speed'] * TICK
            if strike['y'] <= strike['target_y']:
                strike['y'] = strike['target_y']
                strike['hit'] = True
                strike['life'] = .14
                self._resolve_strike(strike, victim, events)
            strikes.append(strike)
        self.strikes = strikes
        # --- Melee hit detection ---
        hits = []
        for i,f in enumerate(self.fighters):
            if self.time_stop > 0 and i != self.time_stop_owner:
                # 定格的敌人不能继续结算自己没打完的招式。
                continue
            kind = f['attack_kind']
            if not kind or kind in ('projectile', 'flame_buff', 'lightning_strike', 'ice_shadow', 'shield_buff', 'vapor_freeze', 'laser'): continue
            if kind == 'tackle':
                continue  # 霸体冲锋由 _tick_tackle_super 自行结算命中
            if kind == 'super' and f.get('super_kind') in ('grab_pummel', 'time_stop'):
                # 抓取乱打 / 砸瓦鲁多都自带状态机；时停本身没有伤害判定。
                continue
            spec = attack_spec(f, kind)
            if not (spec.startup <= f['action_frame'] < spec.startup+spec.active): continue
            multi = spec.hits > 1
            if multi:
                # Multi-hit super: one cut per cadence slot, no single-hit lockout.
                if (f['action_frame'] - spec.startup) % max(1, spec.hit_interval): continue
                if f.get('hit_count', 0) >= spec.hits: continue
            elif f['attack_hit']:
                continue
            victim = self.fighters[1-i]
            if victim['knocked'] or victim['invuln'] > 0:
                # Floored fighters are immune until they get up; rising
                # fighters keep a short wake-up invulnerability window.
                continue
            if (victim['attack_kind'] == 'ice_shadow' and shadow_phase(victim) == 'hide'):
                continue  # 潜行中的敌人不可被命中
            distance = (victim['x']-f['x'])*f['face']
            # A grab on a freshly grabbed opponent would allow an endless loop;
            # ordinary short hit-stun does not block a follow-up grab.
            if kind == 'grab' and victim['stun'] > 0.5:
                continue
            area = f.get('super_radius', 0.)
            if kind == 'super' and area:
                # Radial super: hits both sides around the body, not just in front.
                connects = (abs(victim['x'] - f['x']) <= area and
                            abs(victim['y'] - f['y']) <= spec.hit_height)
            else:
                connects = (0 <= distance <= spec.reach and
                            abs(victim['y']-f['y']) <= spec.hit_height)
            if connects:
                if multi:
                    f['hit_count'] = f.get('hit_count', 0) + 1
                else:
                    f['attack_hit'] = True
                hits.append((i,1-i,kind,spec))
        for source,target,kind,spec in hits:
            victim = self.fighters[target]
            defending = (guard_blocks(victim['action'], kind) and
                         victim['face'] == -self.fighters[source]['face'])
            base = spec.damage // spec.hits if spec.hits > 1 else spec.damage
            attacker = self.fighters[source]
            # Later hits in the same combo are worth less and push further.
            combo_index = (attacker['combo']
                           if self.frame - attacker['last_hit_frame'] < COMBO_WINDOW else 0)
            if defending:
                damage = max(1, base // 5)
            elif kind == 'super':
                # Supers keep their authored damage; the multi-hit slices are
                # already tuned per character.
                damage = base
            else:
                damage = max(1, int(base * COMBO_SCALING[
                    min(combo_index, len(COMBO_SCALING) - 1)]))
            if spec.cancel:
                # Connecting, even on guard, opens the recovery-cancel window.
                attacker['cancel_left'] = spec.cancel
            bonus = 0
            finisher = ''
            if attacker.get('buff_charges', 0) > 0:
                # Flame buff: the next three connecting attacks burn for extra.
                buff = attacker.get('buff_spec') or {}
                bonus = int(buff.get('bonus', 0))
                attacker['buff_charges'] -= 1
                damage += bonus
                if attacker['buff_charges'] <= 0 and buff.get('finisher_projectile'):
                    # The final charged hit throws one shot in the attack direction.
                    finisher = 'crouch_projectile' if kind in CROUCH_ATTACKS else 'projectile'
            shatter = (not defending and victim['frozen'] > 0.
                       and victim.get('frozen_kind') == 'vapor')
            if shatter:
                # 冻脆的身体：冻结中挨到的第一记干净命中额外吃下碎裂伤害。
                # 这 30 点是用剩余冻结时间换来的——碎冰后硬直会回落。
                damage += VAPOR_SHATTER_BONUS
            hp_dmg = apply_damage(victim, damage)
            victim['flash'] = .15
            armored = has_armor(victim)
            radial = kind == 'super' and self.fighters[source].get('super_radius', 0.)
            if not armored:
                stun_frames = spec.block_stun if defending else spec.stun
                # Later hits of a clean combo hold the victim for less time
                # (3rd hit onward scales with COMBO_SCALING), so cancel strings
                # cannot lock the opponent in permanent hit-stun. Supers keep
                # their authored hold (their follow-up sequences depend on it),
                # and grab must stay above the 0.5 s anti-loop threshold.
                if not defending and kind not in ('super', 'grab') and combo_index >= 2:
                    stun_frames = max(1., stun_frames * COMBO_SCALING[
                        min(combo_index, len(COMBO_SCALING) - 1)])
                victim['stun'] = max(victim['stun'], stun_frames * TICK)
                if shatter:
                    # 碎冰：冻结的硬直立刻回落到这一击自己的受击帧数。
                    victim['stun'] = stun_frames * TICK
                if not defending:
                    victim['attack_kind'] = ''
                    # Getting hit ends the victim's own cancel chain as well.
                    victim['cancel_chain'] = 0
                    push_dir = self.fighters[source]['face']
                    if radial:
                        # A radial blast knocks the victim away from the caster.
                        push_dir = 1 if victim['x'] >= self.fighters[source]['x'] else -1
                    push = spec.push * (1. + PUSH_GROWTH * min(combo_index, 4))
                    victim['x'] = max(ARENA_LEFT,min(ARENA_RIGHT,victim['x']+push_dir*push))
                    if spec.launch: victim['vy'] = spec.launch
                    if kind == 'super' and attacker.get('super_bolt'):
                        # Launch supers follow the airborne victim with an extra bolt.
                        self._spawn_strike(source, victim['x'], attacker['super_bolt'], events)
                if radial:
                    self._knock_down(target, events)
                elif kind == 'super' and spec.launch:
                    # A launch super keeps the victim in the air; flooring them
                    # would eat the follow-up bolt.
                    pass
                else:
                    self._build_stagger(
                        target, (spec.block_stun * .25) if defending else spec.stun, events)
            if shatter:
                # 冰壳被这一击打碎：视觉上的冰层消失，冻结状态彻底结束。
                victim['frozen'] = 0.
                victim['frozen_kind'] = ''
                events.append(self._event('vapor_shatter', source, target=target))
            # Supers do not build meter on hit; being hit always does.
            if kind != 'super' and hp_dmg > 0:
                gain_energy(self.fighters[source], HIT_ENERGY_GAIN)
            if hp_dmg > 0:
                gain_energy(victim, DAMAGE_ENERGY_GAIN)
            if defending:
                # Guarding is not a combo: a blocked hit ends the string instead
                # of extending it, so the next clean hit starts at full damage.
                attacker['combo'] = 0
                # Guard pushback: the blocker braces and shoves the attacker
                # back a step, so guarding buys space and melee spam cannot
                # stay glued inside its own reach. (Projectiles resolve in
                # their own collision path and never shove the shooter.)
                back = GUARD_PUSHBACK if attacker['face'] >= 0 else -GUARD_PUSHBACK
                attacker['x'] = max(ARENA_LEFT,
                                    min(ARENA_RIGHT, attacker['x'] - back))
            else:
                attacker['combo'] = combo_index + 1
                attacker['last_hit_frame'] = self.frame
            events.append(self._event('hit',source,target=target,attack=kind,
                                      damage=damage,blocked=defending,bonus=bonus))
            self._apply_hitstop(kind, defending)
            if finisher:
                self._spawn_projectile(source, finisher, events)
            # 记录本回合最后一次命中的招式，供 finish_round 选择败者倒地姿势。
            self.last_hit_kind = kind
        # 技能训练：hp 归零的角色在初始位置重生，不触发回合结束与比分变化。
        if self.training_mode:
            for idx, f in enumerate(self.fighters):
                if f['hp'] <= 0:
                    f['hp'] = f['hp_max']
                    f['x'] = 210. if idx == 0 else 810.
                    f['y'], f['vy'] = 0., 0.
                    f['knocked'] = False
                    f['stun'] = 0.
                    f['stagger'] = 0.
                    f['action'] = 'idle'
                    f['action_frame'] = 0
                    f['action_time'] = 0.
                    f['attack_kind'] = ''
                    f['attack_hit'] = False
                    f['proj_spawned'] = False
                    f['dash_time'] = 0.
                    f['cancel_left'] = 0
                    f['cancel_chain'] = 0
                    f['combo'] = 0
                    f['invuln'] = 0.
                    f['flash'] = .2
                    events.append(self._event('training_respawn', idx))
            return events
        if a['hp'] <= 0 or b['hp'] <= 0 or self.time_left <= 0:
            winner = 0 if a['hp'] > b['hp'] else 1 if b['hp'] > a['hp'] else None
            self.finish_round(winner)
            events.append(self._event('round_end',winner if winner is not None else -1))
            if self.phase == 'match_end': events.append(self._event('match_end',self.winner))
        return events