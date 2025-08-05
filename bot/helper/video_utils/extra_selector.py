from __future__ import annotations
from time import time

from bot import LOGGER, VID_MODE, config_dict
from bot.helper.ext_utils.status_utils import get_readable_file_size
from bot.helper.telegram_helper.message_utils import sendMessage, deleteMessage
from bot.helper.video_utils import executor as exc

class ExtraSelect:
    def __init__(self, executor: exc.VidEcxecutor):
        self._listener = executor.listener
        self._time = time()
        self._reply = None
        self.executor = executor
        self.is_cancelled = False
        LOGGER.info(f"Initialized ExtraSelect for {self.executor.mode} (MID: {self.executor.listener.mid})")

    async def _send_message(self, text: str):
        try:
            if not self._reply:
                LOGGER.info(f"Sending initial ExtraSelect message for {self.executor.mode}")
                self._reply = await sendMessage(text, self._listener.message)
        except Exception as e:
            LOGGER.error(f"Failed to send message: {e}")
            self.is_cancelled = True

    def _format_stream_details(self, stream):
        codec_type = stream.get('codec_type', 'unknown')

        if codec_type == 'video':
            codec_name = stream.get('codec_name', 'Unknown')
            height = stream.get('height')
            resolution = f"{height}p" if height else "Unknown Resolution"
            bitrate = stream.get('bit_rate')
            bitrate_str = f", {int(bitrate) // 1000} kbps" if bitrate else ""
            return f"{codec_name.upper()}, {resolution}{bitrate_str}"

        elif codec_type == 'audio':
            codec_name = stream.get('codec_name', 'Unknown')
            lang = stream.get('tags', {}).get('language', 'und').upper()
            channels = stream.get('channel_layout', 'N/A')
            bitrate = stream.get('bit_rate')
            bitrate_str = f", {int(bitrate) // 1000} kbps" if bitrate else ""
            return f"{codec_name.upper()}, {lang}, {channels}{bitrate_str}"

        elif codec_type == 'subtitle':
            codec_name = stream.get('codec_name', 'Unknown')
            lang = stream.get('tags', {}).get('language', 'und').upper()
            return f"{codec_name.upper()}, {lang}"

        elif stream.get('disposition', {}).get('attached_pic'):
            return "Cover Art (Attached Picture)"

        else:
            return f"{codec_type.title()} Stream"

    def _is_language_match(self, lang, language_list):
        """Check if a language tag matches any in the given list."""
        if not lang:
            return False
        lang = lang.lower()
        return any(tag.strip().lower() in lang for tag in language_list if isinstance(tag, str))

    def _get_language_lists(self):
        supported = config_dict.get('SUPPORTED_LANGUAGES', 'tel,te,తెలుగు,hin,hi').split(',')
        if not supported or not any(isinstance(tag, str) for tag in supported):
            LOGGER.warning("SUPPORTED_LANGUAGES invalid or missing, using default: tel,te,తెలుగు,hin,hi")
            supported = ['tel', 'te', 'తెలుగు', 'hin', 'hi']

        telugu_tags = [tag for tag in supported if tag in ['tel', 'te', 'తెలుగు']]
        hindi_tags = [tag for tag in supported if tag in ['hin', 'hi']]
        return telugu_tags, hindi_tags

    async def streams_select(self, streams=None):
        if 'streams' not in self.executor.data:
            if not streams:
                self.executor.data = {'streams': {}, 'streams_to_remove': []}
                return "No streams found in file."

            self.executor.data = {'streams': {}, 'streams_to_remove': []}
            for stream in streams:
                index = stream['index']
                self.executor.data['streams'][index] = stream
                self.executor.data['streams'][index]['details'] = self._format_stream_details(stream)

        streams_dict = self.executor.data['streams']

        kept_video = []
        kept_audio = []
        kept_attachments = []
        removed_audio = []
        removed_subtitle = []

        telugu_tags, hindi_tags = self._get_language_lists()

        has_telugu = any(s.get('codec_type') == 'audio' and self._is_language_match(s.get('tags', {}).get('language'), telugu_tags) for s in streams_dict.values())
        has_hindi = any(s.get('codec_type') == 'audio' and self._is_language_match(s.get('tags', {}).get('language'), hindi_tags) for s in streams_dict.values())

        for key, stream in streams_dict.items():
            codec_type = stream.get('codec_type', 'unknown')

            if codec_type == 'video':
                kept_video.append(f"  └ {stream['details']}")
            elif stream.get('disposition', {}).get('attached_pic'):
                kept_attachments.append(f"  └ {stream['details']}")
            elif codec_type == 'subtitle':
                self.executor.data['streams_to_remove'].append(key)
                removed_subtitle.append(f"  └ {stream['details']}")
            elif codec_type == 'audio':
                lang = stream.get('tags', {}).get('language', '')
                if has_telugu:
                    if self._is_language_match(lang, telugu_tags):
                        kept_audio.append(f"  └ {stream['details']}")
                    else:
                        self.executor.data['streams_to_remove'].append(key)
                        removed_audio.append(f"  └ {stream['details']}")
                elif has_hindi:
                    if self._is_language_match(lang, hindi_tags):
                        kept_audio.append(f"  └ {stream['details']}")
                    else:
                        self.executor.data['streams_to_remove'].append(key)
                        removed_audio.append(f"  └ {stream['details']}")
                else:
                    kept_audio.append(f"  └ {stream['details']}")

        # Build the message
        msg = "🎬 **Analyzing Streams**\n"
        msg += "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
        msg += f"**File:** `{self.executor.name}`\n\n"

        msg += "**✅ Tracks to Keep:**\n"
        msg += "- - - - - - - - - - - - - - - - -\n"
        if kept_video:
            msg += "**📹 Video:**\n" + "\n".join(kept_video) + "\n"
        if kept_attachments:
            msg += "**🖼️ Attachment:**\n" + "\n".join(kept_attachments) + "\n"
        if kept_audio:
            msg += "**🔊 Audio:**\n" + "\n".join(kept_audio) + "\n"

        msg += "\n**🚫 Tracks to Remove:**\n"
        msg += "- - - - - - - - - - - - - - - - -\n"
        if removed_audio:
            msg += "**🔊 Audio:**\n" + "\n".join(removed_audio) + "\n"
        if removed_subtitle:
            msg += "**📖 Subtitle:**\n" + "\n".join(removed_subtitle) + "\n"

        msg += "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"

        self.executor.event.set()
        return msg