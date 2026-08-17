from email.message import EmailMessage

import aiosmtplib
from fastapi.templating import Jinja2Templates
from config import settings

templates = Jinja2Templates(directory="templates")  # However, we would put email templates in an email subdirectory in the templates directory 



async def send_email(to_email : str, subject : str, plain_text : str, html_content : str) -> None:

    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to_email
    message["Subject"] = subject

    message.set_content(plain_text)

    if html_content:
        message.add_alternative(html_content, subtype="html")

    await aiosmtplib.send(message,
                          hostname=settings.mail_server,
                          port=settings.mail_port,
                          username=settings.mail_username if settings.mail_username else None,
                          password=settings.mail_password.get_secret_value() or None ,
                          start_tls=settings.mail_use_tls)




async def send_password_reset_email(to_email: str, username: str, token: str) -> None:
    reset_url = f"{settings.frontend_url}/reset-password?token={token}"

    template = templates.env.get_template("email/password_reset.html")  # Notice that we are using, templates.env.get_template(), instead of TemplateResponse, this is because TemplateResponse uses a request object while emails don't send emails
    html_content = template.render(reset_url=reset_url, username=username) # So we retrieve the template and render it , then also as we did for Template response, we would also pass in the parameters for the templates, hence the reset_url and username parameters and arguments

    plain_text = f"""Hi {username},

You requested to reset your password. Click the link below to set a new password:

{reset_url}

This link will expire in 1 hour.

If you didn't request this, you can safely ignore this email.

Best regards,
The FastAPI Blog Team
"""

    # Note that in the plain text, the place where we said 1 hour, we could have imported from config and used the reset_expire_token_mins with an f string but we left it hardcoded for now, which works as well
    await send_email(
        to_email=to_email,
        subject="Reset Your Password - FastAPI Blog",
        plain_text=plain_text,
        html_content=html_content,
    )