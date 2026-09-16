import tkinter as tk
from tkinter import ttk, messagebox
from core.db import get_all_customers, add_customer, update_customer, delete_customer, get_connection, get_generic_customer_id

class CustomersView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f1f5f9")
        self.controller = controller

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self.customers_list = []
        self.generic_customer_id = None

        self._build_header()
        self._build_search_bar()
        self._build_table_section()

        self.refresh_data()

    def _build_header(self):
        header_frame = tk.Frame(self, bg="#f1f5f9")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))

        tk.Label(header_frame, text="👥 دليل العملاء ونظام الولاء", font=("Helvetica", 22, "bold"), fg="#0f172a", bg="#f1f5f9").pack(side="right")

        btn_add = tk.Button(header_frame, text="+ إضافة عميل جديد", font=("Helvetica", 11, "bold"), bg="#2563eb", fg="white",
                            padx=15, pady=6, bd=0, cursor="hand2", command=self._show_add_customer_modal)
        btn_add.pack(side="left")

    def _build_search_bar(self):
        search_frame = tk.Frame(self, bg="white", padx=15, pady=10, bd=1, relief="solid")
        search_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)

        tk.Label(search_frame, text="بحث عن عميل:", font=("Helvetica", 11, "bold"), bg="white", fg="#0f172a").pack(side="right", padx=5)
        self.ent_search = tk.Entry(search_frame, font=("Helvetica", 12), width=35, justify="right")
        self.ent_search.pack(side="right", padx=5)
        self.ent_search.bind("<KeyRelease>", self._filter_customers)

        btn_reset = tk.Button(search_frame, text="🔄 إعادة ضبط", font=("Helvetica", 10, "bold"), bg="#f1f5f9", fg="#0f172a",
                              padx=12, pady=4, bd=0, cursor="hand2", command=self.refresh_data)
        btn_reset.pack(side="left", padx=5)

    def _build_table_section(self):
        table_frame = tk.Frame(self, bg="white", padx=15, pady=15)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        cols = ("points", "email", "phone", "name", "id")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=18)
        self.tree.heading("id", text="الرقم")
        self.tree.heading("name", text="اسم العميل")
        self.tree.heading("phone", text="رقم الهاتف")
        self.tree.heading("email", text="البريد الإلكتروني")
        self.tree.heading("points", text="نقاط الولاء")

        self.tree.column("id", width=60, anchor="center")
        self.tree.column("name", width=250, anchor="e")
        self.tree.column("phone", width=150, anchor="center")
        self.tree.column("email", width=250, anchor="e")
        self.tree.column("points", width=120, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.tree.bind("<Double-1>", lambda e: self._view_customer_sales_history())

        bot_bar = tk.Frame(table_frame, bg="white")
        bot_bar.grid(row=1, column=0, sticky="ew", pady=(15, 0))

        btn_hist = tk.Button(bot_bar, text="📜 عرض سجل مشتريات العميل", font=("Helvetica", 11, "bold"), bg="#e2e8f0", fg="#0f172a",
                             padx=15, pady=6, bd=0, cursor="hand2", command=self._view_customer_sales_history)
        btn_hist.pack(side="right", padx=5)

        btn_edit = tk.Button(bot_bar, text="✏️ تعديل المحدد", font=("Helvetica", 11, "bold"), bg="#f1f5f9", fg="#0f172a",
                             padx=15, pady=6, bd=0, cursor="hand2", command=self._show_edit_customer_modal)
        btn_edit.pack(side="right", padx=5)

        btn_del = tk.Button(bot_bar, text="🗑️ حذف المحدد", font=("Helvetica", 11, "bold"), bg="#fee2e2", fg="#dc2626",
                            padx=15, pady=6, bd=0, cursor="hand2", command=self._delete_selected_customer)
        btn_del.pack(side="left", padx=5)

    def refresh_data(self):
        self.ent_search.delete(0, "end")
        self.customers_list = get_all_customers()
        self.generic_customer_id = get_generic_customer_id()
        self._populate_tree(self.customers_list)

    def _populate_tree(self, customers):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for c in customers:
            self.tree.insert("", "end", values=(c['loyalty_points'], c['email'] or "N/A", c['phone'] or "N/A", c['name'], c['id']))

    def _filter_customers(self, event=None):
        query = self.ent_search.get().lower()
        if not query:
            self._populate_tree(self.customers_list)
            return

        filtered = [c for c in self.customers_list if query in c['name'].lower() or (c['phone'] and query in c['phone'].lower()) or (c['email'] and query in c['email'].lower())]
        self._populate_tree(filtered)

    def _show_add_customer_modal(self):
        self._show_customer_form_modal()

    def _show_edit_customer_modal(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("تحديد عميل", "يرجى تحديد عميل من الجدول لتعديل بياناته.")
            return

        values = self.tree.item(selected[0], "values")
        cust_id = int(values[4])
        if self.generic_customer_id and cust_id == self.generic_customer_id:
            messagebox.showwarning("عميل افتراضي", "لا يمكن تعديل بيانات العميل الافتراضي العام.")
            return

        cust_obj = next((c for c in self.customers_list if c['id'] == cust_id), None)
        if cust_obj:
            self._show_customer_form_modal(cust_obj)

    def _show_customer_form_modal(self, cust_obj=None):
        modal = tk.Toplevel(self)
        mode = "تعديل بيانات العميل" if cust_obj else "إضافة عميل جديد"
        modal.title(mode)
        modal.geometry("420x400")
        modal.config(bg="white", padx=25, pady=25)
        modal.grab_set()

        modal.columnconfigure(0, weight=1)

        tk.Label(modal, text=mode, font=("Helvetica", 18, "bold"), bg="white", fg="#0f172a").pack(pady=(0, 20))

        form = tk.Frame(modal, bg="white")
        form.pack(fill="both", expand=True)
        form.columnconfigure(0, weight=1)

        fields = [
            ("الاسم الكامل *", "name"),
            ("رقم الهاتف *", "phone"),
            ("البريد الإلكتروني", "email"),
            ("نقاط الولاء", "loyalty_points")
        ]

        entries = {}
        for i, (lbl, fname) in enumerate(fields):
            tk.Label(form, text=lbl, font=("Helvetica", 11, "bold"), bg="white", fg="#334155").grid(row=i, column=1, sticky="e", pady=10, padx=10)
            ent = tk.Entry(form, font=("Helvetica", 12), width=22, justify="right")
            if cust_obj:
                ent.insert(0, str(cust_obj[fname] or ""))
            elif fname == "loyalty_points":
                ent.insert(0, "0")

            ent.grid(row=i, column=0, pady=10, padx=5)
            entries[fname] = ent

        def save_cust():
            name = entries['name'].get().strip()
            phone = entries['phone'].get().strip()
            email = entries['email'].get().strip()
            try:
                points = int(entries['loyalty_points'].get() or 0)
            except ValueError:
                messagebox.showerror("إدخال غير صحيح", "نقاط الولاء يجب أن تكون رقماً صحيحاً.")
                return

            if not name or not phone:
                messagebox.showwarning("بيانات مطلوبة", "يرجى إدخال اسم العميل ورقم الهاتف.")
                return

            if cust_obj:
                s, m = update_customer(cust_obj['id'], name, phone, email, points)
            else:
                s, m = add_customer(name, phone, email)

            if s:
                messagebox.showinfo("نجاح", "تم حفظ بيانات العميل بنجاح!")
                self.refresh_data()
                modal.destroy()
            else:
                messagebox.showerror("خطأ", m)

        btn_save = tk.Button(modal, text="💾 حفظ بيانات العميل", font=("Helvetica", 13, "bold"), bg="#2563eb", fg="white",
                             pady=10, bd=0, cursor="hand2", command=save_cust)
        btn_save.pack(fill="x", pady=(20, 0))

    def _delete_selected_customer(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("تحديد عميل", "يرجى تحديد عميل من الجدول لحذفه.")
            return

        values = self.tree.item(selected[0], "values")
        cust_id = int(values[4])
        name = values[3]

        if self.generic_customer_id and cust_id == self.generic_customer_id:
            messagebox.showwarning("لا يمكن الحذف", "لا يمكن حذف العميل الافتراضي العام.")
            return

        if messagebox.askyesno("تأكيد الحذف", f"هل أنت متأكد من رغبتك في حذف العميل '{name}'؟"):
            s, m = delete_customer(cust_id)
            if s:
                messagebox.showinfo("تم الحذف", m)
                self.refresh_data()
            else:
                messagebox.showerror("خطأ", m)

    def _view_customer_sales_history(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("تحديد عميل", "يرجى تحديد عميل من الجدول لعرض سجل مشترياته.")
            return

        values = self.tree.item(selected[0], "values")
        cust_id = int(values[4])
        name = values[3]

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sales WHERE customer_id = ? ORDER BY sale_date DESC", (cust_id,))
        sales = cursor.fetchall()
        conn.close()

        modal = tk.Toplevel(self)
        modal.title(f"سجل المشتريات - {name}")
        modal.geometry("650x480")
        modal.config(bg="white", padx=20, pady=20)
        modal.grab_set()

        tk.Label(modal, text=f"سجل مشتريات العميل: {name}", font=("Helvetica", 18, "bold"), bg="white", fg="#0f172a").pack(pady=(0, 5))
        tk.Label(modal, text=f"إجمالي العمليات والفواتير: {len(sales)}", font=("Helvetica", 11), bg="white", fg="#64748b").pack(pady=(0, 15))

        cols = ("pay", "tot", "date", "id")
        s_tree = ttk.Treeview(modal, columns=cols, show="headings", height=12)
        s_tree.heading("id", text="رقم الفاتورة")
        s_tree.heading("date", text="التاريخ والوقت")
        s_tree.heading("tot", text="الإجمالي المدفوع")
        s_tree.heading("pay", text="طريقة الدفع")

        s_tree.column("id", width=90, anchor="center")
        s_tree.column("date", width=200, anchor="center")
        s_tree.column("tot", width=120, anchor="center")
        s_tree.column("pay", width=150, anchor="center")

        scroll = ttk.Scrollbar(modal, orient="vertical", command=s_tree.yview)
        s_tree.configure(yscrollcommand=scroll.set)

        f_tree = tk.Frame(modal, bg="white")
        f_tree.pack(fill="both", expand=True)
        s_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        for s in sales:
            s_tree.insert("", "end", values=(s['payment_method'], f"{s['total_amount']:,.2f}", s['sale_date'], s['id']))

        btn_close = tk.Button(modal, text="إغلاق", font=("Helvetica", 12, "bold"), bg="#e2e8f0", fg="#0f172a",
                              padx=30, pady=8, bd=0, cursor="hand2", command=modal.destroy)
        btn_close.pack(pady=(15, 0))
