from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from driver_management.models import VehicleEntry
from gate_core.models import UnitChoice


class ConstructionMaterialCategory(models.Model):
    """
    Lookup table for construction material categories.
    Examples: Cement, Steel/Rebar, Bricks/Blocks, Sand, etc.
    """
    category_name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category_name"]
        permissions = [
            ("can_manage_material_category", "Can manage material category"),
        ]

    def __str__(self):
        return self.category_name


class ConstructionGateEntry(models.Model):
    """
    Construction / Civil Work Material Gate Pass entry.
    Linked to VehicleEntry via OneToOne relationship.
    """

    SECURITY_APPROVAL_CHOICES = (
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    )

    phone_validator = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in format: '+999999999'. Up to 15 digits allowed."
    )

    # Parent - OneToOne with VehicleEntry
    vehicle_entry = models.OneToOneField(
        VehicleEntry,
        on_delete=models.CASCADE,
        related_name="construction_entry"
    )

    # Project Information
    project_name = models.CharField(max_length=200, blank=True, null=True)

    # Work Order Number (auto-generated: WO-YYYY-NNN)
    work_order_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True
    )

    # Contractor Information
    contractor_name = models.CharField(max_length=200)
    contractor_contact = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        validators=[phone_validator]
    )

    # Material Information
    material_category = models.ForeignKey(
        ConstructionMaterialCategory,
        on_delete=models.SET_NULL,
        null=True,
        related_name="construction_entries"
    )
    material_description = models.TextField()

    # Quantity and Unit
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01, message="Quantity must be positive")]
    )
    unit = models.ForeignKey(
        UnitChoice,
        on_delete=models.SET_NULL,
        null=True,
        related_name="construction_entries"
    )

    # Documents
    challan_number = models.CharField(max_length=100, blank=True, null=True)
    invoice_number = models.CharField(max_length=100, blank=True, null=True)

    # Approval Information
    site_engineer = models.CharField(max_length=100, blank=True, null=True)
    security_approval = models.CharField(
        max_length=10,
        choices=SECURITY_APPROVAL_CHOICES,
        default="PENDING"
    )

    # Notes
    remarks = models.TextField(blank=True, null=True)

    # Inward Time
    inward_time = models.DateTimeField(auto_now_add=True)

    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="construction_entries"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["material_category"]),
            models.Index(fields=["security_approval"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["work_order_number"]),
        ]
        permissions = [
            ("can_complete_construction_entry", "Can complete construction gate entry"),
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
        last_entry = ConstructionGateEntry.objects.filter(
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
