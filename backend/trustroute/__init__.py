"""TrustRoute project package.

PyMySQL is used as a pure-Python MySQL driver so no C compiler / MySQL client
headers are needed on Windows. If you prefer `mysqlclient`, install it and
this shim becomes a no-op.
"""
try:
    import pymysql

    pymysql.version_info = (2, 2, 1, "final", 0)  # satisfy Django's driver version check
    pymysql.install_as_MySQLdb()
except ImportError:  # pragma: no cover
    pass
