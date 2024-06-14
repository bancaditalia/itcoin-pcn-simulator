########################################################################################################################
#                         Copyright (c) 2019-2021 Banca d'Italia - All Rights Reserved                                 #
#                                                                                                                      #
# This file is part of the "itCoin" project.                                                                           #
# Unauthorized copying of this file, via any medium, is strictly prohibited.                                           #
# The content of this and related source files is proprietary and confidential.                                        #
#                                                                                                                      #
# Written by ART (Applied Research Team) - email: appliedresearchteam@bancaditalia.it - web: https://www.bankit.art    #
########################################################################################################################
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import scipy.stats

N_BATCHES = 30
ALFA_CONFIDENCE = 0.95


class StatType(str, Enum):
    SUCCESS = "Success"
    FAIL_NO_PATH = "FailNoPath"
    FAIL_NO_BALANCE = "FailNoBalance"
    FAIL_OFFLINE = "FailOfflineNode"
    FAIL_TIMEOUT_EXPIRED = "FailTimeoutExpired"
    TIME = "Time"
    ATTEMPTS = "Attempts"
    ROUTE_LENGTH = "RouteLength"


class StatInnerKey(str, Enum):
    MEAN = "Mean"
    VARIANCE = "Variance"
    CONFIDENCE_MIN = "ConfidenceMin"
    CONFIDENCE_MAX = "ConfidenceMax"


class GeneralStat(str, Enum):
    TOTAL_WHOLESALE_CAPACITY = "TotalWholeSaleCapacity"
    TOTAL_SUCCESS_VOLUME = "TotalSuccessVolume"
    VOLUME_CAPACITY_RATIO = "VolumeCapacityRatio"
    TOTAL_PAYMENTS = "TotalPayments"
    TOTAL_DEPOSITS = "TotalDeposits"
    TOTAL_WITHDRAWALS = "TotalWithdrawals"
    TOTAL_SUBMARINE_SWAPS = "TotalSubmarineSwaps"
    TOTAL_SUBMARINE_SWAPS_1_1 = "TotalSubmarineSwaps1<>1"
    TOTAL_SUBMARINE_SWAPS_1_2 = "TotalSubmarineSwaps1<>2"
    TOTAL_SUBMARINE_SWAPS_2_2 = "TotalSubmarineSwaps2<>2"


class StatsPerMinute(str, Enum):
    TX_PER_MINUTE = "TransactionsPerMinute"
    PSR_PER_MINUTE = "SuccessPerMinute"
    DEPOSITS_PER_MINUTE = "DepositsPerMinute"
    WITHDRAWALS_PER_MINUTE = "WithdrawalsPerMinute"
    SUBMARINE_SWAPS_PER_MINUTE = "SubmarineSwapsPerMinute"


class DistributionStats(str, Enum):
    ROUTE_LENGTH_DISTR = "RouteLengthDistr"


class DistributionInnerStats(str, Enum):
    TOTAL = "Total"
    ROUTED_BY_L1 = "RoutedByL1"
    ROUTED_BY_L2 = "RoutedByL2"


def generate_data() -> dict[StatType, dict[StatInnerKey, float]]:
    return {stat: {innerStat: 0} for innerStat in StatInnerKey for stat in StatType}


def generate_batches() -> dict[StatType, list[int]]:
    return {stat: [0] * N_BATCHES for stat in StatType}


def generate_general_stats() -> dict[GeneralStat, float]:
    return {stat: 0 for stat in GeneralStat}


def generate_stats_per_minute() -> dict[StatsPerMinute, dict[int, float]]:
    return {stat: {hour: 0 for hour in range(1440)} for stat in StatsPerMinute}


def generate_distribution_stats() -> dict[int, dict[DistributionInnerStats, float]]:
    return {}


@dataclass
class PaymentsStats:
    """Model the payments statistics."""

    data: dict[StatType, dict[StatInnerKey, float]] = field(
        default_factory=generate_data, init=False
    )
    batches: dict[StatType, list[int]] = field(
        default_factory=generate_batches, init=False
    )
    general_stats: dict[GeneralStat, float] = field(
        default_factory=generate_general_stats, init=False
    )
    stats_per_minute: dict[StatsPerMinute, dict[int, float]] = field(
        default_factory=generate_stats_per_minute, init=False
    )
    distributions_stats: dict[
        DistributionStats, dict[int, dict[DistributionInnerStats, float]]
    ] = field(default_factory=generate_distribution_stats, init=False)

    def compute_batch_means(self) -> None:
        """Compute batch means"""
        for stat in StatType:
            self.data[stat][StatInnerKey.MEAN] = np.mean(self.batches[stat])
            h = scipy.stats.sem(self.batches[stat]) * scipy.stats.t.isf(
                (ALFA_CONFIDENCE) / 2.0, N_BATCHES
            )
            self.data[stat][StatInnerKey.CONFIDENCE_MIN] = (
                self.data[stat][StatInnerKey.MEAN] - h
            )
            self.data[stat][StatInnerKey.CONFIDENCE_MAX] = (
                self.data[stat][StatInnerKey.MEAN] + h
            )
            self.data[stat][StatInnerKey.VARIANCE] = np.var(self.batches[stat])
