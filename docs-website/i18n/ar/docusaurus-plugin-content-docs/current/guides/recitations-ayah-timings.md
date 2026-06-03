---
sidebar_position: 5
title: التلاوات وتوقيتات الآيات
description: كيفية جلب مسارات صوت التلاوة ومزامنة توقيتات الآيات لتشغيل الوسائط.
---

# التلاوات وتوقيتات الآيات

زامن الصوت مع النص على مستوى الآية.

## نموذج البيانات

```
التلاوة (GET /recitations/)
  └─ مسارات السور (GET /recitations/{id}/)
       └─ توقيتات الآيات (مدمجة في كل مسار)
```

**التلاوة** هي قراءة مسجلة كاملة لقارئ محدد برواية/قراءة محددة. لكل تلاوة مسار سورة واحد أو أكثر — واحد لكل سورة من سور القرآن الكريم. يحمل كل مسار مصفوفة مدمجة من **توقيتات الآيات** التي تُعيّن الآيات الفردية إلى إزاحات المللي ثانية داخل الملف الصوتي.

## قائمة التلاوات

`GET /recitations/` يُعيد بيانات وصفية لجميع التلاوات المتاحة.

```bash
curl {{API_BASE}}/recitations/
```

```json
{
  "count": 38,
  "results": [
    {
      "id": 7,
      "name": "حفص عن عاصم",
      "description": "تلاوة كاملة لمشاري راشد العفاسي.",
      "publisher": { "id": 3, "name": "إتقان" },
      "reciter": { "id": 12, "name": "مشاري راشد العفاسي" },
      "riwayah": { "id": 1, "name": "حفص" },
      "qiraah": { "id": 2, "name": "عاصم", "bio": "أحد القراء السبعة المعتمدين." },
      "surahs_count": 114
    }
  ]
}
```

`surahs_count` يُخبرك بعدد مسارات السور المتاحة لهذه التلاوة. راجع [تضمين الكائنات المرتبطة](/docs/guides/related-resources) لفهم كيفية عمل كائنات `publisher` و`reciter` و`riwayah` و`qiraah` المدمجة.

## جلب مسارات السور وتوقيتات الآيات

`GET /recitations/{id}/` يُعيد قائمة مسارات السور لتلاوة معينة. يتضمن كل مسار URL الصوت والمصفوفة الكاملة لبيانات توقيت كل آية.

```bash
curl {{API_BASE}}/recitations/7/
```

```json
{
  "count": 114,
  "results": [
    {
      "surah_number": 1,
      "surah_name": "الفاتحة",
      "surah_name_en": "Al-Fatihah",
      "audio_url": "https://cdn.example.com/media/recitations/7/001.mp3",
      "duration_ms": 47000,
      "size_bytes": 752640,
      "revelation_order": 5,
      "revelation_place": "Makkah",
      "ayahs_count": 7,
      "ayahs_timings": [
        { "ayah_key": "1:1", "start_ms": 0,     "end_ms": 4200,  "duration_ms": 4200 },
        { "ayah_key": "1:2", "start_ms": 4200,  "end_ms": 9800,  "duration_ms": 5600 },
        { "ayah_key": "1:7", "start_ms": 36000, "end_ms": 47000, "duration_ms": 11000 }
      ]
    }
  ]
}
```

### حقول مسار السورة

| الحقل | النوع | الوصف |
|---|---|---|
| `surah_number` | صحيح | رقم السورة في القرآن (1–114) |
| `surah_name` | نص | الاسم العربي للسورة |
| `surah_name_en` | نص | الاسم المُترجَم إلى الإنجليزية |
| `audio_url` | نص | رابط مباشر لملف MP3 الصوتي |
| `duration_ms` | صحيح | مدة المسار الكاملة بالمللي ثانية |
| `size_bytes` | صحيح | حجم الملف الصوتي بالبايت |
| `revelation_order` | صحيح | ترتيب النزول (1–114) |
| `revelation_place` | نص | `"Makkah"` أو `"Madinah"` |
| `ayahs_count` | صحيح | عدد الآيات في هذه السورة |
| `ayahs_timings` | مصفوفة | إدخالات التوقيت لكل آية (انظر أدناه) |

### حقول توقيت الآية

| الحقل | النوع | الوصف |
|---|---|---|
| `ayah_key` | نص | `"سورة:آية"` — مثلاً `"2:255"` لآية الكرسي |
| `start_ms` | صحيح | إزاحة بداية الآية بالمللي ثانية من بداية المسار |
| `end_ms` | صحيح | إزاحة نهاية الآية بالمللي ثانية |
| `duration_ms` | صحيح | `end_ms - start_ms` |

التوقيتات داخل المسار مُرتَّبة حسب `ayah_key` (رقم السورة أولاً، ثم رقم الآية).

## مثال عملي: مشغّل متزامن مع الآيات

الكود الوهمي التالي يُظهر كيفية بناء مشغّل تلاوة يُبرز الآية النشطة أثناء التشغيل.

```js
const BASE = "{{API_BASE}}";

async function buildPlayer(recitationId, surahNumber) {
  // 1. جلب مسارات السور
  const resp = await fetch(`${BASE}/recitations/${recitationId}/`);
  const { results: tracks } = await resp.json();

  const track = tracks.find(t => t.surah_number === surahNumber);
  if (!track) throw new Error("السورة غير موجودة في هذه التلاوة");

  // 2. تحميل الصوت
  const audio = new Audio(track.audio_url);
  const timings = track.ayahs_timings; // مُرتَّبة مسبقاً

  // 3. عند كل تحديث للوقت، ابحث عن الآية النشطة
  audio.addEventListener("timeupdate", () => {
    const posMs = audio.currentTime * 1000;
    const active = timings.findLast(t => t.start_ms <= posMs);
    if (!active) return;

    // 4. أبرز الآية النشطة في واجهتك
    highlightAyah(active.ayah_key);
  });

  return audio;
}

function highlightAyah(ayahKey) {
  document.querySelectorAll("[data-ayah]").forEach(el => {
    el.classList.toggle("active", el.dataset.ayah === ayahKey);
  });
}
```

---

**انظر أيضاً:** [تضمين الكائنات المرتبطة](/docs/guides/related-resources) · [البحث والتصفية والترتيب](/docs/guides/search-filter-order) · [مرجع الـ API](/docs/reference/api/)
