from core.transform import auto_yield_class
from DBHHelper.flow import DBHFlow, E

# FUGITIVES

# 0: Defined by choices
# 1: ALICE & KARA STAYED IN MOTEL
# 2: ALICE & KARA STAYED IN ABANDONED CAR
# 3: ALICE & KARA STAYED IN THE SQUAT


@auto_yield_class
class Flow(DBHFlow):
    chapter_number = 10

    def setup(self):
        super().setup()
        self.status = {
            "GUN": True,
            "SHOPLIFT": False,
            "FOOD": False,
            "DOLL": False,
            "LAST_STEAL": "NONE",
        }

    def graph(self):
        (
            self.START
            | E >> self.MISSION_START
            | E >> self.LEAVE_BUS
            | E >> self.TALKING_TO_PARKED_ANDROIDS
            | E >> self.INVESTIGATE_OPTIONS
            | E >> self.TALK_TO_ALICE
            | E >> self.CHECK_MOTEL
            | E >> self.ENTER_LAUNDROMAT
        )
        self.ENTER_LAUNDROMAT | E >> self.GIVE_UP_STEALING_CLOTHES_IN_LAUNDROMAT
        self.ENTER_LAUNDROMAT | E >> self.STEALING_CLOTHES_IN_LAUNDROMAT

        self.GIVE_UP_STEALING_CLOTHES_IN_LAUNDROMAT | E >> self.ENTER_PARKING_LOT
        self.STEALING_CLOTHES_IN_LAUNDROMAT | E >> self.ENTER_SUPERMARKET
        self.ENTER_SUPERMARKET | E >> self.IN_SUPERMARKET

        [
            self.IN_SUPERMARKET | E >> self.THREATEN_CLERK_WITH_THE_GUN,
            self.IN_SUPERMARKET | E >> self.USING_ALICE_AS_DIVERSION_TO_STEAL_MONEY,
            self.IN_SUPERMARKET | E >> self.SHOPLIFT,
            self.IN_SUPERMARKET | E >> self.LEAVE_SUPERMARKET,
        ]
        [
            self.SHOPLIFT | E >> self.STEAL_DOLL,
            self.SHOPLIFT | E >> self.STEAL_FOOD,
            self.SHOPLIFT | E >> self.IN_SUPERMARKET,
        ]
        [self.SHOPLIFT << E | self.STEAL_DOLL | E | self.STEAL_FOOD]
        [self.BE_SEEN_STEALING << E | self.STEAL_DOLL | E | self.STEAL_FOOD]
        [
            self.BE_SEEN_STEALING | E >> self.TAKE_GUN_WHEN_STEALING,
            self.BE_SEEN_STEALING | E >> self.GIVE_UP_STEALING_IN_SUPERMARKET,
        ]
        # Threaten the clerk with gun
        [
            self.THREATEN_CLERK_WITH_THE_GUN | E >> self.GIVE_UP_FOR_SOMEONE_ENTER,
            self.THREATEN_CLERK_WITH_THE_GUN | E >> self.CONTINUE_GRAB_1,
        ]
        [
            self.CONTINUE_GRAB_1 | E >> self.CONTINUE_GRAB_2,
            self.CONTINUE_GRAB_1 | E >> self.GRAB_SMOOTHLY,
        ]
        [
            self.CONTINUE_GRAB_2 | E >> self.GRAB_SMOOTHLY,
            self.CONTINUE_GRAB_2 | E >> self.CONFRONT_WITH_CLERK,
        ]
        [
            self.GRAB_SMOOTHLY | E >> self.EXPLAIN_TO_ALICE_WHY_GRAB,
            self.GRAB_SMOOTHLY | E >> self.LIE_MONEY,
        ]
        [
            self.CONFRONT_WITH_CLERK | E >> self.CONVINCE_THE_CLERK,
            self.CONFRONT_WITH_CLERK | E >> self.GIVE_UP_IN_CONFRONTING,
        ]
        [
            self.TAKE_GUN_WHEN_STEALING | E >> self.TAKE_THE_MONEY_BY_THE_WAY,
            self.TAKE_GUN_WHEN_STEALING | E >> self.LEAVE_SUPERMARKET_DIRECTLY,
        ]
        (
            self.ENTER_PARKING_LOT << E
            | self.GIVE_UP_STEALING_CLOTHES_IN_LAUNDROMAT
            | E
            | self.LEAVE_SUPERMARKET
            | E
            | self.GIVE_UP_FOR_SOMEONE_ENTER
            | E
            | self.GIVE_UP_IN_CONFRONTING
            | E
            | self.LEAVE_SUPERMARKET_DIRECTLY
            | E
            | self.GIVE_UP_STEALING_IN_SUPERMARKET
        )
        (
            self.ENTER_MOTEL << E
            | self.LIE_MONEY
            | E
            | self.EXPLAIN_TO_ALICE_WHY_GRAB
            | E
            | self.CONVINCE_THE_CLERK
            | E
            | self.TAKE_THE_MONEY_BY_THE_WAY
            | E
            | self.USING_ALICE_AS_DIVERSION_TO_STEAL_MONEY
        )

        [
            self.ENTER_MOTEL | E >> self.SLEEP_WITH_ALICE_IN_MOTEL,
            self.ENTER_MOTEL | E >> self.SLEEP_ALONE_IN_MOTEL,
        ]
        self.ENTER_PARKING_LOT | E >> self.STAY_IN_CAR
        self.ENTER_PARKING_LOT | E >> self.ENTER_SQUAT

        self.ENTER_SQUAT | E >> self.LEAVE_SQUAT_TO_CAR
        self.ENTER_SQUAT | E >> self.CALM_RALPH
        self.CALM_RALPH | E >> self.LEAVE_SQUAT_TO_CAR
        self.CALM_RALPH | E >> self.STAY_IN_SQUAT

        self.LEAVE_SQUAT_TO_CAR | E >> self.STAY_IN_CAR
        (
            self.ENDING_1 << E
            | self.SLEEP_ALONE_IN_MOTEL
            | E
            | self.SLEEP_WITH_ALICE_IN_MOTEL
        )
        [self.STAY_IN_CAR | E >> self.ENDING_2]

        self.STAY_IN_SQUAT | E >> self.SLEEP_ALONE_IN_SQUAT
        self.STAY_IN_SQUAT | E >> self.SLEEP_WITH_ALICE_IN_SQUAT
        (
            self.ENDING_3 << E
            | self.SLEEP_ALONE_IN_SQUAT
            | E
            | self.SLEEP_WITH_ALICE_IN_SQUAT
        )

        self.FLOWCHART << E | self.ENDING_1 | E | self.ENDING_2 | E | self.ENDING_3
        self.FLOWCHART | E >> self.END

    def MISSION_START(self):
        self.dbhh.enter_chapter("CHAPTER")
        self.dbhh.set_default_game_speed(self.cfg["DEFAULT_GAME_SPEED"])
        self.dbhh.wait_for_cutscene_ui("CS_BUS_STOP_1")

    def LEAVE_BUS(self):
        self.dbhh.interact("IT_WAKE_UP_ALICE")
        self.dbhh.wait_for_cutscene_ui("CS_BUS_STOP_2")
        self.dbhh.interact("IT_STAND_UP")
        self.dbhh.wait_for_cutscene("CS_BUS_STOP_0")
        self.dbhh.to_pos_ui("WP_LEAVE_BUS_1")
        self.get_choice()
        self.dbhh.wait_for_cutscene("CS_BUS_STOP_ASK_HELP")
        self.dbhh.to_pos("WP_LEAVE_BUS_2")
        self.dbhh.wait_for_cutscene("CS_BUS_STOP_3")

    def TALKING_TO_PARKED_ANDROIDS(self):
        self.dbhh.to_pos_ui("WP_PARKED_ANDROIDS")
        self.dbhh.vg_press_button("BT_TALKING_TO_PARKED_ANDROID")
        self.dbhh.wait_for_cutscene("CS_TALKING_TO_PARKED_ANDROID")
        self.stats["TTPA"] = "TALK TO PARKED ANDROID"

    def INVESTIGATE_OPTIONS(self):
        self.dbhh.to_pos("WP_CENTER")
        self.dbhh.vg_trigger_down(lr="R")
        for vw in [
            "VW_CENTER_PARKING_LOT",
            "VW_CENTER_SQUAT",
            "VW_CENTER_MOTEL",
            "VW_CENTER_LAUNDROMAT",
            "VW_CENTER_SUPERMARKET",
        ]:
            self.dbhh.to_view(vw)
            self.dbhh.vg_press_button("BT_INVESTIGATE_OPTIONS")
            self.dbhh.wait(seconds=5)
            self.dbhh.obs()
            self.dbhh.vg_release_button("BT_RL_INVESTIGATE_OPTIONS")
            self.dbhh.wait(seconds=1)
        self.dbhh.vg_trigger_up(lr="R")

    def TALK_TO_ALICE(self):
        self.dbhh.to_pos("WP_TALK_TO_ALICE")
        self.dbhh.vg_press_button("BT_CHANGE_VIEW_ANGLE")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_press_button("BT_TALK_TO_ALICE")
        self.dbhh.wait_for_cutscene("CS_TALK_TO_ANDROID")
        self.stats["TTATC"] = "TALK TO ANDROID TRASH COLLECTOR"
        self.dbhh.to_pos("WP_CENTER")

    def CHECK_MOTEL(self):
        self.dbhh.to_view("VW_CENTER_MOTEL")
        self.stats["CM"] = "CHECK MOTEL"
        self.dbhh.to_pos_ui("WP_MOTEL_DOOR")
        self.dbhh.interact("IT_CHECK_MOTEL")
        self.dbhh.wait_for_cutscene("CS_CHECK_MOTEL_WITHOUT_MONEY_AND_CLOTHES")
        self.dbhh.to_pos("WP_CENTER")

    def ENTER_LAUNDROMAT(self):
        self.dbhh.to_view("VW_CENTER_LAUNDROMAT")
        self.stats["EL"] = "ENTER LAUNDROMAT"
        self.dbhh.to_pos("WP_LAUNDROMAT_DOOR")
        self.dbhh.to_view("VW_LAUNDROMAT_DOOR")
        self.dbhh.wait_for_ui("UI_LAUNDROMAT_DOOR")
        self.dbhh.exp_rj_interact("IT_OPEN_LAUNDROMAT_DOOR")
        self.dbhh.wait_for_cutscene("CS_ENTER_LAUNDROMAT")
        self.dbhh.to_pos("WP_INSPECT_DRYER")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_press_button("BT_INSPECT_DRYER")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_OPEN_DRYER")
        self.dbhh.wait_for_ui("UI_2")
        self.get_choice("WHETHER_STEALING_IN_LAUNDROMAT")

    def STEALING_CLOTHES_IN_LAUNDROMAT(self):
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_STEAL_0")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_press_button("BT_STEAL_1")
        self.dbhh.wait_for_ui("UI_2")
        self.dbhh.vg_trigger_down(lr="R")
        self.dbhh.wait_for_ui("UI_3")
        self.dbhh.exp_rj_interact("IT_STEAL_2")
        self.dbhh.wait_for_no_ui("NO_UI")
        self.dbhh.reset_gamepad()
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_trigger_down("BT_STEAL_3")
        self.dbhh.wait_for_ui("UI_2")
        self.dbhh.vg_press_button("BT_STEAL_4")
        self.dbhh.wait_for_ui("UI_3")
        self.dbhh.exp_rj_interact(seq=["U"], after=1, pause=1, keep=True)
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_PICK_UP_CLOTHES")
        self.dbhh.to_pos("WP_WEAR_CLOTHES_1")
        self.dbhh.to_pos("WP_WEAR_CLOTHES_2")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_WEAR_CLOTHES")
        self.dbhh.wait_for_cutscene("CS_PUT_ON_CLOTHES")
        self.dbhh.to_pos("WP_LEAVE_LAUNDROMAT_1")
        self.dbhh.to_pos("WP_LEAVE_LAUNDROMAT_2")
        self.dbhh.to_view("VW_LEAVE_LAUNDROMAT")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.exp_rj_interact("IT_LEAVE_LAUNDROMAT_CLOTHES")
        self.dbhh.wait_for_cutscene("CS_LEAVE_LAUNDROMAT_WITH_CLOTHES")
        self.dbhh.to_pos("WP_CENTER")

    def GIVE_UP_STEALING_CLOTHES_IN_LAUNDROMAT(self):
        for key in ["SHOPLIFT", "LAST_STEAL"]:
            self.status.pop(key, None)
        self.dbhh.to_pos("WP_LAUNDROMAT_LEAVE_TEMP_1")
        self.dbhh.to_pos("WP_LEAVE_LAUNDROMAT_1")
        self.dbhh.to_pos("WP_LEAVE_LAUNDROMAT_2")
        self.dbhh.to_view("VW_LEAVE_LAUNDROMAT")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_LEAVE_LAUNDROMAT_NO_CLOTHES")
        self.dbhh.wait_for_cutscene("CS_LEAVE_LAUNDROMAT")
        self.dbhh.to_pos("WP_CENTER")
        self.dbhh.to_view("VW_CENTER_PARKING_LOT")

    def ENTER_SUPERMARKET(self):
        self.dbhh.to_view("VW_CENTER_SUPERMARKET")
        self.stats["ES"] = "ENTER SUPERMARKET"
        self.dbhh.to_pos("WP_SUPERMARKET_DOOR")
        self.dbhh.to_pos("WP_SUPERMARKET_DOOR_INSIDE")
        self.dbhh.to_pos_ui("WP_TALK_TO_CLERK")
        self.dbhh.vg_press_button("BT_TALK_TO_CLERK")
        self.dbhh.wait_for_ui("UI_TALK_TO_CLERK_WITH_CLOTHES")
        self.get_choice("SUPERMARKET_TALK_TO_CLERK_IN_HUMAN_CLOTHES")
        self.dbhh.wait_for_ui("UI_1")

    def IN_SUPERMARKET(self):
        # Fixed keys: X → Y → A → B
        options = [
            ("X", "THREATEN CLERK WITH THE GUN", "THREATEN_CLERK_WITH_THE_GUN"),
            (
                "Y",
                "USING ALICE AS DIVERSION",
                "USING_ALICE_AS_DIVERSION_TO_STEAL_MONEY",
            ),
            ("A", "SHOPLIFT", "SHOPLIFT"),
            ("B", "LEAVE SUPERMARKET", "LEAVE_SUPERMARKET"),
        ]

        CHOICES, BRANCHES = {}, {}
        for k, label, branch in options:
            # Hide SHOPLIFT after it's done
            if branch == "SHOPLIFT" and self.status.get("SHOPLIFT"):
                continue
            CHOICES[k] = label
            BRANCHES[k] = branch

        self.get_choice(
            KEY="IN_SUPERMARKET", CHOICES=CHOICES, BRANCHES=BRANCHES, press_button=False
        )

    def LEAVE_SUPERMARKET(self):
        self.dbhh.to_pos("WP_SUPERMARKET_DOOR_LEAVE")
        keys_to_remove = ["SHOPLIFT", "LAST_STEAL"]
        for key in keys_to_remove:
            self.status.pop(key, None)

    def LEAVE_SUPERMARKET_DIRECTLY(self):
        self.dbhh.to_pos_only_ui("WP_SUPERMARKET_DOOR_UI_2")
        self.dbhh.vg_press_button(button="B")
        self.dbhh.wait_for_cutscene("CS_LEAVE_SUPERMARKET_DIRECTLY")
        keys_to_remove = ["SHOPLIFT", "LAST_STEAL"]
        for key in keys_to_remove:
            self.status.pop(key, None)

    def SHOPLIFT(self):
        self.status["SHOPLIFT"] = True

        # Keys in order: X → Y → A → B
        options = [
            ("X", "STEAL FOOD FOR ALICE", "STEAL_FOOD", not self.status.get("FOOD")),
            ("Y", "STEAL DOLL FOR ALICE", "STEAL_DOLL", not self.status.get("DOLL")),
            ("B", "STOP STEALING", "IN_SUPERMARKET", True),
        ]

        CHOICES, BRANCHES = {}, {}
        for k, label, branch, ok in options:
            if ok:
                CHOICES[k] = label
                BRANCHES[k] = branch

        self.get_choice(
            KEY="SHOPLIFT", CHOICES=CHOICES, BRANCHES=BRANCHES, press_button=False
        )

    def STEAL_DOLL(self):
        self.stats["TOY"] = "STEAL TOY"
        self.dbhh.to_pos("WP_SUPERMARKET_DOLL_TEMP")
        self.dbhh.to_pos("WP_SUPERMARKET_DOLL")
        self.dbhh.to_view("VW_SUPERMARKET_DOLL")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_STEAL_DOLL")
        self.dbhh.wait_for_ui("UI_2")
        self.dbhh.interact(it="R_DOWN")
        self.status["DOLL"] = True
        if self.status["LAST_STEAL"] == "NONE":
            self.next_branch = "SHOPLIFT"
            self.dbhh.to_pos("WP_SUPERMARKET_DOLL_TEMP")
            self.dbhh.to_pos_ui("WP_TALK_TO_CLERK")
        else:
            self.next_branch = "BE_SEEN_STEALING"
        self.status["LAST_STEAL"] = "DOLL"

    def STEAL_FOOD(self):
        self.stats["CHOCOLATE_BAR"] = "STEAL CHOCOLATE BAR"
        self.dbhh.to_pos_ui("WP_SUPERMARKET_FOOD")
        self.dbhh.interact("IT_STEAL_FOOD")
        self.dbhh.wait_for_ui("UI_2")
        self.dbhh.interact("IT_STEAL_FOOD_2")
        self.status["FOOD"] = True
        if self.status["LAST_STEAL"] == "NONE":
            self.next_branch = "SHOPLIFT"
            self.dbhh.to_pos_ui("WP_TALK_TO_CLERK")
            self.dbhh.vg_press_button("BT_CHANGE_VIEW_ANGLE")
        else:
            self.next_branch = "BE_SEEN_STEALING"
        self.status["LAST_STEAL"] = "FOOD"

    def BE_SEEN_STEALING(self):
        self.dbhh.wait_for_ui("UI_2")
        self.get_choice()

    def TAKE_GUN_WHEN_STEALING(self):
        self.dbhh.wait_for_ui("UI_3")
        self.get_choice("SUPERMARKET_STEAL_WORDS")
        if self.status["LAST_STEAL"] == "FOOD":
            self.dbhh.wait_for_cutscene("CS_TAKE_GUN_WHEN_STEALING_FOOD")
        if self.status["LAST_STEAL"] == "DOLL":
            self.dbhh.wait_for_cutscene("CS_TAKE_GUN_WHEN_STEALING_DOLL")
            self.dbhh.to_pos("WP_TAKE_THE_MONEY_BY_THE_WAY_DOLL")
        if self.status["LAST_STEAL"] == "WIRE_CUTTER":
            self.dbhh.wait_for_cutscene("CS_TAKE_GUN_WHEN_STEALING_WIRE_CUTTER")
            self.dbhh.to_pos("WP_TAKE_THE_MONEY_BY_THE_WAY_WIRE_CUTTER_0")
            self.dbhh.to_pos("WP_TAKE_THE_MONEY_BY_THE_WAY_WIRE_CUTTER_1")
        self.dbhh.to_pos("WP_TAKE_THE_MONEY_BY_THE_WAY")
        self.dbhh.to_view("VW_TAKE_THE_MONEY_BY_THE_WAY")
        self.dbhh.wait_for_ui("UI_1")
        self.get_choice("TAKE_THE_MONEY_BY_THE_WAY")

    def TAKE_THE_MONEY_BY_THE_WAY(self):
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact(it="R_DOWN", pause=2, retry=0)
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_press_button(button="LEFT_SHOULDER", duration=1)
        self.stats["TM"] = "TAKE MONEY"
        self.dbhh.wait_for_ui("UI_4")
        self.dbhh.vg_press_button("BT_B")
        keys_to_remove = ["SHOPLIFT", "LAST_STEAL"]
        for key in keys_to_remove:
            self.status.pop(key, None)

    def GIVE_UP_STEALING_IN_SUPERMARKET(self):
        self.status["FOOD"] = False
        self.status["DOLL"] = False
        self.dbhh.wait_for_cutscene("CS_GIVE_UP_STEALING")
        keys_to_remove = ["SHOPLIFT", "LAST_STEAL"]
        for key in keys_to_remove:
            self.status.pop(key, None)

    def THREATEN_CLERK_WITH_THE_GUN(self):
        self.stats["STEAL_MONEY"] = "USE GUN"
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.exp_rj_interact("IT_SUPERMARKET_TAKE_GUN_1")
        self.dbhh.wait_for_ui("UI_2")
        self.dbhh.vg_press_button(button="B")
        self.dbhh.wait_for_ui("UI_LET_ALICE_WAIT_OUTSIDE")
        self.get_choice("SUPERMARKET_GRAB_WORDS")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_press_button("BT_SUPERMARKET_TAKE_GUN_2")
        self.dbhh.wait_for_ui("UI_CASH_REGISTER")
        self.get_choice("SUPERMARKET_SOMEONE_ENTER_WHEN_GRAB")

    def GIVE_UP_FOR_SOMEONE_ENTER(self):
        self.dbhh.wait_for_cutscene("CS_GIVE_UP_FOR_SOMEONE_ENTER")
        if self.status["FOOD"]:
            self.status["FOOD"] = False
        if self.status["DOLL"]:
            self.status["DOLL"] = False
        keys_to_remove = ["SHOPLIFT", "LAST_STEAL"]
        for key in keys_to_remove:
            self.status.pop(key, None)

    def CONTINUE_GRAB_1(self):
        self.dbhh.wait_for_ui("UI_CONTINUE_GRAB")
        self.get_choice()

    def CONTINUE_GRAB_2(self):
        self.dbhh.wait_for_ui("UI_3")
        self.get_choice()

    def CONFRONT_WITH_CLERK(self):
        self.dbhh.wait_for_ui("UI_2")
        self.get_choice()

    def CONVINCE_THE_CLERK(self):
        self.dbhh.wait_for_ui("UI_4")
        self.dbhh.vg_press_button("BT_B")
        for key in ["SHOPLIFT", "LAST_STEAL"]:
            self.status.pop(key, None)

    def GIVE_UP_IN_CONFRONTING(self):
        self.dbhh.wait_for_cutscene("CS_GIVE_UP_IN_CONFRONTING")
        if self.status["FOOD"]:
            self.status["FOOD"] = False
        if self.status["DOLL"]:
            self.status["DOLL"] = False
        for key in ["SHOPLIFT", "LAST_STEAL"]:
            self.status.pop(key, None)

    def GRAB_SMOOTHLY(self):
        self.stats["TM"] = "TAKE MONEY"
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_press_button("BT_SUPERMARKET_GET_MONEY")
        self.dbhh.wait_for_ui("UI_2")
        self.get_choice("EXPLAIN_TO_ALICE_ABOUT_MONEY")

    def EXPLAIN_TO_ALICE_WHY_GRAB(self):
        self.dbhh.wait_for_ui("UI_4")
        self.get_choice("EXPLAIN_TO_ALICE_WHY_GRAB")
        self.dbhh.wait_for_ui("UI_4")
        self.dbhh.vg_press_button("BT_B")
        for key in ["SHOPLIFT", "LAST_STEAL"]:
            self.status.pop(key, None)

    def LIE_MONEY(self):
        self.dbhh.wait_for_ui("UI_4")
        self.dbhh.wait(seconds=1)
        self.dbhh.vg_press_button("BT_B")
        for key in ["SHOPLIFT", "LAST_STEAL"]:
            self.status.pop(key, None)

    def USING_ALICE_AS_DIVERSION_TO_STEAL_MONEY(self):
        self.stats["STEAL_MONEY"] = "USING ALICE AS A DIVERSION"
        self.stats["TM"] = "TAKE MONEY"
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.to_pos_ui("WP_SCAN_CAN_STACK")
        self.dbhh.vg_press_button("BT_SCAN_CAN_STACK")
        # self.dbhh.wait_for_cutscene("CS_SCAN_CAN_STACK") here, the cutscene is unstable
        self.dbhh.to_pos_ui("WP_USING_ALICE_AS_DIVERSION")
        self.dbhh.vg_press_button("BT_A")
        self.dbhh.wait_for_ui("UI_2")
        self.dbhh.vg_press_button("BT_B")
        self.dbhh.wait_for_cutscene("CS_USING_ALICE_AS_DIVERSION")
        self.dbhh.vg_press_button(button="LEFT_SHOULDER")
        self.dbhh.wait(seconds=25, speedup=False)
        self.dbhh.to_pos_ui("WP_SUPERMARKET_REGISTER")
        self.dbhh.wait(seconds=1)
        self.dbhh.interact("IT_OPEN_SUPERMARKET_REGISTER")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.exp_rj_interact("IT_STEAL_MONEY")
        self.dbhh.wait_for_ui("UI_USING_ALICE_AS_DIVERSION")
        self.get_choice("EXPLAIN_TO_ALICE_WHY_STEAL_MONEY")
        self.dbhh.wait_for_ui("UI_4")
        self.dbhh.vg_press_button("BT_B")

        keys_to_remove = ["SHOPLIFT", "LAST_STEAL"]
        for key in keys_to_remove:
            self.status.pop(key, None)

    def ENTER_MOTEL(self):
        keys_to_remove = [
            "SHOPLIFT",
            "LAST_STEAL",
        ]
        for key in keys_to_remove:
            self.status.pop(key, None)
        self.dbhh.to_pos_only_ui("WP_MOTEL_DOOR")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.exp_rj_interact("IT_OPEN_MOTEL_DOOR")
        self.dbhh.wait_for_ui("UI_ENTER_MOTEL")
        self.dbhh.interact("IT_PAY_MOTEL")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_PEN_MOTEL")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.qte("QTE_SIGN_NAME")
        self.dbhh.wait_for_ui("UI_4")
        self.get_choice("CHEAT_DRIVER_LICENSE")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.exp_rj_interact("IT_ROOM_CARD")
        self.dbhh.wait_for_cutscene("CS_ENTER_MOTEL")
        self.dbhh.to_pos("WP_ENTER_ROOM_0")
        self.dbhh.to_pos("WP_ENTER_ROOM_1")
        self.dbhh.to_pos("WP_ENTER_ROOM_2")
        self.dbhh.to_pos_only_ui("WP_ENTER_ROOM_3")
        self.dbhh.interact("IT_OPEN_ROOM_DOOR_IN_MOTEL")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_OPEN_LIGHT_IN_MOTEL")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_press_button("BT_TALK_TO_ALICE_IN_MOTEL")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_HANG_CLOTHES_IN_MOTEL")
        self.dbhh.wait_for_cutscene("CS_HANG_CLOTHES_IN_MOTEL")
        self.dbhh.to_pos_ui("WP_LOOK_OUTSIDE_IN_MOTEL")
        self.dbhh.interact("IT_LOOK_OUTSIDE_IN_MOTEL")
        self.dbhh.wait_for_cutscene("CS_LOOK_OUTSIDE_IN_MOTEL")
        self.dbhh.to_pos("WP_HANG_CLOTHES_IN_MOTEL")
        if self.status["FOOD"]:
            self.dbhh.to_pos_only_ui("UI_GIVE_ALICE_FOOD_IN_MOTEL")
            self.dbhh.interact("IT_GIVE_ALICE_FOOD_IN_MOTEL")
            self.dbhh.wait_for_cutscene("CS_GIVE_ALICE_FOOD_IN_MOTEL")
            self.dbhh.vg_press_button("BT_CHANGE_VIEW_ANGLE")
        self.dbhh.to_pos("WP_GIVE_ALICE_FOOD_IN_MOTEL")
        self.dbhh.to_pos_ui("WP_REMOVE_ALICE_CLOTHES")
        self.dbhh.interact("IT_REMOVE_ALICE_CLOTHES")
        self.dbhh.wait_for_cutscene("CS_REMOVE_ALICE_CLOTHES")
        self.dbhh.to_pos("WP_WASH_ALICE_CLOTHES_0")
        self.dbhh.to_pos_ui("WP_WASH_ALICE_CLOTHES_1")
        self.dbhh.interact("IT_DROP_ALICE_CLOTHES")
        self.dbhh.wait_for_cutscene("CS_DROP_ALICE_CLOTHES")
        self.dbhh.to_pos("WP_WASH_ALICE_CLOTHES_2")
        self.dbhh.to_pos_ui("WP_TALK_TO_ALICE_AGAIN")
        self.dbhh.vg_press_button("BT_TALK_TO_ALICE_AGAIN")
        self.dbhh.wait_for_ui("UI_2")
        self.get_choice("PROMISE_ALICE_IN_MOTEL")
        self.dbhh.wait_for_ui("UI_FOREVER")
        self.dbhh.vg_press_button("BT_FOREVER")
        self.dbhh.wait_for_cutscene("CS_FOREVER")
        self.dbhh.to_pos_ui("WP_TURN_OFF_LIGHT_IN_MOTEL")
        self.dbhh.interact("IT_TURN_OFF_LIGHT_IN_MOTEL")
        if self.status["DOLL"]:
            self.dbhh.wait_for_ui("UI_1")
            self.dbhh.exp_rj_interact("IT_GIVE_ALICE_DOLL_IN_MOTEL")
            self.dbhh.wait_for_no_ui("NO_UI")
        self.dbhh.wait_for_ui("UI_KISS_ALICE")
        self.dbhh.interact("IT_KISS_ALICE")
        self.dbhh.wait_for_ui("UI_2")

        keys_to_remove = [
            "FOOD",
            "DOLL",
        ]
        for key in keys_to_remove:
            self.status.pop(key, None)

        self.get_choice("SLEEP_WITH_ALICE_IN_MOTEL")

    def SLEEP_WITH_ALICE_IN_MOTEL(self):
        self.stats["SLEEP_IN_MOTEL"] = "KARA SLEEP NEXT TO ALICE"
        self.dbhh.interact("IT_SLEEP_WITH_ALICE_IN_MOTEL")

    def SLEEP_ALONE_IN_MOTEL(self):
        self.stats["SLEEP_IN_MOTEL"] = "WATCH ALICE FROM CHAIR"
        self.dbhh.interact("IT_SLEEP_ALONE_IN_MOTEL")
        self.dbhh.to_pos_only_ui("WP_SLEEP_ALONE_IN_MOTEL")
        self.dbhh.interact("IT_SLEEP_IN_CHAIR")

    def ENTER_PARKING_LOT(self):
        self.stats["CPL"] = "CHECK PARKING LOT"
        self.dbhh.to_pos("WP_PARKING_LOT_TEMP")
        self.dbhh.to_pos_ui("WP_PARKING_LOT_DOOR")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_press_button("BT_SCAN_PARKING_LOT")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_ENTER_PARKING_LOT_1")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.qte(button="X", num_poi=1)
        self.dbhh.wait_for_cutscene("CS_ENTER_PARKING_LOT")
        self.dbhh.to_pos_ui("WP_CAR")

        self.dbhh.to_pos_ui("WP_ENTER_SQUAT_RIGHT")
        self.dbhh.interact("IT_LOOK_SQUAT_RIGHT")
        self.dbhh.wait(seconds=1)
        self.dbhh.obs()
        self.dbhh.wait_for_cutscene("CS_LOOK_SQUAT_RIGHT")
        self.dbhh.obs()
        self.dbhh.wait(seconds=1)
        self.dbhh.to_pos_ui("WP_CAR_AFTER_SQUAT")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_press_button("BT_SCAN_CAR")
        self.dbhh.wait_for_ui("UI_1_WITHOUT_OBS")
        self.dbhh.vg_press_button("BT_OPEN_CAR_1")
        self.dbhh.wait_for_ui("UI_1_WITHOUT_OBS")
        self.dbhh.interact("IT_OPEN_CAR_2")
        self.dbhh.wait_for_ui("UI_1_WITHOUT_OBS")
        self.dbhh.interact("IT_OPEN_CAR_2")
        self.dbhh.wait_for_ui("UI_1_WITHOUT_OBS")
        self.dbhh.interact("IT_OPEN_CAR_2")
        self.dbhh.wait_for_ui("UI_1_WITHOUT_OBS")
        self.dbhh.interact("IT_OPEN_CAR_3")
        self.dbhh.wait_for_ui("UI_1_WITHOUT_OBS")
        self.dbhh.vg_press_button("BT_OPEN_CAR_4")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_OPEN_CAR_5")
        self.dbhh.wait_for_ui("UI_2")
        self.get_choice("IN_PARKING_LOT")

    def STAY_IN_CAR(self):
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_CLOSE_CAR_DOOR")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.exp_rj_interact("IT_ORGANIZE_CAR")
        if self.status["DOLL"] and self.status["FOOD"]:
            self.dbhh.wait_for_ui("UI_2")
            self.dbhh.vg_press_button("BT_GIVE_ALICE_DOLL_IN_CAR")
            self.dbhh.wait_for_ui("UI_1")
            self.dbhh.vg_press_button("BT_GIVE_ALICE_FOOD_IN_CAR")
        elif self.status["DOLL"] and not self.status["FOOD"]:
            self.dbhh.wait_for_ui("UI_1")
            self.dbhh.vg_press_button("BT_GIVE_ALICE_DOLL_IN_CAR")
        elif not self.status["DOLL"] and self.status["FOOD"]:
            self.dbhh.wait_for_ui("UI_1")
            self.dbhh.vg_press_button("BT_GIVE_ALICE_FOOD_IN_CAR")
        self.dbhh.wait_for_ui("UI_2")
        self.get_choice("PROMISE_ALICE_IN_CAR")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_press_button("BT_FOREVER")
        keys_to_remove = [
            "FOOD",
            "DOLL",
            "LAST_STEAL",
        ]
        for key in keys_to_remove:
            self.status.pop(key, None)

    def ENTER_SQUAT(self):
        self.stats["ES"] = "ENTER SQUAT"
        self.stats["IP"] = "CHECK SQUAT"
        self.dbhh.to_pos("WP_WIRE_CUTTER_IN_PARKING_LOT_TEMP")
        self.dbhh.to_pos_ui("WP_WIRE_CUTTER_IN_PARKING_LOT")
        self.dbhh.to_view("VW_WIRE_CUTTER_IN_PARKING_LOT")
        self.dbhh.vg_press_button(button="LEFT_SHOULDER", duration=0.5)
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_TAKE_WIRE_CUTTER_IN_PARKING_LOT")
        self.dbhh.to_pos_ui("WP_ENTER_SQUAT_RIGHT")
        self.dbhh.interact("IT_ENTER_SQUAT_RIGHT_0")
        self.dbhh.wait_for_ui(num_poi=1, after=2)
        self.dbhh.interact(it="R_UP", pause=2, retry=0)
        self.dbhh.wait_for_ui(num_poi=1, after=2)

        for _ in range(3):
            self.dbhh.vg_press_button(button="RIGHT_SHOULDER", duration=0.3)
            self.dbhh.wait_for_ui(num_poi=1, after=2)

        self.dbhh.vg_trigger_down(lr="L")
        self.dbhh.wait_for_ui("UI_2")
        self.dbhh.vg_trigger_down(lr="R")
        self.dbhh.wait_for_ui("UI_3")
        self.dbhh.interact(it="R_UP", pause=3)
        self.dbhh.wait_for_no_ui("NO_UI")
        self.dbhh.reset_gamepad()
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_trigger_down(lr="L")
        self.dbhh.wait_for_ui("UI_2")
        self.dbhh.interact(it="R_UP", pause=3, retry=0)
        self.dbhh.wait_for_ui("UI_2")
        self.dbhh.vg_press_button(button="RIGHT_SHOULDER", keep=True)
        self.dbhh.wait_for_no_ui("NO_UI")
        self.dbhh.reset_gamepad()
        self.dbhh.wait_for_cutscene("CS_ENTER_SQUAT_RIGHT")
        self.dbhh.to_pos("WP_SQUAT_RIGHT_TO_LEFT")
        self.dbhh.to_pos_only_ui("WP_SQUAT_WINDOW_0")
        self.dbhh.interact(it="R_UP")
        self.dbhh.to_pos_ui("WP_SQUAT_WINDOW_1")
        self.dbhh.interact(it="R_UP")
        self.dbhh.wait_for_no_ui("NO_UI")
        self.dbhh.to_pos_only_ui("WP_SQUAT_WINDOW_2")
        self.dbhh.interact(it="R_UP")
        self.dbhh.wait_for_cutscene("CS_SQUAT_WINDOW_2")
        self.dbhh.to_pos("WP_FIND_ALICE")
        self.dbhh.wait_for_ui("UI_CONFRONT_WITH_RALPH")
        self.get_choice("CONFRONT_WITH_RALPH_0")
        self.dbhh.wait_for_ui("UI_4")
        self.get_choice("CONFRONT_WITH_RALPH_1")

    def CALM_RALPH(self):
        self.dbhh.wait_for_ui("UI_2")
        self.get_choice("WHETHER_STAY_IN_SQUAT")

    def LEAVE_SQUAT_TO_CAR(self):
        self.dbhh.wait_for_cutscene("CS_LEAVE_SQUAT_RIGHT")
        self.dbhh.to_pos_ui("WP_CAR_AFTER_SQUAT")
        self.dbhh.interact("IT_ENTER_CAR")
        self.dbhh.wait_for_ui("UI_2")
        self.dbhh.vg_press_button(button="B")

    def STAY_IN_SQUAT(self):
        self.dbhh.wait_for_cutscene("CS_STAY_IN_SQUAT")
        self.dbhh.to_pos("WP_FOLLOW_RALPH_0")
        self.dbhh.to_pos("WP_FOLLOW_RALPH_1")
        self.dbhh.wait_for_cutscene("CS_FOLLOW_RALPH")
        self.dbhh.to_pos_ui("WP_TAKE_WOOD")
        self.dbhh.interact("IT_TAKE_WOOD")
        self.dbhh.to_pos_ui("WP_DROP_WOOD")
        self.dbhh.interact("IT_DROP_WOOD")
        self.dbhh.wait_for_cutscene("CS_DROP_WOOD")
        self.dbhh.vg_press_button("BT_CHANGE_VIEW_ANGLE")
        self.dbhh.to_pos_ui("WP_FIRESTONE")
        self.dbhh.exp_rj_interact("IT_TAKE_FIRESTONE")
        self.dbhh.to_pos("WP_PAPER_TEMP")
        self.dbhh.vg_press_button("BT_CHANGE_VIEW_ANGLE")
        self.dbhh.to_pos_ui("WP_PAPER")
        self.dbhh.interact("IT_TAKE_PAPER")
        self.dbhh.wait_for_no_ui("NO_UI")
        self.dbhh.to_pos_ui("WP_PILLOW")
        self.dbhh.interact("IT_TAKE_PILLOW")
        self.dbhh.to_pos_ui("WP_SET_UP_BED")
        self.dbhh.interact("IT_SET_UP_BED")
        self.dbhh.wait_for_cutscene("CS_SET_UP_BED")
        self.dbhh.to_pos_ui("WP_MAKE_FIRE")
        self.dbhh.interact("IT_MAKE_FIRE")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_SCRATCH_MATCH")
        self.dbhh.wait_for_ui("UI_MAKE_FIRE")
        self.dbhh.vg_press_button("BT_TALK_TO_ALICE")
        self.dbhh.wait_for_ui("UI_2")
        self.get_choice("PROMISE_ALICE_IN_SQUAT")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_press_button("BT_FOREVER")
        self.dbhh.wait_for_ui("UI_KISS_ALICE")
        self.dbhh.interact("IT_KISS_ALICE")
        self.dbhh.wait_for_no_ui("NO_UI")
        if self.status.get("DOLL", False):
            self.dbhh.wait_for_ui("UI_1")
            self.dbhh.exp_rj_interact("IT_GIVE_ALICE_DOLL_IN_SQUAT")
        self.dbhh.wait_for_ui("UI_2")
        keys_to_remove = [
            "FOOD",
            "DOLL",
        ]
        for key in keys_to_remove:
            self.status.pop(key, None)
        self.get_choice("SLEEP_WITH_ALICE_IN_SQUAT")

    def SLEEP_WITH_ALICE_IN_SQUAT(self):
        self.stats["SLEEP_IN_SQUAT"] = "KARA SLEEP NEXT TO ALICE"
        self.dbhh.interact("IT_SLEEP_WITH_ALICE")

    def SLEEP_ALONE_IN_SQUAT(self):
        self.stats["SLEEP_IN_SQUAT"] = "WATCH ALICE FROM CHAIR"
        self.dbhh.interact("IT_SLEEP_ALONE_IN_SQUAT")
        self.dbhh.to_pos_ui("WP_SLEEP_ALONE_IN_SQUAT")
        self.dbhh.interact("IT_SLEEP_IN_CHAIR_IN_SQUAT")

    def ENDING_1(self):
        # 1: Spend night in motel
        self.ending = 0
        self.dbhh.info("Ending 1")

    def ENDING_2(self):
        # 2: Spend night in abandoned car
        self.ending = 1
        self.dbhh.info("Ending 2")

    def ENDING_3(self):
        # 3: Spend night in squat
        self.ending = 2
        self.dbhh.info("Ending 3")
