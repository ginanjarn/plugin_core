from functools import wraps
import logging

from ....constant import LOGGING_CHANNEL
from ...message import Response
from ...session import Session

LOGGER = logging.getLogger(LOGGING_CHANNEL)


def client_must_ready(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.client and self.client.is_ready():
            return func(self, *args, **kwargs)
        return None

    return wrapper


def must_initialized(func):
    """exec if initialized"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.session.is_initialized():
            return None
        return func(self, *args, **kwargs)

    return wrapper


class WorkspaceExecuteCommandMixins:

    def workspace_executecommand(self, commands: dict):
        self.message_pool.send_request("workspace/executeCommand", commands)

    def handle_workspace_executecommand(
        self, session: Session, response: Response
    ) -> dict:
        if error := response.error:
            print(error["message"])
        elif result := response.result:
            LOGGER.info(result)

        return None
