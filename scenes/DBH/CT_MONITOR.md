# CT Monitor for Detroit: Become Human

This tool provides Cheat Engine-like functionality to monitor memory addresses from CT files in Detroit: Become Human.

## Features

- Read memory addresses from Cheat Engine table files (CT files)
- Monitor value changes in real-time
- Show only changed values or all values
- Support for various data types (Byte, Word, Dword, Float, etc.)
- Auto-reload CT files when they are modified
- User-friendly command interface

## Usage

### Running the Script

```bash
# Using the default CT file (tmp/Detroit Become Human.CT)
python scenes/DBH/ct_monitor.py

# Or specify a custom CT file
python scenes/DBH/ct_monitor.py path/to/your/ct/file.CT
```

### Commands

Once the script is running, you can use the following commands:

- **Enter**: Update values and show only changes
- **a**: Show all current values
- **r**: Reload the CT file
- **b <address> [range]**: Display bytes around a memory address (e.g., `b 0x12345678 32`)
- **q**: Quit the program
- **h**: Show help message

## Example Workflow

1. Start the script
2. Initial values from all addresses will be displayed
3. Make changes in the game
4. Press Enter to see which values have changed
5. Press 'a' to see all current values
6. Use `b <address>` to inspect memory around a specific address
7. Press 'q' to exit when done

## Memory Inspection

The memory inspection feature (`b` command) allows you to:

1. View the raw bytes around any memory address
2. See both hexadecimal and ASCII representations, with separators every 4 bytes for better readability
3. Specify the range of bytes to display (defaults to 16 bytes before and after)

Example usage:
```
b 0x859D4188    # Shows 16 bytes before and after address 0x859D4188
b 0x859D4188 32 # Shows 32 bytes before and after address 0x859D4188
```

This is especially useful for:
- Examining data structures in memory
- Finding patterns around known addresses
- Debugging when values aren't what you expect

## How It Works

1. The script parses the provided CT file to extract memory addresses
2. It reads the initial values of these addresses from the game's memory
3. When instructed (by pressing Enter), it rereads the values and shows only those that changed
4. This helps identify which memory addresses are affected by specific game actions

## Requirements

- Detroit: Become Human game must be running
