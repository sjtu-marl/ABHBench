from core.transform import auto_yield_class
from DBHHelper.flow import DBHFlow, E

# THE PAINTER

# 0: Defined by choices
# 1: LEO INTRUDED TO ASK FOR MONEY


@auto_yield_class
class Flow(DBHFlow):
    chapter_number = 5

    def setup(self):
        super().setup()

    def graph(self):
        (
            self.START
            | E >> self.MISSION_START
            | E >> self.DEPOSIT_PACKAGE
            | E >> self.GO_UPSTAIRS
            | E >> self.CARL_ROOM
            | E >> self.GO_DOWNSTAIRS
            | E >> self.SERVE_FOOD
            | E >> self.FIND_SOMETHING_TO_DO
        )
        (
            self.FIND_SOMETHING_TO_DO | E >> self.PLAY_CHESS,
            self.FIND_SOMETHING_TO_DO | E >> self.READ_BOOK,
            self.FIND_SOMETHING_TO_DO | E >> self.PLAY_PIANO,
        )
        (
            self.PLAY_CHESS | E >> self.PLAY_CHESS_WIN,
            self.PLAY_CHESS | E >> self.PLAY_CHESS_LOSE,
            self.PLAY_CHESS | E >> self.PLAY_CHESS_DRAW,
        )
        (
            self.PLAY_CHESS_OVER << E
            | self.PLAY_CHESS_WIN
            | E
            | self.PLAY_CHESS_LOSE
            | E
            | self.PLAY_CHESS_DRAW
        )

        (
            self.READ_BOOK | E >> self.READ_BOOK_THE_REPUBLIC_BY_PLATO,
            self.READ_BOOK | E >> self.READ_BOOK_TRAGEDIES_OF_WILLIAM_SHAKESPEARE,
            self.READ_BOOK | E >> self.READ_BOOK_ODES_BY_JOHN_KEATS,
        )
        (
            self.READ_BOOK_OVER << E
            | self.READ_BOOK_THE_REPUBLIC_BY_PLATO
            | E
            | self.READ_BOOK_TRAGEDIES_OF_WILLIAM_SHAKESPEARE
            | E
            | self.READ_BOOK_ODES_BY_JOHN_KEATS
        )
        self.PLAY_PIANO | E >> self.PLAYING_PIANO
        (
            self.GO_TO_STUDIO << E
            | self.PLAY_CHESS_OVER
            | E
            | self.READ_BOOK_OVER
            | E
            | self.PLAYING_PIANO
        )
        self.GO_TO_STUDIO | E >> self.WAIT_FOR_CARL | E >> self.PAINTING_COPY
        (
            self.PAINTING_COPY | E >> self.PAINT_CARL_PAINTING,
            self.PAINTING_COPY | E >> self.PAINT_STATUE,
            self.PAINTING_COPY | E >> self.PAINT_DESK,
        )
        (
            self.PAINTING_COPYING << E
            | self.PAINT_CARL_PAINTING
            | E
            | self.PAINT_STATUE
            | E
            | self.PAINT_DESK
        )
        self.PAINTING_COPYING | E >> self.PAINT_OWNS_WORK
        (
            self.PAINT_OWNS_WORK | E >> self.PAINT_OWNS_WORK_ANDROIDS,
            self.PAINT_OWNS_WORK | E >> self.PAINT_OWNS_WORK_HUMANITY,
            self.PAINT_OWNS_WORK | E >> self.PAINT_OWNS_WORK_IDENTITY,
        )
        (
            self.PAINTING_OWNS_WORK << E
            | self.PAINT_OWNS_WORK_ANDROIDS
            | E
            | self.PAINT_OWNS_WORK_HUMANITY
            | E
            | self.PAINT_OWNS_WORK_IDENTITY
        )
        (
            self.PAINTING_OWNS_WORK
            | E >> self.ENDING_1
            | E >> self.FLOWCHART
            | E >> self.END
        )

    def MISSION_START(self):
        self.dbhh.set_default_game_speed(self.cfg["DEFAULT_GAME_SPEED"])
        self.dbhh.enter_chapter("CHAPTER")
        self.dbhh.wait_for_cutscene("CS_MISSION_START")

    def DEPOSIT_PACKAGE(self):
        self.dbhh.to_pos_ui("WP_DEPOSIT_PACKAGE")
        self.dbhh.interact("IT_DEPOSIT_PACKAGE")
        self.dbhh.wait_for_cutscene("CS_DEPOSIT_PACKAGE")

    def GO_UPSTAIRS(self):
        self.dbhh.to_pos("WP_GO_UPSTAIRS_1")
        self.dbhh.to_pos("WP_GO_UPSTAIRS_2")
        self.dbhh.to_pos("WP_GO_UPSTAIRS_3")
        self.dbhh.to_pos("WP_GO_UPSTAIRS_4")
        self.dbhh.to_pos_ui("WP_GO_UPSTAIRS_5")
        self.dbhh.exp_rj_interact("IT_GO_UPSTAIRS")

    def CARL_ROOM(self):
        self.dbhh.wait_for_cutscene("CS_CARL_ROOM")
        self.dbhh.to_pos("WP_CARL_ROOM_1")
        self.dbhh.to_pos_ui("WP_CARL_ROOM_2")
        self.dbhh.interact("IT_CARL_ROOM_1")
        self.dbhh.wait_for_ui("UI_CARL_ROOM_1")
        self.dbhh.exp_rj_interact("IT_CARL_ROOM_2")
        self.dbhh.wait_for_ui("UI_CARL_ROOM_2")
        self.dbhh.vg_press_button("BT_CARL_ROOM_1")
        self.dbhh.wait_for_ui("UI_CARL_ROOM_3")
        self.dbhh.vg_press_button("BT_CARL_ROOM_2")
        self.dbhh.wait_for_ui("UI_CARL_ROOM_4")
        self.dbhh.rj_interact("IT_CARL_ROOM_3")
        self.dbhh.wait_for_no_ui("UI_CARL_ROOM_5")
        self.dbhh.reset_gamepad()
        self.dbhh.wait_for_ui("UI_CARL_ROOM_4")
        self.dbhh.vg_press_button("BT_CARL_ROOM_2")
        self.dbhh.rj_interact("IT_CARL_ROOM_3")
        self.dbhh.wait_for_no_ui("UI_CARL_ROOM_5")
        self.dbhh.reset_gamepad()

    def GO_DOWNSTAIRS(self):
        self.dbhh.wait_for_cutscene("CS_GO_DOWNSTAIRS_1")
        self.dbhh.to_pos("WP_GO_DOWNSTAIRS_1_1")
        self.dbhh.to_pos("WP_GO_DOWNSTAIRS_1_2")
        self.dbhh.to_pos("WP_GO_DOWNSTAIRS_1_3")
        self.dbhh.to_pos("WP_GO_DOWNSTAIRS_1_4")
        self.dbhh.wait_for_cutscene("CS_GO_DOWNSTAIRS_2")
        # Staircase
        self.dbhh.to_pos("WP_GO_DOWNSTAIRS_2_1")
        self.dbhh.to_pos_only_ui("WP_GO_DOWNSTAIRS_2_2")
        self.dbhh.interact("IT_GO_DOWNSTAIRS")
        self.dbhh.to_pos("WP_GO_DOWNSTAIRS_3_1")
        self.dbhh.to_pos("WP_GO_DOWNSTAIRS_3_2")
        self.dbhh.to_pos("WP_GO_DOWNSTAIRS_3_3")
        self.dbhh.to_pos("WP_GO_DOWNSTAIRS_3_4")
        self.dbhh.to_pos("WP_GO_DOWNSTAIRS_3_5")

    def SERVE_FOOD(self):
        self.dbhh.wait_for_cutscene("CS_SERVE_FOOD")
        self.dbhh.to_pos("WP_SERVE_FOOD_1_1")
        self.dbhh.to_pos("WP_SERVE_FOOD_1_2")
        self.dbhh.to_pos_ui("WP_SERVE_FOOD_1_3")
        self.dbhh.exp_rj_interact("IT_SERVE_FOOD_1")
        self.dbhh.wait_for_ui("UI_SERVE_FOOD_1")
        self.dbhh.exp_rj_interact("IT_SERVE_FOOD_2")
        self.dbhh.to_pos("WP_SERVE_FOOD_2_1")
        self.dbhh.to_pos("WP_SERVE_FOOD_2_2")
        self.dbhh.to_pos_ui("WP_SERVE_FOOD_2_3")
        self.dbhh.interact("IT_SERVE_FOOD_3")
        # Open Cloche
        self.dbhh.wait_for_ui("UI_SERVE_FOOD_2_1")
        self.dbhh.interact("IT_SERVE_FOOD_4")
        self.dbhh.wait_for_ui("UI_SERVE_FOOD_2_2")
        self.dbhh.exp_rj_interact("IT_SERVE_FOOD_5")
        self.dbhh.wait_for_ui("UI_SERVE_FOOD_2_3")
        self.dbhh.interact("IT_SERVE_FOOD_6")

    def FIND_SOMETHING_TO_DO(self):
        self.dbhh.wait_for_cutscene("CS_FIND_SOMETHING_TO_DO")
        self.dbhh.to_pos("WP_FIND_SOMETHING_TO_DO_1")
        # Go to middle of the room
        self.dbhh.to_pos("WP_FIND_SOMETHING_TO_DO_2")
        self.get_choice(press_button=False)

    def PLAY_CHESS(self):
        self.dbhh.to_pos("WP_PLAY_CHESS_1")
        self.dbhh.to_pos_ui("WP_PLAY_CHESS_2")
        self.dbhh.vg_press_button("BT_FIND_SOMETHING_TO_DO")
        self.dbhh.wait_for_ui("UI_PLAY_CHESS_1")
        self.dbhh.interact("IT_PLAY_CHESS")
        self.dbhh.wait_for_ui("UI_PLAY_CHESS_2")
        self.dbhh.interact("IT_PLAY_CHESS")
        self.dbhh.wait_for_ui("UI_PLAY_CHESS_3")
        self.get_choice()

    def PLAY_CHESS_WIN(self):
        self.dbhh.wait_for_ui("UI_PLAY_CHESS_OVER")
        self.get_choice()

    def PLAY_CHESS_LOSE(self):
        self.dbhh.wait_for_ui("UI_PLAY_CHESS_OVER")
        self.get_choice()

    def PLAY_CHESS_DRAW(self):
        self.dbhh.wait_for_ui("UI_PLAY_CHESS_OVER")
        self.get_choice()

    def PLAY_CHESS_OVER(self):
        self.dbhh.wait_for_ui("UI_PLAY_CHESS_OVER_1")
        self.dbhh.interact("IT_PLAY_CHESS_OVER_1")
        self.dbhh.wait_for_ui("UI_PLAY_CHESS_OVER_2")
        self.dbhh.interact("IT_PLAY_CHESS_OVER_2")
        self.dbhh.to_pos("WP_PLAY_CHESS_OVER")

    def READ_BOOK(self):
        self.dbhh.to_pos_ui("WP_READ_BOOK")
        self.dbhh.vg_press_button("BT_FIND_SOMETHING_TO_DO")
        self.dbhh.wait_for_ui("UI_READ_BOOK_1")
        self.dbhh.interact("IT_READ_BOOK_1")
        self.dbhh.wait_for_ui("UI_READ_BOOK_2")
        self.get_choice(press_button=False)

    def READ_BOOK_THE_REPUBLIC_BY_PLATO(self):
        self.dbhh.interact("IT_READ_BOOK_THE_REPUBLIC_BY_PLATO")
        self.dbhh.wait_for_cutscene("CS_READ_BOOK_THE_REPUBLIC_BY_PLATO")

    def READ_BOOK_TRAGEDIES_OF_WILLIAM_SHAKESPEARE(self):
        self.dbhh.interact("IT_READ_BOOK_TRAGEDIES_OF_WILLIAM_SHAKESPEARE")
        self.dbhh.wait_for_cutscene("CS_READ_BOOK_TRAGEDIES_OF_WILLIAM_SHAKESPEARE")

    def READ_BOOK_ODES_BY_JOHN_KEATS(self):
        self.dbhh.interact("IT_READ_BOOK_ODES_BY_JOHN_KEATS")
        self.dbhh.wait_for_cutscene("CS_READ_BOOK_ODES_BY_JOHN_KEATS")

    def READ_BOOK_OVER(self):
        self.dbhh.to_pos_ui("WP_READ_BOOK_OVER")
        self.dbhh.interact("IT_READ_BOOK_OVER")

    def PLAY_PIANO(self):
        self.dbhh.to_pos_ui("WP_PLAY_PIANO")
        self.dbhh.vg_press_button("BT_FIND_SOMETHING_TO_DO")
        self.dbhh.wait_for_ui("UI_PLAY_PIANO_1")
        self.dbhh.interact("IT_PLAY_PIANO_1")
        self.dbhh.wait_for_ui("UI_PLAY_PIANO_2")
        self.dbhh.exp_rj_interact("IT_PLAY_PIANO_2")
        self.dbhh.wait_for_ui("UI_PLAY_PIANO_3")
        self.get_choice()

    def PLAYING_PIANO(self):
        self.dbhh.wait_for_ui("UI_PLAYING_PIANO_1")
        self.dbhh.interact("IT_PLAYING_PIANO_1")
        self.dbhh.wait_for_ui("UI_PLAYING_PIANO_1")
        self.dbhh.vg_press_button("BT_PLAYING_PIANO")
        count = 0
        while count < 60:
            self.dbhh.vg_press_button("BT_PLAYING_PIANO")
            count += 1
        self.dbhh.vg_press_button("BT_PLAYING_PIANO_STOP")
        self.dbhh.wait_for_ui("UI_PLAYING_PIANO_2")
        self.dbhh.interact("IT_PLAYING_PIANO_1")
        self.dbhh.wait_for_cutscene("CS_PLAYING_PIANO")
        self.dbhh.to_pos_ui("WP_PLAYING_PIANO")
        self.dbhh.interact("IT_PLAYING_PIANO_2")
        self.dbhh.to_pos("WP_FIND_SOMETHING_TO_DO_2")

    def GO_TO_STUDIO(self):
        self.dbhh.to_pos("WP_GO_TO_STUDIO_1_1")
        self.dbhh.to_pos("WP_GO_TO_STUDIO_1_2")
        self.dbhh.wait_for_cutscene("CS_GO_TO_STUDIO")
        self.dbhh.to_pos_ui("WP_GO_TO_STUDIO_2")
        self.dbhh.exp_rj_interact("IT_GO_TO_STUDIO")

    def WAIT_FOR_CARL(self):
        self.dbhh.wait_for_ui("UI_WAIT_FOR_CARL_1")
        self.dbhh.vg_press_button("BT_WAIT_FOR_CARL")
        self.dbhh.wait_for_ui("UI_WAIT_FOR_CARL_2")
        self.dbhh.reset_gamepad()
        self.get_choice()

    def PAINTING_COPY(self):
        self.dbhh.wait_for_ui("UI_PAINTING_COPY_1")
        self.dbhh.interact("IT_PAINTING_COPY_1")
        self.dbhh.wait_for_ui("UI_PAINTING_COPY_2")
        self.get_choice(press_button=False)

    def PAINT_CARL_PAINTING(self):
        self.dbhh.to_view("VW_PAINT_CARL_PAINTING")
        self.dbhh.vg_press_button("BT_PAINT_CARL_PAINTING")

    def PAINT_STATUE(self):
        self.dbhh.to_view("VW_PAINT_STATUE")
        self.dbhh.vg_press_button("BT_PAINT_STATUE")

    def PAINT_DESK(self):
        self.dbhh.to_view("VW_PAINT_DESK")
        self.dbhh.vg_press_button("BT_PAINT_DESK")

    def PAINTING_COPYING(self):
        self.dbhh.wait_for_ui("UI_PAINTING_COPYING_1")
        self.dbhh.vg_press_button("BT_PAINTING_COPYING")
        self.dbhh.wait_for_ui("UI_PAINTING_COPYING_1")
        self.dbhh.interact("IT_PAINTING_COPYING_1")
        self.dbhh.wait_for_ui("UI_PAINTING_COPYING_1")
        self.dbhh.interact("IT_PAINTING_COPYING_2")
        self.dbhh.wait_for_ui("UI_PAINTING_COPYING_1")
        self.dbhh.interact("IT_PAINTING_COPYING_2")

    def PAINT_OWNS_WORK(self):
        self.dbhh.wait_for_ui("UI_PAINT_OWNS_WORK_1")
        self.dbhh.vg_press_button("BT_PAINT_OWNS_WORK_1")
        self.dbhh.wait_for_ui("UI_PAINT_OWNS_WORK_2")
        self.get_choice()

    def PAINT_OWNS_WORK_ANDROIDS(self):
        self.dbhh.wait_for_ui("UI_PAINT_OWNS_WORK_3")
        self.get_choice()

    def PAINT_OWNS_WORK_HUMANITY(self):
        self.dbhh.wait_for_ui("UI_PAINT_OWNS_WORK_3")
        self.get_choice()

    def PAINT_OWNS_WORK_IDENTITY(self):
        self.dbhh.wait_for_ui("UI_PAINT_OWNS_WORK_3")
        self.get_choice()

    def PAINTING_OWNS_WORK(self):
        self.dbhh.wait_for_ui("UI_PAINTING_OWNS_WORK_1")
        self.dbhh.vg_press_button("BT_PAINTING_OWNS_WORK_1")
        self.dbhh.wait_for_ui("UI_PAINTING_OWNS_WORK_1")
        self.dbhh.interact("IT_PAINTING_OWNS_WORK_1")
        self.dbhh.wait_for_ui("UI_PAINTING_OWNS_WORK_1")
        self.dbhh.interact("IT_PAINTING_OWNS_WORK_2")
        self.dbhh.wait_for_ui("UI_PAINTING_OWNS_WORK_1")
        self.dbhh.qte("QTE_PAINTING_OWNS_WORK")
        self.dbhh.wait_for_ui("UI_PAINTING_OWNS_WORK_1")
        self.dbhh.interact("IT_PAINTING_OWNS_WORK_3")
        self.dbhh.wait_for_ui("UI_PAINTING_OWNS_WORK_1")
        self.dbhh.interact("IT_PAINTING_OWNS_WORK_3")
        self.dbhh.wait_for_ui("UI_PAINTING_OWNS_WORK_1")
        self.dbhh.vg_press_button("BT_PAINTING_OWNS_WORK_1")
        self.dbhh.wait_for_ui("UI_PAINTING_OWNS_WORK_1")
        self.dbhh.interact("IT_PAINTING_OWNS_WORK_4")
        self.dbhh.wait_for_cutscene("CS_PAINTING_OWNS_WORK")

    def ENDING_1(self):
        self.ending = 1
        self.dbhh.info("Ending 1")
