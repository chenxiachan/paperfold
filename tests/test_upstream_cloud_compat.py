"""New upstream import paths keep cloud originals and unfinished local work durable."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from textfold import capture, engine, fetch, store
from textfold.cloud_storage import StorageError
from textfold.offline_storage import OfflineBackend
from test_capture import SNAP, READ


class UpstreamCloudCompatibility(unittest.TestCase):
    def remote(self):
        return SimpleNamespace(url='https://storage.example.test',
                               sync_health=mock.Mock(side_effect=StorageError('offline')))

    def test_browser_capture_survives_restart_without_overwriting_existing_work(self):
        with tempfile.TemporaryDirectory() as folder:
            remote = self.remote()
            backend = OfflineBackend(folder, remote)
            with store.use_backend(backend), mock.patch.object(backend, 'request_sync'), \
                    mock.patch.object(capture, '_server_url', return_value=None), \
                    mock.patch('textfold.local.prefetch', return_value={}):
                result = capture.receive(dict(SNAP, read=READ))
                pid = result['paper']
                self.assertTrue(result['new'])
                with store.edit(pid) as doc:
                    doc.processing.replies['completed.json'] = b'{"out":{"paid":"keep"}}'
                    doc.notes = {'notes': [{'id': 'n-keep', 'text': 'Unsynchronized note', 'anchor': {'on': 'paper'}}]}
                before = backend.cache.get(pid)
                again = capture.receive(dict(SNAP, html='<p>Different page</p>', read=READ))
                self.assertFalse(again['new'])
                self.assertEqual(backend.cache.get(pid), before)
            restored = OfflineBackend(folder, remote)
            saved = restored.cache.get(pid)
            self.assertEqual(saved.extensions['snapshot.html'], SNAP['html'].encode('utf-8'))
            self.assertEqual(saved.source.originals['html'], SNAP['html'].encode('utf-8'))
            self.assertEqual(saved.extensions['article.html'], READ['defuddle']['html'].encode('utf-8'))
            self.assertEqual(saved.processing.replies['completed.json'], b'{"out":{"paid":"keep"}}')
            self.assertEqual(saved.notes['notes'][0]['text'], 'Unsynchronized note')
            self.assertGreater(restored.status()['pending'], 0)
            restored.clear_cache()
            self.assertEqual(restored.cache.get(pid).source.originals, saved.source.originals)

    def test_arxiv_html_is_kept_across_failed_metadata_and_restart(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as runtime:
            remote = self.remote()
            backend = OfflineBackend(folder, remote)
            html = b'<html><p>Paper</p><img src="2512.23916v2/x.png"></html>'
            def failed(url):
                if '/html/' in url:
                    return html, 'https://arxiv.org/html/2512.23916v2'
                raise StorageError('metadata offline')
            with store.use_backend(backend), mock.patch.object(store, 'DATA', Path(runtime)), \
                    mock.patch.object(backend, 'request_sync'), mock.patch.object(fetch, 'get', side_effect=failed):
                with self.assertRaisesRegex(StorageError, 'metadata offline'), store.repository().workspace('2512.23916'):
                    fetch.fetch('2512.23916', store.DATA)
            restored = OfflineBackend(folder, remote)
            self.assertEqual(restored.cache.get('2512.23916').source.html, html.decode('utf-8'))
            with store.use_backend(restored), mock.patch.object(store, 'DATA', Path(runtime)), \
                    mock.patch.object(restored, 'request_sync'), mock.patch.object(fetch, 'get', return_value=(b'<meta name="citation_title" content="Paper">', '')) as get:
                fetch.fetch('2512.23916', store.DATA)
                get.assert_called_once_with('https://arxiv.org/abs/2512.23916')
                self.assertEqual(restored.cache.get('2512.23916').meta['version'], 'v2')

    def test_engine_default_uses_selected_local_directory_in_cloud_mode(self):
        with tempfile.TemporaryDirectory() as folder, store.use_backend(OfflineBackend(folder, self.remote())), \
                mock.patch('textfold.storage_settings.active_path', return_value=Path(folder) / 'local-library'):
            self.assertEqual(engine.home(), Path(folder) / 'local-library' / 'engine')
