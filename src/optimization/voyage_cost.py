"""Maritime Voyage & Port Cost Economic Modeling for PortPilot AI.

Evaluates the comprehensive economics of continuing to a congested target port
versus diverting to an alternative port:
- Vessel daily operational charter/OPEX costs
- Bunker fuel consumption during transit and while idling at anchorage
- Contractual demurrage penalties for excessive waiting
- Port handling tariffs (TEU basis) and Quay Crane operating costs
- Extra sailing transit time and fuel costs for diversions
"""

from dataclasses import dataclass
from typing import Optional
from src.data.generator import Vessel, PortSpec


@dataclass
class VoyageCostParams:
    """Operational and financial parameters for voyage cost evaluation."""
    vessel_daily_cost_usd: float = 25000.0        # Vessel daily charter/OPEX ($/day)
    fuel_consumption_sea_mt_day: float = 35.0     # Bunker consumption at sea (MT/day at cruise)
    fuel_consumption_idle_mt_day: float = 3.5     # Auxiliary bunker while idling at anchor (MT/day)
    bunker_price_vlsfo_usd_mt: float = 620.0      # VLSFO bunker price ($/MT)
    vessel_speed_knots: float = 16.0              # Cruise sailing speed (knots = NM/h)
    demurrage_rate_day_usd: float = 18000.0       # Demurrage penalty ($/day)
    free_laytime_hours: float = 12.0              # Contractual allowed wait window (hours)
    crane_rate_per_hour_usd: float = 350.0        # STS crane operating tariff ($/crane-hour)


@dataclass
class TargetPortCost:
    """Detailed breakdown of costs incurred by staying at the target port."""
    port_id: str
    port_name: str
    wait_hours: float
    service_hours: float
    wait_opex_cost: float
    wait_idle_fuel_cost: float
    demurrage_cost: float
    port_handling_cost: float
    crane_operating_cost: float
    port_dues_cost: float
    pilotage_tug_cost: float
    congestion_surcharge_cost: float
    total_target_cost: float


@dataclass
class DiversionCost:
    """Detailed breakdown of costs and savings when diverting to an alternative port."""
    candidate_port_id: str
    candidate_port_name: str
    extra_distance_nm: float
    extra_sailing_hours: float
    extra_sailing_fuel_mt: float
    extra_sailing_fuel_cost: float
    extra_sailing_opex_cost: float
    wait_hours_at_alt: float
    wait_opex_cost_alt: float
    wait_idle_fuel_cost_alt: float
    demurrage_cost_alt: float
    port_handling_cost_alt: float
    diversion_tariff_cost: float
    port_dues_cost_alt: float
    pilotage_tug_cost_alt: float
    fixed_diversion_penalty: float
    congestion_surcharge_cost_alt: float
    crane_operating_cost_alt: float
    total_diversion_cost: float
    net_cost_difference: float           # Positive = SAVINGS if diverting, Negative = LOSS
    time_difference_hours: float         # Positive = FASTER at alternative port, Negative = SLOWER
    is_economically_viable: bool         # True if net savings > minimum operational threshold


def compute_target_port_cost(
    vessel: Vessel,
    target_port: PortSpec,
    wait_hours: float,
    params: Optional[VoyageCostParams] = None,
) -> TargetPortCost:
    """Calculate the comprehensive voyage and port call cost at the target port."""
    if params is None:
        params = VoyageCostParams()

    wait_days = max(0.0, wait_hours) / 24.0
    service_hours = vessel.service_duration_h
    cranes = max(1, vessel.required_cranes)

    # 1. Vessel OPEX during waiting period
    wait_opex = wait_days * params.vessel_daily_cost_usd

    # 2. Auxiliary generator fuel consumption during anchor waiting
    wait_idle_fuel = wait_days * params.fuel_consumption_idle_mt_day * params.bunker_price_vlsfo_usd_mt

    # 3. Demurrage cost (incurred only beyond agreed free laytime)
    demurrage_hours = max(0.0, wait_hours - params.free_laytime_hours)
    demurrage_cost = (demurrage_hours / 24.0) * params.demurrage_rate_day_usd

    # 4. Port terminal handling charges based on cargo TEU
    port_handling = vessel.cargo_volume * target_port.handling_cost_per_teu

    # 5. STS crane operational hours tariff (port specific)
    crane_rate = getattr(target_port, "crane_hourly_rate_usd", params.crane_rate_per_hour_usd)
    crane_cost = service_hours * cranes * crane_rate

    # 6. Fixed Port Entry & Harbor Dues
    port_dues = getattr(target_port, "port_dues_fixed_usd", 12000.0)

    # 7. Pilotage & Tugboat Assist Fee
    pilotage_fee = getattr(target_port, "pilotage_tug_fee_usd", 5000.0)

    # 8. Congestion Surcharge (incurred if port wait exceeds 6 hours)
    cong_surcharge = getattr(target_port, "congestion_surcharge_usd", 6000.0) if wait_hours > 6.0 else 0.0

    total_cost = (
        wait_opex
        + wait_idle_fuel
        + demurrage_cost
        + port_handling
        + crane_cost
        + port_dues
        + pilotage_fee
        + cong_surcharge
    )

    return TargetPortCost(
        port_id=target_port.port_id,
        port_name=target_port.port_name,
        wait_hours=round(wait_hours, 2),
        service_hours=round(service_hours, 2),
        wait_opex_cost=round(wait_opex, 2),
        wait_idle_fuel_cost=round(wait_idle_fuel, 2),
        demurrage_cost=round(demurrage_cost, 2),
        port_handling_cost=round(port_handling, 2),
        crane_operating_cost=round(crane_cost, 2),
        port_dues_cost=round(port_dues, 2),
        pilotage_tug_cost=round(pilotage_fee, 2),
        congestion_surcharge_cost=round(cong_surcharge, 2),
        total_target_cost=round(total_cost, 2),
    )


