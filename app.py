import re
import io
import math
import unicodedata
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="LoomPredict", page_icon="🧦", layout="wide")
st.title("🧦 LoomPredict")
st.caption("متابعة الإنتاج والتنبؤ التقديري بموعد تغيير موديل الماكينة")

# ---------- Helpers ----------
def clean_text(value):
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def norm(value):
    text = clean_text(value).lower()
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")
    return re.sub(r"[^a-z0-9\u0600-\u06ff]", "", text)


def unique_headers(columns):
    """Make Excel headers non-empty and unique so column access is reliable."""
    seen = {}
    result = []
    for i, col in enumerate(columns):
        name = clean_text(col) or f"عمود بدون اسم {i + 1}"
        count = seen.get(name, 0)
        seen[name] = count + 1
        if count:
            name = f"{name} ({count + 1})"
        result.append(name)
    return result


def read_excel(upload, label):
    if upload is None:
        return None
    try:
        data = pd.read_excel(upload, header=0)
        data.columns = unique_headers(data.columns)
        # Drop fully empty rows and columns only; keep all real data as-is.
        data = data.dropna(axis=0, how="all").dropna(axis=1, how="all")
        if data.empty:
            st.error(f"ملف {label} لا يحتوي على بيانات ظاهرة. تأكدي أن صف العناوين هو أول صف.")
            return None
        return data
    except Exception as exc:
        st.error(f"تعذرت قراءة ملف {label}: {exc}")
        return None


def find_col(df, hints):
    cols = list(df.columns)
    normalized = [(c, norm(c)) for c in cols]
    # Prefer exact match, then contains match.
    for hint in hints:
        nh = norm(hint)
        for col, nc in normalized:
            if nh and nc == nh:
                return col
    for hint in hints:
        nh = norm(hint)
        for col, nc in normalized:
            if nh and (nh in nc or nc in nh):
                return col
    return None


def choose_col(df, label, hints, key):
    guess = find_col(df, hints)
    options = ["— اختاري العمود —"] + list(df.columns)
    # Use a unique widget key; stale selections from another uploaded file caused the old crash.
    default_index = options.index(guess) if guess in options else 0
    chosen = st.selectbox(label, options, index=default_index, key=key)
    return None if chosen == options[0] else chosen


def as_number(value):
    if pd.isna(value):
        return np.nan
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def machine_key(value):
    value = clean_text(value)
    # Keep numeric machine IDs consistent (e.g. 12 and 12.0).
    number = as_number(value)
    if pd.notna(number) and number.is_integer():
        return str(int(number))
    return value


def get_rate(needle, machine_type, machine):
    typ = norm(machine_type)
    rates = {
        (108, ""): 38,
        (120, ""): 30,
        (132, ""): 31,
        (156, "ساده"): 25,
        (156, "فوطة"): 23.5,
        (168, "فوطة"): 25,
        (168, "ساده"): 26,
        (200, ""): 18,
    }
    if needle == 120 and machine == "98":
        return 35
    if needle == 156:
        if "فوط" in typ:
            return 23.5
        if "ساد" in typ:
            return 25
    if needle == 168:
        if "فوط" in typ:
            return 25
        if "ساد" in typ:
            return 26
    return rates.get((needle, ""))


def safe_text(value):
    text = clean_text(value)
    return text if text else "—"


# ---------- Sidebar / uploads ----------
with st.sidebar:
    st.header("الملفات")
    prod_file = st.file_uploader("ملف متابعة الإنتاج", type=["xlsx", "xls"], key="production_upload")
    plan_file = st.file_uploader("ملف خطة تحميل الماكينات", type=["xlsx", "xls"], key="plan_upload")
    st.divider()
    forecast_days = st.number_input("اعرض الماكينات المتوقع انتهاؤها خلال كام يوم؟", min_value=1, max_value=30, value=3, step=1)

prod = read_excel(prod_file, "متابعة الإنتاج")
plan = read_excel(plan_file, "خطة تحميل الماكينات")

if prod is None or plan is None:
    st.info("ارفعي الملفين من القائمة الجانبية لبدء التحليل.")
    st.stop()

