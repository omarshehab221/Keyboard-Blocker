# Keyboard-Blocker
The `keyboard_blocker.py` blocks all keystrokes as long as the script is running, by intercepting all keystrokes and blocking them at an admin level before they get to any app.

> [!CAUTION]
> I use it to clean my keyboard, without having to turn my device off.
>
> Do with it what you will.

## Usage
Run it with `python keyboard_blocker.py`


# Keyboard-Controller
The `keyboard_controller.py` allows you to enable/disable the driver of the keyboard (Sometimes the touchpad). However, it has a caveat. If the driver of the keyboard and the touchpad is already loaded (which probably is), you would notice the keyboard (and possibly the touchpad didn't get disabled). That's until you restart your device, then you'll realize they got disabled.

I fixed that by plugging in an external mouse and keyboard to turn it back on.

> [!CAUTION]
> That one gave me a heart attack, so don't go playing around with it.
>
> You have been warned

## Usage
Run it with `python keyboard_controller.py [--keyboard-only] [--all]`
