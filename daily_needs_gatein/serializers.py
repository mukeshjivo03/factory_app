import re
from rest_framework import serializers
from daily_needs_gatein.models import DailyNeedGateEntry


class DailyNeedGateEntrySerializer(serializers.ModelSerializer):

    class Meta:
        model = DailyNeedGateEntry
        exclude = ("created_by", "vehicle_entry")
        read_only_fields = ("created_at", "updated_at")

    def validate_quantity(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("Quantity must be a positive number")
        return value

    def validate_contact_number(self, value):
        if value:
            cleaned = re.sub(r'[\s\-]', '', value)
            if not re.match(r'^\+?[0-9]{10,15}$', cleaned):
                raise serializers.ValidationError(
                    "Invalid phone number format. Use 10-15 digits, optionally starting with +"
                )
        return value

    def validate_supplier_name(self, value):
        if value and len(value.strip()) < 2:
            raise serializers.ValidationError("Supplier name must be at least 2 characters")
        return value.strip() if value else value

    def validate_material_name(self, value):
        if value and len(value.strip()) < 2:
            raise serializers.ValidationError("Material name must be at least 2 characters")
        return value.strip() if value else value
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.item_category:
            data['item_category'] = {
                'id': instance.item_category.id,
                'category_name': instance.item_category.category_name
            }
            data["receiving_department"] = {
                'id': instance.receiving_department.id,
                'name': instance.receiving_department.name
            }
        if instance.unit:
            data['unit'] = {
                'id': instance.unit.id,
                'name': instance.unit.name
            }
        return data



class CategoryListSerializer(serializers.ModelSerializer):

    class Meta:
        model = DailyNeedGateEntry.item_category.field.related_model
        fields = "__all__"