# Show headers clearly so the user can see what the app actually read.
with st.expander("معاينة ملف متابعة الإنتاج", expanded=False):
    st.write("الأعمدة التي قرأها التطبيق:")
    st.write(list(prod.columns))
    st.dataframe(prod.head(6), use_container_width=True)
with st.expander("معاينة خطة تحميل الماكينات", expanded=False):
    st.write("الأعمدة التي قرأها التطبيق:")
    st.write(list(plan.columns))
    st.dataframe(plan.head(6), use_container_width=True)

st.subheader("1) تأكيد أعمدة متابعة الإنتاج")
p1, p2, p3 = st.columns(3)
with p1:
    p_machine = choose_col(prod, "رقم الماكينة", ["رقم الماكينة", "رقم الماكينه", "الماكينة", "الماكينه", "machine no", "machine"], "prod_machine_col_v2")
with p2:
    p_need = choose_col(prod, "الكمية المتبقية بالفردة", ["الكمية المتبقية فردة", "الكمية المتبقية فرده", "المتبقية فردة", "المتبقي فردة", "remaining"], "prod_remaining_col_v2")
with p3:
    p_needle = choose_col(prod, "عدد الإبر", ["عدد الابر", "عدد الإبر", "needle"], "prod_needle_col_v2")
p4, p5, p6 = st.columns(3)
with p4:
    p_model = choose_col(prod, "كود/موديل المصنع الحالي", ["رقم موديل المصنع", "كود الموديل", "موديل المصنع", "الموديل"], "prod_model_col_v2")
with p5:
    p_size = choose_col(prod, "المقاس", ["المقاس", "مقاس", "size"], "prod_size_col_v2")
with p6:
    p_color = choose_col(prod, "كود اللون أو اللون", ["كود اللون", "اللون", "color"], "prod_color_col_v2")
p_type = find_col(prod, ["نوع الماكينة", "نوع الماكينه", "إمكانية التشغيل"])
p_order = find_col(prod, ["رقم الطلبية", "طلبية", "order"])

st.subheader("2) تأكيد أعمدة خطة تحميل الماكينات")
q1, q2, q3 = st.columns(3)
with q1:
    q_machine = choose_col(plan, "رقم الماكينة في الخطة", ["رقم الماكينة", "رقم الماكينه", "الماكينة", "الماكينه", "machine"], "plan_machine_col_v2")
with q2:
    q_order = choose_col(plan, "رقم الطلبية", ["طلبية", "رقم الطلبية", "order"], "plan_order_col_v2")
with q3:
    q_model = choose_col(plan, "الموديل في الخطة", ["موديل", "رقم موديل المصنع", "كود الموديل"], "plan_model_col_v2")
q4, q5, q6 = st.columns(3)
with q4:
    q_size = choose_col(plan, "المقاس في الخطة", ["مقاس", "المقاس", "size"], "plan_size_col_v2")
with q5:
    q_color = choose_col(plan, "كود اللون في الخطة", ["كود اللون", "لون", "color"], "plan_color_col_v2")
with q6:
    q_qty = choose_col(plan, "الكمية المطلوبة فردة في الخطة", ["الكمية المطلوبة فردة", "الكمية المطلوبة فرده", "مطلوبة فردة"], "plan_qty_col_v2")
q_rank = choose_col(plan, "ترتيب الموديل في الخطة", ["ترتيب الموديل", "ترتيب", "sequence", "rank"], "plan_rank_col_v2")

required = {
    "رقم الماكينة في المتابعة": p_machine,
    "الكمية المتبقية بالفردة": p_need,
    "عدد الإبر": p_needle,
    "الموديل الحالي": p_model,
    "المقاس في المتابعة": p_size,
    "اللون في المتابعة": p_color,
    "رقم الماكينة في الخطة": q_machine,
    "رقم الطلبية في الخطة": q_order,
    "الموديل في الخطة": q_model,
    "المقاس في الخطة": q_size,
    "كود اللون في الخطة": q_color,
    "الكمية المطلوبة في الخطة": q_qty,
    "ترتيب الموديل في الخطة": q_rank,
}
missing = [name for name, value in required.items() if value is None]
if missing:
    st.warning("اختاري الأعمدة الناقصة أولًا: " + "، ".join(missing))
    st.stop()

