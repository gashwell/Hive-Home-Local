"""Constants for Hive Home Local."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

MIN_HA_VERSION = "2024.1.0"

DOMAIN = "hive_home_local"
CONFIG_VERSION = 1

# ── Config entry keys ─────────────────────────────────────────────────
CONF_MQTT_TOPIC = "mqtt_topic"
CONF_MODEL = "model"
CONF_DEVICE_FAMILY = "device_family"
CONF_Z2M_BASE_TOPIC = "z2m_base_topic"
CONF_BOILER_ENTITY = "boiler_entity"
CONF_PERSON_ENTITIES = "person_entities"
CONF_SHOW_HEAT_SCHEDULE_MODE = "show_heat_schedule_mode"
CONF_SHOW_WATER_SCHEDULE_MODE = "show_water_schedule_mode"

# ── Device families ───────────────────────────────────────────────────
FAMILY_HUB = "hub"       # SLR1 / SLR2 / OTR1 — heating/hot water hub
FAMILY_TRV = "trv"       # UK7004240 / TRV001 — radiator valve

# ── Hub models (SLR/OTR family) ──────────────────────────────────────
MODEL_OTR1 = "OTR1"
MODEL_SLR1 = "SLR1"
MODEL_SLR2 = "SLR2"

HUB_MODELS = [MODEL_OTR1, MODEL_SLR1, MODEL_SLR2]

# ── TRV models ────────────────────────────────────────────────────────
MODEL_TRV = "UK7004240"
MODEL_TRV_ALT = "TRV001"

SUPPORTED_TRV_MODELS = {MODEL_TRV, MODEL_TRV_ALT}

# ── All models combined ───────────────────────────────────────────────
ALL_MODELS = HUB_MODELS + [MODEL_TRV, MODEL_TRV_ALT]

# ── TRV operating modes ───────────────────────────────────────────────
MODE_OFF = "off"
MODE_MANUAL = "manual"
MODE_SCHEDULE = "schedule"
MODE_BOOST = "boost"
MODE_AWAY = "away"
MODE_HOLIDAY = "holiday"

# ── Hub boost / preset ────────────────────────────────────────────────
HIVE_BOOST = "emergency_heat"

# ── Defaults ─────────────────────────────────────────────────────────
DEFAULT_FROST_TEMP = 7.0
DEFAULT_FROST_TEMP_HUB = 12.0
DEFAULT_HEATING_BOOST_MINUTES = 60
DEFAULT_HEATING_BOOST_TEMPERATURE = 22.0
DEFAULT_WATER_BOOST_MINUTES = 60
MAXIMUM_BOOST_MINUTES = 180

# ── Z2M sweep interval ────────────────────────────────────────────────
SWEEP_INTERVAL_S = 30

# ── Storage ───────────────────────────────────────────────────────────
DATA_HUB = "hub"
DATA_STORE = "store"

# ── Service names ─────────────────────────────────────────────────────
SERVICE_BOOST_HEATING = "boost_heating"
SERVICE_CANCEL_BOOST_HEATING = "cancel_boost_heating"
SERVICE_BOOST_WATER = "boost_water"
SERVICE_CANCEL_BOOST_WATER = "cancel_boost_water"
SERVICE_SET_TRV_SCHEDULE = "set_trv_schedule"
SERVICE_CLEAR_TRV_SCHEDULE = "clear_trv_schedule"
SERVICE_ADVANCE_TRV_SCHEDULE = "advance_trv_schedule"
SERVICE_BOOST_TRV = "boost_trv"
SERVICE_END_BOOST_TRV = "end_boost_trv"
SERVICE_SET_HOLIDAY = "set_holiday"
SERVICE_CANCEL_HOLIDAY = "cancel_holiday"
SERVICE_ADD_ROOM = "add_room"
SERVICE_REMOVE_ROOM = "remove_room"

# ── MQTT topic templates ──────────────────────────────────────────────
TOPIC_Z2M_DEVICES = "{base}/bridge/devices"
TOPIC_Z2M_REQUEST = "{base}/bridge/request/devices"
TOPIC_Z2M_RESPONSE = "{base}/bridge/response/devices"
TOPIC_Z2M_STATE = "{base}/{name}"
TOPIC_Z2M_SET = "{base}/{name}/set"

# ── Aliases for hub coordinator compatibility ─────────────────────────
DEFAULT_FROST_TEMPERATURE = DEFAULT_FROST_TEMP_HUB
