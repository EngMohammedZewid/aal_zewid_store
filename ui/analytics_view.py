import csv
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from core.db import (
    calculate_session_summary,
    get_combined_report_rows,
    get_financial_overview,
    get_pos_sessions,
    get_sales_chart_data,
    get_top_selling_products_data,
)


class AnalyticsView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f1f5f9")
        self.controller = controller

        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        self.metric_labels = {}

        self._build_header()
        self._build_financial_summary()
        self._build_note()
        self._build_charts_section()

        self.refresh_data()

    def _build_header(self):
        header_frame = tk.Frame(self, bg="#f1f5f9")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))

        tk.Label(header_frame, text="📈 التحليلات المالية وتقارير المبيعات", font=("Helvetica", 22, "bold"), fg="#0f172a", bg="#f1f5f9").pack(side="right")

        actions = tk.Frame(header_frame, bg="#f1f5f9")
        actions.pack(side="left")
        tk.Button(actions, text="سجل الجلسات", font=("Helvetica", 11, "bold"), bg="#e2e8f0", fg="#0f172a", padx=15, pady=6, bd=0, cursor="hand2", command=self._show_session_history_modal).pack(side="left", padx=5)
        tk.Button(actions, text="📥 تصدير التقرير التنفيذي (CSV)", font=("Helvetica", 11, "bold"), bg="#16a34a", fg="white", padx=15, pady=6, bd=0, cursor="hand2", command=self._export_sales_csv).pack(side="left")

    def _build_financial_summary(self):
        self.summary_frame = tk.Frame(self, bg="#f1f5f9")
        self.summary_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        self.summary_frame.columnconfigure((0, 1, 2, 3), weight=1)

        cards = [
            ("إجمالي المبيعات", "gross_sales", "#2563eb"),
            ("إجمالي المرتجعات", "returns_total", "#dc2626"),
            ("صافي المبيعات", "net_sales", "#16a34a"),
            ("إجمالي تكلفة البضاعة", "gross_cogs", "#475569"),
            ("تكلفة البضاعة المرتجعة", "returned_cogs", "#d97706"),
            ("صافي تكلفة البضاعة", "net_cogs", "#0f172a"),
            ("الربح بعد المرتجعات", "gross_profit_after_returns", "#16a34a"),
            ("النتيجة التشغيلية", "operating_result", "#2563eb"),
        ]

        for index, (title, key, color) in enumerate(cards):
            row = index // 4
            column = 3 - (index % 4)
            card = tk.Frame(self.summary_frame, bg="white", padx=20, pady=15)
            card.grid(row=row, column=column, sticky="nsew", padx=6, pady=6)
            tk.Label(card, text=title, font=("Helvetica", 11, "bold"), fg="#64748b", bg="white").pack(anchor="e")
            label = tk.Label(card, text="0.00", font=("Helvetica", 22, "bold"), fg=color, bg="white")
            label.pack(anchor="e", pady=(5, 0))
            self.metric_labels[key] = label

        margin_card = tk.Frame(self.summary_frame, bg="white", padx=20, pady=15)
        margin_card.grid(row=2, column=3, sticky="nsew", padx=6, pady=6)
        tk.Label(margin_card, text="هامش الربح بعد المرتجعات", font=("Helvetica", 11, "bold"), fg="#64748b", bg="white").pack(anchor="e")
        self.metric_labels["profit_margin"] = tk.Label(margin_card, text="0.0%", font=("Helvetica", 22, "bold"), fg="#d97706", bg="white")
        self.metric_labels["profit_margin"].pack(anchor="e", pady=(5, 0))

        expenses_card = tk.Frame(self.summary_frame, bg="white", padx=20, pady=15)
        expenses_card.grid(row=2, column=2, sticky="nsew", padx=6, pady=6)
        tk.Label(expenses_card, text="إجمالي المصروفات", font=("Helvetica", 11, "bold"), fg="#64748b", bg="white").pack(anchor="e")
        self.metric_labels["expenses_total"] = tk.Label(expenses_card, text="0.00", font=("Helvetica", 22, "bold"), fg="#dc2626", bg="white")
        self.metric_labels["expenses_total"].pack(anchor="e", pady=(5, 0))

    def _build_note(self):
        note = tk.Frame(self, bg="#fff7ed", padx=15, pady=10, bd=1, relief="solid")
        note.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))
        tk.Label(note, text="ملاحظة محاسبية: تكلفة البضاعة المرتجعة تستخدم نفس منطق التطبيق الحالي وتعتمد على سعر تكلفة المنتج الحالي، وليس تكلفة تاريخية مخزنة وقت البيع.", font=("Helvetica", 10), bg="#fff7ed", fg="#9a3412", justify="right", anchor="e").pack(fill="x")

    def _build_charts_section(self):
        self.charts_frame = tk.Frame(self, bg="#f1f5f9")
        self.charts_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=(10, 20))
        self.charts_frame.columnconfigure((0, 1), weight=1)
        self.charts_frame.rowconfigure(0, weight=1)

        self.left_chart_container = tk.Frame(self.charts_frame, bg="white", padx=10, pady=10)
        self.left_chart_container.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.right_chart_container = tk.Frame(self.charts_frame, bg="white", padx=10, pady=10)
        self.right_chart_container.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

    def refresh_data(self):
        self._update_financial_summary()
        self._render_daily_sales_chart()
        self._render_top_selling_chart()

    def _update_financial_summary(self):
        overview = get_financial_overview()
        for key, value in overview.items():
            if key == "profit_margin":
                self.metric_labels[key].config(text=f"{value:,.1f}%")
            elif key in self.metric_labels:
                self.metric_labels[key].config(text=f"{value:,.2f}")

    def _render_daily_sales_chart(self):
        for widget in self.left_chart_container.winfo_children():
            widget.destroy()

        days, revenues = get_sales_chart_data()
        fig = Figure(figsize=(6, 4), dpi=100)
        ax = fig.add_subplot(111)

        bars = ax.bar(days, revenues, color="#3b82f6", edgecolor="#2563eb", width=0.5)
        ax.set_title("صافي المبيعات لآخر 7 أيام", fontsize=14, fontweight="bold", pad=15, color="#0f172a")
        ax.set_ylabel("صافي المبيعات", fontsize=11, color="#475569")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#cbd5e1")
        ax.spines["bottom"].set_color("#cbd5e1")
        ax.tick_params(colors="#475569", labelsize=10)
        fig.tight_layout()

        for bar in bars:
            value = bar.get_height()
            if value != 0:
                ax.text(bar.get_x() + bar.get_width() / 2.0, value, f"{value:,.0f}", ha="center", va="bottom", fontsize=9, color="#0f172a", fontweight="bold")

        canvas = FigureCanvasTkAgg(fig, master=self.left_chart_container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _render_top_selling_chart(self):
        for widget in self.right_chart_container.winfo_children():
            widget.destroy()

        names, quantities = get_top_selling_products_data(limit=5)
        fig = Figure(figsize=(6, 4), dpi=100)
        ax = fig.add_subplot(111)

        if not names:
            ax.text(0.5, 0.5, "لا توجد بيانات مبيعات صافية متوفرة حتى الآن.", ha="center", va="center", fontsize=12, color="#64748b")
            ax.axis("off")
        else:
            y_positions = range(len(names))
            bars = ax.barh(y_positions, quantities, color="#10b981", height=0.5)
            ax.set_yticks(list(y_positions))
            ax.set_yticklabels(names, fontsize=11, color="#0f172a")
            ax.invert_yaxis()
            ax.set_title("أكثر 5 منتجات مبيعاً بعد الاسترجاعات", fontsize=14, fontweight="bold", pad=15, color="#0f172a")
            ax.set_xlabel("صافي الوحدات المباعة", fontsize=11, color="#475569")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_color("#cbd5e1")
            ax.spines["bottom"].set_color("#cbd5e1")
            ax.tick_params(colors="#475569", labelsize=10)
            for bar in bars:
                value = bar.get_width()
                ax.text(value + 0.5, bar.get_y() + bar.get_height() / 2.0, f"{value:,}", ha="left", va="center", fontsize=9, color="#0f172a", fontweight="bold")

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.right_chart_container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _export_sales_csv(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile=f"تقرير_المعاملات_{datetime.now().strftime('%Y%m%d')}.csv",
            title="حفظ التقرير التنفيذي للمبيعات والجلسات",
        )
        if not filename:
            return

        try:
            rows = get_combined_report_rows()
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
            with open(filename, mode="w", newline="", encoding="utf-8-sig") as file_obj:
                writer = csv.writer(file_obj)
                writer.writerow(headers)
                for row in rows:
                    writer.writerow([
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
                    ])
            messagebox.showinfo("نجاح التصدير", f"تم حفظ التقرير التنفيذي بنجاح في:\n{filename}")
        except Exception as exc:
            messagebox.showerror("خطأ في التصدير", f"حدث خطأ أثناء كتابة ملف CSV:\n{str(exc)}")

    def _show_session_history_modal(self):
        modal = tk.Toplevel(self)
        modal.title("سجل جلسات الكاشير")
        modal.geometry("860x520")
        modal.config(bg="white", padx=20, pady=20)
        modal.grab_set()

        tk.Label(modal, text="سجل جلسات الكاشير", font=("Helvetica", 18, "bold"), bg="white", fg="#0f172a").pack(pady=(0, 15))

        frame = tk.Frame(modal, bg="white")
        frame.pack(fill="both", expand=True)
        columns = ("status", "difference", "actual", "expected", "opening", "closed", "opened", "id")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=14)
        tree.heading("id", text="الجلسة")
        tree.heading("opened", text="وقت الفتح")
        tree.heading("closed", text="وقت الإغلاق")
        tree.heading("opening", text="الرصيد الافتتاحي")
        tree.heading("expected", text="الرصيد المتوقع")
        tree.heading("actual", text="الرصيد الفعلي")
        tree.heading("difference", text="الفرق")
        tree.heading("status", text="الحالة")

        tree.column("id", width=70, anchor="center")
        tree.column("opened", width=160, anchor="center")
        tree.column("closed", width=160, anchor="center")
        tree.column("opening", width=110, anchor="center")
        tree.column("expected", width=110, anchor="center")
        tree.column("actual", width=110, anchor="center")
        tree.column("difference", width=90, anchor="center")
        tree.column("status", width=90, anchor="center")

        tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

        for session in get_pos_sessions(limit=100):
            summary = calculate_session_summary(session["id"])
            tree.insert(
                "",
                "end",
                iid=str(session["id"]),
                values=(
                    "مغلقة" if session["status"] == "CLOSED" else "مفتوحة",
                    f"{(summary['difference'] or 0.0):,.2f}" if summary else "—",
                    f"{summary['actual_closing_balance']:,.2f}" if summary and summary["actual_closing_balance"] is not None else "—",
                    f"{summary['expected_cash_balance']:,.2f}" if summary else "—",
                    f"{session['opening_balance']:,.2f}",
                    session["closed_at"] or "—",
                    session["opened_at"],
                    session["id"],
                ),
            )

        def open_selected_report(event=None):
            selected = tree.selection()
            if not selected:
                return
            self._show_session_summary_report(int(selected[0]))

        tree.bind("<Double-1>", open_selected_report)
        tk.Button(modal, text="عرض التقرير", font=("Helvetica", 11, "bold"), bg="#2563eb", fg="white", padx=12, pady=6, bd=0, cursor="hand2", command=open_selected_report).pack(side="right", pady=(15, 0))
        tk.Button(modal, text="إغلاق", font=("Helvetica", 11, "bold"), bg="#e2e8f0", fg="#0f172a", padx=12, pady=6, bd=0, cursor="hand2", command=modal.destroy).pack(side="left", pady=(15, 0))

    def _show_session_summary_report(self, session_id):
        summary = calculate_session_summary(session_id)
        if not summary:
            messagebox.showerror("الجلسات", "تعذر تحميل تقرير الجلسة")
            return

        difference = summary["difference"] or 0.0
        if difference > 0:
            status_text = "زيادة"
            status_color = "#d97706"
        elif difference < 0:
            status_text = "عجز"
            status_color = "#dc2626"
        else:
            status_text = "متوازن"
            status_color = "#16a34a"

        modal = tk.Toplevel(self)
        modal.title(f"تقرير جلسة الكاشير #{session_id}")
        modal.geometry("700x620")
        modal.config(bg="white", padx=20, pady=20)
        modal.grab_set()

        tk.Label(modal, text=f"تقرير جلسة الكاشير #{session_id}", font=("Helvetica", 18, "bold"), bg="white", fg="#0f172a").pack(pady=(0, 15))

        content = tk.Frame(modal, bg="white")
        content.pack(fill="both", expand=True)
        sections = [
            ("معلومات الجلسة", [
                f"وقت الفتح: {summary['opened_at']}",
                f"وقت الإغلاق: {summary['closed_at'] or '—'}",
                f"الرصيد الافتتاحي: {summary['opening_balance']:,.2f}",
                f"ملاحظات الافتتاح: {summary['opening_notes'] or '—'}",
                f"ملاحظات الإغلاق: {summary['closing_notes'] or '—'}",
            ]),
            ("المبيعات", [
                f"عدد فواتير البيع: {summary['sales_count']}",
                f"إجمالي المبيعات: {summary['total_sales']:,.2f}",
                f"المبيعات النقدية: {summary['cash_sales']:,.2f}",
                f"مبيعات البطاقات: {summary['card_sales']:,.2f}",
                f"المدفوعات الإلكترونية: {summary['electronic_sales']:,.2f}",
            ]),
            ("المرتجعات", [
                f"عدد فواتير الاسترجاع: {summary['returns_count']}",
                f"إجمالي المرتجعات: {summary['total_returns']:,.2f}",
                f"المرتجعات النقدية: {summary['cash_returns']:,.2f}",
                f"مرتجعات غير نقدية: {summary['total_returns'] - summary['cash_returns']:,.2f}",
            ]),
            ("المصروفات", [
                f"عدد المصروفات: {summary['expenses_count']}",
                f"إجمالي المصروفات: {summary['total_expenses']:,.2f}",
                f"المصروفات النقدية: {summary['cash_expenses']:,.2f}",
                f"المصروفات غير النقدية: {summary['non_cash_expenses']:,.2f}",
            ] + [f"{category}: {amount:,.2f}" for category, amount in summary['expenses_by_category'].items()]),
            ("مطابقة النقدية", [
                f"الرصيد المتوقع: {summary['expected_cash_balance']:,.2f}",
                f"الرصيد الفعلي: {(summary['actual_closing_balance'] if summary['actual_closing_balance'] is not None else 0.0):,.2f}",
                f"الفرق: {difference:,.2f}",
            ]),
        ]

        for title, lines in sections:
            card = tk.Frame(content, bg="#f8fafc", padx=15, pady=12, bd=1, relief="solid")
            card.pack(fill="x", pady=6)
            tk.Label(card, text=title, font=("Helvetica", 13, "bold"), bg="#f8fafc", fg="#0f172a").pack(anchor="e", pady=(0, 6))
            for line in lines:
                tk.Label(card, text=line, font=("Helvetica", 11), bg="#f8fafc", fg="#334155", anchor="e", justify="right").pack(fill="x", pady=2)

        tk.Label(modal, text=f"حالة الفرق: {status_text}", font=("Helvetica", 16, "bold"), bg="white", fg=status_color).pack(pady=(15, 10))
        tk.Button(modal, text="إغلاق", font=("Helvetica", 11, "bold"), bg="#e2e8f0", fg="#0f172a", padx=12, pady=6, bd=0, cursor="hand2", command=modal.destroy).pack()
