from core.transform import auto_yield_class
from DBHHelper.flow import DBHFlow, E

# STORMY NIGHT

# 0: Defined by choices
# 1: TODD KILL ALICE
# 2: KARA SHOT TODD
# 3: ALICE SHOT TODD
# 4: TODD BROKE KARA IN THE CORRIDOR
# 5: KARA & ALICE FOUGHT THEIR WAY OUT
# 6: TODD BROKE KARA OUTSIDE
# 7: TODD BROKE KARA DOWNSTAIRS
# 8: KARA & ALICE EVADED TODD


@auto_yield_class
class Flow(DBHFlow):
    chapter_number = 7

    def setup(self):
        super().setup()
        self.status = {
            "GUN": False,
            "KARA_KILL": False,
            "ALICE_KILL": False,
            "AFTER_TODD": False,
            "OUT_WINDOW": False,
        }

    def graph(self):
        (
            self.START
            | E >> self.MISSION_START
            | E >> self.SERVE_FOOD
            | E >> self.WAIT_FOR_INSTRUCTION
        )
        [
            self.WAIT_FOR_INSTRUCTION | E >> self.DO_NOT_MOVE_1,
            self.WAIT_FOR_INSTRUCTION | E >> self.MOVE,
        ]
        [
            self.DO_NOT_MOVE_1 | E >> self.DO_NOT_MOVE_2,
            self.DO_NOT_MOVE_1 | E >> self.MOVE,
        ]
        [
            self.DO_NOT_MOVE_2 | E >> self.MOVE,
            self.DO_NOT_MOVE_2 | E >> self.ENDING_1,
        ]
        [
            self.MOVE | E >> self.GO_UPSTAIRS,
            self.MOVE | E >> self.REASONING | E >> self.GO_UPSTAIRS,
        ]
        [
            self.GO_UPSTAIRS
            | E >> self.TAKE_TODD_GUN
            | E >> self.GO_UPSTAIRS_ALICE_ROOM,
            self.GO_UPSTAIRS | E >> self.GO_UPSTAIRS_ALICE_ROOM,
        ]
        [
            self.GO_UPSTAIRS_ALICE_ROOM | E >> self.ALICE_ROOM_BEFORE_TODD,
            self.GO_UPSTAIRS_ALICE_ROOM | E >> self.KARA_TODD_FIGHT,
        ]
        [
            self.ALICE_ROOM_BEFORE_TODD
            | E >> self.RUN_WITH_ALICE
            | E >> self.GO_DOWNSTAIRS_STUN,
            self.ALICE_ROOM_BEFORE_TODD | E >> self.LOCK_ROOM,
            self.ALICE_ROOM_BEFORE_TODD
            | E >> self.SPEAK_TO_TODD
            | E >> self.GO_UPSTAIRS_ALICE_ROOM,
        ]
        [
            self.LOCK_ROOM
            | E >> self.TALK_TO_ALICE
            | E >> self.TAKE_TOO_MUCH_TIME
            | E >> self.KARA_TODD_FIGHT,
            self.LOCK_ROOM
            | E >> self.GRAB_LAMP
            | E >> self.TAKE_TOO_MUCH_TIME
            | E >> self.KARA_TODD_FIGHT,
            self.LOCK_ROOM | E >> self.OPEN_WINDOW,
        ]
        [
            self.OPEN_WINDOW | E >> self.GO_OUT_WINDOW,
            self.OPEN_WINDOW | E >> self.KARA_TODD_FIGHT,
        ]
        [
            self.GO_OUT_WINDOW | E >> self.JOIN_ALICE | E >> self.ON_BUS,
            self.GO_OUT_WINDOW | E >> self.KARA_TODD_FIGHT,
        ]
        [
            self.KARA_TODD_FIGHT | E >> self.FIGHT_OVER_GUN,
            self.KARA_TODD_FIGHT | E >> self.FIGHT_OVER_BELT,
        ]
        [
            self.FIGHT_OVER_GUN | E >> self.BASH,
            self.FIGHT_OVER_GUN | E >> self.NOT_BASH,
        ]
        [
            self.FIGHT_OVER_BELT | E >> self.BASH,
            self.FIGHT_OVER_BELT | E >> self.NOT_BASH,
        ]
        [
            self.BASH | E >> self.GO_DOWNSTAIRS,
            self.BASH | E >> self.TODD_ON_THE_GROUND,
        ]
        [
            self.NOT_BASH | E >> self.GO_DOWNSTAIRS,
            self.NOT_BASH | E >> self.NO_GUN_NOT_BASH | E >> self.TODD_ON_THE_GROUND,
        ]
        self.TODD_ON_THE_GROUND | E >> self.GO_DOWNSTAIRS_STUN
        self.OUTSIDE_STREET << E | self.GO_DOWNSTAIRS | E | self.GO_DOWNSTAIRS_STUN
        self.OUTSIDE_STREET | E >> self.ON_BUS
        [
            self.ON_BUS | E >> self.ENDING_2,
            self.ON_BUS | E >> self.ENDING_3,
            self.ON_BUS | E >> self.ENDING_5,
            self.ON_BUS | E >> self.ENDING_8,
        ]
        (
            self.FLOWCHART << E
            | self.ENDING_1
            | E
            | self.ENDING_2
            | E
            | self.ENDING_3
            # | E
            # | self.ENDING_4
            | E
            | self.ENDING_5
            # | E
            # | self.ENDING_6
            # | E
            # | self.ENDING_7
            | E
            | self.ENDING_8
        )
        self.FLOWCHART | E >> self.END

    def MISSION_START(self):
        self.dbhh.set_default_game_speed(self.cfg["DEFAULT_GAME_SPEED"])
        self.dbhh.enter_chapter("CHAPTER")
        self.dbhh.wait_for_cutscene("CS_MISSION_START")

    def SERVE_FOOD(self):
        self.dbhh.to_pos_ui("WP_SERVE_FOOD")
        self.dbhh.interact("IT_SERVE_FOOD_1")
        self.dbhh.to_pos("WP_SERVE_FOOD_1")
        self.dbhh.to_pos_ui("WP_SERVE_FOOD_2")
        self.dbhh.interact("IT_SERVE_FOOD_2")
        self.dbhh.to_pos_ui("WP_SERVE_FOOD_3")
        self.dbhh.interact("IT_SERVE_FOOD_3")
        self.dbhh.to_pos_ui("WP_SERVE_FOOD_4")
        # POUR WATER
        self.dbhh.interact("IT_SERVE_FOOD_4")
        self.dbhh.wait_for_ui("UI_POUR_WATER_1")
        self.dbhh.exp_rj_interact("IT_POUR_WATER_1")
        self.dbhh.wait_for_ui("UI_POUR_WATER_2")
        self.dbhh.exp_rj_interact("IT_POUR_WATER_2")
        # NAPKIN
        self.dbhh.wait_for_ui("UI_POUR_WATER_2")
        self.dbhh.interact("IT_SERVE_FOOD_5")
        self.dbhh.wait_for_cutscene("CS_SERVE_FOOD")

    def WAIT_FOR_INSTRUCTION(self):
        self.dbhh.wait_for_ui("UI_WAIT_FOR_INSTRUCTION")
        self.dbhh.vg_press_button("BT_WAIT_FOR_INSTRUCTION")
        self.dbhh.wait_for_cutscene("CS_WAIT_FOR_INSTRUCTION_1")
        self.dbhh.vg_trigger_down(lr="R")
        self.dbhh.to_view("VW_WAIT_FOR_INSTRUCTION")
        self.dbhh.vg_trigger_up(lr="R")
        self.dbhh.wait_for_cutscene("CS_WAIT_FOR_INSTRUCTION_2")
        self.get_choice(press_button=False)

    def DO_NOT_MOVE_1(self):
        self.dbhh.to_view("VW_DO_NOT_MOVE_1")
        self.dbhh.wait(15)
        self.get_choice(press_button=False)

    def DO_NOT_MOVE_2(self):
        self.dbhh.to_view("VW_DO_NOT_MOVE_2")
        self.dbhh.wait(15)
        self.get_choice(press_button=False)

    def MOVE(self):
        self.dbhh.to_pos_only_ui("WP_MOVE_1")
        self.dbhh.vg_press_button("BT_MOVE_1")
        self.dbhh.wait_for_ui("UI_MOVE_1")
        self.dbhh.vg_press_button("BT_MOVE_2")
        self.dbhh.wait_for_ui("UI_MOVE_2")
        self.dbhh.qte("QTE_MOVE")
        self.dbhh.reset_gamepad()
        self.dbhh.wait_for_cutscene("CS_MOVE")
        self.get_choice(press_button=False)

    def REASONING(self):
        self.status["AFTER_TODD"] = True
        self.dbhh.to_pos_ui("WP_REASONING")
        self.get_choice("REASONING")
        self.dbhh.wait_for_ui("UI_REASONING")
        self.dbhh.vg_press_button("BT_REASONING")
        self.dbhh.wait(2)
        self.dbhh.exp_rj_interact("IT_REASONING")
        self.dbhh.reset_gamepad()
        self.dbhh.wait_for_cutscene("CS_REASONING")

    def GO_UPSTAIRS(self):
        self.dbhh.to_pos("WP_GO_UPSTAIRS_1")
        self.dbhh.to_pos_ui("WP_GO_UPSTAIRS_2")
        self.get_choice("TODD_ROOM")

    def TAKE_TODD_GUN(self):
        self.status["AFTER_TODD"] = True
        self.dbhh.interact("IT_TAKE_TODD_GUN_1")
        self.dbhh.to_pos_ui("WP_TAKE_TODD_GUN_1")
        self.dbhh.interact("IT_TAKE_TODD_GUN_2")
        self.status["GUN"] = True
        self.dbhh.to_pos("WP_TAKE_TODD_GUN_2")
        self.dbhh.to_pos("WP_TAKE_TODD_GUN_3")

    def GO_UPSTAIRS_ALICE_ROOM(self):
        self.dbhh.to_pos("WP_GO_UPSTAIRS_3")
        self.dbhh.to_pos_only_ui("WP_GO_UPSTAIRS_4")
        self.dbhh.exp_rj_interact("IT_GO_UPSTAIRS")
        if self.status["AFTER_TODD"]:
            self.next_branch = "KARA_TODD_FIGHT"
        else:
            self.dbhh.wait_for_cutscene("CS_GO_UPSTAIRS_ALICE_ROOM")
            self.next_branch = "ALICE_ROOM_BEFORE_TODD"

    def ALICE_ROOM_BEFORE_TODD(self):
        self.dbhh.to_pos("WP_ALICE_ROOM_BEFORE_TODD")
        self.dbhh.wait_for_ui("UI_ALICE_ROOM_BEFORE_TODD")
        self.get_choice()

    def RUN_WITH_ALICE(self):
        self.dbhh.to_pos_only_ui("WP_RUN_WITH_ALICE")
        self.dbhh.vg_press_button("BT_RUN_WITH_ALICE")
        self.dbhh.wait(5)
        self.dbhh.vg_trigger_down(lr="L")
        self.dbhh.wait(10)
        self.dbhh.reset_gamepad()

    def LOCK_ROOM(self):
        self.dbhh.to_pos_ui("WP_LOCK_ROOM")
        self.dbhh.exp_rj_interact("IT_LOCK_ROOM")
        self.dbhh.wait_for_cutscene("CS_LOCK_ROOM")
        self.get_choice(press_button=False)

    def SPEAK_TO_TODD(self):
        self.dbhh.qte("QTE_SPEAK_TO_TODD")
        self.dbhh.wait_for_cutscene("CS_SPEAK_TO_TODD")
        self.status["AFTER_TODD"] = True

    def TALK_TO_ALICE(self):
        self.dbhh.to_pos_ui("WP_OPEN_WINDOW")
        self.dbhh.interact("IT_TALK_TO_ALICE")

    def GRAB_LAMP(self):
        self.dbhh.to_pos_only_ui("WP_GRAB_LAMP")
        self.dbhh.interact("IT_GRAB_LAMP")

    def TAKE_TOO_MUCH_TIME(self):
        self.dbhh.wait_for_ui("UI_TAKE_TOO_MUCH_TIME")
        self.get_choice()

    def OPEN_WINDOW(self):
        self.dbhh.to_pos_ui("WP_OPEN_WINDOW")
        self.dbhh.vg_trigger_down("IT_OPEN_WINDOW_1")
        self.dbhh.wait(2)
        self.dbhh.interact("IT_OPEN_WINDOW_2")
        self.dbhh.wait_for_ui("UI_GO_OUT_WINDOW")
        self.get_choice()

    def GO_OUT_WINDOW(self):
        self.dbhh.wait_for_ui("UI_GO_OUT_WINDOW")
        self.get_choice()

    def JOIN_ALICE(self):
        self.status["OUT_WINDOW"] = True
        self.dbhh.wait_for_ui("UI_JOIN_ALICE")
        self.dbhh.qte("QTE_JOIN_ALICE")
        self.dbhh.wait_for_ui("UI_JOIN_ALICE")
        self.dbhh.interact("IT_JOIN_ALICE_1")
        self.dbhh.wait_for_ui("UI_JOIN_ALICE")
        self.dbhh.interact("IT_JOIN_ALICE_2")
        self.dbhh.wait_for_cutscene("CS_JOIN_ALICE")
        self.dbhh.to_pos("WP_JOIN_ALICE")

    def KARA_TODD_FIGHT(self):
        self.dbhh.wait_for_ui("UI_KARA_TODD_FIGHT_1")
        self.dbhh.interact("IT_KARA_TODD_FIGHT_1")
        self.dbhh.wait_for_ui("UI_KARA_TODD_FIGHT_1")
        self.dbhh.interact("IT_KARA_TODD_FIGHT_2")
        self.dbhh.wait_for_ui("UI_KARA_TODD_FIGHT_1")
        self.dbhh.interact("IT_KARA_TODD_FIGHT_1")
        self.dbhh.wait_for_ui("UI_KARA_TODD_FIGHT_1")
        self.dbhh.interact("IT_KARA_TODD_FIGHT_2")
        self.dbhh.wait_for_ui("UI_KARA_TODD_FIGHT_2")
        self.dbhh.interact("IT_KARA_TODD_FIGHT_3")
        self.dbhh.wait_for_ui("UI_KARA_TODD_FIGHT_1")
        self.dbhh.interact("IT_KARA_TODD_FIGHT_1")
        self.dbhh.wait_for_ui("UI_KARA_TODD_FIGHT_1")
        self.dbhh.qte("QTE_KARA_TODD_FIGHT")
        self.dbhh.wait_for_ui("UI_KARA_TODD_FIGHT_2")
        self.dbhh.qtes("QTES_KARA_TODD_FIGHT")
        self.dbhh.wait_for_ui("UI_KARA_TODD_FIGHT_1")
        self.dbhh.interact("IT_KARA_TODD_FIGHT_4")
        self.dbhh.wait_for_ui("UI_KARA_TODD_FIGHT_1")
        self.dbhh.interact("IT_KARA_TODD_FIGHT_5")
        self.dbhh.wait_for_ui("UI_KARA_TODD_FIGHT_2")
        self.dbhh.vg_triggers("IT_KARA_TODD_FIGHT_6")
        self.dbhh.wait_for_ui("UI_KARA_TODD_FIGHT_1")
        self.dbhh.interact("IT_KARA_TODD_FIGHT_7")
        self.dbhh.wait_for_ui("UI_KARA_TODD_FIGHT_1")
        self.dbhh.interact("IT_KARA_TODD_FIGHT_4")
        self.dbhh.wait_for_ui("UI_KARA_TODD_FIGHT_1")
        self.dbhh.interact("IT_KARA_TODD_FIGHT_5")
        self.dbhh.wait_for_ui("UI_KARA_TODD_FIGHT_1")
        if self.status["GUN"]:
            self.next_branch = "FIGHT_OVER_GUN"
        else:
            self.next_branch = "FIGHT_OVER_BELT"

    def FIGHT_OVER_GUN(self):
        self.get_choice(press_button=False)

    def FIGHT_OVER_BELT(self):
        self.next_branch = "BASH"

    def BASH(self):
        self.dbhh.qte("QTE_BASH")
        if self.status["GUN"]:
            self.status["KARA_KILL"] = True
            self.next_branch = "GO_DOWNSTAIRS"
        else:
            self.next_branch = "TODD_ON_THE_GROUND"

    def NOT_BASH(self):
        if self.status["GUN"]:
            self.status["ALICE_KILL"] = True
            self.next_branch = "GO_DOWNSTAIRS"
        else:
            self.next_branch = "NO_GUN_NOT_BASH"

    def NO_GUN_NOT_BASH(self):
        self.dbhh.wait_for_cutscene("CS_NO_GUN_NOT_BASH")
        self.dbhh.to_view("VW_PUSH")
        self.dbhh.interact("IT_PUSH")

    def TODD_ON_THE_GROUND(self):
        self.dbhh.wait_for_ui("UI_RUN_AWAY")
        self.dbhh.interact("IT_RUN_AWAY")

    def GO_DOWNSTAIRS(self):
        self.dbhh.to_pos("WP_GO_DOWNSTAIRS")
        self.dbhh.wait_for_ui("UI_GO_DOWNSTAIRS")
        self.dbhh.interact("IT_GO_DOWNSTAIRS_1")
        self.dbhh.wait_for_ui("UI_GO_DOWNSTAIRS")
        self.dbhh.exp_rj_interact("IT_GO_DOWNSTAIRS_2")
        self.dbhh.wait_for_ui("UI_GO_DOWNSTAIRS")
        self.dbhh.interact("IT_GO_DOWNSTAIRS_3")

    def GO_DOWNSTAIRS_STUN(self):
        self.dbhh.to_pos("WP_GO_DOWNSTAIRS")
        self.dbhh.wait_for_ui("UI_GO_DOWNSTAIRS_STUN")
        self.dbhh.interact("IT_GO_DOWNSTAIRS_STUN")
        self.dbhh.qte("QTE_GO_DOWNSTAIRS_STUN")
        self.dbhh.wait_for_ui("UI_GO_DOWNSTAIRS")
        self.dbhh.exp_rj_interact("IT_GO_DOWNSTAIRS_STUN_1")
        self.dbhh.wait_for_ui("UI_GO_DOWNSTAIRS")
        self.dbhh.exp_rj_interact("IT_GO_DOWNSTAIRS_STUN_2")
        self.dbhh.wait_for_ui("UI_GO_DOWNSTAIRS")
        self.dbhh.interact("IT_GO_DOWNSTAIRS_3")

    def OUTSIDE_STREET(self):
        self.dbhh.wait_for_cutscene("CS_OUTSIDE_STREET")
        self.dbhh.to_pos("WP_OUTSIDE_STREET")

    def ON_BUS(self):
        self.dbhh.wait_for_ui("UI_OUTSIDE_STREET")
        self.dbhh.interact("IT_OUTSIDE_STREET")
        if self.status["KARA_KILL"]:
            self.next_branch = "ENDING_2"
        elif self.status["ALICE_KILL"]:
            self.next_branch = "ENDING_3"
        elif self.status["OUT_WINDOW"]:
            self.next_branch = "ENDING_8"
        else:
            self.next_branch = "ENDING_5"

    def ENDING_1(self):
        # 1: TODD KILL ALICE
        self.ending = 1
        self.dbhh.info("Ending 1")

    def ENDING_2(self):
        # 2: KARA SHOT TODD
        self.ending = 2
        self.dbhh.info("Ending 2")

    def ENDING_3(self):
        # 3: ALICE SHOT TODD
        self.ending = 3
        self.dbhh.info("Ending 3")

    def ENDING_4(self):
        # 4: TODD BROKE KARA IN THE CORRIDOR
        self.ending = 4
        self.dbhh.info("Ending 4")

    def ENDING_5(self):
        # 5: KARA & ALICE FOUGHT THEIR WAY OUT
        self.ending = 5
        self.dbhh.info("Ending 5")

    def ENDING_6(self):
        # 6: TODD BROKE KARA OUTSIDE
        self.ending = 6
        self.dbhh.info("Ending 6")

    def ENDING_7(self):
        # 7: TODD BROKE KARA DOWNSTAIRS
        self.ending = 7
        self.dbhh.info("Ending 7")

    def ENDING_8(self):
        # 8: KARA & ALICE EVADED TODD
        self.ending = 8
        self.dbhh.info("Ending 8")
