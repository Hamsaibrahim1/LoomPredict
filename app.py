import streamlit as st
import pandas as pd, numpy as np, re, io
from datetime import datetime

st.set_page_config(page_title='LoomPredict', page_icon='🧦', layout='wide')
st.title('🧦 LoomPredict')
st.caption('تحديد الماكينات التي تحتاج إرسال موديلات للتكنكال قبل التغيير')

def norm(v):
    if pd.isna(v): return ''
    s=str(v).replace('\u00a0',' ').strip().lower()
    s=s.replace('أ','ا').replace('إ','ا').replace('آ','ا').replace('ى','ي')
    s=re.sub(r'\s+',' ',s)
    return s

def key(v):
    s=norm(v)
    s=re.sub(r'\s+','',s)
    if re.fullmatch(r'-?\d+\.0+',s): s=s.split('.')[0]
    return s

def num(v):
    if pd.isna(v): return np.nan
    s=str(v).replace(',','').strip()
    try: return float(s)
    except: return np.nan

def find_col(df, hints):
    # Prefer exact header matches before partial matches (important for 'موديل' vs 'ترتيب الموديل').
    for hint in hints:
        h=key(hint)
        for c in df.columns:
            if h and h == key(c): return c
    for hint in hints:
        h=key(hint)
        for c in df.columns:
            if h and h in key(c): return c
    return None

def read_prod(file):
    book=pd.ExcelFile(file)
    # use the sheet with the newest valid header/data and most complete remaining-quantity column
    candidates=[]
    for sheet in book.sheet_names:
        raw=pd.read_excel(file,sheet_name=sheet,header=None)
        idx=None
        for i in range(min(20,len(raw))):
            row=' '.join(key(x) for x in raw.iloc[i].tolist() if pd.notna(x))
            if 'رقمالماكينه' in row and 'المتبقي' in row and 'دستة' in row:
                idx=i; break
        if idx is None: continue
        headers=[]
        for j,v in enumerate(raw.iloc[idx].tolist()):
            h=str(v).strip() if pd.notna(v) else ''
            headers.append(h or f'عمود_{j+1}')
        d=raw.iloc[idx+1:].copy(); d.columns=headers
        d=d.dropna(how='all').reset_index(drop=True)
        machine=find_col(d,['رقم الماكينه']); rem=find_col(d,['الكمية المتبقية دستة'])
        if machine and rem:
            candidates.append((len(d),sheet,d))
    if not candidates: raise ValueError('لم أجد صف العناوين الصحيح في ملف المتابعة.')
    candidates.sort(reverse=True,key=lambda x:x[0])
    # Latest sheet by workbook order is the current one, but prefer the sheet with most rows on ties
    _,sheet,d=candidates[0]
    return d,sheet

def delivered(v):
    s=key(v)
    return 'تمالتسليم' in s or s in {'تم','delivered','done','complete','completed'}

def rate_for(machine, needle, typ):
    t=key(typ)
    if needle==108: return 38
    if needle==120: return 35 if key(machine)=='98' else 30
    if needle==132: return 31
    if needle==156: return 23.5 if 'فوط' in t else 25
    if needle==168: return 25 if 'فوط' in t else 26
    if needle==200: return 18
    return np.nan

