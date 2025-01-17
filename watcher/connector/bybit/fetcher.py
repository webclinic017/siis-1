# @date 2022-09-12
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# www.bybit.com data fetcher

import traceback

from common.utils import timeframe_to_str
from watcher.fetcher import Fetcher

# from connector.bybit.connector import Connector

import logging

logger = logging.getLogger('siis.fetcher.bybit')
error_logger = logging.getLogger('siis.error.fetcher.bybit')


class ByBitFetcher(Fetcher):
    """
    ByBit market data fetcher.
    """

    TF_MAP = {
        60: '1m',
        180: '3m',
        300: '5m',
        900: '15m',
        1800: '30m',
        3600: '1h',
        7200: '2h',
        14400: '4h',
        21600: '6h',
        28800: '8h',
        43200: '12h',
        86400: '1d',
        259200: '3d',
        604800: '1w',
        2592000: '1M'
    }

    def __init__(self, service):
        super().__init__("bybit.com", service)

        self._connector = None

    def connect(self):
        super().connect()

        try:
            identity = self.service.identity(self._name)

            if identity:
                if not self._connector:
                    pass
                    # self._connector = Connector(
                    #     self.service,
                    #     identity.get('api-key'),
                    #     identity.get('api-secret'),
                    #     identity.get('host'))

                if not self._connector.connected:
                    self._connector.connect(use_ws=False)

                #
                # instruments
                #

                # get all products symbols
                self._available_instruments = set()

                instruments = self._connector.client.get_exchange_info().get('symbols', [])

                for instrument in instruments:
                    self._available_instruments.add(instrument['symbol'])

        except Exception as e:
            logger.error(repr(e))
            error_logger.error(traceback.format_exc())

    def disconnect(self):
        super().disconnect()

        try:
            if self._connector:
                self._connector.disconnect()
                self._connector = None
        except Exception as e:
            logger.error(repr(e))
            error_logger.error(traceback.format_exc())

    @property
    def connector(self):
        return self._connector

    @property
    def connected(self) -> bool:
        return self._connector is not None and self._connector.connected

    @property
    def authenticated(self) -> bool:
        return self._connector and self._connector.authenticated

    def fetch_trades(self, market_id, from_date=None, to_date=None, n_last=None):
        trades = []

        try:
            trades = self._connector.client.aggregate_trade_iter(market_id, start_str=int(from_date.timestamp() * 1000),
                                                                 end_str=int(to_date.timestamp() * 1000))
        except Exception as e:
            logger.error("Fetcher %s cannot retrieve aggregated trades on market %s" % (self.name, market_id))

        count = 0

        for trade in trades:
            count += 1
            # timestamp, bid, ask, last, volume, direction
            yield trade['T'], trade['p'], trade['p'], trade['p'], trade['q'], -1 if trade['m'] else 1

        logger.info("Fetcher %s has retrieved on market %s %s aggregated trades" % (self.name, market_id, count))

    def fetch_candles(self, market_id, timeframe, from_date=None, to_date=None, n_last=None):
        if timeframe not in self.TF_MAP:
            logger.error("Fetcher %s does not support timeframe %s" % (self.name, timeframe_to_str(timeframe)))
            return

        candles = []

        tf = self.TF_MAP[timeframe]

        try:
            candles = self._connector.client.get_historical_klines(market_id, tf, int(from_date.timestamp() * 1000),
                                                                   int(to_date.timestamp() * 1000))
        except:
            logger.error("Fetcher %s cannot retrieve candles %s on market %s" % (self.name, tf, market_id))

        count = 0

        for candle in candles:
            count += 1
            # (timestamp, open, high, low, close, spread, volume)
            yield candle[0], candle[1], candle[2], candle[3], candle[4], 0.0, candle[5]

        logger.info("Fetcher %s has retrieved on market %s %s candles for timeframe %s" % (
            self.name, market_id, count, timeframe_to_str(timeframe)))
