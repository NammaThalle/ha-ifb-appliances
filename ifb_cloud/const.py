"""Constants for IFB Cloud API client."""

from enum import Enum, IntEnum

# Base URLs discovered from My IFB Android app (com.sqt_smartapp.ifb_remote)
API_V4_BASE_URL = "https://www.ifbcloud.in:3000/api/v4"
MAGENTO_BASE_URL = "https://ifbappliances.com/rest/V1"
GRAPHQL_AUTH_URL = "https://edge-graph.adobe.io/api/c966e57b-84c0-4ebb-898a-6e860cf1f906/graphql"

# MQTT Broker Endpoints
MQTT_ESP_HOST = "mqttesp.ifbcloud.in"
MQTT_ESP_PORT = 8887
MQTT_GAINSPAN_HOST = "mqtt2.ifbcloud.in"
MQTT_GAINSPAN_PORT = 8883

# REST Endpoints (appended to API_V4_BASE_URL)
ENDPOINT_GET_ALL_DEVICES = "getAllDevices"
ENDPOINT_GET_DEVICE_PROGRESS = "getUserDeviceProgress"
ENDPOINT_GET_DEVICE_STATUS = "deviceStatus"
ENDPOINT_GET_DEVICE_META = "getDeviceMeta"
ENDPOINT_GET_MODEL_SPECIFICATIONS = "getModelSpecifications"
ENDPOINT_GET_MQTT_CLIENT = "mapping/client"
ENDPOINT_SEND_COMMAND = "sendCommand"
ENDPOINT_CONNECT = "connect"
ENDPOINT_DISCONNECT = "disconnect"
ENDPOINT_UPDATE_TOKEN = "updateToken"
ENDPOINT_USER_PROFILE = "getUserProfile"

# Authentication Endpoints
ENDPOINT_AUTH_LOGIN = "restapi/login"
ENDPOINT_AUTH_VERIFY_OTP = "restapi/otpverify"
ENDPOINT_AUTH_GENERATE_TOKEN = "restapi/generatetoken"

# Default HTTP Headers matching the official mobile application
DEFAULT_HEADERS = {
    "User-Agent": "MyIFB/Android (okhttp/4.9.0)",
    "Accept": "application/json",
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

# Wash Programs Catalog
PROGRAM_NAMES = {
    0x01: "Mix / Daily",
    0x02: "Cotton Normal",
    0x03: "Cradle Wash",
    0x04: "Synthetic",
    0x05: "Woollens",
    0x06: "Express 15",
    0x07: "Spin Dry / Drain",
    0x08: "Rinse + Spin",
    0x09: "Tub Clean",
    0x0A: "Baby Wear",
    0x0B: "Bulky / Bedding",
    0x0C: "Curtains",
    0x0D: "Fitness Wear",
    0x0E: "Dark Wash",
    0x0F: "Shirts",
    0x10: "Hygiene / Anti-Allergen",
    0x11: "Refresh",
    0x12: "Wash + Dry 60",
    0x13: "Dry Only",
    0x14: "Eco Cotton",
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
