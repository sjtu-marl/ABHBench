from core.transform import auto_yield_class
from DBHHelper.flow import DBHFlow, E

# BROKEN

# 0: Defined by choices
# 1: LEO ACCUSED MARKUS
# 2: POLICE MISTOOK MARKUS FOR THE AGGRESSOR


@auto_yield_class
class Flow(DBHFlow):
    chapter_number = 8

    def setup(self):
        super().setup()

    def graph(self):
        (
            self.START
            | E >> self.MISSION_START
            | E >> self.WHEEL_CHAIR
            | E >> self.WINE
            | E >> self.CALL_POLICE
            | E >> self.CHECK_OUT
            | E >> self.CONFRONT_LEO
            | E >> self.BREAK_MIND_PALACE
            | E >> self.CHOOSE_PUSH
        )
        [
            self.CHOOSE_PUSH | E >> self.ENDURE | E >> self.ENDING_1,
            self.CHOOSE_PUSH | E >> self.PUSH_LEO | E >> self.ENDING_2,
        ]
        self.FLOWCHART << E | self.ENDING_1 | E | self.ENDING_2
        self.FLOWCHART | E >> self.END

    def MISSION_START(self):
        self.dbhh.set_default_game_speed(self.cfg["DEFAULT_GAME_SPEED"])
        self.dbhh.enter_chapter("CHAPTER")
        self.dbhh.wait_for_ui("UI_MISSION_START")

    def WHEEL_CHAIR(self):
        self.dbhh.interact("IT_WHEEL_CHAIR")

    def WINE(self):
        self.dbhh.to_pos("WP_WINE_1")
        self.dbhh.to_pos("WP_WINE_2")
        self.dbhh.wait_for_ui("UI_WINE")
        self.dbhh.interact("IT_PULL_1")
        self.dbhh.wait_for_ui("UI_WINE")
        self.dbhh.exp_rj_interact("IT_PULL_2")

    def CALL_POLICE(self):
        self.dbhh.wait_for_ui("UI_CALL_POLICE")
        self.dbhh.vg_press_button("BT_CALL_POLICE")

    def CHECK_OUT(self):
        self.dbhh.wait_for_cutscene("CS_CHECK_OUT")
        self.dbhh.to_pos_ui("WP_CHECK_OUT_1")
        self.dbhh.interact("IT_CHECK_OUT")
        self.dbhh.to_pos("WP_CHECK_OUT_2")

    def CONFRONT_LEO(self):
        self.dbhh.wait_for_cutscene("CS_CONFRONT_LEO")
        self.dbhh.to_pos_ui("WP_CONFRONT_LEO")
        self.get_choice("CONFRONT_LEO")

    def BREAK_MIND_PALACE(self):
        self.dbhh.wait_for_ui("UI_BREAK_MIND_PALACE")
        self.dbhh.interact("IT_BREAK_MIND_PALACE")
        self.dbhh.vg_press_button("BT_BREAK_MIND_PALACE_1")
        self.dbhh.vg_press_button("BT_BREAK_MIND_PALACE_2")
        self.dbhh.obs()
        self.dbhh.interact("IT_BREAK_MIND_PALACE_1")
        self.dbhh.interact("IT_BREAK_MIND_PALACE_2")
        self.dbhh.interact("IT_BREAK_MIND_PALACE_3")

    def CHOOSE_PUSH(self):
        self.dbhh.wait_for_ui("UI_CHOOSE_PUSH")
        self.get_choice("CHOOSE_PUSH")

    def PUSH_LEO(self):
        self.dbhh.wait_for_ui("UI_PUSH_LEO")
        self.get_choice("PUSH_LEO")

    def ENDURE(self):
        pass

    def ENDING_1(self):
        self.ending = 1
        self.dbhh.info("Ending 1")

    def ENDING_2(self):
        self.ending = 2
        self.dbhh.info("Ending 2")
