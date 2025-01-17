# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Siis standard implementation of the application (application main)

from __init__ import APP_VERSION, APP_SHORT_NAME, APP_RELEASE

import signal
import sys
import os
import time
import logging
import traceback

from datetime import datetime

from common.utils import parse_utc_datetime, fix_thread_set_name

from watcher.service import WatcherService

from notifier.notifier import Notifier
from trader.service import TraderService
from strategy.service import StrategyService
from monitor.service import MonitorService
from notifier.service import NotifierService
from common.watchdog import WatchdogService
from tools.tool import Tool

from terminal.terminal import Terminal
from terminal.command import CommandsHandler

from database.database import Database

from common.siislog import SiisLog

from view.service import ViewService
from view.defaultviews import setup_default_views

from app.help import display_cli_help, display_welcome
from app.setup import install
from app.generalcommands import register_general_commands
from app.tradingcommands import register_trading_commands
from app.regioncommands import register_region_commands
from app.alertcommands import register_alert_commands


def signal_handler(sig, frame):
    if Terminal.inst():
        Terminal.inst().action('Type command :quit<ENTER> to exit !', view='status')


def terminate(watchdog_service, watcher_service, trader_service, strategy_service, monitor_service,
              view_service, notifier_service):
    if watcher_service:
        watcher_service.terminate()
    if trader_service:
        trader_service.terminate()
    if strategy_service:
        strategy_service.terminate()
    if monitor_service:
        monitor_service.terminate()
    if view_service:
        view_service.terminate()
    if notifier_service:
        notifier_service.terminate()

    Database.terminate()

    if watchdog_service:
        watchdog_service.terminate()


