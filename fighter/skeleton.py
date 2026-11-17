"""Pure-math procedural skeleton: shared anatomy; cosmetic decorations in renderer."""
import math
from .characters import CHARACTERS as CHAR_DATA
from .attacks import ATTACKS

BONES = ('head', 'neck', 'shoulder', 'hip', 'rear_elbow', 'rear_hand',
         'front_elbow', 'front_hand', 'rear_knee', 'rear_foot', 'front_knee', 'front_foot')

def _ease_out(t):
    t = max(0., min(1., t))
    return 1 - (1 - t) ** 3

def _blend(a, b, t):
    return {k: (a[k][0]*(1-t)+b[k][0]*t, a[k][1]*(1-t)+b[k][1]*t) for k in a}

def _attack_target(action, base, punch_side=0):
    """Final pose of an attack; the renderer blends toward it over the frame data."""
    p = dict(base)
    if action == 'punch':
        if punch_side:
            # 时停连打：这一拳由后手（画在躯干后面的那条手臂）挥出，前手收回
            # 护在胸前，连按时前后手交替，做出原著里那串连打。
            p['rear_elbow'], p['rear_hand'] = (36, 98), (71, 98)
            p['front_elbow'], p['front_hand'] = (22, 84), (14, 110)
        else:
            p['front_elbow'], p['front_hand'] = (42, 101), (70, 101)
    elif action == 'jump_punch':
        p['front_elbow'], p['front_hand'] = (38, 95), (75, 85)
    elif action == 'projectile':
        p['front_elbow'], p['front_hand'] = (38, 108), (78, 92)
    elif action == 'crouch_projectile':
        p['front_elbow'], p['front_hand'] = (38, 78), (78, 66)
    elif action == 'crouch_punch':
        p['front_elbow'], p['front_hand'] = (36, 63), (70, 59)
        p['rear_hand'] = (-14, 82)
    elif action == 'grab':
        p['front_elbow'], p['front_hand'] = (36, 96), (72, 100)
        p['rear_elbow'], p['rear_hand'] = (28, 94), (60, 102)
    elif action == 'low_kick':
        p['front_knee'], p['front_foot'] = (60, 18), (100, 22)
        p['front_hand'], p['rear_hand'] = (18, 90), (-12, 92)
    elif action == 'kick':
        p['front_knee'], p['front_foot'] = (52, 70), (88, 75)
        p['front_hand'] = (27, 115)
    elif action == 'super':
        p['front_elbow'], p['front_hand'] = (44, 104), (96, 98)
        p['rear_elbow'], p['rear_hand'] = (18, 100), (66, 92)
        p['shoulder'] = (6, p['shoulder'][1])
        p['hip'] = (4, p['hip'][1])
        p['rear_knee'], p['rear_foot'] = (-24, 30), (-38, 4)
        p['front_knee'], p['front_foot'] = (24, 30), (38, 4)
    elif action == 'flame_buff':
        # Both fists pulled up in front of the chest while the flames take hold.
        p['front_elbow'], p['front_hand'] = (40, 96), (58, 122)
        p['rear_elbow'], p['rear_hand'] = (-30, 96), (-12, 122)
        p['shoulder'] = (2, p['shoulder'][1])
    elif action == 'lightning_strike':
        # Both hands thrown skyward to call the bolt down.
        p['front_elbow'], p['front_hand'] = (26, 118), (18, 162)
        p['rear_elbow'], p['rear_hand'] = (-26, 118), (-18, 162)
        p['shoulder'] = (0, p['shoulder'][1])
    elif action == 'tackle':
        # 霸体冲锋：身体前倾，前手抬到对方脖子的高度准备勾脖。
        p['front_elbow'], p['front_hand'] = (50, 104), (72, 116)
        p['rear_elbow'], p['rear_hand'] = (-18, 90), (-30, 100)
        p['shoulder'] = (8, p['shoulder'][1] - 4)
        p['hip'] = (6, p['hip'][1])
        p['rear_knee'], p['rear_foot'] = (-26, 22), (-40, 0)
        p['front_knee'], p['front_foot'] = (30, 26), (44, 2)
    elif action == 'shield_buff':
        # 晚高峰警告：双臂护在身前，蓄起护盾。
        p['front_elbow'], p['front_hand'] = (24, 104), (14, 130)
        p['rear_elbow'], p['rear_hand'] = (-24, 104), (-14, 130)
        p['shoulder'] = (0, p['shoulder'][1])
    return p

