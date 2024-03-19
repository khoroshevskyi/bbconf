PKG_NAME = "bbconf"


# config file constants
CFG_PATH_KEY = "path"
CFG_PATH_REGION2VEC_KEY = "region2vec"
CFG_PATH_VEC2VEC_KEY = "vec2vec"
CFG_PATH_TEXT2VEC_KEY = "text2vec"

CFG_DATABASE_KEY = "database"
CFG_DATABASE_NAME_KEY = "name"
CFG_DATABASE_HOST_KEY = "host"
CFG_DATABASE_PORT_KEY = "port"
CFG_DATABASE_PASSWORD_KEY = "password"
CFG_DATABASE_USER_KEY = "user"

CFG_QDRANT_KEY = "qdrant"

CFG_QDRANT_HOST_KEY = "host"
CFG_QDRANT_PORT_KEY = "port"
CFG_QDRANT_API_KEY = "api_key"
CFG_QDRANT_COLLECTION_NAME_KEY = "collection"

CFG_SERVER_KEY = "server"
CFG_SERVER_HOST_KEY = "host"
CFG_SERVER_PORT_KEY = "port"

CFG_REMOTE_KEY = "remotes"

DB_DEFAULT_HOST = "localhost"
DB_DEFAULT_USER = "postgres"
DB_DEFAULT_PASSWORD = "bedbasepassword"
DB_DEFAULT_NAME = "postgres"
DB_DEFAULT_PORT = 5432
DB_DEFAULT_DIALECT = "postgresql"

CFG_ACCESS_METHOD_KEY = "access_methods"

DEFAULT_QDRANT_HOST = "localhost"
DEFAULT_QDRANT_PORT = 6333
DEFAULT_QDRANT_COLLECTION_NAME = "bedbase"
DEFAULT_QDRANT_API_KEY = None

SERVER_DEFAULT_PORT = 80
SERVER_DEFAULT_HOST = "0.0.0.0"

DEFAULT_SECTION_VALUES = {
    CFG_DATABASE_KEY: {
        CFG_DATABASE_USER_KEY: DB_DEFAULT_USER,
        CFG_DATABASE_PASSWORD_KEY: DB_DEFAULT_PASSWORD,
        CFG_DATABASE_NAME_KEY: DB_DEFAULT_NAME,
        CFG_DATABASE_PORT_KEY: DB_DEFAULT_PORT,
        CFG_DATABASE_HOST_KEY: DB_DEFAULT_HOST,
    },
    CFG_SERVER_KEY: {
        CFG_SERVER_HOST_KEY: SERVER_DEFAULT_HOST,
        CFG_SERVER_PORT_KEY: SERVER_DEFAULT_PORT,
    },
    CFG_QDRANT_KEY: {
        CFG_QDRANT_HOST_KEY: DEFAULT_QDRANT_HOST,
        CFG_QDRANT_PORT_KEY: DEFAULT_QDRANT_PORT,
        CFG_QDRANT_COLLECTION_NAME_KEY: DEFAULT_QDRANT_COLLECTION_NAME,
        CFG_QDRANT_API_KEY: DEFAULT_QDRANT_API_KEY,
    },
}


DEFAULT_TEXT2VEC_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_VEC2VEC_MODEL = "databio/v2v-MiniLM-v2-ATAC-hg38"
DEFAULT_REGION2_VEC_MODEL = "databio/r2v-ChIP-atlas-hg38"
