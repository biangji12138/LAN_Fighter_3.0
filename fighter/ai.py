"""Practice-mode AI: pure decision logic with no pygame dependency.

One AIController per fighter slot. It reads the world only through the bound
Combat instance and emits one frame of input keys per command() call, exactly
like a human player pressing buttons.
"""
import random

from .attacks import ATTACKS
from .characters import CHARACTERS, CHARACTER_AI, CHARACTER_COMBOS
from .combat import CHAINABLE, CROUCH_ATTACKS, DEFAULT_HP

# AI button pulses are held for longer than one physics tick (1/60s). Combat
# only samples inputs on fixed ticks, so a one-render-frame pulse would be
# dropped whenever the display runs faster than 60 Hz, making the AI stutter.
AI_INPUT_HOLD = .06
# 石面鬼之眼这类引导招式要按住才成形，AI 一次按住约半秒再松手。
AI_LASER_HOLD = .55
# 方向锁的低档基准：同一方向至少松开这么久才允许再次起步。60Hz 下 0.26s
# ≈ 15.6 帧，超过双击冲刺的 14 帧判定窗口——拉锯带边界上"逼近-急停-再逼近"
# 的每帧抖动若不消抖，会自然凑出按下沿双击，让不会冲刺的普通档频繁"无意
# 冲刺"。困难 / 地狱档用更短的 profile["step_lock"]（0.18 / 0.12s）换灵巧。
AI_MIN_STEP = .26
# Crouching guard stops everything except a grab, so the AI ducks under high
# shots and only stands up when the opponent commits to an ordinary melee.
AI_GUARD_TIME = .3
# 节奏预判：最近的近战出招挤在短窗口内即机械连打（0.3 秒一拳的节奏人类也能
# 读出）。连打快过任何反应延迟，等反应计时再掷格挡骰物理上防不住——预判举盾
# 是"单键连打必胜"的结构性解药；读出节奏不等于读出招，投技与下段仍可破盾。
AI_RHYTHM_GUARD = .45
SPAM_MARKS = 5      # 连打判定的最小出招次数
SPAM_WINDOW = 1.2   # 判定窗口（秒）：最近 SPAM_MARKS 次出招挤在窗口内
GUARD_STANCES = ("guard", "crouch_guard")
AI_PUSH_TIME = 1.6

# AI 难度分四档（普通 / 中等 / 困难 / 地狱），沿用《街霸 6》的思路：低档战术
# 少、执行差；逐档先补"会看局面"的战术，再收紧"反应与精准"的执行参数；地狱档
# 在此之上拥有全知全能的读帧能力，绝不失误。
#   super_s —— 能量足够且敌人在大招范围内时，出大招前的最低思考秒数
#   super_p —— 能量足够且敌人在大招范围内时放大招的随机概率
#   shot_p  —— 拉锯距离投掷弹幕的基准概率（对手血多 / 血少）
#   shot_s  —— 拉锯距离投掷弹幕前的最低思考秒数
#   dodge   —— 正确下蹲 / 下蹲格挡闪避来弹的概率
#   push    —— 纯防守多少秒后强制压上（防止龟缩）
#   melee   —— 判为近身压制范围的最大距离
#   watchdog —— 连续多少秒无计划、无移动、无攻击后强制出手（发呆看门狗）。
#               它是"残血双 AI 互相保守、双双站桩到超时"这类活锁的总兜底：
#               无论发呆根因是什么，超时必被掐断。
#   react   —— 反应延迟帧数范围（60Hz）：目击威胁到做出防守动作的间隔，期间
#               照常挨打。大招前摇 14 帧，普通档延迟 14~26 帧 → 物理上防不住
#               大招；档位越高越接近当帧反应。分档手感来自这里，而非概率表面。
#   guard_p —— 反应过来后正确格挡出招的概率。
#   wrong_stance —— 格挡时判错段位（该蹲却站 / 该站却蹲）的概率，蹲/站错
#               的姿势会被相应段位的招式击中。
#   strike_escape —— 看到落雷预警圈后成功走出圈外的概率（蹲防挡不住雷）。
#   dash_p —— 中远距离想压上时改用前冲（双击方向）的概率，0 表示根本不会
#               这门技术；前冲 10 帧 93 像素，是高档位突进接拳的骨架。
#   backdash_p —— 对手抓取起手时用后撤步（8 帧 75 像素）拉开距离的概率，
#               否则只会普通慢退。
#   jump_p —— 拉锯距离机动跳向对手的概率，打乱对手的弹幕与下段节奏。
#   airjump_p —— 跳向对手途中空中再跳一次（二段跳）的概率。
#   step_lock —— 方向锁时长（秒）：同一方向至少松开这么久才允许再次起步。
#               低档 0.26s 超过双击冲刺的 14 帧窗口，杜绝走位抖动凑出按下沿
#               误触冲刺（普通档 dash_p=0，冲了就穿帮）；高档 dash_p 高、
#               误触与主动无法区分，锁可以收紧换来灵巧的进退节奏。
#   evade_p   —— 对手近身起手时"先拉开再谈格挡"的概率（防御性走位）：撤出
#               攻击范围比站着硬挡更省血，是高档才有的判断；判了撤就撤，
#               每招只判一次，失败照常进格挡判定。
#   combo_s  —— 能量足够且局面合适时，出专属连招前的最低思考秒数
#   combo_p  —— 专属连招（角色特色技：素质三连 / 冰千年杀 / 落雷 / 护盾）
#               的使用概率，时机判断见 COMBO_PLANS；普通档也偶尔用一下
#               （与大招同级），档位越高出得越果断、思考越短。
#   prejudge_p —— 识别出机械连打节奏（最近几次近战出招挤在短窗口内）后，不等
#               反应延迟直接预判举盾的概率。连打快过任何反应延迟，这是针对
#               "单键连打必胜"的读招；沿触发掷骰，失败照常挨打，举出的盾仍会
#               被投技与下段破解。
#   punish_p  —— 对手处于收招帧且在近身射程内时，不等走位决策直接插最快一拳
#               反打的概率（恢复帧窗口反击）：连段疲劳（收招加长）与受击硬直
#               衰减创造出的反击窗口，低档偶尔抓住、高档抓住就是確反。
AI_PROFILES = {
    0: dict(super_s=.80, super_p=.55, shot_p=(.62, .35), shot_s=.62,
            dodge=.40, push=4.0, melee=108, watchdog=2.0,
            react=(14, 26), guard_p=.30, wrong_stance=.35, strike_escape=.20,
            step_lock=.26, evade_p=0., prejudge_p=.15, punish_p=.10,
            dash_p=0., backdash_p=0., jump_p=0., airjump_p=0.,
            combo_s=.60, combo_p=.15),
    1: dict(super_s=.50, super_p=.75, shot_p=(.45, .62), shot_s=.50,
            dodge=.62, push=2.8, melee=118, watchdog=1.4,
            react=(9, 17), guard_p=.55, wrong_stance=.15, strike_escape=.45,
            step_lock=.26, evade_p=0., prejudge_p=.45, punish_p=.30,
            dash_p=.10, backdash_p=.12, jump_p=.08, airjump_p=0.,
            combo_s=.45, combo_p=.40),
    2: dict(super_s=.35, super_p=.90, shot_p=(.45, .62), shot_s=.50,
            dodge=.82, push=2.2, melee=124, watchdog=.8,
            react=(5, 9), guard_p=.80, wrong_stance=.05, strike_escape=.75,
            step_lock=.18, evade_p=.35, prejudge_p=.70, punish_p=.55,
            dash_p=.50, backdash_p=.35, jump_p=.22, airjump_p=.45,
            combo_s=.35, combo_p=.70),
    3: dict(super_s=.00, super_p=1.0, shot_p=(1.0, 1.0), shot_s=.00,
            dodge=1.0, push=1.4, melee=132, watchdog=.3,
            react=(0, 1), guard_p=.95, wrong_stance=0., strike_escape=1.0,
            step_lock=.12, evade_p=.60, prejudge_p=.90, punish_p=1.0,
            dash_p=.80, backdash_p=.65, jump_p=.30, airjump_p=1.0,
            combo_s=.00, combo_p=1.0),
}

