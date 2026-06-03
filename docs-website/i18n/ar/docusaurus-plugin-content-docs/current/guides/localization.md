---
sidebar_position: 3
title: التوطين
description: كيفية طلب المحتوى العربي أو الإنجليزي باستخدام ترويسة Accept-Language.
---

# التوطين

طلب واحد، مفتاح واحد — اللغة تتبع الترويسة.

## كيف يعمل

أرسل ترويسة `Accept-Language` مع كل طلب. يُعيد الـ API نفس بنية JSON مع حقول النص المُحلَّلة تعكس اختيار لغتك. لا توجد مفاتيح منفصلة `name_ar` / `name_en` في الاستجابة — مفتاح `name` يظهر دائماً، وقيمته باللغة المطلوبة.

| قيمة الترويسة | اللغة المُعادة |
|---|---|
| `Accept-Language: en` (الافتراضي) | الإنجليزية |
| `Accept-Language: ar` | العربية |

إذا حُذفت الترويسة أو ضُبطت على لغة غير مدعومة، يعود الـ API إلى الإنجليزية.

## الحقول المُحلَّلة حسب المورد

| المورد | الحقول المُحلَّلة |
|---|---|
| التلاوة | `name`، `description` |
| القارئ | `name`، `bio` |
| الرواية | `name`، `bio` |
| القراءة | `name` |
| الناشر | `name` |

الموارد المرتبطة المدمجة (`publisher.name`، `reciter.name`، إلخ) داخل استجابة التلاوة مُحلَّلة أيضاً — تحصل على أسماء عربية في جميع أنحاء الحمولة بترويسة واحدة.

## مثال

نفس واجهة `/reciters/` مع قيمتين مختلفتين لـ `Accept-Language`:

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs groupId="language">
<TabItem value="curl" label="curl">

```bash
# الإنجليزية (الافتراضي)
curl -H "Accept-Language: en" {{API_BASE}}/reciters/

# العربية
curl -H "Accept-Language: ar" {{API_BASE}}/reciters/
```

</TabItem>
<TabItem value="python" label="Python">

```python
import urllib.request, json

url = "{{API_BASE}}/reciters/"

for lang in ("en", "ar"):
    req = urllib.request.Request(url, headers={"Accept-Language": lang})
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    print(f"[{lang}] اسم أول قارئ: {data['results'][0]['name']}")
```

</TabItem>
<TabItem value="js" label="JavaScript">

```js
const url = "{{API_BASE}}/reciters/";

for (const lang of ["en", "ar"]) {
  const resp = await fetch(url, { headers: { "Accept-Language": lang } });
  const { results } = await resp.json();
  console.log(`[${lang}] اسم أول قارئ: ${results[0].name}`);
}
```

</TabItem>
</Tabs>

**الاستجابة بالإنجليزية:**

```json
{
  "count": 42,
  "results": [
    { "id": 1, "name": "Mishary Rashid Alafasy", "bio": "...", "recitations_count": 5 }
  ]
}
```

**الاستجابة بالعربية:**

```json
{
  "count": 42,
  "results": [
    { "id": 1, "name": "مشاري راشد العفاسي", "bio": "...", "recitations_count": 5 }
  ]
}
```

نفس `id`، نفس البنية — قيم النص فقط تختلف.

---

**انظر أيضاً:** [مبادئ التصميم](/docs/guides/api-design) · [تضمين الكائنات المرتبطة](/docs/guides/related-resources) · [معالجة الأخطاء](/docs/guides/errors)
