from decimal import Decimal
from unittest.mock import patch, MagicMock
from io import BytesIO

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from gate_core.enums import GateEntryStatus
from company.models import Company
from driver_management.models import VehicleEntry, Driver
from vehicle_management.models import Vehicle, VehicleType
from raw_material_gatein.models import POReceipt, POItemReceipt
from grpo.models import GRPOPosting, GRPOLinePosting, GRPOStatus, GRPOAttachment, SAPAttachmentStatus
from grpo.services import GRPOService

User = get_user_model()


class GRPOModelTests(TestCase):
    """Tests for GRPO models"""

    @classmethod
    def setUpTestData(cls):
        # Create company
        cls.company = Company.objects.create(
            name="Test Company",
            code="TC001"
        )

        # Create user
        cls.user = User.objects.create_user(
            email="testuser@example.com",
            password="testpass123",
            full_name="Test User",
            employee_code="EMP001"
        )

        # Create vehicle
        cls.vehicle_type = VehicleType.objects.create(name="TRUCK")
        cls.vehicle = Vehicle.objects.create(
            vehicle_number="MH12AB1234",
            vehicle_type=cls.vehicle_type
        )

        # Create driver
        cls.driver = Driver.objects.create(
            name="Test Driver",
            mobile_no="9876543210",
            license_no="DL123456"
        )

        # Create vehicle entry
        cls.vehicle_entry = VehicleEntry.objects.create(
            entry_no="VE-2024-001",
            company=cls.company,
            vehicle=cls.vehicle,
            driver=cls.driver,
            entry_type="RAW_MATERIAL",
            status=GateEntryStatus.COMPLETED
        )

        # Create PO receipt with SAP doc entry
        cls.po_receipt = POReceipt.objects.create(
            vehicle_entry=cls.vehicle_entry,
            po_number="PO-001",
            supplier_code="SUP001",
            supplier_name="Test Supplier",
            sap_doc_entry=12345
        )

    def test_grpo_posting_creation(self):
        """Test GRPOPosting model creation"""
        grpo = GRPOPosting.objects.create(
            vehicle_entry=self.vehicle_entry,
            po_receipt=self.po_receipt,
            status=GRPOStatus.PENDING
        )

        self.assertEqual(grpo.status, GRPOStatus.PENDING)
        self.assertIsNone(grpo.sap_doc_entry)
        self.assertIsNone(grpo.sap_doc_num)

    def test_grpo_posting_str(self):
        """Test GRPOPosting string representation"""
        grpo = GRPOPosting.objects.create(
            vehicle_entry=self.vehicle_entry,
            po_receipt=self.po_receipt,
            status=GRPOStatus.POSTED,
            sap_doc_num=12345
        )

        self.assertIn("PO-001", str(grpo))
        self.assertIn("POSTED", str(grpo))

    def test_grpo_unique_constraint(self):
        """Test that same vehicle_entry + po_receipt cannot have duplicate"""
        GRPOPosting.objects.create(
            vehicle_entry=self.vehicle_entry,
            po_receipt=self.po_receipt,
            status=GRPOStatus.PENDING
        )

        with self.assertRaises(Exception):
            GRPOPosting.objects.create(
                vehicle_entry=self.vehicle_entry,
                po_receipt=self.po_receipt,
                status=GRPOStatus.PENDING
            )

    def test_grpo_line_posting_with_po_linking(self):
        """Test GRPOLinePosting stores base_entry and base_line"""
        grpo = GRPOPosting.objects.create(
            vehicle_entry=self.vehicle_entry,
            po_receipt=self.po_receipt,
            status=GRPOStatus.POSTED,
            sap_doc_num=100
        )
        po_item = POItemReceipt.objects.create(
            po_receipt=self.po_receipt,
            po_item_code="ITEM001",
            item_name="Test Item",
            ordered_qty=Decimal("100.000"),
            received_qty=Decimal("100.000"),
            sap_line_num=0,
            uom="KG"
        )
        line = GRPOLinePosting.objects.create(
            grpo_posting=grpo,
            po_item_receipt=po_item,
            quantity_posted=Decimal("95.000"),
            base_entry=12345,
            base_line=0
        )
        self.assertEqual(line.base_entry, 12345)
        self.assertEqual(line.base_line, 0)


