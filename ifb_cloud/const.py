"""Constants for IFB Cloud API client."""

from enum import Enum, IntEnum

# Base URLs
API_V5_BASE_URL = "https://myifb.ifbcloud.in/api/v5"
API_V4_BASE_URL = "https://www.ifbcloud.in:3000/api/v4"
DEFAULT_BASE_URL = API_V5_BASE_URL
MAGENTO_BASE_URL = "https://ifbappliances.com/rest/V1"
GRAPHQL_AUTH_URL = "https://edge-graph.adobe.io/api/c966e57b-84c0-4ebb-898a-6e860cf1f906/graphql"

# MQTT Broker Endpoints
MQTT_ESP_HOST = "mqttesp.ifbcloud.in"
MQTT_ESP_PORT = 8887
MQTT_GAINSPAN_HOST = "mqtt2.ifbcloud.in"
MQTT_GAINSPAN_PORT = 8883

# REST Endpoints (appended to base URL)
ENDPOINT_GET_ALL_DEVICES = "device/all"
ENDPOINT_GET_DEVICE_PROGRESS = "device/smart/progress"
ENDPOINT_SEND_COMMAND = "device/smart/sendCommand"
ENDPOINT_GET_DEVICE_STATUS = "device/smart/status"
ENDPOINT_GET_DEVICE_META = "device/meta"
ENDPOINT_USER_PROFILE = "user/profile"
ENDPOINT_GET_RESPONSE = "getResponse"
ENDPOINT_GET_MODEL_SPECIFICATIONS = "getModelSpecifications"
ENDPOINT_GET_MQTT_CLIENT = "mapping/client"
ENDPOINT_CONNECT = "connect"
ENDPOINT_DISCONNECT = "disconnect"
ENDPOINT_UPDATE_TOKEN = "updateToken"

# Legacy v4 aliases
LEGACY_GET_ALL_DEVICES = "getAllDevices"
LEGACY_GET_DEVICE_PROGRESS = "getUserDeviceProgress"
LEGACY_DEVICE_STATUS = "deviceStatus"

# Authentication Endpoints
ENDPOINT_AUTH_LOGIN = "restapi/login"
ENDPOINT_AUTH_VERIFY_OTP = "restapi/otpverify"
ENDPOINT_AUTH_GENERATE_TOKEN = "restapi/generatetoken"

# Default HTTP Headers matching the official mobile application
DEFAULT_HEADERS = {
    "User-Agent": "MyIFB/2.0.29(Mobile; iOS; 27.0.1; iPhone 16 Pro)",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
}

# Machine State Definitions
class MachineState(str, Enum):
    """Machine state representations."""
    OFF = "off"
    STANDBY = "standby"
    DELAY_START = "delay_start"
    PREWASH = "prewash"
    MAIN_WASH = "washing"
    SOAK = "soak"
    RINSING = "rinsing"
    SPINNING = "spinning"
    DRYING = "drying"
    STEAM = "steam"
    ANTI_CREASE = "anti_crease"
    PAUSED = "paused"
    COMPLETE = "complete"
    ERROR = "error"
    UNKNOWN = "unknown"

# Wash Programs Catalog - Specific to Washer-Dryer Models (e.g. Executive Plus ZBG 11/7/3)
# Verified directly against physical machine firmware over MQTT
WASHER_DRYER_PROGRAMS = {
    # Left Dial
    14: "Express 15'",
    13: "Mix/Daily",
    17: "Cotton",
    11: "Synthetic",
    10: "Anti-Allergen",
    9: "Baby Wear",
    8: "Bulky",
    # Right Dial
    1: "Wash+Dry 2Hr",
    2: "Wash+Dry 4Hr",
    3: "Spin & Dry",
    4: "Refresh",
    5: "PowerSteam®",
    6: "CradleWash®",
    7: "Wool",
}

# Standard Washing Machine Programs (applianceType == "WASHING_MACHINE")
WASHING_MACHINE_PROGRAMS = {
    0x01: "Mixed Soiled",
    0x02: "Synthetic Daily",
    0x03: "Cotton Normal",
    0x04: "Cotton Eco Plus",
    0x05: "Sports Wear",
    0x06: "Cradle Wash",
    0x07: "Additives / Rinse + Spin",
    0x08: "Spin Dry / Drain",
    0x09: "Baby Wear",
    0x0A: "Woollens",
    0x0B: "Express Wash",
    0x0C: "Anti-Allergen",
    0x0D: "Bulky Bedding / Curtains",
    0x0E: "Dark Wash",
    0x0F: "Tub Clean",
}

# Default program mapping for washer dryers (with fallback for service/tub clean codes)
PROGRAM_NAMES = {
    **WASHER_DRYER_PROGRAMS,
    12: "Eco Clean",
    15: "Drain",
    16: "Tub Clean",
    18: "Service Clean",
}

