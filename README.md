# ChromeInjector
## About
Extensive documentation is done in the module itself. For an overview see [API Documentation](#api-documentation).

## Install
```bash
git clone https://github.com/isaiahsarju/chromeinjector.git
python3 -m venv [env]
source [env]/bin/activate
python3 -m pip install -r requirements.txt
```
## Run
```bash
# from parent directory of chromeinjector
python3 -i -m chromeinjector.chromeinjector
```

## Philosophy
`ChromeInjector` is first and foremost a python API for interacting with Chromium browsers, so Edge and Chrome mostly. ChromeInjector instances do not establish a persistent connection to target browsers with a [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/) (CDP) port open. They merely point towards a target host and port. Once you want to execute a CDP command, the injector attempts to connect to the CDP port, enumerate open tabs, narrow down targets (based on url regex or a target WebSocket url), and then send the command with(out) parameters. The driving design principles behind `ChromeInjector` are:

- Keep data types as python as long as possible, convert to JSON right before sending requests. And vice versa, return data as python data types, not JSON. This allows you to perform programmatic logic in python
- Modular as possible
- Take care of underlying WebSocket interactions such as using TLS when necessary, handling socket timeouts, and incrementing WebSocket request IDs
- Providing helpful logging for debugging
- Providing helpful built-in methods for common tasks, such as getting browser cookies, and taking screenshots
In the end, you will most likely use [InjectorShell](https://github.com/isaiahsarju/injectorshell), which instruments ChromeInjector

# ChromeInjector API
## Intro
Originally, this was built to do in browser key logging. Due to the implementation it can be used to execute arbitrary JS and CDP commands, on a per page basis, against a target chromium browser, with a dev port open.

This talks to chromium browsers (headless or headfull) with a dev port open (default 9222) using the Chrome Dev Protocol (CDP) over websockets. It pulls a list of pages and their associated websockets

Based on a regular expression, evaluated against the windows' "url", it filters down that list. On this filtered down list it performs the CDP `Runtime.evaluate` function of the specified JS on each page, or an arbitrary CDP command. There are a few built in commands for getting cookies per tab, or all of the browser, etc.

## API Documentation
The source of truth should be the [Docstring](https://peps.python.org/pep-0257/) compliant documentation in the modules. All methods/functions should be [Python 3.5+ typed](https://docs.python.org/3/library/typing.html) and be occompanied with Docstring compliant comments.

### `ChromeInjector` class

View Docstring help by running `help(ChromeInjector)` from a python3 shell with [chromeinjector loaded as a module](#run).


### `InjectorCommands` class
`injectorcommands.py` contains the `InjectorCommands` class. This is used by `ChromeInjector`.
View Docstring help by running `help(InjectorCommands)` from a python3 shell with [chromeinjector loaded as a module](#run).

## Execution Flow
It's probably hepful to understand what happens when a built-in ChromeInjector command is ran such as `cdp_get_all_cookies`:

1. ChromeInjector gets the CDP command defined in InjectorCommands (`InjectorCommands.get_command("all_cookies")`). These are broken apart to keep CI modular.
1. If a command requires parameters then they should be checked with `InjectorCommands.create_validated_params(...)` which will return dict of provided params if they're valid
1. `cdp_method_exec(...)` is called with a regex or `ws_url`.
1. `_enum_windows()` is called with every `cdp_method_exec(...)` execution. This ensures that the target tabs are as up-to-date as possible
1. If `ws_url` is specified then the CDP command execution will be limited to the provided `ws_url`. Otherwise, target tabs are all tabs whose URL matches the regex
1. Per tab in enumerated targets, or for a specified WS url, _exec_cdp_params(...) is called regarless of if there are parameters. This calls `_cdp_ws_arb_timeout(...)` to add timeout capabilities. This calls `_cdp_ws_arb(...)` for arbitrary CDP WebSocket interactions with(out) parameters
1. A WS connection is created and the CDP command with(out) parameters is sent. The response is returned up the call stack

When programming against ChromeInjector you will probably only call as low as `cdp_method_exec(...)` but it's helpful to know in case you want to create your own built in functions

# Testing
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

# Contribution
## Adding new chromeinjector `cdp_[command]`:

1. Add `_COMMAND_NAME` to `InjectorCommands` with syntax:
`_COMMAND_NAME = ("CDP_DOMAIN.command", {"var0":"Description", "var1":"Description",...}, "Command description")`
1. Add to `InjectorCommands` `_commands` dict with syntax `'command_name': _COMMAND_NAME`
1. Define in `ChromeInjector`. e.g.:

```python
# Params are optional
# Add time if you want to support timeouts
def cdp_[command_name](self, (params), (time: int=None),...) -> Any:
        """DocString comment"""
        if not time:
            time = self._default_time
        command, *__ = InjectorCommands.get_command("[command_name]")
        # If using params make sure to validate them
        validated_params = InjectorCommands.create_validated_params("[command_name]", params)
        # Add cdp_method_exec arguments as appropriate
        # Appropriate if statements if validating params
        #if validated_params:
          #results = self.cdp_method_exec(command, validated_params, time=time...)
        #else:
          #self._logger.error("Incorrect parameters provided. Returning None")
          #return None
        #  Return what you want or don't return
        # cdp_method_exec(...) returns list of thruples (url, result, tab WS url)
        results = self.cdp_method_exec(command, time=time,...)
        url, result, tab_ws_url = results[0]
        if result:
            return url, result, tab_ws_url
        else:
            return None
```
Please follow the following:

1. Use python 3.11 syntax
1. Add Docstring compliant documentation to all modules/methods/functions
1. Add type hinting to all methods/functions
1. Comment excessively
1. Keep arguments as python data types as long as possible. E.g. Don't write functions that take JSON. Write functions that take dicts/sets/lists/etc and let _cdp_ws_arb convert them to JSON right before making websocket request.


Thnx!

# Other Stuff

## `injectorshell.py`

My implementation of `chromeinjector` with a CMD2 shell: [Injector Shell](https://github.com/isaiahsarju/injectorshell)


## Dev Road Map
Open an issue if you'd like a feature.

## Greetz
- Original inspiration from: [WhiteChocolateMacademiaNut](https://github.com/slyd0g/WhiteChocolateMacademiaNut)
- Thank you to FX Teammates for feedback and feature requests
- Thank you [ACN Security](https://www.accenture.com/us-en/services/cybersecurity) for allowing me to work on this project over the years