class GRPOServiceTests(TestCase):
    """Tests for GRPO service layer"""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            name="Test Company",
            code="TC001"
        )

        cls.user = User.objects.create_user(
            email="testuser@example.com",
            password="testpass123",
            full_name="Test User",
            employee_code="EMP001"
        )

        cls.vehicle_type = VehicleType.objects.create(name="TRUCK")
        cls.vehicle = Vehicle.objects.create(
            vehicle_number="MH12AB1234",
            vehicle_type=cls.vehicle_type
        )

        cls.driver = Driver.objects.create(
            name="Test Driver",
            mobile_no="9876543210",
            license_no="DL123456"
        )

        cls.vehicle_entry = VehicleEntry.objects.create(
            entry_no="VE-2024-001",
            company=cls.company,
            vehicle=cls.vehicle,
            driver=cls.driver,
            entry_type="RAW_MATERIAL",
            status=GateEntryStatus.COMPLETED
        )

        cls.po_receipt = POReceipt.objects.create(
            vehicle_entry=cls.vehicle_entry,
            po_number="PO-001",
            supplier_code="SUP001",
            supplier_name="Test Supplier",
            sap_doc_entry=12345,
            branch_id=1,
            vendor_ref="VINV-2026-001"
        )

        cls.po_item = POItemReceipt.objects.create(
            po_receipt=cls.po_receipt,
            po_item_code="ITEM001",
            item_name="Test Item",
            ordered_qty=Decimal("100.000"),
            received_qty=Decimal("100.000"),
            accepted_qty=Decimal("95.000"),
            rejected_qty=Decimal("5.000"),
            sap_line_num=0,
            unit_price=Decimal("85.500000"),
            tax_code="GST18",
            warehouse_code="WH-01",
            gl_account="40001001",
            uom="KG"
        )

    def test_get_pending_grpo_entries(self):
        """Test fetching pending GRPO entries"""
        service = GRPOService(company_code="TC001")
        entries = service.get_pending_grpo_entries()

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].entry_no, "VE-2024-001")

    def test_get_grpo_preview_data(self):
        """Test getting GRPO preview data returns all PO details for pre-fill"""
        service = GRPOService(company_code="TC001")
        preview_data = service.get_grpo_preview_data(self.vehicle_entry.id)

        self.assertEqual(len(preview_data), 1)
        po_data = preview_data[0]

        # PO header fields
        self.assertEqual(po_data["po_number"], "PO-001")
        self.assertEqual(po_data["supplier_code"], "SUP001")
        self.assertEqual(po_data["sap_doc_entry"], 12345)
        self.assertEqual(po_data["branch_id"], 1)
        self.assertEqual(po_data["vendor_ref"], "VINV-2026-001")
        self.assertTrue(po_data["is_ready_for_grpo"])

        # Item-level pre-filled fields
        self.assertEqual(len(po_data["items"]), 1)
        item = po_data["items"][0]
        self.assertEqual(item["unit_price"], Decimal("85.500000"))
        self.assertEqual(item["tax_code"], "GST18")
        self.assertEqual(item["warehouse_code"], "WH-01")
        self.assertEqual(item["gl_account"], "40001001")
        self.assertEqual(item["sap_line_num"], 0)

    def test_get_grpo_preview_invalid_entry(self):
        """Test getting preview data for non-existent entry"""
        service = GRPOService(company_code="TC001")

        with self.assertRaises(ValueError) as context:
            service.get_grpo_preview_data(99999)

        self.assertIn("not found", str(context.exception))

    @patch('grpo.services.SAPClient')
    def test_post_grpo_success_with_po_linking(self, mock_sap_client):
        """Test successful GRPO posting includes PO linking fields"""
        mock_instance = MagicMock()
        mock_instance.create_grpo.return_value = {
            "DocEntry": 123,
            "DocNum": 456,
            "DocTotal": 4750.00
        }
        mock_sap_client.return_value = mock_instance

        service = GRPOService(company_code="TC001")
        grpo = service.post_grpo(
            vehicle_entry_id=self.vehicle_entry.id,
            po_receipt_id=self.po_receipt.id,
            user=self.user,
            items=[{
                "po_item_receipt_id": self.po_item.id,
                "accepted_qty": Decimal("95.000"),
            }],
            branch_id=1,
            warehouse_code="WH01",
        )

        self.assertEqual(grpo.status, GRPOStatus.POSTED)
        self.assertEqual(grpo.sap_doc_entry, 123)
        self.assertEqual(grpo.sap_doc_num, 456)

        # Verify SAP payload includes PO linking
        call_args = mock_instance.create_grpo.call_args[0][0]
        doc_line = call_args["DocumentLines"][0]
        self.assertEqual(doc_line["BaseEntry"], 12345)
        self.assertEqual(doc_line["BaseLine"], 0)
        self.assertEqual(doc_line["BaseType"], 22)
        self.assertEqual(doc_line["WarehouseCode"], "WH01")

        # Verify structured comments
        self.assertIn("App: FactoryApp v2", call_args["Comments"])
        self.assertIn("PO: PO-001", call_args["Comments"])

        # Check line posting created with base_entry/base_line
        self.assertEqual(grpo.lines.count(), 1)
        line = grpo.lines.first()
        self.assertEqual(line.quantity_posted, Decimal("95.000"))
        self.assertEqual(line.base_entry, 12345)
        self.assertEqual(line.base_line, 0)

    @patch('grpo.services.SAPClient')
    def test_post_grpo_with_line_level_fields(self, mock_sap_client):
        """Test GRPO posting with unit_price, tax_code, gl_account, variety"""
        mock_instance = MagicMock()
        mock_instance.create_grpo.return_value = {
            "DocEntry": 200,
            "DocNum": 500,
            "DocTotal": 9500.00
        }
        mock_sap_client.return_value = mock_instance

        service = GRPOService(company_code="TC001")
        grpo = service.post_grpo(
            vehicle_entry_id=self.vehicle_entry.id,
            po_receipt_id=self.po_receipt.id,
            user=self.user,
            items=[{
                "po_item_receipt_id": self.po_item.id,
                "accepted_qty": Decimal("95.000"),
                "unit_price": Decimal("100.50"),
                "tax_code": "GST18",
                "gl_account": "500100",
                "variety": "Grade-A",
            }],
            branch_id=1,
            vendor_ref="INV-2024-001",
        )

        call_args = mock_instance.create_grpo.call_args[0][0]

        # Header fields
        self.assertEqual(call_args["NumAtCard"], "INV-2024-001")

        # Line-level fields
        doc_line = call_args["DocumentLines"][0]
        self.assertEqual(doc_line["UnitPrice"], 100.50)
        self.assertEqual(doc_line["TaxCode"], "GST18")
        self.assertEqual(doc_line["AccountCode"], "500100")
        self.assertEqual(doc_line["U_Variety"], "Grade-A")

    @patch('grpo.services.SAPClient')
    def test_post_grpo_with_extra_charges(self, mock_sap_client):
        """Test GRPO posting with DocumentAdditionalExpenses"""
        mock_instance = MagicMock()
        mock_instance.create_grpo.return_value = {
            "DocEntry": 300,
            "DocNum": 600,
            "DocTotal": 15000.00
        }
        mock_sap_client.return_value = mock_instance

        service = GRPOService(company_code="TC001")
        grpo = service.post_grpo(
            vehicle_entry_id=self.vehicle_entry.id,
            po_receipt_id=self.po_receipt.id,
            user=self.user,
            items=[{
                "po_item_receipt_id": self.po_item.id,
                "accepted_qty": Decimal("95.000"),
            }],
            branch_id=1,
            extra_charges=[
                {
                    "expense_code": 1,
                    "amount": Decimal("5000.00"),
                    "remarks": "Freight",
                    "tax_code": "GST18"
                }
            ],
        )

        call_args = mock_instance.create_grpo.call_args[0][0]
        self.assertIn("DocumentAdditionalExpenses", call_args)
        expense = call_args["DocumentAdditionalExpenses"][0]
        self.assertEqual(expense["ExpenseCode"], 1)
        self.assertEqual(expense["LineTotal"], 5000.00)
        self.assertEqual(expense["Remarks"], "Freight")
        self.assertEqual(expense["TaxCode"], "GST18")

    def test_post_grpo_already_posted(self):
        """Test posting GRPO that was already posted"""
        GRPOPosting.objects.create(
            vehicle_entry=self.vehicle_entry,
            po_receipt=self.po_receipt,
            status=GRPOStatus.POSTED,
            sap_doc_num=789
        )

        service = GRPOService(company_code="TC001")

        with self.assertRaises(ValueError) as context:
            service.post_grpo(
                vehicle_entry_id=self.vehicle_entry.id,
                po_receipt_id=self.po_receipt.id,
                user=self.user,
                items=[{
                    "po_item_receipt_id": self.po_item.id,
                    "accepted_qty": Decimal("95.000"),
                }],
                branch_id=1,
            )

        self.assertIn("already posted", str(context.exception))

    def test_post_grpo_entry_not_completed(self):
        """Test posting GRPO for non-completed entry"""
        self.vehicle_entry.status = GateEntryStatus.IN_PROGRESS
        self.vehicle_entry.save()

        service = GRPOService(company_code="TC001")

        with self.assertRaises(ValueError) as context:
            service.post_grpo(
                vehicle_entry_id=self.vehicle_entry.id,
                po_receipt_id=self.po_receipt.id,
                user=self.user,
                items=[{
                    "po_item_receipt_id": self.po_item.id,
                    "accepted_qty": Decimal("95.000"),
                }],
                branch_id=1,
            )

        self.assertIn("not completed", str(context.exception))

        # Reset status
        self.vehicle_entry.status = GateEntryStatus.COMPLETED
        self.vehicle_entry.save()

    def test_structured_comments(self):
        """Test structured comments building"""
        service = GRPOService(company_code="TC001")
        comments = service._build_structured_comments(
            self.user, self.po_receipt, self.vehicle_entry, "QC passed"
        )
        self.assertIn("App: FactoryApp v2", comments)
        self.assertIn("PO: PO-001", comments)
        self.assertIn("Gate Entry: VE-2024-001", comments)
        self.assertIn("QC passed", comments)


