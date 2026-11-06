from core.transform import auto_yield_class
from DBHHelper.flow import DBHFlow, E

# The STRATFORD TOWER

# 0: Defined by choices
# 1: The group escaped but Simon was left behind.
# 2: The group escaped.
# 3: The group escaped but Simon was destroyed.


@auto_yield_class
class Flow(DBHFlow):
    chapter_number = 23

    def setup(self):
        super().setup()
        self.status = {"GUARDS_ARE_ALARMED": False, "SIMON_WAS_SHOT": False}

    def graph(self):
        self.START | E >> self.MISSION_START
        self.MISSION_START | E >> self.ACCESS_47TH_FLOOR
        self.ACCESS_47TH_FLOOR | E >> self.ENTER_RESTROOM
        self.ENTER_RESTROOM | E >> self.ACCESS_FIRE_ESCAPE
        self.ACCESS_FIRE_ESCAPE | E >> self.ACCESS_SERVER_ROOM
        self.ACCESS_SERVER_ROOM | E >> self.ATTRACT_GUARDS_AWAY_FROM_DOOR_OF_SERVER_ROOM

        self.ATTRACT_GUARDS_AWAY_FROM_DOOR_OF_SERVER_ROOM | E >> self.HACK_DISPENSER
        self.ATTRACT_GUARDS_AWAY_FROM_DOOR_OF_SERVER_ROOM | E >> self.HACK_ROBOT

        self.IN_SERVER_ROOM << E | self.HACK_DISPENSER | E | self.HACK_ROBOT
        self.IN_SERVER_ROOM | E >> self.LOCK_DOOR_IN_SERVER_ROOM
        self.IN_SERVER_ROOM | E >> self.BE_FOUND_IN_SERVER_ROOM

        (
            self.CUT_WINDOW_IN_SERVER_ROOM << E
            | self.LOCK_DOOR_IN_SERVER_ROOM
            | E
            | self.BE_FOUND_IN_SERVER_ROOM
        )

        self.CUT_WINDOW_IN_SERVER_ROOM | E >> self.CRAWLING_ON_THE_SURFACE_OF_BUILDING
        self.CRAWLING_ON_THE_SURFACE_OF_BUILDING | E >> self.CALL_SERVICES_LIFT
        self.CALL_SERVICES_LIFT | E >> self.ENTER_MAIN_ACCESS

        self.ENTER_MAIN_ACCESS | E >> self.RUSE_IN_MAIN_ACCESS
        self.ENTER_MAIN_ACCESS | E >> self.ASSAULT_IN_MAIN_ACCESS

        self.ASSAULT_IN_MAIN_ACCESS | E >> self.SHOOT_LEFT_GUARD_IN_MAIN_ACCESS
        self.ASSAULT_IN_MAIN_ACCESS | E >> self.SHOOT_RIGHT_GUARD_IN_MAIN_ACCESS

        (
            self.ENTER_BROADCAST_ROOM << E
            | self.SHOOT_LEFT_GUARD_IN_MAIN_ACCESS
            | E
            | self.SHOOT_RIGHT_GUARD_IN_MAIN_ACCESS
            | E
            | self.RUSE_IN_MAIN_ACCESS
        )
        self.ENTER_BROADCAST_ROOM | E >> self.BROADCAST_MESSAGE
        self.BROADCAST_MESSAGE | E >> self.ESCAPE_SMOOTHLY
        self.BROADCAST_MESSAGE | E >> self.SIMON_WAS_SHOT_IN_BROADCAST_ROOM
        self.SIMON_WAS_SHOT_IN_BROADCAST_ROOM | E >> self.SAVE_SIMON_IN_BROADCAST_ROOM

        (
            self.SIMON_WAS_SHOT_IN_BROADCAST_ROOM
            | E >> self.ABANDON_SIMON_IN_BROADCAST_ROOM
        )
        self.ESCAPE_SMOOTHLY | E >> self.WHETHER_KILL_SIMON_ON_ROOFTOP
        self.SAVE_SIMON_IN_BROADCAST_ROOM | E >> self.WHETHER_KILL_SIMON_ON_ROOFTOP

        self.WHETHER_KILL_SIMON_ON_ROOFTOP | E >> self.KILL_SIMON_ON_ROOFTOP
        self.WHETHER_KILL_SIMON_ON_ROOFTOP | E >> self.LEAVE_SIMON_ON_ROOFTOP

        self.ENDING_2 << E | self.ESCAPE_SMOOTHLY

        (
            self.ENDING_1 << E
            | self.LEAVE_SIMON_ON_ROOFTOP
            | E
            | self.KILL_SIMON_ON_ROOFTOP
        )

        (
            self.ENDING_3 << E
            | self.KILL_SIMON_ON_ROOFTOP
            | E
            | self.ABANDON_SIMON_IN_BROADCAST_ROOM
        )

        self.FLOWCHART << E | self.ENDING_1 | E | self.ENDING_2 | E | self.ENDING_3
        self.FLOWCHART | E >> self.END

    def MISSION_START(self):
        self.dbhh.enter_chapter("CHAPTER")
        self.dbhh.set_default_game_speed(self.cfg["DEFAULT_GAME_SPEED"])
        self.dbhh.wait_for_cutscene("CS_MISSION_START")

    def ACCESS_47TH_FLOOR(self):
        self.dbhh.to_pos_ui("WP_RECEPTIONIST")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_press_button("BT_TALK_TO_RECEPTIONIST")
        self.dbhh.wait_for_cutscene("CS_TALK_TO_RECEPTIONIST")
        self.dbhh.to_pos_ui("WP_SUPERVISOR")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_press_button("BT_START_ANALYZE_SUPERVISOR")

        self.dbhh.vg_press_button("BT_ANALYZE_SUPERVISOR")
        self.dbhh.wait(seconds=2)
        self.dbhh.obs()
        self.dbhh.vg_release_button(button="Y")
        self.dbhh.wait(seconds=1)
        for ip in [
            "IP_ANALYZE_SUPERVISOR_2",
            "IP_ANALYZE_SUPERVISOR_3",
            "IP_ANALYZE_SUPERVISOR_4",
            "IP_ANALYZE_SUPERVISOR_5",
        ]:
            self.dbhh.to_ip(ip)
            self.dbhh.obs()
            self.dbhh.vg_release_button(button="Y")
        self.dbhh.wait(seconds=2)
        self.dbhh.wait_for_ui("UI_CALL_SUPERVISOR")
        self.dbhh.vg_press_button("BT_CALL_SUPERVISOR")
        self.dbhh.wait_for_ui("UI_3")

        CHOICE = self.get_choice("CALL_SUPERVISOR")
        if CHOICE == "Y":
            self.stats["CALL_SUPERVISOR"] = "POSE AS PARKING ATTENDANT"
        elif CHOICE == "B":
            self.stats["CALL_SUPERVISOR"] = "POSE AS TEACHER"
        elif CHOICE == "A":
            self.stats["CALL_SUPERVISOR"] = "POSE AS FIREMAN"

        self.dbhh.wait(seconds=3)
        self.dbhh.to_pos("WP_RECEPTIONIST_TEMP")
        self.dbhh.to_pos_ui("WP_RECEPTIONIST_AGAIN")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_press_button("BT_TALK_TO_RECEPTIONIST_AGAIN")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.exp_rj_interact("IT_GIVE_ID_TO_RECEPTIONIST")
        self.dbhh.wait_for_cutscene("CS_TALK_TO_RECEPTIONIST_AGAIN")
        self.dbhh.to_pos("WP_GATE_MACHINE_TEMP")
        self.dbhh.to_pos("WP_ELEVATOR_TEMP")
        self.dbhh.vg_press_button("BT_CHANGE_VIEW_ANGLE")
        self.dbhh.to_pos_ui("WP_ELEVATOR")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_CALL_ELEVATOR")
        self.dbhh.wait(seconds=8)
        self.dbhh.to_pos_only_ui("WP_IN_ELEVATOR")
        self.dbhh.interact("IT_PUSH_ELEVATOR_BUTTON")
        self.dbhh.wait_for_cutscene("CS_GET_OUT_OF_ELEVATOR")
        self.dbhh.to_pos("WP_OUT_OF_ELEVATOR")

    def ENTER_RESTROOM(self):
        self.dbhh.to_pos("WP_IN_47TH_FLOOR_0")
        self.dbhh.to_pos("WP_IN_47TH_FLOOR_1")
        self.dbhh.to_pos_ui("WP_RESTROOM_DOOR")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.exp_rj_interact("IT_OPEN_RESTROOM_DOOR")
        self.dbhh.wait_for_cutscene("CS_ENTER_RESTROOM")
        self.dbhh.to_pos_ui("WP_STALL_IN_RESTROOM")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_ENTER_STALL_IN_RESTROOM")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_CLIMB_IN_STALL")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.exp_rj_interact("IT_RETRIEVE_PACKAGE_IN_STALL")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_EXIT_STALL")
        self.dbhh.wait_for_cutscene("CS_EXIT_STALL")
        self.dbhh.to_pos_ui("WP_EXIT_RESTROOM")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_EXIT_RESTROOM")
        self.dbhh.wait_for_cutscene("CS_EXIT_RESTROOM")

    def ACCESS_FIRE_ESCAPE(self):
        self.dbhh.to_pos("WP_FIND_ANDROID_0")
        self.dbhh.to_pos("WP_FIND_ANDROID_1")
        self.dbhh.to_pos("WP_FIND_ANDROID_2")
        self.dbhh.to_pos_ui("WP_ANDROID_IN_MEETING_ROOM")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_CONVERT_ANDROID_IN_MEETING_ROOM")
        self.dbhh.wait_for_cutscene("CS_CONVERT_ANDROID_IN_MEETING_ROOM")
        self.dbhh.to_pos("WP_ACCESS_HAND_TRUCK_0")
        self.dbhh.to_pos("WP_ACCESS_HAND_TRUCK_1")
        self.dbhh.to_pos_ui("WP_HAND_TRUCK")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_TAKE_HAND_TRUCK")
        self.dbhh.wait_for_cutscene("CS_TAKE_HAND_TRUCK")
        self.dbhh.to_pos("WP_ACCESS_FIRE_ESCAPE")
        self.dbhh.to_pos_only_ui("WP_FIRE_ESCAPE")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_OPEN_FIRE_ESCAPE_DOOR")
        self.dbhh.wait_for_cutscene("CS_OPEN_FIRE_ESCAPE_DOOR")

    def ACCESS_SERVER_ROOM(self):
        self.dbhh.to_pos("WP_FOLLOW_NORTH_0")
        self.dbhh.to_pos("WP_FOLLOW_NORTH_1")
        self.dbhh.wait_for_cutscene("CS_OBSERVE_SERVER_ROOM_GUARDS")

    def ATTRACT_GUARDS_AWAY_FROM_DOOR_OF_SERVER_ROOM(self):
        CHOICE = self.get_choice("ATTRACT_GUARDS_AWAY_FROM_DOOR_OF_SERVER_ROOM")
        if CHOICE == "A":
            self.stats["ATTRACT_GUARDS_AWAY_FROM_DOOR_OF_SERVER_ROOM"] = (
                "HACK DISPENSER"
            )
        elif CHOICE == "B":
            self.stats["ATTRACT_GUARDS_AWAY_FROM_DOOR_OF_SERVER_ROOM"] = "HACK ROBOT"

    def HACK_DISPENSER(self):
        self.dbhh.to_pos("WP_HACK_DISPENSER")
        self.dbhh.to_view("VW_HACK_DISPENSER")
        self.dbhh.vg_trigger_down("LR_OBSERVATION_MODE")
        self.dbhh.wait(seconds=2)
        self.dbhh.vg_press_button("BT_HACK_DISPENSER")
        self.dbhh.wait_for_no_ui("UI_1")
        self.dbhh.reset_gamepad()
        self.dbhh.wait_for_cutscene("CS_HACK_DISPENSER")

    def HACK_ROBOT(self):
        self.dbhh.to_pos_ui("WP_HACK_ROBOT")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_HACK_ROBOT")
        self.dbhh.wait_for_cutscene("CS_HACK_ROBOT")

    def IN_SERVER_ROOM(self):
        self.get_choice("WHETHER_LOCK_DOOR_IN_SERVER_ROOM")

    def LOCK_DOOR_IN_SERVER_ROOM(self):
        self.stats["WHETHER_LOCK_DOOR_IN_SERVER_ROOM"] = "LOCK THE DOOR"

        self.dbhh.to_pos_ui("WP_LOCK_DOOR_IN_SERVER_ROOM")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_LOCK_DOOR_IN_SERVER_ROOM")
        self.dbhh.wait_for_cutscene("CS_LOCK_DOOR_IN_SERVER_ROOM")
        self.dbhh.to_pos_ui("WP_PACKAGE_IN_SERVER_ROOM")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_TAKE_PACKAGE_IN_SERVER_ROOM")
        self.dbhh.wait_for_cutscene("CS_TAKE_PACKAGE_IN_SERVER_ROOM")
        self.dbhh.to_pos_ui("WP_DROP_PACKAGE_IN_SERVER_ROOM")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_DROP_PACKAGE_IN_SERVER_ROOM")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.exp_rj_interact("IT_OPEN_PACKAGE_IN_SERVER_ROOM")
        self.dbhh.interact("IT_PLACE_SAW_ON_WINDOW")

    def BE_FOUND_IN_SERVER_ROOM(self):
        self.status["GUARDS_ARE_ALARMED"] = True
        self.stats["WHETHER_LOCK_DOOR_IN_SERVER_ROOM"] = "FORGET TO LOCK DOOR"

        self.dbhh.to_pos_ui("WP_PACKAGE_IN_SERVER_ROOM")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_TAKE_PACKAGE_IN_SERVER_ROOM")
        self.dbhh.wait_for_cutscene("CS_TAKE_PACKAGE_IN_SERVER_ROOM")
        self.dbhh.to_pos_ui("WP_DROP_PACKAGE_IN_SERVER_ROOM")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_DROP_PACKAGE_IN_SERVER_ROOM")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.exp_rj_interact("IT_OPEN_PACKAGE_IN_SERVER_ROOM")
        self.dbhh.interact("IT_PLACE_SAW_ON_WINDOW")
        self.dbhh.wait_for_ui("UI_3")
        CHOICE = self.get_choice("SOMEONE_ENTER_IN_SERVER_ROOM")
        if CHOICE == "A":
            self.stats["SOMEONE_ENTER_IN_SERVER_ROOM"] = "DRAW GUN"
            self.dbhh.wait_for_ui("UI_1")
            self.dbhh.interact(it="R_RIGHT")
        elif CHOICE == "B":
            self.stats["SOMEONE_ENTER_IN_SERVER_ROOM"] = "STALL"
        else:
            self.stats["SOMEONE_ENTER_IN_SERVER_ROOM"] = "USE ALIBI"

    def CUT_WINDOW_IN_SERVER_ROOM(self):
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_TAKE_LASER_SAW")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.exp_rj_interact("IT_CUT_WINDOW_IN_SERVER_ROOM")
        self.dbhh.wait_for_ui("UI_PULL_GLASS_OUT_OF_WINDOW_IN_SERVER_ROOM")
        self.dbhh.interact("IT_PULL_GLASS_OUT_OF_WINDOW_IN_SERVER_ROOM")
        self.dbhh.wait_for_ui("UI_GO_THROUGH_HOLE_ON_WINDOW_IN_SERVER")
        self.dbhh.exp_rj_interact("IT_GO_THROUGH_HOLE_ON_WINDOW_IN_SERVER")

    def CRAWLING_ON_THE_SURFACE_OF_BUILDING(self):
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_CRAWLING_OUT_OF_PLATFORM")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_GRAB_ROPE")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_press_button("BT_JUMP_OUT_OF_PLATFORM")
        self.dbhh.wait_for_cutscene("CS_JUMP_OUT_OF_PLATFORM")
        # Here are climbing rope.
        self.dbhh.left_joystick_move(x_value_float=0, y_value_float=1)
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.reset_gamepad()
        self.dbhh.interact("IT_TAKE_LASER_SAW_AGAIN")
        self.dbhh.wait_for_ui("UI_CUT_WINDOW_ON_BUILDING")
        self.dbhh.exp_rj_interact("IT_CUT_WINDOW_ON_BUILDING_0")
        self.dbhh.wait_for_ui("UI_CUT_WINDOW_ON_BUILDING")
        self.dbhh.exp_rj_interact("IT_CUT_WINDOW_ON_BUILDING_1")
        self.dbhh.wait_for_ui("UI_CUT_WINDOW_ON_BUILDING")
        self.dbhh.exp_rj_interact("IT_CUT_WINDOW_ON_BUILDING_2")
        self.dbhh.wait_for_cutscene("CS_UI_JUMP_INTO_WINDOW_ON_BUILDING")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_press_button("BT_JUMP_INTO_WINDOW_ON_BUILDING")
        self.dbhh.wait_for_cutscene("CS_JUMP_INTO_WINDOW_ON_BUILDING")

    def CALL_SERVICES_LIFT(self):
        self.dbhh.to_pos("WP_CALL_SERVICES_LIFT_TEMP")
        self.dbhh.to_pos_ui("WP_CALL_SERVICES_LIFT")
        self.dbhh.interact("IT_CALL_SERVICES_LIFT")
        self.dbhh.wait_for_cutscene("CS_CALL_SERVICES_LIFT")

    def ENTER_MAIN_ACCESS(self):
        self.dbhh.to_pos("WP_TOWER_LOCK_TEMP")
        self.dbhh.to_pos_ui("WP_TOWER_LOCK")
        self.dbhh.interact("IT_PLACE_BOMB_ON_TOWER_LOCK")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_ACTIVATE_BOMB_ON_TOWER_LOCK")
        self.dbhh.wait_for_cutscene("CS_ACTIVATE_BOMB_ON_TOWER_LOCK")
        self.dbhh.to_pos("WP_DOOR_TO_MAIN_ACCESS_TEMP")
        self.dbhh.to_pos_ui("WP_DOOR_TO_MAIN_ACCESS")
        self.dbhh.exp_rj_interact("IT_OPEN_DOOR_TO_MAIN_ACCESS")
        self.dbhh.wait_for_ui("UI_2")
        CHOICE = self.get_choice("HOW_TO_GET_RID_OF_GUARDS_IN_MAIN_ACCESS")
        if CHOICE == "B":
            self.stats["HOW_TO_GET_RID_OF_GUARDS_IN_MAIN_ACCESS"] = "RUSE"
        else:
            self.stats["HOW_TO_GET_RID_OF_GUARDS_IN_MAIN_ACCESS"] = "ATTACK"

    def RUSE_IN_MAIN_ACCESS(self):
        self.dbhh.wait_for_cutscene("CS_RUSE_IN_MAIN_ACCESS")
        self.dbhh.to_pos_ui("WP_DRAW_GUN_IN_MAIN_ACCESS")
        self.dbhh.interact("IT_DRAW_GUN_IN_MAIN_ACCESS")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_ORDER_GUARDS_WHEN_RUSE_IN_MAIN_ACCESS")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_KNOCK_OUT_GUARDS_WHEN_RUSE_IN_MAIN_ACCESS")
        self.dbhh.wait_for_cutscene("CS_KNOCK_OUT_GUARDS_WHEN_RUSE_IN_MAIN_ACCESS")

    def ASSAULT_IN_MAIN_ACCESS(self):
        self.dbhh.wait_for_ui("UI_DRAW_GUN_IN_MAIN_ACCESS")
        self.dbhh.interact("IT_DRAW_GUN_IN_MAIN_ACCESS")
        self.dbhh.wait_for_ui("UI_SHOOT_WHO_IN_MAIN_ACCESS")
        self.get_choice("SHOOT_WHO_IN_MAIN_ACCESS")

    def SHOOT_LEFT_GUARD_IN_MAIN_ACCESS(self):
        self.stats["SHOOT_WHO_IN_MAIN_ACCESS"] = "SHOOT GUARD ON PHONE"

        self.dbhh.vg_press_button("BT_SHOOT_LEFT_GUARD_IN_MAIN_ACCESS")
        self.status["SIMON_WAS_SHOT"] = True
        self.dbhh.wait_for_cutscene("CS_SHOOT_GUARD_IN_MAIN_ACCESS")

    def SHOOT_RIGHT_GUARD_IN_MAIN_ACCESS(self):
        self.stats["SHOOT_WHO_IN_MAIN_ACCESS"] = "SHOOT GUARD DRAWING WEAPON"

        self.dbhh.vg_press_button("BT_SHOOT_RIGHT_GUARD_IN_MAIN_ACCESS")
        self.status["GUARDS_ARE_ALARMED"] = True
        self.dbhh.wait_for_cutscene("CS_SHOOT_GUARD_IN_MAIN_ACCESS")

    def ENTER_BROADCAST_ROOM(self):
        self.dbhh.to_pos("WP_DOOR_1_OF_BROADCAST_ROOM")
        self.dbhh.to_pos_ui("WP_DOOR_2_OF_BROADCAST_ROOM")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_AMBUSH_DOOR_OF_BROADCAST_ROOM")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_RING_BELL_OF_BROADCAST_ROOM")
        self.dbhh.wait_for_cutscene("CS_ENTER_BROADCAST_ROOM")
        self.dbhh.to_pos_ui("WP_ANDROID_IN_BROADCAST_ROOM")
        self.dbhh.interact("IT_ORDER_ANDROID_IN_BROADCAST_ROOM")
        self.dbhh.wait_for_ui("UI_2")
        choice = self.get_choice("WHETHER_SHOOT_ESCAPED_HUMAN_IN_BROADCAST_ROOM")
        if choice == "A":
            self.status["GUARDS_ARE_ALARMED"] = True
            self.stats["WHETHER_SHOOT_ESCAPED_HUMAN_IN_BROADCAST_ROOM"] = "DON'T SHOOT"
        else:
            self.stats["WHETHER_SHOOT_ESCAPED_HUMAN_IN_BROADCAST_ROOM"] = "SHOOT"

        self.dbhh.wait_for_cutscene("CS_ESCAPED_HUMAN_IN_BROADCAST_ROOM")

    def BROADCAST_MESSAGE(self):
        self.dbhh.to_pos_ui("WP_BROADCAST_MESSAGE")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_press_button("BT_BROADCAST_MESSAGE")
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.interact("IT_REMOVE_SKIN")
        self.dbhh.wait_for_ui("UI_READY_TO_BROADCAST_MESSAGE")
        self.dbhh.vg_press_button("BT_READY_TO_BROADCAST_MESSAGE")
        self.dbhh.wait_for_ui("UI_2")
        CHOICE_1 = self.get_choice("MESSAGE_1")
        if CHOICE_1 == "B":
            self.stats["MESSAGE_1"] = "BEGIN CALMLY"
        else:
            self.stats["MESSAGE_1"] = "BEGIN DETERMINEDLY"

        self.dbhh.wait_for_ui("UI_4")
        CHOICES_OF_MESSAGE_2_3 = {
            "Y": "RECOGNITION",
            "X": "END OF SLAVERY",
            "B": "EQUAL RIGHTS",
            "A": "FREEDOM OF SPEECH",
        }
        message2_choice = self.get_choice(
            KEY="MESSAGE_2", CHOICES=CHOICES_OF_MESSAGE_2_3
        )
        CHOICES_OF_MESSAGE_2_3.pop(message2_choice)
        CHOICES_OF_MESSAGE_2_3 = dict(
            zip(["Y", "B", "A"], CHOICES_OF_MESSAGE_2_3.values())
        )
        self.dbhh.wait_for_ui("UI_3")
        self.get_choice(KEY="MESSAGE_3", CHOICES=CHOICES_OF_MESSAGE_2_3)
        CHOICES_OF_MESSAGE_4_5 = {
            "Y": "JUSTICE",
            "X": "SEGREGATION",
            "B": "WORK",
            "A": "CIVIL RIGHTS",
        }
        self.dbhh.wait_for_ui("UI_4")
        message4_choice = self.get_choice(
            KEY="MESSAGE_4", CHOICES=CHOICES_OF_MESSAGE_4_5
        )
        CHOICES_OF_MESSAGE_4_5.pop(message4_choice)
        CHOICES_OF_MESSAGE_4_5 = dict(
            zip(["Y", "B", "A"], CHOICES_OF_MESSAGE_4_5.values())
        )
        self.dbhh.wait_for_ui("UI_3")
        self.get_choice(KEY="MESSAGE_5", CHOICES=CHOICES_OF_MESSAGE_4_5)

        self.dbhh.wait_for_ui("UI_3")
        self.get_choice("MESSAGE_6")
        self.dbhh.wait_for_ui("UI_2")
        CHOICE_END = self.get_choice("MESSAGE_END")
        if CHOICE_END == "B":
            self.stats["MESSAGE_END"] = "END PEACEFULLY"
        else:
            self.stats["MESSAGE_END"] = "END DETERMINEDLY"

        if self.status["GUARDS_ARE_ALARMED"]:
            self.next_branch = "SIMON_WAS_SHOT_IN_BROADCAST_ROOM"
        else:
            self.next_branch = "ESCAPE_SMOOTHLY"

    def ESCAPE_SMOOTHLY(self):
        self.dbhh.wait_for_cutscene("CS_MESSAGE_END_SMOOTHLY")
        self.dbhh.to_pos("WP_EXIT_BROADCAST_ROOM_SMOOTHLY")
        if not self.status["SIMON_WAS_SHOT"]:
            self.dbhh.wait_for_cutscene("CS_EXIT_BROADCAST_ROOM_SMOOTHLY")
            self.dbhh.to_pos("WP_ESCAPED_ROOFTOP")
            self.next_branch = "ENDING_2"
        else:
            self.next_branch = "WHETHER_KILL_SIMON_ON_ROOFTOP"
        self.status.pop("SIMON_WAS_SHOT", None)
        self.status.pop("GUARDS_ARE_ALARMED", None)

    def SIMON_WAS_SHOT_IN_BROADCAST_ROOM(self):
        self.status.pop("SIMON_WAS_SHOT", None)
        self.status.pop("GUARDS_ARE_ALARMED", None)
        CHOICE = self.get_choice("WHETHER_SAVE_SIMON_IN_BROADCAST_ROOM")
        if CHOICE == "A":
            self.stats["WHETHER_SAVE_SIMON_IN_BROADCAST_ROOM"] = "SAVE SIMON"
        else:
            self.stats["WHETHER_SAVE_SIMON_IN_BROADCAST_ROOM"] = "LEAVE SIMON"

    def SAVE_SIMON_IN_BROADCAST_ROOM(self):
        self.dbhh.right_joystick_move(x_value_float=1, y_value_float=0)
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_press_button("BT_SAVE_SIMON_IN_BROADCAST_ROOM")
        self.dbhh.reset_gamepad()
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.qte("QTE_SAVE_SIMON_IN_BROADCAST_ROOM")

    def ABANDON_SIMON_IN_BROADCAST_ROOM(self):
        self.dbhh.right_joystick_move(x_value_float=-1, y_value_float=0)
        self.dbhh.wait_for_ui("UI_1")
        self.dbhh.vg_press_button("BT_ABANDON_SIMON_IN_BROADCAST_ROOM")
        self.dbhh.reset_gamepad()
        self.dbhh.wait_for_cutscene("CS_ABANDON_SIMON_IN_BROADCAST_ROOM")
        self.dbhh.to_pos("WP_ESCAPED_ROOFTOP")

    def WHETHER_KILL_SIMON_ON_ROOFTOP(self):
        self.dbhh.wait_for_ui("UI_2")
        CHOICE = self.get_choice("WHETHER_KILL_SIMON_ON_ROOFTOP")
        if CHOICE == "B":
            self.stats["WHETHER_KILL_SIMON_ON_ROOFTOP"] = "KILL SIMON"
        else:
            self.stats["WHETHER_KILL_SIMON_ON_ROOFTOP"] = "LEAVE SIMON"

    def KILL_SIMON_ON_ROOFTOP(self):
        choice = self.get_choice("CONFIRM_KILL_SIMON_ON_ROOFTOP")
        if choice == "B":
            self.dbhh.wait_for_cutscene("CS_KILL_SIMON_ON_ROOFTOP")
            self.next_branch = "ENDING_3"
        else:
            self.dbhh.wait_for_cutscene("CS_LEAVE_SIMON_ON_ROOFTOP")
            self.next_branch = "ENDING_1"
        self.dbhh.to_pos("WP_ESCAPED_ROOFTOP")

    def LEAVE_SIMON_ON_ROOFTOP(self):
        self.dbhh.wait_for_cutscene("CS_LEAVE_SIMON_ON_ROOFTOP")

    def ENDING_1(self):
        # 1: The group escaped but Simon was left behind.
        self.ending = 1
        self.dbhh.info("Ending 1")

    def ENDING_2(self):
        # 2: The group escaped.
        self.ending = 2
        self.dbhh.info("Ending 2")

    def ENDING_3(self):
        # 3: The group escaped but Simon was destroyed.
        self.ending = 3
        self.dbhh.info("Ending 3")
