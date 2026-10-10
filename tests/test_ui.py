import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

@unittest.skipUnless(any(Path('data/processed').glob('*.json')), 'Private corpus not available; run UI smoke locally with the handoff data')
class UITests(unittest.TestCase):
    def test_mock_history_citations_and_refusal(self):
        app=AppTest.from_file(str(Path('app/streamlit_app.py')),default_timeout=30).run()
        self.assertFalse(app.exception)
        app.sidebar.selectbox[0].set_value('UI mock').run()
        app.chat_input[0].set_value('What is tuition?').run()
        self.assertFalse(app.exception)
        messages=app.session_state['messages']
        self.assertEqual(len(messages),2)
        self.assertTrue(messages[-1]['result']['citations'])
        app.chat_input[0].set_value('What is the Wi-Fi password?').run()
        self.assertTrue(app.session_state['messages'][-1]['result']['refused'])
        self.assertEqual(len(app.session_state['messages']),4)
        app.chat_input[0].set_value('Will I qualify for aid?').run()
        self.assertTrue(app.session_state['messages'][-1]['result']['referral'])
        self.assertFalse(app.exception)
if __name__=='__main__':unittest.main()
