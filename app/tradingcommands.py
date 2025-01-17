# @date 2019-06-15
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# terminal trading commands and registration

import re
import sys

from terminal.command import Command
from strategy.strategy import Strategy
from notifier.notifier import Notifier
from trader.trader import Trader

from common.utils import timeframe_from_str
from instrument.instrument import Instrument

from app.script import setup_script


class PlayCommand(Command):
    SUMMARY = "[strategy|notifiers] <empty,notifier-id> <market-id> to enable strategy-trader(s) or notifiers(s)."
    HELP = (
        "param1: [strategy|notifier]",
        "param2: <notifier-id> for notifier only",
        "param3: <market-id> for strategy only (optional)",
    )

    def __init__(self, strategy_service, notifier_service):
        super().__init__('play', None)

        self._strategy_service = strategy_service
        self._notifier_service = notifier_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        if args[0] == 'strategy':
            if len(args) == 1:
                self._strategy_service.set_activity(True)
                return True, "Activated any instruments for strategy"

            elif len(args) == 2:
                strategy = self._strategy_service.strategy()
                if strategy:
                    strategy.set_activity(True, args[1])
                    return True, "Activated instrument %s" % args[1]

        elif args[0] == 'notifiers':
            if len(args) == 1:
                self._notifier_service.set_activity(True)
                return True, "Activated all notifiers"

            elif len(args) == 2:
                notifier = self._notifier_service.notifier(args[1])
                if notifier:
                    notifier.set_activity(True)
                    return True, "Activated notifier %s" % args[1]

        return False, None

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, ['strategy', 'notifiers'], args, tab_pos, direction)

        elif len(args) <= 2:
            if args[0] == "strategy":
                # instrument
                strategy = self._strategy_service.strategy()
                if strategy:
                    return self.iterate(1, strategy.symbols_ids(), args, tab_pos, direction)

            elif args[0] == "notifiers":
                return self.iterate(1, self._notifier_service.notifiers_identifiers(), args, tab_pos, direction)

        return args, 0


class PauseCommand(Command):
    SUMMARY = "[strategy|notifiers] <notifier-id> <market-id> to disable strategy-trader(s) or notifiers(s)."
    HELP = (
        "param1: [strategy|notifier]",
        "param2: <notifier-id> for notifier only",
        "param3: <market-id> for strategy only (optional)",
    )

    def __init__(self, strategy_service, notifier_service):
        super().__init__('pause', None)

        self._strategy_service = strategy_service
        self._notifier_service = notifier_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        if args[0] == 'strategy':
            if len(args) == 1:
                self._strategy_service.set_activity(False)
                return True, "Paused any instruments for strategy"

            elif len(args) == 2:
                strategy = self._strategy_service.strategy()
                if strategy:
                    strategy.set_activity(False, args[1])
                    return True, "Paused instrument %s" % args[1]

        elif args[0] == 'notifiers':
            if len(args) == 1:
                self._notifier_service.set_activity(False)
                return True, "Paused all notifiers"

            elif len(args) == 2:
                notifier = self._notifier_service.notifier(args[1])
                if notifier:
                    notifier.set_activity(False)
                    return True, "Paused notifier %s" % args[1]

        return False, None

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, ['strategy', 'notifiers'], args, tab_pos, direction)

        elif len(args) <= 2:
            if args[0] == "strategy":
                # instrument
                strategy = self._strategy_service.strategy()
                if strategy:
                    return self.iterate(1, strategy.symbols_ids(), args, tab_pos, direction)

            elif args[0] == "notifiers":
                return self.iterate(1, self._notifier_service.notifiers_identifiers(), args, tab_pos, direction)

        return args, 0


class InfoCommand(Command):
    SUMMARY = "[strategy|notifiers] <notifier-id> <market-id> to get info on strategy-trader(s), trader or notifier(s)."
    HELP = (
        "param1: [strategy|notifier]",
        "param2: <notifier-id> for notifier only",
        "param3: <market-id> for strategy only (optional)",
        "param4: <status|details> for strategy with a specified market-id only (optional)",
    )

    DETAIL_CHOICES = ("status", "details")

    def __init__(self, strategy_service, notifier_service):
        super().__init__('info', None)

        self._strategy_service = strategy_service
        self._notifier_service = notifier_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters. Need at at least strategy or notifiers."

        detail = None

        if len(args) == 3:
            if args[2] in InfoCommand.DETAIL_CHOICES:
                detail = args[2]
            else:
                return False, "Invalid detail option."

        if args[0] == 'strategy':
            if len(args) == 1:
                results = self._strategy_service.command(Strategy.COMMAND_INFO, {})
                return self.manage_results(results)

            elif len(args) == 2:
                results = self._strategy_service.command(Strategy.COMMAND_INFO, {'market-id': args[1]})
                return self.manage_results(results)

            elif len(args) == 3:
                results = self._strategy_service.command(Strategy.COMMAND_TRADER_INFO, {
                    'detail': detail,
                    'market-id': args[1]
                })
                return self.manage_results(results)

        elif args[0] == 'notifiers':
            if len(args) == 1:
                results = self._notifier_service.command(Notifier.COMMAND_INFO, {})
                return self.manage_results(results)

            elif len(args) == 2:
                results = self._notifier_service.command(Notifier.COMMAND_INFO, {'notifier': args[1]})
                return self.manage_results(results)

        return False, None

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, ['strategy', 'notifiers'], args, tab_pos, direction)

        elif len(args) <= 2:
            if args[0] == "strategy":
                # instrument
                strategy = self._strategy_service.strategy()
                if strategy:
                    return self.iterate(1, strategy.symbols_ids(), args, tab_pos, direction)

            elif args[0] == "notifiers":
                return self.iterate(1, self._notifier_service.notifiers_identifiers(), args, tab_pos, direction)

        elif len(args) <= 3:
            if args[0] == "strategy" and args[1]:
                return self.iterate(2, InfoCommand.DETAIL_CHOICES, args, tab_pos, direction)

        return args, 0


