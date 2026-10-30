import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import date

st.set_page_config(page_title='LoomPredict', page_icon='🧦', layout='wide')
st.title('🧦 LoomPredict')
st.caption('متابعة الإنتاج والتنبؤ بموعد تغيير موديل الماكينة')

st.info('ارفعي ملف متابعة الإنتاج وملف خطة تحميل الماكينات. التطبيق يحاول التعرف على الأعمدة تلقائيًا، ويمكنك تعديل الاختيارات عند الحاجة.')

def read_excel(upload):
    if upload is None: return None
    try: return pd.read_excel(upload)
    except Exception as e:
        st.error(f'تعذر قراءة الملف: {e}')
        return None

def norm(x):
    return re.sub(r'[^a-z0-9\u0600-\u06ff]', '', str(x).lower())

def find_col(df, hints):
    cols=list(df.columns)
    for h in hints:
        nh=norm(h)
        for c in cols:
            if nh and nh in norm(c): return c
    return None

def choose_col(df, label, hints):
    guess=find_col(df,hints)
    opts=['— اختاري —']+list(df.columns)
    idx=opts.index(guess) if guess in opts else 0
    return st.selectbox(label,opts,index=idx,key=label)

with st.sidebar:
    st.header('الملفات')
    prod_file=st.file_uploader('ملف متابعة الإنتاج',type=['xlsx','xls'])
    plan_file=st.file_uploader('ملف خطة تحميل الماكينات',type=['xlsx','xls'])
    st.divider()
    days=st.number_input('عدد أيام التنبؤ',min_value=1,max_value=30,value=3)

prod=read_excel(prod_file)
plan=read_excel(plan_file)

if prod is not None:
    st.subheader('معاينة ملف متابعة الإنتاج')
    st.dataframe(prod.head(8),use_container_width=True)
    st.subheader('تحديد الأعمدة')
    c1,c2,c3=st.columns(3)
    with c1: p_machine=choose_col(prod,'رقم الماكينة في المتابعة',['رقم الماكينة','machine no','machine'])
    with c2: p_need=choose_col(prod,'الكمية المتبقية (فردة) في المتابعة',['الكمية المتبقية فردة','المتبقية فردة','remaining'])
    with c3: p_needle=choose_col(prod,'عدد الإبر في المتابعة',['عدد الابر','عدد الإبر','needle'])
    c4,c5,c6=st.columns(3)
    with c4: p_model=choose_col(prod,'الموديل الحالي في المتابعة',['كود الموديل','موديل المصنع','الموديل'])
    with c5: p_size=choose_col(prod,'المقاس في المتابعة',['المقاس','size'])
    with c6: p_color=choose_col(prod,'اللون/كود اللون في المتابعة',['كود اللون','اللون','color'])
else:
    p_machine=p_need=p_needle=p_model=p_size=p_color=None

if plan is not None:
    st.subheader('معاينة خطة تحميل الماكينات')
    st.dataframe(plan.head(8),use_container_width=True)
    st.subheader('تحديد أعمدة الخطة')
    a,b,c=st.columns(3)
    with a: q_machine=choose_col(plan,'رقم الماكينة في الخطة',['رقم الماكينة','machine'])
    with b: q_order=choose_col(plan,'رقم الطلبية في الخطة',['طلبية','رقم الطلبية','order'])
    with c: q_model=choose_col(plan,'الموديل في الخطة',['موديل','كود الموديل'])
    d,e,f=st.columns(3)
    with d: q_size=choose_col(plan,'المقاس في الخطة',['مقاس','المقاس','size'])
    with e: q_color=choose_col(plan,'كود اللون في الخطة',['كود اللون','color'])
    with f: q_qty=choose_col(plan,'الكمية المطلوبة فردة في الخطة',['الكمية المطلوبة فردة','مطلوبة فردة'])
    q_rank=choose_col(plan,'ترتيب الموديل في الخطة',['ترتيب الموديل','ترتيب'])

