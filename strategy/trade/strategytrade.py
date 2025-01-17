# @date 2018-12-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy trade base class

from __future__ import annotations

from typing import TYPE_CHECKING, Union, Optional, Tuple, List

if TYPE_CHECKING:
    from trader.trader import Trader
    from instrument.instrument import Instrument
    from strategy.tradeop.tradeop import TradeOp
    from strategy.strategytrader import StrategyTrader
    from strategy.strategytradercontext import StrategyTraderContextBuilder

from datetime import datetime

from common.utils import timeframe_to_str, UTC

from trader.order import Order, order_type_to_str

import logging
logger = logging.getLogger('siis.strategy.trade')


class StrategyTrade(object):
    """
    Strategy trade base abstract class. A trade is related to entry and and one or many exit order.
    It can be created from an automated or manual signal, and having some initial conditions, timeframe, expiry,
    and they are managed according to the policy of a strategy trade manager, or from some other operations added
    manually for semi-automated trading.

    It can only have on entry order. The exit works with the entry quantity. When the entry order is not fully filled,
    the exit order are later adjusted.

    @todo Take care to do not try to serialize objects from extra dict.
    """

    __slots__ = '_trade_type', '_entry_state', '_exit_state', '_closing', '_timeframe', '_operations', '_user_trade', \
                '_next_operation_id', 'id', 'dir', 'op', 'oq', 'tp', 'sl', 'aep', 'axp', 'eot', 'xot', 'e', 'x', \
                'pl', '_stats', 'last_tp_ot', 'last_stop_ot', 'exit_trades', '_label', '_entry_timeout', '_expiry', \
                '_dirty', '_extra', 'context', '_comment'

    VERSION = "1.0.0"

    TRADE_UNDEFINED = -1
    TRADE_BUY_SELL = 0    # spot/asset trade
    TRADE_ASSET = 0
    TRADE_SPOT = 0
    TRADE_MARGIN = 1      # individual margin trade but as FIFO position (incompatible with hedging markets)
    TRADE_IND_MARGIN = 2  # indivisible margin trade position (incompatible with hedging markets)
    TRADE_POSITION = 3    # individual margin trade position (compatible with hedging markets)

    STATE_UNDEFINED = -1
    STATE_NEW = 0
    STATE_REJECTED = 1
    STATE_DELETED = 2
    STATE_CANCELED = 3
    STATE_OPENED = 4
    STATE_PARTIALLY_FILLED = 5
    STATE_FILLED = 6
    STATE_ERROR = 7

    INSUFFICIENT_MARGIN = -3
    INSUFFICIENT_FUNDS = -2
    ERROR = -1
    REJECTED = 0
    ACCEPTED = 1
    NOTHING_TO_DO = 2

    REASON_NONE = 0
    REASON_TAKE_PROFIT_MARKET = 1   # take-profit market hit
    REASON_TAKE_PROFIT_LIMIT = 2    # take-profit limit hit
    REASON_STOP_LOSS_MARKET = 3     # stop-loss market hit
    REASON_STOP_LOSS_LIMIT = 4      # stop-loss limit hit
    REASON_CLOSE_MARKET = 5         # exit signal at market
    REASON_CANCELED_TIMEOUT = 6     # canceled after a timeout expiration delay
    REASON_CANCELED_TARGETED = 7    # canceled before entering because take-profit price reached before entry price
    REASON_MARKET_TIMEOUT = 8       # closed (in profit or in loss) after a timeout

    def __init__(self, trade_type: int, timeframe: float):
        self._trade_type = trade_type

        self._entry_state = StrategyTrade.STATE_NEW
        self._exit_state = StrategyTrade.STATE_NEW
        self._closing = False

        # flag set when the quantity of the entry trade increase and then the exit orders must be updated
        self._dirty = False

        self._timeframe = timeframe  # timeframe that have given this trade

        # list containing the operation to process during the trade for semi-automated trading
        self._operations = []

        # true if the user is responsible for the TP & SL adjustment else (default) strategy manage it
        self._user_trade = False

        self._label = ""           # trade label(must be few chars)
        self._entry_timeout = 0    # expiration delay in seconds of the entry
        self._expiry = 0           # expiration delay in seconds or 0 if never

        self._next_operation_id = 1

        self.id = 0      # unique trade identifier
        self.dir = 0     # direction (1 long, -1 short)

        self.op = 0.0    # ordered price (limit)
        self.oq = 0.0    # ordered quantity

        self.tp = 0.0    # take-profit price
        self.sl = 0.0    # stop-loss price

        self.aep = 0.0   # average entry price
        self.axp = 0.0   # average exit price

        self.eot = 0.0   # entry order opened timestamp
        self.xot = 0.0   # exit order opened timestamp

        # a correctly closed trade must have x == f with f <= q and q > 0
        self.e = 0.0     # current filled entry quantity
        self.x = 0.0     # current filled exit quantity

        self.pl = 0.0    # once closed profit/loss in percent (valid once partially or fully closed)

        self.exit_trades = {}  # contain each executed exit trades {<orderId> : (<qty>, <price>)}

        self.last_stop_ot = [0, 0]
        self.last_tp_ot = [0, 0]

        self.context = None  # reference to an object concerning the context of the trade from StrategySignal.context

        self._stats = {
            'best-price': 0.0,
            'best-timestamp': 0.0,
            'worst-price': 0.0,
            'worst-timestamp': 0.0,
            'entry-order-type': Order.ORDER_LIMIT,
            'take-profit-order-type': Order.ORDER_LIMIT,
            'stop-order-type': Order.ORDER_MARKET,
            'first-realized-entry-timestamp': 0.0,
            'first-realized-exit-timestamp': 0.0,
            'last-realized-entry-timestamp': 0.0,
            'last-realized-exit-timestamp': 0.0,
            'unrealized-profit-loss': 0.0,
            'profit-loss-currency': "",
            'entry-fees': 0.0,
            'exit-fees': 0.0,
            'exit-reason': StrategyTrade.REASON_NONE,
            'conditions': {}
        }

        self._extra = {}
        self._comment = ""

    #
    # getters
    #

    @classmethod
    def version(cls) -> str:
        return cls.VERSION

    @classmethod
    def is_margin(cls) -> bool:
        """
        Overrides, must return true if the trader is margin based.
        """
        return False

    @classmethod
    def is_spot(cls) -> bool:
        """
        Overrides, must return true if the trader is spot based.
        """
        return False

    @property
    def trade_type(self) -> int:
        return self._trade_type

    @property
    def entry_state(self) -> int:
        return self._entry_state

    @property
    def exit_state(self) -> int:
        return self._exit_state   

    @property
    def direction(self) -> int:
        return self.dir
    
    def close_direction(self) -> int:
        return -self.dir

    @property
    def entry_open_time(self) -> float:
        return self.eot

    @property
    def exit_open_time(self) -> float:
        return self.xot

    @property
    def order_quantity(self) -> float:
        return self.oq

    @property
    def quantity(self) -> float:
        """Synonym for order_quantity"""
        return self.oq

    @property
    def invested_quantity(self) -> float:
        """
        Return the actively invested quantity or to be invested if not an active trade.
        """
        if self.is_active():
            return (self.e - self.x) * self.aep
        elif self.op:
            return self.oq * self.op
        else:
            return 0.0

    @property  
    def order_price(self) -> float:
        return self.op

    @property
    def take_profit(self) -> float:
        return self.tp
    
    @property
    def stop_loss(self) -> float:
        return self.sl

    @property
    def entry_price(self) -> float:
        return self.aep

    @property
    def exit_price(self) -> float:
        return self.axp

    @property
    def exec_entry_qty(self) -> float:
        return self.e
    
    @property
    def exec_exit_qty(self) -> float:
        return self.x

    @property
    def profit_loss(self) -> float:
        return self.pl

    @property
    def timeframe(self) -> float:
        return self._timeframe

    @timeframe.setter
    def timeframe(self, timeframe: float):
        self._timeframe = timeframe

    @property
    def expiry(self) -> float:
        return self._expiry

    @property
    def entry_timeout(self) -> float:
        return self._entry_timeout

    @property
    def entry_order_type(self) -> int:
        return self._stats['entry-order-type']

    @property
    def first_realized_entry_time(self) -> float:
        return self._stats['first-realized-entry-timestamp']

    @property
    def first_realized_exit_time(self) -> float:
        return self._stats['first-realized-exit-timestamp']

    @property
    def last_realized_entry_time(self) -> float:
        return self._stats['last-realized-entry-timestamp']

    @property
    def last_realized_exit_time(self) -> float:
        return self._stats['last-realized-exit-timestamp']

    @property
    def unrealized_profit_loss(self) -> float:
        return self._stats['unrealized-profit-loss']

    @property
    def profit_loss_currency(self) -> str:
        return self._stats['profit-loss-currency']

    @property
    def exit_reason(self) -> int:
        return self._stats['exit-reason']

    @exit_reason.setter
    def exit_reason(self, reason: int):
        self._stats['exit-reason'] = reason

    @expiry.setter
    def expiry(self, expiry: float):
        self._expiry = expiry

    @entry_timeout.setter
    def entry_timeout(self, timeout: float):
        self._entry_timeout = timeout

    def set_user_trade(self, user_trade: bool = True):
        self._user_trade = user_trade

    def is_user_trade(self) -> bool:
        return self._user_trade

    @property
    def last_take_profit(self) -> List[float, float]:
        """Last take-profit order creation/modification timestamp"""
        return self.last_tp_ot

    @property
    def last_stop_loss(self) -> List[float, float]:
        """Last stop-loss order creation/modification timestamp"""
        return self.last_stop_ot

    @property
    def label(self) -> str:
        return self._label

    @label.setter
    def label(self, label: str):
        self._label = label

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    @property
    def comment(self) -> str:
        return self._comment

    @comment.setter
    def comment(self, comment: str):
        if len(comment) <= 100:
            self._comment = comment

    #
    # processing
    #

    def open(self, trader: Trader, instrument: Instrument, direction: int, order_type: int,
             order_price: float, quantity: float, take_profit: float, stop_loss: float,
             leverage: float = 1.0, hedging: Optional[bool] = None) -> bool:
        """
        Order to open a position or to buy an asset.

        @param trader Trader Valid trader handler.
        @param instrument Instrument object.
        @param direction int Order direction (1 or -1)
        @param order_type int Order type (market, limit...)
        @param order_price float Limit order price or None for market
        @param quantity float Quantity in unit of quantity
        @param take_profit float Initial take-profit price or None
        @param stop_loss float Initial stop-loss price or None
        @param leverage float For some brokers leverage multiplier else unused
        @param hedging boolean On margin market if True could open positions of opposites directions
        """
        return False

    def reopen(self, trader: Trader, instrument: Instrument, quantity: float) -> bool:
        """
        Order to reopen a position or to buy an asset by using previous parameters except the quantity.

        @param trader Trader Valid trader handler.
        @param instrument Instrument object.
        @param quantity float Quantity in unit of quantity
        """
        return False

    def assign(self, trader: Trader, instrument: Instrument, direction: int, order_type: int,
               order_price: float, quantity: float, take_profit: float, stop_loss: float,
               leverage: float = 1.0, hedging: Optional[bool] = None) -> bool:
        """
        Assign an open a position on buy or sell.

        @param trader Trader Valid trader handler.
        @param instrument Instrument object.
        @param direction int Order direction (1 or -1)
        @param order_type int Order type (market, limit...)
        @param order_price float Executed entry price
        @param quantity float Quantity in unit of quantity
        @param take_profit float Initial take-profit price or None
        @param stop_loss float Initial stop-loss price or None
        @param leverage float For some brokers leverage multiplier else unused
        @param hedging boolean On margin market if True could open positions of opposites directions
        """
        # user managed trade
        self.set_user_trade()

        self._entry_state = StrategyTrade.STATE_FILLED
        self._exit_state = StrategyTrade.STATE_NEW

        self.dir = direction
        self.op = order_price
        self.oq = quantity

        self.tp = take_profit
        self.sl = stop_loss

        self.eot = trader.timestamp

        self.aep = order_price

        self.e = quantity

        self._stats['entry-order-type'] = order_type
        self._stats['profit-loss-currency'] = instrument.quote

        return True

    def remove(self, trader: Trader, instrument: Instrument) -> bool:
        """
        Remove the trade and related remaining orders.
        @return True if all orders no longer exists.
        """
        return True

    def can_delete(self) -> bool:
        """
        Because of the slippage once a trade is closed deletion can only be done once all the quantity of the
        asset or the position are executed.
        """
        if self._entry_state == StrategyTrade.STATE_FILLED and self._exit_state == StrategyTrade.STATE_FILLED:
            # entry and exit are fully filled
            return True

        if self._entry_state == StrategyTrade.STATE_REJECTED:
            # entry rejected
            return True

        if ((self._entry_state == StrategyTrade.STATE_CANCELED or
             self._entry_state == StrategyTrade.STATE_DELETED) and self.e <= 0):
            # entry canceled or deleted and empty
            return True

        return False

    def is_error(self) -> bool:
        """
        Return true if the trade entry or exit are in error state.
        """
        return self._entry_state == StrategyTrade.STATE_ERROR or self._exit_state == StrategyTrade.STATE_ERROR

    def is_active(self) -> bool:
        """
        Return true if the trade is active (non-null entry qty, and exit quantity non fully completed).
        """
        if self._exit_state == StrategyTrade.STATE_FILLED:
            return False

        return (self._entry_state == StrategyTrade.STATE_PARTIALLY_FILLED or
                self._entry_state == StrategyTrade.STATE_FILLED)

    def is_opened(self) -> bool:
        """
        Return true if the entry trade is opened but no qty filled at this moment time.
        """
        return self._entry_state == StrategyTrade.STATE_OPENED

    def is_canceled(self) -> bool:
        """
        Return true if the trade is not active, canceled or rejected.
        """
        if self._entry_state == StrategyTrade.STATE_REJECTED:
            return True

        if self._entry_state == StrategyTrade.STATE_CANCELED and self.e <= 0:
            return True

        return False

    def is_opening(self) -> bool:
        """
        Is entry order in progress.
        """
        return (self._entry_state == StrategyTrade.STATE_OPENED or
                self._entry_state == StrategyTrade.STATE_PARTIALLY_FILLED)

    def is_closing(self) -> bool:
        """
        Is close order in progress.
        """
        return self._closing and self._exit_state != StrategyTrade.STATE_FILLED

    def is_closed(self) -> bool:
        """
        Is trade fully closed (all qty sold).
        """
        return self._exit_state == StrategyTrade.STATE_FILLED

    def is_entry_timeout(self, timestamp: float, timeout: float) -> bool:
        """
        Return true if the trade entry timeout.

        @note created timestamp t must be valid else it will timeout every time.
        """
        return ((self._entry_state == StrategyTrade.STATE_OPENED) and (self.e == 0) and (self.eot > 0) and
                timeout > 0.0 and ((timestamp - self.eot) >= timeout))

    def is_trade_timeout(self, timestamp: float) -> bool:
        """
        Return true if the trade timeout.

        @note created timestamp t must be valid else it will timeout every time.
        """
        return ((self._entry_state in (StrategyTrade.STATE_PARTIALLY_FILLED, StrategyTrade.STATE_FILLED)) and
                (self._expiry > 0.0) and (self.e > 0) and (self.eot > 0) and (timestamp > 0.0) and
                ((timestamp - self.eot) >= self._expiry))

    def is_duration_timeout(self, timestamp: float, duration: float) -> bool:
        """
        Return true if the trade timeout after given duration.

        @note created timestamp t must be valid else it will timeout every time.
        """
        return ((self._entry_state in (StrategyTrade.STATE_PARTIALLY_FILLED, StrategyTrade.STATE_FILLED)) and
                (duration > 0.0) and (self.e > 0) and (self.eot > 0) and (timestamp > 0.0) and
                ((timestamp - self.eot) >= duration))

    def is_valid(self, timestamp: float, validity: float) -> bool:
        """
        Return true if the trade is not expired (signal still acceptable) and entry quantity not fully filled.
        """
        return (((self._entry_state == StrategyTrade.STATE_OPENED or
                  self._entry_state == StrategyTrade.STATE_PARTIALLY_FILLED) and
                 (validity > 0.0) and (timestamp > 0.0) and ((timestamp - self.entry_open_time) <= validity)))

    def cancel_open(self, trader: Trader, instrument: Instrument) -> int:
        """
        Cancel the entire or remaining open order.
        """
        return StrategyTrade.NOTHING_TO_DO

    def cancel_close(self, trader: Trader, instrument: Instrument) -> int:
        """
        Cancel the entire or remaining close order.

        @param trader: Trader instance.
        @param instrument: Related Instrument instance.

        @todo Not implemented in specialized class for now
        """
        return StrategyTrade.NOTHING_TO_DO

    def modify_take_profit(self, trader: Trader, instrument: Instrument, limit_price: float, hard: bool = True) -> int:
        """
        Create/modify the take-order limit order or position limit.
        A limit_price of 0 remove an existing order.

        @param trader: Trader instance.
        @param instrument: Related Instrument instance.
        @param limit_price: Limit (take-profit) price or 0 to remove
        @param hard Create a take profit or limit order, else it is a soft market price managed by the strategy.
        """
        return self.NOTHING_TO_DO

    def modify_stop_loss(self, trader: Trader, instrument: Instrument, stop_price: float, hard: bool = True) -> int:
        """
        Create/modify the stop-loss taker order or position limit.
        A stop_price of 0 remove an existing order.

        @param trader: Trader instance.
        @param instrument: Related Instrument instance.
        @param stop_price: Stop market (stop-loss or stop-profit) price or 0 to remove
        @param hard Create a market stop loss (or profit) order, else it is a soft market price managed by the strategy.
        """
        return self.NOTHING_TO_DO

    def modify_oco(self, trader: Trader, instrument: Instrument, limit_price: float, stop_price: float,
                   hard: bool = True) -> int:
        """
        Create/modify the OCO order with both take-profit and stop-loss orders.

        @param trader: Trader instance.
        @param instrument: Related Instrument instance.
        @param limit_price: Limit (take-profit) price or 0 to remove
        @param stop_price: Stop market (stop-loss or stop-profit) price or 0 to remove
        @param hard Create a take profit or limit order, else it is a soft market price managed by the strategy.
        """
        return self.NOTHING_TO_DO

    def close(self, trader: Trader, instrument: Instrument) -> int:
        """
        Close the position or sell the asset.
        """
        return self.NOTHING_TO_DO

    def has_stop_order(self) -> bool:
        """
        Overrides, must return true if the trade have a broker side stop order, else local trigger stop.
        """
        return False

    def has_limit_order(self) -> bool:
        """
        Overrides, must return true if the trade have a broker side limit order, else local take-profit stop
        """
        return False

    def has_oco_order(self) -> bool:
        """
        Overrides, must return true if the trade have a broker side OCO order
        """
        return False

    def support_both_order(self) -> bool:
        """
        Overrides, must return true if the trader support stop and limit order at the same time
        """
        return False

    def can_modify_limit_order(self, timestamp: float, max_count: int = 1, timeout: float = 10.0) -> bool:
        """
        Can modify the limit order according to current timestamp and previous limit order timestamp,
        and max change per count duration in seconds.
        """
        if self.last_tp_ot[0] <= 0 or self.last_tp_ot[1] <= 0:
            # never modified, accept
            return True

        if timestamp - self.last_tp_ot[0] >= timeout:
            # not modified since timeout
            return True

        if not self.has_limit_order():
            # not have existing limit order
            return True

        return False

    def can_modify_stop_order(self, timestamp: float, max_count: int = 1, timeout: float = 10.0) -> bool:
        """
        Can modify the stop order according to current timestamp and previous stop order timestamp,
        and max change per count duration in seconds.
        """
        if self.last_stop_ot[0] <= 0 or self.last_stop_ot[1] <= 0:
            # never modified, accept
            return True

        if timestamp - self.last_stop_ot[0] >= timeout:
            # not modified since timeout
            return True

        if not self.has_stop_order():
            # not have existing stop order
            return True

        return False

    #
    # signals
    #

    def order_signal(self, signal_type: int, data: dict, ref_order_id: str, instrument: Instrument):
        pass

    def position_signal(self, signal_type: int, data: dict, ref_order_id: str, instrument: Instrument):
        pass

    def is_target_order(self, order_id: str, ref_order_id: str) -> bool:
        return False

    def is_target_position(self, position_id: str, ref_order_id: str) -> bool:
        return False

    def update_dirty(self, trader: Trader, instrument: Instrument):
        pass

    #
    # Helpers
    #

    def direction_to_str(self) -> str:
        if self.dir > 0:
            return 'long'
        elif self.dir < 0:
            return 'short'
        else:
            return ''

    def direction_from_str(self, direction: str):
        if direction == 'long':
            self.dir = 1
        elif direction == 'short':
            self.dir = -1
        else:
            self.dir = 0

    def state_to_str(self) -> str:
        """
        Get a string for the state of the trade (only for display usage).
        """
        if self._entry_state == StrategyTrade.STATE_NEW:
            # entry is new, not ordered
            return 'new'
        elif self._entry_state == StrategyTrade.STATE_OPENED:
            # the entry order is created, waiting for filling
            return 'opened'
        elif self._entry_state == StrategyTrade.STATE_REJECTED:
            # the entry order is rejected, trade must be deleted
            return 'rejected'
        elif self._exit_state == StrategyTrade.STATE_REJECTED and self.e > self.x:
            # exit order is rejected but the exit quantity is not fully filled (x < e), this case must be managed
            return 'problem'
        elif self._entry_state == StrategyTrade.STATE_PARTIALLY_FILLED:
            # entry order filling until complete
            return 'filling'
        elif self._exit_state == StrategyTrade.STATE_PARTIALLY_FILLED:
            # exit order filling until complete
            return 'closing'
        elif self._entry_state == StrategyTrade.STATE_FILLED and self._exit_state == StrategyTrade.STATE_FILLED:
            # entry and exit are completed
            return 'closed'
        elif self._entry_state == StrategyTrade.STATE_CANCELED and self.e <= 0: 
            # not entry quantity and entry order canceled
            return 'canceled'
        elif self._entry_state == StrategyTrade.STATE_FILLED:
            # entry order completed
            return 'filled'
        elif self._entry_state == StrategyTrade.STATE_ERROR or self._exit_state == StrategyTrade.STATE_ERROR:
            # order entry or exit error
            return 'error'
        else:
            # any other's case meaning pending state
            return 'waiting'

    def timeframe_to_str(self) -> str:
        return timeframe_to_str(self._timeframe)

    def trade_type_to_str(self) -> str:
        if self._trade_type == StrategyTrade.TRADE_ASSET:
            return 'asset'
        elif self._trade_type == StrategyTrade.TRADE_MARGIN:
            return 'margin'
        elif self._trade_type == StrategyTrade.TRADE_IND_MARGIN:
            return 'ind-margin'
        elif self._trade_type == StrategyTrade.TRADE_POSITION:
            return 'position'
        else:
            return "undefined"

    @staticmethod
    def trade_type_from_str(trade_type: str) -> int:
        if trade_type == 'asset':
            return StrategyTrade.TRADE_ASSET
        elif trade_type == 'margin':
            return StrategyTrade.TRADE_MARGIN
        elif trade_type == 'ind-margin':
            return StrategyTrade.TRADE_IND_MARGIN
        elif trade_type == 'position':
            return StrategyTrade.TRADE_POSITION
        else:
            return StrategyTrade.TRADE_UNDEFINED

    @staticmethod
    def trade_state_to_str(trade_state: int) -> str:
        if trade_state == StrategyTrade.STATE_NEW:
            return 'new'
        elif trade_state == StrategyTrade.STATE_REJECTED:
            return 'rejected'
        elif trade_state == StrategyTrade.STATE_DELETED:
            return 'deleted'
        elif trade_state == StrategyTrade.STATE_CANCELED:
            return 'canceled'
        elif trade_state == StrategyTrade.STATE_OPENED:
            return 'opened'
        elif trade_state == StrategyTrade.STATE_PARTIALLY_FILLED:
            return 'partially-filled'
        elif trade_state == StrategyTrade.STATE_FILLED:
            return 'filled'
        elif trade_state == StrategyTrade.STATE_ERROR:
            return 'error'
        else:
            return "undefined"

    @staticmethod
    def trade_state_from_str(trade_state: str) -> int:
        if trade_state == 'new':
            return StrategyTrade.STATE_NEW
        elif trade_state == 'rejected':
            return StrategyTrade.STATE_REJECTED
        elif trade_state == 'deleted':
            return StrategyTrade.STATE_DELETED
        elif trade_state == 'canceled':
            return StrategyTrade.STATE_CANCELED
        elif trade_state == 'opened':
            return StrategyTrade.STATE_OPENED
        elif trade_state == 'partially-filled':
            return StrategyTrade.STATE_PARTIALLY_FILLED
        elif trade_state == 'filled':
            return StrategyTrade.STATE_FILLED
        elif trade_state == 'error':
            return StrategyTrade.STATE_ERROR
        else:
            return StrategyTrade.STATE_UNDEFINED

    @staticmethod
    def reason_to_str(reason: int) -> str:
        if reason == StrategyTrade.REASON_NONE:
            return "undefined"
        elif reason == StrategyTrade.REASON_MARKET_TIMEOUT:
            return "timeout-market"
        elif reason == StrategyTrade.REASON_CLOSE_MARKET:
            return "close-market"
        elif reason == StrategyTrade.REASON_STOP_LOSS_MARKET:
            return "stop-loss-market"
        elif reason == StrategyTrade.REASON_STOP_LOSS_LIMIT:
            return "stop-loss-limit"
        elif reason == StrategyTrade.REASON_TAKE_PROFIT_LIMIT:
            return "take-profit-limit"
        elif reason == StrategyTrade.REASON_TAKE_PROFIT_MARKET:
            return "take-profit-market"
        elif reason == StrategyTrade.REASON_CANCELED_TARGETED:
            return "canceled-targeted"
        elif reason == StrategyTrade.REASON_CANCELED_TIMEOUT:
            return "canceled-timeout"
        else:
            return "undefined"

    def entry_order_type_to_str(self) -> str:
        return order_type_to_str(self._stats['entry-order-type'])

    #
    # persistence
    #

    @staticmethod
    def dump_timestamp(timestamp: Optional[float]) -> Union[str, None]:
        return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%S.%fZ') if timestamp else None

    @staticmethod
    def load_timestamp(datetime_str: str) -> float:
        if datetime_str:
            return datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=UTC()).timestamp()
        else:
            return 0.0

    def dumps(self) -> dict:
        """
        Override this method to make a dumps for the persistence.
        @return dict with at least as defined in this method.
        @note Data are not humanized.
        """
        return {
            'version': self.version(),
            'id': self.id,
            'trade': self._trade_type,  # self.trade_type_to_str(),
            'entry-timeout': self._entry_timeout,  # self.timeframe_to_str(self._entry_timeout),
            'expiry': self._expiry,
            'entry-state': self._entry_state,  # self.trade_state_to_str(self._entry_state),
            'exit-state': self._exit_state,  # self.trade_state_to_str(self._exit_state),
            'closing': self._closing,
            'timeframe': self._timeframe,  # self.timeframe_to_str(),
            'user-trade': self._user_trade,
            'label': self._label,
            'avg-entry-price': self.aep,
            'avg-exit-price': self.axp,
            'take-profit-price': self.tp,
            'stop-loss-price': self.sl,
            'direction': self.dir,  # self.direction_to_str(),
            'entry-open-time': self.eot,  # self.dump_timestamp(self.eot),
            'exit-open-time': self.xot,  # self.dump_timestamp(self.xot),
            'order-price': self.op,
            'order-qty': self.oq,
            'filled-entry-qty': self.e,
            'filled-exit-qty': self.x,
            'profit-loss-rate': self.pl,
            'exit-trades': self.exit_trades,
            'last-take-profit-order-time': self.last_tp_ot,
            'last-stop-loss-order-time': self.last_stop_ot,
            'statistics': self._stats,
            'context': self.context.dumps() if self.context else None,
            'comment': self._comment,
            'extra': self._extra,
        }

    def loads(self, data: dict, strategy_trader: StrategyTrader,
              context_builder: Optional[StrategyTraderContextBuilder] = None) -> bool:
        """
        Override this method to make a loads for the persistence model.
        @return True if success.
        @note Data Must not be humanized.
        """
        self.id = data.get('id', -1)
        self._trade_type = data.get('', 0)  # self.trade_type_from_str(data.get('type', ''))
        self._entry_timeout = data.get('entry-timeout', 0)
        self._expiry = data.get('expiry', 0)
        self._entry_state = data.get('entry-state', 0)  # self.trade_state_from_str(data.get('entry-state', ''))
        self._exit_state = data.get('exit-state', 0)  # self.trade_state_from_str(data.get('exit-state', ''))
        self._closing = data.get('closing', False)
        self._timeframe = data.get('timeframe', 0)  # timeframe_from_str(data.get('timeframe', '4h'))
        self._user_trade = data.get('user-trade')
        self._label = data.get('label', "")

        self._operations = []
        self._next_operation_id = -1

        self.dir = data.get('direction', 0)  # self.direction_from_str(data.get('direction', ''))
        self.op = data.get('order-price', 0.0)
        self.oq = data.get('order-qty', 0.0)

        self.tp = data.get('take-profit-price', 0.0)
        self.sl = data.get('stop-loss-price', 0.0)

        self.aep = data.get('avg-entry-price', 0.0)
        self.axp = data.get('avg-exit-price', 0.0)

        self.eot = data.get('entry-open-time', 0)  # self.load_timestamp(data.get('entry-open-datetime'))
        self.xot = data.get('exit-open-time', 0)  # self.load_timestamp(data.get('exit-open-datetime'))

        self.e = data.get('filled-entry-qty', 0.0)
        self.x = data.get('filled-exit-qty', 0.0)

        self.pl = data.get('profit-loss-rate', 0.0)

        self.last_tp_ot = data.get('last-take-profit-order-time')
        self.last_stop_ot = data.get('last-stop-loss-order-time')

        self.exit_trades = data.get('exit-trades', {})

        self._stats = data.get('statistics', {
            'best-price': 0.0,
            'best-timestamp': 0.0,
            'worst-price': 0.0,
            'worst-timestamp': 0.0,
            'entry-order-type': Order.ORDER_LIMIT,
            'take-profit-order-type': Order.ORDER_LIMIT,
            'stop-order-type': Order.ORDER_MARKET,
            'first-realized-entry-timestamp': 0.0,
            'first-realized-exit-timestamp': 0.0,
            'last-realized-entry-timestamp': 0.0,
            'last-realized-exit-timestamp': 0.0,
            'unrealized-profit-loss': 0.0,
            'profit-loss-currency': "",
            'exit-reason': StrategyTrade.REASON_NONE,
            'entry-fees': 0.0,
            'exit-fees': 0.0,
            'conditions': {}
        })

        self._comment = data.get('comment', "")
        self._extra = data.get('extra', {})

        if context_builder and data.get('context'):
            self.context = context_builder.loads(data['context'], strategy_trader)
        else:
            self.context = None

        return True

    def check(self, trader: Trader, instrument: Instrument) -> int:
        """
        Check orders and positions exists and quantities too.
        @return 1 if success, 0 if need repair, -1 if error.
        """
        return 1

    def repair(self, trader: Trader, instrument: Instrument) -> bool:
        """
        Try to repair a trade with an error during retrieving some of its parts (orders, quantity, position).
        @return True if success.
        """
        return False

    #
    # stats
    #

    def update_stats(self, instrument: Instrument, timestamp: float) :
        if self.is_active():
            last_price = instrument.close_exec_price(self.direction)

            if self.dir > 0:
                if last_price > self._stats['best-price']:
                    self._stats['best-price'] = last_price
                    self._stats['best-timestamp'] = timestamp

                if last_price < self._stats['worst-price'] or not self._stats['worst-price']:
                    self._stats['worst-price'] = last_price
                    self._stats['worst-timestamp'] = timestamp

            elif self.dir < 0:
                if last_price < self._stats['best-price'] or not self._stats['best-price']:
                    self._stats['best-price'] = last_price
                    self._stats['best-timestamp'] = timestamp

                if last_price > self._stats['worst-price']:
                    self._stats['worst-price'] = last_price
                    self._stats['worst-timestamp'] = timestamp

    def best_price(self) -> float:
        return self._stats['best-price']

    def worst_price(self) -> float:
        return self._stats['worst-price']

    def best_price_timestamp(self) -> float:
        return self._stats['best-timestamp']

    def worst_price_timestamp(self) -> float:
        return self._stats['worst-timestamp']

    def get_stats(self) -> dict:
        return self._stats

    def add_condition(self, name: str, data):
        self._stats['conditions'][name] = data

    def get_conditions(self):
        return self._stats['conditions']

    def entry_fees(self) -> float:
        """Realized entry fees cost (not rate)"""
        return self._stats['entry-fees']

    def entry_fees_rate(self) -> float:
        """Realized entry fees rate"""
        if self.e > 0 and self.aep > 0:
            return self._stats['entry-fees'] / (self.aep * self.e)

        return 0.0

    def exit_fees(self) -> float:
        """Realized exit fees cost (not rate)"""
        return self._stats['exit-fees']

    def exit_fees_rate(self) -> float:
        """Realized entry fees rate"""
        if self.x > 0 and self.axp > 0:
            return self._stats['exit-fees'] / (self.axp * self.x)

        return 0.0

    def profit_loss_delta(self, instrument: Instrument) -> float:
        """
        During the trade open, compute an estimation of the unrealized profit/loss delta in price.
        """
        # if no entry realised
        if self.e <= 0.0:
            return 0.0

        # estimation at close price
        close_exec_price = instrument.close_exec_price(self.direction)

        # no current price update
        if not close_exec_price:
            return 0.0

        if self.direction > 0 and self.entry_price > 0:
            return close_exec_price - self.entry_price
        elif self.direction < 0 and self.entry_price > 0:
            return self.entry_price - close_exec_price
        else:
            return 0.0

    def estimate_take_profit(self, instrument: Instrument) -> float:
        """
        Estimated take-profit rate.
        """
        # if no entry realised
        if self.e <= 0.0:
            return 0.0

        if self.direction > 0 and self.entry_price > 0:
            profit_loss = (self.tp - self.entry_price) / self.entry_price
        elif self.direction < 0 and self.entry_price > 0:
            profit_loss = (self.entry_price - self.tp) / self.entry_price
        else:
            profit_loss = 0.0

        # minus realized entry fees rate
        profit_loss -= self.entry_fees_rate()

        # and estimation of the exit fees rate
        profit_loss -= self.estimate_exit_fees_rate(instrument)

        return profit_loss

    def estimate_stop_loss(self, instrument: Instrument) -> float:
        """
        Estimated stop-loss rate.
        """
        # if no entry realised
        if self.e <= 0.0:
            return 0.0

        if self.direction > 0 and self.entry_price > 0:
            profit_loss = (self.entry_price - self.sl) / self.entry_price
        elif self.direction < 0 and self.entry_price > 0:
            profit_loss = (self.sl - self.entry_price) / self.entry_price
        else:
            profit_loss = 0.0

        # minus realized entry fees rate
        profit_loss -= self.entry_fees_rate()

        # and estimation of the exit fees rate
        profit_loss -= self.estimate_exit_fees_rate(instrument)

        return profit_loss

    def estimate_profit_loss(self, instrument: Instrument) -> float:
        """
        During the trade open, compute an estimation of the unrealized profit/loss rate.
        """
        # if no entry realised
        if self.e <= 0.0:
            return 0.0

        # estimation at close price
        close_exec_price = instrument.close_exec_price(self.direction)

        # no current price update
        if not close_exec_price:
            return 0.0

        if self.direction > 0 and self.entry_price > 0:
            profit_loss = (close_exec_price - self.entry_price) / self.entry_price
        elif self.direction < 0 and self.entry_price > 0:
            profit_loss = (self.entry_price - close_exec_price) / self.entry_price
        else:
            profit_loss = 0.0

        # minus realized entry fees rate
        profit_loss -= self.entry_fees_rate()

        # and estimation of the exit fees rate
        profit_loss -= self.estimate_exit_fees_rate(instrument)

        return profit_loss

    def estimate_exit_fees_rate(self, instrument: Instrument) -> float:
        """
        Return the estimate fees rate for the exit order.
        """
        # count the exit fees related to limit order type
        if self._stats['take-profit-order-type'] in (Order.ORDER_LIMIT, Order.ORDER_STOP_LIMIT,
                                                     Order.ORDER_TAKE_PROFIT_LIMIT):
            return instrument.maker_fee

        elif self._stats['take-profit-order-type'] in (Order.ORDER_MARKET, Order.ORDER_STOP,
                                                       Order.ORDER_TAKE_PROFIT):
            return instrument.taker_fee

        return 0.0

    #
    # extra
    #

    def set(self, key: str, value):
        """
        Add a key:value pair in the extra member dict of the trade.
        It allow to add you internal trade data, states you want to keep during the live of the trade and even in
        persistence.
        """
        self._extra[key] = value

    def unset(self, key: str):
        """Remove a previously set extra key"""
        if key in self._extra:
            del self._extra[key]

    def get(self, key: str, default=None):
        """Return a value for a previously defined key or default value if not exists"""
        return self._extra.get(key, default)

    #
    # operations
    #

    @property
    def operations(self) -> List[TradeOp]:
        """
        List all pending/persistent operations
        """
        return self._operations

    def cleanup_operations(self):
        """
        Regenerate the list of operations by removing the finished operations.
        """
        ops = []

        for operation in self._operations:
            if not operation.can_delete():
                ops.append(operation)

        # replace the operations list
        self._operations = ops

    def add_operation(self, trade_operation: TradeOp):
        trade_operation.set_id(self._next_operation_id)
        self._next_operation_id += 1

        self._operations.append(trade_operation)

    def remove_operation(self, trade_operation_id: int) -> bool:
        for operation in self._operations:
            if operation.id == trade_operation_id:
                self._operations.remove(operation)
                return True

        return False

    def has_operations(self) -> bool:
        return len(self._operations) > 0

    #
    # dumps for notify/history
    #

    def dumps_notify_entry(self, timestamp: float, strategy_trader: StrategyTrader) -> dict:
        """
        Dumps to dict for stream/notify/history.
        @note Data are humanized.
        """
        return {
            'version': self.version(),
            'trade': self.trade_type_to_str(),
            'id': self.id,
            'app-name': strategy_trader.strategy.name,
            'app-id': strategy_trader.strategy.identifier,
            'timestamp': timestamp,
            'market-id': strategy_trader.instrument.market_id,
            'symbol': strategy_trader.instrument.symbol,
            'alias': strategy_trader.instrument.alias,
            'way': "entry",
            'entry-timeout': timeframe_to_str(self._entry_timeout),
            'expiry': self._expiry,
            'timeframe': timeframe_to_str(self._timeframe),
            'is-user-trade': self._user_trade,
            'label': self._label,
            'direction': self.direction_to_str(),
            'state': self.state_to_str(),
            'order-price': strategy_trader.instrument.format_price(self.op),
            'order-qty': strategy_trader.instrument.format_quantity(self.oq),
            'stop-loss-price': strategy_trader.instrument.format_price(self.sl),
            'take-profit-price': strategy_trader.instrument.format_price(self.tp),
            'avg-entry-price': strategy_trader.instrument.format_price(self.aep),
            'filled-entry-qty': strategy_trader.instrument.format_quantity(self.e),
            'entry-open-time': self.dump_timestamp(self.eot),
            'comment': self._comment,
            'stats': {
                'entry-order-type': order_type_to_str(self._stats['entry-order-type']),
                'close-exec-price': strategy_trader.instrument.format_price(
                    strategy_trader.instrument.close_exec_price(self.dir)),
            }
        }

    def dumps_notify_exit(self, timestamp: float, strategy_trader: StrategyTrader) -> dict:
        """
        Dumps to dict for stream/notify/history.
        @note Data are humanized.
        """
        return {
            'version': self.version(),
            'trade': self.trade_type_to_str(),
            'id': self.id,
            'app-name': strategy_trader.strategy.name,
            'app-id': strategy_trader.strategy.identifier,
            'timestamp': timestamp,
            'market-id': strategy_trader.instrument.market_id,
            'symbol': strategy_trader.instrument.symbol,
            'alias': strategy_trader.instrument.alias,
            'way': "exit",
            'entry-timeout': timeframe_to_str(self._entry_timeout),
            'expiry': self._expiry,
            'timeframe': timeframe_to_str(self._timeframe),
            'is-user-trade': self._user_trade,
            'label': self._label,
            'direction': self.direction_to_str(),
            'state': self.state_to_str(),
            'order-price': strategy_trader.instrument.format_price(self.op),
            'order-qty': strategy_trader.instrument.format_quantity(self.oq),
            'stop-loss-price': strategy_trader.instrument.format_price(self.sl),
            'take-profit-price': strategy_trader.instrument.format_price(self.tp),
            'avg-entry-price': strategy_trader.instrument.format_price(self.aep),
            'avg-exit-price': strategy_trader.instrument.format_price(self.axp),
            'entry-open-time': self.dump_timestamp(self.eot),
            'exit-open-time': self.dump_timestamp(self.xot),
            'filled-entry-qty': strategy_trader.instrument.format_quantity(self.e),
            'filled-exit-qty': strategy_trader.instrument.format_quantity(self.x),
            # minus fees
            'profit-loss-pct': round((self.pl - self.entry_fees_rate() - self.exit_fees_rate()) * 100.0, 2),
            'num-exit-trades': len(self.exit_trades),
            'comment': self._comment,
            'stats': {
                'best-price': strategy_trader.instrument.format_price(self._stats['best-price']),
                'best-datetime': self.dump_timestamp(self._stats['best-timestamp']),
                'worst-price': strategy_trader.instrument.format_price(self._stats['worst-price']),
                'worst-datetime': self.dump_timestamp(self._stats['worst-timestamp']),
                'entry-order-type': order_type_to_str(self._stats['entry-order-type']),
                'first-realized-entry-datetime': self.dump_timestamp(self._stats['first-realized-entry-timestamp']),
                'first-realized-exit-datetime': self.dump_timestamp(self._stats['first-realized-exit-timestamp']),
                'last-realized-entry-datetime': self.dump_timestamp(self._stats['last-realized-entry-timestamp']),
                'last-realized-exit-datetime': self.dump_timestamp(self._stats['last-realized-exit-timestamp']),
                'profit-loss-currency': self._stats['profit-loss-currency'],
                'profit-loss': self._stats['unrealized-profit-loss'],  # use the last computed or updated
                'entry-fees': self._stats['entry-fees'],
                'exit-fees': self._stats['exit-fees'],
                'fees-pct': round((self.entry_fees_rate() + self.exit_fees_rate()) * 100.0, 2),
                'exit-reason': StrategyTrade.reason_to_str(self._stats['exit-reason']),
                'close-exec-price': strategy_trader.instrument.format_price(
                    strategy_trader.instrument.close_exec_price(self.dir)),
            }
        }

    def dumps_notify_update(self, timestamp: float, strategy_trader: StrategyTrader) -> dict:
        """
        Dumps to dict for stream/notify/history.
        @note Data are humanized.
        """
        return {
            'version': self.version(),
            'trade': self.trade_type_to_str(),
            'id': self.id,
            'app-name': strategy_trader.strategy.name,
            'app-id': strategy_trader.strategy.identifier,
            'timestamp': timestamp,
            'market-id': strategy_trader.instrument.market_id,
            'symbol': strategy_trader.instrument.symbol,
            'alias': strategy_trader.instrument.alias,
            'way': "update",
            'entry-timeout': timeframe_to_str(self._entry_timeout),
            'expiry': self._expiry,
            'timeframe': timeframe_to_str(self._timeframe),
            'is-user-trade': self._user_trade,
            'label': self._label,
            'direction': self.direction_to_str(),
            'state': self.state_to_str(),
            'order-price': strategy_trader.instrument.format_price(self.op),
            'order-qty': strategy_trader.instrument.format_quantity(self.oq),
            'stop-loss-price': strategy_trader.instrument.format_price(self.sl),
            'take-profit-price': strategy_trader.instrument.format_price(self.tp),
            'avg-entry-price': strategy_trader.instrument.format_price(self.aep),
            'avg-exit-price': strategy_trader.instrument.format_price(self.axp),
            'entry-open-time': self.dump_timestamp(self.eot),
            'exit-open-time': self.dump_timestamp(self.xot),
            'filled-entry-qty': strategy_trader.instrument.format_quantity(self.e),
            'filled-exit-qty': strategy_trader.instrument.format_quantity(self.x),
            'profit-loss-pct': round(self.estimate_profit_loss(strategy_trader.instrument) * 100.0, 2),
            'num-exit-trades': len(self.exit_trades),
            'comment': self._comment,
            'stats': {
                'best-price': strategy_trader.instrument.format_price(self._stats['best-price']),
                'best-datetime': self.dump_timestamp(self._stats['best-timestamp']),
                'worst-price': strategy_trader.instrument.format_price(self._stats['worst-price']),
                'worst-datetime': self.dump_timestamp(self._stats['worst-timestamp']),
                'entry-order-type': order_type_to_str(self._stats['entry-order-type']),
                'first-realized-entry-datetime': self.dump_timestamp(self._stats['first-realized-entry-timestamp']),
                'first-realized-exit-datetime': self.dump_timestamp(self._stats['first-realized-exit-timestamp']),
                'last-realized-entry-datetime': self.dump_timestamp(self._stats['last-realized-entry-timestamp']),
                'last-realized-exit-datetime': self.dump_timestamp(self._stats['last-realized-exit-timestamp']),
                'profit-loss-currency': self._stats['profit-loss-currency'],
                'profit-loss': self._stats['unrealized-profit-loss'],
                'entry-fees': self._stats['entry-fees'],
                'exit-fees': self._stats['exit-fees'],
                'fees-pct': round((self.entry_fees_rate() + self.exit_fees_rate()) * 100.0, 2),
                'exit-reason': StrategyTrade.reason_to_str(self._stats['exit-reason']),
                'close-exec-price': strategy_trader.instrument.format_price(
                    strategy_trader.instrument.close_exec_price(self.dir)),
            }
        }

    def info_report(self, strategy_trader: StrategyTrader) -> Tuple[str]:
        """
        @todo leverage for phrase command
        """
        entry_phrase = [self.direction_to_str(), strategy_trader.instrument.symbol]
        assign_phrase = [strategy_trader.instrument.symbol, self.direction_to_str()]

        if self.op:
            if self._stats['entry-order-type'] == Order.ORDER_LIMIT:
                entry_phrase.append("L@%s" % strategy_trader.instrument.format_price(self.op))
                assign_phrase.append("limit EP@%s" % strategy_trader.instrument.format_price(self.aep or self.op))

            elif self._stats['entry-order-type'] == Order.ORDER_MARKET:
                assign_phrase.append("market EP@%s" % strategy_trader.instrument.format_price(self.aep))

            elif self._stats['entry-order-type'] == Order.ORDER_STOP:
                # @todo with trigger command
                entry_phrase.append("T@%s" % strategy_trader.instrument.format_price(self.op))
                assign_phrase.append("trigger EP@%s" % strategy_trader.instrument.format_price(self.aep or self.op))

        if self.sl:
            v = "SL@%s" % strategy_trader.instrument.format_price(self.sl)
            entry_phrase.append(v)
            assign_phrase.append(v)

        if self.tp:
            v = "TP@%s" % strategy_trader.instrument.format_price(self.tp)
            entry_phrase.append(v)
            assign_phrase.append(v)

        if self._timeframe:
            v = "'%s" % timeframe_to_str(self._timeframe)
            entry_phrase.append(v)
            assign_phrase.append(v)

        if self._label:
            v = "-%s" % self._label
            entry_phrase.append(v)
            assign_phrase.append(v)

        if self._entry_timeout:
            v = "/%s" % self._entry_timeout
            entry_phrase.append(v)
            # assign_phrase.append(v)

        if self._expiry:
            v = "+%s" % self._expiry
            entry_phrase.append(v)
            assign_phrase.append(v)

        quantity_rate = 1.0

        if strategy_trader.instrument.trade_quantity > 0.0:
            quantity_rate = round(self.invested_quantity / strategy_trader.instrument.trade_quantity, 2)

        if quantity_rate != 1.0:
            entry_phrase.append("*%g" % quantity_rate)

        assign_phrase.append(strategy_trader.instrument.format_quantity(self.e or self.oq))

        msg1 = "Trade info - %s - id %s - on %s. Opened %s." % (
                    self.trade_type_to_str(),
                    self.id,
                    strategy_trader.instrument.symbol,
                    datetime.fromtimestamp(self.eot).strftime('%Y-%m-%d %H:%M:%S'))

        msg2 = "Timeframe %s, Label %s, Entry timeout %s, Expiry %s, %s, Status %s." % (
                    timeframe_to_str(self._timeframe),
                    self._label,
                    timeframe_to_str(self._entry_timeout),
                    self._expiry or "Never",
                    "Manual-Trade" if self._user_trade else "Auto-Trade", self.state_to_str())

        data = [msg1, msg2]

        if self._comment:
            data.append("Comment: %s" % self._comment)

        # 'avg-entry-price' 'avg-exit-price' 'entry-open-time' 'exit-open-time'
        # 'filled-entry-qty' 'filled-exit-qty' 'profit-loss-pct' 'num-exit-trades'

        data.extend((
            "-----",
            "- %s" % ' '.join(entry_phrase),
            "- assign %s" % ' '.join(assign_phrase),
            "- close %s %s" % (strategy_trader.instrument.symbol, self.id),
            "- clean-trade %s %s" % (strategy_trader.instrument.symbol, self.id),
            "-----",
            # specialize for add row with detail such as orders or positions ids
        ))

        return tuple(data)
