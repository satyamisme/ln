from __future__ import annotations
from time import time

from bot import VID_MODE, LOGGER
from bot.helper.listeners import tasks_listener as task
from bot.helper.telegram_helper.message_utils import send_message, delete_message

class SelectMode:
    def __init__(self, listener: task.TaskListener, isLink=False):
        self._isLink = isLink
        self._time = time()
        self._reply = None
        self.listener = listener
        self.mode = 'merge_rmaudio'
        self.newname = ''
        self.extra_data = {}
        self.is_cancelled = False
        LOGGER.info(f"Initialized SelectMode for user {self.listener.user_id}, isLink: {isLink}, mode auto-set to merge_rmaudio")

    async def _send_message(self, text: str):
        try:
            if not self._reply:
                self._reply = await sendMessage(text, self.listener.message)
                LOGGER.info(f"Sent message for mode confirmation to user {self.listener.user_id}")
        except Exception as e:
            LOGGER.error(f"Failed to send message: {e}")
            self.is_cancelled = True

    def _captions(self):
        return (f'<b>VIDEO TOOLS SETTINGS</b>\n'
                f'Mode: <b>{VID_MODE.get(self.mode, "Not Selected")}</b>\n'
                f'Output Name: <b>{self.newname or "Default"}</b>')

    async def list_buttons(self):
        await self._send_message(self._captions())

    async def get_buttons(self):
        LOGGER.info(f"Starting get_buttons for user {self.listener.user_id}")
        try:
            await self.list_buttons()
            await deleteMessage(self._reply)
            LOGGER.info(f"Mode auto-continued: {self.mode}, name: {self.newname}, extra: {self.extra_data}")
            return [self.mode, self.newname, self.extra_data]
        except Exception as e:
            LOGGER.error(f"Error in get_buttons: {e}", exc_info=True)
            self.is_cancelled = True
            return None