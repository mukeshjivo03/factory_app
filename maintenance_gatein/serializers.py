from rest_framework import serializers
from .models import MaintenanceGateEntry, MaintenanceType


class MaintenanceTypeSerializer(serializers.ModelSerializer):
    """Serializer for MaintenanceType lookup"""

    class Meta:
        model = MaintenanceType
        fields = "__all__"


class MaintenanceGateEntrySerializer(serializers.ModelSerializer):
    """
    Serializer for MaintenanceGateEntry.
    Follows same pattern as DailyNeedGateEntrySerializer.
    """

    class Meta:
        model = MaintenanceGateEntry
        exclude = ("created_by", "vehicle_entry")
        read_only_fields = ("created_at", "updated_at")

    def validate_quantity(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("Quantity must be a positive number")
        return value

    def validate_supplier_name(self, value):
        if value and len(value.strip()) < 2:
            raise serializers.ValidationError("Supplier name must be at least 2 characters")
        return value.strip() if value else value

    def validate_material_description(self, value):
        if value and len(value.strip()) < 5:
            raise serializers.ValidationError("Material description must be at least 5 characters")
        return value.strip() if value else value

    def to_representation(self, instance):
        """Expand ForeignKey fields for API response"""
        data = super().to_representation(instance)

        # Expand maintenance_type
        if instance.maintenance_type:
            data['maintenance_type'] = {
                'id': instance.maintenance_type.id,
                'type_name': instance.maintenance_type.type_name
            }

        # Expand receiving_department
        if instance.receiving_department:
            data['receiving_department'] = {
                'id': instance.receiving_department.id,
                'name': instance.receiving_department.name
            }
        
        if instance.unit:
            data['unit'] = {
                'id': instance.unit.id,
                'name': instance.unit.name
            }

        return data
