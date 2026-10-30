# LoomPredict

تطبيق Streamlit أولي لقراءة ملف متابعة الإنتاج وخطة تحميل الماكينات، وإظهار تقدير أيام انتهاء الكمية والتنبيهات.

## التشغيل المحلي
```bash
pip install -r requirements.txt
streamlit run app.py
```

## النشر على Streamlit Community Cloud
ارفع `app.py` و`requirements.txt` و`README.md` إلى مستودع GitHub، ثم اختر Branch `master` وMain file path `app.py`.

> النسخة الأولية: راجعي أعمدة الملفات بعد الرفع. التنبؤ يعتمد على معدل مرجعي أو إدخال إنتاج اليوم، ولا يحل محل مراجعة خطة التحميل الفعلية.
