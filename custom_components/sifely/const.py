"""Constants for the Sifely Smart Lock integration."""

DOMAIN = "sifely"

# API base
API_BASE_URL = "https://app-smart-server.sifely.com"

# Auth
API_LOGIN         = "/system/smart/login"
API_REFRESH_TOKEN = "/system/smart/oauthToken"

# Lock CRUD
API_LOCK_LIST       = "/v3/lock/list"
API_LOCK_DETAIL     = "/v3/lock/detail"
API_LOCK_OPEN_STATE = "/v3/lock/queryOpenState"
API_LOCK_UNLOCK     = "/v3/lock/unlock"
API_LOCK_LOCK       = "/v3/lock/lock"

# Passcode
API_PASSCODE_LIST   = "/v3/lock/listKeyboardPwd"
API_PASSCODE_ADD    = "/v3/keyboardPwd/add"
API_PASSCODE_CHANGE = "/v3/keyboardPwd/change"
API_PASSCODE_DELETE = "/v3/keyboardPwd/delete"

# Settings (Sciener/TTLock platform shared endpoints)
API_SET_AUTO_LOCK    = "/v3/lock/setAutoLockTime"
API_UPDATE_SETTING   = "/v3/lock/updateSetting"
API_GET_PASSAGE_MODE = "/v3/lock/getPassageModeConfig"
API_SET_PASSAGE_MODE = "/v3/lock/configPassageMode"

# Gateway
API_LOCK_GATEWAYS   = "/v3/lock/gateways"

# Config keys
CONF_CLIENT_ID     = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_USERNAME      = "username"
CONF_PASSWORD      = "password"

# Lock open state
OPEN_STATE_LOCKED   = 0
OPEN_STATE_UNLOCKED = 1
OPEN_STATE_UNKNOWN  = 2

# Passcode types
PWD_TYPE_PERMANENT = 2
PWD_TYPE_TIMED     = 3

# Operation type: 2 = via gateway (remote)
REMOTE_OP_TYPE = 2

# updateSetting type values (Sciener platform)
# type=6 is sound volume — confirmed from TTLock hass-ttlock open source
SOUND_TYPE_VALUE = 6

# Sound volume levels: 0=off, 1=low, 2=medium-low, 3=medium, 4=medium-high, 5=high
SOUND_VOLUME_OFF         = 0
SOUND_VOLUME_LOW         = 1
SOUND_VOLUME_MEDIUM_LOW  = 2
SOUND_VOLUME_MEDIUM      = 3
SOUND_VOLUME_MEDIUM_HIGH = 4
SOUND_VOLUME_HIGH        = 5

SOUND_VOLUME_OPTIONS = {
    "off":         SOUND_VOLUME_OFF,
    "low":         SOUND_VOLUME_LOW,
    "medium_low":  SOUND_VOLUME_MEDIUM_LOW,
    "medium":      SOUND_VOLUME_MEDIUM,
    "medium_high": SOUND_VOLUME_MEDIUM_HIGH,
    "high":        SOUND_VOLUME_HIGH,
}
SOUND_VOLUME_LABELS = {v: k for k, v in SOUND_VOLUME_OPTIONS.items()}

# Sifely API success code
SIFELY_OK = 200

# Update interval (seconds)
UPDATE_INTERVAL = 30

# Lock entity attributes
ATTR_LOCK_ID        = "lock_id"
ATTR_LOCK_MAC       = "lock_mac"
ATTR_BATTERY        = "battery"
ATTR_HAS_GATEWAY    = "has_gateway"
ATTR_FIRMWARE       = "firmware_revision"
ATTR_LOCK_ALIAS     = "lock_alias"
ATTR_LOCK_NAME      = "lock_name"
ATTR_REMOTE_ENABLED = "remote_enabled"
ATTR_AUTO_LOCK_TIME = "auto_lock_time"
ATTR_IS_FROZEN      = "is_frozen"

# Service names — passcode
SERVICE_ADD_PASSCODE    = "add_passcode"
SERVICE_CHANGE_PASSCODE = "change_passcode"
SERVICE_DELETE_PASSCODE = "delete_passcode"
SERVICE_LIST_PASSCODES  = "list_passcodes"

# Service field names
ATTR_PASSCODE      = "passcode"
ATTR_PASSCODE_NAME = "passcode_name"
ATTR_PASSCODE_ID   = "passcode_id"
ATTR_START_DATE    = "start_date"
ATTR_END_DATE      = "end_date"
ATTR_PASSCODE_TYPE = "passcode_type"

# Token
GRANT_TYPE_REFRESH = "refresh_token"
