# @date 2020-11-10
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Strategy beta processor.

import time
import traceback

from datetime import datetime, timedelta

from common.utils import UTC

from instrument.instrument import Instrument

from watcher.watcher import Watcher

from strategy.indicator.models import Limits
from strategy.strategydatafeeder import StrategyDataFeeder

from database.database import Database

import logging
logger = logging.getLogger('siis.strategy.process.beta')
error_logger = logging.getLogger('siis.error.strategy.process.beta')
traceback_logger = logging.getLogger('siis.traceback.strategy.process.beta')


def setup_process(strategy):
    """
    Setup this beta processing to the strategy.
    Setup for live and backtesting are OHLCs history, and process trade/tick data for backtesting.
    There is a preprocessing of necessary data that must be disposed by the related strategy data cache
    processing before going to live or to receive backtest data.
    There is a bootstrap processing before going to live or to receive backtest data.
    """
    strategy._setup_backtest = beta_setup_backtest
    strategy._setup_live = beta_setup_live

    strategy._update_strategy = beta_update_strategy
    strategy._async_update_strategy = beta_async_update_strategy


def get_tick_streamer(strategy, strategy_trader, duration=None, from_date=None, timestamp=None):
    to_date = None

    if duration:
        today = datetime.fromtimestamp(time.time(), tz=UTC())

        from_date = today.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC()) - timedelta(seconds=duration)
        to_date = today.replace(tzinfo=UTC())
    elif from_date:
        today = datetime.fromtimestamp(time.time(), tz=UTC())

        # from_date = from_date
        to_date = today.replace(tzinfo=UTC())
    elif timestamp:
        today = datetime.fromtimestamp(time.time(), tz=UTC())

        from_date = datetime.utcfromtimestamp(timestamp).replace(tzinfo=UTC())
        to_date = today.replace(tzinfo=UTC())

    tick_streamer = Database.inst().create_tick_streamer(
        strategy.trader().name, strategy_trader.instrument.market_id, from_date, to_date, buffer_size=32768)

    return tick_streamer


