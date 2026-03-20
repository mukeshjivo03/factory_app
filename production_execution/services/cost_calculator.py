import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


def recalculate_run_cost(production_run) -> None:
    """
    Recalculate and persist the ProductionRunCost for a given run.
    Called after any resource or material save/delete.
    """
    from production_execution.models import ProductionRunCost

    # Material costs — use wastage_qty approach: (opening + issued - closing) * unit_cost
    # For existing material entries without unit_cost, skip
    raw_material_cost = Decimal('0')
    for m in production_run.material_usages.all():
        unit_cost = getattr(m, 'unit_cost', None)
        if unit_cost:
            qty_used = m.opening_qty + m.issued_qty - m.closing_qty
            raw_material_cost += qty_used * Decimal(str(unit_cost))
        else:
            raw_material_cost += getattr(m, 'total_cost', Decimal('0'))

    labour_cost = sum(
        r.total_cost for r in production_run.labour_entries.all()
    )
    machine_cost = sum(
        r.total_cost for r in production_run.machine_cost_entries.all()
    )
    electricity_cost = sum(
        r.total_cost for r in production_run.electricity_usage.all()
    )
    water_cost = sum(
        r.total_cost for r in production_run.water_usage.all()
    )
    gas_cost = sum(
        r.total_cost for r in production_run.gas_usage.all()
    )
    compressed_air_cost = sum(
        r.total_cost for r in production_run.compressed_air_usage.all()
    )
    overhead_cost = sum(
        r.amount for r in production_run.overhead_entries.all()
    )

    # Ensure all are Decimal
    def to_dec(v):
        return Decimal(str(v)) if v else Decimal('0')

    labour_cost = to_dec(labour_cost)
    machine_cost = to_dec(machine_cost)
    electricity_cost = to_dec(electricity_cost)
    water_cost = to_dec(water_cost)
    gas_cost = to_dec(gas_cost)
    compressed_air_cost = to_dec(compressed_air_cost)
    overhead_cost = to_dec(overhead_cost)

    total_cost = (
        raw_material_cost + labour_cost + machine_cost +
        electricity_cost + water_cost + gas_cost +
        compressed_air_cost + overhead_cost
    )

    produced = Decimal(str(production_run.total_production or 0))
    per_unit = (total_cost / produced) if produced > 0 else Decimal('0')

    ProductionRunCost.objects.update_or_create(
        production_run=production_run,
        defaults={
            'raw_material_cost': raw_material_cost,
            'labour_cost': labour_cost,
            'machine_cost': machine_cost,
            'electricity_cost': electricity_cost,
            'water_cost': water_cost,
            'gas_cost': gas_cost,
            'compressed_air_cost': compressed_air_cost,
            'overhead_cost': overhead_cost,
            'total_cost': total_cost,
            'produced_qty': produced,
            'per_unit_cost': per_unit,
        }
    )
    logger.debug(f"Recalculated cost for run {production_run.id}: total={total_cost}, per_unit={per_unit}")