st.divider()
if prod is not None and plan is not None and all([p_machine,p_need,p_needle,p_model,p_size,p_color,q_machine,q_order,q_model,q_size,q_color,q_qty,q_rank]):
    st.subheader('إنتاج اليوم')
    st.write('أدخلي إجمالي إنتاج اليوم لكل ماكينة بالفردة. اتركيه صفرًا إذا لم تتوفر القراءة.')
    machines=sorted(prod[p_machine].dropna().astype(str).unique())
    daily={}
    cols=st.columns(4)
    for i,m in enumerate(machines):
        with cols[i%4]: daily[m]=st.number_input(f'إنتاج ماكينة {m} (فردة)',min_value=0,step=1,value=0,key=f'day_{m}')

    rates={(108,''):38,(120,''):30,(132,''):31,(156,'سادة'):25,(156,'فوطة'):23.5,(168,'فوطة'):25,(168,'سادة'):26,(200,''):18}
    st.subheader('النتائج والتنبؤ')
    results=[]; alerts=[]
    for _,r in prod.iterrows():
        m=str(r[p_machine]);
        try: rem=float(r[p_need])
        except: rem=np.nan
        try: needle=int(float(r[p_needle]))
        except: needle=0
        model=str(r[p_model]); size=str(r[p_size]); color=str(r[p_color])
        typ=''
        if 'نوع الماكينة' in prod.columns: typ=str(r.get('نوع الماكينة',''))
        rate=rates.get((needle,typ),rates.get((needle,''),None))
        actual=daily.get(m,0)
        if actual>0: rate_today=actual/24
        else: rate_today=rate
        days_left=(rem/24/rate_today) if rate_today and pd.notna(rem) and rem>0 else (0 if pd.notna(rem) and rem<=0 else np.nan)
        # next model by machine and rank, then verify the same machine/order/model/size/color identity
        nxt='لا يوجد موديل تالٍ'; nxt_qty=np.nan; warning=''
        machine_plan=plan[plan[q_machine].astype(str)==m].copy()
        if not machine_plan.empty:
            try:
                current_rank=pd.to_numeric(machine_plan[q_rank],errors='coerce')
                current_rows=machine_plan[machine_plan[q_model].astype(str)==model]
                if not current_rows.empty:
                    cr=pd.to_numeric(current_rows[q_rank],errors='coerce').min()
                    later=machine_plan[pd.to_numeric(machine_plan[q_rank],errors='coerce')>cr].copy()
                    later=later.sort_values(q_rank)
                    if not later.empty:
                        nr=later.iloc[0]; nxt=str(nr[q_model]); nxt_qty=pd.to_numeric(pd.Series([nr[q_qty]]),errors='coerce').iloc[0]
                        if pd.notna(nxt_qty) and nxt_qty<=0: warning='كمية الموديل التالي غير كافية/صفر'
                else: warning='لم يتم العثور على الموديل الحالي في كارت الماكينة'
            except Exception: warning='راجعي ترتيب الموديل في الخطة'
        if pd.notna(days_left) and days_left<=days: alerts.append(f'ماكينة {m}: متوقع انتهاء الكمية خلال {days_left:.1f} يوم')
        if warning: alerts.append(f'ماكينة {m}: {warning}')
        if rate and actual>0 and (actual/24>rate*1.3 or actual/24<rate*0.5): alerts.append(f'ماكينة {m}: إنتاج اليوم {actual:,} فردة؛ راجعي قراءة العداد مقارنة بالمرجع {rate} دستة/يوم')
        results.append({'الماكينة':m,'الموديل الحالي':model,'المقاس':size,'اللون':color,'الإبر':needle,'المتبقي فردة':rem,'إنتاج اليوم فردة':actual,'المرجع دستة/يوم':rate,'أيام متوقعة للانتهاء':round(days_left,1) if pd.notna(days_left) else None,'الموديل التالي حسب الترتيب':nxt,'تنبيه':warning})
    out=pd.DataFrame(results).sort_values('أيام متوقعة للانتهاء',na_position='last')
    st.dataframe(out,use_container_width=True,hide_index=True)
    if alerts:
        st.subheader('التنبيهات')
        for x in alerts: st.warning(x)
    else: st.success('لا توجد تنبيهات وفق البيانات المدخلة.')
    st.download_button('تحميل تقرير التوقعات Excel',out.to_csv(index=False,encoding='utf-8-sig'),file_name='LoomPredict_report.csv',mime='text/csv')
else:
    st.warning('ارفعي الملفين وحددي الأعمدة المطلوبة لعرض التوقعات.')

st.caption('ملاحظة: التنبؤ تقديري اعتمادًا على المتبقي ومعدل الإنتاج المرجعي أو إنتاج اليوم المدخل. لا يمثل موعد تغيير مؤكدًا. راجعي تطابق الموديل والمقاس واللون والطلبية وترتيب الكارت قبل اتخاذ قرار التشغيل.')
