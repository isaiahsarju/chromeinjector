# ChromeInjector
## About
See full documentation in the wiki.

On the target system you'll want to start Chrome or Edge restoring the previous session.
If you have to kill the session you may want to first alert the users that an update needs to be installed or whatever. As a note if you use `/F` with kill, Chrome will alert you that it "didn't shutdown correctly". Without the `/F` is a bit nicer of a user experience when you reopen chrome moments later

Mac:
```bash
killall "Google Chrome"
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
--disable-gpu --remote-debugging-port=[remote_debug_port] \
--user-data-dir="/Users/[target_user]/Library/Application Support/Google/Chrome/" \
--restore-last-session
```

Windows:
```winbatch
taskkill /IM "chrome.exe"
"C:\Program Files\Google\Chrome\Application\chrome.exe" \
--disable-gpu --remote-debugging-port=[remote_debug_port] \
--user-data-dir="C:\Users\[target_user]\AppData\Local\Google\Chrome\User Data" \
--restore-last-session
```

or

```winbatch
taskkill /IM "msedge.exe"
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" \
--remote-debugging-port=[remote_debug_port] \
--disable-gpu --user-data-dir="C:\Users\[target_user]\AppData\Local\Microsoft\Edge\User Data" \
--profile-directory="Default" \
--restore-last-session
```

## `chromeinjector.py`

This is a module that contains the `ChromeInjector` class. This can be included in other programs to simplify interacting with the CDP.

## Install
```bash
python3 -m venv [env]
source [env]/bin/activate
python3 -m pip install -r requirements.txt
```

### `ChromeInjector` class

View Docstring help by running `help(ChromeInjector)` from a python3 shell after `from chromeinjector import ChromeInjector`

## `injectorcommands.py`

This is a module that contains the `InjectorCommands` class. This is used by `ChromeInjector`.

### `InjectorCommands` class

View Docstring help by running `help(InjectorCommands)` from a python3 shell after `from injectorcommands import InjectorCommands`

## `injectorshell.py`

My implementation of chromeinjector with a CMD2 shell: [Injector Shell](https://github.com/isaiahsarju/injectorshell)


## Dev Road Map
Open an issue if you'd like a feature.

## Greetz
- Original inspiration from: [WhiteChocolateMacademiaNut](https://github.com/slyd0g/WhiteChocolateMacademiaNut)
- Thank you to FX Teammates for feedback and feature requests
- Thank you [ACN Security](https://www.accenture.com/us-en/services/cybersecurity) for allowing me to work on this project over the years