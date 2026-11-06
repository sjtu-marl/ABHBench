import re
from typing import List, override

from DBHHelper.api import DBHHelperAPI


class MenuIndex:
    MAIN_MENU = 50
    PAUSE_MENU = 49
    IN_GAME = 48


class MainMenuIndex:
    UNKNOWN = -1
    MAIN_MENU = 0
    CHAPTER_SELECT = 1
    CHECKPOINT_SELECT = 2
    SAVE = 3
    NOT_MAIN_MENU = 4


class MemMixin(DBHHelperAPI):
    @override
    def mem_setup(self, find_model=True, retry=5):
        self.pm = self.ppack.load_pymem(self.proc.pid)
        self.entrypoint = self.pm.base_address
        if not find_model:
            return
        self._prepare(retry)
        self.find_chapter_num_addr()

        # Verify that find_model_addr and find_model_addr_legacy return the same address
        model_addr = self.find_model_addr()
        model_addr_legacy = self.find_model_addr_legacy()

        # Verify both methods return the same address if both are not None
        if model_addr is not None and model_addr_legacy is not None:
            if model_addr != model_addr_legacy:
                self.warning(
                    f"Address verification failed: find_model_addr={model_addr:#x}, find_model_addr_legacy={model_addr_legacy:#x}"
                )
            else:
                self.info(
                    f"Address verification successful: both methods returned {model_addr:#x}"
                )

    def _prepare(self, retry=5):
        self.wait(1)
        ret = self.find_model_addr()
        _ret = self.find_model_addr_legacy()
        if ret is None and _ret is not None:
            raise Exception(
                "Failed to find model address. Restart the game and try again."
            )
        if ret:
            self.model_base_addr = ret
            return
        while True:
            if retry == 0:
                self.error(
                    "Failed to find model address. Restart the game and try again."
                )
                raise Exception(
                    "Failed to find model address. Restart the game and try again."
                )
            self.enter_chapter(chapter=1)
            self.wait(15)
            self.pause()
            self.wait(1)
            ret = self.find_model_addr()
            self.resume()
            self.exit_to_main_menu()
            retry -= 1
            if ret:
                self.model_base_addr = ret
                return
            else:
                ret = self.find_model_addr()
                if ret:
                    self.model_base_addr = ret
                    return

    @override
    def read_pointer_chain(self, base_address, offsets):
        return self.ppack.read_pointer_chain(base_address, offsets)

    @override
    def find_chapter_num_addr(self) -> bool:
        self.debug("Use simple pattern")
        ind = self.read_menu_index()
        if ind == MainMenuIndex.MAIN_MENU:
            middle = rb"\xff\xff\xff\xff"
        else:
            middle = rb"[\x00-\xff]\x00{3}"
        pattern = (
            rb"\x01\x00\x00\x00"
            + rb"\x00\x00\x00\x00"
            + middle
            + rb"\x00\x00\x00\x00"
            + rb"\x80\x00\x00\x00"
            + rb"\x20\x03\x00\x00"
            + rb"\x00\x00\x00\x00"
            + rb"\x00\x00\x00\x00"
        )
        addr = self.ppack.pymem.pattern.pattern_scan_all(
            self.pm.process_handle, pattern, return_multiple=True
        )
        if len(addr) > 1:
            for i in addr:
                self.debug(f"Found candidate: {i + 0x08:#x}")
                self.dump_memory(i + 0x08, 64)
        elif addr and len(addr) == 1:
            self.chapter_num_addr = addr[0] + 0x08
            self.info(f"Chapter number address: {self.chapter_num_addr:#x}")
            self.dump_memory(self.chapter_num_addr, 64)
            return True
        self.debug("Use main menu pattern")
        pattern = (
            rb"\xff\xff\xff\xff"
            + rb"...."
            + rb"\x01\x01\x01\x01"
            + rb"\x01\x00\x01[\x00\x01]"
            + rb"...."
            + rb"\x01\x00\x00\x00"
            + rb"\x00\x00\x00\x00"
            + middle
        )
        addr = self.ppack.pymem.pattern.pattern_scan_all(
            self.pm.process_handle, pattern
        )
        if addr:
            self.chapter_num_addr = addr + 0x1C
            self.info(f"Chapter number address: {self.chapter_num_addr:#x}")
            self.dump_memory(self.chapter_num_addr, 64)
            return True
        self.debug("Use legacy pattern")
        pattern = (
            rb"\xff\xff\xff\xff"
            + rb"\xff\xff\xff\xff"
            + rb"\xff\xff\xff\xff"
            + rb"\xff\xff\xff\xff"
            + rb"\xff\xff\xff\xff"
            + rb"...."
            + rb"\x01\x01\x01\x01"
            + rb"\x01\x00\x01[\x00\x01]"
        )
        addr = self.ppack.pymem.pattern.pattern_scan_all(
            self.pm.process_handle, pattern
        )
        if addr:
            self.chapter_num_addr = addr + 0x2C
            self.info(f"Chapter number address: {self.chapter_num_addr:#x}")
            self.dump_memory(self.chapter_num_addr, 64)
            return True
        return False

    @override
    def dump_memory(self, address: int, range_bytes: int = 64):
        """
        Display bytes around a memory address with both hex and ASCII representations.

        Args:
            address: The memory address to inspect
            range_bytes: Number of bytes to display before and after the address
        """
        try:
            # Calculate start and end addresses
            start_addr = address - range_bytes
            total_bytes = range_bytes * 2

            # Read the memory
            bytes_data = self.ppack.pymem.memory.read_bytes(
                self.pm.process_handle, start_addr, total_bytes
            )

            # Format the output with both hex and ASCII representations
            self.debug(
                f"Memory dump around address {address:#x} (+-{range_bytes} bytes):"
            )

            # Process the bytes in 16-byte chunks for clean display
            for i in range(0, len(bytes_data), 16):
                chunk = bytes_data[i : i + 16]
                current_addr = start_addr + i

                # Format address
                addr_str = f"{current_addr:#x}"

                # Format hex values with separator every 4 bytes
                hex_parts = []
                for j in range(0, len(chunk), 4):
                    group = chunk[j : j + 4]
                    hex_parts.append(" ".join([f"{b:02x}" for b in group]))
                hex_values = "  ".join(
                    hex_parts
                )  # Add extra space between 4-byte groups
                hex_str = f"{hex_values:<60}"  # Increased padding for separators

                # Format ASCII representation (only printable chars)
                ascii_str = "".join([chr(b) if 32 <= b <= 126 else "." for b in chunk])

                # Highlight the target address if it's in this line
                if current_addr <= address < current_addr + 16:
                    offset = address - current_addr
                    # Adjust marker position for the new format with separators
                    marker_pos = (
                        offset * 3
                    )  # Base position (3 chars per byte: 2 hex + 1 space)
                    # Add extra spacing for group separators
                    marker_pos += (
                        offset // 4
                    ) * 2  # Add 2 more spaces for each group boundary crossed
                    marker = " " * marker_pos + "^"
                    self.debug(f"{addr_str}: {hex_str} | {ascii_str}")
                    self.debug(f"{'':10}{marker}")
                else:
                    self.debug(f"{addr_str}: {hex_str} | {ascii_str}")

        except Exception as e:
            self.error(f"Error dumping memory at {address:#x}: {e}")

    @override
    def read_chapter_num(self) -> int:
        return self.pm.read_int(self.chapter_num_addr)

    @override
    def read_model_pos(self) -> bool:
        # y, x
        addresses = [
            self.model_base_addr,
            self.model_base_addr - 0x8,
        ]
        return [self.pm.read_float(addr) for addr in addresses]

    def find_model_addr(self) -> int | None:
        self.info("Finding model base address")
        camera_pos_y = self.read_camera_pos()[0]
        pattern = (
            rb"\x30\x01\x00\x01"
            + rb"\xff\xff\xff\x7f"
            + rb"\x00\x00\x00\x00"
            + rb"\x00\x00\x80\x3F"
            + rb"\x01\x00\x7F\x7F"
        )
        ret = self.find_pattern(
            self.pm.process_handle,
            0x88000000,
            0x89000000,
            pattern,
            multiple=True,
        )
        self.debug(f"Found {len(ret)} candidates")
        candidates = []
        for addr in ret:
            real_addr = addr - 0x20
            data_pos = self.pm.read_float(real_addr)
            if abs(data_pos - camera_pos_y) < 0.0001:
                self.debug(f"Skip: {real_addr:#x}, {data_pos}")
                continue
            candidates.append((real_addr, data_pos))
            self.debug(f"Found candidate: {real_addr:#x}, {data_pos}")
            self.dump_memory(real_addr, 64)
        if candidates and len(candidates) == 1:
            model_base_addr = candidates[0][0]
            self.info(f"Model base address: {model_base_addr:#x}")
            self.dump_memory(model_base_addr, 64)
            return model_base_addr
        return None

    def find_model_addr_legacy(self) -> int | None:
        self.info("Finding model base address")
        camera_pos_y = self.read_camera_pos()[0]
        pattern = (
            rb"..\x00[\x01\x02]"
            + rb"...."  # \xff\xff\xff\x7f
            + rb"\x00\x00\x00\x00"
            + rb"\x00\x00\x80\x3F"
            + rb"\x01\x00\x7F\x7F"
        )
        ret = self.find_pattern(
            self.pm.process_handle,
            0x88000000,
            0x89000000,
            pattern,
            multiple=True,
        )
        self.debug(f"Found {len(ret)} candidates")
        candidates = []
        for addr in ret:
            real_addr = addr - 0x20
            data_pos = self.pm.read_float(real_addr)
            if abs(data_pos - camera_pos_y) < 0.0001:
                self.debug(f"Skip: {real_addr:#x}, {data_pos}")
                continue
            candidates.append((real_addr, data_pos))
            self.debug(f"Found candidate: {real_addr:#x}, {data_pos}")
            self.dump_memory(real_addr, 64)
        if candidates and len(candidates) == 1:
            model_base_addr = candidates[0][0]
            self.info(f"Model base address: {model_base_addr:#x}")
            self.dump_memory(model_base_addr, 64)
            return model_base_addr
        return None

    @override
    def read_camera_pos(self) -> List[float]:
        # y, x, z, -ay, ax, az
        camera_base_addr = 0x859D4188
        addresses = [
            camera_base_addr,  # 0x859D4188
            camera_base_addr - 0x8,  # 0x859D4180
            camera_base_addr - 0x4,  # 0x859D4184
            camera_base_addr - 0x88,  # 0x859D4100
            camera_base_addr - 0x80,  # 0x859D4108
            camera_base_addr - 0x70,  # 0x859D4118
        ]
        return [self.pm.read_float(addr) for addr in addresses]

    @override
    def read_indicator(self) -> int:
        indicator_addr = 0x859C7B58
        return self.pm.read_int(indicator_addr)

    @override
    def read_num_poi(self) -> int:
        poi_addr = 0x800268A0
        return self.pm.read_int(poi_addr)

    @override
    def read_num_ip(self) -> int:
        ip_addr = 0x86CE13A8
        return self.pm.read_int(ip_addr)

    @override
    def read_menu_indicator(self) -> int:
        # 50 for main menu
        # 49 for pause menu
        # 48 for in-game
        indicator_addr = 0x8003A02D
        return self.pm.read_bytes(indicator_addr, 1)[0]

    @override
    def read_menu_index(self) -> int:
        ind = self.read_menu_indicator()
        self.debug(f"Menu indicator: {ind}")
        if self.read_menu_indicator() != MenuIndex.MAIN_MENU:
            return MainMenuIndex.NOT_MAIN_MENU
        y = self.read_camera_pos()[0]
        self.debug(f"Camera Y position: {y}")
        if abs(y - 1.302865028) < 0.1:
            return MainMenuIndex.MAIN_MENU
        elif abs(y - 0.4838153124) >= 0.1:
            return MainMenuIndex.UNKNOWN
        ind1 = self.pm.read_int(0x8003CBE0)
        ind2 = self.pm.read_int(0x8328173C)
        self.debug(f"Menu indices: {ind1}, {ind2}")
        if ind1 == 2 and ind2 == 84:
            return MainMenuIndex.CHAPTER_SELECT
        if ind1 == 4:
            return MainMenuIndex.CHECKPOINT_SELECT
        if ind1 == 2 and ind2 == 83:
            return MainMenuIndex.SAVE
        return MainMenuIndex.UNKNOWN

    def find_pattern(self, handle, start_addr, end_addr, pattern, multiple=False):
        pagesize = end_addr - start_addr
        self.debug(f"Reading {pagesize:#x} bytes")
        self.debug(f"Handle: {handle}, Start: {start_addr:#x}, End: {end_addr:#x}")
        page_bytes = self.ppack.pymem.memory.read_bytes(handle, start_addr, pagesize)
        self.debug(f"Pattern: {pattern}")
        if not multiple:
            found = None
            match = re.search(pattern, page_bytes, re.DOTALL)
            if match:
                found = start_addr + match.span()[0]
        else:
            found = []
            for match in re.finditer(pattern, page_bytes, re.DOTALL):
                found_address = start_addr + match.span()[0]
                found.append(found_address)
        return found
