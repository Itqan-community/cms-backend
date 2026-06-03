---
sidebar_position: 6
title: البحث والتصفية والترتيب
description: كيفية البحث وتصفية وترتيب النتائج عبر واجهات Itqan CMS API.
---

# البحث والتصفية والترتيب

ثلاثة قوالب استعلام تتحكم فيما تحصل عليه وبأي ترتيب. يمكن دمج الثلاثة في طلب واحد.

## البحث (`search=`)

بحث نصي حر عبر الاسم والوصف وأسماء الموارد المرتبطة (بالعربية والإنجليزية). المطابقة لا تراعي حالة الأحرف وتبحث عن السجلات التي تحتوي على المصطلح.

```bash
curl "{{API_BASE}}/recitations/?search=مشاري"
```

على `/recitations/`، يُطابق المعامل `search` مع:
- `name`
- `description`
- `publisher.name`
- `reciter.name` (عربي وإنجليزي)
- `riwayah.name` (عربي وإنجليزي)
- `qiraah.name` (عربي وإنجليزي)

الكلمات المتعددة تُطابَق بمنطق AND — `search=حفص+عاصم` يُعيد السجلات التي تطابق كلاً من "حفص" و"عاصم".

## التصفية

تُظهر نقاط النهاية معاملات تصفية خاصة بكل مورد. جميعها تقبل قيماً متعددة (OR منطقي).

### التلاوات (`/recitations/`)

| المعامل | النوع | الوصف |
|---|---|---|
| `publisher_id` | صحيح (قابل للتكرار) | تصفية حسب معرّف الناشر |
| `reciter_id` | صحيح (قابل للتكرار) | تصفية حسب معرّف القارئ |
| `riwayah_id` | صحيح (قابل للتكرار) | تصفية حسب معرّف الرواية |
| `qiraah_id` | صحيح (قابل للتكرار) | تصفية حسب معرّف القراءة |

مرر المعامل عدة مرات لمطابقة أي من القيم (منطق OR):

```bash
# تلاوات القارئ 12 أو القارئ 15
curl "{{API_BASE}}/recitations/?reciter_id=12&reciter_id=15"
```

## الترتيب (`ordering=`)

رتّب النتائج حسب حقل واحد أو أكثر. أضف `-` قبل اسم الحقل للترتيب التنازلي. افصل الحقول المتعددة بفاصلة.

### التلاوات (`/recitations/`)

الحقول المسموح بها: `name`، `created_at`، `updated_at`

```bash
# أبجدياً حسب الاسم (تصاعدي)
curl "{{API_BASE}}/recitations/?ordering=name"

# الأحدث تحديثاً أولاً
curl "{{API_BASE}}/recitations/?ordering=-updated_at"
```

### القراء (`/reciters/`) والروايات (`/riwayahs/`)

الحقل المسموح به: `name`

```bash
curl "{{API_BASE}}/reciters/?ordering=-name"
```

## دمج الثلاثة

```bash
curl "{{API_BASE}}/recitations/\
?search=حفص\
&publisher_id=3\
&reciter_id=12\
&ordering=-created_at\
&page=1\
&page_size=20"
```

يُعيد هذا تلاوات تطابق "حفص"، نشرها الناشر 3، للقارئ 12، مرتبة بالأحدث أولاً، الصفحة 1.

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs groupId="language">
<TabItem value="python" label="Python">

```python
import urllib.request, urllib.parse, json

params = urllib.parse.urlencode({
    "search": "حفص",
    "publisher_id": 3,
    "reciter_id": 12,
    "ordering": "-created_at",
    "page": 1,
    "page_size": 20,
})
url = f"{{API_BASE}}/recitations/?{params}"

with urllib.request.urlopen(url) as resp:
    data = json.load(resp)

print(f"{data['count']} تلاوات مطابقة")
for r in data["results"]:
    print(f"  [{r['id']}] {r['name']}")
```

</TabItem>
<TabItem value="js" label="JavaScript">

```js
const params = new URLSearchParams({
  search: "حفص",
  publisher_id: 3,
  reciter_id: 12,
  ordering: "-created_at",
  page: 1,
  page_size: 20,
});
const resp = await fetch(`{{API_BASE}}/recitations/?${params}`);
const { count, results } = await resp.json();

console.log(`${count} تلاوات مطابقة`);
results.forEach(r => console.log(`  [${r.id}] ${r.name}`));
```

</TabItem>
</Tabs>

---

**انظر أيضاً:** [التصفيح](/docs/guides/pagination) · [تضمين الكائنات المرتبطة](/docs/guides/related-resources) · [مرجع الـ API](/docs/reference/api/)
