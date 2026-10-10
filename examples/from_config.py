"""Configure log4p from a YAML file, then log through the hierarchy."""

import os

from log4p import config, getLogger

config.fileConfig(os.path.join(os.path.dirname(__file__), "log4p.yaml"))

# myapp -> console at DEBUG
getLogger("myapp").debug("starting up")

# myapp.db -> rotating JSON file at INFO, does not also hit console
getLogger("myapp.db").info("select * from orders")
getLogger("myapp.db.pool").debug("pool warmed")  # inherits myapp.db's INFO -> suppressed

# root -> console at WARN
getLogger("other").warning("something to watch")