def compute_diversion_cost(
    vessel: Vessel,
    target_cost: TargetPortCost,
    candidate_port: PortSpec,
    extra_distance_nm: float,
    wait_hours_at_alt: float,
    params: Optional[VoyageCostParams] = None,
    min_saving_threshold_usd: float = 10000.0,
) -> DiversionCost:
    """Calculate the cost of diverting to a candidate port and compare with target port."""
    if params is None:
        params = VoyageCostParams()

    # 1. Additional transit sailing time
    speed = max(1.0, params.vessel_speed_knots)
    extra_sailing_h = extra_distance_nm / speed
    extra_sailing_days = extra_sailing_h / 24.0

    # 2. Transit fuel and vessel operating costs
    extra_fuel_mt = extra_sailing_days * params.fuel_consumption_sea_mt_day
    extra_fuel_cost = extra_fuel_mt * params.bunker_price_vlsfo_usd_mt
    extra_opex_cost = extra_sailing_days * params.vessel_daily_cost_usd

    # 3. Waiting costs at candidate port
    wait_days_alt = max(0.0, wait_hours_at_alt) / 24.0
    wait_opex_alt = wait_days_alt * params.vessel_daily_cost_usd
    wait_idle_fuel_alt = wait_days_alt * params.fuel_consumption_idle_mt_day * params.bunker_price_vlsfo_usd_mt

    demurrage_hours_alt = max(0.0, wait_hours_at_alt - params.free_laytime_hours)
    demurrage_alt = (demurrage_hours_alt / 24.0) * params.demurrage_rate_day_usd

    # 4. Port handling and tariff charges at alternative
    port_handling_alt = vessel.cargo_volume * candidate_port.handling_cost_per_teu

    # 5. Fixed and per-TEU diversion penalty for administrative/manifest alteration
    fixed_div_penalty = getattr(candidate_port, "diversion_penalty_fixed_usd", 10000.0)
    teu_div_surcharge = vessel.cargo_volume * (candidate_port.diversion_cost_per_teu * 0.15)
    total_diversion_penalty = fixed_div_penalty + teu_div_surcharge

    # 6. Harbor Dues and Pilotage/Tugboat Assist at Alternative Port
    port_dues_alt = getattr(candidate_port, "port_dues_fixed_usd", 12000.0)
    pilotage_alt = getattr(candidate_port, "pilotage_tug_fee_usd", 5000.0)

    # 7. Congestion surcharge at alternative port
    cong_surcharge_alt = getattr(candidate_port, "congestion_surcharge_usd", 6000.0) if wait_hours_at_alt > 6.0 else 0.0

    # 8. Crane costs at alternative (port specific)
    cranes = max(1, vessel.required_cranes)
    crane_rate_alt = getattr(candidate_port, "crane_hourly_rate_usd", params.crane_rate_per_hour_usd)
    crane_cost_alt = vessel.service_duration_h * cranes * crane_rate_alt

    total_div_cost = (
        extra_fuel_cost
        + extra_opex_cost
        + wait_opex_alt
        + wait_idle_fuel_alt
        + demurrage_alt
        + port_handling_alt
        + total_diversion_penalty
        + port_dues_alt
        + pilotage_alt
        + cong_surcharge_alt
        + crane_cost_alt
    )

    # Net difference: if target_cost > total_div_cost, diverting saves money!
    net_diff = target_cost.total_target_cost - total_div_cost

    target_total_hours = target_cost.wait_hours + vessel.service_duration_h
    alt_total_hours = extra_sailing_h + wait_hours_at_alt + vessel.service_duration_h
    time_diff_h = target_total_hours - alt_total_hours

    is_viable = net_diff >= min_saving_threshold_usd

    return DiversionCost(
        candidate_port_id=candidate_port.port_id,
        candidate_port_name=candidate_port.port_name,
        extra_distance_nm=round(extra_distance_nm, 1),
        extra_sailing_hours=round(extra_sailing_h, 1),
        extra_sailing_fuel_mt=round(extra_fuel_mt, 1),
        extra_sailing_fuel_cost=round(extra_fuel_cost, 2),
        extra_sailing_opex_cost=round(extra_opex_cost, 2),
        wait_hours_at_alt=round(wait_hours_at_alt, 1),
        wait_opex_cost_alt=round(wait_opex_alt, 2),
        wait_idle_fuel_cost_alt=round(wait_idle_fuel_alt, 2),
        demurrage_cost_alt=round(demurrage_alt, 2),
        port_handling_cost_alt=round(port_handling_alt, 2),
        diversion_tariff_cost=round(total_diversion_penalty, 2),
        port_dues_cost_alt=round(port_dues_alt, 2),
        pilotage_tug_cost_alt=round(pilotage_alt, 2),
        fixed_diversion_penalty=round(fixed_div_penalty, 2),
        congestion_surcharge_cost_alt=round(cong_surcharge_alt, 2),
        crane_operating_cost_alt=round(crane_cost_alt, 2),
        total_diversion_cost=round(total_div_cost, 2),
        net_cost_difference=round(net_diff, 2),
        time_difference_hours=round(time_diff_h, 1),
        is_economically_viable=is_viable,
    )
