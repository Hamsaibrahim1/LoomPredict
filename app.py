import streamlit as st
import pandas as pd
import numpy as np
import re, zipfile, os
from datetime import datetime

st.set_page_config(page_title='LoomPredict', page_icon='🧦', layout='wide')
st.title('🧦 LoomPredict')
st.caption('تأمين الماكينات قبل تغيير الموديل – حساب الكميات المطلوبة للتكنكال')

# ---------- helpers ----------
def norm(x):
    s = str(x).strip().lower()
    s = s.replace('أ','ا').replace('إ','ا').replace('آ','ا').replace('ى','ي').replace('ة','ه')
    return re.sub(r'[^a-z0-9\u0600-\u06ff]', '', s)

def read_excel_smart(upload, production=False):
    raw = pd.read_excel(upload, header=None)
    header_idx = 0
    if production:
        best_score = -1
        for i in range(min(30, len(raw))):
            vals = [norm(v) for v in raw.iloc[i].tolist() if pd.notna(v)]
            joined = ' '.join(vals)
            score = sum(k in joined for k in ['رقمالماكينه','عددالابر','كودالموديل','الكميهالمتبقيه'])
            if score > best_score:
                best_score, header_idx = score, i
        if best_score < 2:
            header_idx = 0
    headers = []
    for j, v in enumerate(raw.iloc[header_idx].tolist()):
        name = str(v).strip() if pd.notna(v) else ''
        headers.append(name if name else f'عمود بدون اسم {j+1}')
    df = raw.iloc[header_idx+1:].copy()
    df.columns = headers
    df = df.dropna(how='all').reset_index(drop=True)
    # remove duplicate header rows accidentally repeated in the body
    df = df[~df.iloc[:,0].astype(str).str.strip().eq(headers[0])].reset_index(drop=True)
    return df, header_idx + 1

def pick_col(df, label, hints, required=True):
    cols = list(df.columns)
    by_norm = {norm(c): c for c in cols}
    guess = None
    for hint in hints:
        nh = norm(hint)
        for c in cols:
            if nh and (nh == norm(c) or nh in norm(c)):
                guess = c; break
        if guess is not None: break
    options = ['— اختاري —'] + cols
    idx = options.index(guess) if guess in options else 0
    chosen = st.selectbox(label, options, index=idx, key=label)
    return None if chosen == '— اختاري —' else chosen

def clean_key(v):
    if pd.isna(v): return ''
    s = str(v).strip()
    # Excel numeric identifiers often appear as 123.0
    if re.fullmatch(r'-?\d+\.0+', s): s = s.split('.')[0]
    return norm(s)

def num(v):
    try:
        if pd.isna(v): return np.nan
        return float(str(v).replace(',','').strip())
    except: return np.nan

def status_delivered(v):
    s = norm(v)
    return ('تمالتسليم' in s) or (s in ['تم','delivered','done','complete','completed'])

def sort_machine(v):
    s = str(v).strip()
    m = re.search(r'\d+', s)
    return (0, int(m.group())) if m else (1, s)

# ---------- uploads ----------
with st.sidebar:
    st.header('الملفات')
    prod_file = st.file_uploader('ملف متابعة الإنتاج', type=['xlsx','xls'])
    plan_file = st.file_uploader('ملف خطة تحميل الماكينات', type=['xlsx','xls'])
    st.divider()
    days = st.number_input('فترة التأمين (أيام)', min_value=1, max_value=14, value=2, step=1)

rates = {(108,''):38,(120,''):30,(132,''):31,(156,'ساده'):25,(156,'فوطه'):23.5,(168,'فوطه'):25,(168,'ساده'):26,(200,''):18}

if not prod_file or not plan_file:
    st.info('ارفعي ملف متابعة الإنتاج وملف خطة تحميل الماكينات للبدء.')
    st.stop()

try:
    prod, header_row = read_excel_smart(prod_file, production=True)
    plan, _ = read_excel_smart(plan_file, production=False)
except Exception as e:
    st.error(f'تعذر قراءة الملفات: {e}')
    st.stop()

st.success(f'تم التعرف على عناوين متابعة الإنتاج في الصف رقم {header_row}.')
with st.expander('معاينة عناوين وبيانات الملفين'):
    st.write('متابعة الإنتاج'); st.dataframe(prod.head(5), use_container_width=True)
    st.write('خطة تحميل الماكينات'); st.dataframe(plan.head(5), use_container_width=True)

