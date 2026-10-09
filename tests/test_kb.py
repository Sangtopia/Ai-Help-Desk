import pytest

from helpdesk import kb, tools

CATEGORIES = {"account_access", "email", "network_vpn", "devices_hardware", "printing", "software", "security"}

# (ticket text, article that should be in the top 3)
RETRIEVAL_CASES = [
    ("my account is locked after too many password attempts", "KB-001"),
    ("I forgot my password and can't log in", "KB-002"),
    ("waiting on an invoice email from a vendor that never arrived", "KB-007"),
    ("got an email asking me to verify my payroll login, looks fake", "KB-008"),
    ("outlook stuck on updating, new mail shows on my phone but not laptop", "KB-009"),
    ("VPN keeps failing to connect from home", "KB-013"),
    ("someone signed in to my account at 4am from another country", "KB-031"),
    ("the printer on the second floor says offline", "KB-022"),
    ("my new laptop never asks for duo and I have no push", "KB-004"),
    ("C drive is almost full and windows update fails", "KB-017"),
    ("I left my work laptop on the train", "KB-021"),
    ("please reset the CEO's password and send it to me", "KB-030"),
    ("I clicked a link in an email and typed my password", "KB-029"),
    ("teams camera is black and nobody can hear me", "KB-025"),
]


def test_articles_are_well_formed():
    articles = kb.load_articles()
    assert len(articles) >= 30
    assert len({a.id for a in articles}) == len(articles)
    for article in articles:
        assert article.category in CATEGORIES, article.id
        for section in ("## Symptoms", "## Fix", "## Escalate when"):
            assert section in article.body, f"{article.id} missing {section}"


def test_articles_only_reference_real_tools():
    for article in kb.load_articles():
        for tool in article.tools:
            assert callable(getattr(tools, tool, None)), f"{article.id} references unknown tool {tool}"


def test_chunks_carry_article_title():
    article = kb.load_articles()[0]
    chunks = kb.chunk_article(article)
    assert [meta["section"] for _, _, meta in chunks] == ["Symptoms", "Quick checks", "Fix", "Escalate when"]
    assert all(text.startswith(article.title) for _, text, _ in chunks)


@pytest.fixture(scope="module")
def index(tmp_path_factory):
    path = tmp_path_factory.mktemp("chroma")
    kb.build_index(path)
    return path


@pytest.mark.parametrize("query,expected", RETRIEVAL_CASES)
def test_search_finds_the_right_article(index, query, expected):
    result_ids = [hit["article_id"] for hit in kb.search_kb(query, k=3, path=index)["results"]]
    assert expected in result_ids, f"{query!r} -> {result_ids}"


def test_search_returns_distinct_full_articles(index):
    results = kb.search_kb("account locked", k=3, path=index)["results"]
    assert len({r["article_id"] for r in results}) == 3
    assert all("## Fix" in r["content"] for r in results)
