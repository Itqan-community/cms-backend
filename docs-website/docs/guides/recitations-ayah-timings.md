---
sidebar_position: 5
title: Recitations & Ayah Timings
description: How to fetch recitation audio tracks and synchronize ayah-level timings for media playback.
---

# Recitations & Ayah Timings

Sync audio to text at ayah resolution.

## Data Model

```
Recitation (GET /recitations/)
  └─ Surah Tracks (GET /recitations/{id}/)
       └─ Ayah Timings (embedded in each track)
```

A **Recitation** is a complete recorded reading by a specific reciter in a specific narration (riwayah/qiraah). Each recitation has one or more **Surah Tracks** — one per chapter of the Quran. Each track carries an embedded array of **Ayah Timings** that map individual verses to millisecond offsets within the audio file.

## Listing Recitations

`GET /recitations/` returns metadata for all available recitations.

```bash
curl {{API_BASE}}/recitations/
```

```json
{
  "count": 38,
  "results": [
    {
      "id": 7,
      "name": "Hafs an Asim",
      "description": "Complete recitation by Mishary Rashid Alafasy.",
      "publisher": { "id": 3, "name": "Itqan" },
      "reciter": { "id": 12, "name": "Mishary Rashid Alafasy" },
      "riwayah": { "id": 1, "name": "Hafs" },
      "qiraah": { "id": 2, "name": "Asim", "bio": "One of the seven canonical readers." },
      "surahs_count": 114
    }
  ]
}
```

`surahs_count` tells you how many surah tracks are available for this recitation. See [Related Object Embeds](/docs/guides/related-resources) for how the embedded `publisher`, `reciter`, `riwayah`, and `qiraah` objects work.

## Fetching Surah Tracks and Ayah Timings

`GET /recitations/{id}/` returns the list of surah tracks for a given recitation. Each track includes the audio URL and the full array of per-ayah timing data.

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
        { "ayah_key": "1:3", "start_ms": 9800,  "end_ms": 15100, "duration_ms": 5300 },
        { "ayah_key": "1:4", "start_ms": 15100, "end_ms": 20400, "duration_ms": 5300 },
        { "ayah_key": "1:5", "start_ms": 20400, "end_ms": 28500, "duration_ms": 8100 },
        { "ayah_key": "1:6", "start_ms": 28500, "end_ms": 36000, "duration_ms": 7500 },
        { "ayah_key": "1:7", "start_ms": 36000, "end_ms": 47000, "duration_ms": 11000 }
      ]
    }
  ]
}
```

### Surah Track Fields

| Field | Type | Description |
|---|---|---|
| `surah_number` | integer | Quran surah number (1–114) |
| `surah_name` | string | Arabic name of the surah |
| `surah_name_en` | string | Transliterated English name |
| `audio_url` | string | Direct URL to the MP3 audio file |
| `duration_ms` | integer | Total track duration in milliseconds |
| `size_bytes` | integer | Audio file size in bytes |
| `revelation_order` | integer | Order of revelation (1–114) |
| `revelation_place` | string | `"Makkah"` or `"Madinah"` |
| `ayahs_count` | integer | Number of ayat in this surah |
| `ayahs_timings` | array | Per-ayah timing entries (see below) |

### Ayah Timing Fields

| Field | Type | Description |
|---|---|---|
| `ayah_key` | string | `"surah:ayah"` — e.g. `"2:255"` for Ayat al-Kursi |
| `start_ms` | integer | Ayah start offset in milliseconds from track beginning |
| `end_ms` | integer | Ayah end offset in milliseconds |
| `duration_ms` | integer | `end_ms - start_ms` |

Timings within a track are sorted by `ayah_key` (surah number first, then ayah number).

## Worked Example: Ayah-Synchronized Player

The following pseudocode shows how to build a karaoke-style recitation player that highlights the active ayah during playback.

```js
const BASE = "{{API_BASE}}";

async function buildPlayer(recitationId, surahNumber) {
  // 1. Fetch surah tracks (page through if needed)
  const resp = await fetch(`${BASE}/recitations/${recitationId}/`);
  const { results: tracks } = await resp.json();

  const track = tracks.find(t => t.surah_number === surahNumber);
  if (!track) throw new Error("Surah not found in this recitation");

  // 2. Load the audio
  const audio = new Audio(track.audio_url);
  const timings = track.ayahs_timings; // already sorted

  // 3. On each timeupdate, find the active ayah
  audio.addEventListener("timeupdate", () => {
    const posMs = audio.currentTime * 1000;

    const active = timings.findLast(t => t.start_ms <= posMs);
    if (!active) return;

    // 4. Highlight the active ayah in your UI
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

**See also:** [Related Object Embeds](/docs/guides/related-resources) · [Searching, Filtering, Ordering](/docs/guides/search-filter-order) · [API Reference](/docs/reference/api/)
