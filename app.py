import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

st.set_page_config(page_title='LoomPredict', page_icon='🧦', layout='wide')
st.title('🧦 LoomPredict')
st.caption('متابعة إنتاج الماكينات، توقع تغيير الموديل، ومراجعة قراءات العدادات')

# ---------- Helpers ----------
def norm(x):
    s = str(x).strip().lower()
    s = s.replace('أ','ا').replace('إ','ا').replace('آ','ا').replace('ى','ي').replace('ة','ه')
    return re.sub(r'[^a-z0-9\u0600-\u06ff]', '', s)

def find_header_row(raw, required_terms, scan=40):
    best_i, best_score = 0, -1
    for i in range(min(scan, len(raw))):
        vals = [norm(v) for v in raw.iloc[i].tolist() if pd.notna(v)]
        joined = ' '.join(vals)
        score = sum(1 for term in required_terms if norm(term) in joined)
        if score > best_score:
            best_i, best_score = i, score
    return best_i, best_score

def read_workbook(upload, production=False):
    if upload is None:
        return None
    try:
        raw = pd.read_excel(upload, header=None)
        terms = ['رقم الماكينة', 'عدد الابر', 'كود الموديل'] if production else ['رقم الماكينة', 'ترتيب الموديل', 'طلبية']
        header_i, score = find_header_row(raw, terms)
        if score < 2:
            # fallback to ordinary first-row header
            return pd.read_excel(upload)
        headers = []
        for j, value in enumerate(raw.iloc[header_i].tolist()):
            name = str(value).strip() if pd.notna(value) else f'عمود_{j+1}'
            if name.lower() == 'nan' or name == '':
                name = f'عمود_{j+1}'
            headers.append(name)
        df = raw.iloc[header_i+1:].copy()
        df.columns = headers
        df = df.dropna(how='all').reset_index(drop=True)
        # remove duplicate column labels safely
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
    cols = list(df.columns)
    for h in hints:
        nh = norm(h)
        for c in cols:
            if nh and nh in norm(c):
                return c
    return None

def choose_col(df, label, hints, key):
    guess = find_col(df, hints)
    opts = ['— اختاري —'] + list(df.columns)
    idx = opts.index(guess) if guess in opts else 0
    return st.selectbox(label, opts, index=idx, key=key)

def num(s):
    return pd.to_numeric(s.astype(str).str.replace(',', '', regex=False), errors='coerce')

def machine_key(x):
    if pd.isna(x): return ''
    s = str(x).strip()
    try:
        f = float(s)
        if f.is_integer(): return str(int(f))
    except Exception:
        pass
    return s

def is_date_header(x):
    s = str(x).strip()
    if re.search(r'\d', s) and (re.search(r'[-/]', s) or 'انتاج' in norm(s) or 'الانتاج' in norm(s)):
        return True
    return False

# ---------- Sidebar ----------
with st.sidebar:
    st.header('الملفات')
    prod_file = st.file_uploader('ملف متابعة الإنتاج', type=['xlsx','xls'])
    plan_file = st.file_uploader('ملف خطة تحميل الماكينات', type=['xlsx','xls'])
    st.divider()
    forecast_days = st.number_input('تنبيه قبل انتهاء الكمية (أيام)', min_value=1, max_value=30, value=3)

prod = read_workbook(prod_file, production=True)
plan = read_workbook(plan_file, production=False)

if prod is not None:
    st.success('تمت قراءة ملف متابعة الإنتاج مع تجاوز صفوف الدمج السابقة للعناوين.')
    with st.expander('معاينة ملف متابعة الإنتاج'):
        st.dataframe(prod.head(8), use_container_width=True)
if plan is not None:
    with st.expander('معاينة خطة تحميل الماكينات'):
        st.dataframe(plan.head(8), use_container_width=True)