def main_calc(prod, plan, days):
    pm=find_col(prod,['رقم الماكينه']); pmodel=find_col(prod,['رقم موديل المصنع','كود الموديل'])
    prem=find_col(prod,['الكمية المتبقية دستة']); pne=find_col(prod,['عدد الابر']); ptype=find_col(prod,['نوع الماكينة'])
    qm=find_col(plan,['رقم الماكينه']); qmodel=find_col(plan,['موديل']); qrank=find_col(plan,['ترتيب الموديل'])
    qqty=find_col(plan,['الكمية المطلوبة دستة']); qstatus=find_col(plan,['وضع الكارت للتكنيكل'])
    qserial=find_col(plan,['رقم مسلسل']); qdate=find_col(plan,['تاريخ استلام التحميل']); qclosed=find_col(plan,['اغلاق كارت االانتاج']); qdateclosed=find_col(plan,['تاريخ الاغلاق'])
    needed=[pm,pmodel,prem,pne,ptype,qm,qmodel,qrank,qqty,qstatus]
    if any(c is None for c in needed): raise ValueError('فيه عمود أساسي مش موجود في واحد من الملفين. راجعي عناوين الملفين.')
    p=prod.copy(); q=plan.copy()
    p['_machine']=p[pm].map(key); p['_model']=p[pmodel].map(key); p['_remaining']=p[prem].map(num); p['_needle']=p[pne].map(num)
    q['_machine']=q[qm].map(key); q['_model']=q[qmodel].map(key); q['_rank']=q[qrank].map(num); q['_qty']=q[qqty].map(num)
    if qdate: q['_date']=pd.to_datetime(q[qdate],errors='coerce')
    else: q['_date']=pd.NaT
    results=[]; issues=[]; stoppages=[]; send_lines=[]
    for _,cur in p.iterrows():
        machine=cur[pm]
        if not key(machine): continue
        rem=cur['_remaining']; needle=cur['_needle']; model=cur[pmodel]
        if pd.isna(rem):
            issues.append({'رقم الماكينة':machine,'المشكلة':'الكمية المتبقية غير مقروءة'}); continue
        if pd.isna(needle):
            issues.append({'رقم الماكينة':machine,'المشكلة':'عدد الإبر غير مقروء'}); continue
        rate=rate_for(machine,int(needle),cur[ptype] if ptype else '')
        if pd.isna(rate):
            issues.append({'رقم الماكينة':machine,'المشكلة':f'لا يوجد معدل مرجعي لعدد الإبر {int(needle)}'}); continue
        need=rate*days
        if rem >= need: continue
        same=q[q['_machine']==key(machine)].copy()
        matches=same[same['_model']==key(model)].copy()
        if matches.empty:
            msg=f'الموديل الحالي ({model}) غير موجود في عمود موديل بالخطة'
            issues.append({'رقم الماكينة':machine,'المشكلة':msg})
            stoppages.append({'رقم الماكينة':machine,'الموديل الحالي':model,'سبب احتمال التوقف':'لم يتم العثور على الموديل الحالي في كروت خطة التحميل'})
            continue
        # Prefer the latest matching card, and prefer a row explicitly marked current if available.
        current_label=find_col(same,['موقف الموديل'])
        if current_label:
            marked=matches[matches[current_label].map(key).str.contains('الموديلالحالي',na=False)]
            if not marked.empty: matches=marked
        matches=matches.sort_values('_date',na_position='first')
        curplan=matches.iloc[-1]
        rank=curplan['_rank']; serial=curplan[qserial] if qserial else None
        # Sequence is followed within the same loading serial when available. If there are no ranked rows after it,
        # report that the future sequence is not specified instead of using old closed cards.
        if pd.isna(rank):
            msg='ترتيب الموديل الحالي غير محدد في الخطة'
            issues.append({'رقم الماكينة':machine,'المشكلة':msg})
            stoppages.append({'رقم الماكينة':machine,'الموديل الحالي':model,'سبب احتمال التوقف':msg})
            continue
        later=same[same['_rank'].notna() & (same['_rank']>rank)].copy()
        if qserial and pd.notna(serial): later=later[later[qserial].astype(str).eq(str(serial))]
        if qclosed: later=later[~later[qclosed].map(key).str.contains('اغلاق',na=False)]
        if qdateclosed: later=later[later[qdateclosed].isna()]
        if qdate: later=later.sort_values(['_date','_rank'],na_position='last')
        else: later=later.sort_values('_rank')
        cumulative=max(0,rem); requested=[]; unknown=[]; saw_next=False
        for _,nxt in later.iterrows():
            saw_next=True
            qty=nxt['_qty']; nxtmodel=nxt[qmodel]; status=nxt[qstatus]
            if pd.isna(qty):
                unknown.append(str(nxtmodel)); break
            if qty < 0:
                unknown.append(str(nxtmodel)); break
            cumulative+=qty
            if not delivered(status):
                requested.append(f'{nxtmodel} — {qty:g} دستة (التكنكال: {status if pd.notna(status) else "غير محدد"})')
                send_lines.append(f'{machine} - {nxtmodel}')
            if cumulative>=need: break
        if not saw_next:
            unknown.append('لا يوجد موديل تالٍ بعد الموديل الحالي في كروت التحميل؛ الماكينة معرضة للتوقف')
            stoppages.append({'رقم الماكينة':machine,'الموديل الحالي':model,'سبب احتمال التوقف':'لا يوجد موديل تالٍ بعد الموديل الحالي في كروت التحميل'})
        elif cumulative < need and not unknown:
            unknown.append('كمية الموديلات المتاحة لا تكفي فترة التأمين')
            stoppages.append({'رقم الماكينة':machine,'الموديل الحالي':model,'سبب احتمال التوقف':'الموديلات التالية المتاحة لا تغطي احتياج فترة التأمين'})
        if requested or cumulative<need:
            results.append({'رقم الماكينة':machine,'الموديل الحالي':model,'المتبقي الحالي (دستة)':rem,'معدل الإنتاج المرجعي (دستة/يوم)':rate,'احتياج فترة التأمين (دستة)':need,'الموديلات المطلوب إرسالها': '\n'.join(requested) if requested else 'لا يوجد موديل غير مستلم محدد','إجمالي المتاح بعد الموديلات التالية (دستة)':cumulative,'الحالة':'آمن بعد الإرسال' if cumulative>=need and requested else ('آمن بدون إرسال' if cumulative>=need else 'غير آمن / الخطة غير كافية'),'ملاحظات':'; '.join(unknown)})
    results.sort(key=lambda x: (0,num(x['رقم الماكينة'])) if pd.notna(num(x['رقم الماكينة'])) else (1,str(x['رقم الماكينة'])))
    return pd.DataFrame(results),pd.DataFrame(issues),pd.DataFrame(stoppages),send_lines

