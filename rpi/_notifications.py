import ssl
from abc import ABC, abstractmethod
from dataclasses import asdict
from email.message import EmailMessage
from smtplib import SMTP

from . import logging
from ._config import GmailConfig
from ._events import Event

logger = logging.getLogger("notification-service")

MESSAGE = ("Sensor alert! A threshold has been crossed at {recording_time}, "
           "value recorded: {value}, threshold {threshold_name} bound was: "
           "{threshold}{unit}.")


class Notification(ABC):
    def __init__(self, event: Event) -> None:
        self.event = event

    @abstractmethod
    def send(self) -> None:
        ...

    @property
    def message(self) -> str:
        return MESSAGE.format(threshold_name=self.event.threshold.name,
                              value=str(self.event.measure),
                              unit=self.event.measure.unit,
                              **asdict(self.event))


class Gmail(Notification):
    def _build_message(self) -> EmailMessage:
        msg = EmailMessage()
        msg.add_header("From", GmailConfig.SENDER)
        msg.add_header("To", GmailConfig.RECIPIENTS)
        msg.add_header("Subject", GmailConfig.SUBJECT)
        msg.set_content(self.message)
        return msg

    def send(self) -> None:
        message = self._build_message()
        context = ssl.create_default_context()
        with SMTP("smtp.gmail.com", 587, timeout=5) as server:
            server.starttls(context=context)
            server.login(GmailConfig.USERNAME, GmailConfig.PASSWORD)
            server.send_message(message)
        logger.info("Sent email notification for event %s", id(self.event))
