from src.ingestion.download_dvf import build_url, parse_years

INDEX_HTML = '''
<a href="../">../</a>
<a href="2021/">2021/</a>
<a href="2023/">2023/</a>
<a href="2022/">2022/</a>
<a href="README.txt">README.txt</a>
'''


def test_parse_years_sorted_and_filtered():
    assert parse_years(INDEX_HTML) == [2021, 2022, 2023]


def test_build_url_full_france():
    assert build_url(2024, base_url="https://x/") == "https://x/2024/full.csv.gz"


def test_build_url_departement():
    assert build_url(2024, "91", base_url="https://x/") == "https://x/2024/departements/91.csv.gz"


def test_parse_years_absolute_links_and_no_trailing_slash():
    html = '<a href="/geo-dvf/latest/csv/2024/">2024</a> <a href=\'2025\'>2025</a>'
    assert parse_years(html) == [2024, 2025]
