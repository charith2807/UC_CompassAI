"""Infrastructure checks that also cover the ingestion handoff."""
import unittest
from pathlib import Path
from crawler import config

class IngestionMonitoringTests(unittest.TestCase):
    def test_rate_and_contact(self):
        self.assertGreaterEqual(config.MIN_DELAY_SECONDS,1)
        self.assertLessEqual(config.MAX_ACCEPTED_CRAWL_DELAY,10)
        self.assertIn('contact:',config.USER_AGENT)
    def test_scraped_data_and_credentials_ignored(self):
        text=Path('.gitignore').read_text()
        for rule in ['.env','data/raw/','data/processed/','data/index/']:
            self.assertIn(rule,text)
    def test_log_schemas(self):
        import csv
        for path,required in [('data/crawl_log.csv',{'url','action','reason'}),('data/seed_decisions.csv',{'url','decision','reason'})]:
            with Path(path).open() as handle:
                reader=csv.DictReader(handle)
                self.assertTrue(required.issubset(reader.fieldnames))
if __name__=='__main__':unittest.main()
