import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from api.deps import get_db_path, require_manager
from core.db import get_combined_report_rows, get_financial_overview, get_sales_chart_data, get_top_selling_products_data

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview")
def overview(user=Depends(require_manager)):
    return get_financial_overview(db_path=get_db_path())


@router.get("/charts")
def charts(user=Depends(require_manager)):
    days, revenues = get_sales_chart_data(db_path=get_db_path())
    names, quantities = get_top_selling_products_data(db_path=get_db_path())
    return {
        "daily_sales": {"labels": days, "values": revenues},
        "top_products": {"labels": names, "values": quantities},
    }


@router.get("/export.csv")
def export_csv(user=Depends(require_manager)):
    rows = get_combined_report_rows(db_path=get_db_path())
    headers = [
        "نوع العملية",
        "رقم المستند",
        "رقم الفاتورة الأصلية",
        "رقم الجلسة",
        "التاريخ",
        "العميل/الوصف",
        "المبلغ",
        "طريقة الدفع/الاسترجاع",
        "الفئة/السبب",
        "ملاحظات",
    ]
    labels = {"Sale": "بيع", "Return": "استرجاع", "Expense": "مصروف"}
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(
            [
                labels.get(row["transaction_type"], row["transaction_type"]),
                row["document_id"],
                row["original_sale_id"] or "",
                row["session_id"] or "",
                row["transaction_date"],
                row["subject_name"],
                f"{row['amount']:.2f}",
                row["payment_method"],
                row["category"] or "",
                row["notes"] or "",
            ]
        )
    filename = f"report_{datetime.now().strftime('%Y%m%d')}.csv"
    payload = buffer.getvalue().encode("utf-8-sig")
    return Response(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
