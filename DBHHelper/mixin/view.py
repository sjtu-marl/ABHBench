import time
from typing import override

from core.transform import register_auto_yield
from core.utils import dict_config
from DBHHelper.api import DBHHelperAPI
from DBHHelper.utils import cross_product, vector_magnitude, vector_subtract


class ViewMixin(DBHHelperAPI):
    def _update_joystick(self, x_value_float, y_value_float, prev_x, prev_y):
        """Only update the gamepad if the joystick position has changed."""
        if x_value_float != prev_x or y_value_float != prev_y:
            self.gamepad.right_joystick_float(
                x_value_float=x_value_float, y_value_float=y_value_float
            )
            self.gamepad.update()
            return x_value_float, y_value_float
        return prev_x, prev_y

    def _to_ip(self, ip, init_loc, init_view, repeat=5):
        self.debug(f"Moving to ip {ip}, {init_loc}, {init_view}")
        if init_loc == "LT":
            x = -1.0
            y = 1.0
        elif init_loc == "RT":
            x = 1.0
            y = 1.0
        elif init_loc == "LB":
            x = -1.0
            y = -1.0
        elif init_loc == "RB":
            x = 1.0
            y = -1.0
        start_time = time.time()
        reached = False
        prev_x, prev_y = None, None  # Initialize previous values

        while True:
            flag = self.read_indicator()
            camera_pos = self.read_camera_pos()
            cur_view = camera_pos[3:]
            d = vector_magnitude(vector_subtract(cur_view, init_view))
            if self._debug_level >= 2:
                self.debug(f"cur: {cur_view}, tar: {init_view}, d: {d}")
            if d < 0.01:
                self.debug("Initial view reached")
                reached = True
                break
            if time.time() - start_time > 15:
                break
            prev_x, prev_y = self._update_joystick(x, y, prev_x, prev_y)
            time.sleep(0.0001)
        if not reached:
            self.debug("Initial view not reached")
            return
        x_dir = -x
        y_dir = -y
        c = 0
        start_time = time.time()
        reached = False

        while True:
            flag = self.read_indicator()
            camera_pos = self.read_camera_pos()
            cur_view = camera_pos[3:]
            d = vector_magnitude(vector_subtract(cur_view[:2], ip[:2]))
            z = ip[2] - cur_view[2]
            if self._debug_level >= 2:
                self.debug(f"cur: {cur_view}, tar: {ip}, d: {d}, flag: {flag}, z: {z}")
            if (d < 0.1 or abs(z) < 0.005) and flag > 0:
                c += 1
                if c == repeat:
                    self.debug("Target view reached")
                    # Reset joystick to center
                    prev_x, prev_y = self._update_joystick(0, 0, prev_x, prev_y)
                    time.sleep(0.01)
                    reached = True
                    break
            else:
                c = 0
            if time.time() - start_time > 15:
                break
            if d > 0.4:
                x = 0.7 * x_dir
            else:
                x = 0.4 * x_dir
            if abs(z) < 0.001:
                y = 0
            elif abs(z) > 0.1:
                y = -0.7 if z > 0 else 0.7
            else:
                y = -0.4 if z > 0 else 0.4
            # Apply joystick input based on calculations
            joystick_x = 0 if y != 0 else x
            joystick_y = y if y != 0 else 0
            prev_x, prev_y = self._update_joystick(
                joystick_x, joystick_y, prev_x, prev_y
            )
            time.sleep(0.0001)
        if not reached:
            self.debug("Target view not reached")
            return

    @register_auto_yield
    @dict_config
    @override
    def to_ip(self, ip, init_loc, init_view, btn="Y", repeat=5):
        before_num_ip = self.read_num_ip()
        while True:
            while True:
                self._to_ip(ip, init_loc, init_view, repeat)
                time.sleep(0.4)
                flag = self.read_indicator()
                if flag > 0:
                    self.debug("Target ip reached")
                    break
            self.vg_press_button(button=btn, duration=3, after=0.1)
            after_num_ip = self.read_num_ip()
            if after_num_ip > before_num_ip:
                yield from self.obs()
                self.vg_press_button(button="A", duration=0.1, after=0.1)
                break

    @dict_config
    @override
    def to_view(self, target_view):
        prev_x, prev_y = None, None  # Initialize previous values
        last_view = None
        last_view_change_time = time.time()

        while True:
            camera_pos = self.read_camera_pos()
            cur_view = camera_pos[3:]

            # Check if view has changed
            if last_view is not None and all(
                abs(cv - lv) < 0.02 for cv, lv in zip(cur_view, last_view)
            ):
                # View hasn't changed, check if it's been stuck for 5 seconds
                if time.time() - last_view_change_time > 5.0:
                    self.debug("View hasn't changed for 5 seconds, resetting gamepad")
                    self.reset_gamepad()
                    last_view_change_time = time.time()  # Reset the timer
                    prev_x, prev_y = None, None  # Reset previous joystick position
            else:
                # View has changed, update last_view and timestamp
                last_view = cur_view
                last_view_change_time = time.time()

            d = cross_product(cur_view[:2], target_view[:2])
            z = target_view[2] - cur_view[2]

            if abs(d) < 0.005 and abs(z) < 0.005:
                self.debug("Target view reached")
                prev_x, prev_y = self._update_joystick(0, 0, prev_x, prev_y)
                time.sleep(0.01)
                break

            if abs(d) > 0.1:
                x = -1.0 if d > 0 else 1.0
            elif abs(d) < 0.01:
                x = -0.2 if d > 0 else 0.2
            else:
                x = -0.4 if d > 0 else 0.4

            if abs(z) > 0.1:
                y = -1.0 if z > 0 else 1.0
            elif abs(z) < 0.01:
                y = -0.2 if z > 0 else 0.2
            else:
                y = -0.4 if z > 0 else 0.4

            if self._debug_level >= 2:
                self.debug(
                    f"cur: {cur_view}, tar: {target_view}, d: {round(d, 3)}, z: {round(z, 3)} x: {x}, y: {y}"
                )
            prev_x, prev_y = self._update_joystick(x, y, prev_x, prev_y)
            time.sleep(0.0001)

    @register_auto_yield
    @dict_config
    @override
    def timeline_slide(self, dirs, view=None):
        if view is not None:
            self.to_view(target_view=view)
        while True:
            flag = self.read_num_poi()
            if flag > 0:
                self.debug("Target timeline reached")
                break
            self.vg_trigger(lr=dirs, duration=0.1, after=0.01)
        self.vg_press_button(button="Y", duration=2)
        yield from self.obs()
