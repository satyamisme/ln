# Video Processing UI/UX Enhancements

This document outlines the new user interface and experience for the advanced video processing features.

## 1. Dynamic Status Message

All video processing tasks will use a single, editable Telegram message to show the status of the operation. This message will be updated through the following stages:

- **Extracting (for archives):**
  ```
  🗜️ **Extracting:** `My.Videos.zip`
  ```
- **Analyzing Streams:**
  ```
  🎬 **Analyzing Streams**
  ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
  **File:** `Love.Under.Construction.2024.mkv`

  **✅ Tracks to Keep:**
  - - - - - - - - - - - - - - - - -
  **📹 Video:**
    └ H264, 1080p, 2.5 Mbps
  **🖼️ Attachment:**
    └ MJPEG, 640x480 (Cover Art)
  **🔊 Audio:**
    ├ AAC, Telugu, 5.1, 320kbps
    └ AAC, Telugu, Stereo, 192kbps

  **🚫 Tracks to Remove:**
  - - - - - - - - - - - - - - - - -
  **🔊 Audio:**
    └ AC3, Hindi, 5.1, 448kbps
  **📖 Subtitle:**
    └ SRT, English
  ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
  ```
- **Processing:**
  ```
  🔄 **Processing: [1/5]** `Love.Under.Construction...`
  [█████     ] 50%
  ```
- **Uploading:**
  ```
  📤 **Uploading:** `Love.Under.Construction.mkv`
  [████████  ] 80%
  Speed: 12.5 MB/s
  ```

## 2. "Process-as-you-go" Workflow & Completion Messages

The bot uses an intelligent "process-as-you-go" algorithm. It merges compatible files and processes incompatible ones individually, uploading each result as it's completed.

### Example Scenario:
A 5-episode series where E03 has an incompatible video stream and E04 is missing the priority audio.

**Message 1: First Merged Batch**
```
🎉 **Task Part 1/4 Completed (Merged)**

**✅ Output File:** `The.Show.S01.E01-E02.mkv`
- **Source Files:** `E01.mkv`, `E02.mkv`
- **Reason:** Files were compatible and merged.

🌟 **Powered by @MaheshBot**
```

**Message 2: Incompatible File**
```
🎉 **Task Part 2/4 Completed (Individual)**

**✅ Output File:** `The.Show.S01.E03.mkv`
- **Reason:** Processed individually due to incompatible video resolution (720p).

🌟 **Powered by @MaheshBot**
```

**Message 3: File with Missing Audio**
```
🎉 **Task Part 3/4 Completed (Individual)**

**✅ Output File:** `The.Show.S01.E04.mkv`
- **Reason:** Processed individually, priority 'Telugu' audio not found.

🌟 **Powered by @MaheshBot**
```

**Message 4: Final File**
```
🎉 **Task Part 4/4 Completed (Individual)**

**✅ Output File:** `The.Show.S01.E05.mkv`
- **Reason:** Last file in sequence.

🏁 **All tasks finished.**
```

## 3. Error Handling Messages

The bot will provide clear, actionable error messages.

**Incompatible Video Streams (during a merge attempt):**
```
❌ **Merge Failed: Incompatible Video Streams**

The following files have different video properties and cannot be merged:
- `S01E01.mkv` (1920x1080, h264)
- `S01E02.mkv` (1280x720, h264)
```

**Missing Priority Audio (during a merge attempt):**
```
❌ **Merge Failed: Missing Audio Track**

The priority audio language 'Telugu' was not found in all files to be merged.
- Missing from: `S01E03.mkv`
```

**Corrupted File (Automatic Recovery):**
If a file is found to be corrupted after download, the bot will automatically process the good files and provide a summary.
```
⚠️ **Task Completed with Errors**

Your task `The.Show.S01.1080p` finished, but 1 out of 5 files failed to process. The remaining 4 files were processed and uploaded individually.

**❌ Failed File:**
- `S01E03.mkv` (Reason: Corrupted or unreadable)

**✅ Successfully Processed Files:**
- `S01E01.mkv`
- `S01E02.mkv`
- `S01E04.mkv`
- `S01E05.mkv`

🌟 **Powered by @MaheshBot**
```