def beta_preprocess(strategy, strategy_trader):
    """
    Load previous cached data and compute missing part of data, cache them.

    @todo to be continued and tested
    @todo must be configurable to take quote streamer in place of trade streamer
    """
    with strategy_trader._mutex:
        if strategy_trader._preprocessing >= 2:
            # in progress
            return

        # preprocessing in progress, avoid live until complete
        strategy_trader._preprocessing = 2

    # @todo non blocking preprocessing       
    instrument = strategy_trader.instrument       

    limits = None
    from_date = None
    to_date = None

    try:
        if strategy_trader._preprocessing == 2:
            logger.debug("%s preprocess begin, now is %s..." % (instrument.market_id, strategy.timestamp))

            try:
                limits = Database.inst().get_cached_limits(strategy.trader_service.trader().name,
                                                           instrument.market_id, strategy.identifier)
            except Exception as e:
                error_logger.error(repr(e))
                limits = None

            if limits is None:
                limits = Limits()

            from_date = datetime.now()  # @todo initial

            if limits.min_price <= 0.0 or limits.max_price <= 0.0:
                # compute limits from the oldest tick
                first_tick = Database.inst().get_first_tick(strategy.trader_service.trader().name, instrument.market_id)
                from_date = datetime.fromtimestamp(first_tick[0], tz=UTC()) if first_tick else None

                logger.debug("%s preprocess missing of trade data, abort %s..." % (
                    instrument.market_id, strategy.timestamp))

                with strategy_trader._mutex:
                    strategy_trader._preprocessing = 0

                return
                # strategy_trader._preprocess_streamer = get_tick_streamer(strategy, strategy_trader, from_date=from_date)
            else:
                # update limits from last computed date
                strategy_trader._preprocess_streamer = strategy_trader.get_tick_streamer(
                    strategy, strategy_trader, timestamp=limits.last_timestamp+0.000001)

            # range of preprocessed data
            strategy_trader._preprocess_range[0] = from_date
            strategy_trader._preprocess_range[1] = datetime.fromtimestamp(time.time(), tz=UTC())

            if strategy_trader._preprocess_streamer:
                timestamp = strategy_trader._preprocess_streamer.from_date.timestamp() + 60*15  # next 15 minutes

                while not strategy_trader._preprocess_streamer.finished():
                    trades = strategy_trader._preprocess_streamer.next(timestamp)

                    for trade in trades:
                        if limits.max_price <= 0.0:
                            limits.max_price = trade[3]

                        if limits.min_price <= 0.0:
                            limits.min_price = trade[3]

                        limits.min_price = min(limits.min_price, trade[3])
                        limits.max_price = max(limits.max_price, trade[3])

                        if limits.from_timestamp <= 0.0:
                            # init first
                            limits.from_timestamp = trade[0]

                        limits.last_timestamp = trade[0]

                        if strategy_trader._preprocess_from_timestamp <= 0:
                            strategy_trader._preprocess_from_timestamp = trade[0]

                    timestamp += 60*15  # next 15 minutes

                # store them
                strategy_trader._limits = limits

                # now limits are computed, reset for the next step
                strategy_trader._preprocess_streamer.reset()

            with strategy_trader._mutex:
                strategy_trader._preprocessing = 3

        if strategy_trader._preprocessing == 3:
            logger.debug("%s preprocess load cache, now is %s..." % (instrument.market_id, strategy.timestamp))

            to_date = datetime.fromtimestamp(strategy.timestamp, tz=UTC())

            if strategy.service.backtesting:
                # start timestamp exclusive
                to_date = to_date - timedelta(microseconds=1)

            from_date = to_date - timedelta(seconds=strategy_trader._preprocess_depth)

            strategy_trader.preprocess_load_cache(from_date, to_date)

            with strategy_trader._mutex:
                # now can update using more recent data
                strategy_trader._preprocessing = 4

        if strategy_trader._preprocessing == 4:
            logger.debug("%s preprocess update, now is %s..." % (instrument.market_id, strategy.timestamp))

            if strategy_trader._preprocess_streamer:
                base_timestamp = 0.0
                timestamp = strategy_trader._preprocess_streamer.from_date.timestamp() + 60*15  # next 15 minutes

                while not strategy_trader._preprocess_streamer.finished():
                    trades = strategy_trader._preprocess_streamer.next(timestamp)

                    for trade in trades:
                        strategy_trader.preprocess(trade)

                    timestamp += 60*15  # next 15 minutes

                strategy_trader._preprocess_streamer = None

            with strategy_trader._mutex:
                # now can store in cache news and updated results
                strategy_trader._preprocessing = 5

        if strategy_trader._preprocessing == 5:
            try:
                Database.inst().store_cached_limits(strategy.trader_service.trader().name,
                                                    instrument.market_id, strategy.identifier, limits)
                strategy_trader.preprocess_store_cache(from_date, to_date)

            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

            with strategy_trader._mutex:
                # now preprocessing is done
                strategy_trader._preprocessing = 0

            logger.debug("%s preprocess done, now is %s" % (instrument.market_id, strategy.timestamp))

    except Exception as e:
        error_logger.error(repr(e))
        traceback_logger.error(traceback.format_exc())


def beta_bootstrap(strategy, strategy_trader):
    """
    Process the bootstrap of the strategy trader until complete using the preloaded OHLCs.
    Any received updates are ignored until the bootstrap is completed.
    """
    with strategy_trader._mutex:
        if strategy_trader._bootstrapping == 2:
            # in progress
            return

        # bootstrapping in progress, avoid live until complete
        strategy_trader._bootstrapping = 2

    try:
        if strategy_trader.is_timeframes_based:
            timeframe_based_bootstrap(strategy, strategy_trader)
        elif strategy_trader.is_tickbars_based:
            tickbar_based_bootstrap(strategy, strategy_trader)
    except Exception as e:
        error_logger.error(repr(e))
        traceback_logger.error(traceback.format_exc())

    with strategy_trader._mutex:
        # bootstrapping done, can now branch to live
        strategy_trader._bootstrapping = 0


