from rest_framework import serializers
from security_checks.models.security_check import SecurityCheck


class SecurityCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityCheck
        fields = [
            "id",
            "vehicle_condition_ok",
            "tyre_condition_ok",
            "fire_extinguisher_available",
            "seal_no_before",
            "seal_no_after",
            "alcohol_test_done",
            "alcohol_test_passed",
            "inspected_by_name",
            "inspection_time",
            "remarks",
            "is_submitted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = (
            "id",
            "inspection_time",
            "is_submitted",
            "created_at",
            "updated_at",
        )
