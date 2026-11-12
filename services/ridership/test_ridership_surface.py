import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from ridership_surface import (
    RailValidationData,
    Route,
    Trip,
    adjust_estimate_for_vehicle_size,
    _validation_day_matches,
    average_daily_validations,
    collect_transit_arcs,
    estimate_rail_route_hour,
    easter_sunday,
    hour_bucket,
    inferred_day_category,
    iter_scenario_journeys,
    load_rail_route_stations,
    load_rail_validation_data,
    load_profile,
    normalize_line_name,
    parse_gtfs_time,
    resolve_surface_daily_average,
    resolve_surface_profile,
    read_scenario_metadata,
    route_network_class,
    scheduled_services_by_hour,
    vehicle_size_adjustment,
    Route,
)


class RidershipSurfaceTests(unittest.TestCase):
    def test_gtfs_time_supports_hours_after_midnight(self):
        self.assertEqual(parse_gtfs_time("25:10:00"), 90_600)
        self.assertIsNone(parse_gtfs_time(""))

    def test_gtfs_time_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            parse_gtfs_time("12:60:00")
        with self.assertRaises(ValueError):
            parse_gtfs_time("12:00")

    def test_hour_bucket_wraps_at_midnight(self):
        self.assertEqual(hour_bucket(23), "23H-0H")
        self.assertEqual(hour_bucket(4), "4H-5H")

    def test_line_name_normalizes_leading_zeroes(self):
        self.assertEqual(normalize_line_name("021"), "21")
        self.assertEqual(normalize_line_name(" N71 "), "n71")

    def test_surface_profile_matches_route_name_prefix_in_line_label(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            profile_file = Path(temporary_directory) / "profiles.csv"
            profile_file.write_text(
                "code_stif_ligne;libelle_ligne;cat_jour;trnc_horr_60;"
                "pourcentage_validations\n"
                "145;N161 -Paris Montparnasse - La Verrière;"
                "DIJFP;2H-3H;10\n",
                encoding="utf-8",
            )
            _, aliases, _, _ = load_profile(profile_file)

        self.assertEqual(aliases["n161"], {"145"})

    def test_surface_profile_falls_back_to_other_day_for_same_line(self):
        profile, categories, method = resolve_surface_profile(
            {("145", "SAHV", 2): 12.0},
            set(),
            "145",
            {"145", "146"},
            "DIJFP",
            2,
        )

        self.assertEqual(profile, 12.0)
        self.assertEqual(categories, ["SAHV"])
        self.assertEqual(method, "line_other_day")

    def test_surface_profile_falls_back_to_similar_line(self):
        profile, categories, method = resolve_surface_profile(
            {("146", "DIJFP", 2): 18.0},
            set(),
            "145",
            {"145", "146"},
            "WEEKEND",
            2,
        )

        self.assertEqual(profile, 18.0)
        self.assertEqual(categories, ["DIJFP"])
        self.assertEqual(method, "similar_line_requested_day")

    def test_surface_profile_falls_back_to_network_nearest_hour(self):
        profile, categories, method = resolve_surface_profile(
            {("146", "JOHV", 3): 8.0},
            set(),
            None,
            set(),
            "DIJFP",
            2,
        )

        self.assertEqual(profile, 8.0)
        self.assertEqual(categories, ["JOHV"])
        self.assertEqual(method, "network_nearest_available_hour")

    def test_surface_daily_average_falls_back_to_similar_line(self):
        average, method = resolve_surface_daily_average(
            {("146", "WEEKEND"): 1200.0},
            None,
            {"145", "146"},
            "WEEKEND",
        )

        self.assertEqual(average, 1200.0)
        self.assertEqual(method, "similar_line_daily_validations")

    def test_sunday_uses_sunday_holiday_category(self):
        self.assertEqual(inferred_day_category(date(2026, 11, 8), None), "DIJFP")
        self.assertTrue(_validation_day_matches(date(2025, 11, 11), "DIJFP"))
        self.assertFalse(_validation_day_matches(date(2025, 11, 10), "DIJFP"))

    def test_weekend_sample_includes_only_saturdays_and_sundays(self):
        self.assertTrue(_validation_day_matches(date(2025, 11, 1), "WEEKEND"))
        self.assertTrue(_validation_day_matches(date(2025, 11, 2), "WEEKEND"))
        self.assertFalse(_validation_day_matches(date(2025, 11, 3), "WEEKEND"))

    def test_weekday_requires_explicit_school_period_category(self):
        with self.assertRaises(ValueError):
            inferred_day_category(date(2026, 11, 12), None)
        self.assertEqual(
            inferred_day_category(date(2026, 11, 12), "JOHV"),
            "JOHV",
        )

    def test_easter_sunday(self):
        self.assertEqual(easter_sunday(2025), date(2025, 4, 20))

    def test_route_network_class(self):
        self.assertEqual(route_network_class(0), "surface")
        self.assertEqual(route_network_class(3), "surface")
        self.assertEqual(route_network_class(1), "rail")
        self.assertEqual(route_network_class(2), "rail")
        self.assertEqual(route_network_class(4), "other")
        self.assertEqual(route_network_class(None), "unknown")

    def test_vehicle_size_adjustments_by_gtfs_route_type(self):
        examples = (
            (Route("bus", "87", 3), ("bus", 1.0)),
            (Route("tram", "T10", 0), ("tramway", 1 / 3)),
            (Route("orlyval", "ORLYVAL", 0), ("orlyval", 1 / 3)),
            (Route("metro", "14", 1), ("metro", 1 / 4)),
            (Route("rer", "A", 2), ("rer", 1 / 8)),
            (Route("transilien", "H", 2), ("other_rail", 1 / 8)),
            (Route("cable-car", "C1", 6), ("cable_car", 1.0)),
        )
        for route, expected in examples:
            with self.subTest(route=route.short_name):
                self.assertEqual(vehicle_size_adjustment(route), expected)

    def test_vehicle_size_adjustment_rejects_unclassified_route_type(self):
        with self.assertRaises(ValueError):
            vehicle_size_adjustment(Route("unknown", "X", 4))

    def test_adjusted_estimate_uses_displayed_original_and_rounds_to_six_places(self):
        self.assertEqual(
            adjust_estimate_for_vehicle_size(226.024164, 1 / 8),
            28.25302,
        )

    def test_streams_journeys_from_large_json_shape(self):
        document = {
            "name": "sample",
            "description": "test",
            "departure_time": "2026-11-08T04:00:00+01:00",
            "journeys": [
                {"journey_id": "j-1", "legs": [{"mode": "transit"}]},
                {"journey_id": "j-2", "legs": []},
            ],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "journeys.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            journeys = list(iter_scenario_journeys(path))
            metadata = read_scenario_metadata(path)
        self.assertEqual(
            [journey["journey_id"] for journey in journeys],
            ["j-1", "j-2"],
        )
        self.assertEqual(metadata.scenario_id, "sample")
        self.assertEqual(metadata.service_date, date(2026, 11, 8))

    def test_scheduled_services_count_each_trip_once_per_overlapped_hour(self):
        service_date = date(2026, 11, 8)
        with tempfile.TemporaryDirectory() as temporary_directory:
            gtfs_dir = Path(temporary_directory)
            stop_times_file = gtfs_dir / "stop_times.txt"
            with stop_times_file.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(("trip_id", "arrival_time", "departure_time"))
                writer.writerow(("trip-1", "04:00:00", "04:00:00"))
                writer.writerow(("trip-1", "05:10:00", "05:10:00"))
                writer.writerow(("trip-2", "04:20:00", "04:20:00"))
                writer.writerow(("trip-2", "04:30:00", "04:30:00"))

            counts = scheduled_services_by_hour(
                gtfs_dir,
                {
                    "trip-1": Trip("route-1", "service"),
                    "trip-2": Trip("route-1", "service"),
                },
                {service_date: {"service"}},
            )

        self.assertEqual(counts[(service_date, "route-1", 4)], 2)
        self.assertEqual(counts[(service_date, "route-1", 5)], 1)

    def test_daily_validation_average_uses_matching_source_dates(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            validation_file = Path(temporary_directory) / "validations.csv"
            validation_file.write_text(
                "jour;code_stif_ligne;nb_vald\n"
                "2025-11-02;021;100\n"
                "2025-11-09;021;200\n"
                "2025-11-10;021;900\n",
                encoding="utf-8",
            )
            averages, day_counts, period = average_daily_validations(
                validation_file,
                {"21"},
                {"DIJFP"},
            )

        self.assertEqual(averages[("21", "DIJFP")], 150)
        self.assertEqual(day_counts["DIJFP"], 2)
        self.assertEqual(period, ("2025-11-02", "2025-11-10"))

    def test_collect_transit_arcs_deduplicates_without_scenario_id(self):
        journey = {
            "journey_id": "j-1",
            "legs": [
                {
                    "mode": "transit",
                    "gtfs_trip_id": "trip-1",
                    "start_time": "2026-11-08T02:15:00+01:00",
                    "end_time": "2026-11-08T02:20:00+01:00",
                    "from_stop": "IDFM:1",
                    "to_stop": "IDFM:2",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            scenarios_dir = Path(temporary_directory)
            for name in ("scenario-a", "scenario-b"):
                scenario_dir = scenarios_dir / name
                scenario_dir.mkdir()
                path = scenario_dir / "journeys.json"
                path.write_text(
                    json.dumps(
                        {
                            "name": name,
                            "departure_time": "2026-11-08T02:00:00+01:00",
                            "journeys": [journey],
                        }
                    ),
                    encoding="utf-8",
                )

            arcs, scenarios, source_count = collect_transit_arcs(
                list(scenarios_dir.glob("*/journeys.json")), None
            )

        self.assertEqual(source_count, 2)
        self.assertEqual(len(scenarios), 2)
        self.assertEqual(len(arcs), 1)
        self.assertEqual(arcs[0]["arc_occurrence_count"], 2)
        self.assertNotIn("scenario_id", arcs[0])

    def test_rail_weekend_estimate_sums_station_components_and_blends_profiles(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            validation_file = directory / "validations.csv"
            validation_file.write_text(
                "jour;code_stif_trns;code_stif_res;code_stif_arret;id_zdc;nb_vald\n"
                "2025-11-01;T;R;A;71013.0;100\n"
                "2025-11-02;T;R;A;71013.0;200\n"
                "2025-11-01;T;R;B;71013.0;50\n"
                "2025-11-02;T;R;B;71013.0;50\n",
                encoding="utf-8",
            )
            validation_file.write_text(
                validation_file.read_text(encoding="utf-8")
                + "2025-11-01;T;R;A;71014.0;10\n"
                + "2025-11-02;T;R;A;71014.0;30\n",
                encoding="utf-8",
            )
            profile_file = directory / "profiles.csv"
            profile_file.write_text(
                "code_stif_trns;code_stif_res;code_stif_arret;id_zdc;"
                "cat_jour;trnc_horr_60;pourcentage_validations\n"
                "T;R;A;71013.0;DIJFP;4H-5H;10\n"
                "T;R;A;71013.0;SAHV;4H-5H;20\n"
                "T;R;A;71013.0;SAVS;4H-5H;30\n"
                "T;R;B;71013.0;DIJFP;4H-5H;10\n"
                "T;R;B;71013.0;SAHV;4H-5H;20\n"
                "T;R;B;71013.0;SAVS;4H-5H;30\n"
                "T;R;A;71014.0;DIJFP;4H-5H;10\n"
                "T;R;A;71014.0;SAHV;4H-5H;20\n"
                "T;R;A;71014.0;SAVS;4H-5H;30\n",
                encoding="utf-8",
            )
            rail_data = load_rail_validation_data(
                validation_file,
                profile_file,
                {"WEEKEND"},
            )

        (
            daily,
            share,
            stop_count,
            categories,
            baseline_methods,
            profile_methods,
        ) = estimate_rail_route_hour({"71013", "71014"}, rail_data, "WEEKEND", 4)
        self.assertEqual(daily, 220)
        self.assertAlmostEqual(share, 20)
        self.assertEqual(stop_count, 2)
        self.assertEqual(categories, ["DIJFP", "SAHV", "SAVS"])
        self.assertEqual(baseline_methods, ["station_daily_validations"])
        self.assertEqual(profile_methods, ["station_requested_day"])

    def test_rail_profile_falls_back_to_peer_station_on_same_route(self):
        ambiguous_identity = ("T", "R", "A", "71013")
        missing_identity = ("T", "R", "B", "71014")
        rail_data = RailValidationData(
            average_daily_validations={
                (ambiguous_identity, "WEEKEND"): 10,
                (missing_identity, "WEEKEND"): 20,
            },
            hourly_shares_pct={(missing_identity, "DIJFP", 4): 30.0},
            ambiguous_hourly_profiles={(ambiguous_identity, "DIJFP", 4)},
            identities_by_station={
                "71013": {ambiguous_identity},
                "71014": {missing_identity},
            },
            validation_day_counts={"WEEKEND": 2},
            validation_period=("2025-11-01", "2025-11-02"),
        )

        estimate = estimate_rail_route_hour(
            {"71013", "71014"}, rail_data, "WEEKEND", 4
        )

        self.assertEqual(estimate[1], 30.0)
        self.assertIn("route_peer_station_requested_day", estimate[5])

    def test_unmatched_rail_station_uses_route_peer_profile_and_baseline(self):
        identity = ("T", "R", "A", "71013")
        rail_data = RailValidationData(
            average_daily_validations={(identity, "WEEKEND"): 100.0},
            hourly_shares_pct={(identity, "DIJFP", 4): 10.0},
            ambiguous_hourly_profiles=set(),
            identities_by_station={"71013": {identity}},
            validation_day_counts={"WEEKEND": 2},
            validation_period=("2025-11-01", "2025-11-02"),
        )

        estimate = estimate_rail_route_hour(
            {"71013", "99999"}, rail_data, "WEEKEND", 4
        )

        self.assertEqual(estimate[0], 200.0)
        self.assertEqual(estimate[1], 10.0)
        self.assertEqual(estimate[2], 1)
        self.assertIn("route_peer_station_daily_validations", estimate[4])
        self.assertIn("route_peer_station_requested_day", estimate[5])

    def test_rail_station_ids_map_through_gtfs_parent_stops(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            gtfs_dir = Path(temporary_directory)
            (gtfs_dir / "stops.txt").write_text(
                "stop_id,parent_station\n"
                "IDFM:platform,IDFM:71013\n"
                "IDFM:71013,\n",
                encoding="utf-8",
            )
            (gtfs_dir / "trips.txt").write_text(
                "trip_id,route_id\ntrip-1,route-1\n",
                encoding="utf-8",
            )
            (gtfs_dir / "stop_times.txt").write_text(
                "trip_id,stop_id\ntrip-1,IDFM:platform\n",
                encoding="utf-8",
            )

            stations_by_route, mapped_ids = load_rail_route_stations(
                gtfs_dir, {"route-1"}, {"71013"}
            )

        self.assertEqual(stations_by_route, {"route-1": {"71013"}})
        self.assertEqual(mapped_ids, {"71013"})


if __name__ == "__main__":
    unittest.main()
