from aiofiles.os import path as aiopath, listdir, remove
from asyncio import sleep, gather
from html import escape
from requests import utils as rutils
from os import path as ospath, walk
import subprocess
import math

from ... import (
    intervals,
    task_dict,
    task_dict_lock,
    LOGGER,
    non_queued_up,
    non_queued_dl,
    queued_up,
    queued_dl,
    queue_dict_lock,
    same_directory_lock,
    DOWNLOAD_DIR,
)
from ...core.config_manager import Config
from ...core.torrent_manager import TorrentManager
from ..common import TaskConfig
from ..ext_utils.bot_utils import sync_to_async
from ..ext_utils.db_handler import database
from ..ext_utils.files_utils import (
    get_path_size,
    clean_download,
    clean_target,
    join_files,
    create_recursive_symlink,
    remove_excluded_files,
    move_and_merge,
)
from ..ext_utils.links_utils import is_gdrive_id
from ..ext_utils.status_utils import get_readable_file_size
from ..ext_utils.task_manager import start_from_queued, check_running_tasks
from ..mirror_leech_utils.gdrive_utils.upload import GoogleDriveUpload
from ..mirror_leech_utils.rclone_utils.transfer import RcloneTransferHelper
from ..mirror_leech_utils.status_utils.gdrive_status import GoogleDriveStatus
from ..mirror_leech_utils.status_utils.queue_status import QueueStatus
from ..mirror_leech_utils.status_utils.rclone_status import RcloneStatus
from ..mirror_leech_utils.status_utils.telegram_status import TelegramStatus
from ..mirror_leech_utils.telegram_uploader import TelegramUploader
from ..video_utils.executor import VidEcxecutor
from ..telegram_helper.button_build import ButtonMaker
from ..telegram_helper.message_utils import (
    send_message,
    delete_status,
    update_status_message,
)


