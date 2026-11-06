# Online Evaluation

In online evaluation the model plays *Detroit: Become Human* through a virtual gamepad while the game is running, and the released offline dataset was collected the same way. The steps below were tested on Manjaro Linux and need a legitimate copy of the game on Steam.

First set up the Python environment and `config.yaml` as described in [Offline Evaluation](../README.md#offline-evaluation). The online experiment reads the `narrator` and `player` model roles of `config.yaml`. Then prepare the game as follows.

## Game Setup

### Steam Proton Side
First you should install [Steam](https://store.steampowered.com/) and install the game [Detroit Become Human](https://store.steampowered.com/app/1222140/_/).

Launch Steam, click the Steam logo in the top left corner. 
Check `Setting` -> `Enable Steam Play for all other titles` and install the game.

Install the following packages:

#### [ProtonUp-Qt](https://github.com/DavidoTek/ProtonUp-Qt)
```
yay -S protonup-qt

protonup-qt 
```
Use ProtonUp-Qt's gui to install GE-Proton-9-10. This one fixes the virtual gamepad issue.

#### [steamtinkerlaunch](https://github.com/sonic2kk/steamtinkerlaunch) 

Better using ProtonUp-Qt's gui to install steamtinkerlaunch, otherwise maybe cause problem that Steam can't find package.


#### [protontricks](https://github.com/Matoking/protontricks) 
```
yay -S protontricks
```
Read the document of protontricks for next commands.

Be sure you have launched game via GE-Proton-9-10 at least one time.

Because of compatibility, `steamtinkerlaunch` can't create a supported prefix by protontricks. So you are supposed do this step before next steps. 

Use protontricks to run Python(3.12.10) installation package like [python-3.12.10-amd64](https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe) to install Python 3.12.10 in the game's prefix.
```
protontricks-launch  python-3.12.10-amd64.exe
```
Remember to check "add python to environment variables" to using pip in cmd.

Launch protontricks gui. 
```
protontricks --gui
```
Choose `Detroit Become Human` -> `select the default wineprefix` -> `run explorer`.
You will find a gui of explorer. Run `My Computer\(C:)\windows\system32\cmd.exe` by double-click. And then install the `requirements-remote.txt` dependencies by pip.

```
pip install -r requirements-remote.txt
```
Right click on the game on Steam, `Properties` -> `Compatibility` -> `Force the use of a specific Steam Play compatibility tool`, select `Steam Tinker Launch`. Click `Play`. 

When the `Steam Tinker Launch` window appears for the first time, click `MAIN MENU`. Then click `GAME MENU`.  

Configure the following settings(Important):
- Check `Use custom command`, and select `start.bat` for `Custom command`. Remember to put the this bat file into the prefix from the repo.
- Check `Force Proton with custom command`.
- Check `Inject custom command`.
- Set `Proton Version` to `GE-Proton-9-10`.
- Set `Enable DLSS` to `True` to prevent recomputing shader.

Click `SAVE AND PLAY`. After this configuration, you don't need to open `MAIN MENU` again.

### xpra (optional)

[xpra](https://xpra.org/) is a tool to run GUI applications over SSH. If you want to use your computer while the game is running, xpra is required to run the game in a separate X11 session.

Install xpra by following the instructions on [Xpra's GitHub repository](https://github.com/Xpra-org/xpra) (the AUR package is no longer maintained). You can also install xpra using pyenv.

Install fluxbox:
```
sudo pacman -S fluxbox
```

Then run the following command to use xpra to create a new X11 session and run the game in that session:
```
xpra desktop :100 --attach=yes --start=steam --start=fluxbox --resize-display="off:1080p"
```

`steam` is the command to start Steam. There might be other commands to start Steam. Check out the steam version you installed.

Then for every DBH experiment you run, you need to add `DISPLAY=:100` before the command. For example:

```
DISPLAY=:100 PYTHONPATH=. python scenes/DBH/dummy/scene.py
```

## Steam Save Files

Run game at least one time to create the save files.

You can run this command to find location of save files.
```
locate WinSavedGames/Quantic Dream/Detroit Become Human/S/
```

Replace `%UserProfile%\WinSavedGames/Quantic Dream/Detroit Become Human/S/765611995xxxxxxxx/R/` with [this](https://www.nexusmods.com/detroitbecomehuman/mods/53?tab=description) save files.

## Run

### Run DBH Dummy Experiment

To test the flow can run correct in your computer, you can run the dummy experiment.

```
DISPLAY=:100 PYTHONPATH=. python scenes/DBH/dummy/scene.py
```

Remove `DISPLAY=:100` if you are not using xpra.

### Run DBH Experiment

```
DISPLAY=:100 PYTHONPATH=. python scenes/DBH/llm/scene.py
```

### Offline Dataset Collection

You can collect offline datasets from the game for later evaluation. This allows you to run LLM evaluations without needing to run the game in real-time.

To collect data:

```
DISPLAY=:100 PYTHONPATH=. python scenes/DBH/dcollect/scene.py
```

The data will be saved to `datasets/dataset_flow_{CHAPTER}` by default.

Options:
- `--output-dir`: Custom output directory for the collected data
- `--max-iterations`: Maximum number of iterations to run (default: unlimited)
- `--no-verify`: Only show warning on hash mismatch instead of raising error

## Issues

### libevdev create_uinput_device PermissionError

```
  File "./vgamepad/lin/virtual_gamepad.py", line 120, in __init__
    self.uinput = self.device.create_uinput_device()
  File "./libevdev/device.py", line 764, in create_uinput_device
    d._uinput = UinputDevice(self._libevdev, uinput_fd)
  File "./libevdev/_clib.py", line 964, in __init__
    raise OSError(-rc, os.strerror(-rc))
PermissionError: [Errno 13] Permission denied
```

Edit `/etc/udev/rules.d/99-uinput.rules`

Add the following line:
```
KERNEL=="uinput", MODE="0666"
```

Then
```
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### Game is not responding to the virtual gamepad

Remember to set `Proton Version` to `GE-Proton-9-10`.

### Game gets stuck in loading screens

Occasionally, the game may get stuck in loading screens when entering chapters. The system is designed to detect this situation automatically after 120 seconds of loading time. When this happens:

1. You will see an error message: "Loading stuck for 120 seconds!"
2. The system will prompt you to "restart the game manually and press Enter to exit..."
3. Steps to handle this situation:
   - Keep the terminal window open
   - Close the game manually through Steam
   - Restart the game through Steam
   - After the game is running again, return to the terminal and press Enter
   - The script will exit with an error code, and you can restart your automation script

This automatic detection prevents the automation from hanging indefinitely if the game gets stuck in a loading screen.
