import json
import os
import requests
import time
import smtplib
from datetime import datetime
from dateutil.parser import parse
from requests import get
from os.path import basename
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
from wand.image import Image as wi


# downloads the Periscope pdf for the dashboard with given options
def download_pdf(file_name, options):
    # sample to illustrate structure of the options, taken from https://doc.periscopedata.com/article/render-api
    # dashboard_id is the only mandatory parameter, rest are optional
    # {
    #     "dashboard_id": 1234,
    #     "daterange": {"start": "2015-01-01", "end": "2015-01-05"},
    #     "aggregation": "daily",
    #     "filters": [{"name": "AGE", "value": [1, 2]}],
    #     "dashboard_ts": 1446069112
    # }

    data = {
        'data': options
    }

    s3_url = pd_url(data)
    while int(requests.get(s3_url, stream=True).headers['Content-length']) < 100:
        # PDF needs time to build and will just say "screenshot not ready" until it's done
        time.sleep(1)

    download(s3_url, file_name)
    return file_name


# gets the URL to the Periscope pdf
def pd_url(options):
    url = 'https://app.periscopedata.com/api/v1/screenshot_requests'
    api_key = 'api_key'
    site_name = 'site-name'
    headers = {
        'Content-Type': 'application/json',
        'HTTP-X-PARTNER-AUTH': f'{site_name}:{api_key}'
    }
    data = json.dumps(options)
    response = requests.post(url, headers=headers, data=data)
    print(data)
    return json.loads(response.text)['url']


# helper function to create daterange filter parameters, if needed
def create_daterange(start, end):
    # pass in start and end daterange values. parse() is somewhat robust so you can enter dates in (most) common formats

    # USAGE: `render_api_body = create_render_dict()`
    # `render_api_body['daterange'] = create_daterange("Jan 1st, 2018", "Jan 29, 2018")`

    try:
        starting = parse(start)
        ending = parse(end)
    except ValueError:
        raise Exception(
            "Date is not parseable. Enter one of the following formats 'YYYY-MM-DD' or 'MM/DD/YYYY' or 'Jan 1st 2018'")
    except OverflowError as err:
        raise Exception(err)
    return dict(start=str(starting.strftime('%Y-%m-%d')), end=str(ending.strftime('%Y-%m-%d')))


# downloads a file
def download(url, file_name):
    with open(file_name, "wb") as f:
        response = get(url)
        f.write(response.content)


# sends an email
# def send_mail(send_from, send_to, subject, text, files=None,
#               server="127.0.0.1"):
def send_mail(send_from, send_to, subject, text, files=None):
    # assert isinstance(send_to, list)
    msg = MIMEMultipart()
    msg['From'] = send_from
    # msg['To'] = COMMASPACE.join(send_to)
    msg['To'] = send_to
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject

    msg.attach(MIMEText('<b>Hi, </b> here is your dashboard.<br><img src="cid:image1"><br>Thanks!', 'html'))

    for f in files or []:
        with open(f, "rb") as fil:
            part = MIMEApplication(
                fil.read(),
                Name=basename(f)
            )
    # After the file is closed
    part['Content-Disposition'] = 'attachment; filename="%s"' % basename(f)
    msg.attach(part)

    # This example assumes the image is in the current directory
    fp = open('1.jpg', 'rb')
    msgImage = MIMEImage(fp.read())
    fp.close()
    msgImage.add_header('Content-ID', '<image1>')
    msg.attach(msgImage)
    # use your own smtp server
    # smtp = smtplib.SMTP(server)

    # uses gmail smtp servers
    smtp = smtplib.SMTP('smtp.gmail.com', 587)
    smtp.starttls()
    smtp.login('email@gmail.com', 'password')
    smtp.sendmail(send_from, send_to, msg.as_string())
    smtp.close()


# who the dashboards will be sent to and how they will be filtered
email_recipients = [
    # {'email': 'user1@company.com', 'filters': [{'name': 'user_id', 'value': '300'}]}
    # {'email': 'user2@company.com', 'filters': [{'name': 'user_id', 'value': '2'}]},
    # {'email': 'user3@company.com', 'filters': [{'name': 'user_id', 'value': '3'}]}
]

dashboard_id = 'dashboard_id'
file = 'dashboard.pdf'

for recipient in email_recipients:
    # get filter values
    parameters = {
        'dashboard_id': dashboard_id,
        'filters': recipient['filters'],
        'dashboard_ts': int(time.time())
    }

    # download dashboard as pdf
    pdf = download_pdf(file, parameters)

    # convert pdf to image
    i = 1
    # change resolution size to fit your needs
    image = wi(filename=file, resolution=50)
    pdfImage = image.convert("jpeg")
    for img in pdfImage.sequence:
        page = wi(image=img)
        page.save(filename=str(i)+".jpg")
        i += 1

    # send it
    send_mail(send_from='reporting@company.com',
              send_to=recipient['email'],
              subject='Updated Dashboard',
              text='Dashboard is attached!',
              files=[pdf])
