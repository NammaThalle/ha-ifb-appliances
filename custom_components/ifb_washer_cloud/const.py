"""Constants for the IFB Washer Cloud integration."""

DOMAIN = "ifb_washer_cloud"

CONF_AUTH_TYPE = "auth_type"
CONF_PHONE = "phone"
CONF_CALLING_CODE = "calling_code"
CONF_PASSWORD = "password"
CONF_TOKEN = "token"
CONF_USER_ID = "user_id"
CONF_OTP = "otp"
CONF_MAC = "mac"
CONF_DEVICE_NAME = "device_name"
CONF_MQTT_CLIENT_ID = "mqtt_client_id"
CONF_MQTT_BACKOFF = "mqtt_backoff"
CONF_SCAN_INTERVAL_RUNNING = "scan_interval_running"
CONF_SCAN_INTERVAL_IDLE = "scan_interval_idle"

AUTH_TYPE_OTP = "otp"
AUTH_TYPE_CREDENTIALS = "credentials"
AUTH_TYPE_TOKEN = "token"

DEFAULT_CALLING_CODE = "+91"
DEFAULT_SCAN_INTERVAL_IDLE = 15
DEFAULT_SCAN_INTERVAL_RUNNING = 5
DEFAULT_MQTT_BACKOFF = 180

PLATFORMS = [
    "sensor",
    "binary_sensor",
    "button",
    "select",
    "switch",
]