# Verify the selected column names are still in the current dataframes.
# This explicitly prevents the KeyError that occurred in the previous version.
for selected, frame, label in [
    (p_machine, prod, "رقم الماكينة في المتابعة"),
    (p_need, prod, "المتبقي"),
    (p_needle, prod, "الإبر"),
    (p_model, prod, "الموديل"),
    (p_size, prod, "المقاس"),
    (p_color, prod, "اللون"),
    (q_machine, plan, "رقم الماكينة في الخطة"),
    (q_order, plan, "الطلبية"),
    (q_model, plan, "موديل الخطة"),
    (q_size, plan, "مقاس الخطة"),
    (q_color, plan, "لون الخطة"),
    (q_qty, plan, "كمية الخطة"),
    (q_rank, plan, "الترتيب"),
]:
    if selected not in frame.columns:
        st.error(f"العمود المختار لـ {label} لم يعد موجودًا. اختاريه مرة أخرى من القائمة.")
        st.stop()

# Normalize matching fields in copies; never overwrite source data.
prod_work = prod.copy()
plan_work = plan.copy()
prod_work["__machine_key"] = prod_work[p_machine].map(machine_key)
plan_work["__machine_key"] = plan_work[q_machine].map(machine_key)
prod_work["__model_key"] = prod_work[p_model].map(norm)
plan_work["__model_key"] = plan_work[q_model].map(norm)
prod_work["__size_key"] = prod_work[p_size].map(norm)
plan_work["__size_key"] = plan_work[q_size].map(norm)
prod_work["__color_key"] = prod_work[p_color].map(norm)
plan_work["__color_key"] = plan_work[q_color].map(norm)
if p_order:
    prod_work["__order_key"] = prod_work[p_order].map(norm)
else:
    prod_work["__order_key"] = ""
plan_work["__order_key"] = plan_work[q_order].map(norm)

machines = sorted([m for m in prod_work["__machine_key"].dropna().unique() if m], key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x))
st.subheader("3) إدخال إنتاج اليوم")
st.write("أدخلي إجمالي إنتاج اليوم لكل ماكينة بالفردة (القطعة)، وليس لكل وردية.")
daily = {}
cols = st.columns(4)
for i, machine in enumerate(machines):
    with cols[i % 4]:
        daily[machine] = st.number_input(f"ماكينة {machine} – إنتاج اليوم بالفردة", min_value=0, step=1, value=0, key=f"daily_prod_{machine}")

