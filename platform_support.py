"""Process and tool paths shared by macOS and Windows."""
import os
import shutil
import subprocess
import sys
from pathlib import Path


def is_windows():
    return sys.platform == 'win32'


def process_options(detached=False):
    if is_windows():
        flags = (getattr(subprocess,'DETACHED_PROCESS',0x8) |
                 getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0x200)) if detached else getattr(subprocess,'CREATE_NO_WINDOW',0x08000000)
        return {'creationflags':flags}
    return {'start_new_session':True} if detached else {}


def ffmpeg_tool(binary, folder):
    """yt-dlp needs a conventional executable name; Windows needs no symlink rights."""
    binary=Path(binary)
    target=Path(folder)/('ffmpeg.exe' if is_windows() else 'ffmpeg')
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.is_symlink() and not target.exists():target.unlink()
    if is_windows():
        if not target.exists() or (target.stat().st_size,target.stat().st_mtime_ns)!=(binary.stat().st_size,binary.stat().st_mtime_ns):
            temporary=target.with_suffix('.exe.part')
            shutil.copy2(binary,temporary)
            temporary.replace(target)
    elif not target.exists():
        target.symlink_to(os.path.relpath(binary,target.parent))
    return target
