import asyncio
import subprocess
import time
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from services.media_downloader_service import MediaDownloaderService

async def main():
    ffmpeg = MediaDownloaderService.get_ffmpeg_path()
    test_dir = BASE_DIR / "scratch" / "test_media"
    test_dir.mkdir(parents=True, exist_ok=True)
    sample_video = test_dir / "big_sample.mp4"
    sample_m4a = test_dir / "big_sample.m4a"
    sample_mp3 = test_dir / "big_sample.mp3"
    
    # 5 daqiqalik test video
    cmd_gen = [
        ffmpeg, "-y",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=300",
        "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=300",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        "-shortest", str(sample_video)
    ]
    subprocess.run(cmd_gen, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Test 1: -c:a copy to .m4a
    t0 = time.time()
    cmd1 = [ffmpeg, "-nostdin", "-y", "-loglevel", "error", "-i", str(sample_video), "-vn", "-sn", "-dn", "-c:a", "copy", "-map", "0:a:0?", str(sample_m4a)]
    res1 = subprocess.run(cmd1)
    t1 = time.time()
    print(f"Direct stream copy (.m4a): {t1 - t0:.4f}s (size: {sample_m4a.stat().st_size} bytes)")
    
    # Test 2: Fast MP3 with -q:a 2
    t0 = time.time()
    cmd2 = [ffmpeg, "-nostdin", "-y", "-loglevel", "error", "-threads", "0", "-i", str(sample_video), "-vn", "-sn", "-dn", "-c:a", "libmp3lame", "-q:a", "2", "-map", "0:a:0?", str(sample_mp3)]
    res2 = subprocess.run(cmd2)
    t1 = time.time()
    print(f"Fast MP3 (-q:a 2): {t1 - t0:.4f}s (size: {sample_mp3.stat().st_size} bytes)")

if __name__ == "__main__":
    asyncio.run(main())
