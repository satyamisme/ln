# Changelog

## [Unreleased] - 2025-08-05

### Added
- **Advanced Video Processing Engine:**
  - Implemented an "Intelligent Batch Processing" algorithm to automatically merge compatible video files from a torrent or zip.
  - The engine can now handle interruptions in compatibility (e.g., different video codecs, missing audio tracks) by processing files in smaller batches or individually.
- **Dynamic UI for Video Processing:**
  - All video tasks now use a single, editable status message that updates through all stages of the process (Extracting, Analyzing, Processing, Uploading).
  - A new "Analyzing Streams" card provides a detailed, user-friendly view of which tracks will be kept or removed, including metadata like resolution, bitrate, and channel layout.
- **Enhanced Stream Selection:**
  - New logic to keep all audio tracks of a priority language (e.g., Telugu) if present.
  - The bot will now always preserve embedded attachments like cover art.
- **Robust Error Handling:**
  - Added specific error handling for many edge cases, including corrupted files, incompatible streams, and FFmpeg timeouts.
- **Windows Startup Script (`start.bat`):**
  - A new batch file to automate the setup and execution of the bot on Windows.
- **Documentation:**
  - Added this `changes.md` file.
  - Updated `README.md` with details on the new video features and Windows setup.

### Changed
- The video processing workflow is now fully automated, from download to upload, with no user input required after the initial command.
- Completion messages for video tasks are now more detailed and provide a clear summary of the work done.
