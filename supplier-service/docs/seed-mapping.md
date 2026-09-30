# Supplier seed mapping

Reviewed with the user on 26 September 2026. This specifies the future importer;
no CSV changes, generated manifest UUIDs, asset copies, or database writes are
part of this documentation increment. The CSV is primarily a one-time initial
source, but importing it again must remain safe.

## Source and field mapping

Read root `data/csv/supplier-seed-data.csv` with explicit CP1252 encoding and
`csv.DictReader`, opening with `newline=""`. The inspected source has 21 rows,
10 columns, six nonblank image references, and five Food/Coffee entries.
Expected category assignments: Food 16, Coffee 5, Shopping 3, Printing 2;
26 assignments in total across four controlled categories.

| Source column | Destination and rule |
| --- | --- |
| Name | name; trim surrounding whitespace, preserve spelling/capitalization |
| Type | Split on `/`, trim, resolve controlled category names to IDs |
| Building | building; trim and apply reviewed aliases below |
| Floor | floor; keep text, including future basement labels |
| Location Description | description; trim; blank becomes null |
| Latitude | location.latitude; parse finite number, validate latitude range |
| Longitude | location.longitude; parse finite number, validate longitude range |
| StartingTime | opening_time; parse HHMMhrs as a local daily time |
| ClosingTime | closing_time; parse HHMMhrs, then apply reviewed exceptions |
| ImageURL | Match the six known references to image keys; blank becomes null |

Normalize absent optional text to null. Construct PostGIS points longitude
first, latitude second. Retain source coordinates without rounding or guessed
corrections. The source lacks area, UUID, timestamps, version, and day offset;
area comes from the reviewed mapping, UUID from the manifest, timestamps and
version from creation, and offset from the resulting pair of times.

## Buildings and reviewed areas

Normalize Com 2 and Com2 to COM2, and Prince George’s Park to Prince George's
Park. Preserve other building labels after trimming. These aliases do not
rewrite supplier display names: Printer @ Com 2 retains that name.

The following table accounts for every source supplier. Ordinals are for
review only and must never become importer identities. Areas are user-reviewed
browsing groupings, not claims inferred from geographic coordinates. All current
rows can use a building mapping; future ambiguous buildings require explicit
seed-key overrides rather than guessing.

| Supplier | Normalized building | Area |
| --- | --- | --- |
| Anna's x Soup Union | Central Library | FASS |
| NUS Co-op | Central Library | FASS |
| Printer @ Com 2 | COM2 | SoC |
| Cool Spot | COM2 | SoC |
| InstaChef | Terrace | SoC |
| Cafe+ Robot Cafe | Central Library | FASS |
| A Hot Hideout | Prince George's Park | PGP |
| Arise and Shine | Engineering Block E4 | Engineering |
| Bakehaus / Aurea | The Ridge | SoC |
| Central Square @ YIH | Yusof Ishak House | YIH |
| Pasta Express | Frontier | Science |
| TOMORO COFFEE | Hon Sui Sen Memorial Library | BIZ |
| Octobox | Prince George's Park | PGP |
| Smooy | COM3 | SoC |
| Goh Bros E-Print Pte Ltd | Yusof Ishak House | YIH |
| Cheers Unmanned Convenience Store | Engineering Block E3 | Engineering |
| Nami | innovation4.0 | BIZ |
| Supersnacks | Prince George's Park | PGP |
| Good Day Cafe | Medicine+Science Library | Science |
| The Coffee Roaster | Blk AS8 | FASS |
| he by He Brews | Engineering Block EA | Engineering |

## Daily hours and reviewed corrections

All schedules apply every day, Monday–Sunday, in Asia/Singapore. This is an
explicit assumption because the source has no weekday information.
Supersnacks keeps 11:00–02:00 and derives closing_day_offset 1.

The user confirmed that these five source 0000hrs–2359hrs schedules mean
24-hour opening. For these records only, convert the parsed times to
00:00–00:00 and derive offset 1:

- Printer @ Com 2
- InstaChef
- Cafe+ Robot Cafe
- Octobox
- Cheers Unmanned Convenience Store

Represent these exceptions by permanent seed key in the future manifest or
associated reviewed mapping. Do not globally convert every 23:59 closing time.
The source CSV stays unchanged. Literal 00:00–23:59 is 23 hours 59 minutes;
conversion is justified by this review, not inferred from the time format.