# 通用默认连段库：任何角色都可用的基础压制连段。角色库（characters.py 的
# CHARACTER_COMBOS，含 grab_bias >= 1.0 自动派生的接抓连段）命中时优先于它。
# 字段说明见 characters.py 的 CHARACTER_COMBOS 注释；无命中时 _pick_combo
# 退回 punch-kick 保底，保证任何档位任何角色都能出手。
DEFAULT_COMBOS = (
    dict(steps=("punch", "kick"), max_range=132., when="any",
         tiers=(0, 1, 2, 3), weight=1.),
    # 对手吃硬直（stun）时高档多补一拳蹭一段伤害；低档不会抓这种时机。
    dict(steps=("punch", "punch", "kick"), max_range=108., when="stun",
         tiers=(2, 3), weight=1.),
)


class AIController:
    """Per-slot AI state machine. Binds to a Combat instance and emits keys."""

    def __init__(self, slot, combat, settings):
        self.slot = slot
        self.combat = combat
        self.settings = settings
        # 本局锁定的难度与风格；None 表示未开局，临时跟随全局设置。
        self.level = None
        self.style_on = None
        self.reset()

    def set_level(self, level):
        """开局时锁定本槽位难度，对局中途改设置不会改变这只 AI 的行为。"""
        self.level = level

    def set_style(self, on):
        """开局时锁定“角色专属风格”开关，对局中途关闭/开启不立刻生效。"""
        self.style_on = on

    def bind(self, combat):
        """Point this controller at the (re)created combat instance."""
        self.combat = combat

    def reset(self, clock=0.):
        self.clock = clock
        self.t = 0.
        self.guard = 0.
        self.plan = None
        self.pulse = 0.
        self.retreat = 0.
        self.crouch = False
        self.rush = 0.
        self.move_dir = 0
        self.dir_exit = {1: -9., -1: -9.}
        self.shot_mark = 0
        self.shot_dodge = None
        self.strike_mark = 0
        self.strike_dodge = None
        self.react_shot = 0.
        self.react_atk = 0.
        self.foe_attack_new = False
        self.atk_defend = None
        self.patience = 0.
        self.force = 0.
        self.idle = 0.
        self.nudge = 0.
        # 节奏预判状态：对手近战出招的启动时刻采样 + 预判举盾计时。
        self.press_marks = []
        self.rhythm_guard = 0.
        self.rhythm_last = False
        # 时停中施法者的出拳节奏计时（见 command 里的时停分支）。
        self.stop_t = 0.

    # ---------------------------------------------------------------- tiers
    def _tier(self):
        level = self.level or self.settings.get("ai_level", "normal")
        return {"normal": 0, "medium": 1, "hard": 2, "hell": 3}.get(level, 0)

    def _profile(self):
        return AI_PROFILES[self._tier()]

    def _smart(self):
        """中等及以上（中等/困难/地狱）读整个局面，而非只看血条。"""
        return self._tier() >= 1

    def _hell(self):
        """地狱难度：在人类判断之上叠加全知全能的读帧反应。"""
        return self._tier() >= 3

    def _style(self, me):
        """开启"角色专属风格"时返回该角色的风格配置，否则 None（走通用 AI）。"""
        on = (self.style_on if self.style_on is not None
              else self.settings.get("char_ai", True))
        if not on:
            return None
        return CHARACTER_AI.get(me.get("char_id", "red_scarf"))

    # -------------------------------------------------------------- spacing
    def _comfort(self, me, foe):
        """Preferred spacing.

        开启角色专属风格时按角色优势距离带打；否则普通按对手血量，中等以上
        自行判断局面。
        """
        style = self._style(me)
        if style:
            return self._style_comfort(me, foe, style)
        if self._smart():
            return self._smart_comfort(me, foe)
        foe_ratio = foe["hp"] / max(1., float(foe.get("hp_max", DEFAULT_HP)))
        if foe["action"] in GUARD_STANCES:
            # Stay inside throw range: grabs beat every guard.
            return 62., 74.
        if foe_ratio > .62:
            return 195., 290.
        if foe_ratio > .32:
            return 100., 190.
        return 42., 110.

    def _smart_comfort(self, me, foe):
        """Medium / hard decide their own range instead of following the health bar."""
        my_ratio = me["hp"] / max(1., float(me.get("hp_max", DEFAULT_HP)))
        foe_ratio = foe["hp"] / max(1., float(foe.get("hp_max", DEFAULT_HP)))
        style = CHARACTERS.get(me.get("char_id", ""), CHARACTERS["red_scarf"])
        spec = me.get("super_spec") or style.get("super")
        if foe["action"] in GUARD_STANCES:
            return 46., 62.            # crowd the guard, then throw or go low
        if foe["stun"] > .15 or foe["attack_kind"]:
            return 48., 84.            # punish a stagger or a whiffed swing
        if spec and me["energy"] >= spec.energy:
            return 58., 96.            # energy is full: walk them into the super
        if my_ratio < .32:
            return 150., 230.          # nearly dead: keep the zoning distance
        if foe_ratio <= .4:
            return 52., 92.            # finish the kill
        return 88., 152.               # otherwise live in pressure range

    def _style_comfort(self, me, foe, style):
        """角色风格的距离决策：以角色的优势距离带为底，叠加同款局面应对。"""
        near, far = style["prefer_range"]
        style_def = CHARACTERS.get(me.get("char_id", ""), CHARACTERS["red_scarf"])
        spec = me.get("super_spec") or style_def.get("super")
        if foe["action"] in GUARD_STANCES:
            return 46., 62.            # 抓取无视防御：贴上去抓 / 下段
        if foe["stun"] > .15 or foe["attack_kind"]:
            return 48., 84.            # 惩罚硬直 / 挥空
        if spec and me["energy"] >= spec.energy:
            return 58., 96.            # 能量满：压进大招射程
        return near, far

    def _incoming_shot(self):
        """An enemy projectile still flying toward this fighter, if any."""
        me = self.combat.fighters[self.slot]
        nearest = None
        for proj in self.combat.projectiles:
            if proj.get("owner") != 1 - self.slot or proj.get("hit"):
                continue
            gap = me["x"] - proj["x"]
            if abs(gap) > 280 or gap * proj.get("vx", 1) <= 0:
                continue
            if nearest is None or abs(gap) < nearest[1]:
                nearest = (proj, abs(gap))
        return nearest[0] if nearest else None

    def _incoming_strike(self):
        """头顶落雷预警圈（仅当自己还在圈内）：蹲防挡不住，走出圈才安全。"""
        me = self.combat.fighters[self.slot]
        for strike in self.combat.strikes:
            if strike.get("owner") == self.slot or strike.get("hit"):
                continue
            if abs(me["x"] - strike["x"]) > strike.get("radius", 60.):
                continue    # 已在圈外，无需躲避
            return strike
        return None

    def _react_time(self):
        """反应延迟：目击威胁到做出防守动作的间隔，档位越低越迟钝。"""
        return random.uniform(*self._profile()["react"]) / 60.

    def _super_area(self, me, spec):
        """Outermost x-distance the super can still connect from."""
        # 射程模式已数据化：角色在 characters.py 声明 super_area_mode，
        # 新角色未写时默认 radius；新增模式才需要在这里加分支。
        mode = me.get("super_area_mode") or "radius"
        reach = spec.reach if spec else 0.
        if mode == "dash_only":
            # 突进 / 冲锋大招：冲刺距离即命中范围。
            return me.get("super_distance", 0.) or reach
        if mode == "dash_plus_reach":
            # 先冲刺 super_distance，再打出原本的拳脚射程。
            return (me.get("super_distance", 0.) or 0.) + reach
        return me.get("super_radius", 0.) or reach

    def _shot_reach(self, me):
        """弹丸真实射程 = 速度 × 存活时长，从角色数据现算（不同角色不一样）。"""
        cfg = me.get("projectile_config", {})
        if cfg.get("style") == "laser":
            # 石面鬼之眼不是飞行道具：速度 × 存活时长恒为 0，射程就是光柱长度。
            return float(cfg.get("length", 430.))
        return float(cfg.get("speed", 420.)) * float(cfg.get("lifetime", .7))

    # ------------------------------------------------------------- combo book
    def _combo_situation(self, me, foe):
        """近身压制的局面归类：连段库按此挑条目。蹲防优先于硬直（抓取破防）。"""
        if foe["action"] == "crouch_guard":
            return "crouch_guard"
        if foe["stun"] > .18:
            return "stun"
        ratio = foe["hp"] / max(1., float(foe.get("hp_max", DEFAULT_HP)))
        if ratio <= .5:
            return "low_hp"
        return "any"

    def _combo_pool(self, me):
        """角色连段池：角色库（CHARACTER_COMBOS）+ grab_bias 派生的接抓连段。

        爱抓的角色（grab_bias >= 1.0）在贴脸距离把抓取接进连段——抓取无视
        任何防御姿态，风格层一个参数即解锁这套接续；风格关闭的红头巾沿用
        旧特判的同一派生，保持原有行为。
        """
        pool = list(CHARACTER_COMBOS.get(me.get("char_id"), ()))
        st = self._style(me)
        want_grab = (st["grab_bias"] >= 1.0 if st is not None
                     else me.get("char_id") == "red_scarf")
        if want_grab:
            pool.append(dict(steps=("punch", "kick", "grab"), max_range=44.,
                             when="any", tiers=(0, 1, 2, 3), weight=1.))
        return pool

    def _pick_combo(self, me, foe, distance):
        """从连段库选一条当前局面可用的压制连段（plan token 列表）。

        选择优先级：角色池 > 通用默认库；局面专属条目（when = stun 等）
        > any 垫底条目；同级命中多条按 weight 加权随机，避免连段锁步。
        无命中时退回 punch-kick 保底。
        """
        tier = self._tier()
        sit = self._combo_situation(me, foe)
        whens = (sit,) if sit == "any" else (sit, "any")
        for pool in (self._combo_pool(me), DEFAULT_COMBOS):
            for when in whens:
                hits = [e for e in pool
                        if e["when"] == when
                        and distance <= e.get("max_range", 132.)
                        and tier in e.get("tiers", (0, 1, 2, 3))]
                if hits:
                    pick = hits[0] if len(hits) == 1 else random.choices(
                        hits, weights=[e.get("weight", 1.) for e in hits])[0]
                    return list(pick["steps"])
        return ["punch", "kick"]

    # --------------------------------------------------------- character AI
    def _char_plan(self, me, foe, distance):
        """角色专属对局计划（仅风格层开启时调用）。

        战术函数在模块级注册表 CHARACTER_PLANS 登记（键 = char_id），签名
        统一 (controller, me, foe, distance) -> bool：返回 True 表示本 tick
        已接管决策，通用流程让位。新角色的绝活写一个函数注册即生效，本
        方法不再随角色膨胀。
        """
        fn = CHARACTER_PLANS.get(me.get("char_id"))
        if fn is None:
            return False
        return fn(self, me, foe, distance)

    def _combo_cost(self, me):
        """专属连招耗能：有 combo_attack 的（冰千年杀 / 护盾）读招式表；
        符印角色（素质三连 / 落雷）读 buff_spec.energy。都没有 = 没有专属技。"""
        ca = me.get("combo_attack")
        if ca is not None:
            return ca.energy
        return int((me.get("buff_spec") or {}).get("energy", 0))

    def _queue_combo(self, me):
        # 搓招编排同样数据化：characters.py 的 combo_motion（plan token 序列），
        # 与 super_motion 同构。新角色不写该字段时视为没有专属技。
        steps = list(me.get("combo_motion") or [])
        if not steps:
            return False
        self._queue_plan(steps, 1.8)
        return True

    def _try_combo(self, me, foe, distance):
        """专属连招决策：与大招的 super_s / super_p 同构的两段门槛。

        时机函数（COMBO_PLANS，键 = char_id）先判"该不该出"（局面合适），
        通过后再过难度层门槛：combo_s 秒思考时间 + combo_p 概率。能量是
        天然的频率上限；大招可出时不零花能量在专属技上。
        """
        p = self._profile()
        if p["combo_p"] <= 0. or self.clock <= p["combo_s"]:
            return False
        cost = self._combo_cost(me)
        if cost <= 0 or me["energy"] < cost:
            return False
        if (not me["grounded"] or me["stun"] > 0 or me["knocked"]
                or me["cooldown"] > 0):
            return False
        # 大招优先：能量够出大招且对手站在射程内时，把能量留给大招。倒地
        # 的对手不在此列——那是压起身专属技（落雷 / 冰千年杀）的时机。
        if not foe.get("knocked"):
            style = CHARACTERS.get(me.get("char_id", ""), CHARACTERS["red_scarf"])
            spec = me.get("super_spec") or style.get("super")
            if (spec and me["energy"] >= spec.energy
                    and distance <= self._super_area(me, spec) - 10):
                return False
        fn = COMBO_PLANS.get(me.get("char_id"))
        if fn is None or not fn(self, me, foe, distance):
            return False
        # 先掷骰后排队：时机函数只回答"局面合不合适"，骰子输了绝不能把
        # 搓招排进计划，否则 combo_p 形同虚设。
        if random.random() >= p["combo_p"]:
            return False
        return self._queue_combo(me)

    def _super_steps(self, me):
        # 搓招编排已数据化：角色在 characters.py 声明 super_motion（plan token
        # 序列），set_loadout 复制进 fighter 状态。新角色不写该字段时退化为
        # 单键 "super"。
        return list(me.get("super_motion") or ["super"])

    def _queue_super(self, me):
        self._queue_plan(self._super_steps(me), 1.8)

    def _super_can_hit(self, me, foe):
        """True when the super is paid for and the opponent is inside its hitbox."""
        style = CHARACTERS.get(me.get("char_id", ""), CHARACTERS["red_scarf"])
        spec = me.get("super_spec") or style.get("super")
        if not spec or me["energy"] < spec.energy or foe.get("knocked"):
            return False
        if not me.get("grounded") or me["cooldown"] > 0:
            return False
        area = self._super_area(me, spec)
        if area <= 0 or abs(foe["x"] - me["x"]) > area - 8:
            return False
        return abs(foe["y"] - me["y"]) <= spec.hit_height

    def _attack_phase(self, foe):
        """对手当前出招处于哪个阶段：起手 / 有效（可命中）/ 收招。"""
        kind = foe.get("attack_kind")
        spec = ATTACKS.get(kind) if kind else None
        if not spec:
            return None
        frame = foe.get("action_frame", 0)
        if frame < spec.startup:
            return "startup"
        if frame < spec.startup + spec.active:
            return "active"
        return "recovery"

    def _hell_react(self, me, foe, distance):
        """地狱难度专用：以全知视角读对手出招帧并做帧级应对。

        - 抓取无视防御：对手抓取一起手就后撤，撤出抓取范围；
        - 对手攻击够不到我时，在其挥空期间前压，抢在收招帧反击；
        - 对手进入收招帧（挥空或被防）时，立即用最优招式反打。
        """
        kind = foe.get("attack_kind")
        phase = self._attack_phase(foe)
        if not kind or phase is None:
            return False
        spec = ATTACKS[kind]
        if kind == "grab":
            if distance <= spec.reach + 40:
                self._queue_plan(["back", "gap", "back"], 1.0)
                return True
            return False
        if phase == "active" and distance > spec.reach:
            # 攻击注定挥空：前压，进入收招帧反击的射程；地狱档直接前冲抢位。
            if (me["grounded"] and me["cooldown"] <= 0 and not self.plan
                    and random.random() < self._profile()["dash_p"]):
                self._queue_plan(["toward", "gap", "toward"], 1.0)
                return True
            self.rush = max(self.rush, .25)
            return False
        if phase == "recovery":
            if distance <= ATTACKS["grab"].reach - 2:
                self._queue_plan(["grab"], 1.2)
            else:
                self._queue_plan(["punch", "kick"], 1.6)
            return True
        return False

    # ----------------------------------------------------------- plan queue
    def _queue_plan(self, steps, limit=2.2, knockdown=False):
        self.plan = {"steps": list(steps), "step": 0, "prev": None,
                     "t": 0., "step_t": 0., "limit": limit,
                     "knockdown": knockdown}
        self.clock = 0.

    def _abort_plan(self, low=.15, high=.4):
        self.plan = None
        self.clock = -random.uniform(low, high)

    def _start_plan(self):
        """Pick a plan that fits the spacing, the health lead and the defence.

        难度按《街霸 6》思路分级：低档战术少、执行差，逐档调紧同一组参数。
        """
        me = self.combat.fighters[self.slot]
        foe = self.combat.fighters[1 - self.slot]
        distance = abs(me["x"] - foe["x"])
        clock = self.clock
        foe_ratio = foe["hp"] / max(1., float(foe.get("hp_max", DEFAULT_HP)))
        retreating = self.retreat > 0
        forcing = self.force > 0
        p = self._profile()
        guard = foe["action"]
        # 角色专属对局计划优先于通用决策（压起身落雷、突进大招位移）。
        if self._style(me) is not None and self._char_plan(me, foe, distance):
            return True
        # 专属连招（角色特色技）：COMBO_PLANS 判时机，难度层管会不会用。
        # 放在倒地分支之前——冰千年杀的压起身要在对手倒地时出手。
        if self._style(me) is not None and self._try_combo(me, foe, distance):
            return True
        if foe.get("knocked"):
            # 对手倒地：拉开抓取距离，等起身后再压起身弹。用普通后撤走位
            # （spacing 的 away 键）而非 "back gap back" 编排——后者已是双击
            # 后方，会误触后撤步冲刺，普通档不该白得这门技术。
            if distance < 230:
                self.retreat = max(self.retreat, 1.0)
            return True
        if guard in GUARD_STANCES:
            # Grabs beat every guard, so walk into throw range and take it.
            if distance <= ATTACKS["grab"].reach - 4:
                self._queue_plan(["grab"], 1.2)
                return True
            if guard == "guard" and distance <= ATTACKS["low_kick"].reach - 6:
                # A standing guard cannot stop crouching attacks, so go low.
                self._queue_plan(["low_kick"], 1.4)
                return True
            return False   # walk into grab range and open a crouching guard
        style = CHARACTERS.get(me.get("char_id", ""), CHARACTERS["red_scarf"])
        spec = me.get("super_spec") or style.get("super")
        area = self._super_area(me, spec)
        if (spec and me["energy"] >= spec.energy and distance <= area - 10 and
                clock > p["super_s"] and random.random() < p["super_p"]):
            self._queue_super(me)
            return True
        # 位移机动：中高档位在中远距离会前冲 / 跳跃变换逼近节奏（普通档只会
        # 走路）。前冲 10 帧 93 像素；地狱档前冲后直接接拳脚连段。
        if (self._tier() >= 1 and distance > p["melee"]
                and me["grounded"] and me["cooldown"] <= 0
                and clock > p["shot_s"]):
            if random.random() < p["jump_p"]:
                steps = ["jump_t", "drift", "drift"]
                if random.random() < p["airjump_p"]:
                    steps += ["gap", "air_jump", "drift"]
                self._queue_plan(steps, 1.5)
                return True
            if random.random() < p["dash_p"]:
                follow = ["punch", "kick"] if self._tier() >= 3 else []
                self._queue_plan(["toward", "gap", "toward"] + follow, 1.5)
                return True
        if retreating and not forcing:
            # Keep the zoning game alive while backing off. 射程钳制：退到
            # 弹幕够不着的位置就不再浪费出手（慢速弹尤其明显）。
            if (120 <= distance <= min(310., self._shot_reach(me))
                    and clock > .55 and random.random() < .5):
                self._queue_plan(["shot"], 1.3)
                return True
            return False
        if forcing:
            # Forced approach: no more zoning, only pressure and grabs.
            if distance <= 82:
                self._queue_plan(self._pick_combo(me, foe, distance), 1.6)
            else:
                self.rush = max(self.rush, .5)
            return False
        if distance <= p["melee"] and (
                foe["stun"] > .18 or foe_ratio <= .5 or clock > .85):
            # 压制连段从连段库选（角色库优先，grab_bias 派生接抓，高档对
            # 硬直多补一拳），不再硬编码 punch-kick。
            self._queue_plan(self._pick_combo(me, foe, distance), 2.0)
            return True
        st = self._style(me)
        reach = self._shot_reach(me)
        if st is not None:
            shot_lo = st["prefer_range"][0]
            chance = min(1.0, p["shot_p"][0 if foe_ratio > .55 else 1] * st["proj_bias"])
        else:
            shot_lo, chance = 105, p["shot_p"][0 if foe_ratio > .55 else 1]
        # 射程钳制：风格声明的理想站位若整体超出弹幕真实射程（数据错位），
        # 退化成默认近带在射程内放弹，而不是 shot_lo <= d <= reach 永假哑火。
        if shot_lo > reach:
            shot_lo = min(105., reach)
        if shot_lo <= distance <= reach and clock > p["shot_s"]:
            if random.random() < chance:
                self._queue_plan(["shot"], 1.3)
                return True
            if random.random() < .6:
                # Do not sit in the pocket forever: commit to a run-in.
                self.rush = random.uniform(.9, 1.8)
            return False
        return False

    def _watchdog_act(self, me, foe, distance):
        """发呆看门狗：长时间无计划、无移动、无攻击时强制出手。

        双方残血互相保守时可能双双卡在拉锯带内谁都不动（射击 roll 反复失败 →
        rush 又打断耐心 → 强制压上永远攒不满的活锁），无论发呆根因是什么，
        超过档位 watchdog 时限就从这里强制选择一个行动，杜绝站桩到超时。
        """
        p = self._profile()
        self.guard = 0.
        self.crouch = False
        self.retreat = 0.
        if (me["grounded"] and not me["attack_kind"]
                and foe["action"] != "crouch_guard"
                and p["melee"] < distance <= self._shot_reach(me)):
            self._queue_plan(["shot"], 1.3)
        elif distance <= p["melee"]:
            self._queue_plan(self._pick_combo(me, foe, distance), 2.0)
        else:
            # 既够不着又打不到：直接压上，不再等耐心积累。
            self.force = AI_PUSH_TIME
            self.rush = AI_PUSH_TIME
            self.patience = 0.
            self.clock = max(self.clock, .5)

    def _run_super(self, me, foe, distance):
        style = CHARACTERS.get(me.get("char_id", ""), CHARACTERS["red_scarf"])
        spec = me.get("super_spec") or style.get("super")
        area = me.get("super_radius", 0.) or spec.reach
        if (me["energy"] < spec.energy or distance > area or
                abs(foe["y"] - me["y"]) > spec.hit_height):
            return {}
        if me["attack_kind"] in ("punch", "kick"):
            # A normal can cancel its early startup into the command super.
            ready = me["attack_hit"] and me["action_frame"] <= 10
        else:
            ready = not me["attack_kind"] and me["cooldown"] <= 0
        return {"punch": True, "kick": True} if ready else {}

    def _melee_ready(self, me, plan, spec, distance, foe):
        """True when the next queued melee can start (or cancel the previous one)."""
        prev = plan.get("prev")
        if prev and me["attack_kind"] in CHAINABLE and me["stun"] <= 0:
            prev_spec = ATTACKS[prev]
            ready = (me["attack_hit"] or
                     me["action_frame"] >= prev_spec.startup + prev_spec.active)
        else:
            ready = not me["attack_kind"] and me["cooldown"] <= 0
        return (ready and distance <= spec.reach - 2 and
                abs(foe["y"] - me["y"]) <= spec.hit_height)

    def _melee_approach(self, me, plan, spec, distance, foe):
        """Melee 步够不着时不干等：第一招先向对手走近一步。

        距离可能卡进"punch 判定外（reach-2）、melee 阈值内"的鬼域——原地空等
        0.5s abort 再重试只会无限循环（残血双 AI 互相站桩到超时的根因之一），
        所以第一招主动贴近；链招等待 cancel 窗口时不动，避免打断连段。
        """
        if plan.get("prev") or me["attack_kind"] or me["stun"] > 0:
            return None
        if not me["grounded"]:
            return None
        if distance > spec.reach - 2 and abs(foe["y"] - me["y"]) <= spec.hit_height:
            return {"right" if me["x"] < foe["x"] else "left": True}
        return None

    def _shot_keys(self, me, foe):
        if me["attack_kind"] or me["cooldown"] > 0 or not me["grounded"]:
            return {}
        if foe["action"] == "crouch_guard":
            return {}   # chip only, so go for the grab instead
        if (me.get("projectile_config") or {}).get("style") == "laser":
            # 激光是按住引导，没有高 / 低弹道之分，蹲下也照样从眼睛射出。
            return {"projectile": True}
        if foe["action"] == "crouch" or random.random() < .4:
            # A low shot still reaches a ducking opponent (and catches players
            # who duck on reaction to high shots).
            return {"down": True, "projectile": True}
        return {"projectile": True}

    def _run_plan(self, me, foe, distance, dt):
        plan = self.plan
        if not plan:
            return None
        plan["t"] += dt
        plan["step_t"] += dt
        if plan["t"] > plan["limit"]:
            self._abort_plan(.15, .45)
            return None
        if me["stun"] > 0 or me["knocked"]:
            self._abort_plan(.35, .9)
            return None
        # Keep re-emitting the last press until the hold time is over, so at
        # least one fixed physics tick samples it on high-refresh displays.
        if self.pulse > 0:
            return plan.get("last", {})
        steps = plan["steps"]
        if plan["step"] >= len(steps):
            # Finished the scripted combo: sometimes reset spacing and add a
            # short, varied breather so the AIs do not chain in lockstep.
            self.plan = None
            self.clock = -random.uniform(.1, .3)
            if not plan.get("knockdown") and random.random() < .3:
                self.retreat = random.uniform(.35, .7)
            return None
        name = steps[plan["step"]]
        # A queued input that cannot be delivered for half a second is stale:
        # abort instead of freezing on it (this is what made the AI stutter).
        if plan["step_t"] > .5 and name not in ("gap", "wait_getup"):
            self._abort_plan(.2, .45)
            return None
        keys = None
        if name == "gap":
            # One neutral frame so the next down tap becomes a fresh press edge.
            plan["step"] += 1
            plan["step_t"] = 0.
            return {}
        if name == "wait_getup":
            if foe.get("knocked"):
                return {}
            plan["step"] += 1
            plan["step_t"] = 0.
            return {}
        if name == "down":
            keys = {"down": True}
        elif name == "up":
            if me["attack_kind"] or me["stun"] > 0 or me["knocked"]:
                return {}
            keys = {"jump": True}
        elif name == "jump_t":
            # 跳向对手：跳与前方向同帧按下，起跳即带横向漂移。
            if me["stun"] > 0 or me["knocked"] or me["attack_kind"] or not me["grounded"]:
                return {}
            keys = {"jump": True, "right" if me["x"] < foe["x"] else "left": True}
        elif name == "air_jump":
            # 空中二段跳：松开跳跃键后（gap 步）再按才有按下沿；同帧按住前方向
            # 保持漂移不断。me["air_jump"] 为 True 表示本跳已用过空中跳。
            if (me["stun"] > 0 or me["knocked"] or me["attack_kind"]
                    or me["grounded"] or me.get("air_jump", True)):
                return {}
            keys = {"jump": True, "right" if me["x"] < foe["x"] else "left": True}
        elif name == "drift":
            # 空中漂移：跳跃没有水平动量，按住前方向才移动。不能带 grounded
            # 守卫——跳起后干等 0.5s 再 abort，二段跳步永远排不上（实测教训）。
            if me["stun"] > 0 or me["knocked"] or me["attack_kind"]:
                return {}
            keys = {"right" if me["x"] < foe["x"] else "left": True}
        elif name == "back":
            if me["attack_kind"] or me["cooldown"] > 0 or not me["grounded"]:
                return {}
            keys = {"right" if me["x"] > foe["x"] else "left": True}
        elif name == "toward":
            if me["attack_kind"] or me["cooldown"] > 0 or not me["grounded"]:
                return {}
            keys = {"right" if me["x"] < foe["x"] else "left": True}
        elif name == "sf_punch":
            # Super-confirm punches: deliberately skip the melee reach gate so
            # the second press can cancel the first into the rush super.
            if me["stun"] > 0 or not me["grounded"]:
                return {}
            keys = {"punch": True}
        elif name == "sf_kick":
            # Command-super setup kicks: like sf_punch, no reach gate, because
            # the K K prefix of the yellow cape super may start a little short.
            if me["stun"] > 0 or not me["grounded"]:
                return {}
            keys = {"kick": True}
        elif name == "shot":
            keys = self._shot_keys(me, foe)
        elif name == "cast":
            # 落雷等符印允许起跳后在空中施放：W W 前缀已经起跳，这里只按弹幕键
            # 触发放雷，不再要求 grounded（与"shot"的区别就在这一处）。
            if me["attack_kind"] or me["stun"] > 0 or me["knocked"]:
                return {}
            keys = {"projectile": True}
        elif name == "super":
            keys = self._run_super(me, foe, distance)
        elif name == "grab":
            if me["stun"] > 0 or not me["grounded"]:
                return {}
            keys = {"grab": True}
        elif name == "guard":
            # 晚高峰警告（S S L）的 L：站姿举盾一瞬即完成搓招，AI 随即松开。
            if me["stun"] > 0 or not me["grounded"]:
                return {}
            keys = {"guard": True}
        elif name in ("crouch_punch", "low_kick"):
            spec = ATTACKS[name]
            if not self._melee_ready(me, plan, spec, distance, foe):
                return self._melee_approach(me, plan, spec, distance, foe) or {}
            keys = {"down": True,
                    ("punch" if name == "crouch_punch" else "kick"): True}
            plan["prev"] = name
        else:
            spec = ATTACKS[name]
            if not self._melee_ready(me, plan, spec, distance, foe):
                return self._melee_approach(me, plan, spec, distance, foe) or {}
            keys = {name: True}
            plan["prev"] = name
        if not keys:
            return {}
        plan["last"] = dict(keys)
        plan["step"] += 1
        plan["step_t"] = 0.
        # 引导型激光要按住一段时间才形成光柱，单帧脉冲前摇都走不完。
        laser_hold = (keys.get("projectile")
                      and (me.get("projectile_config") or {}).get("style") == "laser")
        self.pulse = AI_LASER_HOLD if laser_hold else AI_INPUT_HOLD
        return keys

    # -------------------------------------------------------------- command
    def command(self, dt):
        """Build one frame of AI input for the fighter at ``self.slot``."""
        me = self.combat.fighters[self.slot]
        foe = self.combat.fighters[1 - self.slot]
        tier = self._tier()
        self.clock += dt
        self.t += dt
        self.guard = max(0., self.guard - dt)
        self.pulse = max(0., self.pulse - dt)
        self.retreat = max(0., self.retreat - dt)
        self.rush = max(0., self.rush - dt)
        self.force = max(0., self.force - dt)
        self.react_shot = max(0., self.react_shot - dt)
        self.react_atk = max(0., self.react_atk - dt)
        self.nudge = max(0., self.nudge - dt)
        prev_rhythm = self.rhythm_guard
        self.rhythm_guard = max(0., self.rhythm_guard - dt)
        if prev_rhythm > 0. >= self.rhythm_guard:
            self.rhythm_last = False   # 预判窗口到期，持续压制可重新判定
        # 目击边沿：对手从收招态转入新招的第一帧才启动反应计时，同一招
        # 不会反复刷新；react 期间 AI 照常挨打（低档真的反应不过来）。
        if foe["attack_kind"] and not self.foe_attack_new:
            self.foe_attack_new = True
            self.react_atk = self._react_time()
            self.atk_defend = None
            # 连打节奏采样：每一次"从收招态转入新招"记一笔。采样不受反应
            # 延迟影响——节奏是看出来的，不是反应出来的。
            self.press_marks.append(self.t)
            del self.press_marks[:-SPAM_MARKS]
        elif not foe["attack_kind"]:
            self.foe_attack_new = False
        forcing = self.force > 0
        distance = abs(me["x"] - foe["x"])
        away = "right" if me["x"] > foe["x"] else "left"
        toward = "left" if away == "right" else "right"
        free = not me["attack_kind"] and me["stun"] <= 0 and not me["knocked"]

        # --- 砸瓦鲁多：时停期间只有施法者能出拳，其余一律不动 ---
        if self.combat.time_stop > 0:
            if self.combat.time_stop_owner != self.slot:
                return {}
            # 一格出一格收制造按下沿，约 6 拳/秒（瞬发拳按按下沿结算）。
            self.stop_t += dt
            keys = {"punch": (self.stop_t % .16) < .08}
            # 敌人被定格在远处时先走近再打（时停里移速翻倍）。
            if me["x"] < foe["x"] - 60:
                keys["right"] = True
            elif me["x"] > foe["x"] + 60:
                keys["left"] = True
            return keys

        # --- patience: never defend forever against ranged spam ---
        # rush 前压不算打断：若它清零耐心，拉锯带内"射击失败 → rush → 清零"
        # 会循环，强制压上永远攒不满（残血互保时的站桩活锁根因之一）。
        if (me["stun"] > 0 or me["knocked"] or forcing or self.plan
                or me["attack_kind"]):
            self.patience = 0.
        else:
            self.patience += dt
            if self.patience >= self._profile()["push"]:
                # Time to force the issue: drop the guard, ignore the shots and
                # walk the opponent down for a fixed window.
                self.patience = 0.
                self.force = AI_PUSH_TIME
                self.guard = 0.
                self.crouch = False
                self.retreat = 0.
                self.rush = AI_PUSH_TIME
                self.plan = None
                self.clock = max(self.clock, .5)
                forcing = True

        # --- defence: answer with the stance that actually stops the move ---
        # 反应延迟先行：目击威胁（落雷圈 / 新弹丸 / 对手新出招）要过 react 秒
        # 才做防守动作，期间照常挨打——这是"普通档防不住大招"的物理根源
        # （大招前摇 14 帧 < 普通档反应 14~26 帧），而不是概率表面的差异。
        p = self._profile()
        # --- rhythm read: 机械连打的节奏预判 ---
        # 沿触发：一轮连打节奏只掷一次骰（prejudge_p），失败照常挨打——
        # 预判不是全知；节奏断开或预判窗口到期后，对下一波连打重新判定。
        spamming = (len(self.press_marks) >= SPAM_MARKS
                    and self.t - self.press_marks[-SPAM_MARKS] <= SPAM_WINDOW)
        if self.rhythm_guard <= 0. and spamming and not self.rhythm_last:
            self.rhythm_last = True
            if random.random() < p["prejudge_p"]:
                self.rhythm_guard = AI_RHYTHM_GUARD
        elif not spamming:
            self.rhythm_last = False   # 节奏断开，下一波连打重新判定
        strike_move = None
        strike = self._incoming_strike()
        if strike is not None:
            # 目击与判定不依赖可行动状态：看到圈、反应到点就 roll（决定不需要
            # 等自己打完拳），走位键在能动的帧应用。roll 失败则保持原节奏，
            # 表现为"没注意到雷"。
            if id(strike) != self.strike_mark:
                self.strike_mark = id(strike)
                self.react_shot = self._react_time()
                self.strike_dodge = None
            if self.react_shot <= 0 and self.strike_dodge is None:
                self.strike_dodge = random.random() < p["strike_escape"]
            if self.strike_dodge:
                # 蹲防挡不住落雷：中止手头决策、封锁新计划，走出预警圈是
                # 唯一解——走位必须独占执行权，否则会被射击/近攻循环抢断。
                strike_move = "right" if me["x"] >= strike["x"] else "left"
                if self.plan and not self.plan.get("knockdown"):
                    self.plan = None
                self.rush = 0.
                self.retreat = 0.
        elif free and not forcing and self.guard <= 0:
            if self.rhythm_guard > 0. and distance < 190 and me["grounded"]:
                # 预判举盾：读出了连打节奏，不等起手直接架势迎接。站防为主，
                # 下段踢与投技依然是破解它的正解——博弈保留给玩家。
                self.guard = max(self.guard, AI_RHYTHM_GUARD)
                self.crouch = False
            if (not self.plan and self.rhythm_guard <= 0. and me["grounded"]
                    and me["cooldown"] <= 0
                    and self._attack_phase(foe) == "recovery"
                    and distance <= ATTACKS["punch"].reach + 20
                    and random.random() < p["punish_p"]):
                # 恢复帧窗口反击：对手还在收招、自己已经恢复行动——不等走位
                # 决策，直接插最快一拳打断连打节奏。连段疲劳与硬直衰减造出的
                # 窗口就该这样兑现；反打期间封锁防守决策，别举着盾挨近拳。
                self.plan = None
                self._queue_plan(["punch"], 0.9)
                self.react_atk = max(self.react_atk, 0.5)
            shot = self._incoming_shot()
            if shot is not None:
                if id(shot) != self.shot_mark:
                    # Not every shot is read perfectly, so zoners still land hits.
                    # 弹丸躲避是当帧反应、只靠概率分档：持续的弹幕压制必须能
                    # 把 AI 压进持续蹲防，从而攒满耐心强制压上（对射循环会让
                    # patience 永远攒不满）。
                    self.shot_mark = id(shot)
                    self.shot_dodge = random.random() < p["dodge"]
                if self.shot_dodge:
                    # Ducking beats high shots; crouch guard stops low ones.
                    self.guard = .25
                    self.crouch = True
            elif foe["attack_kind"] and distance < 190 and self.react_atk <= 0:
                kind = foe["attack_kind"]
                a_spec = ATTACKS.get(kind)
                if self.atk_defend is None:
                    # 每招只判定一次：反应过来后决定防不防、姿势对不对；
                    # 判了不防就硬吃这一招，不会反复重 roll 变成必定格挡。
                    if kind == "grab":
                        self.atk_defend = "retreat"
                    elif (a_spec is not None
                          and distance <= a_spec.reach + 30
                          and random.random() < p["evade_p"]):
                        # 高档防御走位：明知对手起手且在攻击范围内，先拉开
                        # 再谈格挡——站着硬挡是中档以下的技术。spacing 接管
                        # 撤退；对手收招后恢复 comfort 节奏。
                        self.atk_defend = "evade"
                    elif random.random() < p["guard_p"]:
                        crouch = kind in CROUCH_ATTACKS
                        if random.random() < p["wrong_stance"]:
                            crouch = not crouch   # 判错段位，姿势反了
                        self.atk_defend = "crouch" if crouch else "stand"
                    else:
                        self.atk_defend = "none"
                if self.atk_defend == "retreat":
                    if (me["grounded"] and me["cooldown"] <= 0 and not self.plan
                            and random.random() < p["backdash_p"]):
                        # 后撤步（双击后方）：一次位移 75 像素，比普通慢退更能
                        # 撤出抓取范围。
                        self._queue_plan(["back", "gap", "back"], 1.0)
                    else:
                        # Grabs beat both guards, so make space instead.
                        self.retreat = max(self.retreat, .35)
                elif self.atk_defend in ("crouch", "stand"):
                    self.guard = AI_GUARD_TIME
                    self.crouch = self.atk_defend == "crouch"

        # 决定躲避雷圈期间封锁新决策：走位独占执行权。roll 失败（没反应过来）
        # 则不封锁，AI 保持原节奏继续手头的事——那才是"没注意到雷"的样子。
        strike_lock = strike is not None and self.strike_dodge is True

        cpu = {"left": False, "right": False,
               "punch": False, "kick": False, "jump": False,
               "guard": self.guard > 0, "grab": False,
               "down": self.guard > 0 and self.crouch,
               "projectile": False}

        # 走位中断（受击 / 出招 / 倒地 / plan 编排接管）即松键：把当前方向记档
        # 进方向锁，恢复后的再次起步仍要等满 AI_MIN_STEP——格挡硬直或短 plan
        # 后立即起步同样会凑出双击沿而误触冲刺。
        if (not free or self.plan) and self.move_dir != 0:
            self.dir_exit[self.move_dir] = self.t
            self.move_dir = 0

        # --- spacing: zone at range, rush a wounded opponent, back off on KD ---
        # plan（脚本化动作，如前冲双击 / 跳跃漂移）执行期间 spacing 让位：走位键
        # 会覆盖 gap 步的中立帧，令双击永远凑不出第二次按下沿，冲刺退化成慢跑。
        if free and not self.plan:
            want = 0
            if foe.get("knocked"):
                if distance < 230:
                    want = -1
            elif forcing:
                if distance > 46:
                    want = 1
            elif self.retreat > 0:
                if distance < 300:
                    want = -1
            elif self.atk_defend == "evade" and foe["attack_kind"] and distance < 260:
                # 防御走位（evade_p 判定过）：对手还在挥，拉开；收招即恢复
                # comfort 节奏。260 上限防止对手长距离招式把 AI 一路追进墙角。
                want = -1
            elif self.guard <= 0:
                if self.rush > 0:
                    low, high = 46., 96.
                else:
                    low, high = self._comfort(me, foe)
                if distance > high:
                    want = 1
                elif distance < low and 130 < me["x"] < 870:
                    # Do not kite straight into the corner.
                    want = -1
                elif self.rush <= 0 and self.nudge <= 0:
                    # 带内拉扯：完全站定一小段后随机小步进退（向对手为主，
                    # 逼近压到带下沿自然触发退回，形成真实的推拉节奏）。
                    # 频率随档位上调；起步走统一方向锁，不会凑出双击误触冲刺。
                    if random.random() < dt * (0.8, 1.2, 1.6, 2.2)[tier]:
                        want = 1 if random.random() < .65 else -1
                        self.nudge = .22
            # 方向锁：切换方向（含急停）时旧方向键自然松开；再次起步前必须
            # 松开满 step_lock（低档 0.26s > 双击窗口，高档收紧换灵巧），否则
            # 拉锯抖动凑出的双击会触发无意冲刺。
            if want != self.move_dir:
                lock = p["step_lock"]
                if (want == 0 or
                        self.t - self.dir_exit.get(want, -9.) >= lock):
                    if self.move_dir != 0:
                        self.dir_exit[self.move_dir] = self.t
                    self.move_dir = want
            if self.move_dir == 1:
                cpu[toward] = True
            elif self.move_dir == -1:
                cpu[away] = True

        # 落雷走位优先于一切移动键：先清反方向，避免"左+右"互相抵消原地冻结。
        if strike_move:
            cpu["left"] = cpu["right"] = False
            cpu[strike_move] = True

        # --- watchdog: no plan, no movement, no attack for too long ---
        # 有计划 / 前压 / 撤退 / 格挡躲避 / 本帧有位移或攻击键都算行动（被弹幕
        # 压制时蹲防是合理防守，不该被看门狗打断）；雷圈走位期间也不抢戏。
        # 超时强制出手，是残血站桩等一切活锁的总兜底。
        if (free and not strike_lock and not self.plan and self.force <= 0
                and self.retreat <= 0 and self.rush <= 0 and self.guard <= 0):
            if (cpu["left"] or cpu["right"] or cpu["punch"] or cpu["kick"]
                    or cpu["jump"] or cpu["grab"] or cpu["projectile"]):
                self.idle = 0.
            else:
                self.idle += dt
                if self.idle >= self._profile()["watchdog"]:
                    self.idle = 0.
                    self._watchdog_act(me, foe, distance)

        # A floored or staggered AI cannot act; drop any queued plan and
        # stagger its next decision so both AIs never re-attack in lockstep.
        if me["stun"] > 0 or me["knocked"]:
            if self.plan:
                self._abort_plan(.35, .9)
            if me["knocked"] and me["stun"] <= 0:
                # The knockdown timer is over: any command stands the fighter
                # up, so the AI must not stay floored forever.
                cpu[toward if distance > 150 else away] = True
            return cpu
        if (foe.get("knocked") and self.plan
                and not self.plan.get("knockdown")):
            # The opponent just got floored: swap to the spacing plan.
            self._abort_plan(.1, .3)
        if self.plan:
            extra = self._run_plan(me, foe, distance, dt)
            if extra is not None:
                cpu.update(extra)
                return cpu
            if self.plan:
                return cpu
        if self.guard > 0:
            return cpu
        # 困难 / 地狱：能量足够、对手站在大招范围内时，当帧直接释放，不再等
        # 决策冷却或随机判定。
        if (tier >= 2 and free and self._super_can_hit(me, foe)):
            self._queue_super(me)
            self.patience = 0.
            return cpu
        # 地狱难度：对手出招期间就读帧应对（抓取后撤、挥空前压、收招帧反打），
        # 而不是像其他难度那样等对手停手后才做决策。
        if (self._hell() and free and self._hell_react(me, foe, distance)):
            return cpu
        # Only start a new plan when the opponent is not swinging right now,
        # and never while dodging a strike ring (walking out takes priority).
        if (not foe["attack_kind"] and not strike_lock and self.clock > .42
                and self._start_plan()):
            return cpu
        return cpu


