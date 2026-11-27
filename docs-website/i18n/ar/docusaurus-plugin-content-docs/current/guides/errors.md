---
sidebar_position: 7
title: معالجة الأخطاء
description: غلاف الخطأ الموحّد وكتالوج الأخطاء الكامل وأنماط المعالجة على جانب العميل.
---

# معالجة الأخطاء

كل استجابة غير 2xx من Fanar API تستخدم نفس الغلاف. ابنِ معالجة الأخطاء مرة واحدة وستغطي كل واجهة استدعاء برمجية.

## غلاف الخطأ

```json
{
  "error_name": "not_found",
  "message": "No asset matches the given query.",
  "extra": null
}
```

| الحقل | النوع | الوصف |
|---|---|---|
| `error_name` | نص | **معرّف آلي ثابت.** قم بتحويل معالجة الأخطاء بناءً عليه، ليس على `message` أو حالة HTTP. لا يحتوي على مسافات. |
| `message` | نص | وصف قابل للقراءة البشرية. مُحلَّل عبر `Accept-Language` — آمن للعرض مباشرة للمستخدمين. |
| `extra` | كائن أو مصفوفة أو null | تفاصيل منظمة اختيارية. الشكل يختلف حسب نوع الخطأ (انظر الكتالوج أدناه). تكون `null` كلما لم يكن للخطأ تفاصيل، ولا تكون كائناً فارغاً أبداً. |

## كتالوج الأخطاء

| HTTP | `error_name` | المُشغِّل | شكل `extra` |
|---|---|---|---|
| 400 | `validation_error` | معاملات استعلام أو جسم طلب غير صحيح، أو قيم لا تستقيم معًا (مثل نطاق آيات يأتي فيه `from` بعد `to`). أخطاء التحقق تستخدم `400` دائمًا | مصفوفة من كائنات الخطأ على مستوى الحقل، أو `null` |
| 400 | `invalid_external_user_id` | ترويسة `X-External-User-Id` فارغة أو طويلة جدًا أو تشبه بيانات شخصية أو تحتوي أحرفًا غير صالحة | `null` |
| 400 | `invalid_json` | جسم طلب JSON مشوَّه | `null` |
| 401 | `authentication_error` | بيانات اعتماد مفقودة أو غير صحيحة | `null` |
| 401 | `invalid_api_key` | ترويسة `X-API-Key` تحمل مفتاحاً غير موجود أو مُلغى أو منتهي الصلاحية. الطلبات التي لا ترسل الترويسة لا تتأثر | `null` |
| 401 | `token_not_valid` | توكن JWT منتهي الصلاحية أو مُلغى | `null` |
| 403 | `permission_denied` | مُصادَق عليه لكن غير مُخوَّل | `null` |
| 404 | `asset_not_found` | الأصل المذكور في المسار غير موجود أو غير متاح عبر الواجهة | `null` |
| 404 | `not_found` | أي مورد آخر غير موجود | `null` |
| 423 | `publisher_closed` | الطلب يذكر نطاق ناشر (في `Origin` أو `X-Tenant`) مغلقًا للصيانة | `null` |
| 4xx/5xx | `http_error` | مسار خطأ HTTP عام | `null` |
| 500 | `internal_error` | استثناء خادم غير معالَج | `null` |
| متغير | *(مخصص)* | خطأ منطق أعمال عبر `ItqanError` | خاص بكل نقطة نهاية؛ موثَّق في صفحة المرجع الخاصة بها |

### شكل `extra` لـ `validation_error`

يختلف شكل `extra` باختلاف سبب الخطأ، فتحقّق من نوعه قبل قراءته:

- **معامل أو حقل غير صحيح**: مصفوفة من كائنات الخطأ على مستوى الحقل، كائن لكل معامل أو حقل غير صحيح:

```json
{
  "error_name": "validation_error",
  "message": "Invalid Input",
  "extra": [
    { "loc": ["query", "page"], "msg": "Input should be greater than or equal to 1", "type": "greater_than_equal" }
  ]
}
```

- **قيم لا تستقيم معًا**: `null`. كل قيمة صحيحة بمفردها، ويبيّن `message` موضع الخطأ:

