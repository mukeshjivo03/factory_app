"""
sap_plan_dashboard/serializers.py

DRF serializers for validating query parameters and shaping API responses.
All data is read-only (no database writes), so only plain Serializer classes are used.
"""

from rest_framework import serializers


# ---------------------------------------------------------------------------
# Query Parameter Serializers (Input Validation)
# ---------------------------------------------------------------------------


class PlanDashboardFilterSerializer(serializers.Serializer):
    """Validates common query parameters shared by all plan-dashboard endpoints."""

    STATUS_CHOICES = [("planned", "Planned"), ("released", "Released"), ("all", "All")]

    status = serializers.ChoiceField(
        choices=STATUS_CHOICES,
        default="all",
        required=False,
        help_text="Filter by production order status. One of: planned, released, all",
    )
    due_date_from = serializers.DateField(
        required=False,
        input_formats=["%Y-%m-%d"],
        help_text="Filter orders with DueDate >= this date. Format: YYYY-MM-DD",
    )
    due_date_to = serializers.DateField(
        required=False,
        input_formats=["%Y-%m-%d"],
        help_text="Filter orders with DueDate <= this date. Format: YYYY-MM-DD",
    )
    warehouse = serializers.CharField(
        required=False,
        max_length=8,
        help_text="Filter by warehouse code (e.g. WH-01)",
    )
    sku = serializers.CharField(
        required=False,
        max_length=50,
        help_text="Filter by SKU / finished good item code",
    )
    show_shortfall_only = serializers.BooleanField(
        required=False,
        default=False,
        help_text="When true, return only items/orders with a shortfall",
    )

    def validate(self, attrs):
        due_from = attrs.get("due_date_from")
        due_to = attrs.get("due_date_to")
        if due_from and due_to and due_from > due_to:
            raise serializers.ValidationError(
                "due_date_from must be before or equal to due_date_to."
            )
        return attrs


# ---------------------------------------------------------------------------
# Response Serializers (Output Shape)
# ---------------------------------------------------------------------------


class SummaryOrderSerializer(serializers.Serializer):
    """One row per production order in the summary view."""

    prod_order_entry = serializers.IntegerField()
    prod_order_num = serializers.IntegerField()
    sku_code = serializers.CharField()
    sku_name = serializers.CharField()
    planned_qty = serializers.FloatField()
    completed_qty = serializers.FloatField()
    status = serializers.CharField()
    due_date = serializers.CharField(allow_null=True)
    post_date = serializers.CharField(allow_null=True)
    priority = serializers.IntegerField()
    warehouse = serializers.CharField()
    total_components = serializers.IntegerField()
    components_with_shortfall = serializers.IntegerField()
    total_remaining_component_qty = serializers.FloatField()


class SummaryMetaSerializer(serializers.Serializer):
    total_orders = serializers.IntegerField()
    orders_with_shortfall = serializers.IntegerField()
    fetched_at = serializers.CharField()


class SummaryResponseSerializer(serializers.Serializer):
    data = SummaryOrderSerializer(many=True)
    meta = SummaryMetaSerializer()


# ---------------------------------------------------------------------------


class BOMComponentSerializer(serializers.Serializer):
    """One BOM component line (used in details and sku-detail responses)."""

    component_line = serializers.IntegerField()
    component_code = serializers.CharField()
    component_name = serializers.CharField()
    component_planned_qty = serializers.FloatField()
    component_issued_qty = serializers.FloatField()
    component_remaining_qty = serializers.FloatField()
    component_warehouse = serializers.CharField()
    base_qty = serializers.FloatField()
    uom = serializers.CharField()
    stock_on_hand = serializers.FloatField()
    stock_committed = serializers.FloatField()
    stock_on_order = serializers.FloatField()
    net_available = serializers.FloatField()
    shortfall_qty = serializers.FloatField()
    vendor_lead_time = serializers.IntegerField()
    default_vendor = serializers.CharField()
    stock_status = serializers.CharField()


class DetailOrderSerializer(serializers.Serializer):
    """One production order with its nested BOM components."""

    prod_order_entry = serializers.IntegerField()
    prod_order_num = serializers.IntegerField()
    sku_code = serializers.CharField()
    sku_name = serializers.CharField()
    sku_planned_qty = serializers.FloatField()
    sku_completed_qty = serializers.FloatField()
    status = serializers.CharField()
    due_date = serializers.CharField(allow_null=True)
    post_date = serializers.CharField(allow_null=True)
    warehouse = serializers.CharField()
    priority = serializers.IntegerField()
    total_components = serializers.IntegerField()
    components_with_shortfall = serializers.IntegerField()
    components = BOMComponentSerializer(many=True)


class DetailsMetaSerializer(serializers.Serializer):
    total_orders = serializers.IntegerField()
    total_component_lines = serializers.IntegerField()
    fetched_at = serializers.CharField()


class DetailsResponseSerializer(serializers.Serializer):
    data = DetailOrderSerializer(many=True)
    meta = DetailsMetaSerializer()


# ---------------------------------------------------------------------------


class ProcurementItemSerializer(serializers.Serializer):
    """One aggregated procurement row for a component."""

    component_code = serializers.CharField()
    component_name = serializers.CharField()
    uom = serializers.CharField()
    total_required_qty = serializers.FloatField()
    stock_on_hand = serializers.FloatField()
    stock_committed = serializers.FloatField()
    stock_on_order = serializers.FloatField()
    net_available = serializers.FloatField()
    shortfall_qty = serializers.FloatField()
    suggested_purchase_qty = serializers.FloatField()
    vendor_lead_time = serializers.IntegerField()
    default_vendor = serializers.CharField()
    related_prod_orders = serializers.ListField(child=serializers.CharField())


class ProcurementMetaSerializer(serializers.Serializer):
    total_components = serializers.IntegerField()
    components_with_shortfall = serializers.IntegerField()
    fetched_at = serializers.CharField()


class ProcurementResponseSerializer(serializers.Serializer):
    data = ProcurementItemSerializer(many=True)
    meta = ProcurementMetaSerializer()


# ---------------------------------------------------------------------------


class SKUDetailHeaderSerializer(serializers.Serializer):
    """Header fields of a single production order."""

    prod_order_entry = serializers.IntegerField()
    prod_order_num = serializers.IntegerField()
    sku_code = serializers.CharField()
    sku_name = serializers.CharField()
    sku_planned_qty = serializers.FloatField()
    sku_completed_qty = serializers.FloatField()
    status = serializers.CharField()
    due_date = serializers.CharField(allow_null=True)
    post_date = serializers.CharField(allow_null=True)
    warehouse = serializers.CharField()
    priority = serializers.IntegerField()
    total_components = serializers.IntegerField()
    components_with_shortfall = serializers.IntegerField()
    components = BOMComponentSerializer(many=True)


class SKUDetailMetaSerializer(serializers.Serializer):
    fetched_at = serializers.CharField()


class SKUDetailResponseSerializer(serializers.Serializer):
    data = SKUDetailHeaderSerializer()
    meta = SKUDetailMetaSerializer()
