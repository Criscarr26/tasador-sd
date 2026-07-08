# Tasador SD API — container image for Hugging Face Spaces (Docker SDK)
# or any container host. Build from the repo root:
#   docker build -t tasador-api .
FROM python:3.11-slim

WORKDIR /app

COPY packages/core_py packages/core_py
COPY apps/api apps/api
COPY ml/training/models ml/training/models

RUN pip install --no-cache-dir \
      scikit-learn==1.9.0 pandas==3.0.3 joblib==1.5.3 fastapi uvicorn \
 && pip install --no-cache-dir -e packages/core_py

ENV MODEL_DIR=/app/ml/training/models

# 7860 is the port Hugging Face Spaces expects.
EXPOSE 7860
CMD ["uvicorn", "main:app", "--app-dir", "apps/api", "--host", "0.0.0.0", "--port", "7860"]
