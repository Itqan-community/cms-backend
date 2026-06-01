---
sidebar_position: 7
title: معالجة الأخطاء
description: غلاف الخطأ الموحّد وكتالوج الأخطاء الكامل وأنماط المعالجة على جانب العميل.
---

# معالجة الأخطاء

كل استجابة غير 2xx من Itqan CMS API تستخدم نفس الغلاف. ابنِ معالجة الأخطاء مرة واحدة وستغطي كل واجهة استدعاء برمجية.

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
| `extra` | كائن أو null | تفاصيل منظمة اختيارية. الشكل يختلف حسب نوع الخطأ (انظر الكتالوج أدناه). |

## كتالوج الأخطاء

| HTTP | `error_name` | المُشغِّل | شكل `extra` |
|---|---|---|---|
| 400 | `validation_error` | معاملات استعلام أو جسم طلب غير صحيح | مصفوفة من كائنات الخطأ على مستوى الحقل |
| 400 | `invalid_json` | جسم طلب JSON مشوَّه | `null` |
| 401 | `authentication_error` | بيانات اعتماد مفقودة أو غير صحيحة | `null` |
| 401 | `token_not_valid` | توكن JWT منتهي الصلاحية أو مُلغى | `null` |
| 403 | `permission_denied` | مُصادَق عليه لكن غير مُخوَّل | `null` |
| 404 | `not_found` | المورد غير موجود | `null` |
| 4xx/5xx | `http_error` | مسار خطأ HTTP عام | `null` |
| 500 | `internal_error` | استثناء خادم غير معالَج | `null` |
| متغير | *(مخصص)* | خطأ منطق أعمال عبر `ItqanError` | خاص بكل نقطة نهاية؛ موثَّق في صفحة المرجع الخاصة بها |

### شكل `extra` لـ `validation_error`

عندما يكون `error_name` هو `validation_error`، يحتوي `extra` على مصفوفة من كائنات الخطأ على مستوى الحقل:

```json
{
  "error_name": "validation_error",
  "message": "Invalid Input",
  "extra": [
    { "loc": ["query", "page"], "msg": "Input should be greater than or equal to 1", "type": "greater_than_equal" }
  ]
}
```

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
    case "not_found":
      return null;
    case "validation_error":
      throw new ValidationError(error.message, error.extra);
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

        if name == "not_found":
            return None
        elif name == "validation_error":
            raise ValueError(f"فشل التحقق: {error['extra']}")
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