def pose(action, action_frame=0, walk=0, face=1, attack=None, downed_style='curl',
         crouch=False, punch_side=0):
    sway = math.sin(walk) * 12 if action == 'run' else 0
    bob = math.sin(walk * .65) * 2 if action in ('idle', 'run') else 0
    p = {'head': (0, 142+bob), 'neck': (0, 112+bob), 'shoulder': (0, 100+bob),
         'hip': (0, 57+bob), 'rear_elbow': (-23, 85), 'rear_hand': (-12, 111),
         'front_elbow': (24, 85), 'front_hand': (33, 105),
         'rear_knee': (-18+sway, 32), 'rear_foot': (-25+sway, 4),
         'front_knee': (18-sway, 31), 'front_foot': (27-sway, 4)}
    # Keep every crouch state on the same low base pose so attacks never pop
    # back to standing during recovery while S is still held.
    if action in ('crouch', 'crouch_guard', 'crouch_punch', 'crouch_projectile', 'low_kick'):
        for key, (x, y) in list(p.items()): p[key] = (x, y*.68)
    # 石面鬼之眼：引导时双臂张开下垂、头微微后仰，双眼射出激光。
    if action == 'laser':
        p['front_elbow'], p['front_hand'] = (30, 74), (44, 52)
        p['rear_elbow'], p['rear_hand'] = (-30, 74), (-44, 52)
        p['head'] = (0, 145)
        if crouch:
            # 蹲着也能放激光：整套姿势压到和蹲下同一高度。
            for key, (x, y) in list(p.items()): p[key] = (x, y*.68)
    spec = attack or ATTACKS.get(action)
    if spec:
        frame = action_frame
        if frame < spec.startup:
            blend = _ease_out((frame + 1) / max(1, spec.startup)) * .92
        elif frame < spec.startup + spec.active:
            blend = 1.0
        else:
            done = frame - spec.startup - spec.active
            blend = 1.0 - _ease_out((done + 1) / max(1, spec.recovery))
        p = _blend(p, _attack_target(action, p, punch_side), max(0., blend))
    elif action == 'jump':
        p['rear_knee'], p['rear_foot'] = (-32, 28), (-12, 20)
        p['front_knee'], p['front_foot'] = (32, 30), (24, 15)
    elif action == 'crouch':
        pass
    elif action == 'hurt':
        p['head'], p['neck'] = (-15, 139), (-9, 107)
        p['front_hand'], p['rear_hand'] = (-16, 92), (-28, 96)
    elif action == 'downed':
        if downed_style == 'flat':
            # 平躺：仰面朝天，四肢摊开。
            p = {'head': (54, 12), 'neck': (36, 14), 'shoulder': (26, 16), 'hip': (-18, 14),
                 'rear_elbow': (10, 26), 'rear_hand': (28, 34),
                 'front_elbow': (36, 30), 'front_hand': (52, 38),
                 'rear_knee': (-42, 20), 'rear_foot': (-58, 8),
                 'front_knee': (-32, 26), 'front_foot': (-52, 6)}
        elif downed_style == 'prone':
            # 趴着：面朝下，头微微抬起。
            p = {'head': (50, 26), 'neck': (34, 20), 'shoulder': (24, 18), 'hip': (-16, 14),
                 'rear_elbow': (-2, 30), 'rear_hand': (16, 34),
                 'front_elbow': (26, 32), 'front_hand': (42, 36),
                 'rear_knee': (-38, 24), 'rear_foot': (-56, 6),
                 'front_knee': (-28, 28), 'front_foot': (-46, 8)}
        elif downed_style == 'kneel':
            # 跪着：单膝撑地，正准备起身。
            p = {'head': (6, 118), 'neck': (3, 100), 'shoulder': (0, 96), 'hip': (-2, 54),
                 'rear_elbow': (-14, 82), 'rear_hand': (-20, 62),
                 'front_elbow': (16, 84), 'front_hand': (24, 64),
                 'rear_knee': (-14, 8), 'rear_foot': (-36, 10),
                 'front_knee': (18, 36), 'front_foot': (30, 2)}
        else:
            # 缩着（默认）：抱头蜷缩。
            p = {'head': (42, 30), 'neck': (28, 26), 'shoulder': (20, 24), 'hip': (-6, 16),
                 'rear_elbow': (-22, 30), 'rear_hand': (-40, 38),
                 'front_elbow': (2, 36), 'front_hand': (14, 42),
                 'rear_knee': (-30, 28), 'rear_foot': (-50, 12),
                 'front_knee': (-10, 32), 'front_foot': (10, 38)}
    elif action in ('guard', 'crouch_guard'):
        scale = .68 if action == 'crouch_guard' else 1.
        p['front_elbow'], p['front_hand'] = (26, 107*scale), (21, 143*scale)
    return {name: (face*x, y) for name, (x,y) in p.items()}

