export const PAYMENT_METHODS = ["كاش (نقدي)", "بطاقة ائتمان", "دفع إلكتروني (مدى/فوري)", "شبكة (مدى)"];
export const EXPENSE_CATEGORIES = ["نقل وشحن", "أدوات نظافة", "صيانة", "كهرباء ومياه", "ضيافة", "مصروف عامل", "مشتريات عاجلة", "مصروفات أخرى"];
export const EXPENSE_PAYMENT_METHODS = ["كاش", "بطاقة", "تحويل", "دفع إلكتروني"];
export const RETURN_REFUND_METHODS = ["كاش", "بطاقة ائتمان", "دفع إلكتروني", "نفس طريقة الدفع الأصلية"];
export const RETURN_REASONS = ["منتج تالف", "منتج غير مناسب", "خطأ في الفاتورة", "استبدال منتج", "طلب العميل", "أخرى"];

export const UNIT_OPTIONS = [
  { value: "Piece", label: "قطعة" },
  { value: "Pack", label: "باكو" },
  { value: "Dozen", label: "دستة" },
  { value: "Box", label: "علبة" },
  { value: "Carton", label: "كرتونة" },
];

const UNIT_LABELS: Record<string, string> = Object.fromEntries(UNIT_OPTIONS.map((unit) => [unit.value, unit.label]));

export function unitLabel(name?: string | null) {
  if (!name) return "قطعة";
  return UNIT_LABELS[name] || name;
}

export function money(value: number | null | undefined) {
  return Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function roundMoney(value: number) {
  return Number(value.toFixed(2));
}

export function taxOf(subtotal: number) {
  return roundMoney(subtotal * 0.08);
}
