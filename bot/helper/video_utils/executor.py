from __future__ import annotations
from aiofiles import open as aiopen
from aiofiles.os import path as aiopath, makedirs
from aioshutil import rmtree
from ast import literal_eval
from asyncio import create_subprocess_exec, gather, Event, wait_for, TimeoutError as AsyncTimeoutError
from asyncio.subprocess import PIPE
import re
from natsort import natsorted
from os import path as ospath, walk
from time import time

from bot import task_dict, task_dict_lock, LOGGER, VID_MODE, FFMPEG_NAME
from bot.helper.ext_utils.bot_utils import sync_to_async, cmd_exec, new_task
from bot.helper.ext_utils.task_manager import ffmpeg_queue, ffmpeg_queue_lock, active_ffmpeg
from bot.helper.ext_utils.files_utils import get_path_size, clean_target
from bot.helper.ext_utils.media_utils import get_document_type, FFProgress
from bot.helper.listeners import task_listener as task
from bot.helper.mirror_leech_utils.status_utils.ffmpeg_status import FFmpegStatus
from bot.helper.telegram_helper.message_utils import send_status_message, send_message

async def get_metavideo(video_file):
    try:
        stdout, stderr, rcode = await cmd_exec(['ffprobe', '-hide_banner', '-print_format', 'json', '-show_streams', video_file])
        if rcode != 0:
            LOGGER.error(f"ffprobe error for {video_file}: {stderr}")
            return []
        metadata = literal_eval(stdout)
        streams = metadata.get('streams', [])
        for stream in streams:
            if stream.get('codec_type') == 'video':
                stream['bit_rate'] = stream.get('bit_rate')
                stream['channel_layout'] = None
            elif stream.get('codec_type') == 'audio':
                stream['bit_rate'] = stream.get('bit_rate')
                stream['channel_layout'] = stream.get('channel_layout')
        return streams
    except Exception as e:
        LOGGER.error(f"Error in get_metavideo: {e}")
        return []

