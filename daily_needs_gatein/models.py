import re
from decimal import Decimal

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from driver_management.models import VehicleEntry
from accounts.models import Department
from gate_core.models import UnitChoice


def validate_phone_number(value):
    if value:
        cleaned = re.sub(r'[\s\-]', '', value)
        if not re.match(r'^\+?[0-9]{10,15}$', cleaned):
            raise ValidationError(
                "Invalid phone number format. Use 10-15 digits, optionally starting with +"
            )


class CategoryList(models.Model):
    category_name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["category_name"]
        permissions = [
            ("can_manage_category", "Can manage category"),
        ]

    def __str__(self):
        return self.category_name


class DailyNeedGateEntry(models.Model):

    # Parent
    vehicle_entry = models.OneToOneField(
        VehicleEntry,
        on_delete=models.CASCADE,
        related_name="daily_need_entry"
    )

    # Category
    item_category = models.ForeignKey(
        'CategoryList',
        on_delete=models.SET_NULL,
        null=True,
        related_name="daily_need_entries"
    )

    # Material
    supplier_name = models.CharField(max_length=200)
    material_name = models.CharField(max_length=200)

    # Quantity
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"), message="Quantity must be positive")]
    )
    unit = models.ForeignKey(
        UnitChoice,
        on_delete=models.SET_NULL,
        null=True,
        related_name="daily_need_entries"
    )

    receiving_department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        related_name="daily_need_entries"
    )

    # Documents
    bill_number = models.CharField(max_length=100, blank=True, null=True)
    delivery_challan_number = models.CharField(max_length=100, blank=True, null=True)

    # Contact
    canteen_supervisor = models.CharField(max_length=100, blank=True, null=True)
    vehicle_or_person_name = models.CharField(max_length=100, blank=True, null=True)
    contact_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        validators=[validate_phone_number]
    )

    # Notes
    remarks = models.TextField(blank=True, null=True)

    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="daily_need_entries"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["item_category"]),
            models.Index(fields=["created_at"]),
        ]
        permissions = [
            ("can_complete_daily_need_entry", "Can complete daily need gate entry"),
        ]

    def __str__(self):
        return f"{self.material_name} ({self.quantity} {self.unit})"
    



