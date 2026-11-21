# PROVLAB Strong-Q1 V1.2 — دليل إعادة التشغيل والتعديل للمحكّمين

هذه الحزمة هي Master Source للمخطوطة الحالية. تحتوي الكود، البيانات العامة المضمّنة، cohorts المعالجة، النماذج والنتائج، ملفات freeze، التحليلات Strong-Q1، نسخها المرجعية، ومولدات Word.

## أهم قاعدة
الـconfirmatory freeze يظل تاريخيًا كما هو. لا تعدّل hashes أو locked artifacts لإجبار نتيجة جديدة على PASS. عند طلب Reviewer تحليلًا جديدًا، أنشئ إصدارًا جديدًا تحت `reviewer_requests/` واحتفظ بالقديم والجديد معًا.

## أحدث الكتابة
- `MS_CLEAN.docx` — أحدث clean submission version (V1.2).
- `MS_REVIEW.docx` — أحدث highlighted review version (V1.2).
- النسخ ذات الاسم الإصدار موجودة تحت `publication/strong_q1_v1_2/` و`DELIVERABLES/`.
- مولد V1.2: `tools/build_strong_q1_manuscript_v1_2.py`.

## الكود
- الدراسة الأصلية: `src/` + launchers القديمة.
- تقوية V1.1: `src/run_strong_q1_extension.py`.
- تقوية V1.2: `src/run_strong_q1_stability_extension.py`.
- أدوات البناء والتحقق: `tools/`.

## إعادة الدراسة الأصلية المجمدة
1. فك الحزمة في `C:\Q1` أو مسار قصير مماثل.
2. `00_SETUP_ENVIRONMENT.bat`.
3. على نسخة pristine: `01_VERIFY_PACKAGE.bat`.
4. عند الحاجة: `03_REPRODUCE_SUCCESSFUL_PIPELINE.bat`.
5. بعد إعادة الإنتاج الكامل، استخدم استخراجًا pristine جديدًا إذا أردت فحص hashes الأصلية مرة أخرى، لأن مسار reproduction يعيد توليد working artifacts عمدًا.

## إعادة Strong-Q1 V1.1
1. `04_SETUP_STRONG_Q1_EXTENSION_ENV.bat`.
2. `05_RUN_STRONG_Q1_EXTENSION.bat`.
3. `07_VERIFY_STRONG_Q1_EXTENSION.bat`.

## إعادة Strong-Q1 V1.2
1. بعد إعداد نفس `.venv_strong_q1`، شغّل `08_RUN_STRONG_Q1_STABILITY_EXTENSION.bat`.
2. شغّل `06_BUILD_STRONG_Q1_MANUSCRIPTS.bat` (أو `09_BUILD_STRONG_Q1_MANUSCRIPT_V1_2.bat`).
3. شغّل `10_VERIFY_STRONG_Q1_V1_2.bat`.
4. V1.2 verifier يقارن CSV/JSON الحالي مع `reference/strong_q1_stability_extension/` بتسامح عددي 1e-6، ويطلب وجود النماذج المعاد تدريبها والمخطوطتين.

## ماذا تحتوي V1.2 الجديدة؟
- 200 stratified half-sample resamples لقياس panel-selection stability.
- mean/median Jaccard وNogueira stability وselection frequency.
- Cox survival stability-consensus comparator.
- 3x3 sensitivity grid: direction threshold 0.05/0.10/0.15 × TES mass 0.90/0.925/0.95.
- framing صريح بأن هذه Post-hoc robustness analyses ولا تغيّر confirmatory freeze.

## عند طلب Reviewer تعديلًا
1. احتفظ بهذه الحزمة كمرجع لا يُكتب فوقه.
2. انسخها إلى إصدار جديد.
3. أنشئ `reviewer_requests/R1_XX_DESCRIPTION/`.
4. انسخ `REVIEWER_REVISION_TEMPLATE.md` وسجّل الطلب والتوقيت والملفات المعدلة.
5. أضف سكربت additive جديد كلما أمكن بدل تعديل frozen script.
6. إذا تغيّر protocol، أنشئ amendment قبل تشغيل التحليل.
7. أعد بناء المخطوطة بإصدار جديد واحتفظ بنتائج النسخة المنشورة والنسخة الجديدة.

## البيئة
- الدراسة الأصلية: Windows 64-bit + CPython 3.12؛ runtime snapshot الاختياري يمكن استعادته من أجزاء Q1_RT السابقة.
- Strong-Q1 V1.1/V1.2: `.venv_strong_q1` مبنية من `requirements_strong_q1_extension_exact.txt` (numpy, pandas, scipy, statsmodels, xgboost, python-docx بالإصدارات المثبتة).

## لا تحذف
`data/`, `external_nhanes3/`, `src/`, `tools/`, `outputs/`, `reference/`, `publication/`, `reviewer_requests/`, ملفات `*_FREEZE.*`, `*_MANIFEST.*`, وملفات requirements.
