"""Every tunable number in the project lives here."""

# --- Catalogue -------------------------------------------------------------
CELESTRAK_GP_URL = "https://celestrak.org/NORAD/elements/gp.php"

# "ALL_LEO": every tracked LEO object against every other (full coverage).
# "PRIMARIES": only PRIMARY_GROUPS against the rest (fast, for development).
SCREEN_MODE = "ALL_LEO"

# Used in "PRIMARIES" mode. Any list of CelesTrak group names.
PRIMARY_GROUPS = ["iridium-NEXT"]

# Everything the primaries are screened against.
SECONDARY_GROUPS = [
    "active",
    "cosmos-2251-debris",
    "iridium-33-debris",
    "fengyun-1c-debris",
]

# Space-Track: full catalogue incl. all debris; used only when .env has a login.
SPACETRACK_CACHE_HOURS = 2.0  # they allow one bulk catalogue request per hour
SPACETRACK_TIMEOUT_S = 180.0

CACHE_MAX_AGE_HOURS = 2.0
REQUEST_PAUSE_S = 2.0
REQUEST_TIMEOUT_S = 30.0
MAX_TLE_AGE_DAYS = 14.0
LEO_MAX_PERIGEE_KM = 2000.0  # objects that never come below this are ignored
DEFAULT_RADIUS_M = 5.0
# Space-Track radar cross-section classes: SMALL < 0.1 m2, MEDIUM 0.1-1 m2, LARGE > 1 m2.
# Approximate radius of a disc with that area; LARGE has no upper bound, so 2 m is a guess.
RCS_RADIUS_M = {"SMALL": 0.15, "MEDIUM": 0.4, "LARGE": 2.0}

# --- Screening -------------------------------------------------------------
WINDOW_HOURS = 72.0
QUICK_WINDOW_HOURS = 24.0
SCREEN_STEP_S = 10.0
SCREEN_THRESHOLD_KM = 5.0  # PRIMARIES mode
# ALL_LEO finds about 2,300 passes an hour under 5 km (measured), so it uses 1 km
SCREEN_THRESHOLD_ALL_LEO_KM = 1.0
MAX_CLOSING_SPEED_KMS = 15.5
ALTITUDE_PAD_KM = 30.0
MIN_RELATIVE_SPEED_KMS = 0.1  # slower pairs are formation neighbours
PROPAGATE_CHUNK_S = 1800.0

# --- Risk ------------------------------------------------------------------
RED_PC_MAX = 1e-4
AMBER_PC_MAX = 1e-5

# Assumed 1-sigma position error, used when no measured value is available:
# sigma = sigma0 + rate * tle_age_days, per RTN axis, in km.
SIGMA0_RTN_KM = (0.1, 0.5, 0.1)
SIGMA_RATE_RTN_KM_PER_DAY = {
    "PAYLOAD": (0.05, 1.0, 0.05),
    "DEBRIS": (0.05, 2.0, 0.05),
    "ROCKET_BODY": (0.05, 2.0, 0.05),
    "UNKNOWN": (0.05, 2.0, 0.05),
}

# --- Manoeuvre -------------------------------------------------------------
TARGET_PC_AFTER = 1e-6  # probability after the burn must be below this ...
TARGET_PC_MAX_AFTER = 1e-5  # ... and the worst case must be back to GREEN
VERIFY_HOURS = 24.0  # how long the manoeuvred orbit is re-screened for new close approaches
DV_GRID_MIN_MS = 0.001
DV_GRID_MAX_MS = 0.1
DV_GRID_POINTS = 12
MAX_LEAD_ORBITS = 8.0
MIN_LEAD_TIME_S = 1800.0
MAX_PLANS_PER_RUN = 5

# --- Monitoring ------------------------------------------------------------
SCHEDULER_INTERVAL_HOURS = 6.0

# --- Physical constants (WGS-72, matching SGP4) ----------------------------
MU_KM3_S2 = 398600.8
EARTH_RADIUS_KM = 6378.135
J2 = 1.082616e-3
