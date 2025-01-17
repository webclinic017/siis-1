# @date 2018-09-02
# @author Frederic Scherma, All rights reserved without prejudices.
# @author Xavier BONNIN
# @license Copyright (c) 2018 Dream Overflow
# @brief Moving Average Convergence Divergence indicator

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample, MMexp_n  # , MM_n
from talib import MACD as ta_MACD

import numpy as np


class MACDIndicator(Indicator):
    """
    Moving Average Convergence Divergence indicator
    https://fr.wikipedia.org/wiki/MACD
    """

    __slots__ = '_short_l', '_long_l', '_signal_l', '_prev_macd', '_last_macd', '_prev_signal', '_last_signal', \
                '_macds', '_signals', '_hists'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OVERLAY

    def __init__(self, timeframe, short_l=12, long_l=26, signal_l=9):
        super().__init__("macd", timeframe)
        
        self._short_l = short_l    # fastest periods number
        self._long_l = long_l      # slowest periods number
        self._signal_l = signal_l  # signal periods number

        self._prev_macd = 0.0
        self._last_macd = 0.0

        self._prev_signal = 0.0
        self._last_signal = 0.0

        self._macds = np.array([])
        self._signals = np.array([])
        self._hists = np.array([])

    @property
    def prev_macd(self):
        return self._prev_macd

    @property
    def last_macd(self):
        return self._last_macd

    @property
    def last_signal(self):
        return self._last_signal

    @property
    def prev_signal(self):
        return self._prev_signal

    @property
    def short_length(self):
        return self._short_l
    
    @short_length.setter
    def short_length(self, length):
        self._short_l = length

    @property
    def long_length(self):
        return self._long_l

    @long_length.setter
    def long_length(self, length):
        self._long_l = length

    @property
    def signal_length(self):
        return self._signal_l

    @signal_length.setter
    def signal_length(self, length):
        self._signal_l = length

    @property
    def macds(self):
        return self._macds

    @property
    def hists(self):
        return self._hists

    @property
    def signals(self):
        return self._signals

    def cross(self):
        if (self._prev_macd > self._prev_signal and self._last_macd < self._last_signal):
            return -1
        elif (self._prev_macd < self._prev_signal and self._last_macd > self._last_signal):
            return 1

        return 0

    @staticmethod
    def MACD(N_short, N_long, data):
        mms = MMexp_n(N_short, data)
        mml = MMexp_n(N_long, data)

        return mms-mml

    @staticmethod
    def MACD_sf(N_short, N_long, data, step=1, filtering=False):
        """ 
        Calcul du MACD avec les 2 parametres N_short et N_long
        step permet de sélectionner 1 echantillon sur step avec filtrage ou non
        """
        sub_data = down_sample(data, step) if filtering else data [::step]
        t_subdata = range(0,len(data),step)

        # wiki dit exp, donc pourquoi MM_n ?
        mms = MMexp_n(N_short, sub_data)
        mml = MMexp_n(N_long, sub_data)

        return np.interp(range(len(data)), t_subdata, mms-mml)

    def compute(self, timestamp, prices):
        self._prev_macd = self._last_macd
        self._prev_signal = self._last_signal

        # self._macds = MACDIndicator.MACD(self._short_l, self._long_l, prices)
        self._macds, self._signals, self._hists = ta_MACD(
            prices, fastperiod=self._short_l, slowperiod=self._long_l, signalperiod=self._short_l)

        self._last_macd = self._macds[-1]
        self._last_signal = self._signals[-1]

        self._last_timestamp = timestamp

        return self._macds, self._signals, self._hists
