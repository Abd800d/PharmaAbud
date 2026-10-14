# ربط المزامنة الحية (اختياري) — Firebase Firestore

التطبيق يعمل **بالكامل دون خادم**: القاعدة والتعديلات والرسائل تُحفظ على الجهاز.
إذا أردت أن تظهر تعديلاتك ورسائلك **لحظياً عند جميع المستخدمين**، فعّل Firebase:

## الخطوات (10 دقائق)
1. ادخل https://console.firebase.google.com وأنشئ مشروع `AbdulmajeedPharma`.
2. أنشئ **Cloud Firestore** (وضع الإنتاج).
3. من إعدادات المشروع أضف تطبيق Android بحزمة `com.abdulmajeedpharma.pharma_encyclopedia`
   ونزّل `google-services.json` وضعه في `android/app/`.
4. في Firestore أنشئ مجموعتين: `drugs` و `messages` والصق قواعد الأمان التالية:

```text
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /drugs/{id}    { allow read: if true; allow write: if request.auth != null; }
    match /messages/{id} { allow read, create: if true; allow update, delete: if request.auth != null; }
  }
}
```

5. فعّل **Authentication → Email/Password** وأنشئ حساب الإدارة الخاص بك
   (د. عبدالمجيد) — وحده من يعدّل الأدوية ويرد كإدارة للمستخدمين.
6. أضف لحزم Flutter: `firebase_core`, `cloud_firestore`, `firebase_auth`
   وخدمة `SyncService` تقرأ `drugs` و `messages` وتبثّها لواجهة المستخدم
   (نفس نماذج `lib/models/drug_models.dart`).

## بديل دون أي خادم (يعمل الآن)
صدّر من التطبيق أو لوحة الويب ملف `aph-database.json`، ثم:
- ارفعه مكان `assets/data/drugs_seed.json` في GitHub → يُبنى APK محدث تلقائياً.
- أو وزّعه على المستخدمين ليستوردوه من: المزيد ← استيراد قاعدة بيانات.
وهكذا تصل تحديثاتك الجميع دون أي تكلفة خادم.

> ملاحظة: أي قاعدة بيانات عالمية (مليون منتج) لا تأتي جاهزة مجاناً بشكل قانوني؛
> الطريقة الاحترافية المعتمدة هنا: قاعدة بداية حقيقية موثقة المصدر + استيراد
> ملفات CSV/Excel/JSON ضخمة + جلب النشرات الرسمية من openFDA/DailyMed عند الاتصال.
