import logging
import os
import sys
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from core.event import Event, EventDispatcher, EventSystemCloseEvent
from core.scenario import Scenario
from DBHHelper.helper import DBHHelper


class Address:
    """Represents a memory address from a Cheat Table."""

    def __init__(self, address: int, var_type: str, description: str):
        self.address = address
        self.var_type = var_type
        self.description = description or "No description"
        self.previous_value = None
        self.current_value = None
        self.changed = False

    def update_value(self, new_value: Any) -> bool:
        """Update the value and check if it changed."""
        self.previous_value = self.current_value
        self.current_value = new_value

        if (
            self.previous_value is not None
            and self.previous_value != self.current_value
        ):
            self.changed = True
            return True
        return False

    def __str__(self) -> str:
        """String representation of the address."""
        base_info = f"{self.address:#x} ({self.var_type}) - {self.description}"
        if self.changed:
            return f"{base_info}: {self.previous_value} -> {self.current_value}"
        return f"{base_info}: {self.current_value}"


class CTParser:
    """Parser for Cheat Engine table files."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.addresses: Dict[str, Address] = {}
        self.last_modified = 0
        self._load_file()

    def _load_file(self) -> None:
        """Load and parse the CT file."""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"CT file not found: {self.file_path}")

        self.last_modified = os.path.getmtime(self.file_path)

        try:
            tree = ET.parse(self.file_path)
            root = tree.getroot()

            # Clear existing addresses
            self.addresses = {}

            for entry in root.findall(".//CheatEntry"):
                entry_id = entry.find("ID").text
                description_elem = entry.find("Description")
                description = (
                    description_elem.text
                    if description_elem is not None
                    else "No description"
                )
                var_type_elem = entry.find("VariableType")
                var_type = var_type_elem.text if var_type_elem is not None else "Byte"
                address_elem = entry.find("Address")

                if address_elem is None or not address_elem.text:
                    continue

                try:
                    address_str = address_elem.text
                    address = int(address_str, 16)
                    self.addresses[entry_id] = Address(address, var_type, description)
                except ValueError:
                    print(
                        f"Warning: Invalid address format for entry {entry_id}: {address_elem.text}"
                    )

        except Exception as e:
            print(f"Error parsing CT file: {e}")
            raise

    def check_for_updates(self) -> bool:
        """Check if the CT file has been modified and reload if necessary."""
        if not os.path.exists(self.file_path):
            return False

        current_modified = os.path.getmtime(self.file_path)
        if current_modified > self.last_modified:
            self._load_file()
            return True
        return False

    def get_addresses(self) -> Dict[str, Address]:
        """Get all addresses."""
        return self.addresses


class CTMonitor(EventDispatcher):
    """Monitor for Cheat Engine table addresses."""

    def __init__(self, dbhh: DBHHelper, ct_file_path: str):
        """
        Initialize the CT monitor.

        Args:
            dbhh: DBHHelper instance
            ct_file_path: Path to the CT file
        """
        self.dbhh = dbhh
        self.ct_file_path = ct_file_path
        self.parser = CTParser(ct_file_path)
        self.first_run = True
        self.show_all = False

    def setup(self):
        """Set up the monitor."""
        pass

    def read_memory(self) -> None:
        """Read memory for all addresses."""
        for addr_id, address_obj in self.parser.get_addresses().items():
            try:
                # Read value based on variable type
                if address_obj.var_type == "Byte":
                    value = self.dbhh.pm.read_bytes(address_obj.address, 1)[0]
                elif (
                    address_obj.var_type == "2 Bytes" or address_obj.var_type == "Word"
                ):
                    value = self.dbhh.pm.read_short(address_obj.address)
                elif (
                    address_obj.var_type == "4 Bytes" or address_obj.var_type == "Dword"
                ):
                    value = self.dbhh.pm.read_int(address_obj.address)
                elif (
                    address_obj.var_type == "8 Bytes" or address_obj.var_type == "Qword"
                ):
                    value = self.dbhh.pm.read_longlong(address_obj.address)
                elif address_obj.var_type == "Float":
                    value = self.dbhh.pm.read_float(address_obj.address)
                elif address_obj.var_type == "Double":
                    value = self.dbhh.pm.read_double(address_obj.address)
                elif (
                    address_obj.var_type == "String"
                    or address_obj.var_type == "Unicode String"
                ):
                    # Read up to 100 chars for strings
                    value = self.dbhh.pm.read_string(address_obj.address, 100)
                else:
                    value = self.dbhh.pm.read_bytes(
                        address_obj.address
                    )  # Default to byte

                # Update the value and check if it changed
                address_obj.update_value(value)

            except Exception as e:
                # Set to error value but don't mark as changed
                error_value = f"Error: {str(e)}"
                address_obj.current_value = error_value

    def print_values(self, show_all: bool = False) -> None:
        """
        Print the values to the console.

        Args:
            show_all: Whether to show all values or only changes
        """
        addresses = self.parser.get_addresses()
        if not addresses:
            self.dbhh.info("No addresses found in the CT file")
            return

        # Get all addresses if show_all is True, otherwise only changed ones
        output_addresses = []
        for addr_id, address_obj in addresses.items():
            if show_all or address_obj.changed:
                output_addresses.append(address_obj)
                # Reset changed flag after displaying
                address_obj.changed = False

        if not output_addresses:
            self.dbhh.info("No changes detected")
            return

        # Sort addresses by their hex address value
        output_addresses.sort(key=lambda x: x.address)

        # Format and print
        output = "\n".join(str(addr) for addr in output_addresses)
        if show_all:
            self.dbhh.info("=== All Values ===")
        else:
            self.dbhh.info("=== Changed Values ===")
        self.dbhh.info(output)

    def dump_memory(self, address: int, range_bytes: int = 16):
        """
        Display bytes around a memory address with both hex and ASCII representations.

        Args:
            address: The memory address to inspect
            range_bytes: Number of bytes to display before and after the address
        """
        # Use the DBHHelper's dump_memory implementation
        self.dbhh.dump_memory(address, range_bytes)

    def run(self):
        """Run the monitor in a loop."""
        try:
            # Initialize memory reading system
            self.dbhh.info("CT Monitor started")
            self.dbhh.info(f"Using CT file: {self.ct_file_path}")
            self.dbhh.info(
                "Commands:\n"
                "  Enter - Update values and show changes\n"
                "  a - Show all values\n"
                "  r - Reload CT file\n"
                "  b <address> [range] - Display bytes around address (e.g. 'b 0x12345678 32')\n"
                "  q - Quit\n"
                "  h - Show this help message"
            )

            # Initial read
            self.read_memory()
            # self.print_values(show_all=True)

            while True:
                cmd = input("Enter command (h for help): ").strip().lower()

                if cmd == "":
                    # Update values
                    if self.parser.check_for_updates():
                        self.dbhh.info("CT file updated, reloaded addresses")

                    self.read_memory()
                    self.print_values(show_all=False)

                elif cmd == "a":
                    # Show all values
                    self.read_memory()
                    self.print_values(show_all=True)

                elif cmd == "r":
                    # Reload CT file
                    try:
                        self.parser = CTParser(self.ct_file_path)
                        self.dbhh.info("CT file reloaded")
                        self.read_memory()
                        self.print_values(show_all=True)
                    except Exception as e:
                        self.dbhh.error(f"Failed to reload CT file: {e}")

                elif cmd == "q":
                    self.dbhh.info("Exiting...")
                    break

                elif cmd.startswith("b "):
                    # Parse the command for address and optional range
                    parts = cmd.split()
                    if len(parts) < 2:
                        self.dbhh.info("Usage: b <address> [range]")
                        continue

                    try:
                        # Parse address (support both 0x prefix and raw hex)
                        addr_str = parts[1]
                        if addr_str.startswith("0x"):
                            address = int(addr_str, 16)
                        else:
                            address = int(addr_str, 16)

                        # Parse optional range parameter
                        range_bytes = 16  # Default range
                        if len(parts) >= 3:
                            range_bytes = int(parts[2])

                        # Dump the memory
                        self.dump_memory(address, range_bytes)
                    except ValueError:
                        self.dbhh.error(
                            "Invalid address format. Use hexadecimal (e.g., 0x12345678)"
                        )
                    except Exception as e:
                        self.dbhh.error(f"Error: {e}")

                elif cmd == "h":
                    self.dbhh.info(
                        "Commands:\n"
                        "  Enter - Update values and show changes\n"
                        "  a - Show all values\n"
                        "  r - Reload CT file\n"
                        "  b <address> [range] - Display bytes around address (e.g. 'b 0x12345678 32')\n"
                        "  q - Quit\n"
                        "  h - Show this help message"
                    )
                else:
                    self.dbhh.info("Unknown command. Press 'h' for help.")

        except KeyboardInterrupt:
            self.dbhh.info("Exiting...")
        except Exception as e:
            self.dbhh.error(f"Error: {e}")
            raise
        yield EventSystemCloseEvent()


class Scen(Scenario):
    def __init__(self, ct_file_path: str):
        """
        Initialize the scenario.

        Args:
            ct_file_path: Path to the CT file
        """
        super().__init__(
            "DBH_Extra",
            "ct_monitor",
            levels=(
                logging.DEBUG
                if os.getenv("flags.console_debug", "false").lower() == "true"
                else logging.INFO,
                logging.INFO,
                logging.DEBUG,
            ),
            tags=["DBH", "ct_monitor"],
        )
        self.ct_file_path = ct_file_path

    def setup(self):
        """Set up the scenario."""
        dbhh = DBHHelper()
        monitor = CTMonitor(dbhh, self.ct_file_path)
        monitor.setup()
        dbhh.setup(
            enable_speedhack=False,
            find_model=False,
            vgamepad=False,
            window_adjust=False,
        )
        dbhh.find_chapter_num_addr()
        self.main_g = monitor.run
        self.triggers = [dbhh, monitor]


def main():
    """Main entry point."""
    # Default CT file path
    default_ct_path = os.path.join("tmp", "Detroit Become Human.CT")

    if len(sys.argv) > 1:
        ct_file_path = sys.argv[1]
    else:
        # Use default if no path provided
        if os.path.exists(default_ct_path):
            ct_file_path = default_ct_path
            print(f"Using default CT file: {default_ct_path}")
        else:
            print("Usage: python ct_monitor.py [path_to_ct_file]")
            print(f"Default CT file not found: {default_ct_path}")
            return

    sys.exit(Scen(ct_file_path).run())


if __name__ == "__main__":
    main()