# Program capability profiles defining allowable controls for each cycle
PROGRAM_PROFILES = {
    14: {  # Express 15'
        "temps": ["Cold", "20°C", "30°C", "40°C"],
        "spins": ["No Spin", "400 RPM", "600 RPM", "800 RPM", "1000 RPM"],
        "dry": False,
        "steam": False,
    },
    13: {  # Mix/Daily
        "temps": ["Cold", "20°C", "30°C", "40°C", "60°C"],
        "spins": ["No Spin", "400 RPM", "600 RPM", "800 RPM", "1000 RPM", "1200 RPM", "1400 RPM"],
        "dry": True,
        "steam": True,
    },
    17: {  # Cotton
        "temps": ["Cold", "20°C", "30°C", "40°C", "60°C", "95°C"],
        "spins": ["No Spin", "400 RPM", "600 RPM", "800 RPM", "1000 RPM", "1200 RPM", "1400 RPM"],
        "dry": True,
        "steam": True,
    },
    11: {  # Synthetic
        "temps": ["Cold", "20°C", "30°C", "40°C", "60°C"],
        "spins": ["No Spin", "400 RPM", "600 RPM", "800 RPM", "1000 RPM", "1200 RPM"],
        "dry": True,
        "steam": True,
    },
    10: {  # Anti-Allergen
        "temps": ["40°C", "60°C", "95°C"],
        "spins": ["No Spin", "400 RPM", "600 RPM", "800 RPM", "1000 RPM", "1200 RPM", "1400 RPM"],
        "dry": True,
        "steam": True,
    },
    9: {  # Baby Wear
        "temps": ["40°C", "60°C", "95°C"],
        "spins": ["No Spin", "400 RPM", "600 RPM", "800 RPM", "1000 RPM", "1200 RPM", "1400 RPM"],
        "dry": True,
        "steam": True,
    },
    8: {  # Bulky
        "temps": ["Cold", "20°C", "30°C", "40°C", "60°C"],
        "spins": ["No Spin", "400 RPM", "600 RPM", "800 RPM", "1000 RPM"],
        "dry": True,
        "steam": True,
    },
    1: {  # Wash+Dry 2Hr
        "temps": ["Cold", "20°C", "30°C", "40°C"],
        "spins": ["No Spin", "400 RPM", "600 RPM", "800 RPM", "1000 RPM", "1200 RPM", "1400 RPM"],
        "dry": True,
        "steam": True,
    },
    2: {  # Wash+Dry 4Hr
        "temps": ["Cold", "20°C", "30°C", "40°C", "60°C"],
        "spins": ["No Spin", "400 RPM", "600 RPM", "800 RPM", "1000 RPM", "1200 RPM", "1400 RPM"],
        "dry": True,
        "steam": True,
    },
    3: {  # Spin & Dry
        "temps": ["Cold"],
        "spins": ["400 RPM", "600 RPM", "800 RPM", "1000 RPM", "1200 RPM", "1400 RPM"],
        "dry": True,
        "steam": False,
    },
    4: {  # Refresh
        "temps": ["Cold"],
        "spins": ["No Spin"],
        "dry": True,
        "steam": True,
    },
    5: {  # PowerSteam®
        "temps": ["Cold", "20°C", "30°C", "40°C", "60°C"],
        "spins": ["No Spin", "400 RPM", "600 RPM", "800 RPM", "1000 RPM", "1200 RPM"],
        "dry": True,
        "steam": True,
    },
    6: {  # CradleWash®
        "temps": ["Cold", "20°C", "30°C", "40°C"],
        "spins": ["No Spin", "400 RPM"],
        "dry": False,
        "steam": False,
    },
    7: {  # Wool
        "temps": ["Cold", "20°C", "30°C", "40°C"],
        "spins": ["No Spin", "400 RPM", "600 RPM", "800 RPM"],
        "dry": False,
        "steam": False,
    },
    18: {  # Tub Clean
        "temps": ["95°C"],
        "spins": ["1400 RPM"],
        "dry": False,
        "steam": False,
    },
}

# Dry Modes for Washer-Dryer combo models
DRY_MODES = {
    0x00: "No Dry",
    0x01: "Cupboard Dry",
    0x02: "Iron Dry",
    0x03: "Extra Dry",
    0x04: "Time Dry 30 Min",
    0x05: "Time Dry 60 Min",
    0x06: "Time Dry 90 Min",
    0x07: "Time Dry 120 Min",
}

# Spin Speeds
SPIN_SPEEDS = [
    "No Spin",
    "400 RPM",
    "600 RPM",
    "800 RPM",
    "1000 RPM",
    "1200 RPM",
    "1400 RPM",
]

# Temperatures
TEMPERATURES = [
    "Cold",
    "20°C",
    "30°C",
    "40°C",
    "60°C",
    "95°C",
]
