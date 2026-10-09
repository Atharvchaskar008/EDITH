# Reference Test Kit for Conjunction Screening

This test kit validates conjunction screening engines against 7 benchmark orbital scenarios.
To test a custom screening function `screen(catalog, t0, hours, threshold_km) -> list[dict]`:

1. Import `check` from `check.py`: `from check import check`.
2. Run `check(your_screen_function)`.
3. The checker runs all 7 test cases in `cases.json` against your function.
4. Pass criteria: exact matching event pairs found within tolerance.
5. Accepted tolerances: Time of Closest Approach (TCA) within 0.5 s, miss distance within 10 m (0.010 km).
6. Test cases cover: ~300m miss, ~2km miss, ~8km out-of-bounds, co-planar 500km separation, dual passes in 72h, fast <10s crossing, and 1-vs-50 background screening.
