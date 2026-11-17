"""Character definitions: visual style, stats, skills, super and signature combo.
Add new entries to CHARACTERS to extend the roster; the fight core reads the
loadout (health / projectile / super / combo) through Combat.set_loadout().
"""
from .attacks import Attack

CHARACTERS = {
    "red_scarf": {
        "id": "red_scarf",
        "name": "愤怒的普通人",
        "accent": (245, 95, 91),
        "decor": "scarf",
        "gender": "男",
        "identity": "烈焰拳师",
        "bio": "省下愤怒的时间去愤怒，愤怒越多，愤怒越少。",
        "health": 1000,
        "move_speed": 300,
        "projectile": {
            "name": "火焰弹",
            "damage": 14,
            "speed": 420,
            "lifetime": 0.8,
            "color": (255, 130, 60),
            "size": 8,
        },
        "skill_desc": "向前发射火焰弹",
        # Grab super: yank an opponent within double the old radius (300 px)
        # in front, punch them 4-10 times (more hits as the caster's health
        # drops), then throw them half an arena away and floor them.
        "super": Attack("拿来吧你", 400, 26, 120, 40, 54, 160, 0, 120,
                        energy=100, hits=10, hit_interval=7, block_stun=22),
        # Command super: tap S twice, then J and K. super_motion 是 AI 的搓招
        # 编排（plan token 序列，toward = 面向对手的双击方向键）。
        "super_command": "double_down",
        "super_motion": ["down", "gap", "down", "gap", "super"],
        # 专属连招（素质三连 S S U）的 AI 搓招编排，与 super_motion 同构，
        # cast = 弹幕键（buff_press 借按下沿触发）。
        "combo_motion": ["down", "gap", "down", "gap", "cast"],
        # 300 = 2x the old 150 px blast radius; used as the pull range now.
        "super_radius": 300,
        "super_kind": "grab_pummel",
        # AI 大招射程模式：radius = super_radius 圈内可命中（新角色默认即此）。
        "super_area_mode": "radius",
        # Half the 928 px arena.
        "super_throw": 464,
        "super_desc": "拉取300范围内的敌人，对敌人打出 4~10 段拳击后击飞",
        # S S U arms the fists: the next three attacks carry bonus damage, and
        # the last one also throws a projectile in the attack direction.
        "buff": {"name": "素质三连", "bonus": 50, "charges": 3,
                 "energy": 25, "finisher_projectile": True},
        "combo": {
            "name": "素质三连",
            "steps": ("S", "S", "U"),
            "note": "释放后下三次攻击附带额外 50 伤害，第三次追加一发远程攻击",
        },
        "combo_desc": "点燃双拳，三击强化，第三击追加火焰弹",
    },
    "blue_headband": {
        "id": "blue_headband",
        "name": "冷静的普通人",
        "accent": (80, 182, 247),
        "decor": "headband",
        "gender": "男",
        "identity": "寒霜游侠",
        "bio": "人非圣贤，要心如止水，就得先打！",
        "health": 800,
        "move_speed": 340,
        "projectile": {
            "name": "冰手里剑",
            "damage": 11,
            "speed": 1350,
            # Same 338px reach as the original 520px/s orb, just far faster.
            "lifetime": 0.25,
            "color": (130, 210, 255),
            "size": 7,
            # A spinning cross shuriken instead of a moving orb.
            "style": "shuriken",
            "length": 16,
            "spin": 18,
        },
        "skill_desc": "向前发射冰制手里剑",
        # Rush super: 5 slashes for 30 damage each. If the opponent is within
        # super_distance the caster flashes behind them before the cuts land.
        "super": Attack("霜影奔袭", 150, 16, 22, 26, 130, 130, 0, 12,
                        energy=100, hits=5, hit_interval=4, block_stun=18),
        "super_command": "double_tap_punch",
        # D D 或 A A，再 J J。"toward" 面向对手，等价人类的 D D / A A。
        "super_motion": ["toward", "gap", "toward", "gap", "sf_punch", "gap", "sf_punch"],
        # 专属连招（冰千年杀 S S + 方向 J）的 AI 搓招编排。
        "combo_motion": ["down", "gap", "down", "gap", "toward", "gap", "sf_punch"],
        "super_kind": "rush_slash",
        # dash_only = 突进距离即命中范围。
        "super_area_mode": "dash_only",
        "super_distance": 260,
        "super_desc": "突进一段距离，命中敌人绕后连斩 5 段",
        "super_keys": ("双击 A/D", "J J"),
        # 专属连招（冰千年杀）：遁入地下消失，1 秒后瞬移至敌人脚下冲出并击飞。
        # 帧结构（12 前摇 → 60 潜行 → 14 冲出 → 16 落地复位）由 combat 的
        # SHADOW_* 常量驱动，attack 声明伤害/耗能等战斗数值。
        "combo": {
            "name": "冰千年杀",
            "steps": ("S", "S", "A/D", "J"),
            "note": "遁入地下消失，1 秒后瞬移至敌人脚下冲出并击飞",
            "attack": Attack("冰千年杀", 70, 12, 1, 89, 0, 250, 30, 30,
                             energy=30, block_stun=14),
        },
        "combo_desc": "遁入地下消失，1 秒后瞬移至敌人脚下冲出并击飞",
    },
    "yellow_cape": {
        "id": "yellow_cape",
        "name": "张扬的普通人",
        "accent": (255, 214, 64),
        "decor": "cape",
        "gender": "男",
        "identity": "奔雷浪客",
        "bio": "杨村第一懒洋洋，我不张扬谁张扬。",
        "health": 850,
        "move_speed": 400,
        "projectile": {
            "name": "雷弧",
            "damage": 3,
            # 2.5x the old speed, triple the old reach (3375 px/s * 0.18 s).
            "speed": 3375,
            "lifetime": 0.18,
            "color": (255, 214, 64),
            "size": 7,
            "style": "beam",
            "length": 37,
        },
        "skill_desc": "向前甩出远距雷弧",
        # Launch super: dash in, then the victim flies up and an extra bolt
        # finishes them in the air. The frames are stretched (like the red
        # scarf super) so the dash, wind-up and follow-through stay readable.
        "super": Attack("雷霆嘎巴", 250, 34, 12, 60, 150, 120, 26, 30,
                        energy=100, launch=700, block_stun=20),
        # Command super: double tap A / D, then J J.
        "super_command": "double_tap_punch",
        # D D 或 A A，再 J J。"toward" 面向对手，等价人类的 D D / A A。
        "super_motion": ["toward", "gap", "toward", "gap", "sf_punch", "gap", "sf_punch"],
        # 专属连招（落雷 S S U）的 AI 搓招编排，与压起身计划共用 cast 收尾。
        "combo_motion": ["down", "gap", "down", "gap", "cast"],
        "super_kind": "dash_launch",
        # dash_plus_reach = 先冲刺再打出拳脚射程，二者相加。
        "super_area_mode": "dash_plus_reach",
        # 向前冲刺的距离（贴近对手会提前停步，避免穿身）。
        "super_distance": 180,
        "super_keys": ("双击 A/D", "J J"),
        "super_desc": "冲刺出拳击飞对手造成250伤害，并在半空强化落雷造成100伤害。",
        # Follow-up bolt fired into the airborne victim.
        "super_bolt": {"damage": 100, "delay": .30, "radius": 90,
                       "air": True, "height": 620, "speed": 3375, "stun": 12},
        # S S U: a warning ring under the foe, then a bolt lands one second later.
        "buff": {"name": "落雷", "kind": "strike", "command": "double_down",
                 "energy": 30, "damage": 75, "delay": 1.0, "radius": 70,
                 "air": False, "height": 620, "speed": 3375, "stun": 20},
        "combo": {
            "name": "打雷",
            "steps": ("S", "S", "U"),
            "note": "在敌人脚下生成两人大的黄圈，1 秒后落雷砸下造成 75 伤害",
        },
        "combo_desc": "在敌人脚下引雷，1 秒后落雷砸落",
    },
    "gray_tie": {
        "id": "gray_tie",
        "name": "上班的普通人",
        "accent": (196, 160, 60),
        "decor": "tie",
        "gender": "男",
        "identity": "通勤打工人",
        "bio": "我只是一个平平无奇的上班族，请不要来打扰我。",
        "health": 1100,
        "move_speed": 280,
        "projectile": {
            "name": "让开！",
            # 每 0.25 秒结算一段伤害，直到波的存活时间耗尽。
            "damage": 4,
            "speed": 100,
            "lifetime": 1.6,
            "color": (196, 160, 60),
            "size": 10,
            "style": "carrier",
            "tick_interval": 0.25,
            "wall_damage": 8,
            "wall_knockdown": 0.8,
        },
        "skill_desc": "发射一面缓行的波",
        # 大招：借过一下 —— S S + 方向 + I，霸体向前冲锋，撞到人后勾脖摔地。
        # 数值：撞击 40 + 摔地 110 = 150；敌人倒地 2 秒，自己立即起身。
        "super": Attack("借过一下", 150, 12, 35, 18, 70, 110, 0, 12,
                        energy=100, hits=2, hit_interval=8, block_stun=0),
        "super_command": "double_down_dir_grab",
        # S S + 方向键 + I。
        "super_motion": ["down", "gap", "down", "gap", "toward", "gap", "grab"],
        # 专属连招（晚高峰警告 S S L）的 AI 搓招编排，guard = 防御键 L。
        "combo_motion": ["down", "gap", "down", "gap", "guard"],
        "super_kind": "tackle_slam",
        # dash_only = 霸体冲锋的冲锋距离即命中范围。
        "super_area_mode": "dash_only",
        "super_distance": 340,
        "super_desc": "霸体向前冲锋，撞到人会使用勾脖摔地。",
        "super_keys": ("S", "S", "A/D", "I"),
        # 专属连招：晚高峰警告 —— S S L，获得 7 秒 200 点护盾。
        "combo": {
            "name": "晚高峰警告",
            "steps": ("S", "S", "L"),
            "trigger": "shield",
            "note": "给自己附加 200 点护盾，持续 7 秒，期间受击先扣护盾",
            "attack": Attack("晚高峰警告", 0, 10, 4, 16, 0, 0, 0, 0, energy=40),
        },
        "combo_desc": "获得 200 点的7秒护盾。",
    },
    "dio": {
        "id": "dio",
        "name": "迪奥布兰达",
        "accent": (255, 200, 36),
        "decor": "dio_hair",
        # 外观：黄色竖发 + 黄外套（躯干/手臂）+ 黄裤子（腿），血红双眼。
        "outfit": {"torso": (240, 194, 44), "arms": (232, 184, 40),
                   "legs": (214, 166, 32)},
        "eye_color": (214, 24, 46),
        "gender": "男",
        "identity": "吸血鬼",
        "bio": "人类的能力是有极限的……除非超越人类。",
        "health": 900,
        "move_speed": 300,
        # 飞刀：向前掷出一把银色小刀，瞬发、飞行快、命中即消失。style = knife
        # 复用战斗里的飞刀绘制（与时停齐射同一套）。这里的 "length" 是刀身视觉
        # 长度，不是射程；AI 的远程距离按 speed × lifetime 计算（约 648 像素）。
        "projectile": {
            "name": "飞刀",
            "damage": 10,
            "speed": 720,
            "lifetime": 0.9,
            "color": (228, 232, 240),
            "size": 5,
            "style": "knife",
            "length": 26,
        },
        "skill_desc": "向前掷出一把飞刀",
        # 砸瓦鲁多：S S + L L。零帧起手——按下指令的下一帧直接进入时停，
        # 没有可被打断的前摇；时停 7 秒的具体规则由 combat 的 time_stop
        # 状态机实现。hit_height 给 AI 判断用，招式本身不结算伤害
        # （由 _time_stop_punch 负责）。
        "super": Attack("砸瓦鲁多", 0, 0, 1, 24, 0, 200, 0, 0, energy=100),
        "super_command": "double_down_cast",
        # S S + L L（L = 防御键，双击）。
        "super_motion": ["down", "gap", "down", "gap", "guard", "gap", "guard"],
        "super_kind": "time_stop",
        "super_area_mode": "radius",
        # 全屏：时停不挑距离，任一帧的敌人都会被定格。
        "super_radius": 928.,
        "super_keys": ("S", "S", "L", "L"),
        "super_desc": "在接下来的停止时间里，7秒解决你。",
        "super_time_stop": 7.0,
        "super_punch_damage": 8,
        # 气化冷冻法：A/D + L L。向前射出一段蓝色冰束，命中把对手冻住 1.5 秒；
        # 冻结中挨到的第一记干净命中额外承受 30 点「碎裂」伤害并提前破冰。
        # 冰束是飞行道具：站立防御能挡（只吃擦伤、不冻结），蹲下可以躲过。
        "combo": {
            "name": "气化冷冻法",
            "steps": ("A/D", "L", "L"),
            "trigger": "vapor",
            "attack": Attack("气化冷冻法", 12, 14, 4, 20, 0, 130, 0, 16,
                             energy=30, block_stun=12),
            # 冰束本体：900 像素/秒 × 0.42 秒 ≈ 378 像素射程。
            "beam": {
                "damage": 12,
                "speed": 900,
                "lifetime": 0.42,
                "length": 64,
                "size": 7,
                "color": (128, 206, 255),
            },
            "note": "向前射出蓝色冰束，命中冻住对手 1.5 秒；冻结中挨的第一击额外 30 伤害并碎冰",
        },
        "combo_desc": "碰到我，就冻成冰雕吧。",
    },
}