def timeframe_based_bootstrap(strategy, strategy_trader):
    # captures all initials candles
    initial_candles = {}

    # compute the beginning timestamp
    timestamp = strategy.timestamp

    instrument = strategy_trader.instrument

    for tf, sub in strategy_trader.timeframes.items():
        candles = instrument.candles(tf)
        initial_candles[tf] = candles

        # reset, distribute one at time
        instrument._candles[tf] = []

        if candles:
            # get the nearest next candle
            timestamp = min(timestamp, candles[0].timestamp + sub.depth*sub.timeframe)

    logger.debug("%s timeframes bootstrap begin at %s, now is %s" % (
        instrument.market_id, timestamp, strategy.timestamp))

    # initials candles
    lower_timeframe = 0

    for tf, sub in strategy_trader.timeframes.items():
        candles = initial_candles[tf]

        # feed with the initials candles
        while candles and timestamp >= candles[0].timestamp:
            candle = candles.pop(0)

            instrument._candles[tf].append(candle)

            # and last is closed
            sub._last_closed = True

            # keep safe size
            if(len(instrument._candles[tf])) > sub.depth:
                instrument._candles[tf].pop(0)

            # prev and last price according to the lower timeframe close
            if not lower_timeframe or tf < lower_timeframe:
                lower_timeframe = tf
                strategy_trader.prev_price = strategy_trader.last_price
                strategy_trader.last_price = candle.close  # last mid close

    # process one lowest candle at time
    while 1:
        num_candles = 0
        strategy_trader.bootstrap(timestamp)

        # at least of lower timeframe
        base_timestamp = 0.0
        lower_timeframe = 0

        # increment by the lower available timeframe
        for tf, sub in strategy_trader.timeframes.items():
            if initial_candles[tf]:
                if not base_timestamp:
                    # initiate with the first
                    base_timestamp = initial_candles[tf][0].timestamp

                elif initial_candles[tf][0].timestamp < base_timestamp:
                    # found a lower
                    base_timestamp = initial_candles[tf][0].timestamp

        for tf, sub in strategy_trader.timeframes.items():
            candles = initial_candles[tf]

            # feed with the next candle
            if candles and base_timestamp >= candles[0].timestamp:
                candle = candles.pop(0)

                instrument._candles[tf].append(candle)

                # and last is closed
                sub._last_closed = True

                # keep safe size
                if(len(instrument._candles[tf])) > sub.depth:
                    instrument._candles[tf].pop(0)

                if not lower_timeframe or tf < lower_timeframe:
                    lower_timeframe = tf
                    strategy_trader.prev_price = strategy_trader.last_price
                    strategy_trader.last_price = candle.close  # last mid close

                num_candles += 1

        # logger.info("next is %s (delta=%s) / now %s (n=%i) (low=%s)" % (base_timestamp, base_timestamp-timestamp, strategy.timestamp, num_candles, lower_timeframe))
        timestamp = base_timestamp

        if not num_candles:
            # no more candles to process
            break

    logger.debug("%s timeframes bootstrapping done" % instrument.market_id)


def tickbar_based_bootstrap(strategy, strategy_trader):
    # captures all initials ticks
    initial_ticks = []

    # compute the beginning timestamp
    timestamp = strategy.timestamp

    instrument = strategy_trader.instrument

    logger.debug("%s tickbars bootstrap begin at %s, now is %s" % (instrument.market_id, timestamp, strategy.timestamp))

    # @todo need tickstreamer, and call strategy_trader.bootstrap(timestamp) at per bulk of ticks (
    #  temporal size defined)

    logger.debug("%s tickbars bootstrapping done" % instrument.market_id)


def beta_update_strategy(strategy, strategy_trader):
    """
    Compute a strategy step per instrument.
    Default implementation supports bootstrapping.
    @param strategy_trader StrategyTrader Instance of the strategy trader to process.
    @note Non thread-safe method.
    """
    if strategy_trader:
        if strategy_trader._initialized == 1:
            initiate_strategy_trader(strategy, strategy_trader)

        if strategy_trader._checked == 1:
            # need to check existing trade orders, trade history and positions
            strategy_trader.check_trades(strategy.timestamp)

        if strategy_trader._initialized != 0 or strategy_trader._checked != 0 or not strategy_trader.instrument.ready():
            # process only if instrument has data
            return

        if strategy_trader._processing:
            # process only if previous job was completed
            return

        try:
            strategy_trader._processing = True

            if strategy_trader._preprocessing > 0:
                # first : preprocessing and data caching
                beta_preprocess(strategy, strategy_trader)

            elif strategy_trader._bootstrapping > 0:
                # second : bootstrap using preloaded data history
                beta_bootstrap(strategy, strategy_trader)

            else:
                # then : until process instrument update
                strategy_trader.process(strategy.timestamp)

        except Exception as e:
            error_logger.error(repr(e))
            traceback_logger.error(traceback.format_exc())

        finally:
            # process complete
            strategy_trader._processing = False


