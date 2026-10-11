# Bulgaria — legislation as Markdown (LawCodex)

Consolidated texts (*актуална редакция*, the current version in force) of Bulgarian legislation,
converted to Markdown, one file per act, in Bulgarian (Cyrillic).

Retrieved: **2026-10-12** (the consolidation date of each act is in its `last_amended` /
`version_in_force_from` front-matter fields).

## Source — and why it is not official

**Bulgaria has no official consolidated-legislation database.** The only official publication
is the State Gazette (*Държавен вестник*, https://dv.parliament.bg), which publishes acts and
their amending acts as adopted; consolidation is done by private legal publishers (АПИС, Сиела,
Лакорда/lex.bg).

This corpus is taken from **АПИС — https://legislation.apis.bg**, the free public
consolidated-legislation portal of the legal publisher **АПИС ЕООД** (APIS), via the JSON API
the portal itself uses (`https://web-api.apis.bg/api/obshtina-legislation/`). The texts are
**unofficial consolidations**; for legal certainty consult the State Gazette.

Sources evaluated and not used:

| Source | Why not used |
|---|---|
| State Gazette, https://dv.parliament.bg (official) | publishes original and amending acts only, no consolidated texts |
| National Assembly, https://www.parliament.bg (official) | laws as adopted (mostly amending acts), no consolidated texts |
| lex.bg (free, unofficial) | every request (incl. robots.txt) answered with a Cloudflare "managed challenge" (HTTP 403); not circumvented |
| Ciela "Свободна зона" (ciela.net, free, unofficial) | `robots.txt` disallows all crawlers except search engines |
| N-Lex (EU) Bulgarian search | State Gazette search; returned no results |

`legislation.apis.bg` and `web-api.apis.bg` publish no `robots.txt` restrictions (no
Crawl-delay); the fetcher nevertheless uses ≤ 2 concurrent requests with a 0.5 s pause.

## Coverage

Everything the free APIS portal lists in its five top-level folders (all documents flagged as
current, `isActual = 1`):

| Directory | Contents | Files |
|---|---|---:|
| `konstitutsiya/` | Конституция на Република България (1991, as amended to 2023 and Constitutional Court decision 13/2024) | 1 |
| `kodeksi/` | кодекси — the statutory codes (НК, НПК, ГПК, АПК, ДОПК, Кодекс на труда, КСО, Семеен кодекс, Изборен кодекс, Кодекс за застраховането, КМЧП, КТК) plus the other "codes" APIS files in this folder (professional ethics codes, IMO maritime codes published in the State Gazette) | 33 |
| `zakoni/<year>/` | закони — all laws in force (other than ratification laws), including ЗЗД, Търговски закон, ЗДДС, Закон за собствеността, Закон за наследството, Закон за лицата и семейството, budget laws, … | 420 |
| `ratifikatsii/<year>/` | закони за ратифициране и денонсиране — laws ratifying/denouncing international treaties (the law's text; treaty texts are included only where APIS includes them) | 1,567 |
| `pravilnitsi/<year>/` | правилници — implementing and organisational regulations (правилници за прилагане, устройствени правилници, …) | 538 |
| **Total** | | **2,559** |

`<year>` is the year of the original promulgation in the State Gazette.

## Not covered

- **Наредби** (ordinances), постановления and other secondary legislation: the free APIS portal
  does not expose them (they are only in the paid APIS product). No free source with a
  machine-readable consolidated text of ordinances was found (see table above).
- Repealed acts, historical versions, amending acts as separate documents (their content is
  merged into the consolidated text of the amended act; the transitional and final provisions
  of amending acts are kept at the end of each act, as APIS publishes them).
- Case law, Constitutional Court decisions, EU law, municipal ordinances.
- Images in annexes are not copied: they are linked to `https://legislation.apis.bg/pi/…`.
- Hyperlinks between acts (APIS cross-references) are reduced to plain text.

## Format and structure

```
konstitutsiya/konstitutsia-na-republika-balgaria.md
kodeksi/nakazatelen-kodeks.md
zakoni/2006/zakon-za-danak-varhu-dobavenata-stoynost.md
ratifikatsii/2016/zakon-za-ratifitsirane-na-konventsiyata-za-....md
pravilnitsi/2019/pravilnik-za-ustroystvoto-i-deynostta-na-....md
```

- File names are the act title transliterated with the official Bulgarian system
  (Закон за транслитерацията, 2009), lowercased and slugified (max ~90 characters); title
  notes such as "(Загл. изм. …)" are dropped. On a collision the APIS id is appended.
- Front matter: `title` (Bulgarian title as published by APIS), `identifier` (original State
  Gazette publication, e.g. `ДВ, бр. 56 от 13.07.1991 г.`), `type`
  (`constitution`/`code`/`act`/`regulation`), `date` (original promulgation date),
  `last_amended` (State Gazette date of the latest amendment included),
  `version_in_force_from`, `in_force_until` (only if a repeal date is already fixed),
  `status`, `source` (APIS URL), `apis_id`, `retrieved`.
- Body: the publication/amendment history line (*Обн., ДВ, бр. …, изм. …*), then the
  structure: parts (Част), divisions (Дял), chapters (Глава), sections (Раздел, Подраздел) and
  unnumbered sub-headings as Markdown headings, with levels assigned per act; articles
  (`Чл.`) and paragraphs of the supplementary/transitional provisions (`§`) as the deepest
  heading level (bold labels if the hierarchy would exceed `######`). Article titles, where
  present, follow the article heading in italics. Amendment notes such as
  "(Изм. – ДВ, бр. … от … г.)" are kept verbatim.
- Annexes (*Приложение*) are level-2 headings; simple tables become Markdown tables, tables with
  merged cells are kept as minimal HTML.

## Licence

Under Art. 4, item 1 of the Bulgarian Copyright and Neighbouring Rights Act (*Закон за
авторското право и сродните му права*), normative acts and official translations of them are
not subject to copyright. The consolidation and markup are APIS's work; only the legal text
is reproduced here, without APIS's annotations or cross-reference links.

## Regenerating

```sh
python3 -m pip install -r scripts/requirements.txt
python3 scripts/bg_fetch.py            # downloads lists + texts to ../_raw/bg (cached, incremental)
python3 scripts/bg_convert.py          # writes the Markdown tree into this repository
```

`bg_fetch.py` re-downloads a document only when APIS reports a newer publication date.
