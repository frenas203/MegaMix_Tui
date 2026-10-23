# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional file-browser boundary and real project creation after selection."""
import builtins
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from megamix.dialogs import choose_project_file, FileBrowserUnavailable
from megamix.engine import Engine
from megamix.terminal import Terminal
from megamix.tui import TUI, UserCancelled

class DialogTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="MegaMix file browser ")
        self.root=Path(self.temp.name)
        self.destination=self.root/"Åsa's new mix.json"
        self.tk=types.ModuleType('tkinter')
        self.tk.TclError=type('TclError',(Exception,),{})
        self.window=Mock()
        self.tk.Tk=Mock(return_value=self.window)
        self.dialog=Mock(return_value=str(self.destination))
        self.tk.filedialog=types.SimpleNamespace(asksaveasfilename=self.dialog)
    def tearDown(self):
        self.temp.cleanup()
    def chooser(self):
        return patch.dict(sys.modules,{'tkinter':self.tk,'tkinter.filedialog':self.tk.filedialog})
    def application(self,answers,project=None):
        answers=iter(answers)
        terminal=Terminal(no_clear=True,no_color=True,output=io.StringIO(),reader=lambda prompt:next(answers))
        return TUI(project,terminal)
    def test_save_dialog_selects_json_path_without_creating_a_file(self):
        with self.chooser():
            selected=choose_project_file(self.root)
        self.assertEqual(selected,self.destination)
        self.assertFalse(self.destination.exists())
        options=self.dialog.call_args.kwargs
        self.assertEqual(options['defaultextension'],'.json')
        self.assertEqual(options['initialdir'],str(self.root))
        self.assertEqual(options['filetypes'],[('MegaMix project','*.json')])
        self.window.withdraw.assert_called_once()
        self.window.destroy.assert_called_once()
    def test_all_cancel_return_types_close_the_window_without_creating_files(self):
        for cancelled in ['',None,()]:
            with self.subTest(cancelled=cancelled):
                self.dialog.return_value=cancelled
                self.window.reset_mock()
                with self.chooser():self.assertIsNone(choose_project_file())
                self.window.destroy.assert_called_once()
        self.assertEqual(list(self.root.iterdir()),[])
    def test_missing_tk_is_optional_and_has_actionable_error(self):
        real_import=builtins.__import__
        def importing(name,*args,**kwargs):
            if name=='tkinter':raise ImportError('Tk not installed')
            return real_import(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=importing):
            with self.assertRaisesRegex(FileBrowserUnavailable,'python3-tk'):
                choose_project_file()
    def test_missing_display_or_failed_dialog_becomes_fallback_error(self):
        self.tk.Tk.side_effect=self.tk.TclError('no display')
        with self.chooser(),self.assertRaisesRegex(FileBrowserUnavailable,'desktop session'):
            choose_project_file()
        self.tk.Tk.side_effect=None
        self.dialog.side_effect=self.tk.TclError('dialog failed')
        with self.chooser(),self.assertRaises(FileBrowserUnavailable):
            choose_project_file()
        self.window.destroy.assert_called_once()
    def test_file_extension_and_unsupported_topmost_option(self):
        self.window.attributes.side_effect=self.tk.TclError('unsupported attribute')
        for name,expected in [('New mix','New mix.json'),('New mix.v2','New mix.v2.json'),('New mix.JSON','New mix.JSON')]:
            with self.subTest(name=name):
                self.dialog.return_value=str(self.root/name)
                with self.chooser():result=choose_project_file(self.root/'missing-folder')
                self.assertEqual(result,self.root/expected)
    def test_browse_creates_project_with_filename_as_default_name(self):
        app=self.application(['',''])
        with patch('megamix.tui.choose_project_file',return_value=self.destination):
            app.dispatch('B')
        p=json.loads(self.destination.read_text(encoding='utf-8'))
        self.assertEqual(p['name'],"Åsa's new mix")
        self.assertEqual(app.path,self.destination)
        self.assertEqual(p['status'],'Draft')
    def test_cancel_preserves_open_project_and_does_not_prompt_for_name(self):
        old=self.root/'old.json'
        Engine(lambda _:None).action('New',old,{'name':'Existing compilation'})
        before=old.read_bytes()
        app=self.application([],old)
        with patch('megamix.tui.choose_project_file',return_value=None) as browser:
            with self.assertRaises(UserCancelled):app.dispatch('B')
        browser.assert_called_once_with(self.root)
        self.assertEqual(app.path,old)
        self.assertEqual(old.read_bytes(),before)
        self.assertFalse(self.destination.exists())
    def test_existing_destination_is_never_overwritten(self):
        self.destination.write_text('keep this file',encoding='utf-8')
        app=self.application([])
        with patch('megamix.tui.choose_project_file',return_value=self.destination):
            with self.assertRaisesRegex(ValueError,'already exists'):app.dispatch('B')
        self.assertEqual(self.destination.read_text(),'keep this file')
        self.assertIsNone(app.path)
    def test_unavailable_browser_falls_back_to_typed_path(self):
        app=self.application([str(self.destination),'Typed fallback',''])
        with patch('megamix.tui.choose_project_file',side_effect=FileBrowserUnavailable('No graphical display')):
            app.dispatch('B')
        self.assertEqual(json.loads(self.destination.read_text())['name'],'Typed fallback')
        self.assertEqual(app.path,self.destination)
    def test_failed_creation_preserves_previously_open_project(self):
        old=self.root/'old.json'
        app=self.application(['New name',''],old)
        with patch('megamix.tui.choose_project_file',return_value=self.destination),patch.object(app.engine,'action',side_effect=PermissionError('read only folder')):
            app.dispatch('B')
        self.assertEqual(app.path,old)
        self.assertFalse(self.destination.exists())
        self.assertIn('read only folder',app.notice)

if __name__=='__main__':
    unittest.main(verbosity=2)