# ----------------------------------------------------------- character plans
# 角色专属战术注册表：键 = char_id，值 = 战术函数，签名统一
# (controller, me, foe, distance) -> bool。新角色的"绝活"写成一个函数注册
# 进来即可，AIController 主流程不用再改。

def _plan_yellow_oki(self, me, foe, distance):
    """奔雷浪客：落雷压起身——对手倒地无法位移，雷环落在其起身点，1 秒后命中。"""
    styled = CHARACTERS.get(me.get("char_id"), CHARACTERS["red_scarf"])
    spec = me.get("buff_spec") or styled.get("buff")
    cost = (spec or {}).get("energy", 30)
    if foe.get("knocked") and me["energy"] >= cost:
        # 落雷压起身：雷击从出招到落地约 "延迟 + 下坠耗时" 秒，且倒地期间
        # 的敌人无视雷击（Invulnerable）。所以等到对手倒地计时快结束时再
        # S S U，让雷砸在起身点，而不是打在无敌帧上。
        travel = (float(spec.get("delay", 1.0))
                  + float(spec.get("height", 620.)) / float(spec.get("speed", 3375.)))
        if foe.get("stun", 0.) <= travel:
            # knockdown=True 避免"对手倒地就切走"的通用逻辑中止本计划；
            # 符印允许空中施放，结尾用 cast（不要求 grounded）触发放雷。
            self._queue_plan(["down", "gap", "down", "gap", "cast"],
                             1.6, knockdown=True)
        # 起身这一拍由落雷接管，绝不让通用"后撤+起身弹"兜底。
        return True
    return False


