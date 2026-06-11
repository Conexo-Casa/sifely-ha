"""Constants for the Sifely Smart Lock integration."""

DOMAIN = "sifely"

# API
API_BASE_URL = "https://app-smart-server.sifely.com"
API_LOGIN          = "/system/smart/login"
API_REFRESH_TOKEN  = "/system/smart/oauthToken"
API_LOCK_LIST      = "/v3/lock/list"
API_LOCK_DETAIL    = "/v3/lock/detail"
API_LOCK_OPEN_STATE = "/v3/lock/queryOpenState"
API_LOCK_UNLOCK    = "/v3/lock/unlock"
API_LOCK_LOCK      = "/v3/lock/lock"
API_GATEWAY_DETAILS = "/v3/gateway/detail"
API_LOCK_GATEWAYS  = "/v3/lock/gateways"

# Config entry keys
CONF_CLIENT_ID     = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_USERNAME      = "username"
CONF_PASSWORD      = "password"

# Token storage
ATTR_ACCESS_TOKEN  = "access_token"
ATTR_REFRESH_TOKEN = "refresh_token"
ATTR_TOKEN_EXPIRES = "token_expires"

# Lock open state values from API: 0=locked, 1=unlocked, 2=unknown
OPEN_STATE_LOCKED   = 0
OPEN_STATE_UNLOCKED = 1
OPEN_STATE_UNKNOWN  = 2

# Update interval (seconds)
UPDATE_INTERVAL = 30

# Attributes
ATTR_LOCK_ID       = "lock_id"
ATTR_LOCK_MAC      = "lock_mac"
ATTR_BATTERY       = "battery"
ATTR_HAS_GATEWAY   = "has_gateway"
ATTR_FIRMWARE      = "firmware_revision"
ATTR_LOCK_ALIAS    = "lock_alias"
ATTR_LOCK_NAME     = "lock_name"
ATTR_REMOTE_ENABLED = "remote_enabled"
ATTR_AUTO_LOCK_TIME = "auto_lock_time"
ATTR_IS_FROZEN     = "is_frozen"

# Token grant types
GRANT_TYPE_CODE    = "authorization_code"
GRANT_TYPE_REFRESH = "refresh_token"
