from rest_framework import serializers
from .models import ConstructionGateEntry, ConstructionMaterialCategory


class ConstructionMaterialCategorySerializer(serializers.ModelSerializer):
    """Serializer for ConstructionMaterialCategory lookup"""

    class Meta:
        model = ConstructionMaterialCategory
        fields = "__all__"


class ConstructionGateEntrySerializer(serializers.ModelSerializer):
    """
    Serializer for ConstructionGateEntry.
    Follows same pattern as MaintenanceGateEntrySerializer.
    """

    class Meta:
        model = ConstructionGateEntry
        exclude = ("created_by", "vehicle_entry")
        read_only_fields = ("created_at", "updated_at")

    def validate_quantity(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("Quantity must be a positive number")
        return value

    def validate_contractor_name(self, value):
        if value and len(value.strip()) < 2:
            raise serializers.ValidationError("Contractor name must be at least 2 characters")
        return value.strip() if value else value

    def validate_material_description(self, value):
        if value and len(value.strip()) < 5:
            raise serializers.ValidationError("Material description must be at least 5 characters")
        return value.strip() if value else value

    def to_representation(self, instance):
        """Expand ForeignKey fields for API response"""
        data = super().to_representation(instance)

        # Expand material_category
        if instance.material_category:
            data['material_category'] = {
                'id': instance.material_category.id,
                'category_name': instance.material_category.category_name
            }
        
        if instance.unit:
            data['unit'] = {
                'id': instance.unit.id,
                'name': instance.unit.name
            }

        return data



