from domain.simulation.scenario import SimulationScenario
from services.simulation.params import SimulatorParameterSet

CATALOG: dict[str, str] = {
    "roas_down": "stress",
    "demand_down": "stress",
    "listing_worse": "sensitivity",
    "eta_ad_pm20": "sensitivity",
    "supplier_delay": "stress",
}


def catalog_kind(name: str) -> str | None:
    return CATALOG.get(name)


def scenario_jobs(name: str, params: SimulatorParameterSet | None = None) -> list[SimulationScenario]:
    params = params or SimulatorParameterSet()
    if name == "roas_down":
        return [_scene(name, "stress", "ROAS down", {"eta_ad": params.eta_ad * 0.8})]
    if name == "demand_down":
        return [_scene(name, "stress", "demand down", {"demand_mult": 0.8})]
    if name == "listing_worse":
        factor = min(1.0, params.listing_refund_factor * 1.2)
        return [_scene(name, "sensitivity", "listing worse", {"listing_refund_factor": factor})]
    if name == "eta_ad_pm20":
        return [
            _scene("eta_ad_p20", "sensitivity", "eta_ad +20%", {"eta_ad": params.eta_ad * 1.2}),
            _scene("eta_ad_m20", "sensitivity", "eta_ad -20%", {"eta_ad": params.eta_ad * 0.8}),
        ]
    if name == "supplier_delay":
        return [_scene(name, "stress", "supplier delay", {"lead_time_extra": 7.0})]
    return []


def _scene(sid: str, kind: str, desc: str, overrides: dict[str, float]) -> SimulationScenario:
    return SimulationScenario(
        scenario_id=sid,
        name=sid,
        scenario_type="stress" if kind == "stress" else "sensitivity",
        description=desc,
        parameter_overrides=overrides,
    )