with st.sidebar:
    st.header('الملفات')
    prod_file=st.file_uploader('ملف متابعة الإنتاج',type=['xlsx','xls'])
    plan_file=st.file_uploader('ملف خطة تحميل الماكينات',type=['xlsx','xls'])
    days=st.number_input('فترة التأمين بالأيام',min_value=1,max_value=14,value=2,step=1)
if not prod_file or not plan_file:
    st.info('ارفعي الملفين من القائمة الجانبية. التطبيق يختار الموديل الحالي من المتابعة ثم يبحث عنه في عمود «موديل» بالخطة.')
    st.stop()
try:
    prod,sheet=read_prod(prod_file)
    plan=pd.read_excel(plan_file,sheet_name='data planning')
    results,issues,stoppages,send_lines=main_calc(prod,plan,int(days))
    st.success(f'تمت قراءة ورقة المتابعة: {sheet}. فترة التأمين: {days} يوم.')
    st.subheader('الماكينات التي تحتاج متابعة/إرسال موديلات')
    if results.empty: st.info('لم تظهر ماكينات تحتاج إرسالًا وفق البيانات المقروءة. راجعي أيضًا قسم مشكلات المطابقة أدناه.')
    else:
        st.dataframe(results,use_container_width=True,hide_index=True)
        st.download_button('تحميل خطة التأمين Excel',data=results.to_csv(index=False,encoding='utf-8-sig'),file_name='LoomPredict_SafetyPlan.csv',mime='text/csv')
    if not stoppages.empty:
        st.subheader('⚠️ ماكينات معرضة للتوقف')
        st.dataframe(stoppages,use_container_width=True,hide_index=True)
        st.download_button('تحميل قائمة الماكينات المعرضة للتوقف CSV',data=stoppages.to_csv(index=False,encoding='utf-8-sig'),file_name='LoomPredict_StopRisk.csv',mime='text/csv')
    st.subheader('📋 قائمة جاهزة للنسخ والإرسال للتكنكال')
    if send_lines:
        copy_text='\n'.join(send_lines)
        st.text_area('رقم الماكينة - الموديل المطلوب إرساله (انسخي القائمة كلها)',value=copy_text,height=220)
        st.download_button('تحميل قائمة إرسال التكنكال CSV',data=pd.DataFrame({'الماكينة - الموديل':send_lines}).to_csv(index=False,encoding='utf-8-sig'),file_name='LoomPredict_Technical_Send.csv',mime='text/csv')
    else:
        st.info('لا توجد موديلات غير مستلمة للتكنكال ضمن التسلسل الذي تم العثور عليه.')
    if not issues.empty:
        st.subheader('مشكلات المطابقة أو البيانات')
        st.dataframe(issues,use_container_width=True,hide_index=True)
    st.caption('مهم: لا تُعتبر الكمية المطلوبة «حسب كمية العداد» كمية مضمونة. إذا لم يوجد تسلسل تالٍ واضح، تظهر ملاحظة بدل اعتبار الماكينة آمنة.')
except Exception as e:
    st.error(f'حصلت مشكلة أثناء قراءة الملفات أو الحساب: {e}')