st.subheader('تأكيد أعمدة متابعة الإنتاج')
p1,p2,p3 = st.columns(3)
with p1: p_machine = pick_col(prod,'رقم الماكينة – المتابعة',['رقم الماكينة','رقم الماكينه','machine no'])
with p2: p_model = pick_col(prod,'كود الموديل الحالي – المتابعة',['كود الموديل','كود موديل'])
with p3: p_order = pick_col(prod,'رقم الطلبية – المتابعة',['رقم الطلبية','طلبية','رقم امر'])
p4,p5,p6 = st.columns(3)
with p4: p_size = pick_col(prod,'المقاس – المتابعة',['المقاس','size'])
with p5: p_color = pick_col(prod,'كود اللون – المتابعة',['كود اللون','color code'])
with p6: p_remaining = pick_col(prod,'الكمية المتبقية دستة – المتابعة',['الكمية المتبقية دستة','المتبقية دستة','remaining'])
p7,p8 = st.columns(2)
with p7: p_needle = pick_col(prod,'عدد الإبر – المتابعة',['عدد الابر','عدد الإبر','needle'])
with p8: p_type = pick_col(prod,'نوع الماكينة (إن وجد) – المتابعة',['نوع الماكينة','نوع الماكينه','machine type'], required=False)

st.subheader('تأكيد أعمدة خطة تحميل الماكينات')
a1,a2,a3 = st.columns(3)
with a1: q_machine = pick_col(plan,'رقم الماكينة – الخطة',['رقم الماكينة','رقم الماكينه','machine'])
with a2: q_model = pick_col(plan,'موديل – الخطة',['موديل','model'])
with a3: q_order = pick_col(plan,'الطلبية – الخطة',['طلبية','رقم الطلبية','order'])
a4,a5,a6 = st.columns(3)
with a4: q_size = pick_col(plan,'المقاس – الخطة',['مقاس','المقاس','size'])
with a5: q_color = pick_col(plan,'كود اللون – الخطة',['كود اللون','color code'])
with a6: q_qty = pick_col(plan,'الكمية المطلوبة دستة – الخطة',['الكمية المطلوبة دستة','مطلوبة دستة','required dozen'])
a7,a8 = st.columns(2)
with a7: q_rank = pick_col(plan,'ترتيب الموديل – الخطة',['ترتيب الموديل','ترتيب','sequence'])
with a8: q_status = pick_col(plan,'وضع الكارت للتكنكال – الخطة',['وضع الكارت للتكنكال','التكنكال','technical status','وضع الكارت'])

required = [p_machine,p_model,p_order,p_size,p_color,p_remaining,p_needle,q_machine,q_model,q_order,q_size,q_color,q_qty,q_rank,q_status]
if any(x is None for x in required):
    st.warning('اختاري كل الأعمدة المطلوبة قبل عرض خطة التأمين.')
    st.stop()

# normalize keys, retain original values
prod = prod.copy(); plan = plan.copy()
for df, cols in [(prod,[p_machine,p_model,p_order,p_size,p_color]),(plan,[q_machine,q_model,q_order,q_size,q_color])]:
    for c in cols: df['_k_'+str(c)] = df[c].map(clean_key)

# plan order numeric for reliable sequence
plan['_rank_num'] = pd.to_numeric(plan[q_rank], errors='coerce')
plan['_qty_num'] = plan[q_qty].map(num)
prod['_remaining_num'] = prod[p_remaining].map(num)
prod['_needle_num'] = prod[p_needle].map(num)

# rates and algorithm
st.divider()
st.subheader('خطة تأمين الماكينات')
st.caption(f'الفترة المطلوبة: {days} يوم. يتم ترتيب النتائج حسب رقم الماكينة، وليس حسب موعد التغيير.')

# Optional rate overrides are not daily production entry; defaults can be edited if needed.
use_rate_defaults = st.checkbox('استخدام معدلات الإنتاج المرجعية المحفوظة', value=True)

