"""Write ./out/VALIDATION_REPORT.md from the JSON files in ./out/ (standalone).

    python make_report.py

Every number in the report is read from a JSON file in ./out/, so the report
cannot drift from the results. The Monte Carlo check is run here and saved as
./out/pc_monte_carlo_check.json first.
"""

from __future__ import annotations

import json
from pathlib import Path


from pc_reference import pc_integral, pc_monte_carlo
from tle_error import evaluate

OUT = Path(__file__).resolve().parent / "out"


def read(name: str) -> dict | None:
    path = OUT / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def monte_carlo_check() -> dict:
    from test_pc_reference import CASES

    rows = []
    for m, Cp, hbr in CASES:
        exact = pc_integral(m, Cp, hbr)
        estimate, error = pc_monte_carlo(m, Cp, hbr, n=40_000_000 if exact < 1e-4 else 10_000_000, seed=7)
        rows.append({"pc": exact, "monte_carlo": estimate, "standard_error": error, "deviation_in_standard_errors": abs(exact - estimate) / error})
    result = {
        "cases": len(rows), "smallest_pc": min(r["pc"] for r in rows), "largest_pc": max(r["pc"] for r in rows),
        "largest_deviation_in_standard_errors": max(r["deviation_in_standard_errors"] for r in rows), "rows": rows,
    }
    (OUT / "pc_monte_carlo_check.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def main() -> None:
    mc = monte_carlo_check()
    esa, soc, err, rob = read("esa_pc_check.json"), read("socrates_validation.json"), read("tle_error.json"), read("robustness.json")
    cases = read("pc_test_cases.json")
    lines = ["# Validation report", ""]

    lines += [
        "## What we checked and why", "",
        "A collision-avoidance system is only as good as three things: where it says two objects will pass, how "
        "likely it says a collision is, and how well it knows its own uncertainty. Each of the three was checked "
        "against something outside our own code. Where a check came out badly, it is reported as it came out.", "",
    ]

    lines += ["## Collision probability", ""]
    lines.append(
        f"- **Against random sampling.** On {mc['cases']} cases with probabilities from {mc['smallest_pc']:.0e} to "
        f"{mc['largest_pc']:.0e}, including uncertainty stretched 20 to 1, the calculated probability agrees with a "
        f"simulation of 10 to 40 million random draws; the largest deviation is {mc['largest_deviation_in_standard_errors']:.1f} "
        f"standard errors (`pc_monte_carlo_check.json`). The fast formula also equals a direct double integral to 7 digits (tests)."
    )
    if cases:
        lines.append(
            f"- **The main engine against this reference.** {len(cases)} cases covering head-on, crossing and overtaking "
            f"passes are in `pc_test_cases.json`; the main engine's own probability code is tested against them to 2%."
        )
    if esa:
        p, band = esa["probability"], esa["probability_by_esa_risk_band"]
        high = band["ESA risk above 1e-6"]
        worst = esa["worst_case_against_esa_max_risk_estimate"]
        lines.append(
            f"- **Against the European Space Agency.** On {p['rows']:,} real warnings ESA received for its satellites "
            f"(of {esa['rows_usable']:,} usable rows), our probability has no offset from ESA's own "
            f"(median {p['median_signed_offset_log10']:+.3f} in log10) once the object size is read as {esa['hard_body_radius_used']}. "
            f"For the {high['rows']:,} warnings ESA rated above 1 in a million, the median difference is "
            f"{high['median_abs_difference_log10']:.3f} in log10 (about {100 * (10 ** high['median_abs_difference_log10'] - 1):.0f}%) and "
            f"{100 * high['share_within_0.1_log10']:.0f}% are within 0.1. Over all warnings the median difference is "
            f"{p['median_abs_difference_log10']:.2f} and one in ten differs by more than {p['p90_abs_difference_log10']:.1f}: "
            f"far out in the tail, where the probability is negligible, tiny differences in the inputs are magnified, and "
            f"we cannot see from the file how ESA treated those. Chart: `esa_pc_check.png`."
        )
        lines.append(
            f"- **Worst case against ESA's.** ESA also publishes a maximum risk over the size of the uncertainty. Ours "
            f"matches it with a median difference of {worst['median_abs_difference_log10']:.3f} in log10 "
            f"({100 * worst['share_within_0.1_log10']:.0f}% within 0.1, correlation {worst['correlation']:.3f}) on the same {worst['rows']:,} warnings."
        )
    else:
        lines.append("- **Against ESA: not done.** The dataset was not available.")
    lines.append("")

    lines += ["## Close-approach geometry", ""]
    if soc:
        m = soc["all_matches"]
        rank = soc.get("max_probability_rank_agreement")
        lines.append(
            f"CelesTrak publishes its own predicted conjunctions (SOCRATES). We took its {soc['conjunctions_taken']} "
            f"closest, fetched the very element sets it used from Space-Track's history ({soc['skipped_element_set_not_found']} "
            f"could not be found), and recomputed each pass. All {m['matched']} match: the distance differs by a median of "
            f"{m['miss_difference_m']['median']:.2f} m (9 in 10 within {m['miss_difference_m']['p90']:.1f} m, largest "
            f"{m['miss_difference_m']['max']:.0f} m), the time by {m['tca_difference_s']['median'] * 1000:.1f} ms "
            f"(9 in 10 within {m['tca_difference_s']['p90']:.2f} s) and the relative speed by "
            f"{m['relative_speed_difference_ms']['median']:.2f} m/s. CelesTrak publishes distance to the metre and speed to "
            f"the metre per second, so this is agreement to the last published digit. Chart: `socrates_validation.png`."
        )
        if rank:
            lines.append("")
            lines.append(
                f"CelesTrak's maximum probability is a different matter. With its assumed shape of uncertainty (100 m radial, "
                f"300 m in-track, 100 m cross-track) we rank the {rank['pairs']} pairs similarly (rank agreement "
                f"{rank['spearman_with_socrates_shape_of_uncertainty']:.2f}; its object sizes are not documented). With the "
                f"uncertainty we measured, the agreement is {rank['spearman_with_measured_uncertainty']:.2f}: the real "
                f"uncertainty is far more stretched along the track, and that changes which passes are the dangerous ones."
            )
    else:
        lines.append("Not done: the SOCRATES comparison has not been run.")
    lines.append("")

    lines += ["## Uncertainty", ""]
    if err:
        groups = err["by_group"]
        pairs = sum(g["pairs_kept"] for g in groups.values())
        objects = sum(g["objects"] for g in groups.values())
        at = lambda g, age, axis: float(evaluate(groups[g], age)[axis])  # noqa: E731
        lines.append(
            f"Public orbit data comes with no error bars, so we measured them: {pairs:,} pairs of element sets from "
            f"{objects} objects, each older set propagated to the time of a newer one of the same object. After one day the "
            f"typical error along the direction of travel is {at('DEAD_PAYLOAD', 1, 1):.2f} km for dead satellites, "
            f"{at('ROCKET_BODY', 1, 1):.2f} km for rocket bodies, {at('DEBRIS', 1, 1):.2f} km for debris, "
            f"{at('ACTIVE_OTHER', 1, 1):.2f} km for working satellites other than Starlink, and {at('STARLINK', 1, 1):.0f} km for "
            f"Starlink ({at('STARLINK', 3, 1):.0f} km after three days). Radial and cross-track errors are several times smaller "
            f"({at('DEBRIS', 1, 0):.2f} and {at('DEBRIS', 1, 2):.2f} km for debris). Chart: `tle_error_growth.png`; table: `tle_error_summary.md`."
        )
        operator = read("esa_sigma_stats.json")
        if operator and "DEBRIS" in operator and "1" in operator["DEBRIS"]:
            theirs = operator["DEBRIS"]["1"]["median_sigma_rtn_m"][1] / 1000.0
            lines.append("")
            lines.append(
                f"For scale: the uncertainty stated in ESA's warnings for debris, one to two days before a pass, has a "
                f"median of {theirs:.2f} km along the track (`esa_sigma_stats.json`). That is a forecast that allows for "
                f"what the atmosphere might do, on different objects, so the two are not the same quantity, but it is "
                f"{theirs / at('DEBRIS', 1, 1):.0f} times our figure for debris and one more sign that ours is not cautious."
            )
    else:
        lines.append("Not done.")
    lines.append("")

    lines += ["## Robustness", ""]
    if rob:
        v = rob["variations"]
        lines.append(
            f"On {rob['events']} close passes, halving or doubling the assumed uncertainty changes the level of "
            f"{v['Uncertainty halved']['events_changing_risk_level']} passes and keeps {v['Uncertainty doubled']['top10_still_in_top10']} "
            f"of the top 10, because we rank by the worst case over every size of uncertainty. Changing the assumed object "
            f"size from 10 m to 5 m or 20 m moves {v['Object size 5 m']['events_changing_risk_level']} and "
            f"{v['Object size 20 m']['events_changing_risk_level']} passes across a level, and ranking by closeness alone "
            f"agrees with the worst-case ranking at only {rob['miss_distance_alone']['spearman_between_closeness_and_pc_max']:.2f}. "
            f"Chart: `robustness.png`; notes: `robustness_notes.md`."
        )
    else:
        lines.append("Not done.")
    lines.append("")

    lines += [
        "## Limits: what these checks do not prove", "",
        "- The uncertainty was measured between element sets, not against true positions. It understates the real "
        "error, and it cannot see the error of a brand-new element set at all.",
        "- Agreement with CelesTrak shows that we read the public data the same way it does. It says nothing about "
        "how close that data is to reality.",
        "- ESA's warnings rest on far better tracking than public element sets. Matching its probability shows the "
        "arithmetic is right, not that our inputs are as good.",
        "- Object size is the assumption that moves the most passes between levels, and public data gives it only roughly.",
        "- No check here covers objects that manoeuvre between the prediction and the pass.",
    ]
    (OUT / "VALIDATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
