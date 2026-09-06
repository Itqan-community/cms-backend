---
sidebar_position: 8
title: التعريف بتطبيقك
description: أرسل اسم تطبيقك ورقم إصداره حتى يمكن تتبّع المشكلات إلى إصدار بعينه.
---

# التعريف بتطبيقك

أخبرنا أي إصدار يُجري الاتصال، وعندها يتوقف تقرير الخطأ عن كونه تخميناً.

## كيف يعمل

أرسل ترويستين اختياريتين مع طلباتك:

| الترويسة | مثال | الغرض |
|---|---|---|
| `X-Client-Name` | `quran-companion` | معرّف ثابت لتطبيقك |
| `X-Client-Version` | `2.4.1` | إصدار تطبيقك الذي يُجري الاتصال |

نُسجّل الاثنتين مع الطلب في نظام تتبّع الأخطاء وتحليلات الاستخدام لدينا. وعند حدوث عطل، نستطيع معرفة أي إصدار من إصداراتك صدرت عنه الطلبات الفاشلة — وتستطيع أنت ذلك أيضاً عند سؤالنا. فإذا ظهر خطأ في `2.4.1` ولم يظهر قط في `2.4.0`، يتّضح ذلك فوراً بدل أسبوع من المراسلات.

كلتا الترويستين اختيارية، ولا تؤثر أي منهما في جسم الاستجابة أو حدّ معدل الطلبات أو المصادقة.

## مثال

```bash
curl https://cms.itqan.dev/recitations/ \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "X-Client-Name: quran-companion" \
  -H "X-Client-Version: 2.4.1"
```

اضبطهما مرة واحدة عند إنشاء عميل HTTP، لا مع كل طلب:

```javascript
const client = axios.create({
  baseURL: 'https://cms.itqan.dev',
  headers: {
    'X-API-Key': process.env.ITQAN_API_KEY,
    'X-Client-Name': 'quran-companion',
    'X-Client-Version': APP_VERSION,
  },
});
```

```python
session = requests.Session()
session.headers.update({
    "X-API-Key": os.environ["ITQAN_API_KEY"],
    "X-Client-Name": "quran-companion",
    "X-Client-Version": __version__,
})
```

## القيم المقبولة

| الترويسة | الطول الأقصى | المحارف المسموحة |
|---|---|---|
| `X-Client-Name` | 64 | `A-Z` `a-z` `0-9` `.` `_` `-` |
| `X-Client-Version` | 32 | `A-Z` `a-z` `0-9` `.` `_` `+` `-` |

تمرّ صيغ الإصدار الدلالي (Semantic Versioning) كما هي، بما فيها بيانات ما قبل الإصدار وبيانات البناء — فـ `2.4.1` و`2.4.1-beta.3` و`2.4.1+build.77` كلها صالحة.

أبقِ `X-Client-Name` ثابتاً عبر الإصدارات. فهو يعرّف التطبيق لا البناء، وتغييره بين الإصدارات يجعل السجل عديم الفائدة.

## عند رفض قيمة

لا تُفشِل الترويسة المشوّهة طلبك أبداً. تُتجاهَل القيمة وتحمل الاستجابة ترويسة `X-Itqan-Warning` تشرح السبب:

```http
HTTP/1.1 200 OK
X-Itqan-Warning: ignored malformed X-Client-Version header; expected at most 32 characters of A-Z a-z 0-9 . _ + -
```

وتبقى بقية الاستجابة كما هي. أما حذف الترويستين تماماً فلا يُنتج أي تحذير — عدم إرسالهما أمر طبيعي.

والسبب الأشيع هو نص إصدار يحوي مسافات أو أقواس، مثل `2.4.1 (nightly)`. أرسل `2.4.1-nightly` بدلاً منه.

:::note
`X-Itqan-Warning` ترويسة خاصة بنا وليست ترويسة `Warning` القياسية التي أهملها [RFC 9111](https://www.rfc-editor.org/rfc/rfc9111#name-warning). وإذا كنت تستدعي الـ API من المتصفح، فهي مكشوفة عبر CORS ليتمكن كود JavaScript لديك من قراءتها.
:::