st.divider()
if st.button("احسبي التوقعات", type="primary", use_container_width=True):
    results = []
    alerts = []
    for _, row in prod_work.iterrows():
        machine = row["__machine_key"]
        if not machine:
            continue
        remaining = as_number(row[p_need])
        needle_num = as_number(row[p_needle])
        needle = int(needle_num) if pd.notna(needle_num) else 0
        model = safe_text(row[p_model])
        size = safe_text(row[p_size])
        color = safe_text(row[p_color])
        order = safe_text(row[p_order]) if p_order else "—"
        machine_type = safe_text(row[p_type]) if p_type else ""
        reference_rate = get_rate(needle, machine_type, machine)
        actual_pieces = daily.get(machine, 0)
        actual_dozen = actual_pieces / 24 if actual_pieces > 0 else None
        effective_rate = actual_dozen if actual_dozen and actual_dozen > 0 else reference_rate

        if pd.notna(remaining) and remaining <= 0:
            days_left = 0.0
        elif pd.notna(remaining) and effective_rate and effective_rate > 0:
            days_left = remaining / 24 / effective_rate
        else:
            days_left = np.nan

        # Find the current row in the same machine's card using machine + model + size + color + order.
        machine_plan = plan_work[plan_work["__machine_key"] == machine].copy()
        match = machine_plan[
            (machine_plan["__model_key"] == row["__model_key"])
            & (machine_plan["__size_key"] == row["__size_key"])
            & (machine_plan["__color_key"] == row["__color_key"])
        ]
        if order != "—" and "__order_key" in match.columns:
            exact = match[match["__order_key"] == row["__order_key"]]
            if not exact.empty:
                match = exact

        next_model = "لا يوجد موديل تالٍ"
        next_order = "—"
        next_size = "—"
        next_color = "—"
        next_qty = np.nan
        warning = ""
        if match.empty:
            warning = "لم يتم العثور على الموديل الحالي بنفس الماكينة والمقاس واللون والطلبية في الخطة؛ راجعي المطابقة"
        else:
            ranks = pd.to_numeric(machine_plan[q_rank], errors="coerce")
            current_rank_values = pd.to_numeric(match[q_rank], errors="coerce").dropna()
            if current_rank_values.empty:
                warning = "ترتيب الموديل الحالي غير رقمي أو فارغ في الخطة"
            else:
                current_rank = current_rank_values.min()
                machine_plan["__rank_num"] = ranks
                later = machine_plan[machine_plan["__rank_num"] > current_rank].copy()
                later = later.sort_values("__rank_num", kind="stable")
                if not later.empty:
                    nxt = later.iloc[0]
                    next_model = safe_text(nxt[q_model])
                    next_order = safe_text(nxt[q_order])
                    next_size = safe_text(nxt[q_size])
                    next_color = safe_text(nxt[q_color])
                    next_qty = as_number(nxt[q_qty])
                    if pd.isna(next_qty) or next_qty <= 0:
                        warning = "كمية الموديل التالي غير واضحة أو صفر؛ راجعي الكمية قبل التغيير"

        if pd.notna(days_left) and days_left <= forecast_days:
            alerts.append(f"ماكينة {machine}: متوقع انتهاء الكمية خلال {days_left:.1f} يوم")
        if warning:
            alerts.append(f"ماكينة {machine}: {warning}")
        if reference_rate and actual_pieces > 0:
            if actual_dozen > reference_rate * 1.3 or actual_dozen < reference_rate * 0.5:
                alerts.append(f"ماكينة {machine}: إنتاج اليوم {actual_pieces:,.0f} فردة؛ راجعي قراءة العداد والتشغيل مقارنة بالمرجع {reference_rate:g} دستة/يوم")

        results.append({
            "الماكينة": machine,
            "الطلبية الحالية": order,
            "الموديل الحالي": model,
            "المقاس الحالي": size,
            "اللون الحالي": color,
            "عدد الإبر": needle,
            "المتبقي فردة": remaining,
            "إنتاج اليوم فردة": actual_pieces,
            "المرجع دستة/يوم": reference_rate,
            "أيام متوقعة للانتهاء": round(days_left, 1) if pd.notna(days_left) else None,
            "الطلبية التالية": next_order,
            "الموديل التالي": next_model,
            "مقاس التالي": next_size,
            "لون التالي": next_color,
            "كمية التالي فردة": next_qty,
            "التنبيه": warning,
        })

    if not results:
        st.error("لم أجد صفوفًا بها أرقام ماكينات في ملف المتابعة. راجعي عمود رقم الماكينة.")
        st.stop()
    output = pd.DataFrame(results)
    output["أيام متوقعة للانتهاء"] = pd.to_numeric(output["أيام متوقعة للانتهاء"], errors="coerce")
    output = output.sort_values("أيام متوقعة للانتهاء", na_position="last")

    st.subheader("النتائج والتنبؤ")
    due = output[output["أيام متوقعة للانتهاء"].notna() & (output["أيام متوقعة للانتهاء"] <= forecast_days)]
    k1, k2, k3 = st.columns(3)
    k1.metric("عدد صفوف التشغيل", len(output))
    k2.metric(f"متوقع تنتهي خلال {forecast_days} أيام", len(due))
    k3.metric("عدد التنبيهات", len(alerts))
    st.dataframe(output, use_container_width=True, hide_index=True)

    if alerts:
        st.subheader("التنبيهات")
        for alert in alerts:
            st.warning(alert)
    else:
        st.success("لا توجد تنبيهات وفق البيانات المدخلة.")

    csv_data = output.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("تحميل تقرير التوقعات CSV", data=csv_data, file_name="LoomPredict_report.csv", mime="text/csv")

st.caption("التوقع تقديري. يعتمد على الكمية المتبقية ومعدل الإنتاج اليومي المدخل، أو المعدل المرجعي عند عدم إدخال إنتاج اليوم. لا يُعد موعد تغيير مؤكدًا. راجعي مطابقة الماكينة والموديل والمقاس واللون والطلبية وترتيب الكارت قبل اتخاذ قرار التشغيل.")
