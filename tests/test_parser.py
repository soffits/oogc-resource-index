from __future__ import annotations

from oogc_resource_index.parser import extract_fid, parse_detail_page, parse_list_page, parse_total_count


def test_parse_list_page_deduplicates_fids() -> None:
    html = """
    <html><body>
      <a href="/zy/down-view?fid=42">First</a>
      <a href="/zy/down-view?fid=42">Duplicate</a>
      <a href="/zy/down-view?fid=43">Second</a>
    </body></html>
    """

    assert parse_list_page(html, "https://oogc.cc/zy/down-class") == [
        ("42", "First", "https://oogc.cc/zy/down-view?fid=42"),
        ("43", "Second", "https://oogc.cc/zy/down-view?fid=43"),
    ]


def test_parse_list_page_resolves_site_relative_detail_links() -> None:
    html = '<html><body><a href="zy/down-view-1500">Resource</a></body></html>'

    assert parse_list_page(html, "https://oogc.cc/zy/down-class") == [
        ("1500", "Resource", "https://oogc.cc/zy/down-view-1500"),
    ]


def test_parse_detail_page_extracts_metadata() -> None:
    html = """
    <html><head><title>Fallback</title></head><body>
      <h1>Resource Name</h1>
      <table>
        <tr><th>分类</th><td>Maps</td></tr>
        <tr><th>更新时间</th><td>2026-04-27</td></tr>
        <tr><th>大小</th><td>12 MB</td></tr>
      </table>
      <div class="description">Useful resource</div>
      <a href="/download/42">下载</a>
    </body></html>
    """

    record = parse_detail_page(html, "https://oogc.cc/zy/down-view?fid=42")

    assert record.fid == "42"
    assert record.title == "Resource Name"
    assert record.category == "Maps"
    assert record.updated_at == "2026-04-27"
    assert record.size == "12 MB"
    assert record.description == "Useful resource"
    assert record.downUrl == "https://oogc.cc/download/42"


def test_extract_fid_and_total_count() -> None:
    assert extract_fid("https://oogc.cc/zy/down-view?fid=123") == "123"
    assert extract_fid("/resource/456.html") == "456"
    assert parse_total_count("<div>共 9 条记录</div>") == 9
