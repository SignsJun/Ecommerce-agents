from decimal import Decimal


def days_of_cover(inventory_available: int, units_sold_7d: int) -> float:
    daily = units_sold_7d / 7
    if daily <= 0:
        return 999.0
    return inventory_available / daily


def excess_units(inventory_available: int, units_sold_7d: int, target_cover_days: int) -> int:
    daily = units_sold_7d / 7
    target = int(daily * target_cover_days)
    return max(0, inventory_available - target)


def inventory_value(unit_cost: Decimal, units: int) -> Decimal:
    return unit_cost * units