class VidEcxecutor(FFProgress):
    def __init__(self, listener: task.TaskListener, path: str, gid: str, metadata=False):
        super().__init__()
        self.data = {}
        self.event = Event()
        self.listener = listener
        self.path = path
        self.name = ''
        self.outfile = ''
        self.size = 0
        self._metadata = metadata
        self._up_path = path
        self._gid = gid
        self._files = []
        self.is_cancelled = False
        self.status_message = None
        LOGGER.info(f"Initialized VidEcxecutor for MID: {self.listener.mid}, path: {self.path}")

    async def _cleanup(self):
        try:
            for f in self._files:
                if await aiopath.exists(f):
                    await clean_target(f)
            self._files.clear()
            input_file = ospath.join(self.path, f'input_{self._gid}.txt')
            if await aiopath.exists(input_file):
                await clean_target(input_file)
            self.data.clear()
            self.is_cancelled = True
            if self.status_message:
                await deleteMessage(self.status_message)
            LOGGER.info(f"Cleanup completed for {self.mode}")
        except Exception as e:
            LOGGER.error(f"Cleanup error: {e}")

    async def _extract_zip(self, zip_path):
        extract_dir = ospath.join(ospath.dirname(zip_path), f"extracted_{self._gid}")
        try:
            await self._send_status("Extracting...")
            await makedirs(extract_dir, exist_ok=True)
            cmd = ['7z', 'x', zip_path, f'-o{extract_dir}', '-y']
            _, stderr, rcode = await cmd_exec(cmd)
            if rcode != 0:
                LOGGER.error(f"Failed to extract ZIP: {stderr}")
                await rmtree(extract_dir, ignore_errors=True)
                return None
            LOGGER.info(f"Extracted ZIP to {extract_dir}")
            return extract_dir
        except Exception as e:
            LOGGER.error(f"ZIP extraction error: {e}")
            await rmtree(extract_dir, ignore_errors=True)
            return None

    async def _get_files(self):
        file_list = []
        if self._metadata:
            file_list.append(self.path)
        elif await aiopath.isfile(self.path):
            if self.path.lower().endswith(('.zip', '.rar', '.7z')):
                extract_dir = await self._extract_zip(self.path)
                if extract_dir:
                    self._files.append(extract_dir)
                    for dirpath, _, files in await sync_to_async(walk, extract_dir):
                        for file in natsorted(files):
                            file_path = ospath.join(dirpath, file)
                            if (await get_document_type(file_path))[0]:
                                file_list.append(file_path)
                                LOGGER.info(f"Found media file: {file_path}")
            elif (await get_document_type(self.path))[0]:
                file_list.append(self.path)
        else:
            for dirpath, _, files in await sync_to_async(walk, self.path):
                for file in natsorted(files):
                    file_path = ospath.join(dirpath, file)
                    if (await get_document_type(file_path))[0]:
                        file_list.append(file_path)
                        LOGGER.info(f"Found media file: {file_path}")
        self.size = sum(await gather(*[get_path_size(f) for f in file_list])) if file_list else 0
        return file_list

    async def execute(self):
        self._is_dir = await aiopath.isdir(self.path)
        try:
            self.mode, self.name, kwargs = self.listener.vid_mode
        except (AttributeError, ValueError) as e:
            LOGGER.error(f"Invalid vid_mode: {e}")
            await self._cleanup()
            await self.listener.onUploadError("Invalid video mode configuration.")
            return None

        file_list = await self._get_files()
        if not file_list:
            await send_message("No valid video files found.", self.listener.message)
            await self._cleanup()
            return None

        event = Event()
        async with ffmpeg_queue_lock:
            ffmpeg_queue[self.listener.mid] = (event, self.mode, file_list)

        try:
            await wait_for(event.wait(), timeout=600)
        except AsyncTimeoutError:
            LOGGER.error(f"FFmpeg queue timeout for MID: {self.listener.mid}")
            async with ffmpeg_queue_lock:
                ffmpeg_queue.pop(self.listener.mid, None)
            await self._cleanup()
            await self.listener.onUploadError("FFmpeg processing timed out.")
            return None

        try:
            result = await self._process_files(file_list)
            if self.is_cancelled or not result:
                await self._cleanup()
                await self.listener.onUploadError(f"{self.mode} processing failed.")
                return None
            return result
        except Exception as e:
            LOGGER.error(f"Execution error in {self.mode} for MID: {self.listener.mid}: {e}")
            await self._cleanup()
            await self.listener.onUploadError(f"Failed to process {self.mode}.")
            return None
        finally:
            global active_ffmpeg
            async with ffmpeg_queue_lock:
                if active_ffmpeg == self.listener.mid:
                    active_ffmpeg = None

    async def _process_files(self, file_list):
        if self.mode == 'merge_rmaudio':
            await self._intelligent_batch_processing(file_list)
        else:
            LOGGER.error(f"Unsupported mode: {self.mode}")
            await self.listener.onUploadError(f"Unsupported mode: {self.mode}")

    async def _intelligent_batch_processing(self, file_list):
        from bot.helper.video_utils.extra_selector import ExtraSelect

        batches = []
        current_batch = []

        if not file_list:
            return

        # Get metadata for all files first
        all_metadata = await gather(*[get_metavideo(f) for f in file_list])

        for i, file_path in enumerate(file_list):
            metadata = all_metadata[i]
            if not metadata:
                LOGGER.warning(f"Could not get metadata for {file_path}. Processing individually.")
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                batches.append([file_path]) # Process as a single-file batch
                continue

            if not current_batch:
                current_batch.append(file_path)
            else:
                # Compare with the first file in the current batch
                first_file_metadata = all_metadata[file_list.index(current_batch[0])]

                # Check for video stream compatibility
                video_stream1 = next((s for s in first_file_metadata if s['codec_type'] == 'video'), None)
                video_stream2 = next((s for s in metadata if s['codec_type'] == 'video'), None)

                if not video_stream1 or not video_stream2 or \
                   video_stream1['codec_name'] != video_stream2['codec_name'] or \
                   video_stream1['height'] != video_stream2['height']:
                    batches.append(current_batch)
                    current_batch = [file_path]
                else:
                    current_batch.append(file_path)

        if current_batch:
            batches.append(current_batch)

        total_batches = len(batches)
        for i, batch in enumerate(batches):
            await self._process_batch(batch, i + 1, total_batches)

    async def _process_batch(self, batch, current_batch_num, total_batches):
        from bot.helper.video_utils.extra_selector import ExtraSelect

        # For now, we only support track removal from the first file in a batch for simplicity
        # This can be expanded later to handle complex logic for all files in a batch
        streams = await get_metavideo(batch[0])
        if not streams:
            await send_message(f"Could not process batch starting with {ospath.basename(batch[0])} due to metadata error.", self.listener.message)
            return

        self.data = {} # Reset data for each batch
        selector = ExtraSelect(self)
        analysis_message = await selector.streams_select(streams)

        if not self.status_message:
            self.status_message = await send_message(analysis_message, self.listener.message)
        else:
            await editMessage(analysis_message, self.status_message)

        await self._start_handler(streams)
        await wait_for(self.event.wait(), timeout=180)

        if self.is_cancelled:
            return

        streams_to_remove = self.data.get('streams_to_remove', [])

        base_dir = await self._name_base_dir(batch[0], 'Merge-RemoveAudio', multi=len(batch) > 1)

        if len(batch) > 1:
            self.name = f"{ospath.splitext(ospath.basename(batch[0]))[0]}-{ospath.splitext(ospath.basename(batch[-1]))[0]}.mkv"
        else:
             self.name = f"{ospath.splitext(ospath.basename(batch[0]))[0]}_processed.mkv"

        self.outfile = ospath.join(base_dir, self.name)
        input_file_path = ospath.join(base_dir, f'input_{self._gid}.txt')

        cmd = [FFMPEG_NAME]
        if len(batch) > 1:
            async with aiopen(input_file_path, 'w') as f:
                await f.write('\n'.join([f"file '{ospath.abspath(f)}'" for f in batch]))
            cmd.extend(['-f', 'concat', '-safe', '0', '-i', input_file_path])
        else:
            cmd.extend(['-i', batch[0]])

        cmd.extend(['-map', '0:v:0'])

        # This logic assumes streams are consistent across the batch, which is checked by the batching logic
        # For simplicity, we use the stream info from the first file
        for stream in streams:
            if stream['index'] not in streams_to_remove and stream['codec_type'] != 'video':
                cmd.extend([f'-map', f"0:{stream['index']}"])

        cmd.extend(['-c', 'copy', self.outfile, '-y'])

        await self._run_cmd(cmd, f"Processing batch {current_batch_num}/{total_batches}")

        if await aiopath.exists(input_file_path):
            await clean_target(input_file_path)

        # After processing, we need to handle the upload. This part needs to be connected to the listener.
        # This is a simplified version. The actual implementation will need to call back to the listener's upload methods.
        LOGGER.info(f"Finished processing batch {current_batch_num}/{total_batches}. Output: {self.outfile}")
        # The listener should handle the upload of self.outfile

    @new_task
    async def _start_handler(self, *args):
        from bot.helper.video_utils.extra_selector import ExtraSelect
        selector = ExtraSelect(self)
        await selector.get_buttons(*args)

    async def _name_base_dir(self, path, info: str=None, multi: bool=False):
        base_dir, file_name = ospath.split(path)
        if not self.name or multi:
            if info:
                if await aiopath.isfile(path):
                    file_name = file_name.rsplit('.', 1)[0]
                file_name += f'_{info}.mkv'
                LOGGER.info(f"Generated name: {file_name}")
            self.name = file_name
        if not self.name.upper().endswith(('MKV', 'MP4')):
            self.name += '.mkv'
        LOGGER.info(f"Set name: {self.name} with base_dir: {base_dir}")
        return base_dir if await aiopath.isfile(path) else path

    async def _run_cmd(self, cmd, status='prog'):
        try:
            await self._send_status(status)
            LOGGER.info(f"Running FFmpeg cmd: {' '.join(cmd)}")
            process = await create_subprocess_exec(*cmd, stderr=PIPE)
            self.listener.suproc = process
            try:
                _, code = await wait_for(gather(self.progress(status), process.wait()), timeout=7200)
            except TimeoutError:
                LOGGER.error("FFmpeg process timed out.")
                process.kill()
                self.is_cancelled = True
                return False
            if code == 0:
                LOGGER.info("FFmpeg succeeded")
                return True
            if self.listener.suproc == 'cancelled' or code == -9:
                self.is_cancelled = True
                LOGGER.info("FFmpeg cancelled")
            else:
                error_msg = (await process.stderr.read()).decode().strip()
                LOGGER.error(f"FFmpeg error: {error_msg}")
                self.is_cancelled = True
            return False
        except Exception as e:
            LOGGER.error(f"Run cmd error: {e}", exc_info=True)
            self.is_cancelled = True
            return False

    async def _merge_and_rmaudio(self, file_list):
        streams = await get_metavideo(file_list[0])
        if not streams:
            LOGGER.error(f"No streams found in {file_list[0]}")
            await send_message("No streams found in the video file.", self.listener.message)
            return None

        base_dir = await self._name_base_dir(file_list[0], 'Merge-RemoveAudio', multi=len(file_list) > 1)
        self._files = file_list
        self.size = sum(await gather(*[get_path_size(f) for f in file_list])) if file_list else 0

        await self._start_handler(streams)
        await wait_for(self.event.wait(), timeout=180)
        if self.is_cancelled:
            LOGGER.info("Cancelled in _merge_and_rmaudio.")
            return None

        streams_to_remove = self.data.get('streams_to_remove', [])
        self.outfile = ospath.join(base_dir, self.name)
        input_file = ospath.join(base_dir, f'input_{self._gid}.txt')

        try:
            if len(file_list) > 1:
                async with aiopen(input_file, 'w') as f:
                    await f.write('\n'.join([f"file '{f}'" for f in file_list]))
                cmd = [FFMPEG_NAME, '-f', 'concat', '-safe', '0', '-i', input_file]
            else:
                cmd = [FFMPEG_NAME, '-i', file_list[0]]

            cmd.extend(['-map', '0:v'])
            kept_streams = [f'0:{s["index"]}' for s in streams if s['index'] not in streams_to_remove and s['codec_type'] != 'video']
            for stream in kept_streams:
                cmd.extend(['-map', stream])
            cmd.extend(['-c', 'copy', self.outfile, '-y'])

            if not await self._run_cmd(cmd, 'direct'):
                await send_message("Merging failed due to FFmpeg error.", self.listener.message)
                return None
            return await self._final_path()
        except Exception as e:
            LOGGER.error(f"Error in _merge_and_rmaudio: {e}", exc_info=True)
            await send_message("Processing failed.", self.listener.message)
            return None
        finally:
            if len(file_list) > 1:
                await clean_target(input_file)