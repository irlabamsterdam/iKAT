FROM python:3.9-bullseye

WORKDIR /app

COPY requirements.txt /app

RUN pip3 install -r /app/requirements.txt
RUN apt-get update && apt-get install -y openjdk-17-jdk-headless

COPY ikat_tools.py spacy_passage_chunker.py /app/

ENTRYPOINT ["python3", "/app/ikat_tools.py"]
