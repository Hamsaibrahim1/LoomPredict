import streamlit as st
import pandas as pd
import numpy as np
import re

st.set_page_config(page_title='LoomPredict', page_icon='🧦', layout='wide')
st.title('🧦 LoomPredict')
st.caption('توقع تغيير موديلات الماكينات ومراجعة قراءات العدادات')

# ---------- Helpers ----------
def norm(x):
    s = str(x).strip().lower()
    s = s.replace('أ','ا').replace('إ','ا').replace('آ','ا').replace('ى','ي').replace('ة','ه')
    return re.sub(r'[^a-z0-9\u0600-\u06ff]', '', s)

def find_header_row(raw, required_terms, scan=50):
    best_i, best_score = 0, -1
    for i in range(min(scan, len(raw))):
        vals = [norm(v) for v in raw.iloc[i].tolist() if pd.notna(v)]
        score = sum(any(norm(term) in v for v in vals) for term in required_terms)
        if score > best_score:
            best_i, best_score = i, score
    return best_i, best_score

def read_workbook(upload, production=False):
    if upload is None:
        return None
    try:
        upload.seek(0)
        raw = pd.read_excel(upload, header=None)
        terms = ['رقم الماكينة', 'عدد الابر', 'كود الموديل', 'الكمية المتبقية'] if production else ['رقم الماكينة', 'ترتيب الموديل', 'موديل']
        header_i, score = find_header_row(raw, terms)
        if score < (2 if production else 2):
            raise ValueError('لم أتمكن من تحديد صف العناوين تلقائيًا. راجعي أن أسماء الأعمدة موجودة في الملف.')
        headers = []
        for j, value in enumerate(raw.iloc[header_i].tolist()):
            name = str(value).strip() if pd.notna(value) else f'عمود_{j+1}'
            if name.lower() == 'nan' or not name:
                name = f'عمود_{j+1}'
            headers.append(name)
        df = raw.iloc[header_i+1:].copy()
        df.columns = headers
        df = df.dropna(how='all').reset_index(drop=True)
        seen, newcols = {}, []
        for c in df.columns:
            seen[c] = seen.get(c, 0) + 1
            newcols.append(c if seen[c] == 1 else f'{c}_{seen[c]}')
        df.columns = newcols
        return df
    except Exception as e:
        st.error(f'تعذر قراءة الملف {upload.name}: {e}')
        return None

def find_col(df, hints):
    for h in hints:
        nh = norm(h)
        for c in df.columns:
            if nh and nh == norm(c):
                return c
    for h in hints:
        nh = norm(h)
        for c in df.columns:
            if nh and nh in norm(c):
                return c
    return None

def choose_col(df, label, hints, key):
    guess = find_col(df, hints)
    opts = ['— اختاري —'] + list(df.columns)
    idx = opts.index(guess) if guess in opts else 0
    return st.selectbox(label, opts, index=idx, key=key)

def machine_key(x):
    if pd.isna(x):
        return ''
    s = str(x).strip()
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
    except Exception:
        pass
    return s

def numeric_machine_sort(value):
    try:
        return (0, float(value))
    except Exception:
        return (1, str(value))

def as_num(value):
    return pd.to_numeric(pd.Series([value]).astype(str).str.replace(',', '', regex=False), errors='coerce').iloc[0]

def is_date_header(value):
    s = str(value).strip()
    return bool(re.search(r'\d', s) and (re.search(r'[-/]', s) or 'انتاج' in norm(s)))

def normalize_value(value):
    if pd.isna(value):
        return ''
    return norm(value)

# ---------- Sidebar ----------
with st.sidebar:
    st.header('الملفات')
    prod_file = st.file_uploader('ملف متابعة الإنتاج', type=['xlsx', 'xls'])
    plan_file = st.file_uploader('ملف خطة تحميل الماكينات', type=['xlsx', 'xls'])
    st.divider()
    forecast_days = st.number_input('اعرض الماكينات المتوقع تغييرها خلال كام يوم؟', min_value=1, max_value=30, value=3)