```json
{
  "error_name": "validation_error",
  "message": "نطاق الآيات غير صالح: من (5) يجب ألا تتجاوز إلى (3).",
  "extra": null
}
```

اعرض `message` في الحالتين، ولا تقرأ أخطاء الحقول من `extra` إلا إذا كان مصفوفة.

### رموز «غير موجود»

يسمّي الخطأ 404 الشيء المفقود:

- `asset_not_found`: الأصل المذكور في المسار (بالمعرّف أو بالاسم المختصر slug) غير موجود، أو غير متاح عبر الواجهة، أو ليس له إصدار منشور. كل نقاط النهاية تستخدم هذا الاسم لهذه الحالة.
- اسم أدق حين يكون الأصل موجودًا وجزء منه مفقودًا: `track_not_found` (لا يوجد مسار صوتي لهذه السورة)، `quality_not_found`، `ayah_not_found`، `language_not_found`، `version_not_found`.
- `not_found` لأي شيء آخر.

## معالجة جانب العميل

قم بالتحويل بناءً على `error_name`. لا تُحوِّل بناءً على `message` (يتغير مع اللغة) أو على حالة HTTP وحدها (معرّفات أخطاء متعددة تشترك في نفس حالة HTTP).

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs groupId="language">
<TabItem value="js" label="JavaScript">

```js
async function apiFetch(url, options = {}) {
  const resp = await fetch(url, options);
  if (resp.ok) return resp.json();

  const error = await resp.json();

  switch (error.error_name) {
    case "asset_not_found":
    case "not_found":
      return null;
    case "validation_error":
      // اعرض message دائمًا؛ extra إما قائمة بأخطاء الحقول أو null
      throw new ValidationError(error.message, Array.isArray(error.extra) ? error.extra : []);
    case "authentication_error":
    case "token_not_valid":
      redirectToLogin();
      return;
    case "internal_error":
      throw new RetryableError(error.message);
    default:
      throw new Error(error.message);
  }
}
```

</TabItem>
<TabItem value="python" label="Python">

```python
import urllib.request, urllib.error, json

def api_fetch(url):
    try:
        with urllib.request.urlopen(url) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        error = json.load(e)
        name = error.get("error_name")

        if name in ("asset_not_found", "not_found"):
            return None
        elif name == "validation_error":
            # احتفظ بـ message دائمًا؛ extra إما قائمة بأخطاء الحقول أو null
            fields = error["extra"] if isinstance(error.get("extra"), list) else []
            raise ValueError(f"فشل التحقق: {error['message']}", fields)
        elif name in ("authentication_error", "token_not_valid"):
            raise PermissionError("المصادقة مطلوبة")
        elif name == "internal_error":
            raise RuntimeError("خطأ في الخادم — أعد المحاولة مع تأخير")
        else:
            raise RuntimeError(error["message"])
```

</TabItem>
</Tabs>

### القواعد الأساسية

- **قم بالتحويل بناءً على `error_name`**، ليس على `message` أو حالة HTTP.
- **اعرض `message` للمستخدمين** — إنه مُحلَّل مسبقاً عبر `Accept-Language`.
- **تعامل مع `error_name` غير المعروف كـ `internal_error`** — قد يضيف الـ API أسماء أخطاء جديدة؛ عميلك يجب ألا يتعطل بسببها.
- **أعد المحاولة مع تأخير عند 5xx فقط** — أخطاء 4xx هي أخطاء عميل ولن تُحل بإعادة المحاولة.

## أخطاء واجهات الاستدعاء المخصصة

بعض واجهات الاستدعاء البرمجية تُثير `ItqanError` لحالات منطق الأعمال (مثلاً، تعارض أو فشل تحقق من النطاق). تُنتج هذه `error_name` مخصصاً لتلك الواجهة. توثّق كل صفحة مرجع واجهة الاستدعاء البرمجية أسماء الأخطاء المخصصة التي يمكن أن تُعيدها.

---

**انظر أيضاً:** [مبادئ التصميم](/docs/guides/api-design) · [مرجع الـ API](/docs/reference/api/) · [المصادقة](/docs/getting-started/authentication)
