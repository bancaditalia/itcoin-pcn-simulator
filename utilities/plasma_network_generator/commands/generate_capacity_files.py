#!/usr/bin/env python3
"""Generate capacity files."""

import argparse
import dataclasses
import json
from abc import ABC, abstractmethod
from pathlib import Path

from plasma_network_generator.core import SubnetworkType
from plasma_network_generator.exceptions import CliArgsValidationError
from plasma_network_generator.utils import (
    check_dir_is_empty,
    check_path_is_directory,
)
from plasma_network_generator.utils import (
    integer_in_human_format as h,
)


class CapacityValue(ABC):
    @property
    def json(self) -> str:
        """Return the capacity value as a JSON-serializable string."""
        raise NotImplementedError

    @abstractmethod
    def scale(self, factor: float) -> "CapacityValue":
        """Scale the capacity value by the given factor."""
        raise NotImplementedError


class CapacityPointValue(int, CapacityValue):
    """Capacity value."""

    def __new__(cls, value: int):
        """Create a new CapacityValue."""
        if value < 0:
            msg = "Capacity cannot be negative."
            raise ValueError(msg)
        return super().__new__(cls, value)

    @property
    def json(self) -> str:
        """Return the capacity value as a JSON-serializable string."""
        return str(self)

    def scale(self, factor: float) -> "CapacityPointValue":
        """Scale the capacity value by the given factor."""
        return CapacityPointValue(int(self * factor))


@dataclasses.dataclass(frozen=True)
class CapacityRange:
    """Capacity range."""

    min: CapacityPointValue
    max: CapacityPointValue

    def __post_init__(self):
        """Check that the range is not empty."""
        if self.min < 0 or self.max < 0:
            msg = "Capacity range cannot be negative."
            raise ValueError(msg)
        if self.min > self.max:
            msg = "Capacity range cannot be empty."
            raise ValueError(msg)

    @property
    def json(self) -> dict:
        """Return the capacity range as a JSON-serializable dictionary."""
        return {
            "min": self.min.json,
            "max": self.max.json,
        }

    def scale(self, factor: float) -> "CapacityRange":
        """Scale the capacity value by the given factor."""
        return CapacityRange(
            min=self.min.scale(factor),
            max=self.max.scale(factor),
        )


CapacityValues = CapacityPointValue | CapacityRange


@dataclasses.dataclass(frozen=True)
class CapacitySpec:
    """Capacity specification."""

    capacity_by_subnetwork: dict[SubnetworkType, CapacityValues]

    def __post_init__(self):
        """Check that the capacity is not negative."""
        unset_subnetworks = set(SubnetworkType) - set(
            self.capacity_by_subnetwork.keys(),
        )
        if len(unset_subnetworks) > 0:
            msg = f"Capacity must be set for all subnetworks, but not set for the following: {unset_subnetworks}"
            raise ValueError(msg)

    @property
    def json(self) -> dict:
        """Return the capacity specification as a JSON-serializable dictionary."""
        return {
            "subnetworks": {
                subnetwork.value: {"capacity": capacity.json}
                for subnetwork, capacity in self.capacity_by_subnetwork.items()
            },
        }


MAX_CAPACITIES_BY_SUBNETWORK = {
    SubnetworkType.S_1_CHANNEL_1: CapacityPointValue(h("5M")),
    SubnetworkType.S_1_CHANNEL_2: CapacityPointValue(h("1M")),  # = 10k EUR
    SubnetworkType.S_2_CHANNEL_2: CapacityPointValue(h("1M")),  # = 10k EUR
    SubnetworkType.S_3_CHANNEL_3: CapacityPointValue(h("500k")),
    SubnetworkType.S_2_CHANNEL_3B: CapacityPointValue(h("300k")),  # = 3k EUR
    SubnetworkType.S_2_CHANNEL_3M_SMALL: CapacityPointValue(h("500k")),  # = 5k EUR
    SubnetworkType.S_2_CHANNEL_3M_MEDIUM: CapacityPointValue(h("5M")),  # = 50k EUR
    SubnetworkType.S_2_CHANNEL_3M_LARGE: CapacityPointValue(h("50M")),  # = 500k EUR
}


def get_capacity_specs() -> dict[str, CapacitySpec]:
    """Get capacity specifications (a mapping name -> spec)."""
    percentages = [p / 100 for p in range(0, 101, 10)]
    result = {}
    for percentage in percentages:
        result[f"capacities-{percentage * 100:03.0f}"] = CapacitySpec(
            {
                subnetwork: (
                    MAX_CAPACITIES_BY_SUBNETWORK[subnetwork].scale(percentage)
                    if subnetwork != SubnetworkType.S_2_CHANNEL_3B
                    and subnetwork != SubnetworkType.S_2_CHANNEL_3M_SMALL
                    and subnetwork != SubnetworkType.S_2_CHANNEL_3M_MEDIUM
                    and subnetwork != SubnetworkType.S_2_CHANNEL_3M_LARGE
                    else MAX_CAPACITIES_BY_SUBNETWORK[subnetwork]
                )
                for subnetwork in SubnetworkType
            },
        )
    return result


def main() -> None:
    """Generate capacity files."""
    parser = argparse.ArgumentParser(description="Generate capacity files.")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("capacities"),
        help="File to write",
    )
    args = parser.parse_args()

    # Validate output directory. Create it if it does not exist.
    args.output_dir.mkdir(parents=True, exist_ok=True)
    check_path_is_directory(args.output_dir, CliArgsValidationError)
    check_dir_is_empty(args.output_dir, CliArgsValidationError)

    for name, capacity_spec in get_capacity_specs().items():
        (args.output_dir / f"{name}.json").write_text(
            json.dumps(capacity_spec.json, indent=4),
        )


if __name__ == "__main__":
    main()
