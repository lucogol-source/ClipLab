"""Format a suggestion and verify approval using GitHub's REST issue and comment records."""
import hashlib
import json
import re
import sys

REPO = "lucogol-source/ClipLab"
OWNER_ID = 325669126
API = "https://api.github.com/repos/" + REPO
PREFIX = "[Suggerimento] "
FOOTER = "\n\nComando di approvazione per il proprietario\n\n"


def command(title, text):
    data = json.dumps([REPO, title, text], ensure_ascii=False, separators=(",", ":")).encode()
    return "/cliplab approva " + hashlib.sha256(data).hexdigest()


def issue_content(row):
    title = PREFIX + row["title"]
    description = row["description"]
    fence = "`" * max(3, 1 + max((len(run) for run in re.findall(r"`+", description)), default=0))
    literal = fence + "\n" + description + "\n" + fence
    text = (literal + "\n\n---\nClipLab V" + row["version"] + " · " + row["platform"]
            + "\nID proposta: " + row["id"])
    return {"title": title, "body": text + FOOTER + "`" + command(title, text) + "`"}


def approved(issue, comments):
    number = issue.get("number")
    url = f"{API}/issues/{number}"
    title = issue.get("title") or ""
    if (not isinstance(number, int) or issue.get("url") != url or issue.get("state") != "open"
            or "pull_request" in issue or not title.startswith(PREFIX)):
        return None
    text, separator, footer = (issue.get("body") or "").replace("\r\n", "\n").rpartition(FOOTER)
    expected = command(title, text)
    if (not separator or footer != f"`{expected}`" or
            not re.search(r"\nID proposta: [a-f0-9]{32}$", text)):
        return None
    latest = None
    for comment in sorted(comments, key=lambda entry: entry["id"]):
        user = comment.get("user") or {}
        if (comment.get("issue_url") != url or user.get("id") != OWNER_ID or
                user.get("login") != REPO.split("/")[0] or user.get("type") != "User" or
                comment.get("author_association") != "OWNER" or comment.get("performed_via_github_app") or
                not comment.get("created_at") or comment["created_at"] != comment.get("updated_at")):
            continue
        body = (comment.get("body") or "").strip()
        if body == "/cliplab revoca":
            latest = None
        if body == expected:
            latest = {"issue": number, "approval_id": comment["id"], "title": title[len(PREFIX):], "scope": text}
    return latest


if __name__ == "__main__":
    records = json.load(sys.stdin)
    print(json.dumps(approved(records["issue"], records["comments"]), ensure_ascii=False))
