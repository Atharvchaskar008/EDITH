# Measured error of public element sets

Typical (1-sigma) error in km when an element set is 1, 3 and 7 days old: T along the direction of travel, R radial, N cross-track. Pairs spanning a manoeuvre are left out; the last column says how many that was. This method cannot measure the error at age zero.

| Kind of object | Objects | Pairs used | T at 1 / 3 / 7 d | R at 1 / 3 / 7 d | N at 1 / 3 / 7 d | Dropped as manoeuvres |
|---|---|---|---|---|---|---|
| Starlink | 100 | 25,459 | 12.27 / 76.84 / 422.78 | 0.22 / 0.80 / 9.54 | 0.21 / 0.60 / 1.66 | 27% |
| Other working satellites | 99 | 54,892 | 0.37 / 1.44 / 5.95 | 0.09 / 0.28 / 0.65 | 0.03 / 0.10 / 0.25 | 6% |
| Iridium NEXT | 80 | 66,708 | 0.12 / 0.43 / 1.63 | 0.13 / 0.40 / 0.90 | 0.02 / 0.04 / 0.11 | 44% |
| Dead satellites | 100 | 52,658 | 0.06 / 0.17 / 0.48 | 0.04 / 0.14 / 0.33 | 0.04 / 0.14 / 0.31 | 6% |
| Rocket bodies | 100 | 44,804 | 0.15 / 0.47 / 1.63 | 0.07 / 0.21 / 0.52 | 0.04 / 0.13 / 0.28 | 5% |
| Debris | 289 | 81,037 | 0.22 / 0.75 / 2.98 | 0.05 / 0.16 / 0.39 | 0.05 / 0.14 / 0.32 | 4% |

Along the direction of travel the error is by far the largest and it grows with age: after one day it is 0.22 km for debris, 0.15 km for rocket bodies and 0.06 km for dead satellites, against 0.05 km radially and 0.05 km cross-track for debris. Starlink is a different case, 12 km after one day and 77 km after three, because these satellites thrust almost continuously and public element sets do not include their planned moves. These are differences between element sets of the same object, not against its true position, so the true error is somewhat larger, and the error of a brand-new element set cannot be measured this way.