def beta_async_update_strategy(strategy, strategy_trader):
    """
    Override this method to compute a strategy step per instrument.
    Default implementation supports bootstrapping.
    @param strategy
    @param strategy_trader StrategyTrader Instance of the strategy trader to process.
    @note Thread-safe method.
    """
    if strategy_trader:
        if strategy_trader._initialized == 1:
            initiate_strategy_trader(strategy, strategy_trader)

        if strategy_trader._checked == 1:
            # need to check existing trade orders, trade history and positions
            strategy_trader.check_trades(strategy.timestamp)

        if strategy_trader._initialized != 0 or strategy_trader._checked != 0 or not strategy_trader.instrument.ready():
            # process only if instrument has data
            return

        if strategy_trader._processing:
            # process only if previous job was completed
            return

        try:
            strategy_trader._processing = True

            if strategy_trader._preprocessing > 0:
                # first : preprocessing and data caching
                beta_preprocess(strategy, strategy_trader)

            elif strategy_trader._bootstrapping > 0:
                # second : bootstrap using preloaded data history
                beta_bootstrap(strategy, strategy_trader)

            else:
                # then : until process instrument update
                strategy_trader.process(strategy.timestamp)

        except Exception as e:
            error_logger.error(repr(e))
            traceback_logger.error(traceback.format_exc())

        finally:
            # process complete
            strategy_trader._processing = False


def initiate_strategy_trader(strategy, strategy_trader):
    """
    Do it async into the workers to avoid long blocking of the strategy thread.
    """
    with strategy_trader._mutex:
        if strategy_trader._initialized != 1:
            # only if waiting for initialize
            return

        strategy_trader._initialized = 2

    now = datetime.now()

    instrument = strategy_trader.instrument
    try:
        watcher = instrument.watcher(Watcher.WATCHER_PRICE_AND_VOLUME)
        if watcher:
            # update from last ticks
            watcher.subscribe(instrument.market_id, None, -1, None)

            # initialization processed, waiting for data be ready
            with strategy_trader._mutex:
                strategy_trader._initialized = 0

        # wake-up
        strategy.send_update_strategy_trader(instrument.market_id)

    except Exception as e:
        logger.error(repr(e))
        logger.debug(traceback.format_exc())


#
# backtesting setup
#

def beta_setup_backtest(strategy, from_date, to_date, base_timeframe=Instrument.TF_TICK):
    """
    Simple load history of trades, no OHLCs.
    """
    for market_id, instrument in strategy._instruments.items():
        # retrieve the related price and volume watcher
        watcher = instrument.watcher(Watcher.WATCHER_PRICE_AND_VOLUME)

        # create a feeder per instrument and fetch ticks only
        feeder = StrategyDataFeeder(strategy, instrument.market_id, [], True)
        strategy.add_feeder(feeder)

        # fetch market info from the DB
        Database.inst().load_market_info(strategy.service, watcher.name, instrument.market_id)

        feeder.initialize(watcher.name, from_date, to_date)

    # initialized state
    for k, strategy_trader in strategy._strategy_traders.items():
        with strategy_trader._mutex:
            strategy_trader._initialized = 0


#
# live setup
#

def beta_setup_live(strategy):
    """
    Do it here dataset preload and other stuff before update be called.
    """
    logger.info("In strategy %s retrieves states and previous trades..." % strategy.name)

    # load the strategy-traders and traders for this strategy/account
    trader = strategy.trader()

    for market_id, instrument in strategy._instruments.items():
        # wake-up all for initialization
        strategy.send_initialize_strategy_trader(market_id)

    if strategy.service.load_on_startup:
        strategy.load()

    logger.info("Strategy %s data retrieved" % strategy.name)
