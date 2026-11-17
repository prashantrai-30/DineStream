
# Airflow 3.x + Snowflake + FAB + Groq + Gemini + dbt
FROM apache/airflow:3.0.3

# Install providers and AI SDKs
RUN pip install --no-cache-dir \
      "apache-airflow==3.0.3" \
      apache-airflow-providers-snowflake \
      apache-airflow-providers-fab \
      openai \
      google-genai

# Install dbt in a separate virtual environment
RUN python -m venv /opt/airflow/dbt_venv && \
    /opt/airflow/dbt_venv/bin/pip install --no-cache-dir \
      "dbt-snowflake==1.8.*"