def application(argv):
    fix_thread_set_name()

    # init terminal display
    Terminal.inst()

    options = {
        'working-path': os.getcwd(),
        'identity': 'real',
        'config-path': './user/config',
        'log-path': './user/log',
        'reports-path': './user/reports',
        'markets-path': './user/markets',
        'log-name': 'siis.log',
        'monitor': False,      # startup HTTP/WS monitor service
        'monitor-port': None,  # monitoring HTTP port (WS is HTTP+1
        'verbose': False,      # verbose mode for tools
        'load': False          # load user data at startup from database
    }

    # create initial siis data structure if necessary
    install(options)

    siis_log = SiisLog(options, Terminal.inst().style())
    siis_logger = logging.getLogger('siis')
    traceback_logger = logging.getLogger('siis.traceback')

    # parse process command line
    if len(argv) > 1:
        options['livemode'] = True

        # utc or local datetime ?
        for arg in argv:
            if arg.startswith('--'):
                if arg == '--paper-mode':
                    # livemode but in paper-mode
                    options['paper-mode'] = True            

                elif arg == '--verbose':
                    # verbose display for tools
                    options['verbose'] = True

                elif arg == '--load':
                    # load trader and trade user data at startup
                    options['load'] = True

                elif arg == '--fetch':
                    # use the fetcher
                    options['tool'] = "fetcher"
                elif arg == '--binarize':
                    # use the binarizer
                    options['tool'] = "binarizer"
                elif arg == '--optimize':
                    # use the optimizer
                    options['tool'] = "optimizer"
                elif arg == '--sync':
                    # use the syncer
                    options['tool'] = "syncer"
                elif arg == '--rebuild':
                    # use the rebuilder
                    options['tool'] = "rebuilder"
                elif arg == '--export':
                    # use the exporter
                    options['tool'] = "exporter"
                elif arg == '--import':
                    # use the importer
                    options['tool'] = "importer"
                elif arg == '--clean':
                    # use the cleaner
                    options['tool'] = "cleaner"
                elif arg == '--statistics':
                    # use the statistics tool
                    options['tool'] = "statistics"
                elif arg == '--history':
                    # use the history tool
                    options['tool'] = "history"
                elif arg.startswith("--tool="):
                    # use a named tool
                    options['tool'] = arg.split('=')[1]

                elif arg == '--no-conf':
                    options['no-conf'] = True
                elif arg == '--zip':
                    options['zip'] = True
                elif arg == '--update':
                    options['update'] = True

                elif arg == '--monitor':
                    # use the importer
                    options['monitor'] = True
                elif arg.startswith('--monitor-port='):
                    # override monitor HTTP port (+1 for WS port)
                    options['monitor-port'] = int(arg.split('=')[1])

                elif arg == '--install-market':
                    # fetcher option
                    options['install-market'] = True
                elif arg == '--initial-fetch' or arg == '--prefetch':
                    # do the initial OHLC fetch for watchers (syncer, watcher), default False
                    options['initial-fetch'] = True
                elif arg == '--store-trade':
                    # store trade/quote/tick during watcher process (watcher), default False
                    options['store-trade'] = True
                elif arg == '--store-ohlc' or arg == '--store-candle':
                    # store OHLCs during watcher process (watcher), default False
                    options['store-ohlc'] = True

                elif arg == '--backtest':
                    # backtest mean always paper-mode
                    options['paper-mode'] = True
                    options['backtesting'] = True
                elif arg.startswith('--timestep='):
                    # backtesting timestep, default is 60 second
                    options['timestep'] = float(arg.split('=')[1])
                elif arg.startswith('--time-factor='):
                    # backtesting time-factor
                    options['time-factor'] = float(arg.split('=')[1])

                elif arg == '--preprocess':
                    # preprocess the indicators for the next backtest or live running
                    options['preprocess'] = True

                elif arg.startswith('--filename='):
                    # used with import or export
                    options['filename'] = arg.split('=')[1]

                elif arg.startswith('--from='):
                    # if backtest from date and tools
                    options['from'] = parse_utc_datetime(arg.split('=')[1])
                    if not options['from']:
                        Terminal.inst().error("Invalid 'from' datetime format")
                        sys.exit(-1)
                elif arg.startswith('--to='):
                    # if backtest to date and tools
                    options['to'] = parse_utc_datetime(arg.split('=')[1])
                    if not options['to']:
                        Terminal.inst().error("Invalid 'to' datetime format")
                        sys.exit(-1)
                elif arg.startswith('--last='):
                    # fetch the last n data history
                    options['last'] = int(arg.split('=')[1])
                    if options['last'] <= 0:
                        Terminal.inst().error("Invalid 'last' value. Must be at least 1")
                        sys.exit(-1)

                elif arg.startswith('--market='):
                    # fetch, binarize, optimize the data history for this market
                    options['market'] = arg.split('=')[1]
                elif arg.startswith('--spec='):
                    # fetcher data history option
                    options['option'] = arg.split('=')[1]
                elif arg.startswith('--delay='):
                    # fetcher data history fetching delay between two calls
                    options['delay'] = float(arg.split('=')[1])
                elif arg.startswith('--broker='):
                    # broker name for fetcher, watcher, optimize, binarize
                    options['broker'] = arg.split('=')[1]
                elif arg.startswith('--timeframe='):
                    # fetch, binarize, optimize base timeframe
                    options['timeframe'] = arg.split('=')[1]
                elif arg.startswith('--cascaded='):
                    # fetch cascaded ohlc generation
                    options['cascaded'] = arg.split('=')[1]
                elif arg.startswith('--target='):
                    # target ohlc generation
                    options['target'] = arg.split('=')[1]

                elif arg == '--watcher-only':
                    # feed only with live data, does not run the trader and strategy services
                    options['watcher-only'] = True              

                elif arg.startswith('--profile='):
                    # profile name
                    options['profile'] = arg.split('=')[1]

                elif arg == '--version':
                    Terminal.inst().info('%s %s release %s' % (
                        APP_SHORT_NAME, '.'.join([str(x) for x in APP_VERSION]), APP_RELEASE))
                    sys.exit(0)

                elif arg == '--help' or arg == '-h':
                    display_cli_help()
                    sys.exit(0)
            else:
                options['identity'] = argv[1]

        # backtesting
        if options.get('backtesting', False):
            if options.get('from') is None or options.get('to') is None:
                del options['backtesting']
                Terminal.inst().error("Backtesting need from= and to= date time")
                sys.exit(-1)

    #
    # tool mode
    #

    # @todo merge as Tool model
    if options.get('tool') == "binarizer":
        if options.get('market') and options.get('from') and options.get('to') and options.get('broker'):
            from tools.binarizer import do_binarizer
            do_binarizer(options)
        else:
            sys.exit(-1)

        sys.exit(0)

    # @todo merge as Tool model
    if options.get('tool') == "fetcher":
        if options.get('market') and options.get('broker'):
            from tools.fetcher import do_fetcher
            do_fetcher(options)
        else:
            sys.exit(-1)

        sys.exit(0)

    # @todo merge as Tool model
    if options.get('tool') == "optimizer":
        if options.get('market') and options.get('from') and options.get('broker'):
            from tools.optimizer import do_optimizer
            do_optimizer(options)
        else:
            sys.exit(-1)

        sys.exit(0)

    # @todo merge as Tool model
    if options.get('tool') == "rebuilder":
        if options.get('market') and options.get('from') and options.get('broker') and options.get('timeframe'):
            from tools.rebuilder import do_rebuilder
            do_rebuilder(options)
        else:
            sys.exit(-1)

        sys.exit(0)

    # @todo merge as Tool model
    if options.get('tool') == "exporter":
        if options.get('market') and options.get('from') and options.get('broker') and options.get('filename'):
            from tools.exporter import do_exporter
            do_exporter(options)
        else:
            sys.exit(-1)

        sys.exit(0)

    # @todo merge as Tool model
    if options.get('tool') == "importer":
        if options.get('filename'):
            from tools.importer import do_importer
            do_importer(options)
        else:
            sys.exit(-1)

        sys.exit(0)

    if options.get('tool'):
        ToolClazz = Tool.load_tool(options.get('tool'))
        if ToolClazz:
            if ToolClazz.need_identity():
                if options['identity'].startswith('-'):
                    Terminal.inst().error("First option must be the identity name")
                    Terminal.inst().flush()

                    sys.exit(-1)

            tool = ToolClazz(options)

            if not tool.check_options(options):
                sys.exit(-1)

            if ToolClazz.need_identity():
                Terminal.inst().info("Starting SIIS %s using %s identity..." % (
                    options.get('tool'), options['identity']))
            else:
                Terminal.inst().info("Starting SIIS %s..." % options.get('tool'))

            Terminal.inst().flush()

            tool.execute(options)

            Terminal.inst().info("%s done!" % (ToolClazz.alias() or options.get('tool')).capitalize())
            Terminal.inst().flush()

            Terminal.terminate()

            sys.exit(0)
        else:
            sys.exit(-1)

    #
    # normal mode
    #

    if options['identity'].startswith('-'):
        Terminal.inst().error("First option must be the identity name")

    Terminal.inst().info("Starting SIIS using %s identity..." % options['identity'])
    Terminal.inst().action("- type ':quit<Enter>' to terminate")
    Terminal.inst().action("- type ':h<Enter> or :help<Enter>' to display help")
    Terminal.inst().flush()

    if options.get('backtesting'):  
        Terminal.inst().notice("Process a backtesting.")
    else:
        Terminal.inst().notice("Process on real time.")

    if options.get('paper-mode'):
        Terminal.inst().notice("- Using paper-mode trader.")
    else:
        Terminal.inst().notice("- Using live-mode trader.")

    signal.signal(signal.SIGINT, signal_handler)

    #
    # application
    #

    # application services

    watchdog_service = WatchdogService(options)  
    monitor_service = MonitorService(options)
    view_service = ViewService(options)
    notifier_service = NotifierService(options)
    watcher_service = WatcherService(monitor_service, options)
    trader_service = TraderService(watcher_service, monitor_service, options)
    strategy_service = StrategyService(watcher_service, trader_service, monitor_service, options)

    # watchdog service
    Terminal.inst().info("Starting watchdog service...")
    try:
        watchdog_service.start(options)
    except Exception as e:
        Terminal.inst().error(str(e))
        terminate(watchdog_service, watcher_service, trader_service, strategy_service, monitor_service,
                  view_service, notifier_service)
        sys.exit(-1)

    # monitoring service
    if options['monitor']:
        Terminal.inst().info("Starting monitor service...")
        try:
            monitor_service.setup(watcher_service, trader_service, strategy_service, view_service)
            monitor_service.start(options)
            watchdog_service.add_service(monitor_service)
        except Exception as e:
            Terminal.inst().error(str(e))
            terminate(watchdog_service, watcher_service, trader_service, strategy_service, monitor_service,
                      view_service, notifier_service)
            sys.exit(-1)

    # notifier service
    try:
        notifier_service.start(options)
    except Exception as e:
        Terminal.inst().error(str(e))
        terminate(watchdog_service, watcher_service, trader_service, strategy_service, monitor_service,
                  view_service, notifier_service)
        sys.exit(-1)

    # view service
    # try:
    #     watchdog_service.add_service(view_service)
    # except Exception as e:
    #     Terminal.inst().error(str(e))
    #     terminate(watchdog_service, watcher_service, trader_service, strategy_service, monitor_service,
    #               view_service, notifier_service)
    #     sys.exit(-1)

    # database manager
    try:
        Database.create(options)
        Database.inst().setup(options)
    except Exception as e:
        Terminal.inst().error(str(e))
        terminate(watchdog_service, watcher_service, trader_service, strategy_service, monitor_service,
                  view_service, notifier_service)
        sys.exit(-1)

    # watcher service
    Terminal.inst().info("Starting watcher service...")
    try:
        watcher_service.start(options)
        watchdog_service.add_service(watcher_service)
    except Exception as e:
        Terminal.inst().error(str(e))
        terminate(watchdog_service, watcher_service, trader_service, strategy_service, monitor_service,
                  view_service, notifier_service)
        sys.exit(-1)

    # trader service
    Terminal.inst().message("Starting trader service...")
    try:
        trader_service.start(options)
        watchdog_service.add_service(trader_service)
    except Exception as e:
        Terminal.inst().error(str(e))
        terminate(watchdog_service, watcher_service, trader_service, strategy_service, monitor_service,
                  view_service, notifier_service)
        sys.exit(-1)

    # want to display desktop notification and update views
    watcher_service.add_listener(view_service)

    # want to display desktop notification and update views
    trader_service.add_listener(view_service)

    # trader service listen to watcher service and update views
    watcher_service.add_listener(trader_service)

    # strategy service
    Terminal.inst().message("Starting strategy service...")
    try:
        strategy_service.start(options)
        watchdog_service.add_service(strategy_service)
    except Exception as e:
        Terminal.inst().error(str(e))
        terminate(watchdog_service, watcher_service, trader_service, strategy_service, monitor_service,
                  view_service, notifier_service)
        sys.exit(-1)

    # want to be notifier of system errors
    watchdog_service.add_listener(notifier_service)

    # strategy service listen to watcher service
    watcher_service.add_listener(strategy_service)

    # want to display watchdog notification, strategy service listen to trader service
    trader_service.add_listener(notifier_service)
    trader_service.add_listener(strategy_service)

    # want to display desktop notification, update view and notify on discord
    strategy_service.add_listener(notifier_service)
    strategy_service.add_listener(view_service)

    # want signal and important notifications
    notifier_service.set_strategy_service(strategy_service)
    notifier_service.set_trader_service(trader_service)

    # register terminal commands
    commands_handler = CommandsHandler()
    commands_handler.init(options)

    # cli commands registration
    register_general_commands(commands_handler)
    register_trading_commands(commands_handler, watcher_service, trader_service, strategy_service,
                              monitor_service, notifier_service)
    register_region_commands(commands_handler, strategy_service)
    register_alert_commands(commands_handler, strategy_service)

    # # setup and start the monitor service
    # monitor_service.setup(watcher_service, trader_service, strategy_service)
    # try:
    #     monitor_service.start(options)
    #     watchdog_service.add_service(monitor_service)
    # except Exception as e:
    #     Terminal.inst().error(str(e))
    #     terminate(watchdog_service, watcher_service, trader_service, strategy_service, monitor_service,
    #               view_service, notifier_service)
    #     sys.exit(-1)

    Terminal.inst().message("Running main loop...")

    Terminal.inst().upgrade()
    Terminal.inst().message("Steady...", view='notice')

    if view_service:
        # setup the default views
        try:
            setup_default_views(view_service, watcher_service, trader_service, strategy_service)
        except Exception as e:
            Terminal.inst().error(str(e))
            terminate(watchdog_service, watcher_service, trader_service, strategy_service, monitor_service,
                      view_service, notifier_service)
            sys.exit(-1)

    display_welcome()

    LOOP_SLEEP = 0.016  # in second
    MAX_CMD_ALIVE = 5   # in second

    running = True

    value = None
    value_changed = False
    command_timeout = 0
    prev_timestamp = 0

    try:
        while running:
            # keyboard input commands
            try:
                c = Terminal.inst().read()
                key = Terminal.inst().key()

                if c:
                    # split the command line
                    args = [arg for arg in (value[1:].split(' ') if value and value.startswith(':') else []) if arg]
                    if value and value[-1] == ' ':
                        args.append('')

                    # update the current type command
                    if Terminal.inst().mode == Terminal.MODE_COMMAND:
                        commands_handler.process_char(c, args)

                    # only in normal mode
                    if Terminal.inst().mode == Terminal.MODE_DEFAULT:
                        view_service.on_char(c)

                if key:
                    if key == 'KEY_ESCAPE':
                        # cancel command
                        value = None
                        value_changed = True
                        command_timeout = 0

                    # split the command line
                    args = [arg for arg in (value[1:].split(' ') if value and value.startswith(':') else []) if arg]
                    if value and value[-1] == ' ':
                        args.append('')

                    # process on the arguments
                    args = commands_handler.process_key(key, args, Terminal.inst().mode == Terminal.MODE_COMMAND)

                    if args:
                        # regen the updated command line
                        value = ":" + ' '.join(args)
                        value_changed = True
                        command_timeout = 0

                    view_service.on_key_pressed(key)

                    if key == 'KEY_ESCAPE':
                        # was in command mode, now in default mode
                        Terminal.inst().set_mode(Terminal.MODE_DEFAULT)

                # @todo move the rest to command_handler
                if c:
                    if value and value[0] == ':':
                        if c == '\b':
                            # backspace, erase last command char
                            value = value[:-1] if value else None
                            value_changed = True
                            command_timeout = time.time()

                        elif c != '\n':
                            # append to the advanced command value
                            value += c
                            value_changed = True
                            command_timeout = time.time()

                        elif c == '\n':
                            result = commands_handler.process_cli(value)
                            command_timeout = 0

                            if not result:
                                # maybe an application level command
                                if value.startswith(':quit'):
                                    opts = value.split(' ')

                                    if opts[0] == ':quit':
                                        strategy_service.set_save_on_exit('save' in opts)
                                        strategy_service.set_terminate_on_exit('term' in opts)

                                        running = False

                            # clear command value
                            value_changed = True
                            value = None

                            # use default mode
                            Terminal.inst().set_mode(Terminal.MODE_DEFAULT)

                    elif c != '\n':
                        # initial command value
                        value = "" + c
                        value_changed = True
                        command_timeout = time.time()

                        if value and value[0] == ':':
                            # use command mode
                            Terminal.inst().set_mode(Terminal.MODE_COMMAND)

                    if value and value[0] != ':':
                        # direct key

                        # use default mode
                        Terminal.inst().set_mode(Terminal.MODE_DEFAULT)

                        try:
                            result = commands_handler.process_accelerator(key)

                            # @todo convert to Command object accelerator
                            # used : ABCDFIMNOPQRSTWXZ? an%,;:!
                            # unused : EGHJKLUVY
                            if not result:
                                result = True

                                # display views @todo must be managed by view_service
                                if value == 'A':
                                    Terminal.inst().switch_view('account')
                                elif value == 'B':
                                    Terminal.inst().switch_view('activealert')
                                elif value == 'C':
                                    Terminal.inst().clear_content()
                                elif value == 'D':
                                    Terminal.inst().switch_view('debug')
                                elif value == 'F':
                                    Terminal.inst().switch_view('strategy')
                                elif value == 'I':
                                    Terminal.inst().switch_view('content')
                                elif value == 'M':
                                    Terminal.inst().switch_view('market')
                                elif value == 'N':
                                    Terminal.inst().switch_view('signal')
                                elif value == 'O':
                                    Terminal.inst().switch_view('order')
                                elif value == 'P':
                                    Terminal.inst().switch_view('perf')
                                elif value == 'Q':
                                    Terminal.inst().switch_view('asset')
                                elif value == 'R':
                                    Terminal.inst().switch_view('region')
                                elif value == 'S':
                                    Terminal.inst().switch_view('stats')
                                elif value == 'T':
                                    Terminal.inst().switch_view('ticker')
                                elif value == 'W':
                                    Terminal.inst().switch_view('alert')
                                elif value == 'X':
                                    Terminal.inst().switch_view('position')
                                elif value == 'Z':
                                    Terminal.inst().switch_view('traderstate')

                                elif value == '?':
                                    # ping services and workers
                                    watchdog_service.ping(1.0)

                                elif value == ' ':
                                    # toggle play/pause on backtesting
                                    if strategy_service.backtesting:
                                        results = strategy_service.toggle_play_pause()
                                        Terminal.inst().notice("Backtesting now %s" % (
                                            "play" if results else "paused"), view='status')

                                elif value == 'a':
                                    if notifier_service:
                                        results = notifier_service.command(Notifier.COMMAND_TOGGLE, {
                                            'notifier': "desktop", 'value': "audible"})
                                        if results and not results.get('error'):
                                            Terminal.inst().notice(results['messages'], view='status')
                                elif value == 'n':
                                    if notifier_service:
                                        results = notifier_service.command(Notifier.COMMAND_TOGGLE, {
                                            'notifier': "desktop", 'value': "popup"})
                                        if results and not results.get('error'):
                                            Terminal.inst().notice(results['messages'], view='status')

                                elif value == '*':
                                    if view_service:
                                        view_service.toggle_opt1()
                                elif value == '$':
                                    if view_service:
                                        view_service.toggle_opt2()
                                elif value == '%':
                                    if view_service:
                                        view_service.toggle_percent()
                                elif value == '=':
                                    if view_service:
                                        view_service.toggle_table()
                                elif value == ',':
                                    if view_service:
                                        view_service.toggle_group()
                                elif value == ';':
                                    if view_service:
                                        view_service.toggle_order()
                                elif value == '!':
                                    if view_service:
                                        view_service.toggle_datetime_format()
                                else:
                                    result = False

                            if result:
                                value = None
                                value_changed = True
                                command_timeout = 0

                        except Exception as e:
                            siis_logger.error(repr(e))
                            traceback_logger.error(traceback.format_exc())

            except IOError:
                pass
            except Exception as e:
                siis_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

            try:
                # display advanced command only
                if value_changed:
                    if value and value.startswith(':'):        
                        Terminal.inst().message("Command: %s" % value[1:], view='command')
                    else:
                        Terminal.inst().message("", view='command')

                # clear input if no char hit during the last MAX_CMD_ALIVE
                if value and not value.startswith(':'):
                    if (command_timeout > 0) and (time.time() - command_timeout >= MAX_CMD_ALIVE):
                        value = None
                        value_changed = True
                        Terminal.inst().info("Current typing canceled", view='status')

                # display strategy trading time (update max once per second)
                if strategy_service.timestamp - prev_timestamp >= 1.0:
                    mode = "live"
                    if trader_service.backtesting:
                        mode = "backtesting" + (" (paused)" if not strategy_service.backtesting_play else "")
                    elif trader_service.paper_mode:
                        mode = "paper-mode"

                    Terminal.inst().message("%s - %s" % (mode, datetime.fromtimestamp(
                        strategy_service.timestamp).strftime('%Y-%m-%d %H:%M:%S')), view='notice')
                    prev_timestamp = strategy_service.timestamp

                # synchronous operations here
                watcher_service.sync()
                trader_service.sync()
                strategy_service.sync()

                if monitor_service:
                    monitor_service.sync()

                if view_service:
                    view_service.sync()

                if notifier_service:
                    notifier_service.sync()

                Terminal.inst().update()

                # don't waste CPU time on main thread
                time.sleep(LOOP_SLEEP)

            except Exception as e:
                siis_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())           

    finally:
        Terminal.inst().restore_term()

    Terminal.inst().info("Terminate...")
    Terminal.inst().flush() 

    commands_handler.terminate(options) if commands_handler else None
    commands_handler = None

    # service terminate
    monitor_service.terminate() if monitor_service else None
    strategy_service.terminate() if strategy_service else None
    trader_service.terminate() if trader_service else None
    watcher_service.terminate() if watcher_service else None
    view_service.terminate() if view_service else None
    notifier_service.terminate() if notifier_service else None

    MonitorService.stop_reactor()

    Terminal.inst().info("Flushing database...")
    Terminal.inst().flush() 

    Database.terminate()
    Terminal.inst().info("Database done !")

    watchdog_service.terminate() if watchdog_service else None

    Terminal.inst().info("Bye (could wait a little...) !")
    Terminal.inst().flush()

    Terminal.terminate()


if __name__ == "__main__":
    application(sys.argv)