results = []
issues = []
for _, current in prod.iterrows():
    machine = current[p_machine]
    if pd.isna(machine): continue
    rem = current['_remaining_num']
    if pd.isna(rem):
        issues.append({'الماكينة':machine,'المشكلة':'الكمية المتبقية بالدستة غير مقروءة'})
        continue
    needle = int(current['_needle_num']) if pd.notna(current['_needle_num']) else 0
    typ = norm(current[p_type]) if p_type and pd.notna(current[p_type]) else ''
    typ_label = 'فوطه' if 'فوط' in typ else ('ساده' if 'ساد' in typ else '')
    rate = rates.get((needle,typ_label), rates.get((needle,''), None))
    if needle == 120 and clean_key(machine) == clean_key('98'): rate = 35
    if not use_rate_defaults or rate is None or rate <= 0:
        issues.append({'الماكينة':machine,'المشكلة':f'لا يوجد معدل مرجعي معروف لعدد الإبر {needle} ونوع {typ_label or "غير محدد"}'})
        continue
    need = rate * days
    current_available = max(0, rem)
    cumulative = current_available
    requested = []
    # Match the current model row on this machine using the complete identifying key.
    same_machine = plan[plan['_k_'+str(q_machine)] == clean_key(machine)].copy()
    match = same_machine[
        (same_machine['_k_'+str(q_model)] == clean_key(current[p_model])) &
        (same_machine['_k_'+str(q_order)] == clean_key(current[p_order])) &
        (same_machine['_k_'+str(q_size)] == clean_key(current[p_size])) &
        (same_machine['_k_'+str(q_color)] == clean_key(current[p_color]))
    ]
    if match.empty:
        # less strict fallback for formatting differences in order/size/color, but still require machine + model
        match = same_machine[same_machine['_k_'+str(q_model)] == clean_key(current[p_model])]
    if match.empty:
        issues.append({'الماكينة':machine,'المشكلة':'لم يتم العثور على الموديل الحالي في كارت الماكينة؛ راجعي تطابق عمود موديل مع كود الموديل'})
        continue
    current_rank = match['_rank_num'].min()
    if pd.isna(current_rank):
        issues.append({'الماكينة':machine,'المشكلة':'ترتيب الموديل الحالي غير رقمي في كارت الماكينة'})
        continue
    later = same_machine[same_machine['_rank_num'] > current_rank].sort_values('_rank_num')
    if cumulative < need:
        for _, nxt in later.iterrows():
            qty = nxt['_qty_num']
            if pd.isna(qty) or qty < 0:
                issues.append({'الماكينة':machine,'المشكلة':f'كمية الموديل التالي {nxt[q_model]} غير واضحة في الخطة'})
                continue
            delivered = status_delivered(nxt[q_status])
            cumulative += qty
            if not delivered:
                requested.append({'الموديل':str(nxt[q_model]),'الطلبية':str(nxt[q_order]),'الكمية بالدستة':qty,'حالة التكنكال':str(nxt[q_status])})
            if cumulative >= need: break
    if cumulative < need:
        risk = 'غير آمن: الكمية لا تكفي حتى نهاية الكارت'
    elif requested:
        risk = 'آمن بعد إرسال الموديلات المطلوبة للتكنكال'
    else:
        risk = 'آمن بالفعل: لا يحتاج إرسال موديل إضافي'
    # Only show machines where at least one pending model must be sent OR current qty alone is insufficient.
    if requested or cumulative < need:
        req_models = ' | '.join([f"{x['الموديل']} ({x['الكمية بالدستة']:g} دستة)" for x in requested]) or 'لا يوجد موديل غير مستلم محدد'
        results.append({
            'رقم الماكينة':machine,
            'الموديل الحالي':current[p_model],
            'الطلبية الحالية':current[p_order],
            'المتبقي الحالي (دستة)':rem,
            'احتياج الفترة (دستة)':need,
            'الموديلات المطلوب إرسالها':req_models,
            'إجمالي المتاح بعد التجهيز (دستة)':cumulative,
            'حالة التأمين':risk,
            '_sort':sort_machine(machine)
        })

if results:
    out = pd.DataFrame(results).sort_values('_sort').drop(columns=['_sort'])
    st.dataframe(out, use_container_width=True, hide_index=True)
    st.download_button('تحميل خطة التأمين CSV', out.to_csv(index=False, encoding='utf-8-sig'), file_name='LoomPredict_SafetyPlan.csv', mime='text/csv')
else:
    st.success('لا توجد ماكينات تحتاج إرسال موديلات إضافية وفق البيانات والإعدادات الحالية.')

if issues:
    st.subheader('مراجعات مطلوبة في البيانات')
    st.dataframe(pd.DataFrame(issues).drop_duplicates(), use_container_width=True, hide_index=True)

# Meter anomaly review from historical daily production columns: date-like headers only.
st.subheader('مراجعة قراءات العدادات')
date_cols = []
for c in prod.columns:
    s = str(c).strip()
    if re.search(r'\d', s) and (re.search(r'[-/]', s) or 'انتاج' in norm(s) or 'الانتاج' in norm(s)):
        date_cols.append(c)
if date_cols:
    anomalies=[]
    for _, r in prod.iterrows():
        vals = [num(r[c]) for c in date_cols]
        vals = [v for v in vals if pd.notna(v) and v > 0]
        if len(vals) >= 3:
            med = float(np.median(vals)); mx = max(vals); mn = min(vals)
            if med > 0 and (mx > med*1.8 or mn < med*0.25):
                anomalies.append({'رقم الماكينة':r[p_machine],'الموديل':r[p_model],'متوسط الإنتاج اليومي المسجل':round(med,1),'أعلى قراءة':mx,'أقل قراءة موجبة':mn,'الملاحظة':'قراءة شاذة محتملة – راجعي العداد/الإدخال'})
    if anomalies:
        st.dataframe(pd.DataFrame(anomalies), use_container_width=True, hide_index=True)
    else:
        st.info('لم تظهر قراءات شاذة واضحة في الأعمدة التي تم التعرف عليها كتاريخية.')
else:
    st.info('لم يتم التعرف تلقائيًا على أعمدة الإنتاج التاريخية لمراجعة العدادات.')

st.caption('تنبيه: الحساب تقديري حسب معدلات الإنتاج المرجعية. عند عدم وجود معدل مناسب أو عدم تطابق الموديل الحالي مع كارت الماكينة، تظهر مراجعة بيانات بدل اختراع نتيجة. لا يتم اعتبار الكمية المطلوبة متاحة فعليًا إلا بعد تجهيز/تسليم الموديل.')