class SetAffinityCommand(Command):
    SUMMARY = "<market-id> [0..100] to modify the affinity per market."
    HELP = (
        "param1: <market-id> for specific (optional)",
        "param2: <affinity> 0..100 integer",
    )

    def __init__(self, strategy_service):
        super().__init__('set-affinity', 'SETAFF')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters. Need at least affinity."

        action = "set-affinity"
        market_id = None

        is_int = True

        try:
            int(args[0])
        except ValueError:
            is_int = False

        if is_int:
            try:
                affinity = int(args[0])
            except ValueError:
                return False, "Invalid affinity format"
        else:
            market_id = args[0]

            try:
                affinity = int(args[1])
            except ValueError:
                return False, "Invalid affinity format"

        if market_id:
            results = self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
                'market-id': market_id,
                'action': action,
                'affinity': affinity
            })
        else:
            results = self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY_ALL, {
                'action': action,
                'affinity': affinity
            })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            if len(args) == 1:
                is_int = True

                try:
                    int(args[0])
                except ValueError:
                    is_int = False

                if is_int:
                    return args, 0

            # instrument
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class SetOptionCommand(Command):
    SUMMARY = "any or specify <market-id> to modify the option per market."
    HELP = (
        "param1: <market-id> for specific (optional)",
        "param2: <name.of.the.parameter> String of the parameter separated by dot",
        "param3: <value> Value of the parameter (integer, decimal or string)",
    )

    # INTEGER_RE = re.compile(r'^[+-]{0,1}[0-9]+$')
    INTEGER_RE = re.compile(r'^[+-]?[0-9]+$')
    FLOAT_RE = re.compile(r'(?i)^\s*[+-]?(?:inf(inity)?|nan|(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)\s*$')

    def __init__(self, strategy_service):
        super().__init__('set-option', 'SETOPT')

        self._strategy_service = strategy_service

    def execute(self, args):
        if len(args) < 2 or len(args) > 3:
            return False, "Missing parameters. Need at least option and value."

        action = "set-option"
        market_id = None
        option = None
        value = None

        def convert_value(v):
            if v is None:
                # undefined
                return None

            if len(v) == 0:
                # empty string
                return ""

            if SetOptionCommand.INTEGER_RE.match(v) is not None:
                # int ?
                try:
                    return int(v)
                except ValueError:
                    return v

            if SetOptionCommand.FLOAT_RE.match(v) is not None:
                # float ?
                try:
                    return float(v)
                except ValueError:
                    return v

            # string
            return v

        if len(args) == 2:
            option = args[0]
            value = convert_value(args[1])

        elif len(args) == 3:
            market_id = args[0]
            option = args[1]
            value = convert_value(args[2])

        if market_id:
            results = self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
                'market-id': market_id,
                'action': action,
                'option': option,
                'value': value
            })
        else:
            results = self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY_ALL, {
                'action': action,
                'option': option,
                'value': value
            })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            # instrument
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class SetFrozenQuantityCommand(Command):
    SUMMARY = "<asset-name> to modify the frozen quantity per asset."
    HELP = (
        "param1: <asset-name> Asset name",
        "param2: <quantity> Quantity",
    )

    def __init__(self, trader_service):
        super().__init__('set-frozen', 'SETFRZ')

        self._trader_service = trader_service

    def execute(self, args):
        if len(args) != 2:
            return False, "Missing parameters"

        action = "set-frozen"

        try:
            asset_name = args[0]
            quantity = float(args[1])

        except ValueError:
            return False, "Invalid parameters"

        results = self._trader_service.command(Trader.COMMAND_TRADER_FROZE_ASSET_QUANTITY, {
            'asset': asset_name,
            'quantity': quantity,
            'action': action
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            # asset
            trader = self._trader_service.trader()
            if trader:
                return self.iterate(0, trader.assets_names(), args, tab_pos, direction)

        return args, 0


class LongCommand(Command):
    SUMMARY = "to manually create to a new trade in LONG direction"
    HELP = (
        "param1: <market-id>",
        "param2: [l|L][@|+|-|%|!]<entry-price> Use @ for a limit, + or - for order book depth, % below in percent,"
        " ! below in pips, else enter at market (optional)",
        "param3: [sl|SL][@|%|!]<stop-loss-price> @ for a stop, % for distance in percent below "
        "market or limit price, ! for distance in pips below market or limit price (optional)",
        "param4: [tp|TP][@|%|!]<take-profit-price> @ for a limit, % for distance in percent above "
        "market or limit price, ! for distance in pips above market or limit price (optional)",
        "param5: [']<timeframe> Related timeframe (1m, 4h, 1d...) (optional)",
        "param6: [-]<context-id> Related context identifier to manage the trade (optional)",
        "param7: [*]<decimal> or <decimal>% Quantity rate factor or rate in percent (optional)",
        "param8: [/]<timeframe> Entry timeout timeframe (1m, 4h, 1d..) (optional)",
        "param9: [x]<decimal> Manual leverage if supported (optional)",
        "param10: [+]<timeframe> Expiry (optional)",
        "param11: [q]<quantity> User defined asset quantity (optional)",
    )

    def __init__(self, strategy_service):
        super().__init__('long', 'L')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        # ie: ":long BTCUSDT L@8500 SL%5 TP@9600", direction base on command name
        direction = 1
        method = 'market'
        limit_price = None
        trigger_price = None
        stop_loss = 0.0
        take_profit = 0.0
        stop_loss_price_mode = "price"
        take_profit_price_mode = "price"
        user_quantity = 0.0
        quantity_rate = 1.0
        timeframe = Instrument.TF_4HOUR
        entry_timeout = None
        expiry = None
        leverage = None
        context = None

        if len(args) < 1:
            return False, "Missing parameters"

        try:
            market_id = args[0]

            for value in args[1:]:
                if not value:
                    continue

                if value.startswith("L@") or value.startswith("l@"):
                    method = 'limit'
                    limit_price = float(value[2:])

                elif value.startswith("L%") or value.startswith("l%"):
                    method = 'limit-percent'
                    limit_price = float(value[2:])

                    if limit_price <= 0:
                        return False, "Percent must be greater than 0"

                elif value.startswith("L!") or value.startswith("l!"):
                    method = 'limit-pip'
                    limit_price = float(value[2:])

                    if limit_price <= 0:
                        return False, "Pip must be greater than 0"

                elif value.startswith("L+") or value.startswith("l+"):
                    dist = int(value[2:])

                    if dist < 1 or dist > 500:
                        return False, "Bid depth must be from 1 to 500"

                    method = 'best+%s' % dist

                elif value.startswith("L-") or value.startswith("l-"):
                    dist = int(value[2:])

                    if dist < 1 or dist > 500:
                        return False, "Ask depth must be from 1 to 500"

                    method = 'best-%s' % dist

                elif value.startswith("T@") or value.startswith("t@"):
                    method = 'trigger'
                    trigger_price = float(value[2:])

                elif value.startswith("SL@") or value.startswith("sl@"):
                    stop_loss = float(value[3:])
                elif value.startswith("SL%") or value.startswith("sl%"):
                    stop_loss = float(value[3:])
                    stop_loss_price_mode = "percent"
                elif value.startswith("SL!") or value.startswith("sl!"):
                    stop_loss = float(value[3:])
                    stop_loss_price_mode = "pip"

                elif value.startswith("TP@") or value.startswith("tp@"):
                    take_profit = float(value[3:])
                elif value.startswith("TP%") or value.startswith("tp%"):
                    take_profit = float(value[3:])
                    take_profit_price_mode = "percent"
                elif value.startswith("TP!") or value.startswith("tp!"):
                    take_profit = float(value[3:])
                    take_profit_price_mode = "pip"

                elif value.startswith("'"):
                    timeframe = timeframe_from_str(value[1:])

                elif value.startswith("*"):
                    quantity_rate = float(value[1:])

                elif value.endswith("%"):
                    quantity_rate = float(value[:-1]) * 0.01

                elif value.startswith("/"):
                    entry_timeout = timeframe_from_str(value[1:])

                elif value.startswith("+"):
                    expiry = timeframe_from_str(value[1:])

                elif value.startswith("x"):
                    leverage = float(value[1:])

                elif value.startswith("-"):
                    context = value[1:]

                elif value.startswith("q"):
                    user_quantity = float(value[1:])

        except ValueError:
            return False, "Invalid parameters"

        if limit_price and stop_loss and stop_loss_price_mode == "price" and stop_loss > limit_price:
            return False, "Stop-loss must be lesser than limit price"

        if limit_price and take_profit and take_profit_price_mode == "price" and take_profit < limit_price:
            return False, "Take-profit must be greater than limit price"

        if quantity_rate <= 0.0:
            return False, "Quantity rate must be greater than zero"

        results = self._strategy_service.command(Strategy.COMMAND_TRADE_ENTRY, {
            'market-id': market_id,
            'direction': direction,
            'limit-price': limit_price,
            'trigger-price': trigger_price,
            'method': method,
            'quantity-rate': quantity_rate,
            'user-quantity': user_quantity,
            'stop-loss': stop_loss,
            'take-profit': take_profit,
            'stop-loss-price-mode': stop_loss_price_mode,
            'take-profit-price-mode': take_profit_price_mode,
            'timeframe': timeframe,
            'entry-timeout': entry_timeout,
            'expiry': expiry,
            'leverage': leverage,
            'context': context
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class ShortCommand(Command):
    SUMMARY = "to manually create to a new trade in SHORT direction"
    HELP = (
        "param1: <market-id>",
        "param2: [l|L][@|+|-|%|!]<entry-price> Use @ for a limit, + or - for order book depth, % above in percent,"
        " ! above in pips, else enter at market (optional)",
        "param3: [sl|SL][@|%|!]<stop-loss-price> @ for a stop, % for distance in percent above market or "
        "limit price, ! for distance in pips above market price (optional)",
        "param4: [tp|TP][@|%|!]<take-profit-price> @ for a limit, % for distance in percent below market or "
        "limit price, ! for distance in pips below market or limit price (optional)",
        "param5: [']<timeframe> Related timeframe (1m, 4h, 1d...) (optional)",
        "param6: [-]<context-id> Related context identifier to manage the trade (optional)",
        "param7: [*]<decimal> or <decimal>% Quantity rate factor or rate in percent (optional)",
        "param8: [/]<timeframe> Entry timeout timeframe (1m, 4h, 1d..) (optional)",
        "param9: [x]<decimal> Manual leverage if supported (optional)",
        "param10: [+]<timeframe> Expiry (optional)",
    )

    def __init__(self, strategy_service):
        super().__init__('short', 'S')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        # ie: ":long BTCUSDT L@8500 SL@8300 TP@9600 1.0", direction base on command name
        direction = -1
        method = 'market'
        limit_price = None
        trigger_price = None
        stop_loss = 0.0
        take_profit = 0.0
        stop_loss_price_mode = "price"
        take_profit_price_mode = "price"
        quantity_rate = 1.0
        timeframe = Instrument.TF_4HOUR
        entry_timeout = None
        expiry = None
        leverage = None
        context = None

        if len(args) < 1:
            return False, "Missing parameters"

        try:
            market_id = args[0]

            for value in args[1:]:
                if not value:
                    continue

                if value.startswith("L@") or value.startswith("l@"):
                    method = 'limit'
                    limit_price = float(value[2:])

                elif value.startswith("L%") or value.startswith("l%"):
                    method = 'limit-percent'
                    limit_price = float(value[2:])

                    if limit_price <= 0:
                        return False, "Percent must be greater than 0"

                elif value.startswith("L!") or value.startswith("l!"):
                    method = 'limit-pip'
                    limit_price = float(value[2:])

                    if limit_price <= 0:
                        return False, "Pip must be greater than 0"

                elif value.startswith("L+") or value.startswith("l+"):
                    dist = int(value[2:])

                    if dist < 1 or dist > 500:
                        return False, "Ask depth must be from 1 to 500"

                    method = 'best+%s' % dist

                elif value.startswith("L-") or value.startswith("l-"):
                    dist = int(value[2:])

                    if dist < 1 or dist > 500:
                        return False, "Bid depth must be from 1 to 500"

                    method = 'best-%s' % dist

                elif value.startswith("T@") or value.startswith("t@"):
                    method = 'trigger'
                    trigger_price = float(value[2:])

                elif value.startswith("SL@") or value.startswith("sl@"):
                    stop_loss = float(value[3:])
                elif value.startswith("SL%") or value.startswith("sl%"):
                    stop_loss = float(value[3:])
                    stop_loss_price_mode = "percent"
                elif value.startswith("SL!") or value.startswith("sl!"):
                    stop_loss = float(value[3:])
                    stop_loss_price_mode = "pip"

                elif value.startswith("TP@") or value.startswith("tp@"):
                    take_profit = float(value[3:])
                elif value.startswith("TP%") or value.startswith("tp%"):
                    take_profit = float(value[3:])
                    take_profit_price_mode = "percent"
                elif value.startswith("TP!") or value.startswith("tp!"):
                    take_profit = float(value[3:])
                    take_profit_price_mode = "pip"

                elif value.startswith("'"):
                    timeframe = timeframe_from_str(value[1:])

                elif value.startswith("*"):
                    quantity_rate = float(value[1:])

                elif value.endswith("%"):
                    quantity_rate = float(value[:-1]) * 0.01

                elif value.startswith("/"):
                    entry_timeout = timeframe_from_str(value[1:])

                elif value.startswith("+"):
                    expiry = timeframe_from_str(value[1:])

                elif value.startswith("x"):
                    leverage = float(value[1:])

                elif value.startswith("-"):
                    context = value[1:]

        except ValueError:
            return False, "Invalid parameters"

        if limit_price and stop_loss and stop_loss_price_mode == "price" and stop_loss < limit_price:
            return False, "Stop-loss must be greater than limit price"

        if limit_price and take_profit and take_profit_price_mode == "price" and take_profit > limit_price:
            return False, "Take-profit must be lesser than limit price"

        if quantity_rate <= 0.0:
            return False, "Quantity must be non empty"

        results = self._strategy_service.command(Strategy.COMMAND_TRADE_ENTRY, {
            'market-id': market_id,
            'direction': direction,
            'limit-price': limit_price,
            'trigger-price': trigger_price,
            'method': method,
            'quantity-rate': quantity_rate,
            'stop-loss': stop_loss,
            'take-profit': take_profit,
            'stop-loss-price-mode': stop_loss_price_mode,
            'take-profit-price-mode': take_profit_price_mode,
            'timeframe': timeframe,
            'entry-timeout': entry_timeout,
            'expiry': expiry,
            'leverage': leverage,
            'context': context
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class CloseCommand(Command):
    SUMMARY = "to manually close a managed trade at market or limit"
    HELP = (
        "param1: <market-id> Market identifier",
        "param2: <trade-id> Trade identifier",
    )

    def __init__(self, strategy_service):
        super().__init__('close', 'C')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        action = "close"

        # ie ":close EURUSD 5"
        if len(args) != 2:
            return False, "Missing parameters"

        try:
            market_id = args[0]
            trade_id = int(args[1])

        except ValueError:
            return False, "Invalid parameters"

        results = self._strategy_service.command(Strategy.COMMAND_TRADE_EXIT, {
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class CleanCommand(Command):
    SUMMARY = "to manually force to remove a managed trade and all its related orders without reducing its " \
              "remaining quantity"
    HELP = (
        "param1: <market-id> Market identifier",
        "param2: <trade-id> Trade identifier",
    )

    def __init__(self, strategy_service):
        super().__init__('clean-trade', 'CT')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        action = "clean"

        # ie ":clean XRPUSDT 5"
        if len(args) != 2:
            return False, "Missing parameters"

        try:
            market_id = args[0]
            trade_id = int(args[1])

        except ValueError:
            return False, "Invalid parameters"

        results = self._strategy_service.command(Strategy.COMMAND_TRADE_CLEAN, {
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class StepStopLossOperationCommand(Command):
    SUMMARY = "to manually add a step-stop-loss operation on a trade"
    HELP = (
        "param1: <market-id> Market identifier",
        "param2: <trade-id> Trade identifier",
        "param3: <trigger-price> Trigger price",
        "param4: <stop-loss-price> Stop-loss price",
    )

    def __init__(self, strategy_service):
        super().__init__('step-stop-loss', 'SSL')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        action = "add-op"
        op = "step-stop-loss"

        # ie ":SSL EURUSD 4 1.12 1.15"
        if len(args) != 4:
            return False, "Missing parameters"

        try:
            market_id = args[0]

            trade_id = int(args[1])

            trigger = float(args[2])
            stop_loss = float(args[3])
        except ValueError:
            return False, "Invalid parameters"

        results = self._strategy_service.command(Strategy.COMMAND_TRADE_MODIFY, {
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action,
            'operation': op,
            'trigger': trigger,
            'stop-loss': stop_loss
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class RemoveOperationCommand(Command):
    SUMMARY = "to manually remove an operation from a trade"
    HELP = (
        "param1: <market-id> Market identifier",
        "param2: <trade-id> Trade identifier"
        "param3: <operation-id> Operation identifier"
    )

    def __init__(self, strategy_service):
        super().__init__('del', 'D')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        action = 'del-op'

        # ie ":D EURUSD 1 5"
        if len(args) < 3:
            return False, "Missing parameters"

        try:
            market_id = args[0]

            trade_id = int(args[1])
            operation_id = int(args[2])
        except ValueError:
            return False, "Invalid parameters"

        results = self._strategy_service.command(Strategy.COMMAND_TRADE_MODIFY, {
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action,
            'operation-id': operation_id
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class CheckTradeCommand(Command):
    SUMMARY = "to manually recheck a trade"
    HELP = (
        "param1: <market-id> Market identifier",
        "param2: <trade-id> Trade identifier",
        "param3: [repair] To repair as possible the trade (optional)",
    )

    def __init__(self, strategy_service):
        super().__init__('check-trade', 'CHKT')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        repair = False

        # ie ":CHKT EURUSD 4"
        if len(args) < 2:
            return False, "Missing parameters"

        try:
            market_id = args[0]

            trade_id = int(args[1])

            if len(args) > 2:
                repair = args[2] == "repair"
        except ValueError:
            return False, "Invalid parameters"

        results = self._strategy_service.command(Strategy.COMMAND_TRADE_CHECK, {
            'market-id': market_id,
            'trade-id': trade_id,
            'repair': repair
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class ModifyStopLossCommand(Command):
    SUMMARY = "to manually modify the stop-loss of a trade"
    HELP = (
        "param1: <market-id> Market identifier",
        "param2: <trade-id> Trade identifier",
        "param3: [ep|m|EP|M][+|-]<stop-loss-price><%><pip(s)> EP: relative to entry-price, M to market-price, "
        "else to last stop price, + or - for relative change, in price, percent, or pips",
        "param4: [force] to force to realize the order if none (optional)",
    )

    def __init__(self, strategy_service):
        super().__init__('stop-loss', 'SL')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        action = 'stop-loss'
        method = 'price'
        force = False

        # ie ":SL EURUSD 1 1.10"
        if len(args) < 3:
            return False, "Missing parameters"

        try:
            market_id = args[0]
            trade_id = int(args[1])

            if args[2].startswith('+') or args[2].startswith('-'):
                # last value relative delta price, % or pip(s)
                if args[2].endswith('%'):
                    method = 'delta-percent'
                    stop_loss = float(args[2][:-1]) * 0.01
                elif args[2].endswith('pip'):
                    method = 'delta-pip'
                    stop_loss = float(args[2][:-3])
                elif args[2].endswith('pips'):
                    method = 'delta-pip'
                    stop_loss = float(args[2][:-4])
                else:
                    method = 'delta-price'
                    stop_loss = float(args[2])

            elif args[2].startswith("EP") or args[2].startswith("ep"):
                # entry-price relative delta price, % or pip(s)
                if args[2].endswith('%'):
                    method = 'entry-delta-percent'
                    stop_loss = float(args[2][2:-1]) * 0.01
                elif args[2].endswith('pip'):
                    method = 'entry-delta-pip'
                    stop_loss = float(args[2][2:-3])
                elif args[2].endswith('pips'):
                    method = 'entry-delta-pip'
                    stop_loss = float(args[2][2:-4])
                else:
                    method = 'entry-delta-price'
                    stop_loss = float(args[2][2:])

            elif args[2].startswith("M") or args[2].startswith("m"):
                # market-price relative delta price, % or pip(s)
                if args[2].endswith('%'):
                    method = 'market-delta-percent'
                    stop_loss = float(args[2][1:-1]) * 0.01
                elif args[2].endswith('pip'):
                    method = 'market-delta-pip'
                    stop_loss = float(args[2][1:-1])
                elif args[2].endswith('pips'):
                    method = 'market-delta-pip'
                    stop_loss = float(args[2][1:-1])
                else:
                    method = 'market-delta-price'
                    stop_loss = float(args[2][1:])

            else:
                # absolute price
                stop_loss = float(args[2])

            if len(args) > 3:
                # create an order or modify the position, else use default
                force = str(args[3]) == "force"

        except ValueError:
            return False, "Invalid parameters"

        results = self._strategy_service.command(Strategy.COMMAND_TRADE_MODIFY, {
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action,
            'method': method,
            'stop-loss': stop_loss,
            'force': force
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class ModifyTakeProfitCommand(Command):
    SUMMARY = "to manually modify the take-profit of a trade"
    HELP = (
        "param1: <market-id> Market identifier",
        "param2: <trade-id> Trade identifier",
        "param3: [ep|m|EP|M][+|-]<take-profit-price><%><pip(s)> EP: relative to entry-price, M to market-price, "
        "else to last take-profit price, + or - for relative change, in price or percent",
        "param4: [force] to force to realize the order if none (optional)",
    )

    def __init__(self, strategy_service):
        super().__init__('take-profit', 'TP')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        action = 'take-profit'
        method = 'price'
        force = False

        # ie ":TP EURUSD 1 1.15"
        if len(args) < 3:
            return False, "Missing parameters"

        try:
            market_id = args[0]
            trade_id = int(args[1])

            if args[2].startswith('+') or args[2].startswith('-'):
                # last value relative delta price or %
                if args[2].endswith('%'):
                    method = 'delta-percent'
                    take_profit = float(args[2][:-1]) * 0.01
                elif args[2].endswith('pip'):
                    method = 'delta-pip'
                    take_profit = float(args[2][:-3])
                elif args[2].endswith('pips'):
                    method = 'delta-pip'
                    take_profit = float(args[2][:-4])
                else:
                    method = 'delta-price'
                    take_profit = float(args[2])

            elif args[2].startswith("EP") or args[2].startswith("ep"):
                # entry-price relative delta price or %
                if args[2].endswith('%'):
                    method = 'entry-delta-percent'
                    take_profit = float(args[2][2:-1]) * 0.01
                elif args[2].endswith('pip'):
                    method = 'entry-delta-pip'
                    take_profit = float(args[2][2:-3])
                elif args[2].endswith('pips'):
                    method = 'entry-delta-pip'
                    take_profit = float(args[2][2:-4])
                else:
                    method = 'entry-delta-price'
                    take_profit = float(args[2][2:])

            elif args[2].startswith("M") or args[2].startswith("m"):
                # market-price relative delta price or %
                if args[2].endswith('%'):
                    method = 'market-delta-percent'
                    take_profit = float(args[2][1:-1]) * 0.01
                elif args[2].endswith('pip'):
                    method = 'market-delta-pip'
                    take_profit = float(args[2][1:-1])
                elif args[2].endswith('pips'):
                    method = 'market-delta-pip'
                    take_profit = float(args[2][1:-1])
                else:
                    method = 'market-delta-price'
                    take_profit = float(args[2][1:])

            else:
                take_profit = float(args[2])

            if len(args) > 3:
                # create an order or modify the position, else use default
                force = str(args[3]) == "force"

        except ValueError:
            return False, "Invalid parameters"

        results = self._strategy_service.command(Strategy.COMMAND_TRADE_MODIFY, {
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action,
            'method': method,
            'take-profit': take_profit,
            'force': force
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class TradeInfoCommand(Command):
    SUMMARY = "to get operations info of a specific trade"
    HELP = (
        "param1: <market-id> Market identifier",
        "param2: <trade-id> Trade identifier",
    )

    def __init__(self, strategy_service):
        super().__init__('trade', 'T')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        if len(args) >= 1:
            try:
                market_id = args[0]

                if len(args) >= 2:
                    trade_id = int(args[1])
                else:
                    trade_id = -1

            except ValueError:
                return False, "Invalid parameters"

            results = self._strategy_service.command(Strategy.COMMAND_TRADE_INFO, {
                'market-id': market_id,
                'trade-id': trade_id
            })

            return self.manage_results(results)
        else:
            return False, "Missing or invalid parameters"

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class AssignCommand(Command):
    SUMMARY = "to manually assign a quantity of asset or an existing position to a new trade"
    HELP = (
        "param1: <market-id> Market identifier",
        "param2: [limit|market|trigger] Order type (optional) (default limit)",
        "param3: [L|S|long|short] Direction (optional) (default long)",
        "param4: [EP@]<entry-price>",
        "param5: [SL@]<stop-loss-price> (optional)",
        "param6: [TP@]<take-profit-price> (optional)",
        "param7: [']<timeframe> (optional)",
        "param8: [-]<context-id> (optional)",
        # "param9: [/]<timeframe> Entry timeout (optional)",
        "param10: [+]<timeframe> Expiry (optional)",
        "last: <quantity>",
    )

    def __init__(self, strategy_service):
        super().__init__('assign', 'AS')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        # ie: ":assign BTCUSDT EP@8500 SL@8300 TP@9600 0.521", direction base on command name
        direction = 1
        order_type = 'limit'
        entry_price = None
        stop_loss = 0.0
        take_profit = 0.0
        quantity = 0.0
        timeframe = Instrument.TF_4HOUR
        # entry_timeout = None
        expiry = None
        leverage = None
        context = None

        if len(args) < 2:
            return False, "Missing parameters. Need at least entry price and quantity"

        try:
            market_id = args[0]

            for value in args[1:]:
                if not value:
                    continue

                if value == 'L' or value == 'long':
                    direction = 1
                elif value == 'S' or value == 'short':
                    direction = -1
                elif value == 'limit':
                    order_type = value
                elif value == 'market':
                    order_type = value
                elif value == 'trigger':
                    order_type = value
                elif value.startswith("EP@"):
                    entry_price = float(value[3:])
                elif value.startswith("SL@"):
                    stop_loss = float(value[3:])
                elif value.startswith("TP@"):
                    take_profit = float(value[3:])
                elif value.startswith("'"):
                    timeframe = timeframe_from_str(value[1:])
                elif value.startswith("-"):
                    context = value[1:]
                # elif value.startswith("/"):
                #     entry_timeout = timeframe_from_str(value[1:])
                elif value.startswith("+"):
                    expiry = timeframe_from_str(value[1:])
                elif value.startswith("x"):
                    leverage = float(value[1:])
                else:
                    quantity = float(value)

        except ValueError:
            return False, "Invalid parameters"

        if entry_price <= 0.0:
            return False, "Entry price must be specified"

        if stop_loss:
            if direction > 0 and stop_loss >= entry_price:
                return False, "Stop-loss must be lesser than entry price"
            elif direction < 0 and stop_loss <= entry_price:
                return False, "Stop-loss must be greater than entry price"

        if take_profit:
            if direction > 0 and take_profit <= entry_price:
                return False, "Take-profit must be greater than entry price"
            elif direction < 0 and take_profit >= entry_price:
                return False, "Take-profit must be lesser than entry price"

        if quantity <= 0.0:
            return False, "Quantity must be specified"

        results = self._strategy_service.command(Strategy.COMMAND_TRADE_ASSIGN, {
            'market-id': market_id,
            'direction': direction,
            'order-type': order_type,
            'entry-price': entry_price,
            'quantity': quantity,
            'stop-loss': stop_loss,
            'take-profit': take_profit,
            'timeframe': timeframe,
            'context': context,
            # 'entry-timeout': entry_timeout,
            'expiry': expiry,
            'leverage': leverage,
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class CommentCommand(Command):
    SUMMARY = "to set the comment of a trade"
    HELP = (
        "param1: <market-id> Market identifier",
        "param2: <trade-id> Trade identifier",
        "last: <str> Comment or empty"
    )

    def __init__(self, strategy_service):
        super().__init__('comment', 'CC')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        action = 'comment'

        # ie ":CC EURUSD 1 do a partial TP before"
        if len(args) < 2:
            return False, "Missing parameters"

        try:
            market_id = args[0]
            trade_id = int(args[1])

        except ValueError:
            return False, "Invalid parameters"

        if len(args) > 2:
            comment = ' '.join(args[2:])
        else:
            comment = ""

        results = self._strategy_service.command(Strategy.COMMAND_TRADE_MODIFY, {
            'market-id': market_id,
            'trade-id': trade_id,
            'action': action,
            'comment': comment
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class UserSaveCommand(Command):
    SUMMARY = "to save user data now (strategy traders states, options, regions, trades)"

    def __init__(self, strategy_service):
        super().__init__('save', 'SAVE')

        self._strategy_service = strategy_service

    def execute(self, args):
        try:
            self._strategy_service.strategy().save()
        except Exception as e:
            return False, repr(e)

        return True, "Successfully saved strategy data for %s - %s" % (
            self._strategy_service.strategy().name, self._strategy_service.strategy().identifier)


class UserLoadCommand(Command):
    SUMMARY = "to load user data now (strategy traders states, options, regions, trades)"

    def __init__(self, strategy_service):
        super().__init__('load', 'LOAD')

        self._strategy_service = strategy_service

    def execute(self, args):
        try:
            if not self._strategy_service.strategy().load():
                return True, "Unable to load strategy user data for %s - %s (can be done once trader is loaded and " \
                             "only once)" % (self._strategy_service.strategy().name,
                                             self._strategy_service.strategy().identifier)

        except Exception as e:
            return False, repr(e)

        return True, "Successfully loaded strategy user data for %s - %s (checking trades can take more time)" % (
            self._strategy_service.strategy().name, self._strategy_service.strategy().identifier)


class UserExportCommand(Command):
    SUMMARY = "to export actives trades or history or trader state at current state in a JSON or CSV file"
    HELP = (
        "param1: <market-id> market-id or any if not specified (optional)",
        "param2: <active|history|closed|alert|region|strategy|trader> Active trade, history trades, alerts, "
        " region, strategy or trader (closed means for history) (optional) (default history)",
        "param3: <pending> Include non realized entry actives trades (optional)",
        "param4: <csv|json> Export format CSV or JSON (optional) (default csv)",
        "last: <filename> Specify the full-path filename (optional) (default "
        "siis_trades<_history><_market-id>.<format>)"
    )

    CHOICES = ("active", "history", "closed", "alert", "region", "strategy", "trader", "csv", "json", "pending")

    def __init__(self, strategy_service, trader_service):
        super().__init__('export', 'EX')

        self._strategy_service = strategy_service
        self._trader_service = trader_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        # ie: ":export BTCUSDT active"
        dataset = "history"
        market_id = None
        export_format = "json"
        pending = False
        filename = None

        arg_offset = 0

        if len(args) > 4:
            return False, "Too many parameters"

        if len(args) >= 1:
            # specific market
            strategy = self._strategy_service.strategy()
            if self._strategy_service:
                if args[0] in strategy.symbols_ids():
                    market_id = args[0]
                    arg_offset += 1

        for i, arg in enumerate(args[arg_offset:]):
            if arg == "active":
                dataset = "active"
            elif arg == "history" or arg == "closed":
                dataset = "history"
            elif arg == "alert":
                dataset = "alert"
            elif arg == "region":
                dataset = "region"
            elif arg == "strategy":
                dataset = "strategy"
            elif arg == "trader":
                dataset = "trader"

            elif arg == "pending":
                pending = True

            elif arg == "csv":
                export_format = "csv"
            elif arg == "json":
                export_format = "json"

            elif i+arg_offset == len(args)-1 and arg.endswith(".csv"):
                filename = arg
            elif i+arg_offset == len(args)-1 and arg.endswith(".json"):
                filename = arg

            else:
                return False, "Unsupported option %s" % arg

        if dataset == "trader":
            results = self._trader_service.command(Trader.COMMAND_EXPORT, {
                'dataset': dataset,
                'export-format': export_format,
                'filename': filename,
            })
        elif market_id:
            results = self._strategy_service.command(Strategy.COMMAND_TRADER_EXPORT, {
                'market-id': market_id,
                'dataset': dataset,
                'pending': pending,
                'export-format': export_format,
                'filename': filename,
            })
        else:
            results = self._strategy_service.command(Strategy.COMMAND_TRADER_EXPORT_ALL, {
                'dataset': dataset,
                'pending': pending,
                'export-format': export_format,
                'filename': filename,
            })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, list(UserExportCommand.CHOICES) + strategy.symbols_ids(), args, tab_pos,
                                    direction)
        elif len(args) > 1:
            return self.iterate(len(args) - 1, UserExportCommand.CHOICES, args, tab_pos, direction)

        return args, 0


class UserImportCommand(Command):
    SUMMARY = "to import actives trades, alerts, regions or trader state from a JSON file, "\
              "previously generated by export command"
    HELP = (
        "param1: <active|history|alert|region|strategy|trader> Active trade, history trades, alerts, region, "
        "strategy or trader",
        "param2: <filename> Specify the full-path filename (optional) (default siis_trades.json)"
    )

    CHOICES = ("active", "history", "closed", "alert", "region", "strategy", "trader")

    def __init__(self, strategy_service, trader_service):
        super().__init__('import', 'IM')

        self._strategy_service = strategy_service
        self._trader_service = trader_service

    def execute(self, args):
        # ie: ":import active siis_trades.json"
        dataset = ""
        filename = ""

        if len(args) > 2:
            return False, "Too many parameters"

        if len(args) == 1:
            dataset = args[0]

        elif len(args) == 2:
            dataset = args[0]
            filename = args[1]

        if not dataset or dataset not in UserImportCommand.CHOICES:
            return False, "Data-set must be specified"

        if dataset == "closed":
            dataset = "history"

        if not filename:
            if dataset == 'active':
                filename = "siis_trades.json"
            elif dataset == 'history':
                filename = "siis_history.json"
            elif dataset == 'alert':
                filename = "siis_alerts.json"
            elif dataset == 'region':
                filename = "siis_regions.json"
            elif dataset == 'strategy':
                filename = "siis_strategy.json"
            elif dataset == 'trader':
                filename = "siis_trader.json"

        if dataset == "trader":
            results = self._trader_service.command(Trader.COMMAND_IMPORT, {
                'dataset': dataset,
                'filename': filename,
            })
        else:
            results = self._strategy_service.command(Strategy.COMMAND_TRADER_IMPORT_ALL, {
                'dataset': dataset,
                'filename': filename,
            })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(len(args) - 1, UserImportCommand.CHOICES, args, tab_pos, direction)

        return args, 0


class SetQuantityCommand(Command):
    SUMMARY = "to change the traded quantity and scale factor per any or specific market"
    HELP = (
        "param1: <market-id> Market identifier (optional)",
        "param2: <quantity> Quantity base size",
    )

    def __init__(self, strategy_service):
        super().__init__('set-quantity', 'SETQTY')

        self._strategy_service = strategy_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        # ie: ":setquantity BTCUSDT 1000"
        action = "set-quantity"
        market_id = None

        if len(args) < 1:
            return False, "Missing parameters"

        if len(args) > 2:
            return False, "Too many parameters"

        is_float = True

        try:
            float(args[0])
        except ValueError:
            is_float = False

        if is_float:
            try:
                quantity = float(args[0])
            except ValueError:
                return False, "Invalid quantity format"
        else:
            market_id = args[0]

            try:
                quantity = float(args[1])
            except ValueError:
                return False, "Invalid quantity format"

        if quantity <= 0.0:
            return False, "Invalid quantity, must be greater than zero"

        if market_id:
            results = self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY, {
                'market-id': market_id,
                'action': action,
                'quantity': quantity
            })
        else:
            results = self._strategy_service.command(Strategy.COMMAND_TRADER_MODIFY_ALL, {
                'action': action,
                'quantity': quantity
            })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            if len(args) == 1:
                is_float = True

                try:
                    float(args[0])
                except ValueError:
                    is_float = False

                if is_float:
                    return args, 0

            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class CloseAllTradeCommand(Command):
    SUMMARY = "to close any current positions and trades (on a specified market or any)"
    HELP = (
        "param1: <market-id> Market identifier (optional)",
    )

    def __init__(self, strategy_service):
        super().__init__('!closeall', '!CLOSEALL')

        self._strategy_service = strategy_service

    def execute(self, args):
        # ie: ":closeall BTCUSDT"
        market_id = None

        if len(args) == 1:
            market_id = args[0]

        results = self._strategy_service.command(Strategy.COMMAND_TRADE_EXIT_ALL, {
            'market-id': market_id,
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class CancelAllPendingTradeCommand(Command):
    SUMMARY = "to cancel any pending trades, having empty realized quantity (on a specified market or any)"
    HELP = (
        "param1: <market-id> Market identifier (optional)",
    )

    def __init__(self, strategy_service):
        super().__init__('!cancelall', '!CANCELALL')

        self._strategy_service = strategy_service

    def execute(self, args):
        # ie: ":cancelall BTCUSDT"
        market_id = None

        if len(args) == 1:
            market_id = args[0]

        results = self._strategy_service.command(Strategy.COMMAND_TRADE_CANCEL_ALL_PENDING, {
            'market-id': market_id,
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class SellAllAssetCommand(Command):
    SUMMARY = "to sell at market, immediately any quantity available of free assets (for a specified market or any)"
    HELP = (
        "param1: <market-id> Market identifier (optional)",
    )

    def __init__(self, trader_service):
        super().__init__('!sellall', '!SELLALL')

        self._trader_service = trader_service

    def execute(self, args):
        # ie: ":sellall BTCUSDT"
        market_id = None

        if len(args) == 1:
            market_id = args[0]

        results = self._trader_service.command(Trader.COMMAND_SELL_ALL_ASSET, {
            'market-id': market_id,
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            trader = self._trader_service.trader()
            if trader:
                return self.iterate(0, trader.symbols_ids(), args, tab_pos, direction)

        return args, 0


class CancelAllOrderCommand(Command):
    SUMMARY = "to cancel any orders, immediately (for a specified market or any)"
    HELP = (
        "param1: <market-id> Market identifier (optional)",
    )

    CHOICES = ("spot-entry", "spot-exit", "spot", "margin-entry", "margin-exit", "margin", "entry", "exit")

    def __init__(self, trader_service):
        super().__init__('!rmallorder', '!RMALLORDER')

        self._trader_service = trader_service

    def execute(self, args):
        # ie: ":!rmallorder BTCUSDT"
        market_id = None
        options = set()
        arg_offset = 0

        if len(args) >= 1:
            # specific market
            trader = self._trader_service.trader()
            if trader:
                if args[0] in trader.symbols_ids():
                    market_id = args[0]
                    arg_offset += 1

        for arg in args[arg_offset:]:
            if arg not in CancelAllOrderCommand.CHOICES:
                return False, "Unsupported option %s" % arg

            if arg == "spot":
                options.add("spot-entry")
                options.add("spot-exit")

            if arg == "margin":
                options.add("margin-entry")
                options.add("margin-exit")

            if arg == "entry":
                options.add("spot-entry")
                options.add("margin-entry")

            if arg == "exit":
                options.add("spot-exit")
                options.add("margin-exit")

            else:
                options.add(arg)

        results = self._trader_service.command(Trader.COMMAND_CANCEL_ALL_ORDER, {
            'market-id': market_id,
            'options': tuple(options)
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            trader = self._trader_service.trader()
            if trader:
                return self.iterate(0, list(CancelAllOrderCommand.CHOICES) + trader.symbols_ids(), args, tab_pos,
                                    direction)
        elif len(args) > 1:
            return self.iterate(len(args) - 1, CancelAllOrderCommand.CHOICES, args, tab_pos, direction)

        return args, 0


class CancelOrderCommand(Command):
    SUMMARY = "<market-id> <order-id> to cancel a specific order, immediately"
    HELP = (
        "param1: <market-id> Market identifier",
        "param2: <order-id> Order identifier",
    )

    def __init__(self, trader_service):
        super().__init__('!rmorder', '!RMORDER')

        self._trader_service = trader_service

    def execute(self, args):
        # ie: ":!rmorder BTCUSDT xxx-yyy-zzz"
        if len(args) != 2:
            return False, "Missing parameters"

        market_id = args[0]
        order_id = args[1]

        results = self._trader_service.command(Trader.COMMAND_CANCEL_ORDER, {
            'market-id': market_id,
            'order-id': order_id
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            trader = self._trader_service.trader()
            if trader:
                return self.iterate(0, trader.symbols_ids(), args, tab_pos, direction)


class TickerMemSetCommand(Command):
    SUMMARY = "<market-id> to reset the mark on market to last price or any markets"
    HELP = (
        "param1: <market-id> Market identifier, optional",
    )

    def __init__(self, trader_service):
        super().__init__('memset', '!MS')

        self._trader_service = trader_service

    def execute(self, args):
        # ie: ":memset BTCUSDT"
        if len(args) == 0:
            results = self._trader_service.command(Trader.COMMAND_TICKER_MEMSET, {
                'market-id': None,
            })
        elif len(args) == 1:
            results = self._trader_service.command(Trader.COMMAND_TICKER_MEMSET, {
                'market-id': args[0],
            })
        else:
            return False, "Invalid parameters"

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            # market
            trader = self._trader_service.trader()
            if trader:
                return self.iterate(0, trader.symbols_ids(), args, tab_pos, direction)

        return args, 0


class ClosePositionCommand(Command):
    SUMMARY = "<position-key> to close at market a specific position, immediately"
    HELP = (
        "param1: <position-key> Position key",
    )

    def __init__(self, trader_service):
        super().__init__('!close-position', '!CP')

        self._trader_service = trader_service

    def execute(self, args):
        # ie: ":!CP 31"

        if len(args) != 1:
            return False, "Missing parameters"

        target = args[0]

        results = self._trader_service.command(Trader.COMMAND_CLOSE_MARKET, {
            'key': target
        })

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        return args, 0


class CloseAllPositionCommand(Command):
    SUMMARY = "to close at market all opened positions, immediately"

    def __init__(self, trader_service):
        super().__init__('!close-all-position', '!CLOSEALLPOSITION')

        self._trader_service = trader_service

    def execute(self, args):
        # ie: ":!CAP"

        if len(args) != 0:
            return False, "Invalid parameters"

        results = self._trader_service.command(Trader.COMMAND_CLOSE_ALL_MARKET, {})

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        return args, 0


class ReconnectCommand(Command):
    SUMMARY = "to force to reconnect"

    def __init__(self, watcher_service):
        super().__init__('reconnect', 'RECON')

        self._watcher_service = watcher_service

    def execute(self, args):
        # will force to try to reconnect
        if len(args) == 1:
            self._watcher_service.reconnect(args[0])
            return True, "Force reconnect for watcher %s" % args[0]

        self._watcher_service.reconnect()
        return True, "Force reconnect for any watchers"

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            watchers_ids = self._watcher_service.watchers_ids()
            return self.iterate(0, watchers_ids, args, tab_pos, direction)

        return args, 0


class RecheckCommand(Command):
    SUMMARY = "to force to recheck any trades"

    def __init__(self, strategy_service):
        super().__init__('recheck', 'RECHK')

        self._strategy_service = strategy_service

    def execute(self, args):
        # will force to recheck trades
        if len(args) > 1:
            return False, "Invalid parameters"

        if len(args) == 1:
            self._strategy_service.command(Strategy.COMMAND_TRADER_RECHECK, {
                'market-id': args[0]
            })

            return True, "Force to recheck any trades for %s" % args[0]

        results = self._strategy_service.command(Strategy.COMMAND_TRADER_RECHECK_ALL, {})

        return self.manage_results(results, "Force to recheck any trades for any markets")

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class SetReinvestGainCommand(Command):
    SUMMARY = "to enable, disable or configure the reinvest gain manager"
    HELP = (
        "param1: [on|off] Enable or disable for any strategy-traders",
        "param2: <context-id> related context identifier must be specified",
        "param3: <trade-quantity> initial trade quantity",
        "param4: <step-size> step size",
        "param5: <initial-total-qty> initial total quantity (optional)",
    )

    def __init__(self, strategy_service):
        super().__init__('set-reinvest-gain', 'SRG')

        self._strategy_service = strategy_service

    def execute(self, args):
        if len(args) < 1:
            return False, "Missing parameters"

        if len(args) > 5:
            return False, "Too many parameters"

        if args[0] not in ('on', 'off'):
            return False, "First parameter must be 'on' or 'off'"

        action = 'reinvest-gain' if args[0] == 'on' else 'normal'
        context = args[1]
        trade_quantity = 0.0
        initial_total_qty = None
        step = 0.0

        if action == 'reinvest-gain':
            if len(args) < 4:
                return False, "Missing parameters"

            try:
                trade_quantity = float(args[2])
            except ValueError:
                return False, "Trade quantity value must be decimal"

            if trade_quantity <= 0:
                return False, "Trade quantity value must be greater than zero"

            try:
                step = float(args[3])
            except ValueError:
                return False, "Step value must be decimal"

            if step <= 0:
                return False, "Step value must be greater than zero"

            if len(args) > 4:
                initial_total_qty = float(args[4])

                if initial_total_qty < 0:
                    return False, "Initial total quantity must be greater than zero"

        elif action == 'normal':
            if len(args) == 2:
                context = args[1]

        if not context:
            return False, "Context must be specified"

        results = self._strategy_service.command(Strategy.COMMAND_QUANTITY_GLOBAL_SHARE, {
            'action': action,
            'context': context,
            'trade-quantity': trade_quantity,
            'step': step,
            'initial-total-qty': initial_total_qty,
        })

        ok_message = "Modify reinvest gain for context %s" % context

        return self.manage_results(results, ok_message)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, ('on', 'off'), args, tab_pos, direction)

        return args, 0


class ScriptCommand(Command):
    SUMMARY = "to execute a python script file"
    HELP = (
        "param1: [exec|remove|unload] Execute a python script or remove an installable script",
        "param2: <module> python module to execute or to remove",
    )

    def __init__(self, watcher_service, trader_service, strategy_service, monitor_service, notifier_service):
        super().__init__('!script', '!SC')

        self._watcher_service = watcher_service
        self._trader_service = trader_service
        self._strategy_service = strategy_service
        self._monitor_service = monitor_service
        self._notifier_service = notifier_service

    def execute(self, args):
        if len(args) < 2:
            return False, "Missing parameters"

        if len(args) > 2:
            return False, "Too many parameters"

        if args[0] not in ('exec', 'remove', 'unload'):
            return False, "First parameter must be 'exec', 'remove' or 'unload'"

        action = args[0]
        module = args[1]

        if not module:
            return False, "Module must be specified"

        results = setup_script(action, module,
                               self._watcher_service, self._trader_service, self._strategy_service,
                               self._monitor_service, self._notifier_service)

        return self.manage_results(results)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            return self.iterate(0, ('exec', 'remove', 'unload'), args, tab_pos, direction)

        if len(args) <= 2 and args[0] in ('remove', 'unload'):
            modules = []

            for module in sys.modules.keys():
                if module.startswith('userscripts.'):
                    modules.append(module.split('.')[-1])

            return self.iterate(1, modules, args, tab_pos, direction)

        return args, 0


class RestartCommand(Command):
    SUMMARY = "to force to restart an instrument of the strategy"

    def __init__(self, strategy_service):
        super().__init__('restart', 'REST')

        self._strategy_service = strategy_service

    def execute(self, args):
        # will force to try to restart an instrument
        if len(args) < 1:
            return False, "Missing parameters"

        if len(args) > 1:
            return False, "Only one parameter is allowed"

        market_id = args[0]

        results = self._strategy_service.command(Strategy.COMMAND_TRADER_RESTART, {
            'market-id': market_id,
        })

        return self.manage_results(results, "Force restart for strategy on instrument %s" % args[0])

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


class SetTraderBalance(Command):
    SUMMARY = "Reset the trader balance in paper-mode only to a specific value."
    HELP = (
        "param1: <balance> new balance",
    )

    def __init__(self, trader_service):
        super().__init__('set-balance', None)

        self._trader_service = trader_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        if not self._trader_service.trader():
            return False, "No configured trader"

        if not self._trader_service.trader().paper_mode:
            return False, "Available only in paper-mode"

        if len(args) != 1:
            return False, "Missing parameter"

        try:
            balance = float(args[0])
        except ValueError:
            return False, "Invalid balance value format"

        if balance <= 0.0:
            return False, "Invalid balance value, must be greater than zero"

        self._trader_service.trader().account.set_balance(balance)

        return True, "Balance value updated"

    def completion(self, args, tab_pos, direction):
        return args, 0


class SetTraderMarketLeverage(Command):
    SUMMARY = "Set the leverage for a specific market if available."
    HELP = (
        "param1: <market-id> market identifier, symbol or alias",
        "param2: <leverage> new leverage",
    )

    def __init__(self, trader_service):
        super().__init__('set-leverage', None)

        self._trader_service = trader_service

    def execute(self, args):
        if not args:
            return False, "Missing parameters"

        if not self._trader_service.trader():
            return False, "No configured trader !"

        if (not self._trader_service.trader().account.account_type & self._trader_service.trader().account.TYPE_MARGIN
                == self._trader_service.trader().account.TYPE_MARGIN):
            return False, "Available only in margin trading !"

        if len(args) != 2:
            return False, "Invalid parameters"

        market_id = args[0]

        try:
            leverage = float(args[1])
        except ValueError:
            return False, "Invalid leverage value format"

        if not 1.0 <= leverage <= 500:
            return False, "Invalid leverage value (must be between 1 to 500)"

        market = self._trader_service.trader().market(market_id)
        if not market:
            return False, "Invalid market identifier or alias"

        if leverage > market.max_leverage:
            return False, "Must be at max %s for this market" % market.max_leverage

        if leverage < market.min_leverage:
            return False, "Must be at least %s for this market" % market.min_leverage

        market.margin_factor = 1.0 / leverage

        return True, "Market leverage updated %s to for %s" % (leverage, market_id)

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            # market
            trader = self._trader_service.trader()
            if trader:
                return self.iterate(0, trader.symbols_ids(), args, tab_pos, direction)

        return args, 0


def register_trading_commands(commands_handler, watcher_service, trader_service, strategy_service,
                              monitor_service, notifier_service):
    #
    # global
    #

    commands_handler.register(PlayCommand(strategy_service, notifier_service))
    commands_handler.register(PauseCommand(strategy_service, notifier_service))
    commands_handler.register(InfoCommand(strategy_service, notifier_service))
    commands_handler.register(UserSaveCommand(strategy_service))
    commands_handler.register(UserLoadCommand(strategy_service))
    commands_handler.register(UserExportCommand(strategy_service, trader_service))
    commands_handler.register(UserImportCommand(strategy_service, trader_service))
    commands_handler.register(SetQuantityCommand(strategy_service))
    commands_handler.register(SetAffinityCommand(strategy_service))
    commands_handler.register(SetOptionCommand(strategy_service))
    commands_handler.register(SetFrozenQuantityCommand(trader_service))

    commands_handler.register(ReconnectCommand(watcher_service))
    commands_handler.register(RestartCommand(strategy_service))
    commands_handler.register(RecheckCommand(strategy_service))

    commands_handler.register(SetReinvestGainCommand(strategy_service))

    commands_handler.register(ScriptCommand(watcher_service, trader_service, strategy_service,
                                            monitor_service, notifier_service))

    #
    # strategy, order operations
    #

    commands_handler.register(LongCommand(strategy_service))
    commands_handler.register(ShortCommand(strategy_service))
    commands_handler.register(CloseCommand(strategy_service))
    commands_handler.register(ModifyStopLossCommand(strategy_service))
    commands_handler.register(ModifyTakeProfitCommand(strategy_service))
    commands_handler.register(AssignCommand(strategy_service))
    commands_handler.register(CommentCommand(strategy_service))

    #
    # strategy multi-trade operations
    #

    commands_handler.register(CloseAllTradeCommand(strategy_service))
    commands_handler.register(CancelAllPendingTradeCommand(strategy_service))

    #
    # strategy, trade operations
    #

    commands_handler.register(CleanCommand(strategy_service))
    commands_handler.register(TradeInfoCommand(strategy_service))
    commands_handler.register(RemoveOperationCommand(strategy_service))
    commands_handler.register(StepStopLossOperationCommand(strategy_service))
    commands_handler.register(CheckTradeCommand(strategy_service))

    #
    # trader order operation
    #

    commands_handler.register(CancelOrderCommand(trader_service))
    commands_handler.register(TickerMemSetCommand(trader_service))
    commands_handler.register(ClosePositionCommand(trader_service))
    commands_handler.register(CloseAllPositionCommand(trader_service))

    #
    # trader operation
    #

    commands_handler.register(SetTraderBalance(trader_service))
    commands_handler.register(SetTraderMarketLeverage(trader_service))

    #
    # multi-trades operations
    #

    commands_handler.register(SellAllAssetCommand(trader_service))
    commands_handler.register(CancelAllOrderCommand(trader_service))