# 角色专属 AI 风格：每个角色“怎么打”的身份层，叠加在难度层之上。
# 难度决定“打得多好”，这里决定“打得像谁”。
#   prefer_range —— (近, 远) 优势距离带，覆盖通用距离决策
#   proj_bias    —— 弹幕概率倍率（1.0 中性；<1 少扔，>1 更爱远程牵制）
#   grab_bias    —— 近身时抓取偏好（>=1 连段后接抓取，<1 只拼拳脚）
CHARACTER_AI = {
    "red_scarf":     dict(prefer_range=(150., 330.), proj_bias=1.0, grab_bias=1.7),
    "blue_headband": dict(prefer_range=(48., 120.),  proj_bias=0.4, grab_bias=0.55),
    "yellow_cape":   dict(prefer_range=(240., 600.), proj_bias=1.5, grab_bias=0.25),
    # 上班的"让开！"是 100px/s 的慢速推进波，真实射程只有 160px（速度×存活
    # 时长）——优势带必须贴着波的有效距离（推波压墙）。此前写 (200, 450)
    # 时放弹区间 shot_lo <= d <= reach 永假，AI 在拉锯带干站不放弹；AI 侧
    # 另有钳制兜底，但数据本身要写对。
    "gray_tie":      dict(prefer_range=(60., 150.),  proj_bias=1.2, grab_bias=0.3),
    # 迪奥靠 430px 的长激光牵制，贴脸收益低（出拳慢），保持中远距离。
    "dio":           dict(prefer_range=(220., 430.), proj_bias=1.3, grab_bias=0.25),
}

# 角色专属 AI 连段库（可选）：键 = char_id，值 = 连段条目列表，命中时优先于
# ai.py 的通用默认库。新角色在这里写几条 dict 即自带特色连段，ai.py 零改动。
# 每条字段：
#   steps     —— plan token 序列（punch/kick/low_kick/crouch_punch/grab/...）
#   max_range —— 起手距离上限（px）；调用方已先按 melee 阈值决定压上，这里兜底
#   when      —— 局面过滤：any / stun（对手吃硬直）/ crouch_guard / low_hp
#   tiers     —— 可用难度档位（0 普通 ~ 3 地狱），缺省全档
#   weight    —— 同局面多条候选时的选中权重（加权随机，避免连段锁步）
# 爱抓的角色无需手写接抓连段：grab_bias >= 1.0 时 AI 自动派生贴脸的
# punch-kick-grab（风格关闭的红头巾沿用同一派生，保持旧特判行为）。
CHARACTER_COMBOS = {
    # "blue_headband": [
    #     dict(steps=("punch", "punch", "kick"), max_range=100., when="any",
    #          tiers=(2, 3), weight=1.),
    # ],
}

# Default P1 / P2 character IDs
PLAYER_CHARS = ["red_scarf", "blue_headband"]
