from decimal import Decimal

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from driver_management.models import VehicleEntry
from accounts.models import Department
from gate_core.models import UnitChoice


class MaintenanceType(models.Model):
    """
    Lookup table for maintenance types.
    Examples: Electrical, Mechanical, Plumbing, HVAC, Civil, Equipment Repair, etc.
    """
    type_name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["type_name"]
        permissions = [
            ("can_manage_maintenance_type", "Can manage maintenance type"),
        ]

    def __str__(self):
        return self.type_name


class MaintenanceGateEntry(models.Model):
    """
    Maintenance & Repair Material Gate Pass entry.
    Linked to VehicleEntry via OneToOne relationship.
    """

    URGENCY_CHOICES = (
        ("NORMAL", "Normal"),
        ("HIGH", "High"),
        ("CRITICAL", "Critical"),
    )

    # Parent - OneToOne with VehicleEntry
    vehicle_entry = models.OneToOneField(
        VehicleEntry,
        on_delete=models.CASCADE,
        related_name="maintenance_entry"
    )

    # Maintenance Type
    maintenance_type = models.ForeignKey(
        MaintenanceType,
        on_delete=models.SET_NULL,
        null=True,
        related_name="maintenance_entries"
    )

    # Work Order Number (auto-generated: WO-YYYY-NNN)
    work_order_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True
    )

    # Supplier Information
    supplier_name = models.CharField(max_length=200)

    # Material Information
    material_description = models.TextField()
    part_number = models.CharField(max_length=100, blank=True, null=True)

    # Quantity and Unit
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"), message="Quantity must be positive")]
    )
    unit = models.ForeignKey(
        UnitChoice,
        on_delete=models.SET_NULL,
        null=True,
        related_name="maintenance_entries"
    )

    # Documents
    invoice_number = models.CharField(max_length=100, blank=True, null=True)

    # Equipment Information
    equipment_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Equipment/Machine ID for the repair/maintenance"
    )

    # Department
    receiving_department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        related_name="maintenance_entries"
    )

    # Urgency Level
    urgency_level = models.CharField(
        max_length=10,
        choices=URGENCY_CHOICES,
        default="NORMAL"
    )

    # Inward Time
    inward_time = models.DateTimeField(auto_now_add=True)

    # Notes
    remarks = models.TextField(blank=True, null=True)

    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="maintenance_entries"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["maintenance_type"]),
            models.Index(fields=["urgency_level"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["work_order_number"]),
        ]
        permissions = [
            ("can_complete_maintenance_entry", "Can complete maintenance gate entry"),
        ]

    def __str__(self):
        return f"{self.material_description[:50]} ({self.quantity} {self.unit})"

    def save(self, *args, **kwargs):
        # Auto-generate work_order_number if not provided
        if not self.work_order_number:
            self.work_order_number = self._generate_work_order_number()
        super().save(*args, **kwargs)

    def _generate_work_order_number(self):
        """Generate work order number in format: WO-YYYY-NNN"""
        from django.utils import timezone
        year = timezone.now().year

        # Get the last work order number for this year
        last_entry = MaintenanceGateEntry.objects.filter(
            work_order_number__startswith=f"WO-{year}-"
        ).order_by("-work_order_number").first()

        if last_entry and last_entry.work_order_number:
            try:
                last_number = int(last_entry.work_order_number.split("-")[-1])
                new_number = last_number + 1
            except (ValueError, IndexError):
                new_number = 1
        else:
            new_number = 1

        return f"WO-{year}-{new_number:03d}"
