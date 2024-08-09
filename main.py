# Libraries
import os
import requests
from requests import adapters
from urllib3 import poolmanager
import ssl
from bs4 import BeautifulSoup
import smtplib
import email.message
from email.utils import formatdate
from email.mime.text import MIMEText

# Variables
announcedResultsURL: str = "https://sonuc.osym.gov.tr/"
resultPageURL: str = "https://sonuc.osym.gov.tr/Sorgu.aspx"

try: 
    tckn = int(os.environ["TCKN"])
    ais_password = os.environ["AIS_PASSWORD"]
    smtp_server = os.environ["SMTP_SERVER"] 
    smtp_port = int(os.environ["SMTP_PORT"])
    smtp_sender = os.environ["SMTP_SENDER"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    mail_receiver = os.environ["MAIL_RECEIVER"]
except KeyError:
    print("One or more environment variables are missing. Using the credentials in the main.py file.")
    tckn: int = 11111111111 # T.C. ID
    ais_password: str = "hunter2" # Plaintext 

    smtp_server = "mail.example.com"
    smtp_port = 587  # For TLS (STARTTLS)
    smtp_sender = "AlperShal@example.com"
    smtp_password = "hunter2"
    mail_receiver = "AlperShal@example.com"


# Magic
class CustomHttpAdapter (adapters.HTTPAdapter):
    def __init__(self, ssl_context=None, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = poolmanager.PoolManager(
            num_pools=connections, maxsize=maxsize,
            block=block, ssl_context=self.ssl_context)

def ssl_supressed_session():
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    # to bypass verification after accepting Legacy connections
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    # accepting legacy connections
    ctx.options |= 0x4    
    session = requests.Session()
    session.mount('https://', CustomHttpAdapter(ctx))
    return session

def send_email(subject, content, isHTML = 0):
    if isHTML == 0:
        msg = MIMEText(content)
    else:
        msg = MIMEText(content, "html")
    msg['Subject'] = subject
    msg['From'] = smtp_sender
    msg['To'] = mail_receiver
    msg["Date"] = formatdate(localtime=True)
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()
        server.login(smtp_sender, smtp_password)
        server.sendmail(smtp_sender, mail_receiver, msg=msg.as_string())
        print(f"Sucessfully sent the email to {mail_receiver}!")


# NOTE: We are supressing SSL (not for SMTP connection) because the SSL version Python 3.12 (and probably the upcoming versions) using (OpenSSL 3.x) is not able to make a proper SSL handshake with ÖSYM. This is probably not the safest method. Your credentials MAY get stolen. Use at your own risk.
html = ssl_supressed_session().get(url=announcedResultsURL, verify=False).text

soup = BeautifulSoup(html, 'html.parser')
lastAnnouncedResultElement = soup.find("a")
lastAnnouncedResultID = lastAnnouncedResultElement["href"].split("=")[1]  # type: ignore
lastAnnouncedResultName = lastAnnouncedResultElement.contents # type: ignore

with open("results/last_checked_result.txt", "r") as file:
    lastSavedResultID = file.read()

if lastSavedResultID == "":
    print("Looks like you are running this script for the first time. Saving the last announced ID and not running a result check.")
    with open("results/last_checked_result.txt", "w") as file:
        file.write(lastAnnouncedResultID)
elif lastSavedResultID == lastAnnouncedResultID:
    print("No new announcement. No action is being taken.")
else:
    with open("results/last_checked_result.txt", "w") as file:
        file.write(lastAnnouncedResultID)
    print("New announcement. Running a result check.")
    params = {"SonucID": lastAnnouncedResultID, "Cache": "0"}
    payload = {"tc": tckn, "sifre": ais_password}
    response = ssl_supressed_session().get(url=resultPageURL, params=params, data=payload, verify=False)
    if len(response.content) == 819: # "No such result or is inactive." page.
        print(f"{lastAnnouncedResultID} is an inactive result ID. Trying next ID if available.")
    elif len(response.content) == 805: # "TCKN or password is incorrect." page.
        print(f"Your credentials are wrong. This script will not run another check for this result. Don't forget to check it yourself from https://sonuc.osym.gov.tr/Sorgu.aspx?SonucID={lastAnnouncedResultID} address.")
        send_email("[ÖSYM-Checker] Your credentials are wrong!",
                   f"[{lastAnnouncedResultID}] {lastAnnouncedResultName} got announced but your credentials are wrong. This script will not run another check for this result. Don't forget to check it yourself from https://sonuc.osym.gov.tr/Sorgu.aspx?SonucID={lastAnnouncedResultID} address. If you have not participated in this exam, you still shouldn't get a wrong credentials error. Please check your credentials to be able to get correct results from the one you are expecting.",
                   0)
    elif len(response.content) == 969: # "You do not have a result record." page.
        print(f"Looks like results of [{lastAnnouncedResultID}] {lastAnnouncedResultName} got announced but you have not participated in it. Sending an email to let you know that this script is functioning properly.")
        send_email("[ÖSYM-Checker] An result you have not participated in is announced.",
                   f"Don't hype! This is just a notification email to let you know the script is working fine. The new announced result is [{lastAnnouncedResultID}] {lastAnnouncedResultName}. If this was an exam you have participated in, you can re-check youself from https://sonuc.osym.gov.tr/Sorgu.aspx?SonucID={lastAnnouncedResultID} address.",
                   0)
    else: # Assuming any other content length will be the result page as result pages don't have a fixed length.
        resultHTML = response.content.decode(encoding="windows-1254")
        # Print result to logs
        print("### START OF RESULT ###")
        print(resultHTML)
        print("### END OF RESULT ###")
        # Save result to file
        with open(f"results/{lastAnnouncedResultID}_{tckn}.html", "a") as file:
            file.write(resultHTML)
            file.write("\n\n")
        # Send result to e-mail
        send_email(f"[ÖSYM-Checker] {lastAnnouncedResultName} has announced!",
                   resultHTML+f"<b>ÖSYM-Checker: If this is not a result page, I am deeply sorry for the inconvience. If this is the result page you were seeking for, you will need to check it yourself from https://sonuc.osym.gov.tr/Sorgu.aspx?SonucID={lastAnnouncedResultID} address. If not, as long as you continue to run the script, results for upcoming announcements will be sent. You don't have to do anything. And, again, if this is not a result page, please make a bug report at <a href='https://github.com/AlperShal/osym-checker/issues/new'>GitHub Issues</a> with what has been mailed to you. (Check if it has any personal information and don't forget to remove if so.)</b>",
                   1)
        print(f"While not being 100% sure, looks like results for [{lastAnnouncedResultID}] {lastAnnouncedResultName} are announced. You can check your email, results/{lastAnnouncedResultID}_{tckn}.html file or the logs. I suggest you to check your email as it will be properly rendered as HTML.")
