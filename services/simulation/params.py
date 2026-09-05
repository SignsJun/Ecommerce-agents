from domain.base import FrozenModel

SIMULATOR_VERSION = "world-v1"
PARAMETER_VERSION = "sim-v1"


class SimulatorParameterSet(FrozenModel):
    version: str = PARAMETER_VERSION
    eta_ad: float = 0.6
    eta_price: float = -1.2
    listing_refund_factor: float = 0.7
    demand_sigma: float = 0.15
    min_margin: float = 0.20
    demand_mult: float = 1.0
    lead_time_extra: float = 0.0


def with_overrides(params: SimulatorParameterSet, overrides: dict[str, float]) -> SimulatorParameterSet:
    data = params.model_dump()
    for key, value in overrides.items():
        if key in data and key != "version":
            data[key] = value
    return SimulatorParameterSet.model_validate(data)
