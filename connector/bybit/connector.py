# @date 2022-09-12
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# HTTPS+WS connector for bybit.com

import logging
logger = logging.getLogger('siis.connector.bybit')


class Connector(object):
    """
    ByBit adapter to REST and WS API.
    """

    def __init__(self, service, account_id, api_key, api_secret, host="bybit.com", callback=None):
        self._protocol = "https://"
        self._host = host or "bybit.com"

        self._base_url = "/api/"  # for REST

        self._account_id = account_id

        self.__api_key = api_key
        self.__api_secret = api_secret

        self._session = None
        self._ws = None

    def connect(self, use_ws=True, futures=False):
        if self._session is None:
            # Create HTTPS session
            self._session = None  # Client(self.__api_key, self.__api_secret, None)

        if self._ws is None and use_ws:
            self._ws = None  # WebsocketClient(self.__api_key, self.__api_secret)

    def disconnect(self):
        if self._ws:
            self._ws.close()
            self._ws = None

        if self._session:
            self._session = None

    @property
    def authenticated(self) -> bool:
        return self.__api_key is not None

    @property
    def connected(self) -> bool:
        return self._session is not None

    @property
    def ws_connected(self) -> bool:
        return self._ws is not None

    @property
    def client(self):
        return self._session

    @property
    def ws(self):
        return self._ws

    @property
    def account_id(self):
        return self._account_id
