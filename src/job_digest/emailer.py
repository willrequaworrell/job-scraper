from __future__ import annotations


class ResendEmailer:
    def __init__(self, api_key: str) -> None:
        try:
            import resend
        except ImportError as exc:
            raise RuntimeError("resend is required for email delivery. Install project dependencies first.") from exc
        resend.api_key = api_key
        self.resend = resend

    def send(self, *, sender: str, recipient: str, subject: str, html: str) -> str:
        response = self.resend.Emails.send(
            {
                "from": sender,
                "to": [recipient],
                "subject": subject,
                "html": html,
            }
        )
        return str(response.get("id", ""))
