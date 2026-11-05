# Image Airflow + Java + PySpark, pour exécuter les scripts du projet dans les tâches du DAG
FROM apache/airflow:3.3.2-python3.12

USER root
# Java est nécessaire à Spark ; default-jre-headless crée /usr/lib/jvm/default-java
RUN apt-get update \
 && apt-get install -y --no-install-recommends default-jre-headless curl \
 && apt-get clean && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/default-java

# Driver JDBC PostgreSQL intégré à l'image (pas de téléchargement à chaque exécution)
RUN mkdir -p /opt/jars \
 && curl -fsSL -o /opt/jars/postgresql.jar \
    https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.4/postgresql-42.7.4.jar
ENV SPARK_JARS=/opt/jars/postgresql.jar

USER airflow
COPY requirements-airflow.txt /tmp/requirements-airflow.txt
RUN pip install --no-cache-dir -r /tmp/requirements-airflow.txt
