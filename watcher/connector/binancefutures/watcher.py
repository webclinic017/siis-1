# @date 2020-05-09
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# www.binance.com futures watcher implementation

from __future__ import annotations

from typing import TYPE_CHECKING, List, Union, Optional, Tuple

import time
import traceback
import math
import copy

from datetime import datetime

from watcher.watcher import Watcher
from common.signal import Signal

from connector.binance.connector import Connector
from connector.binance.client import Client

from trader.order import Order
from trader.market import Market

from instrument.instrument import Instrument, Candle

from database.database import Database

import logging
logger = logging.getLogger('siis.watcher.binancefutures')
exec_logger = logging.getLogger('siis.exec.watcher.binancefutures')
error_logger = logging.getLogger('siis.error.watcher.binancefutures')
traceback_logger = logging.getLogger('siis.traceback.watcher.binancefutures')


class BinanceFuturesWatcher(Watcher):
    """
    Binance futures market watcher using REST + WS.

    @ref https://github.com/binance-exchange/binance-official-api-docs/blob/master/margin-api.md

    @todo Finish order book events.
    @todo Once a market is not longer found (market update) we could remove it from watched list,
        and even have a special signal to strategy, and remove the subscriber, and markets data from watcher and trader

    @note A single connection can listen to a maximum of 200 streams.
    @note WebSocket connections have a limit of 10 incoming messages per second.
    """

    BASE_QUOTE = 'USDT'         # default base quote
    USE_DEPTH_AS_TRADE = False  # Use depth best bid/ask in place of aggregated trade data (use a single stream)

    REV_TF_MAP = {
        '1m': 60,
        '3m': 180,
        '5m': 300,
        '15m': 900,
        '30m': 1800,
        '1h': 3600,
        '2h': 7200,
        '4h': 14400,
        '6h': 21600,
        '8h': 28800,
        '12h': 43200,
        '1d': 86400,
        '3d': 259200,
        '1w': 604800,
        '1M': 2592000
    }

    def __init__(self, service):
        super().__init__("binancefutures.com", service, Watcher.WATCHER_PRICE_AND_VOLUME)

        self._connector = None
        self._depths = {}  # depth chart per symbol tuple (last_id, bids, asks)

        self._symbols_data = {}
        self._tickers_data = {}
        self._leverages_data = {}

        self._total_balance = {
            'totalWalletBalance': 0.0,
            'totalUnrealizedProfit': 0.0,
            'totalCrossMarginBalance': 0.0,
            'totalIsolatedMarginBalance': 0.0,
        }

        self._last_trade_id = {}
        self._last_positions = {}    # cache of the last position for a symbol

        self.__configured_symbols = set()  # cache for configured symbols set
        self.__matching_symbols = set()    # cache for matching symbols

        self._tickers_handler = None       # WS all tickers
        self._book_tickers_handler = None  # WS all book tickers
        self._user_data_handler = None     # WS user data

    def connect(self):
        super().connect()

        with self._mutex:
            try:
                self._ready = False
                self._connecting = True

                identity = self.service.identity(self._name)

                if identity:
                    if not self._connector:
                        self._connector = Connector(
                            self.service,
                            identity.get('account-id', ""),
                            identity.get('api-key'),
                            identity.get('api-secret'),
                            identity.get('host'))
                    # else:
                    #     # to get a clean connection
                    #     self._connector.disconnect()

                    if not self._connector.connected or not self._connector.ws_connected:
                        self._connector.connect(futures=True)

                    if self._connector and self._connector.connected:
                        #
                        # instruments
                        #

                        # get all products symbols
                        self._available_instruments = set()

                        instruments = self._connector.client.futures_exchange_info().get('symbols', [])
                        configured_symbols = self.configured_symbols()
                        matching_symbols = self.matching_symbols_set(
                            configured_symbols, [instrument['symbol'] for instrument in instruments])

                        # cache them
                        self.__configured_symbols = configured_symbols
                        self.__matching_symbols = matching_symbols

                        # prefetch all markets data with a single request to avoid one per market
                        self.__prefetch_markets()

                        for instrument in instruments:
                            self._available_instruments.add(instrument['symbol'])

                        # all tickers and book tickers
                        # self._tickers_handler = self._connector.ws.start_ticker_socket(self.__on_ticker_arr_data)
                        # self._book_tickers_handler = self._connector.ws.start_book_ticker_socket(
                        #     self.__on_book_ticker_data)

                        # userdata
                        self._user_data_handler = self._connector.ws.start_user_socket(self.__on_user_data)

                        # retry the previous subscriptions
                        if self._watched_instruments:
                            logger.debug("%s subscribe to markets data stream..." % self.name)

                            pairs = []

                            for market_id in self._watched_instruments:
                                if market_id in self._available_instruments:
                                    pairs.append(market_id.lower())

                            try:
                                self._connector.ws.subscribe_public(
                                    subscription='ticker',  # 'miniTicker'
                                    pair=pairs,
                                    callback=self.__on_ticker_data
                                )

                                # self._connector.ws.subscribe_public(
                                #     subscription='bookTicker',
                                #     pair=pairs,
                                #     callback=self.__on_book_ticker_data
                                # )

                                self._connector.ws.subscribe_public(
                                    subscription='depth5',
                                    pair=pairs,
                                    callback=self.__on_depth_data
                                )

                                self._connector.ws.subscribe_public(
                                    subscription='aggTrade',
                                    pair=pairs,
                                    callback=self.__on_trade_data
                                )

                                # @todo order book

                            except Exception as e:
                                error_logger.error(repr(e))
                                traceback_logger.error(traceback.format_exc())

                        # and start ws manager if necessary
                        try:
                            self._connector.ws.start()
                        except RuntimeError:
                            logger.debug("%s WS already started..." % self.name)

                        # once market are init
                        self._ready = True
                        self._connecting = False

                        logger.debug("%s connection succeed" % self.name)

            except Exception as e:
                logger.debug(repr(e))
                error_logger.error(traceback.format_exc())

                self._ready = False
                self._connecting = False
                self._connector = None

        if self._connector and self._connector.connected and self._ready:
            self.service.notify(Signal.SIGNAL_WATCHER_CONNECTED, self.name, (time.time(), None))

    def disconnect(self):
        super().disconnect()

        logger.debug("%s disconnecting..." % self.name)

        with self._mutex:
            try:
                if self._connector:
                    self._connector.disconnect()
                    self._connector = None

                    # reset WS handlers
                    self._tickers_handler = None
                    self._book_tickers_handler = None
                    self._user_data_handler = None

                self._ready = False
                self._connecting = False

                logger.debug("%s disconnected" % self.name)

            except Exception as e:
                logger.debug(repr(e))
                error_logger.error(traceback.format_exc())

    @property
    def connector(self):
        return self._connector

    @property
    def connected(self) -> bool:
        return self._connector is not None and self._connector.connected and self._connector.ws_connected

    @property
    def authenticated(self) -> bool:
        return self._connector and self._connector.authenticated

    def pre_update(self):
        if not self._connecting and not self._ready:
            reconnect = False

            with self._mutex:
                if (not self._ready or self._connector is None or not self._connector.connected or
                        not self._connector.ws_connected):
                    # cleanup
                    self._ready = False
                    self._connector = None

                    reconnect = True

            if reconnect:
                time.sleep(2)
                self.connect()
                return

    #
    # instruments
    #

    def subscribe(self, market_id, ohlc_depths=None, tick_depth=None, order_book_depth=None):
        if market_id not in self.__matching_symbols:
            return False

        # live data
        symbol = market_id.lower()

        # fetch from source
        if self._initial_fetch:
            logger.info("%s prefetch for %s" % (self.name, market_id))

            if ohlc_depths:
                for timeframe, depth in ohlc_depths.items():
                    try:
                        if timeframe == Instrument.TF_1M:
                            self.fetch_and_generate(market_id, Instrument.TF_1M, depth, None)

                        elif timeframe == Instrument.TF_2M:
                            self.fetch_and_generate(market_id, Instrument.TF_1M, depth*2, Instrument.TF_2M)

                        elif timeframe == Instrument.TF_3M:
                            self.fetch_and_generate(market_id, Instrument.TF_1M, depth*3, Instrument.TF_3M)
                        
                        elif timeframe == Instrument.TF_5M:
                            self.fetch_and_generate(market_id, Instrument.TF_5M, depth, None)

                        elif timeframe == Instrument.TF_10M:
                            self.fetch_and_generate(market_id, Instrument.TF_5M, depth*2, Instrument.TF_10M)
                        
                        elif timeframe == Instrument.TF_15M:
                            self.fetch_and_generate(market_id, Instrument.TF_15M, depth, None)

                        elif timeframe == Instrument.TF_30M:
                            self.fetch_and_generate(market_id, Instrument.TF_30M, depth, None)

                        elif timeframe == Instrument.TF_1H:
                            self.fetch_and_generate(market_id, Instrument.TF_1H, depth, None)

                        elif timeframe == Instrument.TF_2H:
                            self.fetch_and_generate(market_id, Instrument.TF_1H, depth*2, Instrument.TF_2H)

                        elif timeframe == Instrument.TF_3H:
                            self.fetch_and_generate(market_id, Instrument.TF_1H, depth*3, Instrument.TF_3H)

                        elif timeframe == Instrument.TF_4H:
                            self.fetch_and_generate(market_id, Instrument.TF_4H, depth, None)

                        elif timeframe == Instrument.TF_6H:
                            self.fetch_and_generate(market_id, Instrument.TF_1H, depth*6, Instrument.TF_6H)

                        elif timeframe == Instrument.TF_8H:
                            self.fetch_and_generate(market_id, Instrument.TF_4H, depth*2, Instrument.TF_8H)

                        elif timeframe == Instrument.TF_12H:
                            self.fetch_and_generate(market_id, Instrument.TF_4H, depth*3, Instrument.TF_12H)

                        elif timeframe == Instrument.TF_1D:
                            self.fetch_and_generate(market_id, Instrument.TF_1D, depth, None)

                        elif timeframe == Instrument.TF_2D:
                            self.fetch_and_generate(market_id, Instrument.TF_1D, depth*2, Instrument.TF_2D)

                        elif timeframe == Instrument.TF_3D:
                            self.fetch_and_generate(market_id, Instrument.TF_1D, depth*3, Instrument.TF_3D)

                        elif timeframe == Instrument.TF_1W:
                            self.fetch_and_generate(market_id, Instrument.TF_1W, depth, None)

                        elif timeframe == Instrument.TF_MONTH:
                            self.fetch_and_generate(market_id, Instrument.TF_MONTH, depth, None)

                    except Exception as e:
                        error_logger.error(repr(e))

            if tick_depth:
                try:
                    self.fetch_ticks(market_id, tick_depth)
                except Exception as e:
                    error_logger.error(repr(e))

        with self._mutex:
            # one more watched instrument
            self.insert_watched_instrument(market_id, [0])

            # and start listening for this symbol (trade+depth)

            self._connector.ws.subscribe_public(
                subscription='ticker',  # 'miniTicker'
                pair=[symbol],
                callback=self.__on_ticker_data
            )

            # self._connector.ws.subscribe_public(
            #     subscription='bookTicker',
            #     pair=[symbol],
            #     callback=self.__on_book_ticker_data
            # )

            self._connector.ws.subscribe_public(
                subscription='depth5',
                pair=[symbol],
                callback=self.__on_depth_data
            )

            # not used : ohlc (1m, 5m, 1h), prefer rebuild ourselves using aggregated trades
            # kline_data = ['{}@kline_{}'.format(symbol, '1m')]  # '5m' '1h'...

            self._connector.ws.subscribe_public(
                subscription='aggTrade',
                pair=[symbol],
                callback=self.__on_trade_data
            )

            # if order_book_depth and order_book_depth in (10, 25, 100, 500, 1000):
            #     self._connector.ws.subscribe_public(
            #         subscription='depth',
            #         pair=[symbol],
            #         callback=self.__on_depth_data
            #     )

            # no more than 10 messages per seconds on websocket
            time.sleep(0.1)

        return True

    def unsubscribe(self, market_id, timeframe):
        with self._mutex:
            if market_id in self._watched_instruments:
                instruments = self._available_instruments

                if market_id in instruments:
                    pair = [market_id.lower()]

                    # self._connector.ws.unsubscribe_public('miniTicker', pair)
                    self._connector.ws.unsubscribe_public('aggTrade', pair)
                    self._connector.ws.unsubscribe_public('bookTicker', pair)
                    self._connector.ws.unsubscribe_public('ticker', pair)
                    # self._connector.ws.unsubscribe_public('depth', pair)

                    self._watched_instruments.remove(market_id)

                    return True

        return False

    #
    # processing
    #

    def update(self):
        if not super().update():
            return False

        if not self.connected:
            # connection lost, ready status false to retry a connection
            self._ready = False
            return False

        #
        # ohlc close/open
        #

        with self._mutex:
            self.update_from_tick()

        #
        # market info update (each 4h)
        #

        if time.time() - self._last_market_update >= BinanceFuturesWatcher.UPDATE_MARKET_INFO_DELAY:
            try:
                self.update_markets_info()
                self._last_market_update = time.time()  # update in 4h
            except Exception as e:
                error_logger.error("update_markets_info %s" % str(e))
                self._last_market_update = time.time() - 300.0  # retry in 5 minutes

        return True

    def post_update(self):
        super().post_update()
        time.sleep(0.0005)

    def post_run(self):
        super().post_run()

    def fetch_market(self, market_id):
        """
        Fetch and cache it. It rarely changes.
        """
        symbol = self._symbols_data.get(market_id)
        ticker = self._tickers_data.get(market_id)
        leverage = self._leverages_data.get(market_id)

        market = None

        if symbol and ticker:
            market = Market(symbol['symbol'], symbol['symbol'])

            market.is_open = symbol['status'] == "TRADING"
            market.expiry = '-'

            base_asset = symbol['baseAsset']
            market.set_base(base_asset, base_asset, symbol['baseAssetPrecision'])

            quote_asset = symbol['quoteAsset']
            market.set_quote(quote_asset, symbol.get('quoteAssetUnit', quote_asset), symbol['pricePrecision'])

            # tick size at the base asset precision
            market.one_pip_means = math.pow(10.0, -symbol['pricePrecision'])
            market.value_per_pip = 1.0
            market.contract_size = 1.0
            market.lot_size = 1.0
            market.margin_factor = 1.0
            market.base_exchange_rate = 1.0  # any pairs quote in USDT

            size_limits = ["1.0", "0.0", "1.0"]
            notional_limits = ["0.0", "0.0", "0.0"]
            price_limits = ["0.0", "0.0", "0.0"]

            # size min/max/step
            for sym_filter in symbol["filters"]:
                if sym_filter['filterType'] == "LOT_SIZE":
                    size_limits = [sym_filter['minQty'], sym_filter['maxQty'], sym_filter['stepSize']]

                elif sym_filter['filterType'] == "PRICE_FILTER":  # 'MARKET_LOT_SIZE'
                    price_limits = [sym_filter['minPrice'], sym_filter['maxPrice'], sym_filter['tickSize']]

            market.set_size_limits(float(size_limits[0]), float(size_limits[1]), float(size_limits[2]))
            market.set_price_limits(float(price_limits[0]), float(price_limits[1]), float(price_limits[2]))
            market.set_notional_limits(0.0, 0.0, 0.0)

            market.unit_type = Market.UNIT_AMOUNT
            market.market_type = Market.TYPE_CRYPTO
            market.contract_type = Market.CONTRACT_FUTURE

            market.trade = 0

            hedging = self.connector.client.futures_position_side_dual()
            if hedging:
                market.hedging = hedging['dualSidePosition']

            # @todo special case if dual side position (hedging enabled)
            market.trade = Market.TRADE_MARGIN | Market.TRADE_IND_MARGIN

            # @todo orders capacities
            # symbol['orderTypes'] in ['LIMIT', 'MARKET', 'STOP', 'STOP_MARKET', 'TAKE_PROFIT',
            #   'TAKE_PROFIT_MARKET', 'TRAILING_STOP_MARKET']
            # market.orders = 

            # @todo order time in force
            # symbol['timeInForce'] in ['GTC', 'IOC', 'FOK', 'GTX']
            # market.time_in_force = 

            # no info, hard coded, could be parameters
            market.maker_fee = 0.02 * 0.01
            market.taker_fee = 0.04 * 0.01

            # market.buyer_commission = 0.0
            # market.seller_commission = 0.0

            if leverage:
                market.margin_factor = 1.0 / leverage[1]  # leverage[0] to know if isolated margin
            else:
                market.margin_factor = 1.0 / 125  # no account data let to maximum

            # only order book can give us bid/ask
            market.bid = float(ticker['bidPrice'])
            market.ask = float(ticker['askPrice'])

            mid_price = (market.bid * market.ask) * 0.5

            # volume 24h
            # in ticker/24hr but cost is 40 for any symbols then wait it at all-tickers WS event
            # vol24_base = ticker24h('volume')
            # vol24_quote = ticker24h('quoteVolume')

            # notify for strategy
            self.service.notify(Signal.SIGNAL_MARKET_INFO_DATA, self.name, (market_id, market))

            # store the last market info to be used for backtesting
            Database.inst().store_market_info((
                self.name, market.market_id, market.symbol,
                market.market_type, market.unit_type, market.contract_type,  # type
                market.trade, market.orders,  # type
                market.base, market.base_display, market.base_precision,  # base
                market.quote, market.quote_display, market.quote_precision,  # quote
                market.settlement, market.settlement_display, market.settlement_precision,  # settlement
                market.expiry, int(market.last_update_time * 1000.0),  # expiry, timestamp
                str(market.lot_size), str(market.contract_size), str(market.base_exchange_rate),
                str(market.value_per_pip), str(market.one_pip_means), '-',
                *size_limits,
                *notional_limits,
                *price_limits,
                str(market.maker_fee), str(market.taker_fee), str(market.maker_commission),
                str(market.taker_commission))
            )

        return market

    def fetch_order_book(self, market_id):
        # future_orderbook_tickers
        # future_order_book(market_id)
        pass

    #
    # protected
    #

    def __prefetch_markets(self):
        symbols = self._connector.client.futures_exchange_info().get('symbols', [])
        tickers = self._connector.client.futures_orderbook_ticker()
        account = self._connector.client.futures_account()

        self._symbols_data = {}
        self._tickers_data = {}
        self._leverages_data = {}

        for symbol in symbols:
            self._symbols_data[symbol['symbol']] = symbol

        for ticker in tickers:
            self._tickers_data[ticker['symbol']] = ticker

        for position in account.get('positions', []):
            self._leverages_data[position['symbol']] = (position.get('isolated', False), float(
                position.get('leverage', '1')))

    def __on_ticker_data(self, data):
        # market data instrument by symbol
        if type(data) is not dict:
            return

        event_type = data.get('e', "")
        if event_type != '24hrTicker':
            return

        symbol = data.get('s')
        if not symbol:
            return

        last_trade_id = data.get('L', 0)

        if last_trade_id != self._last_trade_id.get(symbol, 0):
            self._last_trade_id[symbol] = last_trade_id

            last_update_time = data['C'] * 0.001

            # from book ticker
            bid = None
            ask = None

            vol24_base = float(data['v']) if data.get('v') else 0.0
            vol24_quote = float(data['q']) if data.get('q') else 0.0

            market_data = (symbol, last_update_time > 0, last_update_time, bid, ask,
                           None, None, None, vol24_base, vol24_quote)
            self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

    def __on_ticker_arr_data(self, data):
        # market data instrument by symbol
        if type(data) not in (list, tuple):
            return

        for ticker in data:
            if type(ticker) is not dict:
                continue

            symbol = ticker.get('s')
            if not symbol:
                continue

            last_trade_id = ticker.get('L', 0)

            if last_trade_id != self._last_trade_id.get(symbol, 0):
                self._last_trade_id[symbol] = last_trade_id

                last_update_time = None  # ticker['C'] * 0.001

                # from book ticker
                bid = None
                ask = None

                vol24_base = float(ticker['v']) if ticker.get('v') else 0.0
                vol24_quote = float(ticker['q']) if ticker.get('q') else 0.0

                # market_data = (symbol, last_update_time > 0, last_update_time, bid, ask,
                #                None, None, None, vol24_base, vol24_quote)
                market_data = (symbol, None, None, bid, ask,
                               None, None, None, vol24_base, vol24_quote)
                self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

    def __on_book_ticker_data(self, data):
        if type(data) is not dict:
            return

        event_type = data.get('e', "")
        if event_type != 'bookTicker':
            return

        # market data instrument by symbol
        symbol = data.get('s')
        if not symbol:
            return

        bid = float(data['b']) if data.get('b') else None  # B for qty
        ask = float(data['a']) if data.get('a') else None  # A for qty

        market_data = (symbol, None, None, bid, ask, None, None, None, None, None)
        self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

    def __on_multiplex_data(self, data):
        """
        Intercepts ticker all, depth for followed symbols.
        Klines are generated from tickers data. It is a preferred way to reduce network traffic and API usage.
        """
        if type(data) is not dict:
            return

        if not data.get('stream'):
            return

        if data['stream'].endswith('@aggTrade'):
            self.__on_trade_data(data['data'])
        elif data['stream'].endswith('@depth'):
            self.__on_depth_data(data['data'])
        elif data['stream'].endswith('@kline_'):
            self.__on_kline_data(data['data'])
        elif data['stream'].endswith('@ticker'):
            self.__on_ticker_data(data['data'])
        elif data['stream'].endswith('@bookTicker'):
            self.__on_book_ticker_data(data['data'])

    def __on_depth_data(self, data):
        if type(data) is not dict:
            return

        if 'data' in data:
            data = data['data']

        event_type = data.get('e', "")
        if event_type != 'depthUpdate':
            return

        symbol = data.get('s')
        if not symbol:
            return

        # get bid/ask for market update from depth book
        last_update_time = data['T'] * 0.001

        if 'b' in data and data['b']:
            bid = float(data['b'][0][0])  # B for qty
        else:
            bid = None

        if 'a' in data and data['a']:
            ask = float(data['a'][0][0])  # A for qty
        else:
            ask = None

        market_data = (symbol, last_update_time > 0, last_update_time, bid, ask, None, None, None, None, None)
        self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

        # @todo using binance.DepthCache
        # if symbol not in self._depths:
        #     # initial snapshot of the order book from REST API
        #     initial = self._connector.client.get_order_book(symbol=symbol, limit=100)
        #
        #     bids = {}
        #     asks = {}
        #
        #     for bid in initial['bids']:
        #         bids[bid[0]] = bid[1]
        #
        #     for ask in initial['asks']:
        #         asks[ask[0]] = ask[1]
        #
        #     self._depths[symbol] = [initial.get('lastUpdateId', 0), bids, asks]
        #
        # depth = self._depths[symbol]
        #
        # # The first processed should have U <= lastUpdateId+1 AND u >= lastUpdateId+1
        # if data['u'] <= depth[0] or data['U'] >= depth[0]:
        #     # drop event if older than the last snapshot
        #     return
        #
        # if data['U'] != depth[0] + 1:
        #     logger.warning("Watcher %s, there is a gap into depth data for symbol %s" % (self._name, symbol))
        #
        # for bid in data['b']:
        #     # if data['U'] <= depth[0]+1 and data['u'] >= depth[0]+1:
        #     if bid[1] == 0:
        #         del depth[1][bid[0]]  # remove at price
        #     else:
        #         depth[2][bid[0]] = bid[1]  # price : volume
        #
        # for ask in data['a']:
        #     if ask[1] == 0:
        #         del depth[2][ask[0]]
        #     else:
        #         depth[2][ask[0]] = ask[1]
        #
        # # last processed id, next must be +1
        # depth[0] = data['u']
        #
        # # self.service.notify(Signal.SIGNAL_ORDER_BOOK, self.name, (symbol, depth[1], depth[2]))

    def __on_trade_data(self, data):
        if type(data) is not dict:
            return

        if 'data' in data:
            data = data['data']

        event_type = data.get('e', "")
        if event_type == "aggTrade":
            symbol = data.get('s')

            if not symbol:
                return

            trade_time = data['T'] * 0.001

            # trade_id = data['t']
            buyer_maker = -1 if data['m'] else 1

            price = float(data['p'])
            vol = float(data['q'])

            spread = 0.0  # @todo from ticker ask - bid

            tick = (trade_time, price, price, price, vol, buyer_maker)

            self.service.notify(Signal.SIGNAL_TICK_DATA, self.name, (symbol, tick))

            if self._store_trade:
                Database.inst().store_market_trade((
                    self.name, symbol, int(data['T']), data['p'], data['p'], data['p'], data['q'], buyer_maker))

            for tf in Watcher.STORED_TIMEFRAMES:
                # generate candle per timeframe
                candle = None

                with self._mutex:
                    candle = self.update_ohlc(symbol, tf, trade_time, price, spread, vol)

                if candle is not None:
                    self.service.notify(Signal.SIGNAL_CANDLE_DATA, self.name, (symbol, candle))

    def __on_kline_data(self, data):
        if type(data) is not dict:
            return

        if 'data' in data:
            data = data['data']

        event_type = data.get('e', "")
        if event_type == 'kline':
            symbol = data.get('s')

            if not symbol:
                return

            k = data['k']
            timestamp = k['t'] * 0.001

            tf = self.REV_TF_MAP[k['i']]

            candle = Candle(timestamp, tf)

            candle.set_ohlc(
              float(k['o']),
              float(k['h']),
              float(k['l']),
              float(k['c']))

            # @todo from ticker ask - bid
            spread = 0.0

            candle.set_spread(spread)
            candle.set_volume(float(k['v']))
            candle.set_consolidated(k['x'])

            self.service.notify(Signal.SIGNAL_CANDLE_DATA, self.name, (symbol, candle))

            if self._store_ohlc and k['x']:
                # write only consolidated candles. values are string its perfect
                Database.inst().store_market_ohlc((
                    self.name, symbol, int(k['t']), tf,
                    k['o'], k['h'], k['l'], k['c'],
                    spread,
                    k['v']))

    def __on_user_data(self, data):
        """
        @ref https://github.com/binance-exchange/binance-official-api-docs/blob/master/user-data-stream.md#web-socket-payloads
        """
        event_type = data.get('e', "")

        if event_type == "ORDER_TRADE_UPDATE":
            # trade update are pushed before account (position) update in way to be processed before

            # order trade : created, updated, rejected, canceled, deleted
            # @ref https://binance-docs.github.io/apidocs/futures/en/#event-order-update

            # @todo New field "rp" for the realized profit of the trade in event "ORDER_TRADE_UPDATE"

            exec_logger.info("binancefutures.com ORDER_TRADE_UPDATE %s" % str(data))
            event_timestamp = float(data['E']) * 0.001
            transaction_timestamp = float(data['T']) * 0.001  # transaction time

            order = data['o']
            symbol = order['s']

            if order['x'] == Client.ORDER_STATUS_REJECTED:  # and order['X'] == '?':
                client_order_id = order['c']

                self.service.notify(Signal.SIGNAL_ORDER_REJECTED, self.name, (symbol, client_order_id))

            elif (order['x'] == 'TRADE') and (order['X'] == Client.ORDER_STATUS_NEW or
                                              order['X'] == Client.ORDER_STATUS_PARTIALLY_FILLED):
                order_id = str(order['i'])
                client_order_id = str(order['c'])

                timestamp = float(order['T']) * 0.001  # transaction time

                price = None
                stop_price = None

                if order['o'] == Client.ORDER_TYPE_LIMIT:
                    order_type = Order.ORDER_LIMIT
                    price = float(order['p'])

                elif order['o'] == Client.ORDER_TYPE_MARKET:
                    order_type = Order.ORDER_MARKET

                elif order['o'] == Client.ORDER_TYPE_STOP_MARKET:
                    order_type = Order.ORDER_STOP
                    stop_price = float(order['sp'])

                elif order['o'] == Client.ORDER_TYPE_STOP:
                    order_type = Order.ORDER_STOP_LIMIT
                    price = float(order['p'])
                    stop_price = float(order['sp'])

                elif order['o'] == Client.ORDER_TYPE_TAKE_PROFIT_MARKET:
                    order_type = Order.ORDER_TAKE_PROFIT
                    stop_price = float(order['sp'])

                elif order['o'] == Client.ORDER_TYPE_TAKE_PROFIT:
                    order_type = Order.ORDER_TAKE_PROFIT_LIMIT
                    price = float(order['p'])
                    stop_price = float(order['sp'])

                elif order['o'] == Client.ORDER_TYPE_TRAILING_STOP_MARKET:
                    order_type = Order.ORDER_TRAILING_STOP_MARKET

                else:
                    order_type = Order.ORDER_LIMIT

                if order['f'] == Client.TIME_IN_FORCE_GTC:
                    time_in_force = Order.TIME_IN_FORCE_GTC
                elif order['f'] == Client.TIME_IN_FORCE_IOC:
                    time_in_force = Order.TIME_IN_FORCE_IOC
                elif order['f'] == Client.TIME_IN_FORCE_FOK:
                    time_in_force = Order.TIME_IN_FORCE_FOK
                else:
                    time_in_force = Order.TIME_IN_FORCE_GTC

                # "ap":"0" Average Price
                fees = float(order['n'])
                exec_price = float(order['L'])

                if order['N'] == self.BASE_QUOTE:
                    # fees expressed in USDT
                    fees /= exec_price

                order_data = {
                    'id': order_id,
                    'symbol': symbol,
                    'type': order_type,
                    'trade-id': str(order['t']),
                    'direction': Order.LONG if order['S'] == Client.SIDE_BUY else Order.SHORT,
                    'timestamp': timestamp,
                    'quantity': float(order['q']),
                    'price': price,
                    'stop-price': stop_price,
                    'exec-price': exec_price,
                    'avg-price': float(order['ap']),
                    'filled': float(order['l']),
                    'cumulative-filled': float(order['z']),
                    'stop-loss': None,
                    'take-profit': None,
                    'time-in-force': time_in_force,
                    'commission-amount': fees,
                    'commission-asset': order['N'],
                    'profit-loss': float(order['rp']),
                    'profit-currency': self.BASE_QUOTE,
                    'maker': order['m'],   # trade execution over or counter the market : true if maker, false if taker
                    'fully-filled': order['X'] == Client.ORDER_STATUS_FILLED  # fully filled status else its partially
                }

                self.service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (symbol, order_data, client_order_id))

            elif order['x'] == Client.ORDER_STATUS_NEW and order['X'] == Client.ORDER_STATUS_NEW:
                order_id = str(order['i'])
                client_order_id = str(order['c'])

                # timestamp = float(order['T']) * 0.001

                price = None
                stop_price = None

                if order['o'] == Client.ORDER_TYPE_LIMIT:
                    order_type = Order.ORDER_LIMIT
                    price = float(order['p'])

                elif order['o'] == Client.ORDER_TYPE_MARKET:
                    order_type = Order.ORDER_MARKET

                elif order['o'] == Client.ORDER_TYPE_STOP_MARKET:
                    order_type = Order.ORDER_STOP
                    stop_price = float(order['sp'])

                elif order['o'] == Client.ORDER_TYPE_STOP:
                    order_type = Order.ORDER_STOP_LIMIT
                    price = float(order['p'])
                    stop_price = float(order['sp'])

                elif order['o'] == Client.ORDER_TYPE_TAKE_PROFIT_MARKET:
                    order_type = Order.ORDER_TAKE_PROFIT
                    stop_price = float(order['sp'])

                elif order['o'] == Client.ORDER_TYPE_TAKE_PROFIT:
                    order_type = Order.ORDER_TAKE_PROFIT_LIMIT
                    price = float(order['p'])
                    stop_price = float(order['sp'])

                elif order['o'] == Client.ORDER_TYPE_TRAILING_STOP_MARKET:
                    order_type = Order.ORDER_TRAILING_STOP_MARKET

                else:
                    order_type = Order.ORDER_LIMIT

                if order['f'] == Client.TIME_IN_FORCE_GTC:
                    time_in_force = Order.TIME_IN_FORCE_GTC
                elif order['f'] == Client.TIME_IN_FORCE_IOC:
                    time_in_force = Order.TIME_IN_FORCE_IOC
                elif order['f'] == Client.TIME_IN_FORCE_FOK:
                    time_in_force = Order.TIME_IN_FORCE_FOK
                else:
                    time_in_force = Order.TIME_IN_FORCE_GTC

                # execution price
                if order['wt'] == 'CONTRACT_PRICE':
                    price_type = Order.PRICE_LAST
                elif order['wt'] == 'MARK_PRICE':
                    price_type = Order.PRICE_MARK
                else:
                    price_type = Order.PRICE_LAST

                order_data = {
                    'id': order_id,
                    'symbol': symbol,
                    'direction': Order.LONG if order['S'] == Client.SIDE_BUY else Order.SHORT,
                    'type': order_type,
                    'timestamp': transaction_timestamp,
                    'quantity': float(order['q']),
                    'price': price,
                    'stop-price': stop_price,
                    'time-in-force': time_in_force,
                    'post-only': order['m'],
                    'close-only': order['cp'],
                    'reduce-only': order['R'],
                    'stop-loss': None,
                    'take-profit': None
                }

                self.service.notify(Signal.SIGNAL_ORDER_OPENED, self.name, (symbol, order_data, client_order_id))

            elif order['x'] == Client.ORDER_STATUS_CANCELED and order['X'] == Client.ORDER_STATUS_CANCELED:
                order_id = str(order['i'])
                org_client_order_id = str(order['c'])

                self.service.notify(Signal.SIGNAL_ORDER_CANCELED, self.name, (symbol, order_id, org_client_order_id))

            elif order['x'] == Client.ORDER_STATUS_EXPIRED and order['X'] == Client.ORDER_STATUS_EXPIRED:
                order_id = str(order['i'])

                # binance send an expired when a STOP/TAKE_PROFIT is hit, then it create a new market order
                # with the same ID and CLID, and then the order is filled in market with the same id
                # so that we cannot send order delete signal else the trader will think the order does not
                # longer exists could not manage its auto remove

                if order['o'] not in ('STOP_MARKET', 'STOP', 'TAKE_PROFIT_MARKET', 'TAKE_PROFIT',
                                      'TRAILING_STOP_MARKET') or float(order['l']) > 0:
                    self.service.notify(Signal.SIGNAL_ORDER_DELETED, self.name, (symbol, order_id, ""))

            elif order['x'] == 'RESTATED':
                pass  # nothing to do (currently unused)

        elif event_type == "ACCOUNT_UPDATE":
            # process the account update after the trades update events

            # balance and position updated
            # @ref https://binance-docs.github.io/apidocs/futures/en/#event-balance-and-position-update
            # exec_logger.info("binancefutures.com ACCOUNT_UPDATE %s" % str(data))
            # field "m" for event reason type in event "ACCOUNT_UPDATE"
            event_timestamp = float(data['E']) * 0.001           

            total_wallet_balance = None
            total_unrealized_profit = None
            total_cross_margin_balance = None
            total_isolated_margin_balance = None

            if 'B' in data['a']:
                total_wallet_balance = 0.0
                total_cross_margin_balance = 0.0

                balances = data['a']['B']
                for b in balances:
                    total_wallet_balance += float(b['wb'])
                    total_cross_margin_balance += float(b['cw'])

            if 'P' in data['a']:
                total_unrealized_profit = 0.0
                total_isolated_margin_balance = 0.0

                operation_time = float(data['T'])

                positions = data['a']['P']
                for pos in positions:
                    symbol = pos['s']
                    ref_order_id = ""

                    direction = Order.LONG if float(pos['pa']) > 0.0 else Order.SHORT

                    total_unrealized_profit += float(pos['up'])

                    # total sum of isolated margin for each symbols
                    if pos['mt'] == 'isolated':  # else 'cross'
                        total_isolated_margin_balance += float(pos['iw'])

                    quantity = abs(float(pos['pa']))

                    position_data = {
                        'id': symbol,
                        'symbol': symbol,
                        'direction': direction,
                        'hedging': 0 if pos['ps'] == 'BOTH' else 1 if pos['ps'] == 'LONG' else -1,
                        'timestamp': operation_time,
                        'quantity': quantity,
                        'avg-entry-price': float(pos['ep']),
                        'exec-price': None,
                        'stop-loss': None,
                        'take-profit': None,
                        'cumulative-filled': quantity,
                        'filled': None,  # no have
                        'liquidation-price': None,  # no have
                        'commission': 0.0,
                        'profit-currency': self.BASE_QUOTE,
                        # 'profit-loss': float(pos['up']),
                        # 'profit-loss-rate': None,
                    }

                    # needed to know if opened or deleted position, only on ORDER event reason type
                    if data['a']['m'] == 'ORDER':
                        key = "%s:%s" % (direction, symbol)
                        last_quantity = self._last_positions.get(key)

                        if not last_quantity and quantity > 0.0:
                            # not last quantity, but now have so position opened
                            self._last_positions[key] = quantity
                            self.service.notify(Signal.SIGNAL_POSITION_OPENED, self.name, (
                                symbol, position_data, ref_order_id))

                        elif last_quantity and quantity > 0.0:
                            # current qty updated
                            self._last_positions[key] = quantity
                            self.service.notify(Signal.SIGNAL_POSITION_UPDATED, self.name, (
                                symbol, position_data, ref_order_id))

                        elif last_quantity and quantity == 0.0:
                            # empty quantity no remaining open order qty, position deleted
                            del self._last_positions[key]
                            self.service.notify(Signal.SIGNAL_POSITION_DELETED, self.name, (
                                symbol, position_data, ref_order_id))

            with self._mutex:
                if total_wallet_balance is not None:
                    self._total_balance['totalWalletBalance'] = total_wallet_balance

                if total_unrealized_profit is not None:
                    self._total_balance['totalUnrealizedProfit'] = total_unrealized_profit

                if total_cross_margin_balance is not None:
                    self._total_balance['totalCrossMarginBalance'] = total_cross_margin_balance

                if total_isolated_margin_balance is not None:
                    self._total_balance['totalIsolatedMarginBalance'] = total_isolated_margin_balance

        elif event_type == "MARGIN_CALL":
            pass

    #
    # misc
    #

    def price_history(self, market_id, timestamp):
        """
        Retrieve the historical price for a specific market id.
        """
        try:
            d = self.connector.futures_price_for_at(market_id, timestamp)
            return (float(d[0][1]) + float(d[0][4]) + float(d[0][3])) / 3.0
        except Exception as e:
            logger.error("Cannot found price history for %s at %s" % (
                market_id, datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')))
            return None

    def update_markets_info(self):
        """
        Update market info.
        """
        self.__prefetch_markets()

        for market_id in self._watched_instruments:
            market = self.fetch_market(market_id)

            if market is None:
                # can be a removed market, signal its closed
                market_data = (market_id, False, time.time(), None, None, None, None, None, None, None)

            elif market.is_open:
                # market exists and tradeable
                market_data = (market_id, market.is_open, market.last_update_time, market.bid, market.ask,
                               market.base_exchange_rate, market.contract_size, market.value_per_pip,
                               market.vol24h_base, market.vol24h_quote)
            else:
                # market exists but closed
                market_data = (market_id, market.is_open, market.last_update_time,
                               None, None, None, None, None, None, None)

            self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

    def fetch_trades(self, market_id, from_date=None, to_date=None, n_last=None):
        trades = []

        try:
            trades = self._connector.client.futures_aggregate_trade_iter(
                market_id, start_str=int(from_date.timestamp() * 1000), end_str=int(to_date.timestamp() * 1000))
        except Exception as e:
            logger.error("Watcher %s cannot retrieve aggregated trades on market %s" % (self.name, market_id))

        count = 0

        for trade in trades:
            count += 1
            # timestamp, bid, ask, last, volume, direction
            yield trade['T'], trade['p'], trade['p'], trade['p'], trade['q'], -1 if trade['m'] else 1

    def fetch_candles(self, market_id, timeframe, from_date=None, to_date=None, n_last=None):
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

        if timeframe not in TF_MAP:
            logger.error("Watcher %s does not support timeframe %s" % (self.name, timeframe))
            return

        candles = []

        tf = TF_MAP[timeframe]

        try:
            candles = self._connector.client.futures_historical_klines(market_id, tf, int(
                from_date.timestamp() * 1000), int(to_date.timestamp() * 1000))
        except Exception as e:
            logger.error("Watcher %s cannot retrieve candles %s on market %s (%s)" % (self.name, tf, market_id, str(e)))

        count = 0
        
        for candle in candles:
            count += 1
            # (timestamp, open, high, low, close, spread, volume)
            yield candle[0], candle[1], candle[2], candle[3], candle[4], 0.0, candle[5]

    def get_balances(self):
        """
        Return a dict with :
            'totalWalletBalance': float,
            'totalUnrealizedProfit': float,
            'totalCrossMarginBalance': float,
            'totalIsolatedMarginBalance': float,
        """
        balances = None

        with self._mutex:
            balances = copy.copy(self._total_balance)

        return balances