def _dim(color, factor):
    return tuple(max(0, min(255, int(v * factor))) for v in color)

def _draw_cape(pygame, screen, pts, accent, face, walk, action, fighter):
    """Flowing cape: a fanned, tapered cloth painted under the limbs."""
    back = -face
    nx, ny = pts['neck']
    sx, sy = pts['shoulder']
    air = min(1., fighter.get('y', 0) / 160.)
    flare = 1. + air * .8 + (1. if action == 'super' else 0.)
    wave = math.sin(walk * 2.2) * 6
    base = (nx + back * 5, ny + 5)
    for spread, droop in ((-14, 10), (0, 0), (14, 18)):
        tip = (base[0] + back * int(30 * flare) + spread,
               ny + int(52 * flare) + droop + int(wave))
        mid = ((base[0] + tip[0]) // 2 + back * 3, (base[1] + tip[1]) // 2)
        pygame.draw.lines(screen, _dim(accent, .42), False, [base, mid, tip], 8)
        pygame.draw.lines(screen, accent, False,
                          [base, mid, (tip[0] + 2, tip[1] - 2)], 3)
    # high collar bridging the shoulder line
    pygame.draw.line(screen, _dim(accent, .85), (sx, sy - 2), (nx, ny + 2), 6)

def draw(pygame, screen, fighter, index, ground, offset=38):
    char_id = fighter.get('char_id', 'red_scarf')
    style = CHAR_DATA.get(char_id, CHAR_DATA['red_scarf'])
    accent = style['accent']
    face = fighter.get('face', 1)
    action = fighter.get('action', 'idle')
    frame = fighter.get('action_frame', 0)
    walk = fighter.get('walk', 0)
    # 受击闪白：把颜色往白里提亮，但保留服装自身的色相。若像以前那样在闪白
    # 期间直接丢掉 outfit 配色，穿整套黄衣的迪奥会整只变成纯白剪影。
    flash_amt = min(1., max(0., float(fighter.get('flash', 0)) / .15)) * .5
    def _lit(color):
        return tuple(int(c + (255 - c) * flash_amt) for c in color)
    base_body = (231, 238, 249)
    # 服装分色：角色可为躯干 / 手臂 / 腿部各写一个颜色（如迪奥的黄外套与
    # 黄裤子），未写时沿用默认身体色。
    outfit = style.get('outfit') or {}
    body = _lit(base_body)
    torso_color = _lit(outfit.get('torso', base_body))
    arms_color = _lit(outfit.get('arms', base_body))
    legs_color = _lit(outfit.get('legs', base_body))
    eye_color = style.get('eye_color', accent)
    outline = (46, 58, 80)
    x, y = offset + int(fighter['x']), ground - int(fighter.get('y', 0))
    pose_attack = None
    if action == 'super':
        pose_attack = fighter.get('super_spec')
    elif action == 'tackle':
        pose_attack = fighter.get('super_spec')
    elif action in ('ice_shadow', 'shield_buff'):
        pose_attack = fighter.get('combo_attack')
    # 时停连打的交替出拳：只有瞬发拳的纯视觉动画期间才换手（此时不进攻击
    # 状态机，attack_kind 为空），普通拳不变。
    punch_side = (int(fighter.get('time_punch_side', 0))
                  if action == 'punch' and not fighter.get('attack_kind') else 0)
    p = pose(action, frame, walk, face, pose_attack,
             fighter.get('downed_style', 'curl'),
             crouch=bool(fighter.get('laser_low')), punch_side=punch_side)
    # 借过一下抛物线：勾住后双方腾空的高度，纯视觉偏移，u 为 0→1 进度。
    lift, u, vis = 0., 0., fighter.get('tackle_visual')
    if vis:
        u = max(0., min(1., vis['t'] / max(vis['span'], 1e-6)))
        lift = vis['lift_peak'] * 4 * u * (1 - u)
    pts = {key: (int(x + v[0]), int(y - v[1] - lift)) for key, v in p.items()}

    # ---- ground shadow (shrinks while airborne) ----
    crouched = action in ('crouch', 'crouch_guard', 'crouch_punch',
                          'crouch_projectile', 'low_kick')
    shadow_w = 60 if crouched else 74
    shadow_w = int(shadow_w * (1 - min(.34, (fighter.get('y', 0) + lift) / 280.)))
    pygame.draw.ellipse(screen, (15, 24, 40),
                        (x - shadow_w // 2 - 7, ground - 7, shadow_w + 14, 14))
    pygame.draw.ellipse(screen, (8, 14, 25),
                        (x - shadow_w // 2, ground - 5, shadow_w, 10))
    # ---- 借过一下的抛物线轨迹：整条弧线 + 已走过位置的残影 ----
    if vis:
        arc = []
        for k in range(10):
            uk = k / 9
            h = vis['lift_peak'] * 4 * uk * (1 - uk)
            ax = x - int(vis['face'] * vis['carry'] * (u - uk))
            ay = y - int(h + 66)
            arc.append((ax, ay))
        # 整条抛物线（起点 → 落地点）用细线勾出来，运动路线一眼可见。
        pygame.draw.lines(screen, _dim(accent, .34), False, arc, 2)
        # 已经走过的路径点上渐隐残影；被勾住的一方点更大更亮。
        dot = 4 if vis.get('trail') else 3
        for k, (ax, ay) in enumerate(arc):
            if k / 9 >= u:
                break
            pygame.draw.circle(screen, _dim(accent, .6), (ax, ay), dot)
        # 当前位置的高亮。
        cur = arc[min(9, int(round(u * 9)))]
        pygame.draw.circle(screen, accent, cur, dot + 3, 2)

    # ---- super-ready aura (every super costs 100) ----
    if fighter.get('energy', 0) >= 100 and action != 'downed':
        pulse = .5 + .5 * math.sin(walk * 1.6 + index)
        aura = pygame.Rect(x - 36 - int(3 * pulse), y - 132,
                           72 + int(6 * pulse), 140)
        pygame.draw.ellipse(screen, _dim(accent, .52), aura, 2)
        pygame.draw.ellipse(screen, _dim(accent, .30), aura.inflate(14, 14), 1)
    # ---- 晚高峰警告护盾光环 ----
    if fighter.get('shield', 0) > 0:
        shield_color = (196, 160, 60)
        pulse = .5 + .5 * math.sin(walk * 3.0 + index)
        frac = fighter['shield'] / max(1, fighter.get('shield_max', 1))
        ring = pygame.Rect(x - 40, y - 140, 80, 150)
        pygame.draw.ellipse(screen, (*shield_color, max(30, int(90 * frac))),
                            ring.inflate(int(6 * pulse), int(6 * pulse)), 0)
        pygame.draw.ellipse(screen, _dim(shield_color, .9), ring, 3)
        pygame.draw.ellipse(screen, _dim(shield_color, .5),
                            ring.inflate(10, 10), 1)

    def limb(a, b, width, color):
        pygame.draw.line(screen, outline, pts[a], pts[b], width + 5)
        pygame.draw.line(screen, color, pts[a], pts[b], width)

    def joint(key, radius, color):
        pygame.draw.circle(screen, outline, pts[key], radius + 2)
        pygame.draw.circle(screen, color, pts[key], radius)

    # rear limbs sit behind the torso, slightly dimmer for depth
    if style['decor'] == 'cape':
        # The cape hangs behind the body, so it is painted before the limbs.
        _draw_cape(pygame, screen, pts, accent, face, walk, action, fighter)
    limb('hip', 'rear_knee', 7, _dim(legs_color, .84))
    limb('rear_knee', 'rear_foot', 6, _dim(legs_color, .84))
    limb('shoulder', 'rear_elbow', 6, _dim(arms_color, .84))
    limb('rear_elbow', 'rear_hand', 6, _dim(arms_color, .84))
    # torso with a faint accent sash
    pygame.draw.line(screen, outline, pts['neck'], pts['hip'], 20)
    pygame.draw.line(screen, torso_color, pts['neck'], pts['hip'], 14)
    pygame.draw.line(screen, _dim(accent, .72), pts['shoulder'], pts['hip'], 2)
    # front limbs
    limb('hip', 'front_knee', 8, legs_color)
    limb('front_knee', 'front_foot', 7, legs_color)
    limb('shoulder', 'front_elbow', 7, arms_color)
    limb('front_elbow', 'front_hand', 7, arms_color)
    for key, radius, color in (('rear_knee', 5, legs_color), ('front_knee', 6, legs_color),
                               ('rear_elbow', 4, arms_color), ('front_elbow', 5, arms_color)):
        joint(key, radius, _dim(color, .9))
    # accent gloves / boots
    for key in ('rear_hand', 'front_hand'):
        pygame.draw.circle(screen, _dim(accent, .85), pts[key], 4)
    for key in ('rear_foot', 'front_foot'):
        pygame.draw.circle(screen, _dim(accent, .8), pts[key], 5)

    # ---- flame fists while the red scarf buff is armed ----
    if fighter.get('buff_charges', 0) > 0:
        t = pygame.time.get_ticks() / 1000.
        for hand_index, key in enumerate(('front_hand', 'rear_hand')):
            hx, hy = pts[key]
            pulse = .5 + .5 * math.sin(t * 11 + hand_index * 2.3)
            pygame.draw.circle(screen, _dim(accent, .55),
                               (hx, hy), int(9 + 4 * pulse), 2)
            pygame.draw.circle(screen, (255, 224, 150), (hx, hy), 3)
            for k in range(3):
                sway = math.sin(t * 7 + k * 2 + hand_index) * 4
                base = (hx + (k - 1) * 5, hy - 3)
                tip = (hx + (k - 1) * 5 + sway, hy - 13 - 5 * pulse - abs(k - 1) * 3)
                pygame.draw.line(screen, accent, base, tip, 2)

    # ---- head ----
    hx, hy = pts['head']
    pygame.draw.circle(screen, (17, 25, 40), (hx, hy), 23)
    pygame.draw.circle(screen, body, (hx, hy), 24, 5)
    ex, ey = hx + face * 9, hy - 3
    pygame.draw.circle(screen, eye_color, (ex, ey), 4)
    pygame.draw.circle(screen, (255, 255, 255), (ex - 1, ey - 1), 1)
    if fighter.get('attack_kind') == 'laser':
        # 引导激光时双眼亮成血红，光柱本体由 arena 绘制。
        glow = _dim((255, 70, 90), .9)
        pygame.draw.circle(screen, glow, (ex, ey), 8)
        pygame.draw.circle(screen, (255, 232, 236), (ex, ey), 3)
        pygame.draw.circle(screen, (255, 60, 70), (ex, ey), 8, 1)

    # ---- character decoration (flowing scarf / headband) ----
    back = -face
    if style['decor'] == 'scarf':
        nx, ny = pts['neck']
        wave = math.sin(walk * 2.0) * 4
        pygame.draw.line(screen, _dim(accent, .7), (nx - 17, ny + 8), (nx + 20, ny + 8), 9)
        pygame.draw.line(screen, accent, (nx - 17, ny + 8), (nx + 20, ny + 8), 6)
        pygame.draw.line(screen, accent,
                         (nx + back * 6, ny + 10), (nx + back * 28, ny + 22 + wave), 5)
        pygame.draw.line(screen, _dim(accent, .8),
                         (nx + back * 28, ny + 22 + wave),
                         (nx + back * 42, ny + 15 - wave), 3)
    elif style['decor'] == 'headband':
        pygame.draw.line(screen, accent, (hx - 23, hy - 7), (hx + 23, hy - 7), 7)
        pygame.draw.line(screen, (255, 255, 255), (hx - 19, hy - 8), (hx + 19, hy - 8), 1)
        wave = math.sin(walk * 2.4) * 3
        pygame.draw.line(screen, accent,
                         (hx + back * 20, hy - 7), (hx + back * 40, hy + 6 + wave), 4)
        pygame.draw.line(screen, _dim(accent, .8),
                         (hx + back * 40, hy + 6 + wave),
                         (hx + back * 52, hy - 2 - wave), 3)
    elif style['decor'] == 'tie':
        # 通勤打工人的领带：从颈口下垂，随步伐轻摆。
        nx, ny = pts['neck']
        sx, sy = pts['shoulder']
        swing = math.sin(walk * 2.1) * 3
        tie_color = (72, 76, 92)
        # 领结。
        pygame.draw.polygon(screen, tie_color,
                            [(nx - 6, ny + 2), (nx + 6, ny + 2),
                             (nx + 3, ny + 10), (nx - 3, ny + 10)])
        # 领带主体，向下收窄。
        tip_x = nx + int(swing)
        pygame.draw.polygon(screen, tie_color,
                            [(nx - 4, ny + 9), (nx + 4, ny + 9),
                             (tip_x + 2, ny + 44), (tip_x, ny + 50),
                             (tip_x - 2, ny + 44)])
        pygame.draw.line(screen, _dim(tie_color, .7),
                         (nx, ny + 10), (tip_x, ny + 48), 1)
        # 领口细边。
        pygame.draw.line(screen, _dim(accent, .6), (nx - 7, ny + 2), (nx + 7, ny + 2), 2)
    elif style['decor'] == 'dio_hair':
        # 迪奥的黄色竖发：头顶向后梳起的几束尖刺。
        hair = (255, 214, 64)
        sway = math.sin(walk * 1.8) * 1.5
        for dx, rise, lean in ((-19, 12, -4), (-10, 22, -1), (0, 27, 2),
                               (10, 21, 4), (19, 11, 6)):
            bx = hx + dx
            by = hy - 15 - max(0, 8 - abs(dx) * .4)
            tip = (int(hx + dx * 1.25 + back * lean + sway),
                   int(by - rise - (6 if abs(dx) < 12 else 0)))
            mid = ((bx + tip[0]) // 2 - back * 2, (by + tip[1]) // 2)
            pygame.draw.lines(screen, (46, 58, 80), False,
                              [(bx, by), mid, tip], 7)
            pygame.draw.lines(screen, hair, False, [(bx, by), mid, tip], 4)
        # 发根，把尖刺与头顶连成一体。
        pygame.draw.line(screen, hair, (hx - 20, hy - 12), (hx + 20, hy - 12), 7)

    # ---- attack cues ----
    attack_kind = fighter.get('attack_kind')
    if attack_kind:
        # Characters own their super timings, so the cue follows the real move.
        attack = (fighter.get('super_spec') if attack_kind == 'super'
                  else ATTACKS.get(attack_kind))
        if attack:
            end_key = 'front_foot' if 'kick' in attack.name else 'front_hand'
            if attack.startup <= frame < attack.startup + attack.active:
                end = pts[end_key]
                pygame.draw.circle(screen, accent, end, 17, 3)
                pygame.draw.circle(screen, _dim(accent, .7), end, 23, 1)
                pygame.draw.circle(screen, (255, 255, 255), end, 5)
            elif frame < attack.startup:
                prog = (frame + 1) / max(1, attack.startup)
                pygame.draw.circle(screen, _dim(accent, .75), pts[end_key],
                                   int(5 + 7 * prog), 2)
            if attack_kind == 'super':
                if frame < attack.startup:
                    prog = frame / max(1, attack.startup)
                    pygame.draw.circle(screen, accent, (x, y - 72), int(24 + 40 * prog), 3)
                elif fighter.get('super_kind') == 'grab_pummel':
                    # Grab super: the fist glows through the whole flurry.
                    pygame.draw.circle(screen, accent, pts['front_hand'], 24, 2)
                elif fighter.get('super_radius'):
                    # Radial super: show the blast area around the body.
                    pygame.draw.circle(screen, accent, (x, y - 72),
                                       int(fighter['super_radius']), 4)
                    pygame.draw.circle(screen, accent, (x, y - 72), 30, 2)
                else:
                    pygame.draw.circle(screen, accent, pts['front_hand'], 24, 2)
