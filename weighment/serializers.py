from rest_framework import serializers
from .models import Weighment


class WeighmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Weighment
        fields = [
            "id",
            "gross_weight",
            "tare_weight",
            "net_weight",
            "weighbridge_slip_no",
            "first_weighment_time",
            "second_weighment_time",
            "remarks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = (
            "id",
            "net_weight",
            "created_at",
            "updated_at",
        )
