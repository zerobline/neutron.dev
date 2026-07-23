from app.crew.static_navigation import (
    NAVIGATION_CONTRACT,
    find_navigation_violations,
    find_project_navigation_violations,
)


def test_navigation_contract_mentions_required_patterns():
    assert "data-panel" in NAVIGATION_CONTRACT
    assert "data-tab" in NAVIGATION_CONTRACT
    assert "NEVER" in NAVIGATION_CONTRACT
    assert "root-relative" in NAVIGATION_CONTRACT


def test_find_navigation_violations_in_html_and_js():
    html = '<nav><a href="/transactions">Tx</a><iframe src="/dash"></iframe></nav>'
    js = (
        'location.href = "/transactions"; '
        'window.location = "/dashboard"; '
        'history.pushState({}, "", "/settings");'
    )

    assert "root-relative href" in find_navigation_violations(html, "index.html")[0]
    assert any("iframe" in item for item in find_navigation_violations(html, "index.html"))
    assert any("location" in item for item in find_navigation_violations(js, "app.js"))
    assert any("history" in item for item in find_navigation_violations(js, "app.js"))


def test_find_navigation_violations_allows_relative_assets():
    html = '<link rel="stylesheet" href="./styles.css"><script src="./app.js"></script>'
    js = "fetch('./data.json')"

    assert find_navigation_violations(html, "index.html") == []
    assert find_navigation_violations(js, "app.js") == []


def test_find_project_navigation_violations_collects_all_files():
    violations = find_project_navigation_violations({
        "index.html": '<a href="/dashboard">Dash</a>',
        "app.js": "location.assign('/settings');",
        "styles.css": "body { color: red; }",
    })

    assert len(violations) == 2
    assert any("index.html" in item for item in violations)
    assert any("app.js" in item for item in violations)