import os
import re

import pandas as pd
import requests
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

# Constants
GITHUB_API = "https://api.github.com"
TOKEN = os.getenv("GITHUB_TOKEN")  # Replace this with your GitHub token
HEADERS = {'Authorization': f'token {TOKEN}'}
session = requests.Session()
session.headers.update(HEADERS)

def extract_pr_files_content(owner, repo, pull_number, session):
    """Extract the content of changed files from a GitHub pull request."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pull_number}/files"
    response = session.get(url, headers={'Accept': 'application/vnd.github.v3.raw'})
    response.raise_for_status()
    files = response.json()
    result = {"prediction": None, "context": {}}

    for i, file_info in enumerate(files):
        file_url = file_info['raw_url']
        file_response = session.get(file_url)
        file_content = file_response.text

        if i == 0:
            result['prediction'] = file_content
        else:
            result['context'][file_info['filename']] = file_content

    return result

def get_repositories():
    query = (
        "language:python stars:1000..5000 forks:100..1000"
        " created:>=2018-01-01 license:mit is:public"
    )
    params = {
        'q': query,
        'sort': 'updated',
        'order': 'desc',
        'per_page': 100
    }
    response = requests.get(f"{GITHUB_API}/search/repositories", params=params)
    return response.json().get('items', [])


def fetch_issue_comments(issue_url):
    """Fetch the initial comment of an issue from its GitHub URL."""

    # Construct the API endpoint for comments from the given issue URL
    api_endpoint = issue_url.replace('https://github.com', GITHUB_API) + '/comments'

    # Use the session with headers to make the request
    response = session.get(api_endpoint)
    if response.status_code == 200:
        comments = response.json()
        if comments and isinstance(comments, list) and comments:
            # Return the body of the first comment if available
            return comments[0]['body']
        else:
            return "No comments"
    else:
        return f"Failed to fetch comments. Status code: {response.status_code}"


def fetch_issue_data(issue_number, repo):
    """Fetch all comments/discussions on the issue and include the first comment."""
    timeline_url = f"{GITHUB_API}/repos/{repo['owner']['login']}/{repo['name']}/issues/{issue_number}/timeline"
    comments_url = f"{GITHUB_API}/repos/{repo['owner']['login']}/{repo['name']}/issues/{issue_number}/comments"

    # Use a session to make requests
    with requests.Session() as session:
        session.headers.update({'Accept': 'application/vnd.github.mockingbird-preview'})

        # Fetch the timeline and comments concurrently if possible, or sequentially
        timeline_response = session.get(timeline_url)
        comments_response = session.get(comments_url)

        timeline_data = timeline_response.json()
        comments_data = comments_response.json()
        comments_body_string = ""

        # Iterate over each comment and append its body to the result string
        for comment in comments_data:
            comments_body_string += comment['body'] + "\n\n"  # Add two newlines for better readability between comments

        # return comments_body_string
        return timeline_data, comments_body_string


def process_issue(issue, repo):
    # Fetch discussions and the first comment
    discussions, comments= fetch_issue_data(issue['number'], repo)

    # Collect PR links
    pr_links = []
    fix_prs = []
    discussion_context =""
    counter = 0
    first_comment = ""
    pr_files_content = {}
    for event in discussions:
        if counter == 0:
            try:
                first_comment = event['body']
                counter += 1
            except:
                pass

        if counter>0:
            try:
                discussion_context += event['body']
                counter += 1
            except:
                pass

        if event.get('event') == 'referenced' and 'commit_id' in event:
            prs = fetch_pr_from_commit(event['commit_id'], repo)
            pr_links.extend(prs)
            for pr_link in prs:
                pr_number = pr_link.split('/')[-1]
                pr_content = extract_pr_files_content(repo['owner']['login'], repo['name'], pr_number, session)
                pr_files_content[pr_link] = pr_content
        if 'body' in event:
            # Pattern to capture "Fixed by #number" or "closed this as completed in #number"
            fixed_by_prs = re.findall(r"(?:Fixed by|closed this as completed in) #(\d+)", event['body'])
            fix_prs.extend(fixed_by_prs)

        # Optionally fetch details for PRs mentioned as fixing the issue
        for pr_number in fix_prs:
            pr_link = f"https://github.com/{repo['owner']['login']}/{repo['name']}/pull/{pr_number}"
            pr_links.append(pr_link)


    # Compile issue data
    issue_data = {
        'Issue URL': issue['html_url'],
        'Associated PRs': pr_links,
        'Issue Name': issue['title'],
        'Issue Text': issue['body'],
        'Context': str(comments),
        'PR Files Content': pr_files_content
    }
    print("Issue Data: ", issue_data)

    return pd.DataFrame([issue_data])


def fetch_pr_from_commit(commit_id, repo):
    """ Fetch pull requests associated with a commit """
    commit_url = f"{GITHUB_API}/repos/{repo['owner']['login']}/{repo['name']}/commits/{commit_id}/pulls"
    response = requests.get(commit_url, headers={'Accept': 'application/vnd.github.groot-preview+json'})
    pull_requests = response.json()
    return [pr['html_url'] for pr in pull_requests]  # Return a list of PR links



def check_issues(repo):
    all_issues_df = pd.DataFrame()  # Initialize an empty DataFrame
    issues_url = f"{GITHUB_API}/repos/{repo['owner']['login']}/{repo['name']}/issues"
    params = {'state': 'closed', 'labels': 'good first issue', 'per_page': 100, 'since': '2024-01-01T00:00:00Z'}
    response = session.get(issues_url, params=params)
    issues = response.json()

    for issue in issues:
        # print("Issue: ", issue)  # This will help you see what each 'issue' contains
        issue_df = process_issue(issue, repo)
        issue_df['Repository ID'] = repo['id']
        all_issues_df = pd.concat([all_issues_df, issue_df], ignore_index=True)

    return all_issues_df


def main(n):
    main_df = pd.DataFrame()
    rate_limit_status = requests.get('https://api.github.com/rate_limit', headers=HEADERS)
    print(rate_limit_status.json())
    repos = get_repositories()

    for i, repo in enumerate(repos):
        if i == n:
            break
        issues_df = check_issues(repo)
        main_df = pd.concat([main_df, issues_df], ignore_index=True)

    pd.set_option('display.max_columns', None)  # Show all columns
    pd.set_option('display.max_rows', None)  # Show all rows
    pd.set_option('display.max_colwidth', None)

    # print(main_df.head(10))
    return main_df.to_csv('issues.csv', index=False)

if __name__ == "__main__":
    main(n=50)