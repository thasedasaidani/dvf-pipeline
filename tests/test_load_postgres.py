from src.load.load_postgres import JDBC_PACKAGE, jdbc_config, spark_jdbc_conf


def test_jdbc_config_depuis_env(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_PORT", "5544")
    monkeypatch.setenv("POSTGRES_DB", "dvf_test")
    monkeypatch.setenv("POSTGRES_USER", "alice")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    url, props = jdbc_config()
    assert url == "jdbc:postgresql://db:5544/dvf_test"
    assert props["user"] == "alice" and props["password"] == "secret"
    assert props["driver"] == "org.postgresql.Driver"


def test_driver_maven_par_defaut(monkeypatch):
    monkeypatch.delenv("SPARK_JARS", raising=False)
    assert spark_jdbc_conf() == {"spark.jars.packages": JDBC_PACKAGE}


def test_driver_jar_local(monkeypatch):
    monkeypatch.setenv("SPARK_JARS", "/chemin/postgresql.jar")
    assert spark_jdbc_conf() == {"spark.jars": "/chemin/postgresql.jar"}
