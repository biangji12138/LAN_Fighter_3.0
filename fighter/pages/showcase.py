"""Character showcase screen: full-body art plus skill/super/combo cards."""
import pygame

from .. import assets
from ..attacks import ATTACKS
from ..characters import CHARACTERS
from ..combat import DEFAULT_HP
from ..theme import W, H, PANEL_HI, WHITE, MUTED, GOLD, shade


class ShowcasePage:
    """Character showcase page.

    Mixin for :class:`fighter.ui.GameApp`; no ``__init__`` of its own. Expects
    the host to provide ``screen``, ``now``, ``showcase_cid`` and the shared
    helpers ``header`` / ``panel`` / ``rect`` / ``text`` / ``key_pills`` /
    ``button`` / ``draw_avatar`` / ``fighter_art``.
    """

    def open_showcase(self, char_id):
        self.showcase_cid = char_id
        self.page = "showcase"

    def back_from_showcase(self):
        self.page = "select"

    def showcase_page(self):
        cid = getattr(self, "showcase_cid", "red_scarf")
        style = CHARACTERS.get(cid, CHARACTERS["red_scarf"])
        accent = style['accent']
        attack = style.get('super') or ATTACKS['super']
        combo = style.get('combo') or {}
        skill = style['projectile']
        # ---------- accent wash behind the stage ----------
        wash = pygame.Surface((W, H), pygame.SRCALPHA)
        for step in range(18):
            pygame.draw.circle(wash, (*accent, 4), (332, 372), 340 - step * 16)
        self.screen.blit(wash, (0, 0))
        self.header("角色展示", "双击角色卡进入 · 右侧资料 / 大招与专属连招按键")
        # ---------- left: full-body art ----------
        self.panel(107, 152, 450, 452, (16, 25, 41), 18, (48, 66, 96), accent)
        stage_glow = pygame.Surface((430, 430), pygame.SRCALPHA)
        for step in range(14):
            pygame.draw.circle(stage_glow, (*accent, 4), (270, 232), 205 - step * 14)
        self.screen.blit(stage_glow, (117, 162))
        art = assets.fit("characters", style['id'], (400, 342))
        if art is not None:
            self.screen.blit(art, art.get_rect(center=(332, 330)))
        else:
            figure = self.fighter_art(style['id'], (300, 358),
                                      walk=self.now * 2.4)
            self.screen.blit(figure, (332 - 150, 168))
        pygame.draw.ellipse(self.screen, (66, 92, 128), (179, 522, 306, 14), 2)
        pygame.draw.ellipse(self.screen, (34, 48, 72), (205, 524, 254, 10))
        self.text(style['name'], 332, 566, 30, accent, True, shadow=True)
        # ---------- right: profile ----------
        self.panel(577, 152, 526, 452, (20, 30, 48), 18, (48, 66, 96))
        self.draw_avatar(cid, 633, 200, 54, accent)
        self.text(style['name'], 675, 176, 38, accent, shadow=True)
        self.text(style.get('identity', '格斗家'), 675, 222, 18, MUTED)
        self.text("性别：" + style.get('gender', '未知'), 607, 252, 20, WHITE)
        self.text(f"血量：{style.get('health', DEFAULT_HP)} · 移动速度：{style.get('move_speed', 260)}",
                  607, 280, 20, WHITE)
        self.text(style.get('bio', ''), 607, 308, 16, MUTED)
        pygame.draw.line(self.screen, (48, 64, 92), (607, 334), (1073, 334), 1)
        # Skill cards: name, effect, damage, energy cost and key input.
        step_attacks = {"J": "punch", "K": "kick", "I": "grab",
                        "S+J": "crouch_punch", "S+K": "low_kick",
                        "空中 J": "jump_punch"}
        combo_damage = combo_energy = 0
        for step in combo.get('steps', ()):
            if step == "J+K":
                combo_damage += attack.damage
                combo_energy += attack.energy
            elif step in step_attacks:
                combo_damage += ATTACKS[step_attacks[step]].damage
        buff = style.get('buff')
        if buff:
            if buff.get('kind') == 'strike':
                # Delayed spell: one bolt, no buff counters.
                combo_damage = int(buff.get('damage', 0))
                combo_energy = int(buff.get('energy', 0))
            else:
                combo_damage = buff['bonus'] * buff['charges']
                combo_energy = buff.get('energy', 0)
        combo_atk = combo.get('attack')
        if combo_atk and not buff:
            combo_damage = combo_atk.damage
            combo_energy = combo_atk.energy
        # 没有招式数据的连招（瞬发、不进入招式帧）把能耗直接写在 combo 里。
        if combo.get('energy') is not None:
            combo_energy = int(combo['energy'])
        radius = float(style.get('super_radius', 0.))
        if radius:
            super_effect = f"自身两侧 {int(radius)} 范围同时命中，击倒 2 秒"
        elif style.get('super_kind') == 'rush_slash':
            super_effect = (f"突进 {int(style.get('super_distance', 0))} 近身绕后，"
                            f"{attack.hits} 段斩击")
        else:
            super_effect = "向前突进一击，命中击飞"
        # 角色自定义大招描述优先，未填则回退到按类型生成的文案。
        super_effect = style.get('super_desc') or super_effect
        super_keys = style.get('super_keys')
        if not super_keys:
            super_keys = ("S", "S", "J+K") if style.get('super_command') else ("J+K",)
        if skill.get('style') == 'beam':
            skill_effect = "高速蓝色冰束线，站立为高位、下蹲为低位"
        elif skill.get('style') == 'wave':
            skill_effect = "高速横向波，站立为高位、下蹲为低位"
        else:
            skill_effect = "发射远程弹道，站立为高位、下蹲为低位"
        # 角色自定义小技能描述优先。
        skill_effect = style.get('skill_desc') or skill_effect
        combo_stats = f"伤害 {combo_damage} · 能耗 {combo_energy}"
        if buff and buff.get('kind') != 'strike':
            combo_stats = f"附加伤害 {combo_damage} · 能耗 {combo_energy}"
        combo_effect = style.get('combo_desc') or combo.get('note', '')
        super_stats = f"伤害 {attack.damage} · 能耗 {attack.energy}"
        if style.get('super_kind') == 'grab_pummel':
            super_stats = f"伤害 40×4~10（最多 {attack.damage}） · 能耗 {attack.energy}"
        cards = (
            ("小技能", skill['name'], skill['color'], skill_effect,
             f"伤害 {skill['damage']} · 能耗 0", ("U", "S+U")),
            ("大招", attack.name, accent, super_effect,
             super_stats, super_keys),
        )
        cards += (("专属连招", combo.get('name', ''), accent, combo_effect,
                   combo_stats, combo.get('steps', ("J", "K"))),)
        for idx, (label, name, color, effect, stats, keys) in enumerate(cards):
            top = 342 + idx * 87
            self.rect(607, top, 466, 78, shade(PANEL_HI, .82), 12, (44, 60, 88))
            self.text(label, 623, top + 8, 16, GOLD)
            self.text(name, 695, top + 6, 20, color, shadow=True)
            # Key caps sit on the title row, right-aligned against a fixed 780
            # column so they never spill past the panel edge (was 806 @16px).
            self.key_pills(keys, 835, top + 16, color, 14,
                           "/" if label == "小技能" else "→")
            self.text("效果 " + effect, 623, top + 34, 15, MUTED)
            self.text(stats, 623, top + 56, 15, MUTED)
        self.button("返回选角", (115, 620, 170, 48), self.back_from_showcase, PANEL_HI)
