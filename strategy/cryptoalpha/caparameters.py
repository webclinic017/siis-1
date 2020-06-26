# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Crypto Alpha strategy default parameters.

DEFAULT_PARAMS = {
    "reversal": True,
    "max-trades": 3,    # max number of simultaned trades for a same market
    "trade-delay": 30,  # at least wait 30 seconds before sending another signal 
    "min-traded-timeframe": "1m",
    "max-traded-timeframe": "1m",
    "sltp-timeframe": "1h",
    "ref-timeframe": "4h",
    "min-vol24h": 100,        # 100 BTC per 24h
    "min-price": 0.00000069,  # or 69 sats
    "region-allow": False,    # don"t trade if no defined region
    "timeframes": {
        "weely": {
            "timeframe": "1w",
            "mode": "C",
            "depth": 22,
            "history": 22,
            "score-ratio": 8,
            "score-level": 0.05,
            "update-at-close": False,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 1,),
                "volume": ("volume", 0,),
                "rsi": ("rsi", 21,),
                "stochrsi": ("stochrsi", 13, 13, 13),
                "sma": ("sma", 21,),
                "ema": ("ema", 21,),
                "hma": None,
                "vwma": ("vwma", 21,),
                "momentum": ("momentum", 21,),
                "stochastic": None,
                "macd": None,  # ("macd", 21,),
                "bollingerbands": None, # (""bollingerbands", 21,),
                "triangle": None,
                "fibonacci": None,  # ("fibonacci", 15,),
                "pivotpoint": ("pivotpoint", 3,),
                "tomdemark": None,
                "atr": ("atr", 14, 2.618),
            },
            "constants": {
                "rsi_low": 30,
                "rsi_high": 70,
            },
        },
        "daily": {
            "timeframe": "1d",
            "mode": "C",
            "depth": 22,
            "history": 22,
            "score-ratio": 8,
            "score-level": 0.05,
            "update-at-close": False,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 1,),
                "volume": ("volume", 0,),
                "rsi": ("rsi", 21,),
                "stochrsi": ("stochrsi", 13, 13, 13),
                "sma": ("sma", 20,),
                "ema": ("ema", 20,),
                "hma": None,
                "vwma": ("vwma", 20,),
                "momentum": ("momentum", 20,),
                "stochastic": None,
                "macd": None,  # ("macd", 21,),
                "bollingerbands": ("bollingerbands", 21,),
                "triangle": None,
                "fibonacci": None,  # ("fibonacci", 15,),
                "pivotpoint": ("pivotpoint", 3,),
                "tomdemark": ("tomdemark", 9),
                "atr": ("atr", 14, 2.618),
            },
            "constants": {
                "rsi_low": 30,
                "rsi_high": 70,
            },
        },
        "4hour": {
            "timeframe": "4h",
            "mode": "A",
            "depth": 56,
            "history": 56,
            "score-ratio": 6,
            "score-level": 0.05,
            "update-at-close": False,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 1,),
                "volume": ("volume", 0,),
                "rsi": ("rsi", 21,),
                "stochrsi": ("stochrsi", 13, 13, 13),
                "sma": ("sma", 21,),
                "ema": ("ema", 55,),
                "hma": None,
                "vwma": ("vwma", 21,),
                "momentum": ("momentum", 21,),
                "stochastic": None,
                "macd": None,  # ("macd", 21,),
                "bollingerbands": ("bollingerbands", 21,),
                "triangle": None,
                "fibonacci": None,  # ("fibonacci", 15,),
                "pivotpoint": ("pivotpoint", 3,),
                "tomdemark": ("tomdemark", 9),
                "atr": ("atr", 14, 2.618),
            },
            "constants": {
                "rsi_low": 30,
                "rsi_high": 70,
            }   
        },
        "hourly": {
            "timeframe": "1h,"
            "mode": "A",
            "depth": 22,
            "history": 22,
            "score-ratio": 4,
            "score-level": 0.05,
            "update-at-close": False,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 1,),
                "volume": ("volume", 0,),
                "rsi": ("rsi", 21,),
                "stochrsi": ("stochrsi", 13, 13, 13),
                "sma": ("sma", 21,),
                "ema": ("ema", 21,),
                "hma": None,
                "vwma": ("vwma", 21,),
                "momentum": ("momentum", 21,),
                "stochastic": None,
                "macd": None,  # ("macd", 17,),
                "bollingerbands": ("bollingerbands", 21,),
                "triangle": None,
                "fibonacci": None,  # ("fibonacci", 15,),
                "pivotpoint": ("pivotpoint", 3,),
                "tomdemark": ("tomdemark", 9),
                "atr": ("atr", 14, 2.618),
                "mama": ("mama", 0.5, 0.05),
            },
            "constants": {
                "rsi_low": 30,
                "rsi_high": 70,
            }
        },
        "15min": {
            "timeframe": "15m",
            "mode": "A",
            "depth": 22,
            "history": 22,
            "score-ratio": 2,
            "score-level": 0.05,
            "update-at-close": False,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 1,),
                "volume": ("volume", 0,),
                "rsi": ("rsi", 21,),
                "stochrsi": ("stochrsi", 13, 13, 13),
                "sma": ("sma", 21,),
                "ema": ("ema", 21,),
                "hma": None,
                "vwma": ("vwma", 21,),
                "momentum": ("momentum", 21,),
                "stochastic": None,
                "macd": None,  # ("macd", 17,),
                "bollingerbands": ("bollingerbands", 21,),
                "triangle": None,
                "fibonacci": None,  # ("fibonacci", 15,),
                "pivotpoint": ("pivotpoint", 3,),
                "tomdemark": ("tomdemark", 9),
                "atr": ("atr", 14, 2.618),
            },
            "constants": {
                "rsi_low": 30,
                "rsi_high": 70,
            }
        },
        "5min": {
            "timeframe": "5m",
            "mode": "A",
            "depth": 14,
            "history": 14,
            "score-ratio": 1,
            "score-level": 0.05,
            "update-at-close": False,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 1,),
                "volume": ("volume", 0,),
                "rsi": ("rsi", 13,),
                "stochrsi": ("stochrsi", 13, 13, 13),
                "sma": ("sma", 13,),
                "ema": ("ema", 13,),
                "hma": None,
                "vwma": ("vwma", 13,),
                "momentum": ("momentum", 13,),
                "stochastic": None,
                "macd": None,  # ("macd", 17,),
                "bollingerbands": ("bollingerbands", 13,),
                "triangle": None,
                "fibonacci": None,  # ("fibonacci", 15,),
                "pivotpoint": ("pivotpoint", 3,),
                "tomdemark": ("tomdemark", 9),
                "atr": ("atr", 14, 2.618),
            },
            "constants": {
                "rsi_low": 30,
                "rsi_high": 70,
            }
        },
        "1min": {
            "timeframe": "1m,"
            "mode": "A",
            "depth": 20,
            "history": 20,
            "score-ratio": 0.5,
            "score-level": 0.05,
            "update-at-close": True,
            "signal-at-close": True,
            "indicators": {
                "price": ("price", 1,),
                "volume": ("volume", 0,),
                "rsi": ("rsi", 8,),
                "stochrsi": ("stochrsi", 13, 13, 13),
                "sma": ("sma", 20,),
                "ema": ("ema", 8,),
                "hma": ("hma", 8,),
                "vwma": ("vwma", 8,),
                "momentum": ("momentum", 20,),
                "stochastic": None,
                "macd": None,  # ("macd", 17,),
                "bollingerbands": None, # ("bollingerbands", 26,),
                "triangle": None,
                "fibonacci": None,  # ("fibonacci", 15,),
                "pivotpoint": ("pivotpoint", 3,),
                "tomdemark": ("tomdemark", 9),
                "atr": ("atr", 14, 2.618),
            },
            "constants": {
                "rsi_low": 30,
                "rsi_high": 70,
            }
        }
    }
}
