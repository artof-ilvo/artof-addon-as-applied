# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV ILVO_PATH=/var/lib/ilvo
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# artof_utils is installed from the named build context "artof_utils" (a local checkout):
#   docker build --build-context artof_utils=../../artof-utils -t axelwillekens/artof-taskmap-addon:dev .
COPY --from=artof_utils . /tmp/artof_utils
RUN pip install --no-cache-dir /tmp/artof_utils && rm -rf /tmp/artof_utils

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY taskmap /app/taskmap

CMD ["python", "-m", "taskmap.main"]
