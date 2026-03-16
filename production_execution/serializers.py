from rest_framework import serializers
from .models import (
    ProductionLine, Machine, MachineChecklistTemplate,
    ProductionRun, ProductionLog, MachineBreakdown,
    ProductionMaterialUsage, MachineRuntime, ProductionManpower,
    LineClearance, LineClearanceItem,
    MachineChecklistEntry, WasteLog,
    ResourceElectricity, ResourceWater, ResourceGas, ResourceCompressedAir,
    ResourceLabour, ResourceMachineCost, ResourceOverhead,
    ProductionRunCost, InProcessQCCheck, FinalQCCheck,
)


# ---------------------------------------------------------------------------
# Master Data
# ---------------------------------------------------------------------------

class ProductionLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionLine
        fields = ['id', 'name', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class ProductionLineCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True, default='')


class MachineSerializer(serializers.ModelSerializer):
    line_name = serializers.CharField(source='line.name', read_only=True)

    class Meta:
        model = Machine
        fields = [
            'id', 'name', 'machine_type', 'line', 'line_name',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class MachineCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    machine_type = serializers.CharField(max_length=30)
    line_id = serializers.IntegerField()


class ChecklistTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MachineChecklistTemplate
        fields = [
            'id', 'machine_type', 'task', 'frequency',
            'sort_order', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class ChecklistTemplateCreateSerializer(serializers.Serializer):
    machine_type = serializers.CharField(max_length=30)
    task = serializers.CharField(max_length=500)
    frequency = serializers.CharField(max_length=10)
    sort_order = serializers.IntegerField(required=False, default=0)


# ---------------------------------------------------------------------------
# Production Runs
# ---------------------------------------------------------------------------

class ProductionRunCreateSerializer(serializers.Serializer):
    production_plan_id = serializers.IntegerField()
    line_id = serializers.IntegerField()
    date = serializers.DateField()
    brand = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    pack = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    sap_order_no = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    rated_speed = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )


class ProductionRunUpdateSerializer(serializers.Serializer):
    brand = serializers.CharField(max_length=200, required=False, allow_blank=True)
    pack = serializers.CharField(max_length=100, required=False, allow_blank=True)
    sap_order_no = serializers.CharField(max_length=50, required=False, allow_blank=True)
    rated_speed = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )


class ProductionRunListSerializer(serializers.ModelSerializer):
    line_name = serializers.CharField(source='line.name', read_only=True)
    plan_item_name = serializers.CharField(source='production_plan.item_name', read_only=True)

    class Meta:
        model = ProductionRun
        fields = [
            'id', 'production_plan', 'plan_item_name', 'run_number', 'date',
            'line', 'line_name', 'brand', 'pack', 'sap_order_no', 'rated_speed',
            'total_production', 'total_breakdown_time', 'status',
            'created_by', 'created_at',
        ]


class ProductionRunDetailSerializer(serializers.ModelSerializer):
    line_name = serializers.CharField(source='line.name', read_only=True)
    plan_item_name = serializers.CharField(source='production_plan.item_name', read_only=True)
    logs = serializers.SerializerMethodField()
    breakdowns = serializers.SerializerMethodField()

    class Meta:
        model = ProductionRun
        fields = [
            'id', 'production_plan', 'plan_item_name', 'run_number', 'date',
            'line', 'line_name', 'brand', 'pack', 'sap_order_no', 'rated_speed',
            'total_production', 'total_minutes_pe', 'total_minutes_me',
            'total_breakdown_time', 'line_breakdown_time', 'external_breakdown_time',
            'unrecorded_time', 'status',
            'created_by', 'created_at', 'updated_at',
            'logs', 'breakdowns',
        ]

    def get_logs(self, obj):
        return ProductionLogSerializer(obj.logs.all(), many=True).data

    def get_breakdowns(self, obj):
        return MachineBreakdownSerializer(obj.breakdowns.all(), many=True).data


# ---------------------------------------------------------------------------
# Hourly Production Logs
# ---------------------------------------------------------------------------

class ProductionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionLog
        fields = [
            'id', 'time_slot', 'time_start', 'time_end',
            'produced_cases', 'machine_status', 'recd_minutes',
            'breakdown_detail', 'remarks', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class ProductionLogCreateSerializer(serializers.Serializer):
    time_slot = serializers.CharField(max_length=20)
    time_start = serializers.TimeField()
    time_end = serializers.TimeField()
    produced_cases = serializers.IntegerField(min_value=0, default=0)
    machine_status = serializers.CharField(max_length=20, default='RUNNING')
    recd_minutes = serializers.IntegerField(min_value=0, max_value=60, default=0)
    breakdown_detail = serializers.CharField(
        max_length=500, required=False, allow_blank=True, default=''
    )
    remarks = serializers.CharField(required=False, allow_blank=True, default='')


# ---------------------------------------------------------------------------
# Machine Breakdowns
# ---------------------------------------------------------------------------

class MachineBreakdownSerializer(serializers.ModelSerializer):
    machine_name = serializers.CharField(source='machine.name', read_only=True)

    class Meta:
        model = MachineBreakdown
        fields = [
            'id', 'machine', 'machine_name', 'start_time', 'end_time',
            'breakdown_minutes', 'type', 'is_unrecovered',
            'reason', 'remarks', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class MachineBreakdownCreateSerializer(serializers.Serializer):
    machine_id = serializers.IntegerField()
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField(required=False, allow_null=True)
    breakdown_minutes = serializers.IntegerField(min_value=0, required=False, default=0)
    type = serializers.CharField(max_length=10)
    is_unrecovered = serializers.BooleanField(default=False)
    reason = serializers.CharField(max_length=500)
    remarks = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        if attrs.get('end_time') and attrs['end_time'] < attrs['start_time']:
            raise serializers.ValidationError("end_time must be >= start_time.")
        return attrs


# ---------------------------------------------------------------------------
# Material Usage
# ---------------------------------------------------------------------------

class MaterialUsageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionMaterialUsage
        fields = [
            'id', 'material_code', 'material_name',
            'opening_qty', 'issued_qty', 'closing_qty', 'wastage_qty',
            'uom', 'batch_number', 'created_at', 'updated_at',
        ]
        read_only_fields = ['wastage_qty', 'created_at', 'updated_at']


class MaterialUsageCreateSerializer(serializers.Serializer):
    material_code = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    material_name = serializers.CharField(max_length=255)
    opening_qty = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=0, default=0)
    issued_qty = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=0, default=0)
    closing_qty = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=0, default=0)
    uom = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    batch_number = serializers.IntegerField(min_value=1, max_value=3, default=1)


# ---------------------------------------------------------------------------
# Machine Runtime
# ---------------------------------------------------------------------------

class MachineRuntimeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MachineRuntime
        fields = [
            'id', 'machine', 'machine_type',
            'runtime_minutes', 'downtime_minutes',
            'remarks', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class MachineRuntimeCreateSerializer(serializers.Serializer):
    machine_id = serializers.IntegerField(required=False, allow_null=True)
    machine_type = serializers.CharField(max_length=30)
    runtime_minutes = serializers.IntegerField(min_value=0, default=0)
    downtime_minutes = serializers.IntegerField(min_value=0, default=0)
    remarks = serializers.CharField(required=False, allow_blank=True, default='')


# ---------------------------------------------------------------------------
# Manpower
# ---------------------------------------------------------------------------

class ManpowerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionManpower
        fields = [
            'id', 'shift', 'worker_count',
            'supervisor', 'engineer', 'remarks',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class ManpowerCreateSerializer(serializers.Serializer):
    shift = serializers.CharField(max_length=20)
    worker_count = serializers.IntegerField(min_value=0, default=0)
    supervisor = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    engineer = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    remarks = serializers.CharField(required=False, allow_blank=True, default='')


# ---------------------------------------------------------------------------
# Line Clearance
# ---------------------------------------------------------------------------

class LineClearanceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = LineClearanceItem
        fields = ['id', 'checkpoint', 'sort_order', 'result', 'remarks']


class LineClearanceItemUpdateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    result = serializers.CharField(max_length=5)
    remarks = serializers.CharField(required=False, allow_blank=True, default='')


class LineClearanceCreateSerializer(serializers.Serializer):
    date = serializers.DateField()
    line_id = serializers.IntegerField()
    production_plan_id = serializers.IntegerField()
    document_id = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')


class LineClearanceDetailSerializer(serializers.ModelSerializer):
    items = LineClearanceItemSerializer(many=True, read_only=True)
    line_name = serializers.CharField(source='line.name', read_only=True)

    class Meta:
        model = LineClearance
        fields = [
            'id', 'date', 'line', 'line_name', 'production_plan',
            'document_id', 'verified_by',
            'qa_approved', 'qa_approved_by', 'qa_approved_at',
            'production_supervisor_sign', 'production_incharge_sign',
            'status', 'created_by', 'created_at', 'updated_at',
            'items',
        ]


class LineClearanceListSerializer(serializers.ModelSerializer):
    line_name = serializers.CharField(source='line.name', read_only=True)

    class Meta:
        model = LineClearance
        fields = [
            'id', 'date', 'line', 'line_name', 'production_plan',
            'document_id', 'status', 'qa_approved',
            'created_by', 'created_at',
        ]


class LineClearanceUpdateSerializer(serializers.Serializer):
    items = LineClearanceItemUpdateSerializer(many=True, required=False)
    production_supervisor_sign = serializers.CharField(
        max_length=200, required=False, allow_blank=True
    )
    production_incharge_sign = serializers.CharField(
        max_length=200, required=False, allow_blank=True
    )


# ---------------------------------------------------------------------------
# Machine Checklists
# ---------------------------------------------------------------------------

class MachineChecklistEntrySerializer(serializers.ModelSerializer):
    machine_name = serializers.CharField(source='machine.name', read_only=True)

    class Meta:
        model = MachineChecklistEntry
        fields = [
            'id', 'machine', 'machine_name', 'machine_type',
            'date', 'month', 'year', 'template',
            'task_description', 'frequency', 'status',
            'operator', 'shift_incharge', 'remarks',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class MachineChecklistCreateSerializer(serializers.Serializer):
    machine_id = serializers.IntegerField()
    template_id = serializers.IntegerField()
    date = serializers.DateField()
    status = serializers.CharField(max_length=10, default='NA')
    operator = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    shift_incharge = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    remarks = serializers.CharField(required=False, allow_blank=True, default='')


# ---------------------------------------------------------------------------
# Waste Management
# ---------------------------------------------------------------------------

class WasteLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WasteLog
        fields = [
            'id', 'production_run', 'material_code', 'material_name',
            'wastage_qty', 'uom', 'reason',
            'engineer_sign', 'engineer_signed_by', 'engineer_signed_at',
            'am_sign', 'am_signed_by', 'am_signed_at',
            'store_sign', 'store_signed_by', 'store_signed_at',
            'hod_sign', 'hod_signed_by', 'hod_signed_at',
            'wastage_approval_status',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class WasteLogCreateSerializer(serializers.Serializer):
    production_run_id = serializers.IntegerField()
    material_code = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    material_name = serializers.CharField(max_length=255)
    wastage_qty = serializers.DecimalField(max_digits=12, decimal_places=3)
    uom = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    reason = serializers.CharField(required=False, allow_blank=True, default='')


class WasteApprovalSerializer(serializers.Serializer):
    sign = serializers.CharField(max_length=200)
    remarks = serializers.CharField(required=False, allow_blank=True, default='')


# ---------------------------------------------------------------------------
# Resource Tracking Serializers
# ---------------------------------------------------------------------------

class ResourceElectricitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceElectricity
        fields = ['id', 'description', 'units_consumed', 'rate_per_unit', 'total_cost', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'total_cost', 'created_at', 'updated_at']


class ResourceElectricityCreateSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=200, required=False, default='')
    units_consumed = serializers.DecimalField(max_digits=12, decimal_places=3)
    rate_per_unit = serializers.DecimalField(max_digits=12, decimal_places=4)


class ResourceWaterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceWater
        fields = ['id', 'description', 'volume_consumed', 'rate_per_unit', 'total_cost', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'total_cost', 'created_at', 'updated_at']


class ResourceWaterCreateSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=200, required=False, default='')
    volume_consumed = serializers.DecimalField(max_digits=12, decimal_places=3)
    rate_per_unit = serializers.DecimalField(max_digits=12, decimal_places=4)


class ResourceGasSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceGas
        fields = ['id', 'description', 'qty_consumed', 'rate_per_unit', 'total_cost', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'total_cost', 'created_at', 'updated_at']


class ResourceGasCreateSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=200, required=False, default='')
    qty_consumed = serializers.DecimalField(max_digits=12, decimal_places=3)
    rate_per_unit = serializers.DecimalField(max_digits=12, decimal_places=4)


class ResourceCompressedAirSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceCompressedAir
        fields = ['id', 'description', 'units_consumed', 'rate_per_unit', 'total_cost', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'total_cost', 'created_at', 'updated_at']


class ResourceCompressedAirCreateSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=200, required=False, default='')
    units_consumed = serializers.DecimalField(max_digits=12, decimal_places=3)
    rate_per_unit = serializers.DecimalField(max_digits=12, decimal_places=4)


class ResourceLabourSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceLabour
        fields = ['id', 'worker_name', 'hours_worked', 'rate_per_hour', 'total_cost', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'total_cost', 'created_at', 'updated_at']