prod = read_workbook(prod_file, production=True)
plan = read_workbook(plan_file, production=False)

if prod is not None:
    with st.expander('معاينة متابعة الإنتاج'):
        st.dataframe(prod.head(6), use_container_width=True)
if plan is not None:
    with st.expander('معاينة خطة تحميل الماكينات'):
        st.dataframe(plan.head(6), use_container_width=True)

if prod is not None and plan is not None:
    st.subheader('تحديد الأعمدة')
    st.caption('مش مطلوب إدخال إنتاج يومي يدويًا. الحساب يعتمد على الكمية المتبقية بالدستة ومعدلات الإنتاج المرجعية.')
    a,b,c = st.columns(3)
    with a: p_machine = choose_col(prod, 'رقم الماكينة في المتابعة', ['رقم الماكينة', 'رقم الماكينه', 'machine no'], 'pm')
    with b: p_need = choose_col(prod, 'الكمية المتبقية بالدستة', ['الكمية المتبقية دستة', 'الكمية المتبقية بالدستة'], 'pn')
    with c: p_needle = choose_col(prod, 'عدد الإبر', ['عدد الابر', 'عدد الإبر', 'needle'], 'pneedle')
    d,e,f = st.columns(3)
    with d: p_model = choose_col(prod, 'الموديل الحالي / كود الموديل', ['كود الموديل', 'موديل المصنع', 'الموديل'], 'pmodel')
    with e: p_order = choose_col(prod, 'رقم الطلبية في المتابعة', ['رقم الطلبية', 'طلبية', 'order'], 'porder')
    with f: p_size = choose_col(prod, 'المقاس', ['المقاس', 'size'], 'psize')
    g,h = st.columns(2)
    with g: p_color = choose_col(prod, 'كود اللون', ['كود اللون', 'color'], 'pcolor')
    with h: p_type = choose_col(prod, 'نوع الماكينة (اختياري)', ['نوع الماكينة', 'نوع الماكينه'], 'ptype')

    st.subheader('أعمدة خطة تحميل الماكينات')
    a,b,c = st.columns(3)
    with a: q_machine = choose_col(plan, 'رقم الماكينة في الخطة', ['رقم الماكينة', 'رقم الماكينه', 'machine'], 'qm')
    with b: q_model = choose_col(plan, 'عمود موديل في الخطة', ['موديل'], 'qmodel')
    with c: q_rank = choose_col(plan, 'ترتيب الموديل', ['ترتيب الموديل', 'ترتيب'], 'qrank')
    d,e,f = st.columns(3)
    with d: q_order = choose_col(plan, 'رقم الطلبية في الخطة', ['طلبية', 'رقم الطلبية', 'order'], 'qo')
    with e: q_size = choose_col(plan, 'المقاس في الخطة', ['مقاس', 'المقاس', 'size'], 'qsize')
    with f: q_color = choose_col(plan, 'كود اللون في الخطة', ['كود اللون', 'color'], 'qcolor')

    required = [p_machine,p_need,p_needle,p_model,p_order,p_size,p_color,q_machine,q_model,q_rank]
    if any(x == '— اختاري —' for x in required):
        st.warning('اختاري الأعمدة المطلوبة عشان الحساب يكون صحيح.')
        st.stop()

    # Production reference rates: dozen per day.
    rates = {
        (108, ''): 38, (120, ''): 30, (132, ''): 31,
        (156, 'ساده'): 25, (156, 'فوطه'): 23.5,
        (168, 'فوطه'): 25, (168, 'ساده'): 26, (200, ''): 18
    }

    # Index the machine plan and its sequence.
    plan_work = plan.copy()
    plan_work['_machine'] = plan_work[q_machine].map(machine_key)
    plan_work['_rank'] = pd.to_numeric(plan_work[q_rank], errors='coerce')
    plan_work['_model_key'] = plan_work[q_model].map(normalize_value)
    plan_work = plan_work[plan_work['_machine'] != '']

    change_rows = []
    counter_rows = []
    no_rate_rows = []

    for _, row in prod.iterrows():
        machine = machine_key(row[p_machine])
        if not machine:
            continue
        remaining_dozen = as_num(row[p_need])
        needle_val = as_num(row[p_needle])
        needle = int(needle_val) if pd.notna(needle_val) else 0
        current_model = row[p_model]
        current_model_key = normalize_value(current_model)
        order_key = normalize_value(row[p_order])
        size_key = normalize_value(row[p_size])
        color_key = normalize_value(row[p_color])
        machine_type = str(row[p_type]) if p_type != '— اختاري —' and pd.notna(row[p_type]) else ''
        type_key = 'فوطه' if 'فوطه' in norm(machine_type) else ('ساده' if 'ساده' in norm(machine_type) else '')
        rate = rates.get((needle, type_key), rates.get((needle, '')))

        if pd.isna(remaining_dozen) or remaining_dozen < 0:
            days_left = np.nan
        elif remaining_dozen == 0:
            days_left = 0.0
        elif rate and rate > 0:
            days_left = float(remaining_dozen) / float(rate)
        else:
            days_left = np.nan
            no_rate_rows.append({'الماكينة': machine, 'الموديل': str(current_model), 'عدد الإبر': needle, 'نوع الماكينة': machine_type, 'المتبقي دستة': remaining_dozen})

        machine_plan = plan_work[plan_work['_machine'] == machine].copy()
        model_matches = machine_plan[machine_plan['_model_key'] == current_model_key].copy()
        # Narrow a model match with order/size/color when these fields exist in the plan.
        if not model_matches.empty:
            for plan_col, value_key in [(q_order, order_key), (q_size, size_key), (q_color, color_key)]:
                if plan_col in model_matches.columns and value_key:
                    narrowed = model_matches[model_matches[plan_col].map(normalize_value) == value_key]
                    if not narrowed.empty:
                        model_matches = narrowed
            model_matches = model_matches.sort_values('_rank', na_position='last')
            current_rank = model_matches['_rank'].iloc[0]
            later = machine_plan[machine_plan['_rank'] > current_rank].sort_values('_rank', na_position='last')
            if not later.empty:
                next_row = later.iloc[0]
                next_model = str(next_row[q_model])
                next_order = str(next_row[q_order]) if q_order in plan.columns else ''
                next_rank = next_row['_rank']
                plan_status = 'تم تحديد الموديل التالي من ترتيب الكارت'
            else:
                next_model, next_order, next_rank = '', '', np.nan
                plan_status = 'الموديل الحالي آخر ترتيب في كارت الماكينة'
        else:
            # Never falsely claim there is no next model when matching failed.
            next_model, next_order, next_rank = '', '', np.nan
            plan_status = 'لم تتم مطابقة الموديل الحالي مع عمود موديل في كارت الماكينة؛ راجعي الكود/الطلبية'

        # Only list machines expected to finish within the selected horizon.
        if pd.notna(days_left) and 0 <= days_left <= forecast_days:
            change_rows.append({
                'رقم الماكينة': machine,
                'الموديل الحالي': str(current_model),
                'الطلبية الحالية': str(row[p_order]),
                'المتبقي دستة': float(remaining_dozen),
                'معدل الإنتاج المرجعي دستة/يوم': rate,
                'أيام متوقعة للتغيير': round(days_left, 2),
                'الموديل التالي حسب الكارت': next_model if next_model else 'مراجعة الكارت',
                'طلبية الموديل التالي': next_order,
                'حالة مطابقة الكارت': plan_status
            })

    # Sort changes by machine number as requested (not by date/remaining quantity).
    changes = pd.DataFrame(change_rows)
    st.subheader(f'الماكينات المتوقع تغييرها خلال {forecast_days} أيام')
    if not changes.empty:
        changes['_sort'] = changes['رقم الماكينة'].map(numeric_machine_sort)
        changes = changes.sort_values('_sort').drop(columns='_sort').reset_index(drop=True)
        st.dataframe(changes, use_container_width=True, hide_index=True)
        st.download_button('تحميل جدول الماكينات المتوقع تغييرها CSV', changes.to_csv(index=False, encoding='utf-8-sig'), file_name='LoomPredict_changes.csv', mime='text/csv')
    else:
        st.success(f'لا توجد ماكينات متوقع تغييرها خلال {forecast_days} أيام وفق الكمية المتبقية ومعدلات الإنتاج المرجعية.')

    # Counter anomaly detection from the historical daily production columns.
    daily_cols = [col for col in prod.columns if is_date_header(col)]
    for machine, group in prod.groupby(prod[p_machine].map(machine_key), dropna=True):
        vals = []
        for col in daily_cols:
            vals.extend([v for v in pd.to_numeric(group[col], errors='coerce').dropna().tolist() if v > 0])
        if len(vals) < 3:
            continue
        med = float(np.median(vals))
        high = float(np.max(vals))
        low = float(np.min(vals))
        reasons = []
        if med > 0 and high > med * 2.5:
            reasons.append('فيه قراءة إنتاج أعلى من وسيط إنتاج الماكينة بأكثر من 2.5 مرة')
        if med > 0 and low < med * 0.2:
            reasons.append('فيه قراءة منخفضة جدًا مقارنة بباقي إنتاج الماكينة؛ قد تكون توقف أو قراءة عداد')
        if high >= 100000:
            reasons.append('فيه رقم كبير جدًا؛ راجعي احتمال خطأ إدخال أو قراءة عداد')
        if reasons:
            counter_rows.append({'رقم الماكينة': machine_key(machine), 'أسباب المراجعة': '؛ '.join(reasons), 'أعلى قراءة تاريخية': high, 'أقل قراءة تاريخية': low, 'وسيط الإنتاج التاريخي': round(med, 1), 'عدد القراءات المستخدمة': len(vals)})

    st.subheader('ماكينات قراءاتها محتاجة مراجعة')
    if counter_rows:
        counter_df = pd.DataFrame(counter_rows)
        counter_df['_sort'] = counter_df['رقم الماكينة'].map(numeric_machine_sort)
        counter_df = counter_df.sort_values('_sort').drop(columns='_sort').reset_index(drop=True)
        st.warning('دي قراءات غير معتادة وتحتاج مراجعة سجل الإنتاج والعداد؛ مش معناها إن العداد تالف بشكل مؤكد.')
        st.dataframe(counter_df, use_container_width=True, hide_index=True)
        st.download_button('تحميل تقرير مراجعة العدادات CSV', counter_df.to_csv(index=False, encoding='utf-8-sig'), file_name='LoomPredict_counter_review.csv', mime='text/csv')
    else:
        st.info('لم تظهر قراءات تاريخية شاذة بوضوح وفق قواعد الفحص الحالية. الماكينات التي لا تحتوي على 3 قراءات تاريخية على الأقل لا يمكن الحكم عليها.')

    if no_rate_rows:
        with st.expander('ماكينات لم يتوفر لها معدل إنتاج مرجعي'):
            st.dataframe(pd.DataFrame(no_rate_rows), use_container_width=True, hide_index=True)

else:
    st.info('ارفعي ملف متابعة الإنتاج وملف خطة تحميل الماكينات لبدء التوقعات.')

st.caption('الحساب يعتمد على الكمية المتبقية بالدستة ÷ معدل الإنتاج المرجعي بالدستة/يوم. التوقع تقديري، ويجب مراجعة ترتيب الكارت وتطابق الموديل قبل قرار التغيير.')
