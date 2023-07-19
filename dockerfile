FROM python:3.9

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt
RUN pip install gunicorn
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./ /code

WORKDIR /code

EXPOSE 8000

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "website:create_app()"]