def _plan_blue_rush_super(self, me, foe, distance):
    """寒霜游侠：突进大招当位移——透视后交叉斩（在射程内）或纯冲刺逼近（射程外）。"""
    styled = CHARACTERS.get(me.get("char_id"), CHARACTERS["red_scarf"])
    super_spec = me.get("super_spec") or styled.get("super")
    reach = float(me.get("super_distance", 0.))
    if (super_spec and me["energy"] >= super_spec.energy and
            me.get("super_kind") == "rush_slash" and
            90 < distance <= 400 and reach and me["cooldown"] <= 0):
        # 尚未进入近身范围就交突进大招：卡射程交叉斩、超出射程则位移逼近。
        self._queue_super(me)
        return True
    return False


CHARACTER_PLANS = {
    "yellow_cape": _plan_yellow_oki,
    "blue_headband": _plan_blue_rush_super,
}


# ------------------------------------------------------- signature combos
# 专属连招（角色特色技）的时机函数注册表，键 = char_id，签名与
# CHARACTER_PLANS 一致：(controller, me, foe, distance) -> bool。与
# CHARACTER_PLANS 不同的是返回值语义：True 只表示"局面合适"，由 _try_combo
# 统一掷骰（combo_p）后再排队，这里绝不能自行 _queue_combo。难度层
# （combo_s / combo_p、能量、大招优先）已在 _try_combo 把关。新角色写好
# combo_motion 并注册一个时机函数即可；不注册则永远不会用专属技
# （能量只花在大招上）。

