import os
import tempfile
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

APP=Path(__file__).resolve().parents[1]/'app.py'


class AppFlowTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.previous=os.environ.get('FBO_REVIEW_DIR')
        os.environ['FBO_REVIEW_DIR']=self.directory.name
        self.app=AppTest.from_file(str(APP),default_timeout=30).run()
        self.app.button[0].click().run()

    def tearDown(self):
        if self.previous is None:os.environ.pop('FBO_REVIEW_DIR',None)
        else:os.environ['FBO_REVIEW_DIR']=self.previous
        self.directory.cleanup()

    def element(self,kind,label):
        return next(x for x in getattr(self.app,kind) if x.label==label)

    def assert_clean(self):self.assertFalse(list(self.app.exception))

    def test_complete_plan_review_then_weather_change_stales_review(self):
        self.assert_clean()
        self.app.button(key='preview').click().run()
        self.assert_clean()
        self.element('text_area','Required review note').set_value('Synthetic UI verification: review only, no booking.')
        self.element('button','Save review').click().run()
        self.assert_clean()
        self.assertTrue(any('Review saved' in x.value for x in self.app.success))
        self.app.toggle(key='weather').set_value(True).run()
        self.app.slider(key='unavailable').set_value(5).run()
        self.app.slider(key='delay').set_value(4).run()
        self.assert_clean()
        self.assertTrue(any('Out of date' in x.value for x in self.app.warning))
        self.assertTrue(any('Weather what-if active' in x.value for x in self.app.caption))

    def test_source_switch_uses_latest_marvin_and_does_not_fake_shortage(self):
        self.app.selectbox(key='data_source').select("Marvin’s latest private-only case").run()
        self.assert_clean()
        self.assertTrue(any('fits within usable main-ramp' in x.value for x in self.app.markdown))
        self.app.radio(key='case').set_value('Higher demand').run()
        self.assert_clean()
        self.assertTrue(any('Marvin source + synthetic stays' in x.value for x in self.app.markdown))

    def test_review_requires_note(self):
        self.element('button','Save review').click().run()
        self.assertTrue(any('Add a review note' in x.value for x in self.app.error))

    def test_upload_empty_shows_instructions_not_fallback_metrics(self):
        self.app.selectbox(key='data_source').select('Upload visit CSV').run()
        self.assert_clean()
        self.assertTrue(any('No bookings loaded' in x.value for x in self.app.info))
        self.assertFalse(any('Peak shortfall:' in x.value for x in self.app.markdown))


if __name__=='__main__':unittest.main()
