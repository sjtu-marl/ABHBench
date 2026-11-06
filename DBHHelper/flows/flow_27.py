from core.transform import auto_yield_class
from DBHHelper.flow import DBHFlow, E

# MEET KAMSKI

# 0: Defined by choices
# 1: HANK WAS DISAPPOINTED WITH CONNOR'S DECISION
# 2: HANK THOUGHT CONNOR MADE THE RIGHT DECISION


@auto_yield_class
class Flow(DBHFlow):
    chapter_number = 27

    def setup(self):
        super().setup()

    def graph(self):
        (
            self.START
            | E >> self.MISSION_START
            | E >> self.OPEN_CAR_DOOR
            | E >> self.OUTSIDE_CAR
            | E >> self.AT_DOOR
            | E >> self.RECEPTION_AREA
            | E >> self.MOVE_INSIDE
            | E >> self.TALK_TO_KAMSKI
            | E >> self.CHOOSE_SHOOT
        )
        (
            self.CHOOSE_SHOOT | E >> self.SHOOT,
            self.CHOOSE_SHOOT | E >> self.DONT_SHOOT | E >> self.ENDING_2,
        )
        (
            self.SHOOT | E >> self.GET_INFO,
            self.SHOOT | E >> self.JERICHO_LOCATION,
        )
        self.ENDING_1 << E | self.GET_INFO | E | self.JERICHO_LOCATION
        self.FLOWCHART << E | self.ENDING_1 | E | self.ENDING_2
        self.FLOWCHART | E >> self.END

    def MISSION_START(self):
        self.dbhh.set_default_game_speed(self.cfg["DEFAULT_GAME_SPEED"])
        self.dbhh.enter_chapter("CHAPTER")
        self.dbhh.wait_for_ui("UI_MISSION_START")

    def OPEN_CAR_DOOR(self):
        self.dbhh.interact("IT_CAR_DOOR")

    def OUTSIDE_CAR(self):
        self.dbhh.wait_for_ui("UI_OUTSIDE_CAR")
        self.get_choice()
        self.dbhh.reset_gamepad()
        self.dbhh.wait(seconds=3, speedup=False)

    def AT_DOOR(self):
        self.dbhh.to_pos("WP_SIDE_CAR")
        self.dbhh.to_pos("WP_AT_DOOR")

    def RECEPTION_AREA(self):
        self.dbhh.wait_for_ui("UI_RECEPTION_AREA_1")
        self.get_choice("RECEPTION_AREA_1")
        # WALK TO CHAIR
        self.dbhh.to_pos_ui("WP_CHAIR")
        self.dbhh.exp_rj_interact("IT_CHAIR")
        self.dbhh.wait_for_ui("UI_RECEPTION_AREA_2")
        self.get_choice("RECEPTION_AREA_2")

    def MOVE_INSIDE(self):
        self.dbhh.wait_for_ui("UI_SIT")
        self.dbhh.wait_for_no_ui("UI_STAND")
        self.dbhh.to_pos("WP_INSIDE_1")
        self.dbhh.wait(5)
        self.dbhh.to_pos("WP_INSIDE_2")
        self.dbhh.to_view("VW_INSIDE")

    def TALK_TO_KAMSKI(self):
        self.dbhh.wait_for_ui("UI_TALK_TO_KAMSKI_1")
        self.get_choice("TALK_TO_KAMSKI_1")
        self.dbhh.wait_for_ui("UI_TALK_TO_KAMSKI_2")
        self.get_choice("TALK_TO_KAMSKI_2")
        self.dbhh.wait_for_ui("UI_TALK_TO_KAMSKI_3")
        self.get_choice("TALK_TO_KAMSKI_3")

    def CHOOSE_SHOOT(self):
        self.dbhh.wait_for_ui("UI_CHOOSE_SHOOT")
        self.get_choice()

    def SHOOT(self):
        self.dbhh.wait_for_ui("UI_SHOOT")
        self.get_choice()

    def DONT_SHOOT(self):
        pass

    def JERICHO_LOCATION(self):
        self.dbhh.wait_for_ui("UI_JERICHO_LOCATION_1")
        self.dbhh.exp_rj_interact("IT_JERICHO_LOCATION")
        self.dbhh.wait_for_ui("UI_JERICHO_LOCATION_2")
        self.dbhh.vg_press_button("BT_JERICHO_LOCATION")
        self.dbhh.reset_gamepad()

    def GET_INFO(self):
        pass

    def ENDING_1(self):
        self.ending = 1
        self.dbhh.info("Ending 1")

    def ENDING_2(self):
        self.ending = 2
        self.dbhh.info("Ending 2")