def check_dependencies():
    for cmd in ['ffmpeg', 'ffprobe']:
        try:
            subprocess.run([cmd, '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            LOGGER.error(f"{cmd} not found. Install FFmpeg and ensure it's in PATH.")
            return False
    return True

def get_file_size(file_path):
    try:
        return ospath.getsize(file_path)
    except OSError as e:
        LOGGER.error(f"Cannot access file {file_path}: {e}")
        return 0

def get_video_info(file_path):
    try:
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        duration = float(result.stdout.strip())
        bitrate = int((get_file_size(file_path) * 8) / duration) if duration > 0 else 0
        return {'duration': duration, 'bitrate': bitrate}
    except Exception as e:
        LOGGER.error(f"Error getting video info for {file_path}: {e}")
        return None

def smart_guess_split(input_file, start_time, target_min, target_max, total_duration, max_iterations=5):
    bytes_per_second = get_file_size(input_file) / total_duration
    guess = target_max / bytes_per_second
    low, high = guess * 0.95, min(total_duration - start_time, guess * 1.05)
    best_time, best_size = guess, 0
    for i in range(max_iterations):
        mid = (low + high) / 2
        temp_file = ospath.join(ospath.dirname(input_file), f"smart_temp_{i}.mkv")
        cmd = ['ffmpeg', '-y', '-i', input_file, '-ss', str(start_time), '-t', str(mid), '-c', 'copy', temp_file]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=300)
            size = get_file_size(temp_file)
            remove(temp_file)
            LOGGER.info(f"Smart Iter {i+1}: {mid:.2f}s, {size / (1024*1024*1024):.2f} GB")
            if 1_931_069_952 <= size <= 2_028_896_563:
                return mid, size
            elif size > 2_028_896_563:
                high = mid
            elif size < 1_931_069_952:
                low = mid
            best_time, best_size = mid, size
            if high - low < 2.0:
                break
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            LOGGER.error(f"Smart guess failed: {e}")
            if ospath.exists(temp_file):
                aioremove(temp_file)
            return None, None
    return best_time if 1_931_069_952 <= best_size <= 2_028_896_563 else None, best_size


class TaskListener(TaskConfig):
    def __init__(self):
        super().__init__()

    async def clean(self):
        try:
            if st := intervals["status"]:
                for intvl in list(st.values()):
                    intvl.cancel()
            intervals["status"].clear()
            await gather(TorrentManager.aria2.purgeDownloadResult(), delete_status())
        except:
            pass

    def clear(self):
        self.subname = ""
        self.subsize = 0
        self.files_to_proceed = []
        self.proceed_count = 0
        self.progress = True

    async def remove_from_same_dir(self):
        async with task_dict_lock:
            if (
                self.folder_name
                and self.same_dir
                and self.mid in self.same_dir[self.folder_name]["tasks"]
            ):
                self.same_dir[self.folder_name]["tasks"].remove(self.mid)
                self.same_dir[self.folder_name]["total"] -= 1

    async def on_download_start(self):
        if (
            self.is_super_chat
            and Config.INCOMPLETE_TASK_NOTIFIER
            and Config.DATABASE_URL
        ):
            await database.add_incomplete_task(
                self.message.chat.id, self.message.link, self.tag
            )

    async def on_download_complete(self):
        await sleep(2)
        if self.is_cancelled:
            return
        multi_links = False
        if (
            self.folder_name
            and self.same_dir
            and self.mid in self.same_dir[self.folder_name]["tasks"]
        ):
            async with same_directory_lock:
                while True:
                    async with task_dict_lock:
                        if self.mid not in self.same_dir[self.folder_name]["tasks"]:
                            return
                        if (
                            self.same_dir[self.folder_name]["total"] <= 1
                            or len(self.same_dir[self.folder_name]["tasks"]) > 1
                        ):
                            if self.same_dir[self.folder_name]["total"] > 1:
                                self.same_dir[self.folder_name]["tasks"].remove(
                                    self.mid
                                )
                                self.same_dir[self.folder_name]["total"] -= 1
                                spath = f"{self.dir}{self.folder_name}"
                                des_id = list(self.same_dir[self.folder_name]["tasks"])[
                                    0
                                ]
                                des_path = f"{DOWNLOAD_DIR}{des_id}{self.folder_name}"
                                LOGGER.info(f"Moving files from {self.mid} to {des_id}")
                                await move_and_merge(spath, des_path, self.mid)
                                multi_links = True
                            break
                    await sleep(1)
        async with task_dict_lock:
            if self.is_cancelled:
                return
            if self.mid not in task_dict:
                return
            download = task_dict[self.mid]
            self.name = download.name()
            gid = download.gid()
        LOGGER.info(f"Download completed: {self.name}")

        if not (self.is_torrent or self.is_qbit):
            self.seed = False

        if multi_links:
            self.seed = False
            await self.on_upload_error(
                f"{self.name} Downloaded!\n\nWaiting for other tasks to finish..."
            )
            return
        elif self.same_dir:
            self.seed = False

        if self.folder_name:
            self.name = self.folder_name.strip("/").split("/", 1)[0]

        if not await aiopath.exists(f"{self.dir}/{self.name}"):
            try:
                files = await listdir(self.dir)
                self.name = files[-1]
                if self.name == "yt-dlp-thumb":
                    self.name = files[0]
            except Exception as e:
                await self.on_upload_error(str(e))
                return

        dl_path = f"{self.dir}/{self.name}"
        self.size = await get_path_size(dl_path)
        self.is_file = await aiopath.isfile(dl_path)

        if self.seed:
            up_dir = self.up_dir = f"{self.dir}10000"
            up_path = f"{self.up_dir}/{self.name}"
            await create_recursive_symlink(self.dir, self.up_dir)
            LOGGER.info(f"Shortcut created: {dl_path} -> {up_path}")
        else:
            up_dir = self.dir
            up_path = dl_path

        await remove_excluded_files(self.up_dir or self.dir, self.excluded_extensions)

        if not Config.QUEUE_ALL:
            async with queue_dict_lock:
                if self.mid in non_queued_dl:
                    non_queued_dl.remove(self.mid)
            await start_from_queued()

        if self.join and not self.is_file:
            await join_files(up_path)

        if self.extract and not self.is_nzb:
            up_path = await self.proceed_extract(up_path, gid)
            if self.is_cancelled:
                return
            self.is_file = await aiopath.isfile(up_path)
            self.name = up_path.replace(f"{up_dir}/", "").split("/", 1)[0]
            self.size = await get_path_size(up_dir)
            self.clear()
            await remove_excluded_files(up_dir, self.excluded_extensions)

        if self.ffmpeg_cmds:
            up_path = await self.proceed_ffmpeg(
                up_path,
                gid,
            )
            if self.is_cancelled:
                return
            self.is_file = await aiopath.isfile(up_path)
            self.name = up_path.replace(f"{up_dir}/", "").split("/", 1)[0]
            self.size = await get_path_size(up_dir)
            self.clear()

        if self.vid_mode:
            up_path = await VidEcxecutor(self, up_path, gid).execute()
            if not up_path:
                return
            self.seed = False

        if self.name_sub:
            up_path = await self.substitute(up_path)
            if self.is_cancelled:
                return
            self.is_file = await aiopath.isfile(up_path)
            self.name = up_path.replace(f"{up_dir}/", "").split("/", 1)[0]

        if self.screen_shots:
            up_path = await self.generate_screenshots(up_path)
            if self.is_cancelled:
                return
            self.is_file = await aiopath.isfile(up_path)
            self.name = up_path.replace(f"{up_dir}/", "").split("/", 1)[0]
            self.size = await get_path_size(up_dir)

        if self.convert_audio or self.convert_video:
            up_path = await self.convert_media(
                up_path,
                gid,
            )
            if self.is_cancelled:
                return
            self.is_file = await aiopath.isfile(up_path)
            self.name = up_path.replace(f"{up_dir}/", "").split("/", 1)[0]
            self.size = await get_path_size(up_dir)
            self.clear()

        if self.sample_video:
            up_path = await self.generate_sample_video(up_path, gid)
            if self.is_cancelled:
                return
            self.is_file = await aiopath.isfile(up_path)
            self.name = up_path.replace(f"{up_dir}/", "").split("/", 1)[0]
            self.size = await get_path_size(up_dir)
            self.clear()

        if self.compress:
            up_path = await self.proceed_compress(
                up_path,
                gid,
            )
            self.is_file = await aiopath.isfile(up_path)
            if self.is_cancelled:
                return
            self.clear()

        self.name = up_path.replace(f"{up_dir}/", "").split("/", 1)[0]
        self.size = await get_path_size(up_dir)

        o_files = []
        m_size = []
        if self.is_leech and not self.compress:
            is_split = await self.proceedSplit(up_dir, m_size, o_files, self.size, gid)
            if self.is_cancelled:
                return
            if is_split:
                self.clear()

        self.subproc = None

        add_to_queue, event = await check_running_tasks(self, "up")
        await start_from_queued()
        if add_to_queue:
            LOGGER.info(f"Added to Queue/Upload: {self.name}")
            async with task_dict_lock:
                task_dict[self.mid] = QueueStatus(self, gid, "Up")
            await event.wait()
            if self.is_cancelled:
                return
            LOGGER.info(f"Start from Queued/Upload: {self.name}")

        self.size = await get_path_size(up_dir)

        if self.is_leech:
            LOGGER.info(f"Leech Name: {self.name}")
            tg = TelegramUploader(self, up_dir)
            async with task_dict_lock:
                task_dict[self.mid] = TelegramStatus(self, tg, gid, "up")
            await gather(
                update_status_message(self.message.chat.id),
                tg.upload(o_files, m_size),
            )
            del tg
        elif is_gdrive_id(self.up_dest):
            LOGGER.info(f"Gdrive Upload Name: {self.name}")
            drive = GoogleDriveUpload(self, up_path)
            async with task_dict_lock:
                task_dict[self.mid] = GoogleDriveStatus(self, drive, gid, "up")
            await gather(
                update_status_message(self.message.chat.id),
                sync_to_async(drive.upload),
            )
            del drive
        else:
            LOGGER.info(f"Rclone Upload Name: {self.name}")
            RCTransfer = RcloneTransferHelper(self)
            async with task_dict_lock:
                task_dict[self.mid] = RcloneStatus(self, RCTransfer, gid, "up")
            await gather(
                update_status_message(self.message.chat.id),
                RCTransfer.upload(up_path),
            )
            del RCTransfer
        return

    async def proceedSplit(self, up_dir, m_size, o_files, size, gid):
        if not self.is_leech or not await aiopath.isdir(up_dir):
            return True

        target_min_bytes = 1_931_069_952
        target_max_bytes = 2_028_896_563
        telegram_limit = 2_097_152_000

        for dirpath, _, files in await sync_to_async(walk, up_dir):
            for file_ in files:
                input_file = ospath.join(dirpath, file_)
                if not await aiopath.exists(input_file) or file_.endswith(('.aria2', '.!qB')):
                    continue

                file_size = get_file_size(input_file)
                if file_size <= target_max_bytes:
                    o_files.append(ospath.basename(input_file))
                    m_size.append(file_size)
                    continue

                video_info = get_video_info(input_file)
                if not video_info:
                    await self.on_upload_error("Failed to get video info.")
                    return False

                num_parts = math.ceil(file_size / target_max_bytes)
                start_time = 0
                parts = []
                base_name = ospath.splitext(file_)[0]

                for i in range(num_parts):
                    part_num = i + 1
                    is_last_part = (i == num_parts - 1)
                    part_file = ospath.join(self.dir, f"{base_name}.part{part_num}.mkv")

                    if not is_last_part:
                        split_duration, split_size = smart_guess_split(input_file, start_time, target_min_bytes, target_max_bytes, video_info['duration'])
                        if split_duration is None:
                            await self.on_upload_error(f"Failed to split part {part_num}.")
                            return False
                        cmd = ['ffmpeg', '-y', '-i', input_file, '-ss', str(start_time), '-t', str(split_duration), '-c', 'copy', part_file]
                        try:
                            subprocess.run(cmd, capture_output=True, text=True, check=True)
                            part_size = get_file_size(part_file)
                            if not (target_min_bytes <= part_size <= target_max_bytes):
                                await self.on_upload_error(f"Part {part_num} size out of range.")
                                return False
                            parts.append(part_file)
                            start_time += split_duration
                        except subprocess.CalledProcessError as e:
                            LOGGER.error(f"Split error: {e}")
                            return False
                    else:
                        cmd = ['ffmpeg', '-y', '-i', input_file, '-ss', str(start_time), '-c', 'copy', part_file]
                        subprocess.run(cmd, capture_output=True, text=True, check=True)
                        part_size = get_file_size(part_file)
                        if part_size > telegram_limit:
                            await self.on_upload_error(f"Last part exceeds Telegram limit.")
                            return False
                        parts.append(part_file)

                for part in parts:
                    o_files.append(ospath.basename(part))
                    m_size.append(get_file_size(part))
                await remove(input_file)

        return True

    async def on_upload_complete(
        self, link, files, folders, mime_type, rclone_path="", dir_id=""
    ):
        if (
            self.is_super_chat
            and Config.INCOMPLETE_TASK_NOTIFIER
            and Config.DATABASE_URL
        ):
            await database.rm_complete_task(self.message.link)

        if self.vid_mode:
            # The VidEcxecutor will handle sending the final message
            pass
        else:
            msg = f"<b>Name: </b><code>{escape(self.name)}</code>\n\n<b>Size: </b>{get_readable_file_size(self.size)}"
            LOGGER.info(f"Task Done: {self.name}")
            if self.is_leech:
                msg += f"\n<b>Total Files: </b>{folders}"
                if mime_type != 0:
                    msg += f"\n<b>Corrupted Files: </b>{mime_type}"
                msg += f"\n<b>cc: </b>{self.tag}\n\n"
                if not files:
                    await send_message(self.message, msg)
                else:
                    fmsg = ""
                    for index, (link, name) in enumerate(files.items(), start=1):
                        fmsg += f"{index}. <a href='{link}'>{name}</a>\n"
                        if len(fmsg.encode() + msg.encode()) > 4000:
                            await send_message(self.message, msg + fmsg)
                            await sleep(1)
                            fmsg = ""
                    if fmsg != "":
                        await send_message(self.message, msg + fmsg)
            else:
                msg += f"\n\n<b>Type: </b>{mime_type}"
                if mime_type == "Folder":
                    msg += f"\n<b>SubFolders: </b>{folders}"
                    msg += f"\n<b>Files: </b>{files}"
                if (
                    link
                    or rclone_path
                    and Config.RCLONE_SERVE_URL
                    and not self.private_link
                ):
                    buttons = ButtonMaker()
                    if link:
                        buttons.url_button("☁️ Cloud Link", link)
                    else:
                        msg += f"\n\nPath: <code>{rclone_path}</code>"
                    if rclone_path and Config.RCLONE_SERVE_URL and not self.private_link:
                        remote, rpath = rclone_path.split(":", 1)
                        url_path = rutils.quote(f"{rpath}")
                        share_url = f"{Config.RCLONE_SERVE_URL}/{remote}/{url_path}"
                        if mime_type == "Folder":
                            share_url += "/"
                        buttons.url_button("🔗 Rclone Link", share_url)
                    if not rclone_path and dir_id:
                        INDEX_URL = ""
                        if self.private_link:
                            INDEX_URL = self.user_dict.get("INDEX_URL", "") or ""
                        elif Config.INDEX_URL:
                            INDEX_URL = Config.INDEX_URL
                        if INDEX_URL:
                            share_url = f"{INDEX_URL}/findpath?id={dir_id}"
                            buttons.url_button("⚡ Index Link", share_url)
                            if mime_type.startswith(("image", "video", "audio")):
                                share_urls = f"{INDEX_URL}/findpath?id={dir_id}&view=true"
                                buttons.url_button("🌐 View Link", share_urls)
                    button = buttons.build_menu(2)
                else:
                    msg += f"\n\nPath: <code>{rclone_path}</code>"
                    button = None
                msg += f"\n\n<b>cc: </b>{self.tag}"
                await send_message(self.message, msg, button)

        if self.seed:
            await clean_target(self.up_dir)
            async with queue_dict_lock:
                if self.mid in non_queued_up:
                    non_queued_up.remove(self.mid)
            await start_from_queued()
            return
        await clean_download(self.dir)
        async with task_dict_lock:
            if self.mid in task_dict:
                del task_dict[self.mid]
            count = len(task_dict)
        if count == 0:
            await self.clean()
        else:
            await update_status_message(self.message.chat.id)

        async with queue_dict_lock:
            if self.mid in non_queued_up:
                non_queued_up.remove(self.mid)

        await start_from_queued()

    async def on_download_error(self, error, button=None):
        async with task_dict_lock:
            if self.mid in task_dict:
                del task_dict[self.mid]
            count = len(task_dict)
        await self.remove_from_same_dir()
        msg = f"{self.tag} Download: {escape(str(error))}"
        await send_message(self.message, msg, button)
        if count == 0:
            await self.clean()
        else:
            await update_status_message(self.message.chat.id)

        if (
            self.is_super_chat
            and Config.INCOMPLETE_TASK_NOTIFIER
            and Config.DATABASE_URL
        ):
            await database.rm_complete_task(self.message.link)

        async with queue_dict_lock:
            if self.mid in queued_dl:
                queued_dl[self.mid].set()
                del queued_dl[self.mid]
            if self.mid in queued_up:
                queued_up[self.mid].set()
                del queued_up[self.mid]
            if self.mid in non_queued_dl:
                non_queued_dl.remove(self.mid)
            if self.mid in non_queued_up:
                non_queued_up.remove(self.mid)

        await start_from_queued()
        await sleep(3)
        await clean_download(self.dir)
        if self.up_dir:
            await clean_download(self.up_dir)
        if self.thumb and await aiopath.exists(self.thumb):
            await remove(self.thumb)

    async def on_upload_error(self, error):
        async with task_dict_lock:
            if self.mid in task_dict:
                del task_dict[self.mid]
            count = len(task_dict)
        await send_message(self.message, f"{self.tag} {escape(str(error))}")
        if count == 0:
            await self.clean()
        else:
            await update_status_message(self.message.chat.id)

        if (
            self.is_super_chat
            and Config.INCOMPLETE_TASK_NOTIFIER
            and Config.DATABASE_URL
        ):
            await database.rm_complete_task(self.message.link)

        async with queue_dict_lock:
            if self.mid in queued_dl:
                queued_dl[self.mid].set()
                del queued_dl[self.mid]
            if self.mid in queued_up:
                queued_up[self.mid].set()
                del queued_up[self.mid]
            if self.mid in non_queued_dl:
                non_queued_dl.remove(self.mid)
            if self.mid in non_queued_up:
                non_queued_up.remove(self.mid)

        await start_from_queued()
        await sleep(3)
        await clean_download(self.dir)
        if self.up_dir:
            await clean_download(self.up_dir)
        if self.thumb and await aiopath.exists(self.thumb):
            await remove(self.thumb)
