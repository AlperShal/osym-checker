# Libraries
import requests
from requests import adapters
from urllib3 import poolmanager
import ssl
import smtplib
import email.message
from email.utils import formatdate
from email.mime.text import MIMEText

# Variables
resultPageURL: str = "https://sonuc.osym.gov.tr/Sorgu.aspx"
possibleResultIDs: list[str] = ["9905", "9906", "9912", "9913", "9914"] # Go to [this](https://sonuc.osym.gov.tr/) webpage and try to find possible result IDs by checking last announced exams' IDs.

tckn: int = 11111111111 # T.C. ID
ais_password: str = "hunter2" # Plaintext 

smtp_server = "mail.example.com"
smtp_port = 587  # For TLS (STARTTLS)
smtp_sender = "alper@example.com"
smtp_password = "hunter2"
mail_receiver = "alper@example.com"


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

# NOTE: We are supressing SSL because the SSL version Python 3.12 using (OpenSSL 3.x) is not able to make a proper SSL handshake with ÖSYM. This is definitely not the safest method. Your credentials MAY get stolen. Use at your own risk.

for resultID in possibleResultIDs:
    url = resultPageURL
    params = {"SonucID": resultID, "Cache": "0"}
    payload = {"tc": tckn, "sifre": ais_password}
    response = ssl_supressed_session().get(url=url, params=params, data=payload, verify=False)
    if len(response.content) == 819: # "No such result or is inactive." page.
        print(f"{resultID} is an inactive result ID. Trying next ID if available.")
    elif len(response.content) == 805: # "TCKN or password is incorrect." page.
        print("Your credentials are wrong.")
    elif len(response.content) == 969: # "You do not have a result record." page.
        print(f"Looks like results of {resultID} got announced but you have not participated in it. Please remove this ID from possibleResultIDs to not spam ÖSYM with unnecessary requests. This may get you banned at some point.")
    else: # Assuming any other content length will be the result page as result pages don't have a fixed length.
        resultHTML = response.content.decode(encoding="windows-1254")
        # Save result to file
        with open(f"{resultID}_{tckn}.html", "a") as file:
            file.write(resultHTML)
            file.write("\n\n")
        # Save result to logs
        print("### START OF RESULT ###")
        print(resultHTML)
        print("### END OF RESULT ###")
        # Send result to e-mail
        msg = MIMEText(resultHTML, "html")
        msg['Subject'] = f"ÖSYM results are announced for {resultID}!"
        msg['From'] = smtp_sender
        msg['To'] = mail_receiver
        msg["Date"] = formatdate(localtime=True)
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(smtp_sender, smtp_password)
            server.sendmail(smtp_sender, mail_receiver, msg=msg.as_string())
            print(f"Sent the result to {mail_receiver}!")
        print(f"While not being 100% sure, looks like results for {resultID} is announced. You can check your email or {resultID}_{tckn}.html file. I suggest you to check your email as it will be properly formatted as HTML.")