class GRPOAPITests(APITestCase):
    """Tests for GRPO API endpoints"""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            name="Test Company",
            code="TC001"
        )

        cls.user = User.objects.create_user(
            email="testuser@example.com",
            password="testpass123",
            full_name="Test User",
            employee_code="EMP001"
        )

        cls.vehicle_type = VehicleType.objects.create(name="TRUCK")
        cls.vehicle = Vehicle.objects.create(
            vehicle_number="MH12AB1234",
            vehicle_type=cls.vehicle_type
        )

        cls.driver = Driver.objects.create(
            name="Test Driver",
            mobile_no="9876543210",
            license_no="DL123456"
        )

        cls.vehicle_entry = VehicleEntry.objects.create(
            entry_no="VE-2024-001",
            company=cls.company,
            vehicle=cls.vehicle,
            driver=cls.driver,
            entry_type="RAW_MATERIAL",
            status=GateEntryStatus.COMPLETED
        )

        cls.po_receipt = POReceipt.objects.create(
            vehicle_entry=cls.vehicle_entry,
            po_number="PO-001",
            supplier_code="SUP001",
            supplier_name="Test Supplier",
            sap_doc_entry=12345
        )

        cls.po_item = POItemReceipt.objects.create(
            po_receipt=cls.po_receipt,
            po_item_code="ITEM001",
            item_name="Test Item",
            ordered_qty=Decimal("100.000"),
            received_qty=Decimal("100.000"),
            accepted_qty=Decimal("95.000"),
            rejected_qty=Decimal("5.000"),
            sap_line_num=0,
            uom="KG"
        )

    def setUp(self):
        self.client = APIClient()

    def test_pending_grpo_list_unauthenticated(self):
        """Test that unauthenticated requests are rejected"""
        response = self.client.get("/api/v1/grpo/pending/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_grpo_preview_unauthenticated(self):
        """Test that unauthenticated requests are rejected"""
        response = self.client.get(f"/api/v1/grpo/preview/{self.vehicle_entry.id}/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_post_grpo_unauthenticated(self):
        """Test that unauthenticated requests are rejected"""
        response = self.client.post("/api/v1/grpo/post/", {
            "vehicle_entry_id": self.vehicle_entry.id,
            "po_receipt_id": self.po_receipt.id
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_grpo_history_unauthenticated(self):
        """Test that unauthenticated requests are rejected"""
        response = self.client.get("/api/v1/grpo/history/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class GRPOSerializerTests(TestCase):
    """Tests for GRPO serializers"""

    def test_grpo_post_request_serializer_valid_full(self):
        """Test full GRPO post request with all new fields"""
        from grpo.serializers import GRPOPostRequestSerializer

        data = {
            "vehicle_entry_id": 1,
            "po_receipt_id": 2,
            "items": [
                {
                    "po_item_receipt_id": 10,
                    "accepted_qty": "95.000",
                    "unit_price": "50.00",
                    "tax_code": "GST18",
                    "gl_account": "500100",
                    "variety": "Grade-A"
                }
            ],
            "branch_id": 1,
            "warehouse_code": "WH01",
            "comments": "Test comment",
            "vendor_ref": "INV-2024-001",
            "extra_charges": [
                {
                    "expense_code": 1,
                    "amount": "5000.00",
                    "remarks": "Freight",
                    "tax_code": "GST18"
                }
            ]
        }

        serializer = GRPOPostRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        # Verify parsed values
        vd = serializer.validated_data
        self.assertEqual(vd["vendor_ref"], "INV-2024-001")
        self.assertEqual(len(vd["extra_charges"]), 1)
        self.assertEqual(vd["extra_charges"][0]["expense_code"], 1)
        self.assertEqual(vd["items"][0]["unit_price"], Decimal("50.00"))
        self.assertEqual(vd["items"][0]["variety"], "Grade-A")

    def test_grpo_post_request_serializer_minimal(self):
        """Test minimal GRPO post request (only required fields)"""
        from grpo.serializers import GRPOPostRequestSerializer

        data = {
            "vehicle_entry_id": 1,
            "po_receipt_id": 2,
            "items": [
                {"po_item_receipt_id": 10, "accepted_qty": "95.000"}
            ],
            "branch_id": 1,
        }

        serializer = GRPOPostRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_grpo_post_request_serializer_invalid(self):
        """Test invalid GRPO post request"""
        from grpo.serializers import GRPOPostRequestSerializer

        data = {
            "vehicle_entry_id": 1
            # Missing required po_receipt_id, items, branch_id
        }

        serializer = GRPOPostRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("po_receipt_id", serializer.errors)
        self.assertIn("items", serializer.errors)
        self.assertIn("branch_id", serializer.errors)

    def test_grpo_item_input_serializer_with_optional_fields(self):
        """Test item input serializer accepts optional fields"""
        from grpo.serializers import GRPOItemInputSerializer

        data = {
            "po_item_receipt_id": 1,
            "accepted_qty": "100.000",
            "unit_price": "50.50",
            "tax_code": "GST18",
            "gl_account": "500100",
            "variety": "Grade-A"
        }

        serializer = GRPOItemInputSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_extra_charge_serializer(self):
        """Test extra charge serializer validation"""
        from grpo.serializers import ExtraChargeInputSerializer

        data = {
            "expense_code": 1,
            "amount": "5000.00",
            "remarks": "Freight charges",
            "tax_code": "GST18"
        }

        serializer = ExtraChargeInputSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)


class GRPOAttachmentModelTests(TestCase):
    """Tests for GRPOAttachment model"""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Test Company", code="TC001")
        cls.user = User.objects.create_user(
            email="testuser@example.com", password="testpass123",
            full_name="Test User", employee_code="EMP001"
        )
        cls.vehicle_type = VehicleType.objects.create(name="TRUCK")
        cls.vehicle = Vehicle.objects.create(
            vehicle_number="MH12AB1234", vehicle_type=cls.vehicle_type
        )
        cls.driver = Driver.objects.create(
            name="Test Driver", mobile_no="9876543210", license_no="DL123456"
        )
        cls.vehicle_entry = VehicleEntry.objects.create(
            entry_no="VE-2024-001", company=cls.company,
            vehicle=cls.vehicle, driver=cls.driver,
            entry_type="RAW_MATERIAL", status=GateEntryStatus.COMPLETED
        )
        cls.po_receipt = POReceipt.objects.create(
            vehicle_entry=cls.vehicle_entry, po_number="PO-001",
            supplier_code="SUP001", supplier_name="Test Supplier",
            sap_doc_entry=12345
        )
        cls.grpo_posting = GRPOPosting.objects.create(
            vehicle_entry=cls.vehicle_entry, po_receipt=cls.po_receipt,
            status=GRPOStatus.POSTED, sap_doc_entry=12345, sap_doc_num=456
        )

    def test_attachment_creation(self):
        """Test GRPOAttachment model creation"""
        test_file = SimpleUploadedFile("invoice.pdf", b"file_content", content_type="application/pdf")
        attachment = GRPOAttachment.objects.create(
            grpo_posting=self.grpo_posting,
            file=test_file,
            original_filename="invoice.pdf",
            sap_attachment_status=SAPAttachmentStatus.PENDING,
            uploaded_by=self.user
        )
        self.assertEqual(attachment.original_filename, "invoice.pdf")
        self.assertEqual(attachment.sap_attachment_status, SAPAttachmentStatus.PENDING)
        self.assertIsNone(attachment.sap_absolute_entry)
        # Clean up file
        attachment.file.delete(save=False)

    def test_attachment_str(self):
        """Test GRPOAttachment string representation"""
        test_file = SimpleUploadedFile("report.pdf", b"content", content_type="application/pdf")
        attachment = GRPOAttachment.objects.create(
            grpo_posting=self.grpo_posting,
            file=test_file,
            original_filename="report.pdf",
        )
        self.assertIn("report.pdf", str(attachment))
        attachment.file.delete(save=False)

    def test_attachment_cascade_delete(self):
        """Test attachments are deleted when GRPO posting is deleted"""
        # Create a new posting for this test
        po_receipt2 = POReceipt.objects.create(
            vehicle_entry=self.vehicle_entry, po_number="PO-002",
            supplier_code="SUP001", supplier_name="Test Supplier",
            sap_doc_entry=99999
        )
        posting = GRPOPosting.objects.create(
            vehicle_entry=self.vehicle_entry, po_receipt=po_receipt2,
            status=GRPOStatus.POSTED, sap_doc_entry=99999
        )
        test_file = SimpleUploadedFile("test.pdf", b"content")
        GRPOAttachment.objects.create(
            grpo_posting=posting, file=test_file,
            original_filename="test.pdf"
        )
        posting_id = posting.id
        self.assertEqual(GRPOAttachment.objects.filter(grpo_posting_id=posting_id).count(), 1)
        posting.delete()
        self.assertEqual(GRPOAttachment.objects.filter(grpo_posting_id=posting_id).count(), 0)


class GRPOAttachmentServiceTests(TestCase):
    """Tests for GRPO attachment service methods"""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Test Company", code="TC001")
        cls.user = User.objects.create_user(
            email="testuser@example.com", password="testpass123",
            full_name="Test User", employee_code="EMP001"
        )
        cls.vehicle_type = VehicleType.objects.create(name="TRUCK")
        cls.vehicle = Vehicle.objects.create(
            vehicle_number="MH12AB1234", vehicle_type=cls.vehicle_type
        )
        cls.driver = Driver.objects.create(
            name="Test Driver", mobile_no="9876543210", license_no="DL123456"
        )
        cls.vehicle_entry = VehicleEntry.objects.create(
            entry_no="VE-2024-001", company=cls.company,
            vehicle=cls.vehicle, driver=cls.driver,
            entry_type="RAW_MATERIAL", status=GateEntryStatus.COMPLETED
        )
        cls.po_receipt = POReceipt.objects.create(
            vehicle_entry=cls.vehicle_entry, po_number="PO-001",
            supplier_code="SUP001", supplier_name="Test Supplier",
            sap_doc_entry=12345
        )

    def _create_posted_grpo(self):
        """Helper to create a POSTED GRPO"""
        grpo, _ = GRPOPosting.objects.get_or_create(
            vehicle_entry=self.vehicle_entry,
            po_receipt=self.po_receipt,
            defaults={
                "status": GRPOStatus.POSTED,
                "sap_doc_entry": 12345,
                "sap_doc_num": 456,
                "posted_by": self.user
            }
        )
        if grpo.status != GRPOStatus.POSTED:
            grpo.status = GRPOStatus.POSTED
            grpo.sap_doc_entry = 12345
            grpo.sap_doc_num = 456
            grpo.save()
        return grpo

    @patch('grpo.services.SAPClient')
    def test_upload_attachment_success(self, mock_sap_client):
        """Test successful attachment upload and linking"""
        mock_instance = MagicMock()
        mock_instance.upload_attachment.return_value = {"AbsoluteEntry": 789}
        mock_instance.link_attachment_to_grpo.return_value = {
            "DocEntry": 12345, "AttachmentEntry": 789
        }
        mock_sap_client.return_value = mock_instance

        grpo = self._create_posted_grpo()
        service = GRPOService(company_code="TC001")
        test_file = SimpleUploadedFile("invoice.pdf", b"pdf_content", content_type="application/pdf")

        attachment = service.upload_grpo_attachment(
            grpo_posting_id=grpo.id,
            file=test_file,
            user=self.user
        )

        self.assertEqual(attachment.sap_attachment_status, SAPAttachmentStatus.LINKED)
        self.assertEqual(attachment.sap_absolute_entry, 789)
        self.assertEqual(attachment.original_filename, "invoice.pdf")
        self.assertIsNone(attachment.sap_error_message)

        # Verify SAP calls
        mock_instance.upload_attachment.assert_called_once()
        mock_instance.link_attachment_to_grpo.assert_called_once_with(
            doc_entry=12345, absolute_entry=789
        )

        # Clean up
        attachment.file.delete(save=False)

    @patch('grpo.services.SAPClient')
    def test_upload_attachment_sap_failure(self, mock_sap_client):
        """Test attachment upload when SAP fails - file should be saved locally"""
        from sap_client.exceptions import SAPConnectionError

        mock_instance = MagicMock()
        mock_instance.upload_attachment.side_effect = SAPConnectionError("SAP unavailable")
        mock_sap_client.return_value = mock_instance

        grpo = self._create_posted_grpo()
        service = GRPOService(company_code="TC001")
        test_file = SimpleUploadedFile("invoice.pdf", b"pdf_content")

        attachment = service.upload_grpo_attachment(
            grpo_posting_id=grpo.id,
            file=test_file,
            user=self.user
        )

        # File should be saved locally even though SAP failed
        self.assertEqual(attachment.sap_attachment_status, SAPAttachmentStatus.FAILED)
        self.assertIsNotNone(attachment.sap_error_message)
        self.assertIn("SAP unavailable", attachment.sap_error_message)
        self.assertTrue(attachment.file)

        # Clean up
        attachment.file.delete(save=False)

    def test_upload_attachment_non_posted_grpo(self):
        """Test that attachments cannot be added to non-POSTED GRPOs"""
        grpo = self._create_posted_grpo()
        grpo.status = GRPOStatus.PENDING
        grpo.save()

        service = GRPOService(company_code="TC001")
        test_file = SimpleUploadedFile("invoice.pdf", b"content")

        with self.assertRaises(ValueError) as context:
            service.upload_grpo_attachment(
                grpo_posting_id=grpo.id,
                file=test_file,
                user=self.user
            )
        self.assertIn("Only POSTED", str(context.exception))

    def test_upload_attachment_no_sap_doc_entry(self):
        """Test that attachments need SAP DocEntry"""
        grpo = self._create_posted_grpo()
        grpo.sap_doc_entry = None
        grpo.save()

        service = GRPOService(company_code="TC001")
        test_file = SimpleUploadedFile("invoice.pdf", b"content")

        with self.assertRaises(ValueError) as context:
            service.upload_grpo_attachment(
                grpo_posting_id=grpo.id,
                file=test_file,
                user=self.user
            )
        self.assertIn("no SAP DocEntry", str(context.exception))

    @patch('grpo.services.SAPClient')
    def test_retry_attachment_upload_success(self, mock_sap_client):
        """Test retrying a failed attachment upload"""
        mock_instance = MagicMock()
        mock_instance.upload_attachment.return_value = {"AbsoluteEntry": 999}
        mock_instance.link_attachment_to_grpo.return_value = {
            "DocEntry": 12345, "AttachmentEntry": 999
        }
        mock_sap_client.return_value = mock_instance

        grpo = self._create_posted_grpo()
        test_file = SimpleUploadedFile("invoice.pdf", b"content")
        attachment = GRPOAttachment.objects.create(
            grpo_posting=grpo, file=test_file,
            original_filename="invoice.pdf",
            sap_attachment_status=SAPAttachmentStatus.FAILED,
            sap_error_message="Previous error"
        )

        service = GRPOService(company_code="TC001")
        result = service.retry_attachment_upload(attachment_id=attachment.id)

        self.assertEqual(result.sap_attachment_status, SAPAttachmentStatus.LINKED)
        self.assertEqual(result.sap_absolute_entry, 999)
        self.assertIsNone(result.sap_error_message)

        # Clean up
        result.file.delete(save=False)

    @patch('grpo.services.SAPClient')
    def test_retry_skips_upload_if_already_uploaded(self, mock_sap_client):
        """Test retry skips upload when sap_absolute_entry already set"""
        mock_instance = MagicMock()
        mock_instance.link_attachment_to_grpo.return_value = {
            "DocEntry": 12345, "AttachmentEntry": 555
        }
        mock_sap_client.return_value = mock_instance

        grpo = self._create_posted_grpo()
        test_file = SimpleUploadedFile("invoice.pdf", b"content")
        attachment = GRPOAttachment.objects.create(
            grpo_posting=grpo, file=test_file,
            original_filename="invoice.pdf",
            sap_attachment_status=SAPAttachmentStatus.FAILED,
            sap_absolute_entry=555,  # Already uploaded
            sap_error_message="Link failed"
        )

        service = GRPOService(company_code="TC001")
        result = service.retry_attachment_upload(attachment_id=attachment.id)

        # Upload should NOT be called since absolute_entry exists
        mock_instance.upload_attachment.assert_not_called()
        mock_instance.link_attachment_to_grpo.assert_called_once_with(
            doc_entry=12345, absolute_entry=555
        )
        self.assertEqual(result.sap_attachment_status, SAPAttachmentStatus.LINKED)

        # Clean up
        result.file.delete(save=False)

    def test_retry_already_linked(self):
        """Test that already linked attachments cannot be retried"""
        grpo = self._create_posted_grpo()
        test_file = SimpleUploadedFile("invoice.pdf", b"content")
        attachment = GRPOAttachment.objects.create(
            grpo_posting=grpo, file=test_file,
            original_filename="invoice.pdf",
            sap_attachment_status=SAPAttachmentStatus.LINKED,
            sap_absolute_entry=789
        )

        service = GRPOService(company_code="TC001")
        with self.assertRaises(ValueError) as context:
            service.retry_attachment_upload(attachment_id=attachment.id)
        self.assertIn("already", str(context.exception))

        # Clean up
        attachment.file.delete(save=False)


class GRPOAttachmentAPITests(APITestCase):
    """Tests for GRPO attachment API endpoints"""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Test Company", code="TC001")
        cls.user = User.objects.create_user(
            email="testuser@example.com", password="testpass123",
            full_name="Test User", employee_code="EMP001"
        )
        cls.vehicle_type = VehicleType.objects.create(name="TRUCK")
        cls.vehicle = Vehicle.objects.create(
            vehicle_number="MH12AB1234", vehicle_type=cls.vehicle_type
        )
        cls.driver = Driver.objects.create(
            name="Test Driver", mobile_no="9876543210", license_no="DL123456"
        )
        cls.vehicle_entry = VehicleEntry.objects.create(
            entry_no="VE-2024-001", company=cls.company,
            vehicle=cls.vehicle, driver=cls.driver,
            entry_type="RAW_MATERIAL", status=GateEntryStatus.COMPLETED
        )
        cls.po_receipt = POReceipt.objects.create(
            vehicle_entry=cls.vehicle_entry, po_number="PO-001",
            supplier_code="SUP001", supplier_name="Test Supplier",
            sap_doc_entry=12345
        )
        cls.grpo_posting = GRPOPosting.objects.create(
            vehicle_entry=cls.vehicle_entry, po_receipt=cls.po_receipt,
            status=GRPOStatus.POSTED, sap_doc_entry=12345, sap_doc_num=456
        )

    def setUp(self):
        self.client = APIClient()

    def test_attachment_list_unauthenticated(self):
        """Test unauthenticated access to attachment list"""
        url = f"/api/v1/grpo/{self.grpo_posting.id}/attachments/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_attachment_upload_unauthenticated(self):
        """Test unauthenticated upload is rejected"""
        url = f"/api/v1/grpo/{self.grpo_posting.id}/attachments/"
        test_file = SimpleUploadedFile("invoice.pdf", b"content")
        response = self.client.post(url, {"file": test_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_attachment_delete_unauthenticated(self):
        """Test unauthenticated delete is rejected"""
        url = f"/api/v1/grpo/{self.grpo_posting.id}/attachments/1/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_attachment_retry_unauthenticated(self):
        """Test unauthenticated retry is rejected"""
        url = f"/api/v1/grpo/{self.grpo_posting.id}/attachments/1/retry/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class GRPOPostingSerializerWithAttachmentsTest(TestCase):
    """Test that GRPOPostingSerializer includes attachments"""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Test Company", code="TC001")
        cls.user = User.objects.create_user(
            email="testuser@example.com", password="testpass123",
            full_name="Test User", employee_code="EMP001"
        )
        cls.vehicle_type = VehicleType.objects.create(name="TRUCK")
        cls.vehicle = Vehicle.objects.create(
            vehicle_number="MH12AB1234", vehicle_type=cls.vehicle_type
        )
        cls.driver = Driver.objects.create(
            name="Test Driver", mobile_no="9876543210", license_no="DL123456"
        )
        cls.vehicle_entry = VehicleEntry.objects.create(
            entry_no="VE-2024-001", company=cls.company,
            vehicle=cls.vehicle, driver=cls.driver,
            entry_type="RAW_MATERIAL", status=GateEntryStatus.COMPLETED
        )
        cls.po_receipt = POReceipt.objects.create(
            vehicle_entry=cls.vehicle_entry, po_number="PO-001",
            supplier_code="SUP001", supplier_name="Test Supplier",
            sap_doc_entry=12345
        )

    def test_posting_serializer_includes_attachments(self):
        """Test that GRPOPostingSerializer includes attachments field"""
        from grpo.serializers import GRPOPostingSerializer

        grpo = GRPOPosting.objects.create(
            vehicle_entry=self.vehicle_entry, po_receipt=self.po_receipt,
            status=GRPOStatus.POSTED, sap_doc_entry=12345, sap_doc_num=456
        )

        # Create an attachment
        test_file = SimpleUploadedFile("invoice.pdf", b"content")
        GRPOAttachment.objects.create(
            grpo_posting=grpo, file=test_file,
            original_filename="invoice.pdf",
            sap_attachment_status=SAPAttachmentStatus.LINKED,
            sap_absolute_entry=789
        )

        serializer = GRPOPostingSerializer(grpo)
        data = serializer.data

        self.assertIn("attachments", data)
        self.assertEqual(len(data["attachments"]), 1)
        self.assertEqual(data["attachments"][0]["original_filename"], "invoice.pdf")
        self.assertEqual(data["attachments"][0]["sap_attachment_status"], "LINKED")
        self.assertEqual(data["attachments"][0]["sap_absolute_entry"], 789)

        # Clean up
        grpo.attachments.first().file.delete(save=False)
