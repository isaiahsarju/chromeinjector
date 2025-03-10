""" This module contains the InjectorCommands class.
It is a helper class to manage the templates for
CDP command execution with(out) parameters. It is also used to hold
the commands for commonly ran CDP methods like Network.getCookies. This is
used by the ChromeInjector instance method get_open_tab_cookies() method
which retrieves the CDP command from InjectorCommands.get_command("tab_cookies")
"""
import sys
from string import Template
import logging


class InjectorCommands:
    """A helper class to manage command templates and commonly used CDP commands"""


    # Pre-written CDP commands
    # Update _commands dict after adding new CDP command
    # Create new cdp_[command name] function
    # Syntax is (method, dict of {parameters:description}, description)
    # Set of parameters are important for the create_validated_params class function
    _GET_TAB_COOKIES    = ("Network.getCookies", None, "Get tab cookies")
    _GET_ALL_COOKIES    = ("Storage.getCookies", None, "Get all browser cookies")
    _JS_EVALUATE        = ("Runtime.evaluate", None, "Command to execute JS")
    _GET_DOMAIN_COOKIES = ("Network.getCookies", {"urls":"Target Domain"}, "Get cookies for specific Domain")
    _CAPTURE_SCREENSHOT = ("Page.captureScreenshot", None, "Capture screenshot of page")
    _NEW_WINDOW         = ("Target.createTarget",
                            {"url":"Target URL",\
                            "background":"Whether to create the target in background or foreground",\
                            "newWindow":"Whether to create a new Window or Tab (chrome only)",
                            "forTab": "Whether to create the target of type 'tab'"},
                            "Open a new tab or window")
    _CLOSE_WINDOW       = ("Target.closeTarget", {"targetId":"TargetID of tab to close"},
                            "Close target window by TargetID (last part of ws_url)")
    _GET_TAB_HISTORY    = ("Page.getNavigationHistory", None, "Get navigation history per tab")

    # Template commands for executing CDP commands
    # Syntax is (Template, description)
    _CDP_EXEC = (
        Template("{\"id\": $id, \"method\": \"$method\"}"),
        "Template to execute arbitrary CDP method without arguments"
    )
    _CDP_EXEC_PARAMS = (
        Template("{\"id\": $id, \"method\": \"$method\", \"params\": $params}"),
        "Template to execute arbitrary CDP method with arguments"
    )

    _commands = {
        'tab_cookies'       : _GET_TAB_COOKIES,
        'all_cookies'       : _GET_ALL_COOKIES,
        'js_exec'           : _JS_EVALUATE,
        'get_domain_cookies': _GET_DOMAIN_COOKIES,
        'capture_screenshot': _CAPTURE_SCREENSHOT,
        'new_window'        : _NEW_WINDOW,
        'close_window'      : _CLOSE_WINDOW,
        'get_tab_history'   : _GET_TAB_HISTORY
    }

    _template_commands = {
        'cdp_exec'          : _CDP_EXEC,
        'cdp_exec_params'   : _CDP_EXEC_PARAMS
    }

    @classmethod
    def get_command(cls, name: str) -> tuple[str,dict,str]:
        """Takes a command name, returns command, arguments dict, and description"""
        command, params, description = cls._commands.get(name)
        if command:
            return command, params, description
        else:
            logging.getLogger(__name__).error(f"No such command:{name}")
            return None

    @classmethod
    def get_commands(cls) -> dict[str,tuple]:
        """Returns dictionary of commands
        in form
        {cmd name: ({parameters:description}, description)}
        """
        commands_dict = {}
        for key, value in cls._commands.items():
            *__, params, description = value
            commands_dict[key] = (params, description)

        return commands_dict

    @classmethod
    def get_command_template(cls, name: str) -> tuple[str, Template]:
        """Takes a template name, returns template and description"""
        template, description = cls._template_commands.get(name)
        if template:
            return template, description
        else:
            logging.getLogger(__name__).error(f"No such template:{template}")
            return None

    @classmethod
    def get_req_params(cls, name: str) -> dict:
        """Takes a command name, returns required params set"""
        command, params, *__ = cls.get_command(name)
        if command:
            return params
        else:
            logging.getLogger(__name__).error(f"No such command:{name}, Returning None")
            return None

    @classmethod
    def create_validated_params(cls, name:str , supplied_params:dict) -> dict:
        """Takes a command name, and supplied_params dict.
        Returns dict of supplied_params.
        If supplied_params is missing required keys
        from command_params returns None
        """
        command, command_params_dict, *__ = cls.get_command(name)
        if not command:
            logging.getLogger(__name__).error(f"No such command:{name}. Returning None")
            return None

        if type(supplied_params) is not dict:
            logging.getLogger(__name__).error(f"Supplied parameters are not a dict. Returning None")
            return None

        command_params = set(command_params_dict.keys())
        if not all(key in command_params for key in supplied_params.keys()):
            logging.getLogger(__name__).error("Not all parameters defined. Returning None")
            logging.getLogger(__name__).debug(f"Require: {command_params}\nProvided:{supplied_params.keys()}")
            return None
        elif not all(key in supplied_params.keys() for key in command_params):
            logging.getLogger(__name__).warning(f"All parameters accounted for, but provided extra. May experience unexpected behavior")
            return supplied_params
        else:
            logging.getLogger(__name__).debug(f"All parameters accounted for")
            return supplied_params