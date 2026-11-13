# Ridership estimates for transit arcs

From the repository root, run:

```powershell
uv run --package routing python services\ridership\ridership_surface.py
```

The script reads scenario journeys from `data/output/scenarios/`, validation
files from `data/input/frequentation/`, and the GTFS feed from
`data/input/IDFM-gtfs-0511/`. It writes:

- `data/output/ridership/ridership_by_transit_arc.csv`: one row per distinct
  transit arc. Arcs shared by multiple journeys or scenarios are deduplicated;
  `arc_occurrence_count` records how often each arc occurred.
- `data/output/ridership/ridership_coverage_summary.json`: unique-arc and
  occurrence counts, estimate coverage, status counts, validation-source
  periods, and rail-station matching statistics.

The estimate is:

```text
average daily validations × hourly profile share
÷ GTFS trips on the route active during that hour
```

The result approximates validations per scheduled service, **not vehicle
occupancy**.

## Profile and validation fallbacks

Surface route names are matched to validation line codes, full labels, or the
line-name prefix before a spaced hyphen in a label. Similar surface lines are
grouped by service-name family: `N*` night buses together, `T*` tramways
together, other letter-prefixed lines by initial, and numeric lines by their
first two digits.

The hourly-profile fallback order is:

1. matched line and requested day category;
2. the same line's profile from another day category;
3. similar lines using the requested category, then their other categories;
4. network-wide profile for the requested category, then another category;
5. if that hour is absent network-wide, the nearest available profile hour.

Daily validation baselines use the matched line, then similar lines, then the
network-wide average. For rail, profiles and validation baselines first use
the station and requested category, then another category for the same
station, other stations on the route, and finally the rail-network average.
Rail stations missing from validation data are imputed from other stations
on their route, or from the rail network if no route station has usable data.

These are explicit approximations, not observed values. Each CSV row reports
`validation_baseline_method`, `hourly_profile_method`, and
`service_count_method` so fallback estimates remain identifiable.

If GTFS reports no scheduled service in the arc's route-hour, the journey's
observed trip is used as a minimum count of one service and marked
`observed_trip_minimum`. This avoids dividing by zero, but is a lower-bound
proxy rather than a complete service count.

## Vehicle-size adjustment and score

The original `estimated_validations_per_service` value is retained. The CSV
also includes `vehicle_category` and `vehicle_size_ratio`. First multiply the
original estimate by this ratio (rounded to six decimal places), then convert
it to an inverse score in `estimated_validations_per_service_adjusted`:

```text
weighted = round(original estimate × vehicle-size ratio, 6)
score = 100 × (1 - min(max(weighted, 0), 50) / 50)
```

Thus 0 maps to 100, 25 maps to 50, and values greater than or equal to 50 map
to 0. The output score is bounded between 0 and 100.

| Category | Ratio |
|---|---:|
| Bus | 1 |
| RER | 1/8 |
| Other rail (Transilien/TER) | 1/8 |
| Metro | 1/4 |
| Tramway | 1/3 |
| ORLYVAL | 1/3 |
| Cable car C1 | 1 |

The ratios are user-provided relative weights, not measured vehicle
capacities. The `estimated_validations_per_service_adjusted` column now
contains the normalized score, not the weighted raw estimate.

## Weekend sample

Weekend scenarios (`DIJFP`, `SAHV`, or `SAVS`) use daily validation totals
averaged over Saturdays and Sundays. The hourly share is the unweighted mean
of available `DIJFP`, `SAHV`, and `SAVS` profiles for the line/station and
hour. Daily data does not distinguish school periods, and the profile
categories are blended equally. Sunday and French public-holiday categories
are detected automatically. Weekday scenarios require `--day-category`
(`JOVS` or `JOHV`); Saturday scenarios require `SAHV` or `SAVS`.

## Rail data approximation

Metro, RER, train, and tram-train routes are identified using GTFS `route_type`
1 and 2. Validation counts are summed by station over all validation
components at that station, then assigned in full to every GTFS rail route
serving it. Shared stations may therefore contribute their full validations
to multiple lines. Station IDs are matched by the numeric suffix of GTFS
`parent_station`/`stop_id` and validation `id_zdc`.

## `validation_status`

- `estimated`: direct matched line/station inputs, requested-day profile, and
  GTFS service count were available.
- `estimated_with_fallback`: one or more surface baselines, profiles, or
  service counts were imputed.
- `estimated_partial_rail_station_mapping`: some rail stations were not
  matched, but a route-level estimate was calculated using station fallbacks.
- `estimated_partial_rail_station_mapping_with_fallback`: the rail mapping is
  partial and other profile, baseline, or service-count fallbacks were used.
- `estimated_with_network_fallback`: an unclassified route was estimated from
  the surface network as a proxy.

Every transit arc has a numeric `estimated_validations_per_service`. Check the
method columns before interpreting an imputed estimate as a direct match.
`validation_stop_count` records matched rail validation stations.
