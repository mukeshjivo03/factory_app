from django.urls import path
from .views import (
    # BOM Request
    BOMRequestCreateAPI, BOMRequestListAPI, BOMRequestDetailAPI,
    BOMRequestApproveAPI, BOMRequestRejectAPI,
    # Material Issue
    MaterialIssueAPI,
    # Stock Check
    StockCheckAPI,
    # Finished Goods Receipt
    FGReceiptCreateAPI, FGReceiptListAPI, FGReceiptDetailAPI,
    FGReceiptReceiveAPI, FGReceiptPostToSAPAPI,
)

urlpatterns = [
    # ------------------------------------------------------------------
    # BOM Requests
    # ------------------------------------------------------------------
    path('bom-requests/', BOMRequestListAPI.as_view(), name='wh-bom-request-list'),
    path('bom-requests/create/', BOMRequestCreateAPI.as_view(), name='wh-bom-request-create'),
    path('bom-requests/<int:request_id>/', BOMRequestDetailAPI.as_view(), name='wh-bom-request-detail'),
    path('bom-requests/<int:request_id>/approve/', BOMRequestApproveAPI.as_view(), name='wh-bom-request-approve'),
    path('bom-requests/<int:request_id>/reject/', BOMRequestRejectAPI.as_view(), name='wh-bom-request-reject'),

    # ------------------------------------------------------------------
    # Material Issue (to SAP)
    # ------------------------------------------------------------------
    path('bom-requests/<int:request_id>/issue/', MaterialIssueAPI.as_view(), name='wh-material-issue'),

    # ------------------------------------------------------------------
    # Stock Check
    # ------------------------------------------------------------------
    path('stock/check/', StockCheckAPI.as_view(), name='wh-stock-check'),

    # ------------------------------------------------------------------
    # Finished Goods Receipt
    # ------------------------------------------------------------------
    path('fg-receipts/', FGReceiptListAPI.as_view(), name='wh-fg-receipt-list'),
    path('fg-receipts/create/', FGReceiptCreateAPI.as_view(), name='wh-fg-receipt-create'),
    path('fg-receipts/<int:receipt_id>/', FGReceiptDetailAPI.as_view(), name='wh-fg-receipt-detail'),
    path('fg-receipts/<int:receipt_id>/receive/', FGReceiptReceiveAPI.as_view(), name='wh-fg-receipt-receive'),
    path('fg-receipts/<int:receipt_id>/post-to-sap/', FGReceiptPostToSAPAPI.as_view(), name='wh-fg-receipt-post-sap'),
]
