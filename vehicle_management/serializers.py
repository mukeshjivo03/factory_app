from rest_framework import serializers
from .models import Transporter,Vehicle, VehicleType
from driver_management.models import VehicleEntry
from driver_management.serializers import DriverSerializer
from company.serializers import CompanySerializer

class VehicleTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleType
        fields = [
            "id",
            "name",
        ]
        read_only_fields = ("id",)

class TransporterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transporter
        fields = [
            "id",
            "name",
            "contact_person",
            "mobile_no",
            "created_at",
        ]
        read_only_fields = ("id", "created_at")

class TransporterNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transporter
        fields = [
            "id",
            "name",
        ]
        read_only_fields = ("id",)

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            "id",
            "vehicle_number",
            "vehicle_type",
            "transporter",
            "capacity_ton",
            "created_at",
        ]
        read_only_fields = ("id", "created_at")

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["transporter"] = TransporterSerializer(instance.transporter).data
        representation["vehicle_type"] = VehicleTypeSerializer(instance.vehicle_type).data
        return representation
    
class VehicleNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            "id",
            "vehicle_number",
        ]
        read_only_fields = ("id",)


class VehicleEntrySerializer(serializers.ModelSerializer):

    class Meta:
        model = VehicleEntry
        fields = [
            "id",
            "entry_no",
            "company",
            "vehicle",
            "driver",
            "status",
            "entry_time",
            "entry_type",
            "remarks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = (
            "id",
            "status",
            "entry_time",
            "created_at",
            "updated_at",
        )

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["vehicle"] = VehicleSerializer(instance.vehicle).data
        representation["driver"] = DriverSerializer(instance.driver, context={"request": self.context.get("request")}).data
        representation["company"] = CompanySerializer(instance.company).data
        representation["suppliers"] = [
            {"supplier_code": po.supplier_code, "supplier_name": po.supplier_name}
            for po in instance.po_receipts.all()
        ]
        return representation
    

