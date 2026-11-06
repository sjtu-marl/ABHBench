from core.transform import auto_yield_class
from DBHHelper.flow import DBHFlow, E

# THE HOSTAGE

# 0: Defined by choices
# 1: CONNER FAILED TO REACH DEVIANT IN TIME
# 2: CONNER LEAPT FOR EMMA AND FELL
# 3: SNIPERS SHOT DEVIANT
# 4: CONNOR DIED PROTECTING EMMA
# 5: DEVIANT SHOT CONNOR
# 6: CONNOR SHOT DEVIANT


@auto_yield_class
class Flow(DBHFlow):
    chapter_number = 1

    def setup(self):
        super().setup()
        self.status = {
            "GUN": False,
            "NEAR": False,
            "key_options": [
                "POSSIBLE CAUSE",
                "EMMA AND YOU",
            ],
            "other_options": [
                "REALISTIC",
                "BLAMING",
                "SYMPATHETIC",
                "DEFECTIVE",
            ],
        }

    def graph(self):
        self.START | E >> self.MISSION_START | E >> self.FRAME | E >> self.FISH
        [
            self.FISH | E >> self.SAVE_FISH,
            self.FISH | E >> self.LEAVE_FISH,
        ]
        self.MOTHER << E | self.SAVE_FISH | E | self.LEAVE_FISH
        (
            self.MOTHER
            | E >> self.CAPT_ALLEN
            | E >> self.GUN_CASE
            | E >> self.ROOM
            | E >> self.FATHER
            | E >> self.CAUSE
            | E >> self.COP
            | E >> self.GUN
        )
        [
            self.GUN | E >> self.GUN_TAKE,
            self.GUN | E >> self.GUN_PUTBACK,
        ]
        self.OUTSIDE << E | self.GUN_TAKE | E | self.GUN_PUTBACK
        self.OUTSIDE | E >> self.CONFRONT
        [
            self.CONFRONT | E >> self.ARMED | E >> self.POSSIBLE_CAUSE,
            self.CONFRONT | E >> self.POSSIBLE_CAUSE,
        ]
        (
            self.POSSIBLE_CAUSE
            | E >> self.INJURED_COP
            | E >> self.NEAR_DEVIANT_1
            | E >> self.HELI
            | E >> self.NEAR_DEVIANT_2
        )
        [
            self.NEAR_DEVIANT_2 | E >> self.NEAR_DEVIANT_3,
            self.NEAR_DEVIANT_2 | E >> self.BLUFF,
        ]
        [
            self.NEAR_DEVIANT_3 | E >> self.USE_GUN,
            self.NEAR_DEVIANT_3 | E >> self.SACRIFICE_SELF | E >> self.ENDING_4,
            self.NEAR_DEVIANT_3 | E >> self.NEAR_DEVIANT_4,
            self.NEAR_DEVIANT_3 | E >> self.REFUSE | E >> self.QTE,
        ]
        [
            self.NEAR_DEVIANT_4 | E >> self.USE_GUN,
            self.NEAR_DEVIANT_4 | E >> self.SACRIFICE_SELF | E >> self.ENDING_4,
            self.NEAR_DEVIANT_4 | E >> self.REASSURE | E >> self.ENDING_3,
            self.NEAR_DEVIANT_4 | E >> self.TRUTH | E >> self.QTE,
        ]
        [
            self.BLUFF | E >> self.MOVE_CLOSER | E >> self.QTE,
            self.BLUFF | E >> self.GIVE_UP | E >> self.NEAR_DEVIANT_3,
        ]
        [
            self.USE_GUN | E >> self.EXECUTE | E >> self.ENDING_6,
            self.USE_GUN | E >> self.INTIMIDATE,
        ]
        [self.INTIMIDATE | E >> self.ENDING_5, self.INTIMIDATE | E >> self.ENDING_6]
        [
            self.QTE | E >> self.NO_QTE_RUN | E >> self.ENDING_1,
            self.QTE | E >> self.QTE_RUN | E >> self.ENDING_2,
        ]
        (
            self.FLOWCHART << E
            | self.ENDING_1
            | E
            | self.ENDING_2
            | E
            | self.ENDING_3
            | E
            | self.ENDING_4
            | E
            | self.ENDING_5
            | E
            | self.ENDING_6
        )
        self.FLOWCHART | E >> self.END

    def MISSION_START(self):
        self.dbhh.set_default_game_speed(self.cfg["DEFAULT_GAME_SPEED"])
        self.dbhh.enter_chapter("CHAPTER")
        self.dbhh.wait_for_cutscene("CS_MISSION_START")

    def FRAME(self):
        self.dbhh.to_pos_ui("WP_FRAME")
        self.dbhh.interact("IT_FRAME_PICKUP")
        self.dbhh.wait_for_cutscene_ui("CS_FRAME_PICKUP")
        self.dbhh.exp_rj_interact("IT_FRAME_PUT")
        self.dbhh.wait_for_cutscene("CS_FRAME_PUT")

    def FISH(self):
        self.dbhh.to_pos("WP_FISH_1")
        self.dbhh.to_pos_ui("WP_FISH_2")
        self.dbhh.interact("IT_FISH_DOWN")
        self.dbhh.wait_for_cutscene_ui("CS_FISH_DOWN")
        self.get_choice(press_button=False)

    def SAVE_FISH(self):
        self.dbhh.exp_rj_interact("IT_SAVE_FISH")
        self.dbhh.wait_for_cutscene("CS_SAVE_FISH")

    def LEAVE_FISH(self):
        self.dbhh.interact("IT_LEAVE_FISH")
        self.dbhh.wait_for_cutscene("CS_LEAVE_FISH")

    def MOTHER(self):
        self.dbhh.to_pos("WP_MOTHER")
        self.dbhh.wait_for_cutscene("CS_MOTHER")

    def CAPT_ALLEN(self):
        self.dbhh.to_pos("WP_CAPT_ALLEN_1")
        self.dbhh.to_pos("WP_CAPT_ALLEN_2")
        self.dbhh.to_pos_ui("WP_CAPT_ALLEN_3")
        self.dbhh.vg_press_button("BT_CAPT_ALLEN")
        self.dbhh.wait_for_cutscene_ui("CS_CAPT_ALLEN_1")
        CHOICES = {
            "Y": "DEVIANT'S NAME",
            "X": "DEVIANT'S BEHAVIOR",
            "B": "EMOTIONAL SHOCK",
            "A": "DEACTIVATION CODE",
        }
        CHOICE = self.get_choice("CAPT_ALLEN_1", CHOICES=CHOICES)
        self.dbhh.wait_for_cutscene_ui("CS_CAPT_ALLEN_2")
        if CHOICE == "A":
            CHOICES = {
                "Y": "DEVIANT'S BEHAVIOR",
                "B": "EMOTIONAL SHOCK",
                "A": "DEVIANT'S NAME",
            }
        else:
            CHOICES.pop(CHOICE)
            CHOICES = dict(zip(["Y", "B", "A"], CHOICES.values()))
        CHOICE = self.get_choice("CAPT_ALLEN_2", CHOICES=CHOICES)
        self.dbhh.wait_for_cutscene("CS_CAPT_ALLEN_3")

    def GUN_CASE(self):
        self.dbhh.to_pos_ui("WP_GUN_CASE")
        self.dbhh.interact("IT_GUN_CASE")
        self.dbhh.wait_for_cutscene("CS_GUN_CASE")
        self.dbhh.to_ip("IP_GUN_CASE_1")
        self.dbhh.to_ip("IP_GUN_CASE_2")
        self.dbhh.vg_press_button("BT_GUN_CASE_1")
        self.dbhh.timeline_slide("TL_GUN_CASE_1")
        self.dbhh.vg_press_button("BT_GUN_CASE_2")
        self.dbhh.wait_for_cutscene("CS_GUN_CASE_FINISH")

    def ROOM(self):
        self.dbhh.to_pos("WP_ROOM_1")
        self.dbhh.to_pos_ui("WP_ROOM_2")
        self.dbhh.exp_rj_interact("IT_ROOM_1")
        self.dbhh.wait_for_cutscene_ui("CS_ROOM_1")
        self.dbhh.interact("IT_ROOM_2")
        self.dbhh.wait_for_cutscene("CS_ROOM_2")
        self.dbhh.to_pos_ui("WP_ROOM_3")
        self.dbhh.exp_rj_interact("IT_ROOM_3")
        self.dbhh.wait_for_cutscene("CS_ROOM_3")

    def FATHER(self):
        self.dbhh.to_pos("WP_FATHER_1")
        self.dbhh.to_pos("WP_FATHER_2")
        self.dbhh.to_pos_ui("WP_FATHER_3")
        self.dbhh.interact("IT_FATHER_1")
        self.dbhh.wait_for_cutscene("CS_FATHER_1")
        self.dbhh.to_ip("IP_FATHER_1")
        self.dbhh.to_ip("IP_FATHER_2")
        self.dbhh.to_ip("IP_FATHER_3")
        self.dbhh.to_ip("IP_FATHER_4")
        self.dbhh.vg_press_button("BT_FATHER_1")
        self.dbhh.timeline_slide("TL_FATHER_1")
        self.dbhh.timeline_slide("TL_FATHER_2")
        self.dbhh.vg_press_button("BT_FATHER_2")
        self.dbhh.wait_for_cutscene("CS_FATHER_2")

    def CAUSE(self):
        self.dbhh.to_pos_ui("WP_CAUSE_1")
        self.dbhh.interact("IT_CAUSE_1")
        self.dbhh.wait_for_cutscene_ui("CS_CAUSE_1")
        self.dbhh.interact("IT_CAUSE_2")
        self.dbhh.wait_for_cutscene("CS_CAUSE_2")

    def COP(self):
        self.dbhh.to_pos("WP_COP_1")
        self.dbhh.to_pos_ui("WP_COP_2")
        self.dbhh.interact("IT_COP_1")
        self.dbhh.wait_for_cutscene("CS_COP_1")
        self.dbhh.to_ip("IP_COP_1")
        self.dbhh.to_ip("IP_COP_2")
        self.dbhh.to_ip("IP_COP_3")
        self.dbhh.vg_press_button("BT_COP_1")
        self.dbhh.timeline_slide("TL_COP_1")
        self.dbhh.timeline_slide("TL_COP_2")
        self.dbhh.timeline_slide("TL_COP_3")
        self.dbhh.vg_press_button("BT_COP_2")
        self.dbhh.wait_for_cutscene("CS_COP_2")

    def GUN(self):
        self.dbhh.to_pos("WP_GUN_1")
        self.dbhh.to_pos("WP_GUN_2")
        self.dbhh.to_pos_ui("WP_GUN_3")
        self.dbhh.exp_rj_interact("IT_GUN_1")
        self.dbhh.wait_for_cutscene_ui("CS_GUN_1")
        self.get_choice()

    def GUN_TAKE(self):
        self.status["GUN"] = True
        self.dbhh.interact("IT_GUN_TAKE")
        self.dbhh.wait_for_cutscene("CS_GUN_TAKE")

    def GUN_PUTBACK(self):
        self.status["GUN"] = False
        self.dbhh.exp_rj_interact("IT_GUN_PUTBACK")

    def OUTSIDE(self):
        self.dbhh.to_pos("WP_OUTSIDE_1")
        self.dbhh.exp_rj_interact("IT_OUTSIDE_1")
        self.dbhh.wait_for_cutscene_ui("CS_OUTSIDE_1")
        # Know name of the deviant
        CHOICE = "A"
        self.dbhh.vg_press_button(button=CHOICE)

    def CONFRONT(self):
        self.dbhh.to_pos_only_ui("WP_CONFRONT_1")
        self.get_choice()
        if self.status["GUN"]:
            self.next_branch = "ARMED"
        else:
            self.next_branch = "POSSIBLE_CAUSE"

    def ARMED(self):
        self.dbhh.to_pos_only_ui("WP_INJURED_COP_1")
        CHOICE = self.get_choice()
        if CHOICE == "A":
            self.status["GUN"] = False

    def POSSIBLE_CAUSE(self):
        self.dbhh.to_pos_only_ui("WP_INJURED_COP_2")
        self.get_choice()
        if self.last_choice in self.status["key_options"]:
            self.status["key_options"].remove(self.last_choice)
        if self.last_choice in self.status["other_options"]:
            self.status["other_options"].remove(self.last_choice)

    def INJURED_COP(self):
        self.dbhh.to_pos_ui("WP_INJURED_COP_3")
        self.dbhh.exp_rj_interact("IT_INJURED_COP")
        self.dbhh.wait_for_cutscene_ui("CS_INJURED_COP_1")
        self.get_choice()

    def NEAR_DEVIANT_1(self):
        self.dbhh.wait_for_cutscene_ui("CS_INJURED_COP_2")
        if len(self.status["key_options"]) == 2:
            CHOICES = dict(
                zip(
                    ["Y", "X", "B", "A"],
                    self.status["key_options"]
                    + [
                        self.status["other_options"][0],
                        self.status["other_options"][-1],
                    ],
                )
            )
        if len(self.status["key_options"]) == 1:
            CHOICES = dict(
                zip(
                    ["Y", "X", "B", "A"],
                    self.status["key_options"]
                    + self.status["other_options"][:2]
                    + [self.status["other_options"][-1]],
                )
            )
        self.get_choice("NEAR_DEVIANT_1_1", CHOICES=CHOICES)
        if self.last_choice in self.status["key_options"]:
            self.status["key_options"].remove(self.last_choice)
        if self.last_choice in self.status["other_options"]:
            self.status["other_options"].remove(self.last_choice)
        self.dbhh.to_pos_only_ui("WP_NEAR_DEVIANT")
        if len(self.status["key_options"]) == 2:
            CHOICES = dict(
                zip(
                    ["Y", "X", "B", "A"],
                    self.status["key_options"]
                    + [
                        self.status["other_options"][0],
                        self.status["other_options"][-1],
                    ],
                )
            )
        if len(self.status["key_options"]) == 1:
            CHOICES = dict(
                zip(
                    ["Y", "X", "B", "A"],
                    self.status["key_options"]
                    + self.status["other_options"][:2]
                    + [self.status["other_options"][-1]],
                )
            )
        if len(self.status["key_options"]) == 0:
            CHOICES = dict(zip(["Y", "X", "B", "A"], self.status["other_options"]))
        self.get_choice("NEAR_DEVIANT_1_2", CHOICES=CHOICES)
        self.status["key_options"] = []
        self.status["other_options"] = []

    def HELI(self):
        self.dbhh.to_pos_only_ui("WP_HELI_1")
        self.get_choice()

    def NEAR_DEVIANT_2(self):
        self.dbhh.wait_for_cutscene_ui("CS_NEAR_DEVIANT_1")
        num_poi = self.dbhh.read_num_poi()
        if num_poi == 3:
            CHOICES = {
                "Y": "LAST CHANCE",
                "B": "TRUST",
                "A": "RATIONAL",
            }
            BRANCHES = {
                "Y": "NEAR_DEVIANT_3",
                "B": "NEAR_DEVIANT_3",
                "A": "NEAR_DEVIANT_3",
            }
        else:  # 4
            CHOICES = {
                "Y": "LAST CHANCE",
                "X": "TRUST",
                "B": "BLUFF",
                "A": "RATIONAL",
            }
            BRANCHES = {
                "Y": "NEAR_DEVIANT_3",
                "X": "NEAR_DEVIANT_3",
                "B": "BLUFF",
                "A": "NEAR_DEVIANT_3",
            }
            self.status["NEAR"] = True
        ENDINGS = {
            lambda self: self.ending in [1, 2] and num_poi == 4: "B",
            lambda self: self.ending in [3, 4, 5, 6] and num_poi == 4: "X",
        }
        self.get_choice(ENDINGS=ENDINGS, CHOICES=CHOICES, BRANCHES=BRANCHES)

    def BLUFF(self):
        self.dbhh.wait_for_ui("UI_BLUFF")
        ENDINGS = {
            lambda self: self.ending in [1]: "A",
            lambda self: self.ending in [2]: "B",
        }
        self.get_choice(ENDINGS=ENDINGS)

    def MOVE_CLOSER(self):
        pass

    def GIVE_UP(self):
        pass

    def NEAR_DEVIANT_3(self):
        self.dbhh.wait_for_cutscene_ui("CS_NEAR_DEVIANT_2")
        num_poi = self.dbhh.read_num_poi()
        if num_poi == 3:
            CHOICES = {
                "Y": "USE GUN",
                "B": "COMPROMISE",
                "A": "REFUSE",
            }
            BRANCHES = {
                "Y": "USE_GUN",
                "B": "NEAR_DEVIANT_4",
                "A": "REFUSE",
            }
        else:
            CHOICES = {
                "Y": "USE GUN",
                "X": "SACRIFICE SELF",
                "B": "COMPROMISE",
                "A": "REFUSE",
            }
            BRANCHES = {
                "Y": "USE_GUN",
                "X": "SACRIFICE_SELF",
                "B": "NEAR_DEVIANT_4",
                "A": "REFUSE",
            }
        if not self.status["GUN"]:
            CHOICES.pop("Y")
            BRANCHES.pop("Y")
        if not self.status["NEAR"]:
            CHOICES.pop("X")
            BRANCHES.pop("X")
        ENDINGS = {
            lambda self: self.ending in [1]: "A",
            lambda self: self.ending in [3]: "B",
            lambda self: self.ending in [4]: "X",
            lambda self: self.ending in [5, 6]: "Y",
        }
        self.get_choice(ENDINGS=ENDINGS, CHOICES=CHOICES, BRANCHES=BRANCHES)

    def USE_GUN(self):
        self.dbhh.wait_for_cutscene_ui("CS_USE_GUN")
        ENDINGS = {
            lambda self: self.ending in [5]: "A",
            lambda self: self.ending in [6]: "B",
        }
        self.get_choice(ENDINGS=ENDINGS)

    def EXECUTE(self):
        pass

    def INTIMIDATE(self):
        self.dbhh.wait_for_ui("UI_INTIMIDATE")
        ENDINGS = {
            lambda self: self.ending in [5]: "A",
            lambda self: self.ending in [6]: "B",
        }
        self.get_choice(ENDINGS=ENDINGS)

    def NEAR_DEVIANT_4(self):
        self.dbhh.wait_for_ui("UI_NEAR_DEVIANT_4")
        CHOICES = {
            "Y": "USE GUN",
            "X": "SACRIFICE SELF",
            "B": "REASSURE",
            "A": "TRUTH",
        }
        BRANCHES = {
            "Y": "USE_GUN",
            "X": "SACRIFICE_SELF",
            "B": "REASSURE",
            "A": "TRUTH",
        }
        if not self.status["GUN"]:
            CHOICES.pop("Y")
            BRANCHES.pop("Y")
        ENDINGS = {
            lambda self: self.ending in [3]: "B",
            lambda self: self.ending in [4]: "X",
        }
        self.get_choice(ENDINGS=ENDINGS, CHOICES=CHOICES, BRANCHES=BRANCHES)

    def REASSURE(self):
        pass

    def TRUTH(self):
        pass

    def SACRIFICE_SELF(self):
        pass

    def REFUSE(self):
        pass

    def QTE(self):
        self.dbhh.wait_for_ui("UI_QTE")
        self.get_choice(press_button=False)

    def NO_QTE_RUN(self):
        pass

    def QTE_RUN(self):
        self.dbhh.qte("QTE_RUN")

    def ENDING_1(self):
        self.ending = 1
        self.dbhh.info("Ending 1")

    def ENDING_2(self):
        self.ending = 2
        self.dbhh.info("Ending 2")

    def ENDING_3(self):
        self.ending = 3
        self.dbhh.info("Ending 3")

    def ENDING_4(self):
        self.ending = 4
        self.dbhh.info("Ending 4")

    def ENDING_5(self):
        self.ending = 5
        self.dbhh.info("Ending 5")

    def ENDING_6(self):
        self.ending = 6
        self.dbhh.info("Ending 6")
