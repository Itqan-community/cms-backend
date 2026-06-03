---
id: index
title: مرجع الـ API
slug: /reference/api/
sidebar_label: نظرة عامة
sidebar_position: 0
hide_title: false
---

# مرجع الـ API

Quranic CMS API هي واجهة REST لبيانات تلاوات القرآن الكريم — القراء، التلاوات، الروايات، القراءات، وتوقيتات الآيات الصوتية من ناشرين موثَّقين. عنوان URL الأساسي: `{{API_BASE}}`.

## روابط سريعة

| | |
|---|---|
| [البداية السريعة](/docs/getting-started/quickstart) | أجرِ أول استدعاء للـ API في أقل من دقيقة |
| [أدلة الواجهات البرمجية](/docs/guides/api-design) | اتفاقيات التصميم، التصفيح، التوطين، والمزيد |
| [المصادقة](/docs/getting-started/authentication) | نقاط نهاية OAuth 2 للعمليات المتميزة |

## الاتفاقيات

- **هيكل الاستجابة** — [هيكل الاستجابة](/docs/guides/response-structure): جميع واجهات القوائم تُعيد `{count, results}`.
- **التصفيح** — [التصفيح](/docs/guides/pagination): معاملَا `page` و`page_size`، الافتراضي 20، الحد الأقصى 1000.
- **التوطين** — [التوطين](/docs/guides/localization): أرسل `Accept-Language: ar` للنص العربي في جميع حقول الاسم والسيرة.
- **الأخطاء** — [معالجة الأخطاء](/docs/guides/errors): كل استجابة غير 2xx تستخدم `{error_name, message, extra}`.

## مجموعات الموارد

**القراء** — قراء القرآن الموثَّقون مع الاسم والسيرة وعدد التلاوات. ابدأ بـ [قائمة القراء](/docs/reference/api/apps-content-api-public-reciters-list-reciters).

**التلاوات** — سجلات التلاوة الكاملة التي تربط قارئاً ورواية وقراءة وناشراً. تتضمن أعداد المسارات على مستوى السور. ابدأ بـ [قائمة التلاوات](/docs/reference/api/apps-content-api-public-recitation-list-list-recitations).

**مسارات التلاوة** — إدخالات المسار الصوتي على مستوى السورة لتلاوة معينة، بما في ذلك توقيتات الآيات. ابدأ بـ [قائمة مسارات التلاوة](/docs/reference/api/apps-content-api-public-recitation-track-list-list-recitation-tracks).

**الروايات** — سلاسل الرواية (مثل حفص عن عاصم، ورش). ابدأ بـ [قائمة الروايات](/docs/reference/api/apps-content-api-public-riwayahs-list-riwayahs).

**المصادقة** — إصدار التوكنات وإلغاؤها للعمليات المُصادق عليها. راجع [دليل المصادقة](/docs/getting-started/authentication).
