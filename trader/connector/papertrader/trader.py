# @date 2018-09-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Generic paper trader.

from __future__ import annotations

from typing import TYPE_CHECKING, List, Union, Optional

if TYPE_CHECKING:
    from trader.service import TraderService
    from trader.market import Market
    from instrument.instrument import Instrument

import base64
import copy
import json
import time
import uuid

from datetime import datetime

from common.signal import Signal

from trader.trader import Trader

from .account import PaperTraderAccount

from trader.asset import Asset
from trader.order import Order
from trader.position import Position

from .papertraderindmargin import exec_indmargin_order
from .papertradermargin import exec_margin_order
from .papertraderposition import close_position
from .papertraderspot import exec_buysell_order

import logging
logger = logging.getLogger('siis.trader.paper')
error_logger = logging.getLogger('siis.error.paper')
traceback_logger = logging.getLogger('siis.traceback.trade.paper')


class PaperTrader(Trader):
    """
    Only for simulation paper trader.
    In backtesting market data are set manually using method set_market(...).

    @todo Simulation of a pseudo-random slippage.
    """

    def __init__(self, service: TraderService, name: str = "papertrader.siis"):
        super().__init__(name, service)

        self._slippage = 0  # slippage in ticks (not supported for now)

        self._watcher = None  # in backtesting refers to a dummy watcher
        self._unlimited = False

        self._closed_orders = {}  # history of closed or canceled orders

        trader_config = service.trader_config()
        paper_mode = trader_config.get('paper-mode')
        if paper_mode:
            self._unlimited = paper_mode.get("unlimited", False)

        self._account = PaperTraderAccount(self)

    @property
    def paper_mode(self) -> bool:
        return True

    @property
    def authenticated(self) -> bool:
        # always authenticated in paper-mode
        return True

    @property
    def connected(self) -> bool:
        if self.service.backtesting:
            # always connected in backtesting
            return True
        else:
            return self._watcher is not None and self._watcher.connector is not None and self._watcher.connector.connected

    def connect(self):
        super().connect()

        if self.service.backtesting:
            # no connection when backtesting
            return

        # retrieve the pair watcher and take its connector
        with self._mutex:
            self._watcher = self.service.watcher_service.watcher(self._name)

            if self._watcher:
                self.service.watcher_service.add_listener(self)

        if self._watcher and self._watcher.connected:
            self.on_watcher_connected(self._watcher.name)   

    def disconnect(self):
        super().disconnect()

        with self._mutex:
            if self._watcher:
                self.service.watcher_service.remove_listener(self)
                self._watcher = None

    def on_watcher_connected(self, watcher_name: str):
        super().on_watcher_connected(watcher_name)

        logger.info("Paper trader %s retrieving data..." % self._name)

        # insert the assets
        # @todo

        logger.info("Paper trader %s data retrieved." % self._name)

    def on_watcher_disconnected(self, watcher_name: str):
        super().on_watcher_disconnected(watcher_name)

    def has_margin(self, market_id: str, quantity: float, price: float) -> bool:
        """
        Return True for a margin trading if the account have sufficient free margin.
        """
        if self._unlimited:
            return True

        margin = None

        with self._mutex:
            market = self._markets.get(market_id)
            margin = market.margin_cost(quantity, price)

        return margin is not None and self.account.margin_balance >= margin

    def has_quantity(self, asset_name: str, quantity: float) -> bool:
        """
        Return True if a given asset has a minimum quantity.
        @note The benefit of this method is it can be overloaded and offers a generic way for a strategy
            to check if an order can be created
        """
        if self._unlimited:
            return True

        result = False

        with self._mutex:
            asset = self._assets.get(asset_name)
            result = asset and asset.free >= quantity

        return result

    def market(self, market_id: str, force: bool = False) -> Union[Market, None]:
        """
        Fetch from the watcher and cache it. It rarely changes so assume it once per connection.
        @param market_id Unique market identifier
        @param force Force to update the cache
        """
        with self._mutex:
            market = self._markets.get(market_id)

        if (market is None or force) and self._watcher is not None and self._watcher.connected:
            try:
                market = self._watcher.fetch_market(market_id)
            except Exception as e:
                logger.error("fetch_market: %s" % repr(e))
                return None

            if market:
                with self._mutex:
                    self._markets[market_id] = market

        return market

    def post_update(self):
        super().post_update()

        # don't wast the CPU 5 ms loop, and this will simulate at least a 5ms slippage
        # for limits order execution in paper-mode
        if not self.service.backtesting:
            time.sleep(0.0001)
        time.sleep(0.005)

    @property
    def timestamp(self) -> float:
        """
        Current real time or last timestamp in backtesting
        """
        if self.service.backtesting:
            return self._timestamp
        else:
            return time.time()

    def update(self):
        """
        This update its called synchronously by strategy update during the backtesting or threaded in live mode.
        """
        super().update()

        #
        # update positions (margin trading)
        #

        if self._positions:
            rm_list = []

            with self._mutex:
                for k, position in self._positions.items():
                    # remove empty and closed positions
                    if position.quantity <= 0.0:
                        rm_list.append(k)
                    else:
                        market = self._markets.get(position.symbol)
                        if market:
                            # managed position take-profit and stop-loss
                            if market.has_position and (position.take_profit or position.stop_loss):
                                open_exec_price = market.close_exec_price(position.direction)
                                close_exec_price = market.close_exec_price(position.direction)

                                order_type = None

                                if position.direction > 0:
                                    if position.take_profit and close_exec_price >= position.take_profit:
                                        order_type = Order.ORDER_LIMIT

                                    elif position.stop_loss and close_exec_price <= position.stop_loss:
                                        order_type = Order.ORDER_MARKET

                                elif position.direction < 0:
                                    if position.take_profit and close_exec_price <= position.take_profit:
                                        order_type = Order.ORDER_LIMIT

                                    elif position.stop_loss and close_exec_price >= position.stop_loss:
                                        order_type = Order.ORDER_MARKET

                                if order_type is not None:
                                    if close_position(self, market, position, close_exec_price, order_type):
                                        rm_list.append(k)

                for rm in rm_list:
                    # remove empty positions
                    del self._positions[rm]

        #
        # update account balance and margin
        #

        if not self._unlimited:
            with self._mutex:
                self._account.update(None)

            if self._account.account_type & PaperTraderAccount.TYPE_MARGIN == PaperTraderAccount.TYPE_MARGIN:
                # support margin
                used_margin = 0.0
                used_cost = 0.0
                profit_loss = 0.0

                with self._mutex:
                    # dynamic balance over profit/loss
                    self.account.use_balance(self.account.profit_loss)

                    for k, position in self._positions.items():
                        market = self._markets.get(position.symbol)

                        # only for non-empty positions
                        if market and position.quantity > 0.0:
                            # manually compute here because of paper trader
                            profit_loss += position.raw_profit_loss / market.base_exchange_rate
                            used_margin += position.margin_cost(market) / market.base_exchange_rate
                            used_cost += position.position_cost(market) / market.base_exchange_rate

                    self.account.set_used_margin(used_margin-profit_loss)
                    self.account.set_unrealized_profit_loss(profit_loss)

                    # dynamic balance over profit/loss
                    self.account.use_balance(-self.account.profit_loss)
                    self.account.set_net_worth(self.account.balance)

                    # risk limit (no reality on paper)
                    # risk_limit =
                    # self.account.set_risk_limit(risk_limit)

                    # margin level
                    used_cost += self.account.profit_loss
                    if used_cost > 0.0:
                        self.account.set_margin_level(self.account.margin_balance / used_cost)
                    else:
                        self.account.set_margin_level(0.0)

            if self._account.account_type & PaperTraderAccount.TYPE_ASSET == PaperTraderAccount.TYPE_ASSET:
                # support spot
                balance = 0.0
                free_balance = 0.0
                profit_loss = 0.0

                with self._mutex:
                    for k, asset in self._assets.items():
                        asset_name = asset.symbol
                        free = asset.free
                        locked = asset.locked

                        if free or locked:
                            # found the last market price
                            if asset.quote:
                                price = 0.0
                                base_exchange_rate = 1.0

                                if asset.symbol == self._account.currency:
                                    # as primary currency
                                    price = 1.0
                                    base_exchange_rate = 1.0
                                else:
                                    # from a know market
                                    market_id = asset.market_ids[0] if asset.market_ids else asset_name+asset.quote
                                    market = self._markets.get(market_id)
                                    if market:
                                        price = market.price / market.base_exchange_rate
                                        base_exchange_rate = market.base_exchange_rate

                                if price:
                                    balance += free * price + locked * price  # current total free+locked balance
                                    free_balance += free * price              # current total free balance

                                    # current total P/L in primary account currency
                                    profit_loss += asset.raw_profit_loss / base_exchange_rate

                    self.account.set_asset_balance(balance, free_balance)
                    self.account.set_unrealized_asset_profit_loss(profit_loss)
        else:
            with self._mutex:
                # not updated uPNL then always reset            
                if self._account.account_type & PaperTraderAccount.TYPE_MARGIN:
                    self.account.set_unrealized_profit_loss(0.0)

                if self._account.account_type & PaperTraderAccount.TYPE_ASSET:
                    self.account.set_unrealized_asset_profit_loss(0.0)

        #
        # limit/trigger orders executions
        #
        if self._orders:
            rm_list = []

            with self._mutex:
                orders = list(self._orders.values())

            for order in orders:
                market = self._markets.get(order.symbol)
                if market is None:
                    # unsupported market
                    rm_list.append(order.order_id)
                    continue

                # slippage emulation
                # @todo deferred execution, could make a rand delay around the slippage factor

                # open long are executed on bid and short on ask, close the inverse
                if order.direction == Position.LONG:
                    open_exec_price = market.ask
                    close_exec_price = market.bid
                elif order.direction == Position.SHORT:
                    open_exec_price = market.bid
                    close_exec_price = market.ask
                else:
                    # unsupported direction
                    rm_list.append(order.order_id)
                    continue

                if order.order_type == Order.ORDER_MARKET:
                    # market
                    # does not support the really offered qty, take all at current price in one shot
                    if order.margin_trade and market.has_margin:
                        if market.indivisible_position:
                            # use order price because could have non realistic spread/slippage
                            # exec_indmargin_order(self, order, market, open_exec_price, close_exec_price)
                            exec_indmargin_order(self, order, market, order.price, order.price)
                        else:
                            # use order price because could have non realistic spread/slippage
                            # exec_margin_order(self, order, market, open_exec_price, close_exec_price)
                            exec_margin_order(self, order, market, order.price, order.price)
                    elif not order.margin_trade and market.has_spot:
                        # use order price because could have non realistic spread/slippage
                        # exec_buysell_order(self, order, market, open_exec_price, close_exec_price)
                        exec_buysell_order(self, order, market, order.price, order.price)

                    # fully executed
                    rm_list.append(order.order_id)

                elif order.order_type == Order.ORDER_LIMIT:
                    # limit
                    if ((order.direction == Position.LONG and open_exec_price <= order.price) or
                            (order.direction == Position.SHORT and open_exec_price >= order.price)):

                        # does not support the really offered qty, take all at current price in one shot
                        if order.margin_trade and market.has_margin:
                            if market.indivisible_position:
                                exec_indmargin_order(self, order, market, open_exec_price, close_exec_price)
                            else:
                                exec_margin_order(self, order, market, open_exec_price, close_exec_price)
                        elif not order.margin_trade and market.has_spot:
                            exec_buysell_order(self, order, market, open_exec_price, close_exec_price)

                        # fully executed
                        rm_list.append(order.order_id)

                elif order.order_type == Order.ORDER_STOP:
                    # trigger + market
                    if ((order.direction == Position.LONG and close_exec_price >= order.stop_price) or
                            (order.direction == Position.SHORT and close_exec_price <= order.stop_price)):

                        if order.margin_trade and market.has_margin:
                            if market.indivisible_position:
                                # use order price because could have non realistic spread/slippage
                                # exec_indmargin_order(self, order, market, open_exec_price, close_exec_price)
                                exec_indmargin_order(self, order, market, order.stop_price, order.stop_price)
                            else:
                                exec_margin_order(self, order, market, open_exec_price, close_exec_price)
                        elif not order.margin_trade and market.has_spot:
                            # use order price because could have non realistic spread/slippage
                            # exec_buysell_order(self, order, market, open_exec_price, close_exec_price)
                            exec_buysell_order(self, order, market, order.price, order.price)

                        # fully executed
                        rm_list.append(order.order_id)

                elif order.order_type == Order.ORDER_STOP_LIMIT:
                    # trigger + limit
                    if ((order.direction == Position.LONG and close_exec_price >= order.stop_price) or
                            (order.direction == Position.SHORT and close_exec_price <= order.stop_price)):

                        # limit
                        if order.direction == Position.LONG:
                            open_exec_price = min(order.price, open_exec_price)
                            close_exec_price = min(order.price, close_exec_price)
                        elif order.direction == Position.SHORT:
                            open_exec_price = max(order.price, open_exec_price)
                            close_exec_price = max(order.price, close_exec_price)

                        # does not support the really offered qty, take all at current price in one shot
                        if order.margin_trade and market.has_margin:
                            if market.indivisible_position:
                                exec_indmargin_order(self, order, market, open_exec_price, close_exec_price)
                            else:
                                exec_margin_order(self, order, market, open_exec_price, close_exec_price)
                        elif not order.margin_trade and market.has_spot:
                            exec_buysell_order(self, order, market, open_exec_price, close_exec_price)

                    # fully executed
                    rm_list.append(order.order_id)

                elif order.order_type == Order.ORDER_TAKE_PROFIT:
                    # opposite trigger + market
                    if ((order.direction == Position.LONG and close_exec_price <= order.stop_price) or
                            (order.direction == Position.SHORT and close_exec_price >= order.stop_price)):

                        if order.margin_trade and market.has_margin:
                            if market.indivisible_position:
                                exec_indmargin_order(self, order, market, open_exec_price, close_exec_price)
                            else:
                                exec_margin_order(self, order, market, open_exec_price, close_exec_price)
                        elif not order.margin_trade and market.has_spot:
                            exec_buysell_order(self, order, market, open_exec_price, close_exec_price)

                    # fully executed
                    rm_list.append(order.order_id)

                elif order.order_type == Order.ORDER_TAKE_PROFIT_LIMIT:
                    # opposite trigger + limit
                    if ((order.direction == Position.LONG and close_exec_price <= order.stop_price) or
                            (order.direction == Position.SHORT and close_exec_price >= order.stop_price)):

                        # limit
                        if order.direction == Position.LONG:
                            open_exec_price = min(order.price, open_exec_price)
                            close_exec_price = min(order.price, close_exec_price)
                        elif order.direction == Position.SHORT:
                            open_exec_price = max(order.price, open_exec_price)
                            close_exec_price = max(order.price, close_exec_price)

                        # does not support the really offered qty, take all at current price in one shot
                        if order.margin_trade and market.has_margin:
                            if market.indivisible_position:
                                exec_indmargin_order(self, order, market, open_exec_price, close_exec_price)
                            else:
                                exec_margin_order(self, order, market, open_exec_price, close_exec_price)
                        elif not order.margin_trade and market.has_spot:
                            exec_buysell_order(self, order, market, open_exec_price, close_exec_price)

                    # fully executed
                    rm_list.append(order.order_id)

            with self._mutex:
                for rm in rm_list:
                    # remove fully executed orders
                    if rm in self._orders:
                        del self._orders[rm]
                        # self._closed_orders[rm.order_id] = rm  # keep for history

    def post_run(self):
        super().post_run()

    def create_asset(self, asset_name, quantity, price, quote, precision=8):
        asset = Asset(self, asset_name, precision)
        asset.set_quantity(0, quantity)
        asset.update_price(datetime.now().timestamp(), 0, price, quote)

        with self._mutex:
            self._assets[asset_name] = asset

    #
    # ordering
    #

    def create_order(self, order: Order, market_or_instrument: Union[Market, Instrument]) -> int:
        if not order or not market_or_instrument:
            return Order.REASON_INVALID_ARGS

        trader_market = self._markets.get(market_or_instrument.market_id)
        if not trader_market:
            error_logger.error("Trader %s refuse order because the market %s is not found" % (
                self.name, market_or_instrument.market_id))
            return Order.REASON_INVALID_ARGS

        if (trader_market.min_size > 0.0) and (order.quantity < trader_market.min_size):
            # reject if lesser than min size
            logger.error("Trader %s refuse order because the min size is not reached (%s<%s) %s in ref order %s" % (
                self.name, order.quantity, trader_market.min_size, order.symbol, order.ref_order_id))
            return Order.REASON_INVALID_ARGS

        #
        # price according to order type
        #

        bid_price = 0
        ask_price = 0

        if order.order_type in (Order.ORDER_LIMIT, Order.ORDER_STOP_LIMIT, Order.ORDER_TAKE_PROFIT_LIMIT):
            bid_price = order.price
            ask_price = order.price

        elif order.order_type in (Order.ORDER_MARKET, Order.ORDER_STOP, Order.ORDER_TAKE_PROFIT):
            bid_price = trader_market.bid
            ask_price = trader_market.ask

        # open long are executed on bid and short on ask, close the inverse
        if order.direction == Position.LONG:
            open_exec_price = ask_price
            close_exec_price = bid_price
        elif order.direction == Position.SHORT:
            open_exec_price = bid_price
            close_exec_price = ask_price
        else:
            logger.error("Unsupported direction")
            return Order.REASON_INVALID_ARGS

        if not open_exec_price or not close_exec_price:
            logger.error("No order execution price")
            return Order.REASON_INVALID_ARGS

        # adjust quantity to step min and max, and round to decimal place of min size, and convert it to str
        quantity = order.quantity
        notional = quantity * open_exec_price

        if notional < trader_market.min_notional:
            # reject if lesser than min notional
            logger.error("%s refuse order because the min notional is not reached (%s<%s) %s in ref order %s" % (
                self.name, notional, trader_market.min_notional, order.symbol, order.ref_order_id))
            return Order.REASON_INVALID_ARGS

        # unique order id
        order_id = "siis_" + base64.b64encode(uuid.uuid4().bytes).decode('utf8').rstrip('=\n')
        order.set_order_id(order_id)
        order.created_time = self.timestamp

        if order.order_type == Order.ORDER_MARKET:
            # immediate execution of the order at market
            # @todo add to orders for emulate the slippage

            if order.margin_trade and trader_market.has_margin:
                if trader_market.indivisible_position:
                    return exec_indmargin_order(self, order, trader_market, open_exec_price, close_exec_price)
                else:
                    return exec_margin_order(self, order, trader_market, open_exec_price, close_exec_price)
            elif not order.margin_trade and trader_market.has_spot:
                return exec_buysell_order(self, order, trader_market, open_exec_price, close_exec_price)
        else:
            # create accepted, add to orders
            with self._mutex:
                self._orders[order_id] = order

            #
            # order signal
            #

            order_data = {
                'id': order.order_id,
                'symbol': order.symbol,
                'type': order.order_type,
                'direction': order.direction,
                'timestamp': order.created_time,
                'quantity': order.quantity,
                'price': order.price,
                'stop-price': order.stop_price,
                'stop-loss': order.stop_loss,
                'take-profit': order.take_profit,
                'time-in-force': order.time_in_force
            }

            # signal as watcher service (opened + full traded qty and immediately deleted)
            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_OPENED, self.name, (
                order.symbol, order_data, order.ref_order_id))

            return Order.REASON_OK

        return Order.REASON_ERROR

    def cancel_order(self, order_id: str, market_or_instrument: Union[Market, Instrument]) -> int:
        if not order_id or not market_or_instrument:
            return Order.REASON_INVALID_ARGS

        result = False

        with self._mutex:
            if order_id in self._orders:
                # self._closed_orders[rm.order_id] = self._orders[order_id]  # keep for history
                del self._orders[order_id]
                result = True

        if result:
            # signal of canceled order
            self.service.watcher_service.notify(Signal.SIGNAL_ORDER_CANCELED, self.name, (
                market_or_instrument.market_id, order_id, ""))

            return Order.REASON_OK

        return Order.REASON_ERROR

    def close_position(self, position_id: str, market_or_instrument: Union[Market, Instrument],
                       direction: int, quantity: float, market: bool = True,
                       limit_price: Optional[float] = None) -> bool:

        if not position_id or not market_or_instrument:
            return False

        trader_market = self._markets.get(market_or_instrument.market_id)
        if not trader_market:
            error_logger.error("Trader %s refuse to close position because the market %s is not found" % (
                self.name, market_or_instrument.market_id))
            return False

        result = False

        with self._mutex:
            # retrieve the position
            position = self._positions.get(position_id)

            if position and position.is_opened():
                # market stop order
                order = Order(self, position.symbol)
                order.set_position_id(position_id)

                order.direction = position.close_direction()

                if limit_price:
                    order.order_type = Order.ORDER_LIMIT
                    order.price = limit_price
                else:
                    order.order_type = Order.ORDER_MARKET

                order.quantity = position.quantity  # fully close
                order.leverage = position.leverage  # same as open

                order.close_only = True
                order.reduce_only = True

                #
                # price according to order type
                #

                bid_price = 0
                ask_price = 0

                if order.order_type == Order.ORDER_LIMIT:
                    bid_price = order.price
                    ask_price = order.price

                elif order.order_type == Order.ORDER_MARKET:
                    bid_price = trader_market.bid
                    ask_price = trader_market.ask

                # open long are executed on bid and short on ask, close the inverse
                if order.direction == Position.LONG:
                    open_exec_price = ask_price   # bid_price
                    close_exec_price = bid_price  # ask_price
                elif order.direction == Position.SHORT:
                    open_exec_price = bid_price   # ask_price
                    close_exec_price = ask_price  # bid_price
                else:
                    logger.error("Unsupported direction")
                    return False

                if not open_exec_price or not close_exec_price:
                    logger.error("No order execution price")
                    return False

                if self._slippage > 0.0:
                    # @todo deferred to update
                    return False
                else:
                    # immediate execution of the order
                    if trader_market.has_position:
                        # close isolated position
                        result = close_position(self, trader_market, position, close_exec_price, Order.ORDER_MARKET)
                    else:
                        # close position (could be using FIFO method)
                        result = exec_margin_order(self, order, trader_market, open_exec_price, close_exec_price)
            else:
                result = False

        return result

    def modify_position(self, position_id: str, market_or_instrument: Union[Market, Instrument],
                        stop_loss_price: Optional[float] = None, take_profit_price: Optional[float] = None) -> bool:

        if not position_id or not market_or_instrument:
            return False

        result = False

        with self._mutex:
            position = self._positions.get(position_id)
            if position:
                if market_or_instrument.has_position:
                    if stop_loss_price:
                        position.stop_loss = stop_loss_price
                    if take_profit_price:
                        position.take_profit = take_profit_price

                    position_data = {
                        'id': position_id,
                        'symbol': market_or_instrument.market_id,
                        'direction': position.direction,
                        'timestamp': self.timestamp,
                        'quantity': position.quantity,
                        'exec-price': None,
                        'avg-entry-price': None,
                        'avg-price': None,
                        'stop-loss': stop_loss_price,
                        'take-profit': take_profit_price,
                        'profit-loss': None,
                        'profit-currency': None,
                        'cumulative-filled': None,
                        'filled': None,
                        'liquidation-price': None
                    }

                    self.service.watcher_service.notify(Signal.SIGNAL_POSITION_AMENDED, self.name, (
                        market_or_instrument.market_id, position_data, None))

                result = True

        return result

    #
    # global accessors
    #

    def positions(self, market_id: str) -> List[Position]:
        """
        @deprecated
        """
        positions = []

        with self._mutex:
            for k, position in self._positions.items():
                if position.symbol == market_id:
                    positions.append(copy.copy(position))

        return positions

    def order_info(self, order_id: str, market_or_instrument: Union[Market, Instrument]) -> Union[dict, None]:
        """
        @todo for closed or canceled orders
        @todo Order should support the cumulative commission amount
        """
        if not order_id or not market_or_instrument:
            return None

        with self._mutex:
            order = self._orders.get(order_id)

            if order is None:
                # empty means success returns but does not exists
                return {
                    'id': None
                }

            order_info = {
                'id': order_id,
                'symbol': market_or_instrument.symbol,
                'status': 'opened',
                'ref-id': order.ref_order_id,
                'direction': order.direction,
                'type': order.order_type,
                'timestamp': order.transact_time or order.created_time,
                'avg-price': order.avg_price,
                'quantity': order.quantity,
                'cumulative-filled': order.executed,
                # 'cumulative-commission-amount': None,  # no have in Order object
                'price': order.price,
                'stop-price': order.stop_price,
                'time-in-force': order.time_in_force,
                'post-only': order.post_only,
                'close-only': order.close_only,
                'reduce-only': order.reduce_only,
                'stop-loss': None,
                'take-profit': None,
                'fully-filled': order.fully_filled
                # 'trades': trades
            }

            return order_info

    #
    # slots
    #

    def on_account_updated(self, balance: float, free_margin: float, unrealized_pnl: float, currency: str,
                           risk_limit: float):
        # not interested in account details
        pass

    def on_position_opened(self, market_id: str, position_data: dict, ref_order_id: str):
        # not interested in account positions
        pass

    def on_position_amended(self, market_id: str, position_data: dict, ref_order_id: str):
        pass
        
    def on_position_updated(self, market_id: str, position_data: dict, ref_order_id: str):
        pass

    def on_position_deleted(self, market_id: str, position_data: dict, ref_order_id: str):
        pass

    def on_order_opened(self, market_id: str, order_data: dict, ref_order_id: str):
        # not interested in account orders
        pass

    def on_order_updated(self, market_id: str, order_data: dict, ref_order_id: str):
        pass

    def on_order_deleted(self, market_id: str, order_id: str, ref_order_id: str):
        pass

    def on_order_traded(self, market_id: str, order_data: dict, ref_order_id: str):
        pass        

    @Trader.mutexed
    def on_update_market(self, market_id: str, tradeable: bool, last_update_time: float, bid: float, ask: float,
                         base_exchange_rate: Optional[float] = None,
                         contract_size: Optional[float] = None, value_per_pip: Optional[float] = None,
                         vol24h_base: Optional[float] = None, vol24h_quote: Optional[float] = None):

        market = self._markets.get(market_id)
        if market is None:
            # not interested in this market
            return

        if bid and ask and market.price:
            ratio = ((bid + ask) * 0.5) / market.price
        else:
            ratio = 1.0

        # push last price to keep a local cache of history
        if bid or ask:
            market.push_price()

        # defined and not 0
        if bid:
            market.bid = bid

        if ask:
            market.ask = ask

        if base_exchange_rate is not None:
            market.base_exchange_rate = base_exchange_rate

        if last_update_time:
            # defined and not 0
            market.last_update_time = last_update_time

        if tradeable is not None:
            market.is_open = tradeable

        if contract_size is not None:
            market.contract_size = contract_size

        if value_per_pip is not None:
            market.value_per_pip = value_per_pip

        if vol24h_base is not None:
            market.vol24h_base = vol24h_base

        if vol24h_quote is not None:
            market.vol24h_quote = vol24h_quote

        # update positions profit/loss for the related market id
        if not self._unlimited:
            if self.service.backtesting:
                # fake values
                market.base_exchange_rate = market.base_exchange_rate * ratio
                market.contract_size = market.contract_size * ratio

            if self._assets:
                # update profit/loss (informational) for each asset
                for k, asset in self._assets.items():
                    if asset.symbol == market.base and asset.quote and asset.quote == market.quote:
                        asset.update_profit_loss(market)

            if self._positions:
                # update profit/loss for each positions
                for k, position in self._positions.items():
                    if position.symbol == market.market_id:
                        position.update_profit_loss(market)

    #
    # persistence
    #

    def cmd_export(self, data: dict) -> dict:
        results = {
            'messages': [],
            'error': False
        }

        # clear the file
        dataset = data.get('dataset', "full")
        export_format = data.get('export-format', "json")
        filename = data.get('filename', "")

        if dataset not in ('trader',):
            results = {'message': "Unsupported export dataset", 'error': True}
            return results

        if export_format not in ('json',):
            results = {'message': "Unsupported export format", 'error': True}
            return results

        if not filename:
            if dataset == "trader":
                filename = "siis_trader.%s" % export_format

        with self._mutex:
            try:
                # account state
                account_dumps = self._account.dumps()

                # orders
                orders_dumps = []
                for order_id, order in self._orders.items():
                    order_dumps = order.dumps()
                    orders_dumps.append(order_dumps)

                # positions
                positions_dumps = []
                for position_id, position in self._positions.items():
                    position_dumps = position.dumps()
                    positions_dumps.append(position_dumps)

                # assets (qty)
                assets_dumps = []
                for asset_id, asset in self._assets.items():
                    asset_dumps = asset.dumps()
                    assets_dumps.append(asset_dumps)

            except Exception as e:
                error_logger.error(repr(e))

        dataset = {
            'name': self._name,
            'activity': self._activity,
            'account': account_dumps,
            'orders': orders_dumps,
            'positions': positions_dumps,
            'assets': assets_dumps
        }

        if export_format == "json":
            try:
                with open(filename, "w") as f:
                    json.dump(dataset, f, indent=4)

            except Exception as e:
                results['messages'].append(repr(e))
                results['error'] = True

        # with open(filename, "w") as f:
        #     f.write(json.dumps(dataset))

        return results

    def cmd_import(self, data: dict) -> dict:
        results = {
            'messages': [],
            'error': False
        }

        filename = data.get('filename', "")
        dataset = data.get('dataset', "trader")

        if dataset not in ('trader',):
            results = {'message': "Unsupported import dataset", 'error': True}
            return results

        if not filename:
            if dataset == 'trader':
                filename = "siis_trader.json"

        try:
            with open(filename, "rt") as f:
                data_dumps = json.loads(f.read())
        except FileNotFoundError:
            results = {'message': "File %s not found or no permissions" % filename, 'error': True}
            return results
        except json.JSONDecodeError as e:
            results = {'message': ["Error during parsing %s" % filename, repr(e)], 'error': True}
            return results

        try:
            self._activity = data_dumps.get('activity', self._activity)
            self._account.loads(data_dumps.get('account', {}))
        except Exception as e:
            error_logger.error(repr(e))
            results = {'message': ["Error during loading %s" % filename, repr(e)], 'error': True}

        orders_dumps = data_dumps.get('orders', [])
        for order_data in orders_dumps:
            try:
                symbol = order_data.get('symbol', "")

                order = Order(self, symbol)
                order.loads(order_data)

                with self._mutex:
                    self._orders[order.order_id] = order

            except Exception as e:
                error_logger.error(repr(e))
                results = {'message': ["Error during loading  %s order" % filename, repr(e)], 'error': True}

        positions_dumps = data_dumps.get('positions', [])
        for position_data in positions_dumps:
            try:
                symbol = position_data.get('symbol', "")

                position = Position(self)
                position.loads(position_data)

                with self._mutex:
                    self._positions[position.position_id] = position

            except Exception as e:
                error_logger.error(repr(e))
                results = {'message': ["Error during loading %s position" % filename, repr(e)], 'error': True}

        asset_dumps = data_dumps.get('assets', [])
        for asset_data in asset_dumps:
            try:
                symbol = asset_data.get('symbol', "")

                with self._mutex:
                    asset = self._assets.get(symbol)
                    if asset is not None:
                        asset.loads(asset_data)

            except Exception as e:
                error_logger.error(repr(e))
                results = {'message': ["Error during loading %s asset" % filename, repr(e)], 'error': True}

        return results
