import math

from core.chat_blob import ChatBlob
from core.decorators import instance, command
from core.command_param_types import Any, Int, Decimal
import os
import re
import json

from core.dict_object import DictObject


@instance()
class SpecialsController:
    def __init__(self):
        pass

    def inject(self, registry):
        self.db = registry.get_instance("db")
        self.text = registry.get_instance("text")
        self.items_controller = registry.get_instance("items_controller")
        self.command_alias_service = registry.get_instance("command_alias_service")

    def start(self):
        self.command_alias_service.add_alias("aimshot", "aimedshot")
        self.command_alias_service.add_alias("as", "aimedshot")
        self.command_alias_service.add_alias("inits", "weapon")
        self.command_alias_service.add_alias("specials", "weapon")

    @command(command="aggdef", params=[Decimal("weapon_attack"), Decimal("weapon_recharge"), Int("init_skill")], access_level="all",
             description="Show agg/def information for a particular weapon and init skill")
    def aggdef_cmd(self, request, weapon_attack, weapon_recharge, init_skill):
        init_result = self.get_init_result(weapon_attack, weapon_recharge, init_skill)
        bar_position = init_result * 8 / 100

        inits_full_agg = self.get_inits_needed(100, weapon_attack, weapon_recharge)
        inits_neutral = self.get_inits_needed(87.5, weapon_attack, weapon_recharge)
        inits_full_def = self.get_inits_needed(0, weapon_attack, weapon_recharge)

        blob = "Attack: <highlight>%.2f<end> seconds\n" % weapon_attack
        blob += "Recharge: <highlight>%.2f<end> seconds\n" % weapon_recharge
        blob += "Init Skill: <highlight>%d<end>\n\n" % init_skill
        blob += "You must set you AGG/DEF bar at <highlight>%d%% (%.2f)<end> to wield your weapon at 1/1.\n\n" % (int(init_result), bar_position)
        blob += "Init needed for max speed at Full Agg (100%%): <highlight>%d<end>\n" % inits_full_agg
        blob += "Init needed for max speed at Neutral (88%%): <highlight>%d<end>\n" % inits_neutral
        blob += "Init needed for max speed at Full Def (0%%): <highlight>%d<end>\n\n" % inits_full_def
        blob += "Note that at the neutral position (88%), your attack and recharge time will match that of the weapon you are using.\n\n"
        blob += "Based on the !aggdef command from Budabot, which was based upon a RINGBOT module made by NoGoal(RK2) and modified for Budabot by Healnjoo(RK2)"

        return ChatBlob("Agg/Def Results", blob)

    @command(command="aimedshot", params=[Decimal("weapon_attack"), Decimal("weapon_recharge"), Int("aimed_shot_skill")], access_level="all",
             description="Show aimedshot information for a particular weapon and init skill")
    def aimedshot_cmd(self, request, weapon_attack, weapon_recharge, aimed_shot_skill):
        as_info = self.get_aimed_shot_info(weapon_attack, weapon_recharge, aimed_shot_skill)

        blob = "Attack: <highlight>%.2f<end> seconds\n" % weapon_attack
        blob += "Recharge: <highlight>%.2f<end> seconds\n" % weapon_recharge
        blob += "Aimed Shot Skill: <highlight>%d<end>\n\n" % aimed_shot_skill
        blob += "Aimed Shot Multiplier: <highlight>1 - %dx<end>\n" % as_info.multiplier
        blob += "Aimed Shot Recharge: <highlight>%d<end> seconds\n\n" % as_info.recharge
        blob += "You will need <highlight>%d<end> Aimed Shot Skill to cap your recharge at <highlight>%d<end> seconds." % (as_info.skill_cap, as_info.hard_cap)

        return ChatBlob("Aimed Shot Results", blob)

    def get_init_result(self, weapon_attack, weapon_recharge, init_skill):
        if init_skill < 1200:
            attack_calc = (((weapon_attack - (init_skill / 600)) - 1) / 0.02) + 87.5
            recharge_calc = (((weapon_recharge - (init_skill / 300)) - 1) / 0.02) + 87.5
        else:
            attack_calc = (((weapon_attack - (1200 / 600) - ((init_skill - 1200) / 600 / 3)) - 1) / 0.02) + 87.5
            recharge_calc = (((weapon_recharge - (1200 / 300) - ((init_skill - 1200) / 300 / 3)) - 1) / 0.02) + 87.5

        if attack_calc < recharge_calc:
            init_result = recharge_calc
        else:
            init_result = attack_calc

        init_result = min(init_result, 100)  # max of 100
        init_result = max(init_result, 0)  # min of 0

        return init_result

    def get_inits_needed(self, init_result, weapon_attack, weapon_recharge):
        inits_attack = (((init_result - 87.5) * 0.02) + 1 - weapon_attack) * -600
        inits_recharge = (((init_result - 87.5) * 0.02) + 1 - weapon_recharge) * -300

        if inits_attack > 1200:
            inits_attack = ((((init_result - 87.5) * 0.02) + 1 - weapon_attack + 2) * -1800) + 1200

        if inits_recharge > 1200:
            inits_recharge = ((((init_result - 87.5) * 0.02) + 1 - weapon_attack + 4) * -900) + 1200

        if inits_attack < inits_recharge:
            return inits_recharge
        else:
            return inits_attack

    def get_aimed_shot_info(self, weapon_attack, weapon_recharge, aimed_shot_skill):
        result = DictObject()
        result.multiplier = round(aimed_shot_skill / 95)
        result.hard_cap = math.floor(weapon_attack + 10)
        result.skill_cap = math.ceil((4000 * weapon_recharge - 1100) / 3)

        as_recharge = math.ceil((weapon_recharge * 40) - (aimed_shot_skill * 3 / 100) + weapon_attack - 1)
        if as_recharge < result.hard_cap:
            as_recharge = result.hard_cap

        result.recharge = as_recharge

        return result