After applying exceptions, use the shared rule: closing equal to or before
opening derives 1, otherwise 0. Both times absent produce unknown hours and
null offset; only one absent is invalid. Existing rows all have populated hours.

## Image mapping and deployment

Keep the source files in root data/images/. During asset integration, copy
the six files into frontend-service/public/images/suppliers/ and bundle them
in the frontend container. Its existing Dockerfile copies public into the
runtime image. No shared volume or extra image-serving container is required.

| Supplier | Source filename / image_key |
| --- | --- |
| Anna's x Soup Union | ANNA.jpeg |
| NUS Co-op | NUS_COOP.jpeg |
| Printer @ Com 2 | PRINTER_COM2.jpeg |
| Cool Spot | COOL_SPOT.jpeg |
| InstaChef | INSTACHEF.jpeg |
| Cafe+ Robot Cafe | ROBOT_CAFE.jpeg |

Map the known CSV GitHub blob references explicitly to these files; do not
fetch arbitrary URLs or use GitHub HTML pages as image delivery URLs. The other
15 suppliers have null image_key. Reject unknown nonblank references for review.

Supplier Service stores and returns the filename key only. The frontend maps
ANNA.jpeg to /images/suppliers/ANNA.jpeg on its own origin, locally
http://localhost:3000/images/suppliers/ANNA.jpeg. Null displays a placeholder.
Updating bundled images requires rebuilding the frontend container. Runtime
uploads and external object storage are outside the initial implementation.

## Permanent seed identities and explicit review

When implementing parsing, author seed/manifest.json with a permanent seed_key,
a random supplier_id generated once, and source_match containing Name and
Building. Use normalized name/building pairs to locate source rows: trim names
while preserving case/spelling, and apply the reviewed building aliases. This
matching is separate from lowercase duplicate detection in the database.
Require exactly one source row per manifest entry and one manifest entry per
source row. Row order is never an identity; never generate new UUIDs each run.

Illustrative shape (replace the UUID placeholder when authoring the manifest):

```json
{
  "seed_key": "supplier-001",
  "supplier_id": "<generate-once>",
  "source_match": {
    "Name": "Anna's x Soup Union",
    "Building": "Central Library"
  }
}
```

If a name/building changes beyond normalization, reject the unmatched source
and require explicit review. Update the association while keeping the seed key
and UUID when confirmed to be the same supplier. Do not guess from coordinates:
Anna's and Cafe+ Robot Cafe share a point. A reviewed source change does not
update an existing database supplier; existing seed UUIDs are skipped, including
deleted records, preserving later edits and category assignments.

## Dry run, atomicity, and acceptance

Validate the complete input and collect independently detectable issues before
writing. Any invalid row rejects the entire batch; never import only valid rows.
Insert missing identities and their categories in one transaction. Any database
failure rolls back the batch. Apply the active-only duplicate policy and report
unexpected identity conflicts rather than overwriting existing records.

The future dry-run report should include source count, validated count, category
counts/assignment total, reviewed hour corrections, and per-record issues with
seed key when matched, source name/building, field, and reason. Row numbers may
help diagnostics but are not identifiers. Once database access is implemented,
report proposed inserts, existing-identity skips (including deleted), and
conflicts. Dry run writes nothing and generates no permanent UUIDs. Invalid
input or conflicts produce a nonzero exit status.

Report missing/unapproved areas, missing columns, malformed coordinates/times,
unknown categories/images, unmatched or ambiguous source associations, repeated
seed keys/UUIDs, and database identity/active-duplicate conflicts. Existing
seed identities are expected skips, not conflicts merely because later edits
changed their values.

Acceptance checks for later implementation:

- All 21 rows map to reviewed areas; six image references resolve to six files.
- Fresh import produces 21 suppliers, four categories, and 26 assignments.
- Exactly the five reviewed records become 24-hour schedules; Supersnacks is overnight.
- Reordering source rows preserves identities; changed unmatched names fail review.
- Reimport preserves administrator edits and deleted records and adds no duplicates.
- One invalid row or failed database write leaves the whole batch unapplied.
- The frontend container serves all six image paths and handles null with a placeholder.
