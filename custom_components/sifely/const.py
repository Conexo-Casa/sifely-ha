"""Constants for the Sifely Smart Lock integration."""

DOMAIN = "sifely"

# API base
API_BASE_URL = "https://app-smart-server.sifely.com"

# Auth
API_LOGIN         = "/system/smart/login"
API_REFRESH_TOKEN = "/system/smart/oauthToken"

# Lock
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

# Gateway
API_GATEWAY_DETAILS = "/v3/gateway/detail"
API_LOCK_GATEWAYS   = "/v3/lock/gateways"

# Config entry keys
CONF_CLIENT_ID     = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_USERNAME      = "username"
CONF_PASSWORD      = "password"

# Lock open state: 0=locked, 1=unlocked, 2=unknown
OPEN_STATE_LOCKED   = 0
OPEN_STATE_UNLOCKED = 1
OPEN_STATE_UNKNOWN  = 2

# Passcode types
PWD_TYPE_PERMANENT = 2
PWD_TYPE_TIMED     = 3

# addType / changeType / deleteType 2 = via gateway (remote)
REMOTE_OP_TYPE = 2

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

# Service names
SERVICE_ADD_PASSCODE    = "add_passcode"
SERVICE_CHANGE_PASSCODE = "change_passcode"
SERVICE_DELETE_PASSCODE = "delete_passcode"
SERVICE_LIST_PASSCODES  = "list_passcodes"

# Service field names
ATTR_PASSCODE         = "passcode"
ATTR_PASSCODE_NAME    = "passcode_name"
ATTR_PASSCODE_ID      = "passcode_id"
ATTR_START_DATE       = "start_date"
ATTR_END_DATE         = "end_date"
ATTR_PASSCODE_TYPE    = "passcode_type"

# Token
GRANT_TYPE_REFRESH = "refresh_token"

# Sifely API success code (actual live value)
SIFELY_OK = 200