if prod is not None and plan is not None:
    st.subheader('تحديد الأعمدة')
    st.caption('راجعي الاختيارات؛ الكمية المتبقية يمكن أن تكون بالدستة أو بالفردة.')
    p1,p2,p3 = st.columns(3)
    with p1: p_machine = choose_col(prod,'رقم الماكينة في المتابعة',['رقم الماكينة','رقم الماكينه','machine no'], 'pm')
    with p2: p_need = choose_col(prod,'الكمية المتبقية',['الكمية المتبقية دستة','الكمية المتبقية فردة','remaining'], 'pn')
    with p3: p_unit = st.selectbox('وحدة الكمية المتبقية',['دستة','فردة'], key='punit')
    p4,p5,p6 = st.columns(3)
    with p4: p_needle = choose_col(prod,'عدد الإبر',['عدد الابر','عدد الإبر','needle'], 'pneedle')
    with p5: p_model = choose_col(prod,'الموديل الحالي',['كود الموديل','موديل المصنع','الموديل'], 'pmodel')
    with p6: p_order = choose_col(prod,'رقم الطلبية في المتابعة',['رقم الطلبية','طلبية','order'], 'porder')
    p7,p8,p9 = st.columns(3)
    with p7: p_size = choose_col(prod,'المقاس',['المقاس','size'], 'psize')
    with p8: p_color = choose_col(prod,'كود اللون أو اللون',['كود اللون','اللون','color'], 'pcolor')
    with p9: p_type = choose_col(prod,'نوع الماكينة (اختياري)',['نوع الماكينة','نوع الماكينه'], 'ptype')

    st.subheader('أعمدة خطة تحميل الماكينات')
    q1,q2,q3 = st.columns(3)
    with q1: q_machine = choose_col(plan,'رقم الماكينة في الخطة',['رقم الماكينة','رقم الماكينه','machine'], 'qm')
    with q2: q_order = choose_col(plan,'رقم الطلبية في الخطة',['طلبية','رقم الطلبية','order'], 'qo')
    with q3: q_model = choose_col(plan,'الموديل في الخطة',['موديل المصنع','كود الموديل','موديل'], 'qmodel')
    q4,q5,q6 = st.columns(3)
    with q4: q_size = choose_col(plan,'المقاس في الخطة',['مقاس','المقاس','size'], 'qsize')
    with q5: q_color = choose_col(plan,'كود اللون في الخطة',['كود اللون','color'], 'qcolor')
    with q6: q_rank = choose_col(plan,'ترتيب الموديل',['ترتيب الموديل','ترتيب'], 'qrank')

    required_choices = [p_machine,p_need,p_needle,p_model,p_order,p_size,p_color,q_machine,q_order,q_model,q_size,q_color,q_rank]
    if any(x == '— اختاري —' for x in required_choices):
        st.warning('اختاري كل الأعمدة المطلوبة عشان نطلع النتائج بشكل صحيح.')
        st.stop()

    # Historical daily production columns are detected from date-like headings.
    daily_cols = [c for c in prod.columns if is_date_header(c)]
    st.subheader('إنتاج اليوم')
    st.write('اكتبي إجمالي إنتاج اليوم لكل ماكينة بالفردة. لو مش معاكي قراءة اليوم سيبيها صفر.')
    machine_values = sorted({machine_key(x) for x in prod[p_machine].dropna() if machine_key(x)})
    daily_input = {}
    cols = st.columns(4)
    for i,m in enumerate(machine_values):
        with cols[i%4]:
            daily_input[m] = st.number_input(f'إنتاج ماكينة {m} اليوم (فردة)', min_value=0, step=1, value=0, key=f'daily_{m}')

    rates = {(108,''):38,(120,''):30,(132,''):31,(156,'ساده'):25,(156,'فوطه'):23.5,(168,'فوطه'):25,(168,'ساده'):26,(200,''):18}
    results, counter_flags, alerts = [], [], []
    for _, r in prod.iterrows():
        m = machine_key(r[p_machine])
        if not m: continue
        rem_raw = pd.to_numeric(pd.Series([r[p_need]]), errors='coerce').iloc[0]
        rem_pieces = rem_raw * 24 if pd.notna(rem_raw) and p_unit == 'دستة' else rem_raw
        needle = pd.to_numeric(pd.Series([r[p_needle]]), errors='coerce').iloc[0]
        needle = int(needle) if pd.notna(needle) else 0
        model, order, size, color = map(str, [r[p_model],r[p_order],r[p_size],r[p_color]])
        typ = str(r[p_type]) if p_type != '— اختاري —' else ''
        typn = norm(typ)
        typ_key = 'فوطه' if 'فوطه' in typn else ('ساده' if 'ساده' in typn else '')
        rate = rates.get((needle,typ_key), rates.get((needle,'')))
        actual = daily_input.get(m,0)
        rate_pieces = (actual/24) if actual > 0 else rate
        days_left = (rem_pieces/24/rate_pieces) if rate_pieces and pd.notna(rem_pieces) and rem_pieces > 0 else (0 if pd.notna(rem_pieces) and rem_pieces <= 0 else np.nan)

        # Find next model by same machine and next rank, matching current order/model/size/color where possible.
        mp = plan[plan[q_machine].map(machine_key) == m].copy()
        next_model = 'لا يوجد موديل تالٍ'
        next_order = ''
        plan_warning = ''
        if not mp.empty:
            rank_num = pd.to_numeric(mp[q_rank], errors='coerce')
            same = mp[mp[q_model].astype(str).str.strip() == model.strip()]
            if q_order:
                same_order = same[same[q_order].astype(str).str.strip() == order.strip()]
                if not same_order.empty: same = same_order
            if not same.empty:
                current_rank = pd.to_numeric(same[q_rank], errors='coerce').min()
                later = mp[rank_num > current_rank].copy()
                later['_rank'] = pd.to_numeric(later[q_rank], errors='coerce')
                later = later.sort_values('_rank')
                if not later.empty:
                    nr = later.iloc[0]
                    next_model = str(nr[q_model]); next_order = str(nr[q_order])
            else:
                plan_warning = 'لم يتم العثور على الموديل/الطلبية الحالية في كارت الماكينة'

        # Counter anomaly checks from historical daily columns, plus today's manual entry.
        hist_values = []
        for dc in daily_cols:
            val = pd.to_numeric(pd.Series([r[dc]]), errors='coerce').iloc[0]
            if pd.notna(val) and val > 0:
                hist_values.append(float(val))
        hist_median = float(np.median(hist_values)) if hist_values else np.nan
        hist_max = float(np.max(hist_values)) if hist_values else np.nan
        flags = []
        if pd.notna(rem_pieces) and rem_pieces < 0:
            flags.append('المتبقي بالسالب')
        if actual > 0:
            if actual > 100000:
                flags.append('قراءة اليوم كبيرة جدًا؛ احتمال خطأ إدخال/عداد')
            if hist_median and actual > hist_median * 2.5:
                flags.append('إنتاج اليوم أعلى من المعتاد بأكثر من 2.5 مرة')
            if hist_median and actual < hist_median * 0.2:
                flags.append('إنتاج اليوم أقل من المعتاد بشكل كبير؛ راجعي العداد أو التوقف')
            if rate and actual/24 > rate*1.35:
                flags.append('الإنتاج أعلى من المعدل المرجعي؛ راجعي قراءة العداد')
        if len(hist_values) >= 3 and hist_max > 0 and hist_max > hist_median * 3:
            flags.append('يوجد يوم تاريخي شاذ مقارنة بباقي قراءات الماكينة')
        if flags:
            counter_flags.append({'الماكينة':m,'الموديل':model,'الطلبية':order,'أسباب المراجعة':'؛ '.join(dict.fromkeys(flags)),'أعلى إنتاج تاريخي فردة':hist_max if pd.notna(hist_max) else None,'متوسط الإنتاج التاريخي فردة':round(float(np.mean(hist_values)),1) if hist_values else None})

        if pd.notna(days_left) and days_left <= forecast_days:
            alerts.append(f'ماكينة {m}: الكمية المتبقية قد تنتهي خلال {days_left:.1f} يوم')
        if plan_warning: alerts.append(f'ماكينة {m}: {plan_warning}')
        results.append({'الماكينة':m,'الموديل الحالي':model,'الطلبية':order,'المقاس':size,'اللون':color,'الإبر':needle,'المتبقي فردة':rem_pieces,'إنتاج اليوم فردة':actual,'المرجع دستة/يوم':rate,'أيام متوقعة للانتهاء':round(days_left,1) if pd.notna(days_left) else None,'الموديل التالي حسب ترتيب الكارت':next_model,'طلبية الموديل التالي':next_order,'ملاحظة الخطة':plan_warning})

    out = pd.DataFrame(results).sort_values('أيام متوقعة للانتهاء', na_position='last')
    st.subheader('نتائج التوقعات')
    st.dataframe(out, use_container_width=True, hide_index=True)
    st.download_button('تحميل تقرير التوقعات CSV', out.to_csv(index=False, encoding='utf-8-sig'), file_name='LoomPredict_report.csv', mime='text/csv')

    st.subheader('مراجعة الماكينات والعدادات')
    if counter_flags:
        flags_df = pd.DataFrame(counter_flags).drop_duplicates()
        st.warning(f'تم رصد {len(flags_df)} سجل يحتاج مراجعة. دي إشارات اشتباه وليست حكمًا مؤكدًا بوجود عطل.')
        st.dataframe(flags_df, use_container_width=True, hide_index=True)
        st.download_button('تحميل تقرير مراجعة العدادات CSV', flags_df.to_csv(index=False, encoding='utf-8-sig'), file_name='LoomPredict_counter_checks.csv', mime='text/csv')
    else:
        st.success('لم تظهر قراءات شاذة واضحة وفق قواعد الفحص الحالية. ده لا يستبعد وجود مشكلة عداد.')
    if alerts:
        st.subheader('تنبيهات تغيير الموديل')
        for a in alerts: st.warning(a)
else:
    st.info('ارفعي ملف متابعة الإنتاج وملف خطة تحميل الماكينات لبدء تحديد الأعمدة.')

st.caption('التوقعات تقديرية. مراجعة العداد تعتمد على مقارنة القراءات اليومية بالمعدل التاريخي والمرجعي؛ أي قراءة مشبوهة تحتاج مراجعة فعلية للعداد وسجل الإنتاج.')
