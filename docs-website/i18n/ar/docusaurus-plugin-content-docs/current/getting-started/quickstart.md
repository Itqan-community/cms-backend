---
sidebar_position: 1
---

# البداية السريعة

يمنحك **Itqan CMS API** بيانات قرآنية موثوقة — قراء، تلاوات، روايات، قراءات، وتوقيتات صوتية على مستوى الآية — من ناشرين معتمدين، عبر واجهة REST/JSON نظيفة.

## طلبك الأول

> **الوقت:** ~30 ثانية. انسخ، الصق، نفّذ — المحتوى العام قابل للقراءة دون مفتاح اليوم. للميزات المعتمدة على الحساب وحدود أعلى، [احصل على مفتاح API](/docs/getting-started/authentication) وأرسله في هيدر `X-API-Key`.

عنوان URL الأساسي: `{{API_BASE}}`

اعرض القراء المتاحين في الفهرس:

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs groupId="language">
<TabItem value="curl" label="curl">

```bash
curl {{API_BASE}}/reciters/
```

</TabItem>
<TabItem value="python" label="Python">

```python
import urllib.request
import json

with urllib.request.urlopen("{{API_BASE}}/reciters/") as resp:
    data = json.load(resp)

print(f"إجمالي القراء: {data['count']}")
for reciter in data["results"]:
    print(f"  {reciter['name']} — {reciter['recitations_count']} تلاوة")
```

</TabItem>
<TabItem value="js" label="JavaScript">

```js
const resp = await fetch("{{API_BASE}}/reciters/");
const { count, results } = await resp.json();

console.log(`إجمالي القراء: ${count}`);
results.forEach((r) => console.log(`  ${r.name} — ${r.recitations_count} تلاوة`));
```

</TabItem>
</Tabs>

**الاستجابة:**

```json
{
  "count": 42,
  "results": [
    {
      "id": 1,
      "name": "مشاري راشد العفاسي",
      "bio": "...",
      "recitations_count": 3
    }
  ]
}
```

هذا تكامل حيّ. تريد العربية بدلاً من ذلك؟ أضف `-H "Accept-Language: ar"` فتعود كل حقول `name` و`description` و`bio` مُوطَّنة.

← مرجع كامل للنقطة: [قائمة القراء](/docs/reference/api/apps-content-api-public-reciters-list-reciters)

## مصمَّم بعناية للمطورين

- **اعرض من طلب واحد.** الموارد المرتبطة مُضمَّنة ككائنات مضغوطة `{id, name}`، فتحمل الاستجابة الواحدة كل ما تحتاجه لعرض عنصر قائمة كامل. ← [الموارد المرتبطة](/docs/guides/related-resources)
- **حقل واحد، أي لغة.** اطلب العربية أو الإنجليزية عبر ترويسة `Accept-Language` — مفاتيح JSON لا تتغير أبداً، تتغير القيم فقط. ← [التوطين](/docs/guides/localization)
- **أشكال ثابتة ومتوقعة.** مسارات بأسماء جمع، وغلاف `{count, results}` متسق، وصيغة أخطاء موحدة تجعل كتابة العملاء سهلة. ← [مبادئ التصميم](/docs/guides/api-design)
- **آمن للبناء عليه.** معرّفات الموارد أعداد صحيحة ثابتة، والـ API يتطور إضافياً — الحقول الجديدة لا تكسر التكاملات القائمة.

## ما التالي؟

- [مرجع الـ API](/docs/reference/api/) — جميع نقاط النهاية مع أمثلة تفاعلية
- [مبادئ التصميم](/docs/guides/api-design) — الاتفاقيات وراء الـ API
- [معالجة الأخطاء](/docs/guides/errors) — بناء عملاء متينين
