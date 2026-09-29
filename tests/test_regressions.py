import asyncio
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from types import SimpleNamespace
from services.fast_telethon import FastTelethon, CHUNK_SIZE

from services.dialogue_service import TOPIC_METADATA, get_dialogues_for_topic, format_dialogue_telegram_message
from services.media_downloader_service import MediaDownloaderService
from services.user_service import UserService


class RegressionTests(unittest.IsolatedAsyncioTestCase):
    def test_all_dialogue_steps_render(self):
        for language in ('en', 'ru'):
            for topic in TOPIC_METADATA:
                for index, dialogue in enumerate(get_dialogues_for_topic(topic, language)):
                    for step in range(len(dialogue['lines'])):
                        message = format_dialogue_telegram_message(dialogue, step, topic, index, language)
                        self.assertLess(len(message), 4096)
                        self.assertIn(f'{step + 1}/{len(dialogue["lines"])}', message)

    def test_html_escaping(self):
        dialogue = {'title': '<title>', 'lines': [{'speakerIcon': '', 'speaker': 'A&B', 'textTarget': '<hi>', 'textUz': 'salom'}]}
        result = format_dialogue_telegram_message(dialogue, 0, 'taxi', 0)
        self.assertIn('&lt;hi&gt;', result)
        self.assertIn('A&amp;B', result)

    def test_registration_and_activity(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('services.user_service.USERS_FILE', Path(folder) / 'users.json'):
                UserService.register_user(123, 'test', 'Test')
                UserService.register_user(123, 'test', 'Test')
                self.assertEqual(len(UserService._load_users()), 1)
                self.assertEqual(UserService.get_recent_users_count(), 1)

    async def test_parallel_downloads_are_isolated_and_progress_on_loop(self):
        main_thread = threading.get_ident()
        callback_threads = []
        class FakeYDL:
            def __init__(self, options): self.options = options
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def extract_info(self, url, download):
                directory = Path(self.options['outtmpl']).parent
                path = directory / 'same.mp4'
                path.write_bytes(url.encode())
                self.options['progress_hooks'][0]({'status': 'downloading', 'downloaded_bytes': 10, 'total_bytes': 10})
                return {'title': url}
        with tempfile.TemporaryDirectory() as folder, patch('services.media_downloader_service.yt_dlp.YoutubeDL', FakeYDL):
            a, b = await asyncio.gather(*[
                MediaDownloaderService.download_external_media(url, save_dir=Path(folder), progress_callback=lambda *args: callback_threads.append(threading.get_ident()))
                for url in ('first', 'second')
            ])
            self.assertNotEqual(a['path'], b['path'])
            self.assertEqual(Path(a['path']).read_text(), 'first')
            self.assertEqual(Path(b['path']).read_text(), 'second')
            self.assertEqual(callback_threads, [main_thread, main_thread])

    async def test_mp3_format_and_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'sample.mp4'
            output = Path(folder) / 'sample.mp3'
            proc = await asyncio.create_subprocess_exec(
                MediaDownloaderService.get_ffmpeg_path(), '-y', '-loglevel', 'error',
                '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1', '-c:a', 'aac', str(source),
            )
            self.assertEqual(await proc.wait(), 0)
            result = await MediaDownloaderService.extract_high_quality_mp3(source, output)
            self.assertEqual(result.suffix, '.mp3')
            self.assertGreater(result.stat().st_size, 30000)
            timestamp = result.stat().st_mtime_ns
            await MediaDownloaderService.extract_high_quality_mp3(source, output)
            self.assertEqual(result.stat().st_mtime_ns, timestamp)

    async def test_cloudflare_retry_uses_browser_transport_once(self):
        from yt_dlp.utils import DownloadError
        attempts = []
        class FakeYDL:
            def __init__(self, options):
                self.options = options
                attempts.append(options)
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def extract_info(self, url, download):
                if len(attempts) == 1:
                    raise DownloadError('HTTP Error 403 caused by Cloudflare anti-bot challenge')
                Path(self.options['outtmpl']).parent.joinpath('result.mp4').write_bytes(b'video')
                return {'title': 'Test'}
        with tempfile.TemporaryDirectory() as folder, patch('services.media_downloader_service.yt_dlp.YoutubeDL', FakeYDL):
            result = await MediaDownloaderService.download_external_media('https://example.com/video', save_dir=Path(folder))
            self.assertEqual(Path(result['path']).read_bytes(), b'video')
        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[1]['extractor_args']['generic']['impersonate'], ['chrome'])
        self.assertNotIn('http_headers', attempts[1])

    async def test_incomplete_telegram_chunks_use_fallback(self):
        class Client:
            async def __call__(self, request):
                return SimpleNamespace(bytes=b'')
            async def download_media(self, media, file, progress_callback):
                Path(file).write_bytes(b'complete-fallback')
                return file
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(FastTelethon, 'extract_file_info', return_value=(object(), 1, CHUNK_SIZE * 2, 'sample.mp4')), patch('services.fast_telethon.GetFileRequest', return_value=object()), patch('services.fast_telethon.asyncio.sleep', new_callable=AsyncMock):
                output = await asyncio.wait_for(FastTelethon.download_media(Client(), object(), Path(folder) / 'result.mp4'), 5)
                self.assertEqual(output.read_bytes(), b'complete-fallback')


if __name__ == '__main__':
    unittest.main()
