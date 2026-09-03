from decimal import Decimal

from domain.business.inventory import days_of_cover, excess_units, inventory_value


def test_days_of_cover():
    assert days_of_cover(70, 70) == 7.0
    assert days_of_cover(10, 0) == 999.0


def test_excess_and_value():
    assert excess_units(200, 14, 21) == 158
    assert inventory_value(Decimal("10.00"), 5) == Decimal("50.00")
