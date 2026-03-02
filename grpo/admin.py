from django.contrib import admin
from .models import GRPOPosting, GRPOLinePosting, GRPOAttachment


class GRPOLinePostingInline(admin.TabularInline):
    model = GRPOLinePosting
    extra = 0
    readonly_fields = ["po_item_receipt", "quantity_posted", "base_entry", "base_line"]
    can_delete = False


class GRPOAttachmentInline(admin.TabularInline):
    model = GRPOAttachment
    extra = 0
    readonly_fields = [
        "file", "original_filename", "sap_attachment_status",
        "sap_absolute_entry", "sap_error_message",
        "uploaded_at", "uploaded_by"
    ]
    can_delete = True


@admin.register(GRPOPosting)
class GRPOPostingAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "get_entry_no",
        "get_po_number",
        "status",
        "sap_doc_num",
        "sap_doc_total",
        "posted_at",
        "posted_by"
    ]
    list_filter = ["status", "posted_at"]
    search_fields = [
        "vehicle_entry__entry_no",
        "po_receipt__po_number",
        "sap_doc_num"
    ]
    readonly_fields = [
        "vehicle_entry",
        "po_receipt",
        "sap_doc_entry",
        "sap_doc_num",
        "sap_doc_total",
        "status",
        "error_message",
        "posted_at",
        "posted_by",
        "created_at",
        "updated_at"
    ]
    inlines = [GRPOLinePostingInline, GRPOAttachmentInline]

    def get_entry_no(self, obj):
        return obj.vehicle_entry.entry_no
    get_entry_no.short_description = "Entry No"

    def get_po_number(self, obj):
        return obj.po_receipt.po_number
    get_po_number.short_description = "PO Number"
