# Frontend: Streamlit chat UI
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    streamlit \
    requests \
    st-flexible-callout-elements

COPY streamlit_app/ ./streamlit_app/

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "streamlit_app/app.py", "--server.address=0.0.0.0", "--server.port=8501"]