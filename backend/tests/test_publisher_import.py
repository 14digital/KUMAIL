import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('publisher_import',Path(__file__).parents[2]/'scripts/import_publishers.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_import_parses_unicode_atom_and_approved_links():
    source=module.source_for('BBC Urdu','https://feeds.bbci.co.uk/urdu/rss.xml','Pakistan Urdu')
    xml='''<feed xmlns="http://www.w3.org/2005/Atom"><title>اردو</title><entry><title>خبر</title><link href="https://www.bbc.com/urdu/articles/test"/></entry></feed>'''.encode()
    result=module.inspect_feed(source,lambda *args:xml)
    assert result['approved_links']==1
    assert result['parse_warning'] is False


def test_html_and_empty_rss_are_not_enabled():
    source=module.source_for('Example','https://example.com/rss','global')
    for data in [b'<html><body>Sign in</body></html>',b'<rss version="2.0"><channel><title>Empty</title></channel></rss>']:
        with pytest.raises(ValueError):module.inspect_feed(source,lambda *args:data)


def test_unapproved_feed_links_are_not_enabled():
    source=module.source_for('Example','https://example.com/rss','global')
    data=b'<rss version="2.0"><channel><item><title>External</title><link>https://unapproved.example/article</link></item></channel></rss>'
    with pytest.raises(ValueError):module.inspect_feed(source,lambda *args:data)


def test_all_33_exact_feeds_are_unique():
    import json
    rows=json.loads((Path(__file__).parents[2]/'config/publisher-feeds.json').read_text())
    assert len(rows)==len({row[1] for row in rows})==33
    assert all(url.startswith('https://') for _,url,_ in rows)
