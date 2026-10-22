import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, render_template, request

# Read GMAIL_USER and GMAIL_APP_PASSWORD from the .env file next to this script
load_dotenv(Path(__file__).parent / ".env")
GMAIL_USER = os.environ.get("GMAIL_USER", "")
# Google shows the app password in groups of four, the spaces are not part of it
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
SIGNATURE = "Met vriendelijke groet,\nJan Willem Schipper"

app = Flask(__name__)
app.secret_key = os.urandom(24)  # needed for flash messages


def split_addresses(text: str) -> list[str]:
    """Turn "a@x.nl, b@x.nl" into ["a@x.nl", "b@x.nl"]."""
    return [address.strip() for address in text.split(",") if address.strip()]


@app.route("/")
def index() -> str:
    return render_template("webmail.html", sender=GMAIL_USER, signature=SIGNATURE, form={})


@app.route("/send", methods=["POST"])
def send() -> str:
    form = request.form
    to = split_addresses(form.get("to", ""))
    cc = split_addresses(form.get("cc", ""))
    bcc = split_addresses(form.get("bcc", ""))
    signature = form.get("signature", "")

    body = form.get("body", "")
    if form.get("use_signature"):
        body = body + "\n\n-- \n" + signature

    message = EmailMessage()
    message["From"] = GMAIL_USER
    message["To"] = ", ".join(to)
    if cc:
        message["Cc"] = ", ".join(cc)
    message["Subject"] = form.get("subject", "")
    message.set_content(body)

    for file in request.files.getlist("attachments"):
        if file.filename:
            message.add_attachment(
                file.read(),
                maintype="application",
                subtype="octet-stream",
                filename=file.filename,
            )

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            # BCC addresses are only passed here, never as a header, so they stay hidden
            smtp.send_message(message, to_addrs=to + cc + bcc)
    except (smtplib.SMTPException, OSError) as error:
        flash(f"Verzenden mislukt: {error}", "error")
        # Show the form again with everything the user typed
        return render_template("webmail.html", sender=GMAIL_USER, signature=signature, form=form)

    flash("Bericht verzonden.", "success")
    return render_template("webmail.html", sender=GMAIL_USER, signature=SIGNATURE, form={})


if __name__ == "__main__":
    app.run(debug=True)