def _plan_red_buff(self, me, foe, distance):
    """愤怒的普通人：素质三连——中近距离点燃双拳再压上，接下来三拳各
    附加 50 伤害；三连在身时不重复施放。远处不点：拉扯中开 buff 等于
    提前告诉对手我要冲了。"""
    if me.get("buff_charges"):
        return False
    return distance <= 240


def _plan_blue_shadow(self, me, foe, distance):
    """冷静的普通人：冰千年杀——潜行 1 秒后瞬移至对手脚下，出手距离
    无关。对手倒地是标准压起身（起身点即落点）；站着的对手当全图偷袭；
    腾空的对手会落空，不浪费能量。"""
    return bool(foe.get("knocked") or foe["grounded"])


def _plan_yellow_bolt(self, me, foe, distance):
    """张扬的普通人：落雷——压起身由 CHARACTER_PLANS 的 oki 计划负责，
    这里补拉锯骚扰：雷圈画在站立对手脚下，1 秒后砸落。贴脸不如直接
    连段，太近不放。"""
    return not foe.get("knocked") and foe["grounded"] and distance >= 100


def _plan_gray_shield(self, me, foe, distance):
    """上班的普通人：晚高峰警告——残血保命，或对手能量满（大招威胁）
    时举盾。盾还在身上时不重复施放。"""
    if me.get("shield", 0) > 0:
        return False
    ratio = me["hp"] / max(1., float(me.get("hp_max", DEFAULT_HP)))
    return ratio <= .5 or foe.get("energy", 0.) >= 100.


COMBO_PLANS = {
    "red_scarf": _plan_red_buff,
    "blue_headband": _plan_blue_shadow,
    "yellow_cape": _plan_yellow_bolt,
    "gray_tie": _plan_gray_shield,
}
