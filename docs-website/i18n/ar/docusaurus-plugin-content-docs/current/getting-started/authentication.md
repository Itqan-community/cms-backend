---
sidebar_position: 2
---

# المصادقة

تستخدم واجهات Itqan **مفتاح API** للتعرّف على تطبيقك. نقاط القراءة العامة تعمل حاليًا دون مفتاح، لكننا ننصح بإنشاء مفتاح الآن — فهو يفتح الميزات المعتمدة على الحساب، وحدود استخدام أعلى، ويُبقي تكاملك جاهزًا مع توسّع المصادقة.

## احصل على مفتاح API

1. سجّل الدخول إلى مكتبة الأصول على **[cms.itqan.dev](https://cms.itqan.dev)**.
2. افتح إعدادات حسابك وانتقل إلى **مفاتيح API**.
3. أنشئ مفتاحًا، وأعطه اسمًا وصفيًا (مثل `my-recitation-app`)، وانسخه.

> **خزّنه بأمان.** تعامل مع المفتاح كأنه كلمة مرور — احفظه في متغيّر بيئة أو مدير أسرار، ولا تضعه أبدًا في نظام التحكم بالمصادر أو في كود يعمل على جهة العميل.

## أرسل المفتاح

مرّر مفتاحك في كل طلب عبر ترويسة `X-API-Key`:

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs groupId="language">
<TabItem value="curl" label="curl">

```bash
curl {{API_BASE}}/reciters/ \
  -H "X-API-Key: YOUR_API_KEY"
```

</TabItem>
<TabItem value="python" label="Python">

```python
import urllib.request
import json

req = urllib.request.Request(
    "{{API_BASE}}/reciters/",
    headers={"X-API-Key": "YOUR_API_KEY"},
)
with urllib.request.urlopen(req) as resp:
    data = json.load(resp)

print(f"إجمالي القراء: {data['count']}")
```

</TabItem>
<TabItem value="js" label="JavaScript">

```js
const resp = await fetch("{{API_BASE}}/reciters/", {
  headers: { "X-API-Key": "YOUR_API_KEY" },
});
const { count, results } = await resp.json();

console.log(`إجمالي القراء: ${count}`);
```

</TabItem>
</Tabs>

## الأخطاء

المفتاح المفقود أو غير الصالح يعيد خطأً بـ[صيغة الأخطاء الموحدة](/docs/guides/errors):

| الحالة | المعنى | الحل |
|--------|--------|------|
| `401 Unauthorized` | المفتاح مفقود أو بصيغة خاطئة | أضف ترويسة `X-API-Key` صالحة |
| `403 Forbidden` | المفتاح صالح لكنه غير مسموح لهذا المورد | راجع صلاحيات المفتاح في مكتبة الأصول |

تستمر التكاملات الحالية مع نقاط القراءة العامة في العمل دون انقطاع أثناء التطبيق التدريجي لاشتراط المفتاح.

---

**انظر أيضاً:** [البداية السريعة](/docs/getting-started/quickstart) · [معالجة الأخطاء](/docs/guides/errors)
