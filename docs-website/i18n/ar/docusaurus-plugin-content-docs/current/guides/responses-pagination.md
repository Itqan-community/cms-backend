---
sidebar_position: 2
title: غلاف الاستجابة والتصفيح
description: كيفية هيكلة استجابات القوائم المُصفَّحة، وكيفية التنقل بين مجموعات النتائج الكبيرة.
---

# غلاف الاستجابة والتصفيح

## شكل الغلاف

تُعيد جميع واجهات استدعاء القوائم غلافاً متسقاً:

```json
{
  "count": 150,
  "results": [
    { "id": 1, "name": "..." },
    { "id": 2, "name": "..." }
  ]
}
```

| الحقل | النوع | الوصف |
|---|---|---|
| `count` | صحيح | إجمالي عدد السجلات المطابقة عبر جميع الصفحات |
| `results` | مصفوفة | العناصر في الصفحة الحالية |

واجهات الاستدعاء للمورد الواحد (مثلاً `GET /recitations/{id}/`) تُعيد الكائن مباشرة بدون غلاف.

## معاملات التصفيح

| المعامل | النوع | الافتراضي | الحد الأقصى |
|---|---|---|---|
| `page` | صحيح (يبدأ من 1) | `1` | — |
| `page_size` | صحيح | `20` | `1000` |

كلا المعاملين اختياريان. حذفهما يُعيد أول 20 نتيجة.

## التنقل بين الصفحات

استخدم `count` لتحديد عدد الصفحات، ثم زد `page` حتى تحصل على جميع السجلات.

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs groupId="language">
<TabItem value="curl" label="curl">

```bash
# الصفحة الأولى
curl "{{API_BASE}}/reciters/?page=1&page_size=10"

# الصفحة الثانية
curl "{{API_BASE}}/reciters/?page=2&page_size=10"
```

</TabItem>
<TabItem value="python" label="Python">

```python
import urllib.request, urllib.parse, json

BASE = "{{API_BASE}}"
PAGE_SIZE = 50

def fetch_all_reciters():
    results = []
    page = 1
    while True:
        params = urllib.parse.urlencode({"page": page, "page_size": PAGE_SIZE})
        url = f"{BASE}/reciters/?{params}"
        with urllib.request.urlopen(url) as resp:
            body = json.load(resp)
        results.extend(body["results"])
        if len(results) >= body["count"]:
            break
        page += 1
    return results
```

</TabItem>
<TabItem value="js" label="JavaScript">

```js
const BASE = "{{API_BASE}}";
const PAGE_SIZE = 50;

async function fetchAllReciters() {
  const results = [];
  let page = 1;
  while (true) {
    const resp = await fetch(`${BASE}/reciters/?page=${page}&page_size=${PAGE_SIZE}`);
    const { count, results: items } = await resp.json();
    results.push(...items);
    if (results.length >= count) break;
    page++;
  }
  return results;
}
```

</TabItem>
</Tabs>

## أحجام الصفحات الكبيرة

اضبط `page_size=1000` لجلب ما يصل إلى 1000 سجل في طلب واحد. هذا هو الحد الصارم؛ القيم التي تتجاوز 1000 تُخفَّض بصمت إلى 1000.

---

**انظر أيضاً:** [مبادئ التصميم](/docs/guides/api-design) · [البحث والتصفية والترتيب](/docs/guides/search-filter-order) · [معالجة الأخطاء](/docs/guides/errors)