class ResourceLabourCreateSerializer(serializers.Serializer):
    worker_name = serializers.CharField(max_length=200)
    hours_worked = serializers.DecimalField(max_digits=8, decimal_places=2)
    rate_per_hour = serializers.DecimalField(max_digits=12, decimal_places=4)


class ResourceMachineCostSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceMachineCost
        fields = ['id', 'machine_name', 'hours_used', 'rate_per_hour', 'total_cost', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'total_cost', 'created_at', 'updated_at']


class ResourceMachineCostCreateSerializer(serializers.Serializer):
    machine_name = serializers.CharField(max_length=200)
    hours_used = serializers.DecimalField(max_digits=8, decimal_places=2)
    rate_per_hour = serializers.DecimalField(max_digits=12, decimal_places=4)


class ResourceOverheadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceOverhead
        fields = ['id', 'expense_name', 'amount', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ResourceOverheadCreateSerializer(serializers.Serializer):
    expense_name = serializers.CharField(max_length=200)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)


# ---------------------------------------------------------------------------
# Cost Summary Serializer
# ---------------------------------------------------------------------------

class ProductionRunCostSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionRunCost
        fields = [
            'id', 'raw_material_cost', 'labour_cost', 'machine_cost',
            'electricity_cost', 'water_cost', 'gas_cost', 'compressed_air_cost',
            'overhead_cost', 'total_cost', 'produced_qty', 'per_unit_cost', 'calculated_at'
        ]
        read_only_fields = [
            'id', 'raw_material_cost', 'labour_cost', 'machine_cost',
            'electricity_cost', 'water_cost', 'gas_cost', 'compressed_air_cost',
            'overhead_cost', 'total_cost', 'produced_qty', 'per_unit_cost', 'calculated_at'
        ]


# ---------------------------------------------------------------------------
# QC Check Serializers
# ---------------------------------------------------------------------------

class InProcessQCCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = InProcessQCCheck
        fields = [
            'id', 'checked_at', 'parameter', 'acceptable_min', 'acceptable_max',
            'actual_value', 'result', 'remarks', 'checked_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class InProcessQCCheckCreateSerializer(serializers.Serializer):
    checked_at = serializers.DateTimeField()
    parameter = serializers.CharField(max_length=200)
    acceptable_min = serializers.DecimalField(max_digits=10, decimal_places=3, required=False, allow_null=True)
    acceptable_max = serializers.DecimalField(max_digits=10, decimal_places=3, required=False, allow_null=True)
    actual_value = serializers.DecimalField(max_digits=10, decimal_places=3, required=False, allow_null=True)
    result = serializers.ChoiceField(choices=['PASS', 'FAIL', 'NA'], default='NA')
    remarks = serializers.CharField(required=False, default='', allow_blank=True)


class FinalQCCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinalQCCheck
        fields = [
            'id', 'checked_at', 'overall_result', 'parameters',
            'remarks', 'checked_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class FinalQCCheckCreateSerializer(serializers.Serializer):
    checked_at = serializers.DateTimeField()
    overall_result = serializers.ChoiceField(choices=['PASS', 'FAIL', 'CONDITIONAL'])
    parameters = serializers.ListField(child=serializers.DictField(), default=list)
    remarks = serializers.CharField(required=False, default='', allow_blank=True)


# ---------------------------------------------------------------------------
# SAP Order Serializers (plain, not model-based)
# ---------------------------------------------------------------------------

class SAPProductionOrderSerializer(serializers.Serializer):
    DocEntry = serializers.IntegerField()
    DocNum = serializers.IntegerField()
    ItemCode = serializers.CharField()
    ItemName = serializers.CharField()
    PlannedQty = serializers.FloatField()
    CmpltQty = serializers.FloatField()
    RjctQty = serializers.FloatField()
    RemainingQty = serializers.FloatField()
    StartDate = serializers.DateField(allow_null=True)
    DueDate = serializers.DateField(allow_null=True)
    Warehouse = serializers.CharField(allow_null=True, allow_blank=True)
    Status = serializers.CharField()


class SAPOrderComponentSerializer(serializers.Serializer):
    ItemCode = serializers.CharField()
    ItemName = serializers.CharField()
    PlannedQty = serializers.FloatField()
    IssuedQty = serializers.FloatField()
    Warehouse = serializers.CharField(allow_null=True, allow_blank=True)
    UomCode = serializers.CharField(allow_null=True, allow_blank=True)
